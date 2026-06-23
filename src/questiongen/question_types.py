from __future__ import annotations

from dataclasses import dataclass

from .schemas import (
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
)

SENTENCE_INSERTION_STEM = "글의 흐름으로 보아, 주어진 문장이 들어가기에 가장 적절한 곳은?"
PARAGRAPH_ORDERING_STEM = "주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?"
MOOD_ATMOSPHERE_STEM = "다음 글에 나타난 심경 변화로 가장 적절한 것은?"
UNDERLINED_PHRASE_MEANING_STEM = "다음 글의 밑줄 친 부분의 의미로 가장 적절한 것은?"

SENTENCE_INSERTION_PLANNER_PROMPT = """
- Select exactly one target sentence ID from the sentence inventory.
- Select exactly five unique gap IDs from the gap inventory.
- Do not select both gaps that sit immediately before and after the target sentence, because they collapse into one rendered position once the target sentence is removed.
- Before returning, verify that the five selected gap IDs still map to five distinct rendered positions after removing the target sentence from the paragraph.
- First finalize `selected_gap_ids`, then choose `correct_gap_id` from that exact five-item list only.
- Set correct_gap_id to the gap where the target sentence best fits back into the paragraph.
- The target sentence text must remain unchanged.
- Use only IDs that appear in the inventories.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the textual flow using sentence meaning, not internal IDs, schema fields, gap labels, or renderer mechanics.
- Do not generate final student-facing paragraph text.
""".strip()

PARAGRAPH_ORDERING_PLANNER_PROMPT = """
- Partition the full sentence inventory into exactly four contiguous non-empty blocks in original order.
- The first block is the intro section shown before (A), (B), (C).
- The remaining three blocks are the continuation blocks that must follow the intro in their original logical order.
- Use every sentence exactly once across the intro block and the three continuation blocks.
- Before returning, verify that flattening the intro block followed by the three continuation blocks reproduces the full sentence inventory in exactly the original order.
- Do not generate final student-facing paragraph text.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the thematic or logical progression, not internal sentence IDs, block inventories, or schema mechanics.
""".strip()

MOOD_ATMOSPHERE_PLANNER_PROMPT = """
- Treat this first rollout as the emotion_shift subtype under the broad key mood_atmosphere.
- Use the source passage unchanged; do not remove, reorder, or underline any text.
- Only create an item if the passage contains one clear feeling-holder such as the writer, narrator, or a single clearly identifiable character.
- Reject neutral, informational, or weakly affective passages rather than forcing an emotion question onto them.
- Identify a real emotional change from an initial state to a different final state.
- Set `target_holder` to a short natural label for that one clear holder.
- Set `initial_emotion` and `final_emotion` to distinct English emotion adjectives or short adjective phrases.
- Create exactly five unique English answer choices in `emotion -> emotion` format.
- Set `correct_choice` to the one choice that exactly matches `initial_emotion -> final_emotion`.
- Use distractors that are plausible but clearly wrong in direction, endpoint, or nuance.
- Copy `initial_evidence` and `final_evidence` as short exact snippets from the passage that support the initial and final emotional states.
- `shift_trigger` may be omitted, but if present it must be a short exact snippet from the passage that helps explain the change.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the emotional movement using textual evidence, not schema fields, internal labels, or mechanics.
- Do not generate final student-facing paragraph text.
""".strip()

UNDERLINED_PHRASE_MEANING_PLANNER_PROMPT = """
- Treat this first rollout as a single-span contextual paraphrase item under the broad key underlined_phrase_meaning.
- Self-select exactly one span candidate from the provided span inventory.
- Prefer abstract, figurative, evaluative, or claim-bearing phrases whose meaning must be inferred from the passage.
- Reject literal dictionary-gloss phrases, phrase targets that are too context-free, and weak targets that are not central to the passage claim.
- Copy the selected span ID into `selected_span_id` and the exact source text into `selected_span_text`.
- Do not alter the source passage text or generate final student-facing paragraph text.
- Create exactly five unique Korean contextual paraphrase choices in `paraphrase_choices_ko`.
- Set `correct_choice` to the one clear best Korean paraphrase from that five-item list.
- Use distractors that stay close to the topic but are wrong in implication, scope, tone, or inference.
- Set `surface_meaning` to a short Korean explanation of the phrase's literal or surface wording.
- Set `contextual_meaning` to a short Korean explanation of what the phrase means in this passage.
- Copy `supporting_evidence` as a short exact snippet from the passage that best supports the contextual interpretation.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the phrase through passage evidence, not schema fields, internal IDs, or mechanics.
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
    "underlined_phrase_meaning": QuestionTypeSpec(
        format_key="underlined_phrase_meaning_5_ko",
        label_ko="밑줄 친 부분 의미",
        planner_prompt=UNDERLINED_PHRASE_MEANING_PLANNER_PROMPT,
        question_stem=UNDERLINED_PHRASE_MEANING_STEM,
        unit_level="span",
        renderer_key="underlined_phrase_meaning",
        validator_key="underlined_phrase_meaning",
        plan_schema=UnderlinedPhraseMeaningPlan,
        min_source_units=2,
        choice_count=5,
    ),
}

MOOD_ATMOSPHERE_SPEC = QuestionTypeSpec(
    format_key="emotion_shift_pair_choice_5",
    label_ko="심경·분위기",
    planner_prompt=MOOD_ATMOSPHERE_PLANNER_PROMPT,
    question_stem=MOOD_ATMOSPHERE_STEM,
    unit_level="passage",
    renderer_key="mood_atmosphere",
    validator_key="mood_atmosphere",
    plan_schema=MoodAtmospherePlan,
    min_source_units=5,
    choice_count=5,
)
