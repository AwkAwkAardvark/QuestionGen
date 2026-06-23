from __future__ import annotations

from .question_types import QuestionTypeSpec
from .schemas import PreparedSource


def build_sentence_insertion_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        f"- {unit.id}: {unit.text}"
        for unit in prepared_source.sentence_units
    )
    gap_inventory = "\n".join(
        f"- {gap.id}: before={gap.before_unit_id or 'START'}, after={gap.after_unit_id or 'END'}"
        for gap in prepared_source.gap_units
    )
    return f"""
You are planning an English exam sentence insertion question.

Return only structured data matching the required schema.

Question type:
- Key: sentence_insertion
- Label: {type_spec.label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}

Gap units:
{gap_inventory}
""".strip()


def build_sentence_insertion_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- `correct_gap_id` must be exactly one of the IDs listed in `selected_gap_ids`.
- Re-check that `selected_gap_ids` contains exactly five unique gap IDs.
- Re-check that you did not choose both gaps immediately before and after the target sentence.
- Re-check that the five selected gap IDs still map to five distinct rendered positions after removing the target sentence.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that uses sentence meaning rather than internal IDs, gap labels, schema field names, or renderer mechanics.
- Return only structured data matching the schema.
""".strip()


def build_paragraph_ordering_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        f"- {unit.id}: {unit.text}"
        for unit in prepared_source.sentence_units
    )
    return f"""
You are planning an English exam paragraph ordering question.

Return only structured data matching the required schema.

Question type:
- Key: paragraph_ordering
- Label: {type_spec.label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}
""".strip()


def build_paragraph_ordering_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- The intro block and continuation blocks must together cover every sentence exactly once.
- Re-check that flattening the intro block followed by the three continuation blocks reproduces the full sentence inventory in exactly the original order.
- Keep exactly three continuation blocks.
- Keep each block non-empty.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that uses thematic or logical progression rather than internal sentence IDs, block inventories, or schema mechanics.
- Return only structured data matching the schema.
""".strip()


def build_mood_atmosphere_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        f"- {unit.id}: {unit.text}"
        for unit in prepared_source.sentence_units
    )
    return f"""
You are planning an English exam mood/atmosphere question.

Return only structured data matching the required schema.

Question type:
- Key: mood_atmosphere
- Label: {type_spec.label_ko}
- Active subtype: emotion_shift
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}
""".strip()


def build_mood_atmosphere_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- Keep the subtype as emotion_shift.
- Re-check that `initial_emotion` and `final_emotion` are different.
- Re-check that `choice_pairs` contains exactly five unique English `emotion -> emotion` choices.
- Re-check that `correct_choice` is one of `choice_pairs` and exactly matches `initial_emotion -> final_emotion`.
- Re-check that `initial_evidence`, `final_evidence`, and optional `shift_trigger` are copied as exact passage snippets.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that uses emotional evidence rather than schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()


def build_underlined_phrase_meaning_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        f"- {unit.id}: {unit.text}"
        for unit in prepared_source.sentence_units
    )
    span_inventory = "\n".join(
        (
            f"- {span.id}: text={span.text!r}; sentence={span.sentence_unit_id or 'NONE'}; "
            f"chars={span.char_start}:{span.char_end}; tags={','.join(span.heuristic_tags) or 'none'}; "
            f"before={span.context_before or 'NONE'}; after={span.context_after or 'NONE'}"
        )
        for span in prepared_source.span_units
    )
    return f"""
You are planning an English exam underlined phrase meaning question.

Return only structured data matching the required schema.

Question type:
- Key: underlined_phrase_meaning
- Label: {type_spec.label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}

Span candidates:
{span_inventory}
""".strip()


def build_underlined_phrase_meaning_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- Re-check that `selected_span_id` is one of the provided span IDs.
- Re-check that `selected_span_text` exactly matches the source text for that selected span.
- Re-check that `paraphrase_choices_ko` contains exactly five unique Korean choices.
- Re-check that `correct_choice` is one of `paraphrase_choices_ko`.
- Re-check that `supporting_evidence` is copied as an exact passage snippet.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that explains surface wording, contextual meaning, and passage evidence without schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()
