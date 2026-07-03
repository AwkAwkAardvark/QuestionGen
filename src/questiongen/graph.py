from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, cast

from langgraph.graph import END, START, StateGraph

from .config import (
    resolve_planner_elapsed_log_interval_seconds,
    resolve_planner_timeout_seconds,
    resolve_verbose_planner_logging,
)
from .designers import build_design
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
    _graph: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._graph = self._compile_graph()

    def invoke(self, state: QuestionState) -> QuestionState:
        working_state: QuestionState = {
            **state,
            "errors": list(state["errors"]),
        }
        final_state = cast(dict[str, Any], self._graph.invoke(working_state))
        final_state["errors"] = list(final_state["errors"])
        return cast(QuestionState, final_state)

    def _compile_graph(self) -> Any:
        workflow = StateGraph(QuestionState)

        workflow.add_node("input_check", self._run_input_check)
        workflow.add_node("prepare_source", self._run_prepare_source)
        workflow.add_node("source_check", self._run_source_check)
        workflow.add_node("design", self._run_design)
        workflow.add_node("planner", self._run_planner)
        workflow.add_node("plan_check", self._run_plan_check)
        workflow.add_node("render", self._run_render)
        workflow.add_node("build_explanation_context", self._run_build_explanation_context)
        workflow.add_node("write_explanation", self._run_write_explanation)
        workflow.add_node("validate_generated_question", self._run_validate_generated_question)

        workflow.add_edge(START, "input_check")
        workflow.add_conditional_edges(
            "input_check",
            lambda state: "prepare_source" if state["status"] == "input_passed" else END,
        )
        workflow.add_conditional_edges(
            "prepare_source",
            lambda state: "source_check" if state["status"] == "source_prepared" else END,
        )
        workflow.add_conditional_edges(
            "source_check",
            lambda state: "design" if state["status"] == "source_passed" else END,
        )
        workflow.add_conditional_edges(
            "design",
            lambda state: "planner" if state["status"] == "source_passed" else END,
        )
        workflow.add_conditional_edges(
            "planner",
            lambda state: "plan_check" if state["status"] == "planned" else END,
        )
        workflow.add_conditional_edges(
            "plan_check",
            lambda state: "render" if state["status"] == "planned" else END,
        )
        workflow.add_conditional_edges(
            "render",
            lambda state: "build_explanation_context" if state["status"] == "rendered" else END,
        )
        workflow.add_conditional_edges(
            "build_explanation_context",
            lambda state: "write_explanation" if state["status"] == "rendered" else END,
        )
        workflow.add_conditional_edges(
            "write_explanation",
            lambda state: "validate_generated_question" if state["status"] == "rendered" else END,
        )
        workflow.add_edge("validate_generated_question", END)

        return workflow.compile()

    def _run_input_check(self, state: QuestionState) -> NodeResult:
        return self._run_stage(
            state,
            stage_name="input_check",
            type_spec=None,
            operation=lambda working_state, _type_spec: input_check(working_state, self.question_types),
        )

    def _run_prepare_source(self, state: QuestionState) -> NodeResult:
        return self._run_stage(
            state,
            stage_name="prepare_source",
            type_spec=None,
            operation=lambda working_state, _type_spec: {
                "prepared_source": prepare_source(working_state["source_paragraph"]),
                "status": "source_prepared",
                "errors": [],
            },
        )

    def _run_source_check(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return self._run_stage(
                state,
                stage_name="source_check",
                type_spec=None,
                operation=lambda _working_state, _resolved_type_spec: error_result,
            )
        assert type_spec is not None
        return self._run_stage(
            state,
            stage_name="source_check",
            type_spec=type_spec,
            operation=lambda working_state, resolved_type_spec: source_check(working_state, resolved_type_spec),
        )

    def _run_design(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return error_result
        assert type_spec is not None
        return self._run_stage(
            state,
            stage_name="design",
            type_spec=type_spec,
            operation=lambda working_state, resolved_type_spec: build_design(working_state, resolved_type_spec),
        )

    def _run_planner(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return error_result
        assert type_spec is not None
        planner = PLANNERS[type_spec.renderer_key]
        return self._run_stage(
            state,
            stage_name="planner",
            type_spec=type_spec,
            operation=lambda working_state, resolved_type_spec: planner(
                working_state,
                resolved_type_spec,
                self.structured_llm_factory,
                self.runtime_logger,
                self.planner_timeout_seconds,
                self.planner_elapsed_log_interval_seconds,
            ),
        )

    def _run_plan_check(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return error_result
        assert type_spec is not None
        return self._run_stage(
            state,
            stage_name="plan_check",
            type_spec=type_spec,
            operation=lambda working_state, resolved_type_spec: plan_check(working_state, resolved_type_spec),
        )

    def _run_render(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return error_result
        assert type_spec is not None
        renderer = RENDERERS[type_spec.renderer_key]
        return self._run_stage(
            state,
            stage_name="render",
            type_spec=type_spec,
            operation=lambda working_state, resolved_type_spec: renderer(working_state, resolved_type_spec),
        )

    def _run_build_explanation_context(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return error_result
        assert type_spec is not None
        return self._run_stage(
            state,
            stage_name="build_explanation_context",
            type_spec=type_spec,
            operation=lambda working_state, _resolved_type_spec: build_explanation_context(working_state),
        )

    def _run_write_explanation(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return error_result
        assert type_spec is not None
        return self._run_stage(
            state,
            stage_name="write_explanation",
            type_spec=type_spec,
            operation=lambda working_state, _resolved_type_spec: write_teacher_facing_explanation(working_state),
        )

    def _run_validate_generated_question(self, state: QuestionState) -> NodeResult:
        type_spec, error_result = self._resolve_type_spec(state)
        if error_result is not None:
            return error_result
        assert type_spec is not None
        return self._run_stage(
            state,
            stage_name="validate_generated_question",
            type_spec=type_spec,
            operation=lambda working_state, resolved_type_spec: validate_generated_question(
                working_state, resolved_type_spec
            ),
        )

    def _run_stage(
        self,
        state: QuestionState,
        *,
        stage_name: str,
        type_spec: QuestionTypeSpec | None,
        operation: Callable[[QuestionState, QuestionTypeSpec | None], NodeResult],
    ) -> NodeResult:
        working_state: QuestionState = {
            **state,
            "errors": list(state["errors"]),
        }
        self._log_stage(working_state, stage_name, "start", type_spec)
        result = operation(working_state, type_spec)
        self._apply_result(working_state, result)
        self._log_stage(working_state, stage_name, "finish", type_spec)
        return result

    def _resolve_type_spec(self, state: QuestionState) -> tuple[QuestionTypeSpec | None, NodeResult | None]:
        question_subtype_key = state.get("QuestionSubtypeKey")
        type_spec = self.question_types.get(question_subtype_key or "")
        if type_spec is not None:
            return type_spec, None

        resolved = resolve_question_type_spec(
            state["QuestionTypeKey"],
            question_subtype_key,
        )
        if resolved is not None:
            return resolved, None

        return None, {
            "status": "input_error",
            "errors": [f"Unknown subtype for {state['QuestionTypeKey']}: {question_subtype_key}"],
        }

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
