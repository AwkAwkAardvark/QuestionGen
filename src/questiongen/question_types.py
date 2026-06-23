from __future__ import annotations

from dataclasses import dataclass

from .schemas import (
    FillInTheBlankPlan,
    GrammarPlan,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
    VocabPlan,
)

SENTENCE_INSERTION_STEM = "글의 흐름으로 보아, 주어진 문장이 들어가기에 가장 적절한 곳은?"
PARAGRAPH_ORDERING_STEM = "주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?"
MOOD_ATMOSPHERE_STEM = "다음 글에 나타난 심경 변화로 가장 적절한 것은?"
UNDERLINED_PHRASE_MEANING_STEM = "다음 글의 밑줄 친 부분의 의미로 가장 적절한 것은?"
FILL_IN_THE_BLANK_STEM = "다음 빈칸에 들어갈 말로 가장 적절한 것은?"
VOCAB_STEM = "다음 글의 밑줄 친 부분 중, 문맥상 낱말의 쓰임이 적절하지 않은 것은?"
GRAMMAR_STEM = "다음 글의 밑줄 친 부분 중, 어법상 틀린 것은?"

SENTENCE_INSERTION_PLANNER_PROMPT = """
- Select exactly one target sentence ID from the sentence inventory.
- Select exactly five unique gap IDs from the gap inventory.
- Use the ranked target-candidate notes to choose the best available strong target, not merely any schema-valid sentence.
- Treat weak or reject-by-default target hints as a sign to choose a different target rather than forcing the item.
- Do not select both gaps that sit immediately before and after the target sentence, because they collapse into one rendered position once the target sentence is removed.
- Before returning, verify that the five selected gap IDs still map to five distinct rendered positions after removing the target sentence from the paragraph.
- First finalize `selected_gap_ids`, then choose `correct_gap_id` from that exact five-item list only.
- Set correct_gap_id to the gap where the target sentence best fits back into the paragraph.
- Prefer target sentences with distinct evidence on both sides: the left context should make the target sentence necessary, and the right context should read better because the target sentence is present.
- Good target shape: a sentence whose wording is prepared by the sentence before it and whose consequence, explanation, or reference is completed by the sentence after it.
- Bad target shape: a sentence that only begins with However/Therefore/But and could fit anywhere once that connector is ignored.
- Reject first-sentence, last-sentence, fragmentary, or connector-only targets instead of forcing a weak item.
- Do not treat the given sentence itself as the main explanation evidence. Use the surrounding sentences as the evidence anchors.
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
- Use the boundary hints and candidate block-start notes to choose the strongest available partition, not just any contiguous four-block split.
- Treat weak boundary hints or parallel-example block starts as a sign to rebuild the partition rather than forcing a generic four-block answer.
- Prefer block boundaries whose adjacency is forced by the passage, not just by a generic start-middle-end outline.
- Good partition shape: one block clearly raises a stage, question, or step that the next block directly continues or answers.
- Bad partition shape: three case-example blocks that look parallel enough to be swapped without changing the broad summary.
- Reject partitions where the continuation blocks behave like parallel examples or interchangeable subpoints.
- In the explanation, justify why one block follows the previous block, not just that the text starts, develops, and ends.
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
- Use the ranked span inventory and prefer the strongest claim-bearing or proposition-bearing target unless it is clearly unusable.
- Treat weak or local centrality hints as a sign to pick a different span rather than forcing a merely valid phrase boundary.
- Prefer abstract, figurative, evaluative, or claim-bearing phrases whose meaning must be inferred from the passage.
- Reject literal dictionary-gloss phrases, dangling phrase fragments, punctuation-crossing chunks that are not complete clause-level units, surface comparison phrases, and weak targets that are not central to the passage claim.
- Prefer propositionally or argumentatively central spans over easy surface-paraphrase fragments.
- Good target shape: a phrase that carries the passage's conclusion, mechanism, evaluation, contrast, or limitation.
- Bad target shape: a merely local wording fragment that is easy to gloss without understanding the passage claim.
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

FILL_IN_THE_BLANK_PLANNER_PROMPT = """
- Treat this first rollout as the blank_inference_proposition_5_choices format under the broad key fill_in_the_blank.
- Self-select exactly one span candidate from the provided phrase-span inventory.
- Prefer a proposition-like, clause-level, claim-bearing, reason-bearing, effect-bearing, contrast-bearing, or limitation-bearing span.
- If no strongly proposition-like span exists, still prefer the most readable clause-sized contextual span rather than falling back to a local phrase fragment.
- Do not generate a trivial lexical blank or a pure grammar blank.
- Reject punctuation-crossing chunks unless the selected span remains a complete clause-level unit.
- Reject blanks that mainly restore a short surface phrase, connective fragment, or mechanically copied wording.
- Copy the selected span ID into `selected_span_id` and the exact source text into `selected_span_text`.
- Do not alter the source passage text or generate final student-facing paragraph text.
- Create exactly five unique English completion choices in `completion_choices`.
- Set `correct_choice` to the one option that best restores the original passage meaning.
- Keep distractors readable English and broadly on-topic, even if they are rough.
- Set `contextual_meaning_ko` to a short Korean teacher-facing note describing what idea the blank must convey.
- Copy `supporting_evidence` as a short exact snippet from the passage that best supports the correct completion.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain what the blank should mean in context, not internal IDs, schema fields, or renderer mechanics.
""".strip()

VOCAB_PLANNER_PROMPT = """
- Treat this first rollout as the contextual_vocab_error_5 format under the broad key vocab.
- Select exactly five unique single-word target IDs from the provided vocab-target inventory.
- Treat `target_span_ids` as the authoritative source-owned contract; `target_span_texts` should simply mirror those selected IDs.
- Choose exactly one of those five targets as `corrupted_span_id`.
- Replace only that one target with one single English word in `corrupted_word`.
- Prefer targets whose corruption can reverse or clearly distort the passage meaning, not flat content words with weak semantic pressure.
- The corrupted word should remain grammatically readable in the sentence, but it must reverse or clearly distort the passage meaning.
- Do not use a near-synonym or near-paraphrase of the original word. Replacements such as `stick -> adhere`, `help -> aid`, or `large -> big` are invalid because they preserve the meaning too closely.
- Keep the other four target words unchanged from the source.
- Set `correction_basis_ko` to a short Korean note explaining why the corrupted word does not fit and what meaning the original word supports instead.
- Copy `supporting_evidence` as a short exact snippet from the passage that helps show why the original word fits the context.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the contextual mismatch, not internal IDs, schema fields, or renderer mechanics.
- Do not generate final student-facing paragraph text.
""".strip()

GRAMMAR_PLANNER_PROMPT = """
- Treat this first rollout as the grammar_error_5 format under the broad key grammar.
- Narrow the task to one controlled verb-form corruption family only.
- Select exactly five unique single-word target IDs from the provided grammar-target inventory.
- Treat `target_span_ids` as the authoritative source-owned contract; `target_span_texts` should simply mirror those selected IDs.
- Choose exactly one of those five targets as `corrupted_span_id`.
- Replace only that one target with one single English word in `corrupted_word`.
- The corrupted word must be a real English verb form chosen from the deterministic allowed family for the original target.
- Never invent malformed pseudo-words such as `increaseed`, `reduceing`, `understanded`, or `rethinked`.
- Keep the other four target words unchanged from the source.
- Set `correction_basis_ko` to a short Korean note explaining what structural cue makes the original verb form correct and the corrupted form wrong.
- Copy `supporting_evidence` as a short exact snippet from the passage that helps show the governing structural cue.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the structural mismatch, not internal IDs, schema fields, or renderer mechanics.
- Do not generate final student-facing paragraph text.
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
    "fill_in_the_blank": QuestionTypeSpec(
        format_key="blank_inference_proposition_5_choices",
        label_ko="빈칸 추론",
        planner_prompt=FILL_IN_THE_BLANK_PLANNER_PROMPT,
        question_stem=FILL_IN_THE_BLANK_STEM,
        unit_level="span",
        renderer_key="fill_in_the_blank",
        validator_key="fill_in_the_blank",
        plan_schema=FillInTheBlankPlan,
        min_source_units=2,
        choice_count=5,
    ),
    "vocab": QuestionTypeSpec(
        format_key="contextual_vocab_error_5",
        label_ko="어휘",
        planner_prompt=VOCAB_PLANNER_PROMPT,
        question_stem=VOCAB_STEM,
        unit_level="span",
        renderer_key="vocab",
        validator_key="vocab",
        plan_schema=VocabPlan,
        min_source_units=2,
        choice_count=5,
    ),
    "grammar": QuestionTypeSpec(
        format_key="grammar_error_5",
        label_ko="어법",
        planner_prompt=GRAMMAR_PLANNER_PROMPT,
        question_stem=GRAMMAR_STEM,
        unit_level="span",
        renderer_key="grammar",
        validator_key="grammar",
        plan_schema=GrammarPlan,
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
