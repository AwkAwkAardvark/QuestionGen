from __future__ import annotations

import json
import os

from questiongen.batch import run_batch_rows
from questiongen.config import create_structured_llm
from questiongen.graph import compile_question_graph
from questiongen.schemas import BatchInputRow, SentenceInsertionPlan


class StaticStructuredPlanner:
    def __init__(self, output_schema: type[SentenceInsertionPlan]) -> None:
        self.output_schema = output_schema

    def invoke(self, prompt: str) -> SentenceInsertionPlan:
        return self.output_schema(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G3", "G4"],
            correct_gap_id="G2",
            explanation="문맥상 핵심 전환 문장이므로 세 번째 위치에 들어가는 것이 가장 자연스럽습니다.",
        )


def build_structured_llm(output_schema: type[SentenceInsertionPlan]) -> object:
    if os.getenv("QUESTIONGEN_USE_LLM") == "1":
        return create_structured_llm(output_schema)
    return StaticStructuredPlanner(output_schema)


def main() -> None:
    paragraph = (
        "Many people excuse perfectionism at work by claiming it is professionalism. "
        "Differentiating between the two is useful. "
        "Managing perfectionism does not mean dropping critical standards. "
        "It becomes a problem when your personal expectations become unmanageable, "
        "self-imposed demands that create more pressure than is needed. "
        "It is not permission for work sloppiness or low standards; rather it means "
        "spending less time on tasks that do not need the level of input you are providing. "
        "What are the acceptable standards of professionalism in your work and how do these compare with your own? "
        "With the busyness of workplaces these days, trying to achieve a benchmark of 110% perfect on everything "
        "can be a recipe for burnout. "
        "If you are a manager expecting this of others, you may be setting yourself up for failure."
    )

    runner = compile_question_graph(structured_llm_factory=build_structured_llm)
    rows = [BatchInputRow(OriginalQuestionNumber=1, source_paragraph=paragraph)]
    results = run_batch_rows(rows, ["sentence_insertion"], runner)
    print(json.dumps([row.model_dump() for row in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
