from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Protocol, Sequence

from .exporters import write_results_csv, write_results_markdown
from .planners import (
    PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR,
    classify_planner_error,
    is_quota_planning_error,
    normalize_planner_error,
)
from .question_types import QUESTION_TYPES
from .schemas import BatchInputRow, BatchResultRow, GeneratedQuestion, QuestionState, make_initial_state


class RunnerProtocol(Protocol):
    def invoke(self, state: QuestionState) -> QuestionState:
        ...


def run_batch_rows(
    rows: Iterable[BatchInputRow],
    question_type_keys: Sequence[str],
    runner: RunnerProtocol,
) -> list[BatchResultRow]:
    _ensure_runner(runner)
    results: list[BatchResultRow] = []
    quota_exhausted = False

    for row in rows:
        input_row = row if isinstance(row, BatchInputRow) else BatchInputRow.model_validate(row)
        for question_type_key in question_type_keys:
            state = make_initial_state(
                source_paragraph=input_row.source_paragraph,
                original_question_number=input_row.OriginalQuestionNumber,
                batch_row_id=input_row.BatchRowId,
                question_type_key=question_type_key,
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

    return results


def run_batch_dataframe(df: object, question_type_keys: Sequence[str], runner: RunnerProtocol) -> object:
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("pandas is required for run_batch_dataframe().") from exc

    records = df.to_dict(orient="records")
    rows = [
        BatchInputRow.model_validate(_coerce_tabular_row(record, batch_row_id=index))
        for index, record in enumerate(records)
    ]
    results = run_batch_rows(rows, question_type_keys, runner)
    return pd.DataFrame([result.model_dump() for result in results])


def run_batch_files(
    input_csv: str | Path,
    output_csv: str | Path,
    question_type_keys: Sequence[str],
    runner: RunnerProtocol,
    output_markdown: str | Path | None = None,
) -> list[BatchResultRow]:
    rows: list[BatchInputRow] = []
    with Path(input_csv).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, raw_row in enumerate(reader):
            rows.append(BatchInputRow.model_validate(_coerce_tabular_row(raw_row, batch_row_id=index)))

    results = run_batch_rows(rows, question_type_keys, runner)
    write_results_csv(results, output_csv)
    if output_markdown is not None:
        write_results_markdown(results, output_markdown)
    return results


def _ensure_runner(runner: object) -> None:
    if runner is None or not callable(getattr(runner, "invoke", None)):
        raise ValueError("runner must be an invoke-capable compiled graph or equivalent object.")


def _coerce_tabular_row(row: dict[str, object], *, batch_row_id: int) -> dict[str, object]:
    payload = dict(row)
    payload["BatchRowId"] = payload.get("BatchRowId", batch_row_id)
    return payload


def _state_to_result_row(state: QuestionState) -> BatchResultRow:
    question_type_key = state["QuestionTypeKey"]
    type_spec = QUESTION_TYPES.get(question_type_key)
    generated = state["generated"]
    generated_payload = generated if isinstance(generated, GeneratedQuestion) else None

    return BatchResultRow(
        OriginalQuestionNumber=state["OriginalQuestionNumber"],
        BatchRowId=state["BatchRowId"],
        QuestionTypeKey=question_type_key,
        QuestionType=generated_payload.QuestionType if generated_payload else (type_spec.label_ko if type_spec else None),
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
