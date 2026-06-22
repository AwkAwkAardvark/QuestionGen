from __future__ import annotations

from dataclasses import dataclass

from .schemas import SentenceInsertionPlan

SENTENCE_INSERTION_STEM = "글의 흐름으로 보아, 주어진 문장이 들어가기에 가장 적절한 곳은?"

SENTENCE_INSERTION_PLANNER_PROMPT = """
- Select exactly one target sentence ID from the sentence inventory.
- Select exactly five unique gap IDs from the gap inventory.
- Set correct_gap_id to the gap where the target sentence best fits back into the paragraph.
- The target sentence text must remain unchanged.
- Use only IDs that appear in the inventories.
- Write the explanation entirely in Korean.
- Do not generate final student-facing paragraph text.
""".strip()


@dataclass(frozen=True)
class QuestionTypeSpec:
    label_ko: str
    planner_prompt: str
    question_stem: str
    unit_level: str
    renderer_key: str
    validator_key: str
    plan_schema: type
    min_source_units: int | None = None
    choice_count: int | None = None


QUESTION_TYPES: dict[str, QuestionTypeSpec] = {
    "sentence_insertion": QuestionTypeSpec(
        label_ko="문장 삽입",
        planner_prompt=SENTENCE_INSERTION_PLANNER_PROMPT,
        question_stem=SENTENCE_INSERTION_STEM,
        unit_level="sentence",
        renderer_key="sentence_insertion",
        validator_key="sentence_insertion",
        plan_schema=SentenceInsertionPlan,
        min_source_units=5,
        choice_count=5,
    ),
}
