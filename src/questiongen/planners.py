from __future__ import annotations

import inspect
import threading
import time
from typing import Any, Callable, Iterable, Literal

from .config import create_structured_llm
from .designers import build_design, hydrate_plan_from_draft
from .prompts import (
    build_fill_in_the_blank_semantic_adjudication_prompt,
    build_fill_in_the_blank_prompt,
    build_fill_in_the_blank_repair_prompt,
    build_grammar_prompt,
    build_grammar_repair_prompt,
    build_mood_atmosphere_prompt,
    build_mood_atmosphere_repair_prompt,
    build_paragraph_ordering_prompt,
    build_paragraph_ordering_repair_prompt,
    build_sentence_insertion_prompt,
    build_sentence_insertion_repair_prompt,
    build_underlined_phrase_meaning_prompt,
    build_underlined_phrase_meaning_repair_prompt,
    build_vocab_prompt,
    build_vocab_repair_prompt,
)
from .question_types import QuestionTypeSpec
from .schemas import (
    BaseModel,
    FillInTheBlankDesign,
    FillInTheBlankPlan,
    PreparedSource,
    QuestionState,
    coerce_model,
)
from .validators import validate_plan_against_prepared_source

StructuredLLMFactory = Callable[..., Any]
RuntimeEventLogger = Callable[[str], None]
MAX_PLANNER_ATTEMPTS = 2
PLANNER_MODEL_ROLE = "planner"
LIGHT_MODEL_ROLE = "light"
_TIER1_SEMANTIC_ADJUDICATION_SUBTYPE_KEYS = frozenset(
    {
        "blank_inference_proposition_5_choices",
        "blank_summary_completion_5_choices",
    }
)
PLANNER_QUOTA_EXHAUSTED_ERROR = "Planner service failed: upstream LLM quota exhausted (insufficient_quota)."
PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR = (
    "Planner service failed: upstream LLM quota exhausted (insufficient_quota); "
    "skipped after earlier quota failure in this batch."
)
_PLANNER_SERVICE_ERROR_MARKERS = (
    "error code:",
    "apiconnectionerror",
    "apitimeouterror",
    "authenticationerror",
    "permissiondeniederror",
    "notfounderror",
    "internalservererror",
    "serviceunavailable",
    "ratelimiterror",
)


class PlannerTimeoutError(TimeoutError):
    def __init__(self, *, timeout_seconds: float, context_label: str, attempt_number: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.context_label = context_label
        self.attempt_number = attempt_number
        super().__init__(
            f"Planner timed out after {timeout_seconds:.1f}s for {context_label} "
            f"on attempt {attempt_number}."
        )


class PlannerSemanticAdjudicationResult(BaseModel):
    fits_discourse_role: bool
    visible_frame_semantically_valid: bool
    failure_reason: str | None = None


def classify_planner_error(exc: BaseException) -> Literal["service_quota", "service", "planner"]:
    error_text = _normalized_exception_text(exc).lower()
    if "insufficient_quota" in error_text:
        return "service_quota"
    if any(marker in error_text for marker in _PLANNER_SERVICE_ERROR_MARKERS):
        return "service"
    return "planner"


def normalize_planner_error(exc: BaseException) -> str:
    if isinstance(exc, PlannerTimeoutError):
        return str(exc)
    failure_kind = classify_planner_error(exc)
    if failure_kind == "service_quota":
        return PLANNER_QUOTA_EXHAUSTED_ERROR
    error_text = _normalized_exception_text(exc)
    if failure_kind == "service":
        return f"Planner service failed: {error_text}"
    return f"Planner failed: {error_text}"


def is_quota_planning_error(errors: Iterable[str]) -> bool:
    return any("insufficient_quota" in error.lower() for error in errors)


def _normalized_exception_text(exc: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        message = " ".join(str(current).split())
        if message:
            messages.append(message)
        current = current.__cause__ or current.__context__

    if not messages:
        return exc.__class__.__name__
    return " | ".join(messages)


def _run_planner_with_repair(
    *,
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    base_prompt: str,
    repair_prompt_builder: Callable[..., str],
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    planner = _build_structured_llm(
        structured_llm_factory=structured_llm_factory,
        output_schema=type_spec.draft_schema,
        model_role=PLANNER_MODEL_ROLE,
        request_timeout_seconds=planner_timeout_seconds,
    )
    current_prompt = base_prompt
    last_exc: Exception | None = None
    context_label = _planner_context_label(state, type_spec)

    for attempt in range(MAX_PLANNER_ATTEMPTS):
        attempt_number = attempt + 1
        prompt_kind = "repair" if attempt > 0 else "initial"
        _log_runtime_event(
            runtime_logger,
            f"[planner] {context_label} | attempt {attempt_number}/{MAX_PLANNER_ATTEMPTS} start ({prompt_kind})",
        )
        attempt_started_at = time.monotonic()
        try:
            raw_draft = _invoke_planner_with_timeout(
                planner=planner,
                prompt=current_prompt,
                timeout_seconds=planner_timeout_seconds,
                elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
                runtime_logger=runtime_logger,
                context_label=context_label,
                attempt_number=attempt_number,
            )
            attempt_elapsed = time.monotonic() - attempt_started_at
            draft = coerce_model(raw_draft, type_spec.draft_schema)
            plan = hydrate_plan_from_draft(
                design=state.get("design"),
                draft=draft,
                type_spec=type_spec,
            )
            prepared_source = state["prepared_source"]
            if prepared_source is not None:
                deterministic_errors = validate_plan_against_prepared_source(
                    prepared_source,
                    plan,
                    type_spec,
                    design=state.get("design"),
                )
                if deterministic_errors:
                    last_exc = RuntimeError("; ".join(deterministic_errors))
                    _log_runtime_event(
                        runtime_logger,
                        f"[planner] {context_label} | attempt {attempt_number}/{MAX_PLANNER_ATTEMPTS} "
                        f"failed deterministic plan check in {attempt_elapsed:.1f}s: "
                        f"{_single_line_summary('; '.join(deterministic_errors))}",
                    )
                    if attempt + 1 >= MAX_PLANNER_ATTEMPTS:
                        break
                    _log_runtime_event(
                        runtime_logger,
                        f"[planner] {context_label} | retrying with repair prompt after attempt "
                        f"{attempt_number}/{MAX_PLANNER_ATTEMPTS}",
                    )
                    current_prompt = repair_prompt_builder(
                        base_prompt=base_prompt,
                        previous_error="; ".join(deterministic_errors),
                    )
                    continue
            _log_runtime_event(
                runtime_logger,
                f"[planner] {context_label} | attempt {attempt_number}/{MAX_PLANNER_ATTEMPTS} "
                f"finished in {attempt_elapsed:.1f}s",
            )
            return {
                "plan": plan,
                "status": "planned",
                "errors": [],
            }
        except Exception as exc:
            last_exc = exc
            attempt_elapsed = time.monotonic() - attempt_started_at
            if isinstance(exc, PlannerTimeoutError):
                _log_runtime_event(
                    runtime_logger,
                    f"[planner] {context_label} | attempt {attempt_number}/{MAX_PLANNER_ATTEMPTS} "
                    f"timed out after {attempt_elapsed:.1f}s",
                )
                break
            _log_runtime_event(
                runtime_logger,
                f"[planner] {context_label} | attempt {attempt_number}/{MAX_PLANNER_ATTEMPTS} "
                f"failed in {attempt_elapsed:.1f}s: {_single_line_summary(_normalized_exception_text(exc))}",
            )
            if attempt + 1 >= MAX_PLANNER_ATTEMPTS:
                break
            _log_runtime_event(
                runtime_logger,
                f"[planner] {context_label} | retrying with repair prompt after attempt "
                f"{attempt_number}/{MAX_PLANNER_ATTEMPTS}",
            )
            current_prompt = repair_prompt_builder(
                base_prompt=base_prompt,
                previous_error=str(exc),
            )

    return {
        "status": "planning_error",
        "errors": [normalize_planner_error(last_exc or RuntimeError("Planner failed without an exception."))],
    }


def _structured_llm_factory_supports_model_role(structured_llm_factory: StructuredLLMFactory) -> bool:
    try:
        signature = inspect.signature(structured_llm_factory)
    except (TypeError, ValueError):
        return False
    return any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD or name == "model_role"
        for name, parameter in signature.parameters.items()
    )


def _build_structured_llm(
    *,
    structured_llm_factory: StructuredLLMFactory,
    output_schema: type[BaseModel],
    model_role: Literal["planner", "light"],
    request_timeout_seconds: float | None,
) -> Any:
    if _structured_llm_factory_supports_model_role(structured_llm_factory):
        return structured_llm_factory(output_schema, model_role=model_role)
    if model_role == LIGHT_MODEL_ROLE:
        return create_structured_llm(
            output_schema,
            model_role=LIGHT_MODEL_ROLE,
            request_timeout_seconds=request_timeout_seconds,
        )
    return structured_llm_factory(output_schema)


def _invoke_planner_with_timeout(
    *,
    planner: Any,
    prompt: str,
    timeout_seconds: float | None,
    elapsed_log_interval_seconds: float,
    runtime_logger: RuntimeEventLogger | None,
    context_label: str,
    attempt_number: int,
) -> Any:
    result_holder: dict[str, Any] = {}
    error_holder: dict[str, BaseException] = {}
    finished = threading.Event()

    def invoke() -> None:
        try:
            result_holder["value"] = planner.invoke(prompt)
        except BaseException as exc:  # pragma: no cover - exercised through caller
            error_holder["error"] = exc
        finally:
            finished.set()

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()

    started_at = time.monotonic()
    next_elapsed_log_at = elapsed_log_interval_seconds if runtime_logger is not None else None

    while True:
        if finished.is_set():
            break
        elapsed = time.monotonic() - started_at
        wait_for = 0.1
        if timeout_seconds is not None:
            wait_for = min(wait_for, max(timeout_seconds - elapsed, 0.0))
        if next_elapsed_log_at is not None:
            wait_for = min(wait_for, max(next_elapsed_log_at - elapsed, 0.0))
        finished.wait(max(wait_for, 0.01))
        elapsed = time.monotonic() - started_at
        if finished.is_set():
            break
        if next_elapsed_log_at is not None and elapsed >= next_elapsed_log_at:
            _log_runtime_event(
                runtime_logger,
                f"[planner] {context_label} | attempt {attempt_number}/{MAX_PLANNER_ATTEMPTS} "
                f"still running after {elapsed:.1f}s",
            )
            next_elapsed_log_at += elapsed_log_interval_seconds
        if timeout_seconds is not None and elapsed >= timeout_seconds:
            raise PlannerTimeoutError(
                timeout_seconds=timeout_seconds,
                context_label=context_label,
                attempt_number=attempt_number,
            )

    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder["value"]


def _planner_context_label(state: QuestionState, type_spec: QuestionTypeSpec) -> str:
    row_label = state["OriginalQuestionNumber"] or f"row {state['BatchRowId']}"
    subtype_label = type_spec.subtype_key or type_spec.family_key
    return f"{row_label} / {subtype_label}"


def _log_runtime_event(runtime_logger: RuntimeEventLogger | None, message: str) -> None:
    if runtime_logger is None:
        return
    runtime_logger(message)


def _single_line_summary(message: str, *, limit: int = 240) -> str:
    collapsed = " ".join(message.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def _ensure_design(state: QuestionState, type_spec: QuestionTypeSpec) -> dict[str, Any] | None:
    if state.get("design") is not None:
        return None
    result = build_design(state, type_spec)
    if "design" in result:
        state["design"] = result["design"]
        return None
    return result


def should_run_semantic_planner_adjudication(type_spec: QuestionTypeSpec) -> bool:
    return type_spec.subtype_key in _TIER1_SEMANTIC_ADJUDICATION_SUBTYPE_KEYS


def run_semantic_planner_adjudication(
    *,
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    plan: FillInTheBlankPlan,
    structured_llm_factory: StructuredLLMFactory,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> list[str]:
    prepared_source = state.get("prepared_source")
    if not isinstance(prepared_source, PreparedSource):
        return ["PreparedSource is required before planner semantic adjudication."]
    design = state.get("design")
    if not isinstance(design, FillInTheBlankDesign):
        return ["FillInTheBlankDesign is required before planner semantic adjudication."]

    adjudicator = _build_structured_llm(
        structured_llm_factory=structured_llm_factory,
        output_schema=PlannerSemanticAdjudicationResult,
        model_role=LIGHT_MODEL_ROLE,
        request_timeout_seconds=planner_timeout_seconds,
    )
    try:
        prompt = build_fill_in_the_blank_semantic_adjudication_prompt(
            design=design,
            plan=plan,
            prepared_source=prepared_source,
            type_spec=type_spec,
        )
    except Exception as exc:
        return [normalize_planner_error(exc)]
    context_label = f"{_planner_context_label(state, type_spec)} / semantic_adjudication"
    _log_runtime_event(runtime_logger, f"[planner] {context_label} | attempt 1/1 start")
    attempt_started_at = time.monotonic()
    try:
        raw_result = _invoke_planner_with_timeout(
            planner=adjudicator,
            prompt=prompt,
            timeout_seconds=planner_timeout_seconds,
            elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
            runtime_logger=runtime_logger,
            context_label=context_label,
            attempt_number=1,
        )
    except Exception as exc:
        attempt_elapsed = time.monotonic() - attempt_started_at
        _log_runtime_event(
            runtime_logger,
            f"[planner] {context_label} | attempt 1/1 failed in {attempt_elapsed:.1f}s: "
            f"{_single_line_summary(_normalized_exception_text(exc))}",
        )
        return [normalize_planner_error(exc)]

    attempt_elapsed = time.monotonic() - attempt_started_at
    decision = coerce_model(raw_result, PlannerSemanticAdjudicationResult)
    if decision.fits_discourse_role and decision.visible_frame_semantically_valid:
        _log_runtime_event(
            runtime_logger,
            f"[planner] {context_label} | attempt 1/1 accepted in {attempt_elapsed:.1f}s",
        )
        return []

    failure_reason = _semantic_adjudication_failure_reason(decision)
    _log_runtime_event(
        runtime_logger,
        f"[planner] {context_label} | attempt 1/1 rejected in {attempt_elapsed:.1f}s: "
        f"{_single_line_summary(failure_reason)}",
    )
    return [failure_reason]


def _semantic_adjudication_failure_reason(decision: PlannerSemanticAdjudicationResult) -> str:
    normalized_reason = " ".join((decision.failure_reason or "").split())
    if normalized_reason:
        return normalized_reason

    failures: list[str] = []
    if not decision.fits_discourse_role:
        failures.append("selected correct_choice does not fit the blank's discourse or proposition role")
    if not decision.visible_frame_semantically_valid:
        failures.append("the visible sentence frame makes the selected correct_choice semantically wrong")
    return "; ".join(failures) or "selected correct_choice failed semantic adjudication"


def plan_sentence_insertion(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    if state["prepared_source"] is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before planning."],
        }
    if structured_llm_factory is None:
        return {
            "status": "planning_error",
            "errors": ["No structured LLM factory was provided for planning."],
        }
    design_result = _ensure_design(state, type_spec)
    if design_result is not None:
        return design_result

    prompt = build_sentence_insertion_prompt(
        design=state["design"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_sentence_insertion_repair_prompt,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )


def plan_paragraph_ordering(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    if state["prepared_source"] is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before planning."],
        }
    if structured_llm_factory is None:
        return {
            "status": "planning_error",
            "errors": ["No structured LLM factory was provided for planning."],
        }
    design_result = _ensure_design(state, type_spec)
    if design_result is not None:
        return design_result

    prompt = build_paragraph_ordering_prompt(
        design=state["design"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_paragraph_ordering_repair_prompt,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )


def plan_mood_atmosphere(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    if state["prepared_source"] is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before planning."],
        }
    if structured_llm_factory is None:
        return {
            "status": "planning_error",
            "errors": ["No structured LLM factory was provided for planning."],
        }
    design_result = _ensure_design(state, type_spec)
    if design_result is not None:
        return design_result

    prompt = build_mood_atmosphere_prompt(
        design=state["design"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_mood_atmosphere_repair_prompt,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )


def plan_underlined_phrase_meaning(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    if state["prepared_source"] is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before planning."],
        }
    if structured_llm_factory is None:
        return {
            "status": "planning_error",
            "errors": ["No structured LLM factory was provided for planning."],
        }
    design_result = _ensure_design(state, type_spec)
    if design_result is not None:
        return design_result

    prompt = build_underlined_phrase_meaning_prompt(
        design=state["design"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_underlined_phrase_meaning_repair_prompt,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )


def plan_fill_in_the_blank(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    if state["prepared_source"] is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before planning."],
        }
    if structured_llm_factory is None:
        return {
            "status": "planning_error",
            "errors": ["No structured LLM factory was provided for planning."],
        }
    design_result = _ensure_design(state, type_spec)
    if design_result is not None:
        return design_result

    prompt = build_fill_in_the_blank_prompt(
        design=state["design"],
        type_spec=type_spec,
    )
    result = _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_fill_in_the_blank_repair_prompt,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )
    if result.get("status") != "planned" or not should_run_semantic_planner_adjudication(type_spec):
        return result

    plan = result.get("plan")
    if not isinstance(plan, FillInTheBlankPlan):
        return {
            "status": "planning_error",
            "errors": ["Planner semantic adjudication requires a hydrated FillInTheBlankPlan."],
        }

    semantic_errors = run_semantic_planner_adjudication(
        state=state,
        type_spec=type_spec,
        plan=plan,
        structured_llm_factory=structured_llm_factory,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )
    if semantic_errors:
        return {
            "status": "planning_error",
            "errors": [f"Planner semantic adjudication failed: {'; '.join(semantic_errors)}"],
        }
    return result


def plan_vocab(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    if state["prepared_source"] is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before planning."],
        }
    if structured_llm_factory is None:
        return {
            "status": "planning_error",
            "errors": ["No structured LLM factory was provided for planning."],
        }
    design_result = _ensure_design(state, type_spec)
    if design_result is not None:
        return design_result

    prompt = build_vocab_prompt(
        design=state["design"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_vocab_repair_prompt,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )


def plan_grammar(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
    runtime_logger: RuntimeEventLogger | None = None,
    planner_timeout_seconds: float | None = None,
    planner_elapsed_log_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    if state["prepared_source"] is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before planning."],
        }
    if structured_llm_factory is None:
        return {
            "status": "planning_error",
            "errors": ["No structured LLM factory was provided for planning."],
        }
    design_result = _ensure_design(state, type_spec)
    if design_result is not None:
        return design_result

    prompt = build_grammar_prompt(
        design=state["design"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_grammar_repair_prompt,
        runtime_logger=runtime_logger,
        planner_timeout_seconds=planner_timeout_seconds,
        planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
    )


PLANNERS: dict[
    str,
    Callable[
        [
            QuestionState,
            QuestionTypeSpec,
            StructuredLLMFactory | None,
            RuntimeEventLogger | None,
            float | None,
            float,
        ],
        dict[str, Any],
    ],
] = {
    "sentence_insertion": plan_sentence_insertion,
    "paragraph_ordering": plan_paragraph_ordering,
    "mood_atmosphere": plan_mood_atmosphere,
    "underlined_phrase_meaning": plan_underlined_phrase_meaning,
    "fill_in_the_blank": plan_fill_in_the_blank,
    "vocab": plan_vocab,
    "grammar": plan_grammar,
}
