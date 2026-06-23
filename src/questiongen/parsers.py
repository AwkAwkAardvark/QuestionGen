from __future__ import annotations

import re

from .schemas import GapUnit, PreparedSource, SourceUnit, SpanUnit

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:[-'’][A-Za-z]+)*")
_FUNCTION_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
}
_CONTEXTUAL_CUE_WORDS = {
    "against",
    "because",
    "beyond",
    "depends",
    "despite",
    "less",
    "more",
    "not",
    "only",
    "rather",
    "relative",
    "than",
    "though",
    "while",
    "without",
}
_ABSTRACT_CUE_WORDS = {
    "ability",
    "assumption",
    "attention",
    "belief",
    "change",
    "claim",
    "confidence",
    "consequence",
    "context",
    "discontent",
    "effect",
    "emotion",
    "evidence",
    "expectation",
    "freedom",
    "growth",
    "happiness",
    "idea",
    "inequality",
    "influence",
    "limitation",
    "meaning",
    "motive",
    "outcome",
    "pattern",
    "perspective",
    "pressure",
    "priority",
    "relation",
    "response",
    "risk",
    "shift",
    "signal",
    "status",
    "value",
    "wealth",
}
_MULTIWORD_CUE_PATTERNS = (
    "as if",
    "as though",
    "at stake",
    "in fact",
    "in turn",
    "more than",
    "no longer",
    "rather than",
)
_MAX_SPAN_CANDIDATES = 24


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    sentence_spans = _split_sentences_with_spans(text)
    if not sentence_spans:
        return []
    return [sentence for sentence, _, _ in sentence_spans]


def prepare_source(source_paragraph: str) -> PreparedSource:
    sentence_spans = _split_sentences_with_spans(source_paragraph)
    sentence_texts = [sentence for sentence, _, _ in sentence_spans]
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

    span_units = _prepare_span_units(sentence_units, sentence_spans)
    return PreparedSource(
        source_text=source_paragraph,
        sentence_units=sentence_units,
        gap_units=gap_units,
        span_units=span_units,
    )


def _split_sentences_with_spans(text: str) -> list[tuple[str, int, int]]:
    normalized = text.strip()
    if not normalized:
        return []

    leading_whitespace = len(text) - len(text.lstrip())
    parts = _SENTENCE_SPLIT_RE.split(normalized)
    cursor = 0
    sentence_spans: list[tuple[str, int, int]] = []

    for part in parts:
        sentence = part.strip()
        if not sentence:
            continue
        relative_start = normalized.find(sentence, cursor)
        if relative_start < 0:
            relative_start = cursor
        relative_end = relative_start + len(sentence)
        sentence_spans.append(
            (
                sentence,
                leading_whitespace + relative_start,
                leading_whitespace + relative_end,
            )
        )
        cursor = relative_end

    return sentence_spans


def _prepare_span_units(
    sentence_units: list[SourceUnit],
    sentence_spans: list[tuple[str, int, int]],
) -> list[SpanUnit]:
    raw_candidates: list[dict[str, object]] = []
    for sentence_unit, (sentence_text, sentence_start, _) in zip(sentence_units, sentence_spans):
        raw_candidates.extend(
            _collect_sentence_span_candidates(
                sentence_text=sentence_text,
                sentence_start=sentence_start,
                sentence_unit=sentence_unit,
            )
        )

    selected_candidates = _select_span_candidates(raw_candidates)
    selected_candidates.sort(key=lambda candidate: (int(candidate["char_start"]), int(candidate["char_end"])))

    return [
        SpanUnit(
            id=f"P{index}",
            text=str(candidate["text"]),
            normalized_text=normalize_text(str(candidate["text"])),
            char_start=int(candidate["char_start"]),
            char_end=int(candidate["char_end"]),
            sentence_unit_id=str(candidate["sentence_unit_id"]),
            sentence_index=int(candidate["sentence_index"]),
            context_before=candidate["context_before"],
            context_after=candidate["context_after"],
            heuristic_tags=list(candidate["heuristic_tags"]),
            priority_score=int(candidate["priority_score"]),
        )
        for index, candidate in enumerate(selected_candidates)
    ]


def _collect_sentence_span_candidates(
    *,
    sentence_text: str,
    sentence_start: int,
    sentence_unit: SourceUnit,
) -> list[dict[str, object]]:
    token_matches = list(_TOKEN_RE.finditer(sentence_text))
    candidates: list[dict[str, object]] = []

    for start_index in range(len(token_matches)):
        for end_index in range(start_index + 2, min(len(token_matches), start_index + 6) + 1):
            start_match = token_matches[start_index]
            end_match = token_matches[end_index - 1]
            candidate_text = sentence_text[start_match.start() : end_match.end()]
            priority_score, heuristic_tags = _score_span_candidate(
                token_matches=token_matches,
                start_index=start_index,
                end_index=end_index,
                candidate_text=candidate_text,
            )
            if priority_score < 3:
                continue

            context_before = sentence_text[max(0, start_match.start() - 36) : start_match.start()].strip() or None
            context_after = sentence_text[end_match.end() : min(len(sentence_text), end_match.end() + 36)].strip() or None
            candidates.append(
                {
                    "text": candidate_text,
                    "char_start": sentence_start + start_match.start(),
                    "char_end": sentence_start + end_match.end(),
                    "sentence_unit_id": sentence_unit.id,
                    "sentence_index": sentence_unit.index,
                    "context_before": context_before,
                    "context_after": context_after,
                    "heuristic_tags": heuristic_tags,
                    "priority_score": priority_score,
                }
            )

    return candidates


def _score_span_candidate(
    *,
    token_matches: list[re.Match[str]],
    start_index: int,
    end_index: int,
    candidate_text: str,
) -> tuple[int, list[str]]:
    token_texts = [match.group(0) for match in token_matches[start_index:end_index]]
    lowered_tokens = [token.lower() for token in token_texts]
    content_tokens = [token for token in lowered_tokens if token not in _FUNCTION_WORDS]
    if len(content_tokens) < 1:
        return 0, []

    score = 0
    tags: list[str] = []

    if 2 <= len(token_texts) <= 5:
        score += 2
    if len(content_tokens) >= 2:
        score += 1
    if any(token in _CONTEXTUAL_CUE_WORDS for token in lowered_tokens):
        score += 2
        tags.append("contextual_cue")
    if any(token in _ABSTRACT_CUE_WORDS for token in lowered_tokens):
        score += 2
        tags.append("abstract_term")
    if any(pattern in candidate_text.lower() for pattern in _MULTIWORD_CUE_PATTERNS):
        score += 2
        tags.append("phrase_frame")
    if start_index > 0 and end_index < len(token_matches):
        score += 1
        tags.append("embedded_phrase")
    if any(len(token) >= 8 for token in content_tokens):
        score += 1
        tags.append("dense_lexis")
    if {"contextual_cue", "abstract_term"} <= set(tags) or "phrase_frame" in tags:
        score += 1
        tags.append("claim_bearing")
    if len(token_texts) == 2 and not {"contextual_cue", "abstract_term", "phrase_frame"} & set(tags):
        score -= 1

    return score, sorted(set(tags))


def _select_span_candidates(raw_candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    if not raw_candidates:
        return []

    selected: list[dict[str, object]] = []
    seen_normalized: set[str] = set()
    for candidate in sorted(
        raw_candidates,
        key=lambda item: (
            -int(item["priority_score"]),
            -(int(item["char_end"]) - int(item["char_start"])),
            int(item["char_start"]),
            int(item["char_end"]),
        ),
    ):
        normalized = normalize_text(str(candidate["text"])).lower()
        if normalized in seen_normalized:
            continue
        if any(_overlaps_too_much(candidate, existing) for existing in selected):
            continue
        selected.append(candidate)
        seen_normalized.add(normalized)
        if len(selected) >= _MAX_SPAN_CANDIDATES:
            break
    return selected


def _overlaps_too_much(left: dict[str, object], right: dict[str, object]) -> bool:
    left_start = int(left["char_start"])
    left_end = int(left["char_end"])
    right_start = int(right["char_start"])
    right_end = int(right["char_end"])

    overlap = max(0, min(left_end, right_end) - max(left_start, right_start))
    if overlap == 0:
        return False

    shorter = min(left_end - left_start, right_end - right_start)
    return overlap / shorter > 0.6
