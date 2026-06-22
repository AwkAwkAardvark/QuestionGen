from __future__ import annotations

from typing import Any, Callable

from .prompts import build_sentence_insertion_prompt, build_sentence_insertion_repair_prompt
from .question_types import QuestionTypeSpec
from .schemas import BaseModel, QuestionState, coerce_model

StructuredLLMFactory = Callable[[type[BaseModel]], Any]
MAX_PLANNER_ATTEMPTS = 2


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

    planner = structured_llm_factory(type_spec.plan_schema)
    current_prompt = prompt
    last_exc: Exception | None = None

    for attempt in range(MAX_PLANNER_ATTEMPTS):
        try:
            raw_plan = planner.invoke(current_prompt)
            plan = coerce_model(raw_plan, type_spec.plan_schema)
            return {
                "plan": plan,
                "status": "planned",
                "errors": [],
            }
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= MAX_PLANNER_ATTEMPTS:
                break
            current_prompt = build_sentence_insertion_repair_prompt(
                base_prompt=prompt,
                previous_error=str(exc),
            )

    return {
        "status": "planning_error",
        "errors": [f"Planner failed: {last_exc}"],
    }


PLANNERS: dict[str, Callable[[QuestionState, QuestionTypeSpec, StructuredLLMFactory | None], dict[str, Any]]] = {
    "sentence_insertion": plan_sentence_insertion,
}
