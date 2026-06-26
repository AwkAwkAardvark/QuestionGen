from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal, Protocol, Sequence

from .exporters import write_results_csv, write_results_markdown
from .planners import (
    PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR,
    classify_planner_error,
    is_quota_planning_error,
    normalize_planner_error,
)
from .question_types import QUESTION_FAMILY_SPECS, QUESTION_TYPE_SPECS_BY_FAMILY, QUESTION_TYPES, expand_question_type_keys
from .schemas import BatchInputRow, BatchResultRow, GeneratedQuestion, QuestionState, make_initial_state


@dataclass(frozen=True)
class BatchProgressUpdate:
    event: Literal["started", "item_started", "item_completed", "completed"]
    completed_items: int
    total_items: int
    current_row_number: str | None = None
    batch_row_id: int | None = None
    question_type_key: str | None = None
    question_subtype_key: str | None = None
    status: str | None = None
    message: str | None = None


BatchProgressCallback = Callable[[BatchProgressUpdate], None]


class RunnerProtocol(Protocol):
    def invoke(self, state: QuestionState) -> QuestionState:
        ...


def run_batch_rows(
    rows: Iterable[BatchInputRow],
    question_type_keys: Sequence[str],
    runner: RunnerProtocol,
    progress_callback: BatchProgressCallback | None = None,
) -> list[BatchResultRow]:
    _ensure_runner(runner)
    results: list[BatchResultRow] = []
    quota_exhausted = False
    concrete_specs = expand_question_type_keys(list(question_type_keys))
    unknown_question_type_keys = [key for key in question_type_keys if key not in QUESTION_TYPE_SPECS_BY_FAMILY]
    validated_rows = [
        row if isinstance(row, BatchInputRow) else BatchInputRow.model_validate(row)
        for row in rows
    ]
    total_items = len(validated_rows) * (len(concrete_specs) + len(unknown_question_type_keys))
    completed_items = 0

    _emit_progress(
        progress_callback,
        BatchProgressUpdate(
            event="started",
            completed_items=0,
            total_items=total_items,
            message=(
                f"Starting batch run for {len(validated_rows)} input rows across "
                f"{len(concrete_specs)} concrete question subtypes."
            ),
        ),
    )

    for input_row in validated_rows:
        for type_spec in concrete_specs:
            _emit_progress(
                progress_callback,
                BatchProgressUpdate(
                    event="item_started",
                    completed_items=completed_items,
                    total_items=total_items,
                    current_row_number=input_row.OriginalQuestionNumber,
                    batch_row_id=input_row.BatchRowId,
                    question_type_key=type_spec.family_key,
                    question_subtype_key=type_spec.subtype_key,
                    status="running",
                    message="Generating question.",
                ),
            )
            state = make_initial_state(
                source_paragraph=input_row.source_paragraph,
                original_question_number=input_row.OriginalQuestionNumber,
                batch_row_id=input_row.BatchRowId,
                question_type_key=type_spec.family_key,
                question_format_key=type_spec.format_key,
                question_subtype_key=type_spec.subtype_key,
            )
            if quota_exhausted:
                results.append(
                    _state_to_result_row(
                        {
                            **state,
                            "status": "planning_error",
                            "errors": [PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR],
                        }
                    )
                )
                completed_items += 1
                _emit_progress(
                    progress_callback,
                    BatchProgressUpdate(
                        event="item_completed",
                        completed_items=completed_items,
                        total_items=total_items,
                        current_row_number=input_row.OriginalQuestionNumber,
                        batch_row_id=input_row.BatchRowId,
                        question_type_key=type_spec.family_key,
                        question_subtype_key=type_spec.subtype_key,
                        status="planning_error",
                        message=PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR,
                    ),
                )
                continue
            try:
                final_state = runner.invoke(state)
            except Exception as exc:
                if classify_planner_error(exc) == "service_quota":
                    errors = [normalize_planner_error(exc)]
                else:
                    errors = [f"Runner invocation failed: {exc}"]
                final_state = {
                    **state,
                    "status": "planning_error",
                    "errors": errors,
                }
            if final_state["status"] == "planning_error" and is_quota_planning_error(final_state["errors"]):
                quota_exhausted = True
            results.append(_state_to_result_row(final_state))
            completed_items += 1
            _emit_progress(
                progress_callback,
                BatchProgressUpdate(
                    event="item_completed",
                    completed_items=completed_items,
                    total_items=total_items,
                    current_row_number=input_row.OriginalQuestionNumber,
                    batch_row_id=input_row.BatchRowId,
                    question_type_key=type_spec.family_key,
                    question_subtype_key=type_spec.subtype_key,
                    status=final_state["status"],
                    message=(final_state["errors"][0] if final_state["errors"] else None),
                ),
            )
        for question_type_key in unknown_question_type_keys:
            _emit_progress(
                progress_callback,
                BatchProgressUpdate(
                    event="item_started",
                    completed_items=completed_items,
                    total_items=total_items,
                    current_row_number=input_row.OriginalQuestionNumber,
                    batch_row_id=input_row.BatchRowId,
                    question_type_key=question_type_key,
                    status="running",
                    message="Validating requested question type.",
                ),
            )
            results.append(
                _state_to_result_row(
                    {
                        **make_initial_state(
                            source_paragraph=input_row.source_paragraph,
                            original_question_number=input_row.OriginalQuestionNumber,
                            batch_row_id=input_row.BatchRowId,
                            question_type_key=question_type_key,
                        ),
                        "status": "input_error",
                        "errors": [f"Unknown QuestionTypeKey: {question_type_key}"],
                    }
                )
            )
            completed_items += 1
            _emit_progress(
                progress_callback,
                BatchProgressUpdate(
                    event="item_completed",
                    completed_items=completed_items,
                    total_items=total_items,
                    current_row_number=input_row.OriginalQuestionNumber,
                    batch_row_id=input_row.BatchRowId,
                    question_type_key=question_type_key,
                    status="input_error",
                    message=f"Unknown QuestionTypeKey: {question_type_key}",
                ),
            )

    _emit_progress(
        progress_callback,
        BatchProgressUpdate(
            event="completed",
            completed_items=completed_items,
            total_items=total_items,
            message=f"Completed batch run with {len(results)} exported rows.",
        ),
    )

    return results


def run_batch_dataframe(
    df: object,
    question_type_keys: Sequence[str],
    runner: RunnerProtocol,
    progress_callback: BatchProgressCallback | None = None,
) -> object:
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("pandas is required for run_batch_dataframe().") from exc

    records = df.to_dict(orient="records")
    rows = [
        BatchInputRow.model_validate(_coerce_tabular_row(record, batch_row_id=index))
        for index, record in enumerate(records)
    ]
    results = run_batch_rows(rows, question_type_keys, runner, progress_callback=progress_callback)
    return pd.DataFrame([result.model_dump() for result in results])


def run_batch_files(
    input_csv: str | Path,
    output_csv: str | Path,
    question_type_keys: Sequence[str],
    runner: RunnerProtocol,
    output_markdown: str | Path | None = None,
    progress_callback: BatchProgressCallback | None = None,
) -> list[BatchResultRow]:
    rows: list[BatchInputRow] = []
    with Path(input_csv).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, raw_row in enumerate(reader):
            rows.append(BatchInputRow.model_validate(_coerce_tabular_row(raw_row, batch_row_id=index)))

    results = run_batch_rows(rows, question_type_keys, runner, progress_callback=progress_callback)
    write_results_csv(results, output_csv)
    if output_markdown is not None:
        write_results_markdown(results, output_markdown)
    return results


def _emit_progress(
    progress_callback: BatchProgressCallback | None,
    update: BatchProgressUpdate,
) -> None:
    if progress_callback is None:
        return
    progress_callback(update)


def _ensure_runner(runner: object) -> None:
    if runner is None or not callable(getattr(runner, "invoke", None)):
        raise ValueError("runner must be an invoke-capable compiled graph or equivalent object.")


def _coerce_tabular_row(row: dict[str, object], *, batch_row_id: int) -> dict[str, object]:
    payload = dict(row)
    payload["BatchRowId"] = payload.get("BatchRowId", batch_row_id)
    return payload


def _state_to_result_row(state: QuestionState) -> BatchResultRow:
    question_type_key = state["QuestionTypeKey"]
    type_spec = next(
        (
            spec
            for spec in QUESTION_TYPE_SPECS_BY_FAMILY.get(question_type_key, ())
            if spec.subtype_key == state["QuestionSubtypeKey"]
        ),
        None,
    )
    family_spec = QUESTION_TYPES.get(question_type_key) or QUESTION_FAMILY_SPECS.get(question_type_key)
    generated = state["generated"]
    generated_payload = generated if isinstance(generated, GeneratedQuestion) else None

    return BatchResultRow(
        OriginalQuestionNumber=state["OriginalQuestionNumber"],
        BatchRowId=state["BatchRowId"],
        QuestionTypeKey=question_type_key,
        QuestionFormatKey=(
            generated_payload.QuestionFormatKey if generated_payload else (type_spec.format_key if type_spec else state["QuestionFormatKey"])
        ),
        QuestionSubtypeKey=(
            generated_payload.QuestionSubtypeKey if generated_payload else (type_spec.subtype_key if type_spec else state["QuestionSubtypeKey"])
        ),
        QuestionSubtype=(
            generated_payload.QuestionSubtype if generated_payload else (type_spec.subtype_label_ko if type_spec else None)
        ),
        QuestionType=generated_payload.QuestionType if generated_payload else (family_spec.label_ko if family_spec else None),
        status=state["status"],
        errors=list(state["errors"]),
        source_paragraph=state["source_paragraph"],
        student_paragraph=generated_payload.student_paragraph if generated_payload else None,
        question_stem=generated_payload.question_stem if generated_payload else None,
        given_sentence=generated_payload.given_sentence if generated_payload else None,
        choices=generated_payload.choices if generated_payload else None,
        answer=generated_payload.answer if generated_payload else None,
        explanation=generated_payload.explanation if generated_payload else None,
    )
