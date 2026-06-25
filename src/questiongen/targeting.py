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
_LEXICAL_CHOICE_RE = re.compile(r"^[A-Za-z]+(?:[-'’][A-Za-z]+)*(?: [A-Za-z]+(?:[-'’][A-Za-z]+)*){0,3}$")
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:[-'’][A-Za-z]+)*")
_CROSS_PUNCTUATION_RE = re.compile(r"[,;:()]|(?:\s[-–—]\s)")
_INNER_PROPER_NOUN_RE = re.compile(r"(?<!^)\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")
_TECHNICAL_LABEL_RE = re.compile(r"\b(?:[A-Z]{2,}|\w*\d\w*)\b")

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
_FINITE_VERB_CUES = _FINITE_AUXILIARIES | {
    "did",
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
    "without",
    "you",
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
_DISCOURSE_CUE_WORDS = {
    "although",
    "because",
    "but",
    "despite",
    "even",
    "however",
    "instead",
    "only",
    "rather",
    "so",
    "still",
    "therefore",
    "though",
    "while",
    "without",
    "yet",
}
_POLARITY_SCOPE_CUE_WORDS = {
    "all",
    "always",
    "any",
    "barely",
    "broad",
    "broader",
    "broadly",
    "each",
    "entire",
    "entirely",
    "every",
    "few",
    "fewer",
    "fully",
    "hardly",
    "higher",
    "largely",
    "less",
    "little",
    "lower",
    "mainly",
    "many",
    "more",
    "most",
    "much",
    "narrow",
    "narrower",
    "narrowly",
    "never",
    "no",
    "none",
    "not",
    "nothing",
    "only",
    "partly",
    "rarely",
    "scarcely",
    "several",
    "slightly",
    "some",
    "too",
    "under",
    "very",
    "without",
}
_BROAD_OPPOSITE_HINTS = {
    "accept": {"reject", "refuse"},
    "allow": {"block", "deny", "prevent"},
    "benefit": {"harm", "hurt"},
    "cease": {"continue", "maintain"},
    "expand": {"contract", "limit", "reduce", "shrink"},
    "fail": {"succeed"},
    "ignore": {"heed", "notice"},
    "increase": {"decrease", "lower", "reduce"},
    "lead": {"follow"},
    "protect": {"damage", "expose", "harm"},
    "reduce": {"increase", "raise"},
    "support": {"oppose", "undermine"},
    "weaken": {"strengthen"},
}
_INCOMPLETE_EDGE_WORDS = {
    "a",
    "an",
    "another",
    "but",
    "few",
    "her",
    "his",
    "its",
    "less",
    "many",
    "more",
    "my",
    "much",
    "older",
    "other",
    "our",
    "rather",
    "same",
    "several",
    "such",
    "that",
    "the",
    "their",
    "these",
    "this",
    "those",
    "who",
    "which",
    "whose",
    "your",
}
_LOW_VALUE_FACTUAL_WORDS = {
    "area",
    "blocks",
    "book",
    "books",
    "boy",
    "boys",
    "city",
    "days",
    "field",
    "girl",
    "girls",
    "man",
    "men",
    "month",
    "months",
    "people",
    "report",
    "reports",
    "road",
    "roads",
    "room",
    "rooms",
    "station",
    "street",
    "streets",
    "system",
    "systems",
    "teacher",
    "teachers",
    "thing",
    "things",
    "time",
    "times",
    "week",
    "weeks",
    "woman",
    "women",
    "year",
    "years",
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
    "rethink": {"rethink", "rethinking", "rethinks", "rethought"},
    "understand": {"understand", "understanding", "understands", "understood"},
    "use": {"use", "used", "uses", "using"},
    "write": {"write", "writes", "writing", "written", "wrote"},
}
_IRREGULAR_VARIANT_INDEX = {
    variant: base
    for base, variants in _IRREGULAR_VARIANTS.items()
    for variant in variants
}


def phrase_span_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return [
        span
        for span in prepared_source.span_units
        if "single_word" not in span.heuristic_tags
    ]


def underlined_phrase_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    candidates = [
        span
        for span in phrase_span_inventory(prepared_source)
        if underlined_span_quality_error(span) is None
    ]
    return sorted(candidates, key=_underlined_span_sort_key)


def fill_blank_target_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    candidates = [
        span
        for span in phrase_span_inventory(prepared_source)
        if fill_blank_span_quality_error(span) is None
    ]
    return sorted(candidates, key=_fill_blank_span_sort_key)


def fill_blank_connective_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    candidates = [
        span
        for span in phrase_span_inventory(prepared_source)
        if fill_blank_connective_quality_error(span) is None
    ]
    return sorted(candidates, key=_fill_blank_connective_sort_key)


def fill_blank_summary_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    candidates = [
        span
        for span in phrase_span_inventory(prepared_source)
        if fill_blank_summary_quality_error(span) is None
    ]
    return sorted(candidates, key=_fill_blank_summary_sort_key)


def vocab_target_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return _dedupe_by_text(
        span
        for span in prepared_source.span_units
        if "single_word" in span.heuristic_tags and "vocab_candidate" in span.heuristic_tags
    )


def vocab_choice_inventory(
    prepared_source: PreparedSource,
    subtype_key: str = "contextual_vocab_choice_5",
) -> list[SpanUnit]:
    return sorted(
        _dedupe_by_text(
            span
            for span in prepared_source.span_units
            if vocab_choice_target_quality_error(span, subtype_key=subtype_key) is None
        ),
        key=_vocab_choice_sort_key,
    )


def vocab_hard_candidate_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return sorted(
        _dedupe_by_text(
            span
            for span in prepared_source.span_units
            if vocab_choice_target_quality_error(span, subtype_key="contextual_vocab_choice_5") is None
        ),
        key=_vocab_choice_sort_key,
    )


def grammar_target_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return _dedupe_by_text(
        span
        for span in prepared_source.span_units
        if "single_word" in span.heuristic_tags and "grammar_candidate" in span.heuristic_tags
    )


def grammar_subtype_inventory(prepared_source: PreparedSource, subtype_key: str) -> list[SpanUnit]:
    inventory = grammar_target_inventory(prepared_source)
    if subtype_key == "grammar_error_verb_form_5":
        return [span for span in inventory if "verb_form_candidate" in span.heuristic_tags]
    if subtype_key == "grammar_error_subject_verb_agreement_5":
        return [span for span in inventory if "subject_verb_agreement_candidate" in span.heuristic_tags]
    if subtype_key == "grammar_error_finite_nonfinite_5":
        return [span for span in inventory if "finite_nonfinite_candidate" in span.heuristic_tags]
    if subtype_key == "grammar_error_participle_voice_5":
        return [span for span in inventory if "participle_voice_candidate" in span.heuristic_tags]
    if subtype_key == "grammar_error_relative_clause_5":
        return [span for span in inventory if "relative_clause_candidate" in span.heuristic_tags]
    if subtype_key == "grammar_error_noun_clause_introducer_5":
        return [span for span in inventory if "noun_clause_candidate" in span.heuristic_tags]
    if subtype_key == "grammar_error_parallel_structure_5":
        return [span for span in inventory if "parallel_structure_candidate" in span.heuristic_tags]
    if subtype_key == "grammar_error_conjunction_preposition_5":
        return [span for span in inventory if "conjunction_preposition_candidate" in span.heuristic_tags]
    return inventory


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
    irregular_base = _IRREGULAR_VARIANT_INDEX.get(normalized)
    if irregular_base is not None:
        return set(_IRREGULAR_VARIANTS[irregular_base])

    base = _approximate_base_form(normalized)
    if not base:
        return {normalized}

    variants = {
        base,
        _regular_third_person_singular(base),
        _regular_past_form(base),
        _regular_present_participle(base),
    }
    return {variant for variant in variants if variant}


def is_auxiliary_like(word: str) -> bool:
    return normalize_english_word(word) in _FINITE_AUXILIARIES


def span_crosses_punctuation(text: str) -> bool:
    return _CROSS_PUNCTUATION_RE.search(text) is not None


def span_shape_label(span: SpanUnit) -> str:
    tags = set(span.heuristic_tags)
    if _has_proposition_signal(span.text, tags):
        return "proposition"
    if "claim_bearing" in tags:
        return "claim"
    if "phrase_frame" in tags or "abstract_term" in tags:
        return "phrase"
    return "local"


def underlined_span_quality_error(span: SpanUnit) -> str | None:
    tags = set(span.heuristic_tags)
    tokens = _span_tokens(span.text)
    content_count = _content_word_count(tokens)
    has_clause_signal = _has_clause_signal(span.text, tags)
    has_proposition_signal = _has_proposition_signal(span.text, tags)

    if not tokens:
        return "Selected span is empty for underlined_phrase_meaning."
    if "single_word" in tags:
        return "Selected span is too short for underlined_phrase_meaning."
    if content_count < 2:
        return "Selected span is too short or too function-word heavy for underlined_phrase_meaning."
    if _has_incomplete_edge(tokens, span):
        return "Selected span is fragmentary and leaves an awkward semantic chunk."
    if span_crosses_punctuation(span.text) and not has_clause_signal:
        return "Selected span crosses punctuation without forming a complete clause-level unit."
    if span.priority_score < 5:
        return "Selected span is too literal or weak for underlined_phrase_meaning."
    if "surface_comparison" in tags and "abstract_term" not in tags:
        return "Selected span is a surface comparison phrase, not a central contextual target."
    if not (
        {"abstract_term", "claim_bearing", "phrase_frame"} & tags
        or (has_proposition_signal and ("evaluative" in tags or "abstract_term" in tags))
    ):
        return "Selected span is not central enough to the passage claim for underlined_phrase_meaning."
    if "embedded_phrase" in tags and not (has_proposition_signal or "claim_bearing" in tags):
        return "Selected span is too local for underlined_phrase_meaning."
    return None


def fill_blank_span_quality_error(span: SpanUnit) -> str | None:
    tags = set(span.heuristic_tags)
    tokens = _span_tokens(span.text)
    token_count = len(tokens)
    content_count = _content_word_count(tokens)
    has_clause_signal = _has_clause_signal(span.text, tags)
    has_proposition_signal = _has_proposition_signal(span.text, tags)

    if not tokens:
        return "Selected span is empty and cannot support a blank."
    if "single_word" in tags:
        return "Selected span is too short and becomes a lexical deletion rather than a blank-inference target."
    if token_count < 4 or content_count < 2:
        return "Selected span is too short for a proposition-level blank target."
    if _has_incomplete_edge(tokens, span):
        return "Selected span is a surface-restoration fragment rather than a self-contained idea unit."
    if span_crosses_punctuation(span.text) and not has_clause_signal:
        return "Selected span crosses punctuation without forming a complete clause-level blank target."
    if not (has_proposition_signal or has_clause_signal):
        return "Selected span is not proposition-like enough for fill_in_the_blank."
    if "embedded_phrase" in tags and not has_proposition_signal:
        return "Selected span is too local and reads like a cloze fragment rather than a central blank target."
    return None


def fill_blank_connective_quality_error(span: SpanUnit) -> str | None:
    base_error = fill_blank_span_quality_error(span)
    if base_error is not None:
        return base_error
    lowered = normalize_text(span.text).lower()
    tags = set(span.heuristic_tags)
    if not (
        {"contextual_cue", "clause_like", "proposition_like"} & tags
        or any(token in lowered.split() for token in _PROPOSITION_CUE_WORDS)
    ):
        return "Selected span is not relation-bearing enough for a connective blank."
    if len(_span_tokens(span.text)) > 7:
        return "Selected span is too long for a connective-relation blank."
    return None


def fill_blank_summary_quality_error(span: SpanUnit) -> str | None:
    base_error = fill_blank_span_quality_error(span)
    if base_error is not None:
        return base_error
    tags = set(span.heuristic_tags)
    if "claim_bearing" not in tags and "abstract_term" not in tags:
        return "Selected span is not summary-worthy enough for a summary-completion blank."
    if span.priority_score < 5:
        return "Selected span is too weak for a summary-completion blank."
    return None


def is_short_english_lexical_choice(value: str) -> bool:
    normalized = " ".join(value.split())
    if not normalized or _LEXICAL_CHOICE_RE.fullmatch(normalized) is None:
        return False
    return 1 <= len(normalized.split()) <= 4


def is_phrase_level_lexical_choice(value: str) -> bool:
    normalized = " ".join(value.split())
    return is_short_english_lexical_choice(normalized) and len(normalized.split()) >= 2


def vocab_choice_target_cue_count(span: SpanUnit) -> int:
    tags = set(span.heuristic_tags)
    score = 0
    if {"abstract_term", "claim_bearing", "phrase_frame"} & tags:
        score += 1
    if {"contextual_cue", "antonym_invertible"} & tags:
        score += 1
    if _context_has_semantic_anchor(span.context_before) and _context_has_semantic_anchor(span.context_after):
        score += 1
    elif _context_has_semantic_anchor(span.context_before) or _context_has_semantic_anchor(span.context_after):
        score += 1
    if span.priority_score >= 6:
        score += 1
    return score


def vocab_choice_target_quality_error(
    span: SpanUnit,
    *,
    subtype_key: str = "contextual_vocab_choice_5",
) -> str | None:
    tags = set(span.heuristic_tags)
    tokens = _span_tokens(span.text)
    token_count = len(tokens)
    content_count = _content_word_count(tokens)

    if not tokens:
        return "Selected span is empty for vocab."
    if span_crosses_punctuation(span.text):
        return "Selected span crosses punctuation and is not a clean lexical slot."
    if subtype_key == "contextual_vocab_phrase_choice_5" and token_count < 2:
        return "Selected span must be a multiword phrase for contextual_vocab_phrase_choice_5."
    if not is_short_english_lexical_choice(span.text):
        return "Selected span is not a short lexical word or phrase target."
    if _TECHNICAL_LABEL_RE.search(span.text) is not None:
        return "Selected span looks like a technical label rather than a contextual vocab target."
    if _looks_proper_nounish_span(span):
        return "Selected span looks like a proper noun rather than a contextual vocab target."
    if token_count == 1:
        token = tokens[0]
        if token in _FUNCTION_WORDS or is_auxiliary_like(token):
            return "Selected span collapses into a function-word or auxiliary target."
        if token in _PROPOSITION_CUE_WORDS or (
            token in _DISCOURSE_CUE_WORDS and not ({"abstract_term", "antonym_invertible"} & tags)
        ):
            return "Selected span is a discourse or grammar-only function target rather than a lexical-fit target."
        if (
            token in _LOW_VALUE_FACTUAL_WORDS
            and span.priority_score < 6
            and not ({"abstract_term", "contextual_cue", "antonym_invertible"} & tags)
        ):
            return "Selected span is a low-value factual term for vocab."
    else:
        if content_count < 2:
            return "Selected span is too function-word heavy for vocab."
        if _has_incomplete_edge(tokens, span):
            return "Selected span is a fragmentary phrase rather than a clean lexical slot."
        if _has_clause_signal(span.text, tags) or _has_proposition_signal(span.text, tags):
            return "Selected span is clause-like rather than a short lexical phrase."
        if "embedded_phrase" in tags and not ({"abstract_term", "phrase_frame", "claim_bearing"} & tags):
            return "Selected span is too local to serve as a contextual vocab phrase target."

    if vocab_choice_target_cue_count(span) < 2:
        return "Selected span does not provide two independent contextual cues."
    if (
        not ({"abstract_term", "claim_bearing", "contextual_cue", "phrase_frame", "antonym_invertible"} & tags)
        and span.priority_score < 5
    ):
        return "Selected span is not central enough to passage interpretation for vocab."
    return None


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


def _regular_third_person_singular(base: str) -> str:
    if _ends_with_consonant_y(base):
        return f"{base[:-1]}ies"
    if base.endswith(("ch", "sh", "o", "s", "x", "z")):
        return f"{base}es"
    return f"{base}s"


def _regular_past_form(base: str) -> str:
    if base.endswith("e"):
        return f"{base}d"
    if _ends_with_consonant_y(base):
        return f"{base[:-1]}ied"
    if _should_double_final_consonant(base):
        return f"{base}{base[-1]}ed"
    return f"{base}ed"


def _regular_present_participle(base: str) -> str:
    if base.endswith("ie") and len(base) > 2:
        return f"{base[:-2]}ying"
    if base.endswith("e") and not base.endswith(("ee", "oe", "ye")):
        return f"{base[:-1]}ing"
    if _should_double_final_consonant(base):
        return f"{base}{base[-1]}ing"
    return f"{base}ing"


def _ends_with_consonant_y(base: str) -> bool:
    return len(base) >= 2 and base.endswith("y") and base[-2] not in "aeiou"


def _should_double_final_consonant(base: str) -> bool:
    if len(base) < 3 or len(base) > 4:
        return False
    if base.endswith(("w", "x", "y")):
        return False
    return (
        base[-1] not in "aeiou"
        and base[-2] in "aeiou"
        and base[-3] not in "aeiou"
    )


def _underlined_span_sort_key(span: SpanUnit) -> tuple[int, int, int, int]:
    tags = set(span.heuristic_tags)
    bonus = 0
    if _has_proposition_signal(span.text, tags):
        bonus += 3
    elif "claim_bearing" in tags:
        bonus += 2
    elif "abstract_term" in tags or "phrase_frame" in tags:
        bonus += 1
    if span_crosses_punctuation(span.text):
        bonus -= 2
    if "embedded_phrase" in tags and "claim_bearing" not in tags:
        bonus -= 1
    return (-(span.priority_score + bonus), span.char_start, span.char_end - span.char_start, span.char_end)


def _fill_blank_span_sort_key(span: SpanUnit) -> tuple[int, int, int, int]:
    tags = set(span.heuristic_tags)
    bonus = 0
    if _has_proposition_signal(span.text, tags):
        bonus += 4
    elif _has_clause_signal(span.text, tags):
        bonus += 2
    if "claim_bearing" in tags:
        bonus += 1
    if span_crosses_punctuation(span.text):
        bonus -= 2
    return (-(span.priority_score + bonus), span.char_start, span.char_end - span.char_start, span.char_end)


def _fill_blank_connective_sort_key(span: SpanUnit) -> tuple[int, int, int, int]:
    tags = set(span.heuristic_tags)
    bonus = 0
    if "contextual_cue" in tags:
        bonus += 4
    if _has_proposition_signal(span.text, tags):
        bonus += 2
    token_penalty = max(0, len(_span_tokens(span.text)) - 5)
    return (-(span.priority_score + bonus), token_penalty, span.char_start, span.char_end)


def _fill_blank_summary_sort_key(span: SpanUnit) -> tuple[int, int, int, int]:
    tags = set(span.heuristic_tags)
    bonus = 0
    if "claim_bearing" in tags:
        bonus += 4
    if "abstract_term" in tags:
        bonus += 2
    sentence_bias = -(span.sentence_index or 0)
    return (-(span.priority_score + bonus), sentence_bias, span.char_start, span.char_end)


def _vocab_choice_sort_key(span: SpanUnit) -> tuple[int, int, int, int, int]:
    tags = set(span.heuristic_tags)
    token_count = len(_span_tokens(span.text))
    bonus = vocab_choice_target_cue_count(span)
    if {"abstract_term", "claim_bearing", "phrase_frame"} & tags:
        bonus += 2
    if {"contextual_cue", "antonym_invertible"} & tags:
        bonus += 1
    if token_count in {2, 3}:
        bonus += 1
    return (-(span.priority_score + bonus), abs(token_count - 2), span.char_start, span.char_end - span.char_start, span.char_end)


def _span_tokens(text: str) -> list[str]:
    return [normalize_english_word(match.group(0)) for match in _TOKEN_RE.finditer(text)]


def _content_word_count(tokens: list[str]) -> int:
    return sum(1 for token in tokens if token not in _FUNCTION_WORDS)


def _has_clause_signal(text: str, tags: set[str]) -> bool:
    tokens = _span_tokens(text)
    if "claim_bearing" in tags:
        return True
    if any(token in _PROPOSITION_CUE_WORDS for token in tokens):
        return True
    for token in tokens:
        if token in _FINITE_VERB_CUES:
            return True
        if len(token) > 4 and token.endswith("ed"):
            return True
        if len(token) > 4 and token.endswith("ing"):
            return True
        if len(token) > 4 and token.endswith("s") and token not in _FUNCTION_WORDS:
            return True
    return False


def _has_proposition_signal(text: str, tags: set[str]) -> bool:
    tokens = _span_tokens(text)
    if {"claim_bearing", "abstract_term"} <= tags:
        return True
    if "claim_bearing" in tags and any(token in _EVALUATIVE_CUE_WORDS for token in tokens):
        return True
    if _has_clause_signal(text, tags) and ("contextual_cue" in tags or "abstract_term" in tags):
        return True
    return False


def _has_incomplete_edge(tokens: list[str], span: SpanUnit) -> bool:
    if not tokens:
        return True
    if tokens[0] in _INCOMPLETE_EDGE_WORDS or tokens[-1] in _INCOMPLETE_EDGE_WORDS:
        return True
    next_token = _neighbor_first_token(span.context_after)
    if next_token in {"a", "an", "his", "her", "its", "my", "our", "that", "the", "their", "these", "this", "those", "your"}:
        if tokens[-1].endswith("ing") or tokens[-1].endswith("ed") or tokens[-1].endswith("er"):
            return True
        if len(tokens) >= 2 and tokens[-2] in {"to", "can", "could", "may", "might", "must", "should", "will", "would"}:
            return True
    if next_token and len(tokens) >= 2 and tokens[-2] in {"a", "an", "his", "her", "its", "my", "our", "that", "the", "their", "these", "this", "those", "your"}:
        return True
    return False


def _neighbor_first_token(text: str | None) -> str:
    if not text:
        return ""
    match = _TOKEN_RE.search(text)
    if match is None:
        return ""
    return normalize_english_word(match.group(0))


def _context_has_semantic_anchor(text: str | None) -> bool:
    if not text:
        return False
    tokens = _span_tokens(text)
    content_tokens = [token for token in tokens if token not in _FUNCTION_WORDS]
    if len(content_tokens) >= 2:
        return True
    return any(token in _DISCOURSE_CUE_WORDS for token in tokens)


def _looks_proper_nounish_span(span: SpanUnit) -> bool:
    text = span.text.strip()
    if not text:
        return False
    if _INNER_PROPER_NOUN_RE.search(text) is not None:
        return True
    tokens = text.split()
    if len(tokens) >= 2 and all(token[:1].isupper() for token in tokens if token):
        return True
    if len(tokens) == 1 and tokens[0][:1].isupper():
        context_before = span.context_before or ""
        if context_before and not re.search(r"[.!?]\s*$", context_before):
            return True
    return False


def malformed_verb_form_reason(original_word: str, corrupted_word: str) -> str | None:
    """Return a short reason when *corrupted_word* is an obviously malformed form.

    This intentionally stays narrow and deterministic. It is only meant to catch
    pseudo-forms such as ``increaseed`` or ``reduceing`` before they fall through
    to the broader controlled-family check.
    """
    original = normalize_english_word(original_word)
    corrupted = normalize_english_word(corrupted_word)
    if not original or not corrupted:
        return None
    if corrupted in allowed_verb_form_variants(original_word):
        return None

    base = _IRREGULAR_VARIANT_INDEX.get(original, _approximate_base_form(original))
    if not base:
        return None

    if base.endswith("e") and corrupted == f"{base}ed":
        return "adds an extra 'e' before the past-tense ending"
    if base.endswith("e") and not base.endswith(("ee", "oe", "ye")) and corrupted == f"{base}ing":
        return "keeps a silent final 'e' before -ing"
    if base.endswith("ie") and corrupted == f"{base}ing":
        return "keeps final 'ie' before -ing"
    if base in _IRREGULAR_VARIANTS and corrupted == f"{base}ed":
        return "regularizes an irregular past form"
    if _ends_with_consonant_y(base) and corrupted == f"{base}ed":
        return "keeps consonant+y before the past-tense ending"
    if _ends_with_consonant_y(base) and corrupted == f"{base}s":
        return "keeps consonant+y before the third-person singular ending"
    return None


# ---------------------------------------------------------------------------
# Near-synonym denial (for vocab validator)
# ---------------------------------------------------------------------------

# Maps a source word (normalised lowercase) to the set of corrupted-word values
# that are near-synonyms and therefore do NOT constitute a valid contextual error.
# Using a set lets the validator quickly check: if corrupted ∈ denial_set[original],
# the corruption is too weak.
_NEAR_SYNONYM_DENIAL: dict[str, set[str]] = {
    # stick / adhere / cling family
    "stick":    {"adhere", "cling", "hold", "attach"},
    "adhere":   {"stick", "cling", "hold", "attach"},
    "cling":    {"stick", "adhere", "hold", "attach"},
    # help / aid / assist family
    "help":     {"aid", "assist", "support", "facilitate"},
    "aid":      {"help", "assist", "support", "facilitate"},
    "assist":   {"help", "aid", "support", "facilitate"},
    "support":  {"aid", "assist", "help", "back"},
    # begin / start / commence / initiate
    "begin":    {"start", "commence", "initiate", "launch"},
    "start":    {"begin", "commence", "initiate", "launch"},
    "commence": {"begin", "start", "initiate", "launch"},
    # end / finish / complete / conclude
    "end":      {"finish", "complete", "conclude", "finalize"},
    "finish":   {"end", "complete", "conclude", "finalize"},
    "complete": {"end", "finish", "conclude", "finalize"},
    # show / display / demonstrate / reveal
    "show":     {"display", "demonstrate", "reveal", "exhibit"},
    "display":  {"show", "demonstrate", "reveal", "exhibit"},
    "reveal":   {"show", "display", "demonstrate", "uncover"},
    # use / employ / utilise / apply
    "use":      {"employ", "utilise", "utilize", "apply"},
    "employ":   {"use", "utilise", "utilize", "apply"},
    "utilise":  {"use", "employ", "utilize", "apply"},
    "utilize":  {"use", "employ", "utilise", "apply"},
    # get / obtain / acquire / gain / receive
    "get":      {"obtain", "acquire", "gain", "receive", "attain"},
    "obtain":   {"get", "acquire", "gain", "receive", "attain"},
    "acquire":  {"get", "obtain", "gain", "receive", "attain"},
    # make / create / produce / generate / form
    "make":     {"create", "produce", "generate", "form", "build"},
    "create":   {"make", "produce", "generate", "form", "build"},
    "produce":  {"make", "create", "generate", "form", "build"},
    # keep / maintain / retain / preserve
    "keep":     {"maintain", "retain", "preserve", "sustain"},
    "maintain": {"keep", "retain", "preserve", "sustain"},
    "retain":   {"keep", "maintain", "preserve", "sustain"},
    # think / believe / consider / suppose / assume
    "think":    {"believe", "consider", "suppose", "assume"},
    "believe":  {"think", "consider", "suppose", "assume"},
    "consider": {"think", "believe", "regard", "view"},
    # look / seem / appear / feel (copula family)
    "look":     {"seem", "appear"},
    "seem":     {"look", "appear"},
    "appear":   {"look", "seem"},
    # big / large / great / significant / major
    "big":      {"large", "great", "significant", "substantial"},
    "large":    {"big", "great", "significant", "substantial"},
    "great":    {"big", "large", "significant", "substantial"},
    # small / little / minor / slight
    "small":    {"little", "minor", "slight", "limited"},
    "little":   {"small", "minor", "slight", "limited"},
    # important / significant / crucial / vital / key
    "important":   {"significant", "crucial", "vital", "key", "essential"},
    "significant": {"important", "crucial", "vital", "key", "essential"},
    "crucial":     {"important", "significant", "vital", "key", "essential"},
    "essential":   {"important", "significant", "crucial", "vital", "key"},
    # allow / permit / enable / let
    "allow":   {"permit", "enable", "let"},
    "permit":  {"allow", "enable", "let"},
    "enable":  {"allow", "permit", "let"},
    # replaceable / expendable (near enough in context)
    "expendable":   {"replaceable", "dispensable"},
    "replaceable":  {"expendable", "dispensable"},
    "dispensable":  {"expendable", "replaceable"},
}


def is_near_synonym_corruption(original_word: str, corrupted_word: str) -> bool:
    """Return True if *corrupted_word* is a near-synonym of *original_word*.

    Near-synonym corruptions are invalid vocab items because the sentence logic
    is not clearly changed by the substitution, so a test-taker cannot identify
    the error from context alone.
    """
    orig = normalize_english_word(original_word)
    corr = normalize_english_word(corrupted_word)
    denial_set = _NEAR_SYNONYM_DENIAL.get(orig, set())
    return corr in denial_set


def is_near_synonym_choice(original_text: str, candidate_text: str) -> bool:
    original_tokens = _span_tokens(original_text)
    candidate_tokens = _span_tokens(candidate_text)
    if not original_tokens or not candidate_tokens:
        return False
    if len(original_tokens) == len(candidate_tokens) == 1:
        return is_near_synonym_corruption(original_tokens[0], candidate_tokens[0])
    if len(original_tokens) != len(candidate_tokens):
        return False
    differing_pairs = [
        (original_token, candidate_token)
        for original_token, candidate_token in zip(original_tokens, candidate_tokens)
        if original_token != candidate_token
    ]
    if len(differing_pairs) != 1:
        return False
    return is_near_synonym_corruption(*differing_pairs[0])


def vocab_corruption_is_polarity_scope_like(original_text: str, replacement_text: str) -> bool:
    original_tokens = _span_tokens(original_text)
    replacement_tokens = _span_tokens(replacement_text)
    if not original_tokens or not replacement_tokens:
        return False

    original_scope = {token for token in original_tokens if token in _POLARITY_SCOPE_CUE_WORDS}
    replacement_scope = {token for token in replacement_tokens if token in _POLARITY_SCOPE_CUE_WORDS}
    if original_scope != replacement_scope:
        return True

    if len(original_tokens) == len(replacement_tokens) == 1:
        original = original_tokens[0]
        replacement = replacement_tokens[0]
        if replacement in _BROAD_OPPOSITE_HINTS.get(original, set()):
            return True
        if original in _BROAD_OPPOSITE_HINTS.get(replacement, set()):
            return True
        if {original, replacement} & {"more", "less", "most", "least", "always", "never", "all", "some"}:
            return True
    return False


def vocab_corruption_is_collocation_like(original_text: str, replacement_text: str) -> bool:
    if vocab_corruption_is_polarity_scope_like(original_text, replacement_text):
        return False
    original_tokens = _span_tokens(original_text)
    replacement_tokens = _span_tokens(replacement_text)
    if not original_tokens or not replacement_tokens:
        return False
    if len(original_tokens) != len(replacement_tokens):
        return False
    if len(original_tokens) == 1 and normalize_english_word(original_tokens[0]) == normalize_english_word(replacement_tokens[0]):
        return False
    return True


def vocab_target_is_antonym_invertible(span: SpanUnit) -> bool:
    """Return True if the span carries the ``antonym_invertible`` heuristic tag."""
    return "antonym_invertible" in span.heuristic_tags
