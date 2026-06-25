from __future__ import annotations

from typing import Any, Callable, Iterable, Literal

from .prompts import (
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
    ContextualVocabChoicePlan,
    GrammarPlan,
    PreparedSource,
    QuestionState,
    UnderlinedVocabPlan,
    VocabPlan,
    coerce_model,
)
from .targeting import (
    grammar_subtype_inventory,
    grammar_target_inventory,
    vocab_choice_inventory,
    vocab_target_inventory,
)
from .validators import validate_plan_against_prepared_source

StructuredLLMFactory = Callable[[type[BaseModel]], Any]
MAX_PLANNER_ATTEMPTS = 2
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


def classify_planner_error(exc: BaseException) -> Literal["service_quota", "service", "planner"]:
    error_text = _normalized_exception_text(exc).lower()
    if "insufficient_quota" in error_text:
        return "service_quota"
    if any(marker in error_text for marker in _PLANNER_SERVICE_ERROR_MARKERS):
        return "service"
    return "planner"


def normalize_planner_error(exc: BaseException) -> str:
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
) -> dict[str, Any]:
    planner = structured_llm_factory(type_spec.plan_schema)
    current_prompt = base_prompt
    last_exc: Exception | None = None

    for attempt in range(MAX_PLANNER_ATTEMPTS):
        try:
            raw_plan = planner.invoke(current_prompt)
            plan = coerce_model(raw_plan, type_spec.plan_schema)
            prepared_source = state["prepared_source"]
            if prepared_source is not None:
                plan = _canonicalize_source_owned_plan(plan, prepared_source, type_spec)
                deterministic_errors = validate_plan_against_prepared_source(prepared_source, plan, type_spec)
                if deterministic_errors:
                    last_exc = RuntimeError("; ".join(deterministic_errors))
                    if attempt + 1 >= MAX_PLANNER_ATTEMPTS:
                        break
                    current_prompt = repair_prompt_builder(
                        base_prompt=base_prompt,
                        previous_error="; ".join(deterministic_errors),
                    )
                    continue
            return {
                "plan": plan,
                "status": "planned",
                "errors": [],
            }
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= MAX_PLANNER_ATTEMPTS:
                break
            current_prompt = repair_prompt_builder(
                base_prompt=base_prompt,
                previous_error=str(exc),
            )

    return {
        "status": "planning_error",
        "errors": [normalize_planner_error(last_exc or RuntimeError("Planner failed without an exception."))],
    }


def _canonicalize_source_owned_plan(
    plan: BaseModel,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> BaseModel:
    if isinstance(plan, VocabPlan):
        inventory = {span.id: span for span in vocab_target_inventory(prepared_source)}
        if len(plan.target_span_ids) == 5 and all(span_id in inventory for span_id in plan.target_span_ids):
            return plan.model_copy(
                update={
                    "target_span_texts": [inventory[span_id].text for span_id in plan.target_span_ids],
                }
            )
        return plan

    if isinstance(plan, GrammarPlan):
        inventory = {span.id: span for span in grammar_subtype_inventory(prepared_source, type_spec.subtype_key)}
        if len(plan.target_span_ids) == 5 and all(span_id in inventory for span_id in plan.target_span_ids):
            return plan.model_copy(
                update={
                    "target_span_texts": [inventory[span_id].text for span_id in plan.target_span_ids],
                }
            )
        return plan

    if isinstance(plan, ContextualVocabChoicePlan):
        inventory = {span.id: span for span in vocab_choice_inventory(prepared_source, type_spec.subtype_key)}
        selected_span = inventory.get(plan.selected_span_id)
        if selected_span is not None:
            return plan.model_copy(
                update={
                    "selected_span_text": selected_span.text,
                }
            )
        return plan

    if isinstance(plan, UnderlinedVocabPlan):
        inventory = {span.id: span for span in vocab_choice_inventory(prepared_source, type_spec.subtype_key)}
        if len(plan.target_span_ids) == 5 and all(span_id in inventory for span_id in plan.target_span_ids):
            return plan.model_copy(
                update={
                    "target_span_texts": [inventory[span_id].text for span_id in plan.target_span_ids],
                }
            )
        return plan

    return plan


def plan_sentence_insertion(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
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

    prompt = build_sentence_insertion_prompt(
        source_paragraph=state["source_paragraph"],
        prepared_source=state["prepared_source"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_sentence_insertion_repair_prompt,
    )


def plan_paragraph_ordering(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
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

    prompt = build_paragraph_ordering_prompt(
        source_paragraph=state["source_paragraph"],
        prepared_source=state["prepared_source"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_paragraph_ordering_repair_prompt,
    )


def plan_mood_atmosphere(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
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

    prompt = build_mood_atmosphere_prompt(
        source_paragraph=state["source_paragraph"],
        prepared_source=state["prepared_source"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_mood_atmosphere_repair_prompt,
    )


def plan_underlined_phrase_meaning(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
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

    prompt = build_underlined_phrase_meaning_prompt(
        source_paragraph=state["source_paragraph"],
        prepared_source=state["prepared_source"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_underlined_phrase_meaning_repair_prompt,
    )


def plan_fill_in_the_blank(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
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

    prompt = build_fill_in_the_blank_prompt(
        source_paragraph=state["source_paragraph"],
        prepared_source=state["prepared_source"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_fill_in_the_blank_repair_prompt,
    )


def plan_vocab(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
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

    prompt = build_vocab_prompt(
        source_paragraph=state["source_paragraph"],
        prepared_source=state["prepared_source"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_vocab_repair_prompt,
    )


def plan_grammar(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
    structured_llm_factory: StructuredLLMFactory | None,
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

    prompt = build_grammar_prompt(
        source_paragraph=state["source_paragraph"],
        prepared_source=state["prepared_source"],
        type_spec=type_spec,
    )
    return _run_planner_with_repair(
        state=state,
        type_spec=type_spec,
        structured_llm_factory=structured_llm_factory,
        base_prompt=prompt,
        repair_prompt_builder=build_grammar_repair_prompt,
    )


PLANNERS: dict[str, Callable[[QuestionState, QuestionTypeSpec, StructuredLLMFactory | None], dict[str, Any]]] = {
    "sentence_insertion": plan_sentence_insertion,
    "paragraph_ordering": plan_paragraph_ordering,
    "mood_atmosphere": plan_mood_atmosphere,
    "underlined_phrase_meaning": plan_underlined_phrase_meaning,
    "fill_in_the_blank": plan_fill_in_the_blank,
    "vocab": plan_vocab,
    "grammar": plan_grammar,
}
