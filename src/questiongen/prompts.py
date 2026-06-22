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
