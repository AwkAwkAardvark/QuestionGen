from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .explanations import build_explanation_context, write_teacher_facing_explanation
from .parsers import prepare_source
from .planners import PLANNERS, StructuredLLMFactory
from .question_types import QUESTION_SUBTYPE_SPECS, QuestionTypeSpec, resolve_question_type_spec
from .renderers import RENDERERS
from .schemas import QuestionState
from .validators import input_check, plan_check, source_check, validate_generated_question

NodeResult = dict[str, Any]


@dataclass(slots=True)
class LocalQuestionGraphRunner:
    question_types: Mapping[str, QuestionTypeSpec]
    structured_llm_factory: StructuredLLMFactory | None = None

    def invoke(self, state: QuestionState) -> QuestionState:
        working_state: QuestionState = {
            **state,
            "errors": list(state["errors"]),
        }

        self._apply_result(working_state, input_check(working_state, self.question_types))
        if working_state["status"] != "input_passed":
            return working_state

        prepared = prepare_source(working_state["source_paragraph"])
        self._apply_result(
            working_state,
            {
                "prepared_source": prepared,
                "status": "source_prepared",
                "errors": [],
            },
        )

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
        self._apply_result(working_state, source_check(working_state, type_spec))
        if working_state["status"] != "source_passed":
            return working_state

        planner = PLANNERS[type_spec.renderer_key]
        self._apply_result(
            working_state,
            planner(working_state, type_spec, self.structured_llm_factory),
        )
        if working_state["status"] != "planned":
            return working_state

        self._apply_result(working_state, plan_check(working_state, type_spec))
        if working_state["status"] != "planned":
            return working_state

        renderer = RENDERERS[type_spec.renderer_key]
        self._apply_result(working_state, renderer(working_state, type_spec))
        if working_state["status"] != "rendered":
            return working_state

        self._apply_result(working_state, build_explanation_context(working_state))
        if working_state["status"] != "rendered":
            return working_state

        self._apply_result(working_state, write_teacher_facing_explanation(working_state))
        if working_state["status"] != "rendered":
            return working_state

        self._apply_result(working_state, validate_generated_question(working_state, type_spec))
        return working_state

    @staticmethod
    def _apply_result(state: QuestionState, result: NodeResult) -> None:
        for key, value in result.items():
            state[key] = value


def compile_question_graph(
    *,
    structured_llm_factory: StructuredLLMFactory | None = None,
    question_types: Mapping[str, QuestionTypeSpec] | None = None,
) -> LocalQuestionGraphRunner:
    return LocalQuestionGraphRunner(
        question_types=question_types or QUESTION_SUBTYPE_SPECS,
        structured_llm_factory=structured_llm_factory,
    )
