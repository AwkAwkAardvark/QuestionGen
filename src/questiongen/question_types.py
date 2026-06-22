from __future__ import annotations

from dataclasses import dataclass

from .schemas import ParagraphOrderingPlan, SentenceInsertionPlan

SENTENCE_INSERTION_STEM = "글의 흐름으로 보아, 주어진 문장이 들어가기에 가장 적절한 곳은?"
PARAGRAPH_ORDERING_STEM = "주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?"

SENTENCE_INSERTION_PLANNER_PROMPT = """
- Select exactly one target sentence ID from the sentence inventory.
- Select exactly five unique gap IDs from the gap inventory.
- Do not select both gaps that sit immediately before and after the target sentence, because they collapse into one rendered position once the target sentence is removed.
- First finalize `selected_gap_ids`, then choose `correct_gap_id` from that exact five-item list only.
- Set correct_gap_id to the gap where the target sentence best fits back into the paragraph.
- The target sentence text must remain unchanged.
- Use only IDs that appear in the inventories.
- Write the explanation entirely in Korean.
- Do not generate final student-facing paragraph text.
""".strip()

PARAGRAPH_ORDERING_PLANNER_PROMPT = """
- Partition the full sentence inventory into exactly four contiguous non-empty blocks in original order.
- The first block is the intro section shown before (A), (B), (C).
- The remaining three blocks are the continuation blocks that must follow the intro in their original logical order.
- Use every sentence exactly once across the intro block and the three continuation blocks.
- Do not generate final student-facing paragraph text.
- Write the explanation entirely in Korean.
""".strip()


@dataclass(frozen=True)
class QuestionTypeSpec:
    format_key: str
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
        format_key="sentence_insertion_5_gaps",
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
    "paragraph_ordering": QuestionTypeSpec(
        format_key="abc_ordering_after_intro",
        label_ko="글의 순서",
        planner_prompt=PARAGRAPH_ORDERING_PLANNER_PROMPT,
        question_stem=PARAGRAPH_ORDERING_STEM,
        unit_level="sentence",
        renderer_key="paragraph_ordering",
        validator_key="paragraph_ordering",
        plan_schema=ParagraphOrderingPlan,
        min_source_units=6,
        choice_count=5,
    ),
}
