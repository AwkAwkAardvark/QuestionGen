from __future__ import annotations

import re
from typing import Iterable

from .parsers import normalize_text
from .schemas import PreparedSource, SpanUnit

BLANK_MARKER = "_____"
NUMBERED_UNDERLINE_OPEN_TEMPLATE = "[밑줄{marker}]"
NUMBERED_UNDERLINE_CLOSE_TEMPLATE = "[/밑줄{marker}]"

_SINGLE_WORD_RE = re.compile(r"^[A-Za-z]+(?:[-'’][A-Za-z]+)*$")
_ENGLISH_WORD_RE = re.compile(r"^[A-Za-z]+(?:[-'’][A-Za-z]+)*$")

_FINITE_AUXILIARIES = {
    "am",
    "are",
    "be",
    "been",
    "being",
    "can",
    "could",
    "did",
    "do",
    "does",
    "had",
    "has",
    "have",
    "is",
    "may",
    "might",
    "must",
    "shall",
    "should",
    "was",
    "were",
    "will",
    "would",
}
_IRREGULAR_VARIANTS = {
    "be": {"am", "are", "be", "been", "being", "is", "was", "were"},
    "begin": {"begin", "began", "begun", "begins", "beginning"},
    "bring": {"bring", "brings", "bringing", "brought"},
    "come": {"came", "come", "comes", "coming"},
    "do": {"did", "do", "does", "doing", "done"},
    "feel": {"feel", "feeling", "feels", "felt"},
    "find": {"find", "finding", "finds", "found"},
    "go": {"go", "goes", "going", "gone", "went"},
    "grow": {"grew", "grow", "growing", "grows", "grown"},
    "have": {"had", "has", "have", "having"},
    "hear": {"hear", "hearing", "heard", "hears"},
    "keep": {"keep", "keeping", "keeps", "kept"},
    "know": {"knew", "know", "knowing", "known", "knows"},
    "lead": {"lead", "leading", "leads", "led"},
    "leave": {"leave", "leaves", "leaving", "left"},
    "make": {"made", "make", "makes", "making"},
    "read": {"read", "reading", "reads"},
    "run": {"ran", "run", "running", "runs"},
    "see": {"saw", "see", "seeing", "seen", "sees"},
    "show": {"show", "showing", "shown", "shows"},
    "speak": {"speak", "speaking", "speaks", "spoke", "spoken"},
    "take": {"take", "taken", "takes", "taking", "took"},
    "think": {"think", "thinking", "thinks", "thought"},
    "use": {"use", "used", "uses", "using"},
    "write": {"write", "writes", "writing", "written", "wrote"},
}


def phrase_span_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return [
        span
        for span in prepared_source.span_units
        if "single_word" not in span.heuristic_tags
    ]


def vocab_target_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return _dedupe_by_text(
        span
        for span in prepared_source.span_units
        if "single_word" in span.heuristic_tags and "vocab_candidate" in span.heuristic_tags
    )


def grammar_target_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return _dedupe_by_text(
        span
        for span in prepared_source.span_units
        if "single_word" in span.heuristic_tags and "grammar_candidate" in span.heuristic_tags
    )


def numbered_underline_open(marker: str) -> str:
    return NUMBERED_UNDERLINE_OPEN_TEMPLATE.format(marker=marker)


def numbered_underline_close(marker: str) -> str:
    return NUMBERED_UNDERLINE_CLOSE_TEMPLATE.format(marker=marker)


def render_numbered_span_edits(
    *,
    source_text: str,
    selected_spans: list[SpanUnit],
    replacement_by_span_id: dict[str, str] | None,
    markers: list[str],
) -> str:
    replacement_by_span_id = replacement_by_span_id or {}
    ordered_spans = sorted(selected_spans, key=lambda span: span.char_start)
    pieces: list[str] = []
    cursor = 0

    for marker, span in zip(markers, ordered_spans):
        pieces.append(source_text[cursor:span.char_start])
        replacement_text = replacement_by_span_id.get(span.id, span.text)
        pieces.append(f"{numbered_underline_open(marker)}{replacement_text}{numbered_underline_close(marker)}")
        cursor = span.char_end

    pieces.append(source_text[cursor:])
    return "".join(pieces)


def is_single_english_word(value: str) -> bool:
    return _SINGLE_WORD_RE.fullmatch(value.strip()) is not None


def normalize_english_choice(value: str) -> str:
    return normalize_text(value)


def normalize_english_word(value: str) -> str:
    return value.strip().lower().replace("’", "'")


def allowed_verb_form_variants(word: str) -> set[str]:
    normalized = normalize_english_word(word)
    if not normalized or _ENGLISH_WORD_RE.fullmatch(word.strip()) is None:
        return set()
    if normalized in _IRREGULAR_VARIANTS:
        return set(_IRREGULAR_VARIANTS[normalized])

    base = _approximate_base_form(normalized)
    if not base:
        return {normalized}

    variants = {base, f"{base}s", f"{base}ed", f"{base}ing"}
    if base.endswith("e") and len(base) > 2:
        variants.add(f"{base[:-1]}ing")
        variants.add(f"{base}d")
    if len(base) >= 3 and base.endswith("y") and base[-2] not in "aeiou":
        variants.add(f"{base[:-1]}ies")
        variants.add(f"{base[:-1]}ied")
    return {variant for variant in variants if variant}


def is_auxiliary_like(word: str) -> bool:
    return normalize_english_word(word) in _FINITE_AUXILIARIES


def _dedupe_by_text(spans: Iterable[SpanUnit]) -> list[SpanUnit]:
    ordered = sorted(
        spans,
        key=lambda span: (-span.priority_score, span.char_start, span.char_end),
    )
    selected: list[SpanUnit] = []
    seen_texts: set[str] = set()
    for span in ordered:
        normalized_text = normalize_english_word(span.text)
        if normalized_text in seen_texts:
            continue
        selected.append(span)
        seen_texts.add(normalized_text)
    return selected


def _approximate_base_form(word: str) -> str:
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        if stem.endswith("k") and not stem.endswith("ck"):
            return stem
        if stem.endswith("v"):
            return stem + "e"
        return stem
    if word.endswith("ied") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ed") and len(word) > 4:
        stem = word[:-2]
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        if stem.endswith("i"):
            return stem[:-1] + "y"
        if stem.endswith("us"):
            return stem + "e"
        return stem
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        return word[:-1]
    return word
