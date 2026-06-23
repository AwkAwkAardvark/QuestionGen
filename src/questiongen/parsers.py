from __future__ import annotations

import re

from .schemas import GapUnit, PreparedSource, SourceUnit, SpanUnit

_TOKEN_RE = re.compile(r"[A-Za-z]+(?:[-'’][A-Za-z]+)*")
_BOUNDARY_CLOSERS = "\"')]}”’"
_COMMON_ABBREVIATIONS = {
    "a.m.",
    "dr.",
    "e.g.",
    "etc.",
    "i.e.",
    "jr.",
    "mr.",
    "mrs.",
    "ms.",
    "p.m.",
    "prof.",
    "sr.",
    "st.",
    "u.k.",
    "u.s.",
    "vs.",
}
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
    "you",
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
_PROPOSITION_CUE_WORDS = {
    "because",
    "despite",
    "if",
    "rather",
    "than",
    "therefore",
    "though",
    "while",
    "without",
}
_EVALUATIVE_CUE_WORDS = {
    "even",
    "merely",
    "only",
    "still",
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
    "spectrum",
    "status",
    "value",
    "wealth",
}
_MULTIWORD_CUE_PATTERNS = (
    "as if",
    "as though",
    "at stake",
    "end of the spectrum",
    "in fact",
    "in turn",
    "more than",
    "no longer",
    "rather than",
)
_SENTENCE_FRAGMENT_STARTERS = {
    "and",
    "because",
    "but",
    "or",
    "than",
    "though",
    "while",
    "whereas",
}
_SENTENCE_TERMINAL_FRAGMENT_WORDS = {
    "and",
    "as",
    "because",
    "if",
    "or",
    "than",
    "that",
    "though",
    "when",
    "while",
    "whereas",
}
_HANGING_EDGE_WORDS = {
    "around",
    "and",
    "as",
    "because",
    "for",
    "from",
    "if",
    "in",
    "of",
    "on",
    "or",
    "than",
    "that",
    "though",
    "to",
    "when",
    "while",
    "with",
    "without",
}
_DETERMINER_LIKE_WORDS = {
    "a",
    "an",
    "his",
    "her",
    "its",
    "my",
    "our",
    "that",
    "the",
    "their",
    "these",
    "this",
    "those",
    "your",
}
_INCOMPLETE_SPAN_EDGE_WORDS = _HANGING_EDGE_WORDS | {
    "another",
    "but",
    "brighter",
    "fewer",
    "her",
    "his",
    "its",
    "less",
    "more",
    "my",
    "older",
    "only",
    "other",
    "our",
    "rather",
    "same",
    "several",
    "such",
    "their",
    "who",
    "which",
    "whose",
    "your",
}
_PERMISSIVE_TERMINAL_PREPOSITIONS = {
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "to",
    "with",
    "without",
}
_FINITE_VERB_CUES = {
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
_IRREGULAR_VERB_CUES = {
    "been",
    "brought",
    "came",
    "come",
    "felt",
    "found",
    "gone",
    "heard",
    "kept",
    "knew",
    "left",
    "made",
    "met",
    "put",
    "read",
    "said",
    "saw",
    "set",
    "spent",
    "spoke",
    "stood",
    "stuck",
    "taught",
    "thought",
    "told",
    "took",
    "went",
    "wrote",
}
# Words that have a clear semantic opposite and therefore make a strong vocab
# corruption target: replacing one with its antonym produces an unambiguous error.
_ANTONYM_INVERTIBLE_WORDS = {
    # Negation-class verbs
    "cease", "prevent", "stop", "halt", "ban", "prohibit", "restrict",
    "avoid", "ignore", "neglect", "reject", "refuse", "oppose", "resist",
    "destroy", "harm", "damage", "ruin", "eliminate", "remove",
    "hide", "conceal", "suppress", "deny",
    # Direction verbs
    "increase", "decrease", "expand", "shrink", "grow", "reduce",
    "improve", "worsen", "strengthen", "weaken", "accelerate", "slow",
    "rise", "fall", "gain", "lose", "add", "subtract",
    "open", "close", "start", "end", "begin", "finish",
    # Clear antonym adjectives / state adjectives
    "active", "passive", "positive", "negative", "major", "minor",
    "complex", "simple", "direct", "indirect", "efficient", "inefficient",
    "effective", "ineffective", "successful", "unsuccessful",
    "stable", "unstable", "certain", "uncertain", "clear", "unclear",
    "possible", "impossible", "necessary", "unnecessary",
    "safe", "dangerous", "useful", "useless", "relevant", "irrelevant",
    "equal", "unequal", "fair", "unfair", "free", "restricted",
    "eager", "reluctant", "willing", "unwilling",
    # Common content nouns with clear antonyms
    "advantage", "disadvantage", "benefit", "harm",
    "success", "failure", "agreement", "disagreement",
    "presence", "absence", "truth", "falsehood",
    "strength", "weakness", "support", "opposition",
    "inclusion", "exclusion", "unity", "division",
    "equity", "inequity", "equality", "inequality",
}

_MAX_SPAN_CANDIDATES = 24
_MAX_SINGLE_WORD_SPAN_CANDIDATES = 48
_MAX_SENTENCE_SPAN_TOKENS = 7
_GRAMMAR_LEFT_CONTEXT_CUES = {
    "and",
    "can",
    "could",
    "did",
    "do",
    "does",
    "first",
    "he",
    "i",
    "it",
    "may",
    "might",
    "must",
    "next",
    "she",
    "should",
    "they",
    "to",
    "we",
    "will",
    "would",
    "you",
}


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    sentence_spans = _split_sentences_with_spans(text)
    if not sentence_spans:
        return []
    return [sentence for sentence, _, _ in sentence_spans]


def content_tokens(text: str) -> set[str]:
    tokens = [
        normalized
        for match in _TOKEN_RE.finditer(text)
        if (normalized := _normalize_token(match.group(0)))
    ]
    return {
        token
        for token in tokens
        if token not in _FUNCTION_WORDS and len(token) >= 3
    }


def looks_hanging_phrase(text: str) -> bool:
    tokens = [_normalize_token(match.group(0)) for match in _TOKEN_RE.finditer(text)]
    if not tokens:
        return False
    return tokens[0] in _HANGING_EDGE_WORDS or tokens[-1] in _HANGING_EDGE_WORDS


def looks_fragmentary_sentence(text: str, *, previous_text: str | None = None) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False

    tokens = [_normalize_token(match.group(0)) for match in _TOKEN_RE.finditer(normalized)]
    if not tokens:
        return False

    first_alpha = next((char for char in normalized if char.isalpha()), "")
    if previous_text and first_alpha and first_alpha.islower() and tokens[0] in _SENTENCE_FRAGMENT_STARTERS:
        return True

    if _ends_with_abbreviation(normalized) and not _has_finite_verb(tokens):
        return True

    if _looks_terminal_fragment(tokens):
        return True

    return False


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
    sentence_spans: list[tuple[str, int, int]] = []
    sentence_start = 0
    index = 0

    while index < len(normalized):
        char = normalized[index]
        if char not in ".!?":
            index += 1
            continue

        boundary_end = index
        while boundary_end + 1 < len(normalized) and normalized[boundary_end + 1] in _BOUNDARY_CLOSERS:
            boundary_end += 1

        if not _is_sentence_boundary(normalized, index, boundary_end):
            index = boundary_end + 1
            continue

        sentence = normalized[sentence_start : boundary_end + 1].strip()
        if sentence:
            relative_start = normalized.find(sentence, sentence_start)
            if relative_start < 0:
                relative_start = sentence_start
            relative_end = relative_start + len(sentence)
            sentence_spans.append(
                (
                    sentence,
                    leading_whitespace + relative_start,
                    leading_whitespace + relative_end,
                )
            )

        sentence_start = _skip_whitespace(normalized, boundary_end + 1)
        index = sentence_start

    remainder = normalized[sentence_start:].strip()
    if remainder:
        relative_start = normalized.find(remainder, sentence_start)
        if relative_start < 0:
            relative_start = sentence_start
        relative_end = relative_start + len(remainder)
        sentence_spans.append(
            (
                remainder,
                leading_whitespace + relative_start,
                leading_whitespace + relative_end,
            )
        )

    return sentence_spans


def _prepare_span_units(
    sentence_units: list[SourceUnit],
    sentence_spans: list[tuple[str, int, int]],
) -> list[SpanUnit]:
    raw_candidates: list[dict[str, object]] = []
    single_word_candidates: list[dict[str, object]] = []
    for sentence_unit, (sentence_text, sentence_start, _) in zip(sentence_units, sentence_spans):
        raw_candidates.extend(
            _collect_sentence_span_candidates(
                sentence_text=sentence_text,
                sentence_start=sentence_start,
                sentence_unit=sentence_unit,
            )
        )
        single_word_candidates.extend(
            _collect_single_word_span_candidates(
                sentence_text=sentence_text,
                sentence_start=sentence_start,
                sentence_unit=sentence_unit,
            )
        )

    selected_candidates = _select_span_candidates(raw_candidates)
    selected_candidates.extend(_select_single_word_candidates(single_word_candidates))
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
        for end_index in range(start_index + 2, min(len(token_matches), start_index + _MAX_SENTENCE_SPAN_TOKENS) + 1):
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


def _collect_single_word_span_candidates(
    *,
    sentence_text: str,
    sentence_start: int,
    sentence_unit: SourceUnit,
) -> list[dict[str, object]]:
    token_matches = list(_TOKEN_RE.finditer(sentence_text))
    candidates: list[dict[str, object]] = []

    for token_index, token_match in enumerate(token_matches):
        token_text = token_match.group(0)
        lowered = _normalize_token(token_text)
        if lowered in _FUNCTION_WORDS or len(lowered) < 4:
            continue

        priority_score, heuristic_tags = _score_single_word_candidate(
            token_matches=token_matches,
            token_index=token_index,
            token_text=token_text,
        )
        if priority_score < 3:
            continue

        context_before = sentence_text[max(0, token_match.start() - 28) : token_match.start()].strip() or None
        context_after = sentence_text[token_match.end() : min(len(sentence_text), token_match.end() + 28)].strip() or None
        candidates.append(
            {
                "text": token_text,
                "char_start": sentence_start + token_match.start(),
                "char_end": sentence_start + token_match.end(),
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
    lowered_tokens = [_normalize_token(token) for token in token_texts]
    candidate_lowered = candidate_text.lower()
    content = [token for token in lowered_tokens if token not in _FUNCTION_WORDS]
    if len(content) < 1:
        return 0, []
    if looks_hanging_phrase(candidate_text):
        return 0, []
    previous_token = _normalize_token(token_matches[start_index - 1].group(0)) if start_index > 0 else ""
    next_token = _normalize_token(token_matches[end_index].group(0)) if end_index < len(token_matches) else ""
    if _looks_incomplete_span_boundary(lowered_tokens, previous_token=previous_token, next_token=next_token):
        return 0, []

    score = 0
    tags: list[str] = []
    has_clause_signal = _span_has_clause_signal(lowered_tokens)
    crosses_punctuation = any(punct in candidate_text for punct in (",", ";", ":", " - ", " — ", " – ", "(", ")"))

    if 2 <= len(token_texts) <= 5:
        score += 2
    elif len(token_texts) in {6, 7}:
        score += 1
    if len(content) >= 2:
        score += 1
    if any(token in _CONTEXTUAL_CUE_WORDS for token in lowered_tokens):
        score += 2
        tags.append("contextual_cue")
    if any(token in _ABSTRACT_CUE_WORDS for token in lowered_tokens):
        score += 2
        tags.append("abstract_term")
    if any(pattern in candidate_lowered for pattern in _MULTIWORD_CUE_PATTERNS):
        score += 2
        tags.append("phrase_frame")
    if any(token in _EVALUATIVE_CUE_WORDS for token in lowered_tokens):
        score += 1
        tags.append("evaluative")
    if "rather than" in candidate_lowered and "abstract_term" not in tags:
        score -= 3
        tags.append("surface_comparison")
    if start_index > 0 and end_index < len(token_matches):
        score += 1
        tags.append("embedded_phrase")
    if any(len(token) >= 8 for token in content):
        score += 1
        tags.append("dense_lexis")
    if has_clause_signal:
        score += 2
        tags.append("clause_like")
    if crosses_punctuation:
        if has_clause_signal:
            score -= 1
            tags.append("punctuation_crossing")
        else:
            return 0, []
    if {"contextual_cue", "abstract_term"} <= set(tags) or (
        "phrase_frame" in tags and "surface_comparison" not in tags
    ):
        score += 1
        tags.append("claim_bearing")
    if has_clause_signal and (
        {"contextual_cue", "abstract_term"} & set(tags) or any(token in _PROPOSITION_CUE_WORDS for token in lowered_tokens)
    ):
        score += 1
        tags.append("proposition_like")
    if len(token_texts) == 2 and not {"contextual_cue", "abstract_term", "phrase_frame"} & set(tags):
        score -= 1

    return score, sorted(set(tags))


def _score_single_word_candidate(
    *,
    token_matches: list[re.Match[str]],
    token_index: int,
    token_text: str,
) -> tuple[int, list[str]]:
    lowered = _normalize_token(token_text)
    score = 3
    tags = ["single_word"]

    if lowered in _ABSTRACT_CUE_WORDS:
        score += 2
        tags.append("abstract_term")
    if lowered in _CONTEXTUAL_CUE_WORDS:
        score += 1
        tags.append("contextual_cue")
    if len(lowered) >= 7:
        score += 1
        tags.append("dense_lexis")

    previous_token = _normalize_token(token_matches[token_index - 1].group(0)) if token_index > 0 else ""
    next_token = _normalize_token(token_matches[token_index + 1].group(0)) if token_index + 1 < len(token_matches) else ""
    # --- vocab candidate tagging ---
    if lowered not in _FINITE_VERB_CUES:
        tags.append("vocab_candidate")
        score += 1

    # antonym_invertible: clear semantic opposite exists, so corruption = strong contextual error
    if _looks_antonym_invertible(lowered):
        tags.append("antonym_invertible")
        score += 2

    # --- grammar candidate tagging ---
    if _looks_grammar_target(lowered, previous_token=previous_token, next_token=next_token):
        score += 2
        tags.append("grammar_candidate")
        tags.append("verb_form_candidate")
        if previous_token == "to":
            score += 1
            tags.append("to_infinitive_context")
        if previous_token in {"can", "could", "may", "might", "must", "should", "will", "would"}:
            score += 1
            tags.append("modal_context")
        if previous_token in {"am", "are", "be", "been", "being", "is", "was", "were"}:
            tags.append("be_context")

    if previous_token in _GRAMMAR_LEFT_CONTEXT_CUES:
        score += 1
        tags.append("local_context")

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


def _select_single_word_candidates(raw_candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    if not raw_candidates:
        return []

    selected: list[dict[str, object]] = []
    seen_bounds: set[tuple[int, int]] = set()
    for candidate in sorted(
        raw_candidates,
        key=lambda item: (
            -int(item["priority_score"]),
            int(item["char_start"]),
            int(item["char_end"]),
        ),
    ):
        bounds = (int(candidate["char_start"]), int(candidate["char_end"]))
        if bounds in seen_bounds:
            continue
        selected.append(candidate)
        seen_bounds.add(bounds)
        if len(selected) >= _MAX_SINGLE_WORD_SPAN_CANDIDATES:
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


def _is_sentence_boundary(text: str, period_index: int, boundary_end: int) -> bool:
    next_index = _skip_whitespace(text, boundary_end + 1)
    if next_index >= len(text):
        return True

    if text[period_index] == "." and _looks_like_nonterminal_period(text, period_index):
        return False

    next_char = text[next_index]
    if next_char.islower():
        return False
    return True


def _looks_like_nonterminal_period(text: str, period_index: int) -> bool:
    previous_char = text[period_index - 1] if period_index > 0 else ""
    next_char = text[period_index + 1] if period_index + 1 < len(text) else ""
    if previous_char.isdigit() and next_char.isdigit():
        return True
    if previous_char.isupper() and next_char.isupper():
        if period_index + 2 < len(text) and text[period_index + 2] == ".":
            return True

    if _ends_with_abbreviation(text[: period_index + 1]):
        next_index = _skip_whitespace(text, period_index + 1)
        if next_index < len(text):
            return True

    return False


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _ends_with_abbreviation(text: str) -> bool:
    stripped = text.strip().lower()
    if any(stripped.endswith(abbreviation) for abbreviation in _COMMON_ABBREVIATIONS):
        return True
    return re.search(r"(?:\b[A-Za-z]\.){2,}$", stripped) is not None


def _has_finite_verb(tokens: list[str]) -> bool:
    for token in tokens:
        if token in _FINITE_VERB_CUES:
            return True
        if len(token) >= 4 and token.endswith("ed"):
            return True
    return False


def _looks_terminal_fragment(tokens: list[str]) -> bool:
    last_token = tokens[-1]
    if last_token in _SENTENCE_TERMINAL_FRAGMENT_WORDS:
        return True
    if last_token not in _HANGING_EDGE_WORDS:
        return False
    if last_token in _PERMISSIVE_TERMINAL_PREPOSITIONS:
        return not _looks_complete_terminal_preposition_clause(tokens)
    return True


def _looks_complete_terminal_preposition_clause(tokens: list[str]) -> bool:
    if len(tokens) < 5 or not _has_finite_verb(tokens):
        return False

    content = [token for token in tokens if token not in _FUNCTION_WORDS]
    if len(content) < 2:
        return False

    tail_token = tokens[-2]
    if tail_token in _FINITE_VERB_CUES or tail_token in _IRREGULAR_VERB_CUES:
        return True
    if tail_token.endswith("ed") or tail_token.endswith("en"):
        return True
    if len(tokens) >= 6 and tokens[-3] in _FINITE_VERB_CUES and tail_token in {"already", "ever", "just", "never", "still"}:
        return True
    if len(tokens) >= 6 and tokens[-3] == "to":
        return True
    return False


def _normalize_token(token: str) -> str:
    lowered = token.lower().strip("'’")
    if lowered.endswith("'s") or lowered.endswith("’s"):
        lowered = lowered[:-2]
    if len(lowered) > 4 and lowered.endswith("ies"):
        return lowered[:-3] + "y"
    if len(lowered) > 4 and lowered.endswith("es") and not lowered.endswith("ses"):
        return lowered[:-2]
    if len(lowered) > 3 and lowered.endswith("s") and not lowered.endswith("ss"):
        return lowered[:-1]
    return lowered


def _looks_antonym_invertible(lowered: str) -> bool:
    return lowered in _ANTONYM_INVERTIBLE_WORDS


def _looks_grammar_target(current_token: str, *, previous_token: str, next_token: str) -> bool:
    if current_token in _FINITE_VERB_CUES or current_token in _IRREGULAR_VERB_CUES:
        return True
    if current_token.endswith("ing") and len(current_token) > 4:
        return True
    if current_token.endswith("ed") and len(current_token) > 4:
        return True
    if previous_token == "to":
        return True
    if previous_token in {"can", "could", "may", "might", "must", "should", "will", "would"}:
        return True
    if previous_token in {"am", "are", "be", "been", "being", "is", "was", "were"}:
        return True
    if current_token.endswith("s") and previous_token in {
        "he",
        "it",
        "she",
        "this",
        "that",
    }:
        return True
    if next_token in {"to", "that"} and current_token in _IRREGULAR_VERB_CUES:
        return True
    return False


def _span_has_clause_signal(tokens: list[str]) -> bool:
    for token in tokens:
        if token in _FINITE_VERB_CUES or token in _IRREGULAR_VERB_CUES:
            return True
        if len(token) > 4 and token.endswith("ed"):
            return True
        if len(token) > 4 and token.endswith("ing"):
            return True
    return any(token in _PROPOSITION_CUE_WORDS for token in tokens)


def _looks_incomplete_span_boundary(tokens: list[str], *, previous_token: str, next_token: str) -> bool:
    if not tokens:
        return True

    first_token = tokens[0]
    last_token = tokens[-1]
    if previous_token and first_token in _INCOMPLETE_SPAN_EDGE_WORDS:
        return True
    if last_token in _INCOMPLETE_SPAN_EDGE_WORDS:
        return True
    if next_token in _DETERMINER_LIKE_WORDS and (
        last_token.endswith("ing")
        or last_token.endswith("ed")
        or last_token.endswith("er")
        or (len(tokens) >= 2 and tokens[-2] in {"to", "can", "could", "may", "might", "must", "should", "will", "would"})
    ):
        return True
    if next_token and len(tokens) >= 2 and tokens[-2] in _DETERMINER_LIKE_WORDS and last_token not in _FINITE_VERB_CUES:
        return True
    if next_token and last_token in {"relative"}:
        return True
    return False
