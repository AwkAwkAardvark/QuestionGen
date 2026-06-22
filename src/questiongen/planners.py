from __future__ import annotations

from typing import Any, Callable

from .prompts import build_sentence_insertion_prompt
from .question_types import QuestionTypeSpec
from .schemas import BaseModel, QuestionState, coerce_model

StructuredLLMFactory = Callable[[type[BaseModel]], Any]


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

    try:
        planner = structured_llm_factory(type_spec.plan_schema)
        raw_plan = planner.invoke(prompt)
        plan = coerce_model(raw_plan, type_spec.plan_schema)
    except Exception as exc:
        return {
            "status": "planning_error",
            "errors": [f"Planner failed: {exc}"],
        }

    return {
        "plan": plan,
        "status": "planned",
        "errors": [],
    }


PLANNERS: dict[str, Callable[[QuestionState, QuestionTypeSpec, StructuredLLMFactory | None], dict[str, Any]]] = {
    "sentence_insertion": plan_sentence_insertion,
}
