from __future__ import annotations

import re

from .schemas import GapUnit, PreparedSource, SourceUnit

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    parts = _SENTENCE_SPLIT_RE.split(normalized)
    sentences = [part.strip() for part in parts if part.strip()]
    return sentences if sentences else [normalized]


def prepare_source(source_paragraph: str) -> PreparedSource:
    sentence_texts = split_sentences(source_paragraph)
    sentence_units = [
        SourceUnit(id=f"S{index}", text=text, index=index)
        for index, text in enumerate(sentence_texts)
    ]

    gap_units: list[GapUnit] = []
    for index in range(len(sentence_units) + 1):
        before_unit_id = sentence_units[index - 1].id if index > 0 else None
        after_unit_id = sentence_units[index].id if index < len(sentence_units) else None
        gap_units.append(
            GapUnit(
                id=f"G{index}",
                index=index,
                before_unit_id=before_unit_id,
                after_unit_id=after_unit_id,
            )
        )

    return PreparedSource(sentence_units=sentence_units, gap_units=gap_units)
