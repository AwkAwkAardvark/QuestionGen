from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .parsers import prepare_source
from .planners import PLANNERS, StructuredLLMFactory
from .question_types import QUESTION_TYPES, QuestionTypeSpec
from .renderers import RENDERERS
from .schemas import QuestionState
from .validators import input_check, source_check, validate_generated_question

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

        self._apply_result(working_state, input_check(working_state))
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

        type_spec = self.question_types[working_state["QuestionTypeKey"]]
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

        renderer = RENDERERS[type_spec.renderer_key]
        self._apply_result(working_state, renderer(working_state, type_spec))
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
        question_types=question_types or QUESTION_TYPES,
        structured_llm_factory=structured_llm_factory,
    )
