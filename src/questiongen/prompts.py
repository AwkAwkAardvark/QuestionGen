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
- Keep the explanation in Korean.
- Return only structured data matching the schema.
""".strip()
