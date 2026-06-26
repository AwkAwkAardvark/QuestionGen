from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .config import (
    resolve_planner_elapsed_log_interval_seconds,
    resolve_planner_timeout_seconds,
    resolve_verbose_planner_logging,
)
from .explanations import build_explanation_context, write_teacher_facing_explanation
from .parsers import prepare_source
from .planners import PLANNERS, RuntimeEventLogger, StructuredLLMFactory
from .question_types import QUESTION_SUBTYPE_SPECS, QuestionTypeSpec, resolve_question_type_spec
from .renderers import RENDERERS
from .schemas import QuestionState
from .validators import input_check, plan_check, source_check, validate_generated_question

NodeResult = dict[str, Any]


@dataclass(slots=True)
class LocalQuestionGraphRunner:
    question_types: Mapping[str, QuestionTypeSpec]
    structured_llm_factory: StructuredLLMFactory | None = None
    runtime_logger: RuntimeEventLogger | None = None
    planner_timeout_seconds: float | None = None
    planner_elapsed_log_interval_seconds: float = 30.0

    def invoke(self, state: QuestionState) -> QuestionState:
        working_state: QuestionState = {
            **state,
            "errors": list(state["errors"]),
        }

        self._log_stage(working_state, "input_check", "start")
        self._apply_result(working_state, input_check(working_state, self.question_types))
        self._log_stage(working_state, "input_check", "finish")
        if working_state["status"] != "input_passed":
            return working_state

        self._log_stage(working_state, "prepare_source", "start")
        prepared = prepare_source(working_state["source_paragraph"])
        self._apply_result(
            working_state,
            {
                "prepared_source": prepared,
                "status": "source_prepared",
                "errors": [],
            },
        )
        self._log_stage(working_state, "prepare_source", "finish")

        question_subtype_key = working_state.get("QuestionSubtypeKey")
        type_spec = self.question_types.get(question_subtype_key or "")
        if type_spec is None:
            resolved = resolve_question_type_spec(
                working_state["QuestionTypeKey"],
                question_subtype_key,
            )
            if resolved is None:
                return {
                    **working_state,
                    "status": "input_error",
                    "errors": [
                        f"Unknown subtype for {working_state['QuestionTypeKey']}: {question_subtype_key}"
                    ],
                }
            type_spec = resolved
        self._log_stage(working_state, "source_check", "start", type_spec)
        self._apply_result(working_state, source_check(working_state, type_spec))
        self._log_stage(working_state, "source_check", "finish", type_spec)
        if working_state["status"] != "source_passed":
            return working_state

        planner = PLANNERS[type_spec.renderer_key]
        self._log_stage(working_state, "planner", "start", type_spec)
        self._apply_result(
            working_state,
            planner(
                working_state,
                type_spec,
                self.structured_llm_factory,
                self.runtime_logger,
                self.planner_timeout_seconds,
                self.planner_elapsed_log_interval_seconds,
            ),
        )
        self._log_stage(working_state, "planner", "finish", type_spec)
        if working_state["status"] != "planned":
            return working_state

        self._log_stage(working_state, "plan_check", "start", type_spec)
        self._apply_result(working_state, plan_check(working_state, type_spec))
        self._log_stage(working_state, "plan_check", "finish", type_spec)
        if working_state["status"] != "planned":
            return working_state

        renderer = RENDERERS[type_spec.renderer_key]
        self._log_stage(working_state, "render", "start", type_spec)
        self._apply_result(working_state, renderer(working_state, type_spec))
        self._log_stage(working_state, "render", "finish", type_spec)
        if working_state["status"] != "rendered":
            return working_state

        self._log_stage(working_state, "build_explanation_context", "start", type_spec)
        self._apply_result(working_state, build_explanation_context(working_state))
        self._log_stage(working_state, "build_explanation_context", "finish", type_spec)
        if working_state["status"] != "rendered":
            return working_state

        self._log_stage(working_state, "write_explanation", "start", type_spec)
        self._apply_result(working_state, write_teacher_facing_explanation(working_state))
        self._log_stage(working_state, "write_explanation", "finish", type_spec)
        if working_state["status"] != "rendered":
            return working_state

        self._log_stage(working_state, "validate_generated_question", "start", type_spec)
        self._apply_result(working_state, validate_generated_question(working_state, type_spec))
        self._log_stage(working_state, "validate_generated_question", "finish", type_spec)
        return working_state

    @staticmethod
    def _apply_result(state: QuestionState, result: NodeResult) -> None:
        for key, value in result.items():
            state[key] = value

    def _log_stage(
        self,
        state: QuestionState,
        stage_name: str,
        phase: str,
        type_spec: QuestionTypeSpec | None = None,
    ) -> None:
        if self.runtime_logger is None:
            return
        row_label = state["OriginalQuestionNumber"] or f"row {state['BatchRowId']}"
        subtype_label = (
            (type_spec.subtype_key if type_spec is not None else None)
            or state.get("QuestionSubtypeKey")
            or state["QuestionTypeKey"]
        )
        self.runtime_logger(
            f"[graph] {row_label} / {subtype_label} | {stage_name} {phase} | status={state['status']}"
        )


def compile_question_graph(
    *,
    structured_llm_factory: StructuredLLMFactory | None = None,
    question_types: Mapping[str, QuestionTypeSpec] | None = None,
    runtime_logger: RuntimeEventLogger | None = None,
    verbose_runtime: bool | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float | None = None,
) -> LocalQuestionGraphRunner:
    logging_enabled = resolve_verbose_planner_logging(verbose_runtime)
    if runtime_logger is not None and verbose_runtime is None:
        logging_enabled = True
    active_runtime_logger = runtime_logger if logging_enabled else None
    if active_runtime_logger is None and logging_enabled:
        active_runtime_logger = print
    return LocalQuestionGraphRunner(
        question_types=question_types or QUESTION_SUBTYPE_SPECS,
        structured_llm_factory=structured_llm_factory,
        runtime_logger=active_runtime_logger,
        planner_timeout_seconds=resolve_planner_timeout_seconds(planner_timeout_seconds),
        planner_elapsed_log_interval_seconds=resolve_planner_elapsed_log_interval_seconds(
            planner_elapsed_log_interval_seconds
        ),
    )
