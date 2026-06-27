from __future__ import annotations

from dataclasses import dataclass
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
_ENGLISH_COMPLETION_RE = re.compile(r"^[A-Za-z]+(?:[-'’][A-Za-z]+)*(?: [A-Za-z]+(?:[-'’][A-Za-z]+)*){0,11}$")
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
_RELATION_CUE_WORDS = {
    "although",
    "because",
    "but",
    "despite",
    "however",
    "if",
    "instead",
    "meanwhile",
    "rather",
    "so",
    "still",
    "therefore",
    "though",
    "thus",
    "unless",
    "whereas",
    "while",
    "yet",
}
_SUMMARY_LEADIN_PHRASES = (
    "the lesson is",
    "the point is",
    "overall",
    "in short",
    "in conclusion",
    "ultimately",
)
_RELATION_CUE_PHRASES = (
    "as a consequence",
    "as a result",
    "even so",
    "for example",
    "for this reason",
    "in contrast",
    "on the other hand",
)
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
_POLARITY_SCOPE_DIRECTIONAL_WORDS = {
    "all",
    "allow",
    "always",
    "cease",
    "decrease",
    "each",
    "every",
    "expand",
    "few",
    "fewer",
    "higher",
    "increase",
    "largely",
    "less",
    "little",
    "lower",
    "many",
    "more",
    "most",
    "much",
    "narrow",
    "never",
    "no",
    "none",
    "not",
    "only",
    "partly",
    "prevent",
    "rarely",
    "reduce",
    "several",
    "some",
}
_GRAMMARISH_SINGLE_WORDS = {
    "how",
    "like",
    "more",
    "most",
    "rather",
    "so",
    "than",
    "then",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "why",
}
_WEAK_PHRASE_LEADERS = {
    "a",
    "an",
    "another",
    "any",
    "each",
    "every",
    "few",
    "fewer",
    "many",
    "more",
    "most",
    "much",
    "no",
    "none",
    "some",
    "such",
    "that",
    "the",
    "these",
    "this",
    "those",
}
_WEAK_PHRASE_HEADS = {
    "area",
    "change",
    "issue",
    "kind",
    "part",
    "sort",
    "thing",
    "type",
    "way",
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


@dataclass(frozen=True)
class VocabHardBundle:
    selected_spans: tuple[SpanUnit, ...]
    corruptible_span_ids: tuple[str, ...] = ()
    answer_span_id: str | None = None
    untouched_distractor_span_id: str | None = None
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


def fill_blank_inventory_for_subtype(
    prepared_source: PreparedSource,
    subtype_key: str = "blank_inference_proposition_5_choices",
) -> list[SpanUnit]:
    if subtype_key == "blank_connective_relation_5_choices":
        return fill_blank_connective_inventory(prepared_source)
    if subtype_key == "blank_summary_completion_5_choices":
        return fill_blank_summary_inventory(prepared_source)
    return fill_blank_target_inventory(prepared_source)


def fill_blank_design_target(
    prepared_source: PreparedSource,
    subtype_key: str = "blank_inference_proposition_5_choices",
) -> SpanUnit | None:
    inventory = fill_blank_inventory_for_subtype(prepared_source, subtype_key)
    if not inventory:
        return None
    if subtype_key == "blank_inference_proposition_5_choices":
        return inventory[0]

    proposition_inventory = fill_blank_target_inventory(prepared_source)
    proposition_target = proposition_inventory[0] if proposition_inventory else None
    return _select_distinct_fill_blank_target(
        inventory,
        proposition_target,
        prefer_sentence_change=subtype_key == "blank_summary_completion_5_choices",
    )


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
    sort_key = _vocab_choice_sort_key
    if subtype_key == "contextual_vocab_best_paraphrase_choice_5":
        sort_key = _vocab_best_paraphrase_sort_key
    elif subtype_key == "contextual_vocab_phrase_choice_5":
        sort_key = _vocab_phrase_choice_sort_key
    return sorted(
        _dedupe_by_text(
            span
            for span in prepared_source.span_units
            if vocab_choice_target_quality_error(span, subtype_key=subtype_key) is None
        ),
        key=sort_key,
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


def vocab_polarity_scope_candidate_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return [
        span
        for span in vocab_hard_candidate_inventory(prepared_source)
        if vocab_target_is_polarity_scope_eligible(span)
    ]


def vocab_collocation_candidate_inventory(prepared_source: PreparedSource) -> list[SpanUnit]:
    return [
        span
        for span in vocab_hard_candidate_inventory(prepared_source)
        if vocab_target_is_collocation_eligible(span)
    ]


def vocab_hard_bundle(prepared_source: PreparedSource, subtype_key: str) -> VocabHardBundle | None:
    inventory = vocab_hard_candidate_inventory(prepared_source)
    if len(inventory) < 5:
        return None

    if subtype_key == "contextual_vocab_error_1_among_5_polarity_scope_5":
        selected = _best_hard_bundle_with_eligible(
            inventory,
            predicate=vocab_target_is_polarity_scope_eligible,
        )
        if selected is None:
            return None
        selected_eligible_ids = tuple(span.id for span in selected if vocab_target_is_polarity_scope_eligible(span))
        return VocabHardBundle(
            selected_spans=selected,
            corruptible_span_ids=selected_eligible_ids,
        )

    if subtype_key == "contextual_vocab_error_1_among_5_collocation_5":
        selected = _best_hard_bundle_with_eligible(
            inventory,
            predicate=vocab_target_is_collocation_eligible,
        )
        if selected is None:
            return None
        selected_eligible_ids = tuple(span.id for span in selected if vocab_target_is_collocation_eligible(span))
        return VocabHardBundle(
            selected_spans=selected,
            corruptible_span_ids=selected_eligible_ids,
        )

    if subtype_key == "contextual_vocab_correct_among_3_corrupted_5":
        for start in range(len(inventory) - 4):
            candidate = inventory[start : start + 5]
            bundle = _build_correct_among_3_bundle(candidate)
            if bundle is not None:
                return bundle
        return None

    if subtype_key == "contextual_vocab_correct_among_4_corrupted_5":
        bundle = _best_correct_among_4_bundle(inventory)
        if bundle is None:
            return None
        return bundle

    if subtype_key == "contextual_vocab_error_1_among_5_5":
        selected = _best_generic_hard_bundle(inventory)
        if selected is None:
            return None
        return VocabHardBundle(
            selected_spans=selected,
            answer_span_id=_strongest_bundle_span_id(selected),
        )

    selected = _best_generic_hard_bundle(inventory)
    if selected is None:
        return None
    return VocabHardBundle(selected_spans=selected)


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
    anchor_count = _fill_blank_contextual_anchor_count(span)
    echoed_content_count = _fill_blank_echoed_content_count(span)

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
    if anchor_count == 0:
        return "Selected span is too locally recoverable and lacks surrounding evidence for a non-restoration blank."
    if echoed_content_count >= max(2, content_count - 1):
        return "Selected span is too strongly echoed by the remaining sentence context for a non-restoration blank."
    return None


def fill_blank_connective_quality_error(span: SpanUnit) -> str | None:
    tokens = _span_tokens(span.text)
    content_count = _content_word_count(tokens)
    if not tokens:
        return "Selected span is empty and cannot support a connective blank."
    if len(tokens) < 2:
        return "Selected span is too short for a connective-relation blank."
    if content_count < 1:
        return "Selected span is too function-word heavy for a connective blank."
    if span_crosses_punctuation(span.text):
        return "Selected span crosses punctuation and is not a clean connective blank."
    if not _has_explicit_relation_cue(span.text):
        return "Selected span is not explicitly relation-bearing enough for a connective blank."
    if _fill_blank_contextual_anchor_count(span) < 1:
        return "Selected span does not preserve enough surrounding support for a connective blank."
    if tokens and (tokens[-1] in _FUNCTION_WORDS or is_auxiliary_like(tokens[-1])):
        return "Selected span is truncated and does not land on a stable relation-bearing completion."
    if len(tokens) > 7:
        return "Selected span is too long for a connective-relation blank."
    return None


def fill_blank_summary_quality_error(span: SpanUnit) -> str | None:
    base_error = fill_blank_span_quality_error(span)
    if base_error is not None:
        return base_error
    tags = set(span.heuristic_tags)
    if "claim_bearing" not in tags and "abstract_term" not in tags and not _has_summary_leadin(span):
        return "Selected span is not summary-worthy enough for a summary-completion blank."
    if span.priority_score < 5:
        return "Selected span is too weak for a summary-completion blank."
    return None


def fill_blank_completion_option_quality_error(
    value: str,
    *,
    subtype_key: str = "blank_inference_proposition_5_choices",
) -> str | None:
    normalized = " ".join(value.split())
    tokens = _span_tokens(normalized)
    content_count = _content_word_count(tokens)

    if not normalized:
        return "Choice is empty."
    if _ENGLISH_COMPLETION_RE.fullmatch(normalized) is None:
        return "Choice is not readable English text."
    if span_crosses_punctuation(normalized):
        return "Choice crosses punctuation and is not a clean blank completion."
    if subtype_key == "blank_connective_relation_5_choices":
        if not _has_explicit_relation_cue(normalized):
            return "Choice does not express a clear discourse relation."
        if len(tokens) > 8:
            return "Choice is too long for a connective blank."
        return None
    if len(tokens) < 4 or content_count < 2:
        return "Choice is too short for an inference-style blank."
    if subtype_key == "blank_summary_completion_5_choices" and len(tokens) < 5:
        return "Choice is too short for a summary-completion blank."
    return None


def fill_blank_connective_allows_source_near_completion(span: SpanUnit) -> bool:
    return (
        fill_blank_connective_quality_error(span) is None
        and _has_explicit_relation_cue(span.text)
        and _fill_blank_echoed_content_count(span) < 2
    )


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
        if (
            subtype_key == "contextual_vocab_best_paraphrase_choice_5"
            and _looks_grammarish_choice_text(span.text)
            and not _has_strong_content_profile(tags)
        ):
            return "Selected span is a grammar-heavy anchor rather than a content-bearing paraphrase target."
    else:
        if content_count < 2:
            return "Selected span is too function-word heavy for vocab."
        if _has_incomplete_edge(tokens, span):
            return "Selected span is a fragmentary phrase rather than a clean lexical slot."
        if _has_clause_signal(span.text, tags) or _has_proposition_signal(span.text, tags):
            return "Selected span is clause-like rather than a short lexical phrase."
        if subtype_key == "contextual_vocab_phrase_choice_5":
            if _phrase_target_is_weak_fragment(span):
                return "Selected span is a weak phrase fragment rather than a stable phrase-frame target."
            if "phrase_frame" not in tags and "claim_bearing" not in tags and "abstract_term" not in tags:
                return "Selected span is not structured enough for contextual_vocab_phrase_choice_5."
        if "embedded_phrase" in tags and not ({"abstract_term", "phrase_frame", "claim_bearing"} & tags):
            return "Selected span is too local to serve as a contextual vocab phrase target."

    if vocab_choice_target_cue_count(span) < 2:
        return "Selected span does not provide two independent contextual cues."
    if subtype_key == "contextual_vocab_best_paraphrase_choice_5":
        if not _has_strong_content_profile(tags) and span.priority_score < 6:
            return "Selected span is not content-bearing enough for contextual_vocab_best_paraphrase_choice_5."
        if token_count > 1 and "phrase_frame" in tags and "claim_bearing" not in tags and "abstract_term" not in tags:
            return "Selected span is too frame-like and not content-bearing enough for contextual_vocab_best_paraphrase_choice_5."
    if subtype_key == "contextual_vocab_phrase_choice_5" and span.priority_score < 6:
        return "Selected span is too weak for contextual_vocab_phrase_choice_5."
    if (
        not ({"abstract_term", "claim_bearing", "contextual_cue", "phrase_frame", "antonym_invertible"} & tags)
        and span.priority_score < 5
    ):
        return "Selected span is not central enough to passage interpretation for vocab."
    return None


def vocab_choice_option_quality_error(
    value: str,
    *,
    subtype_key: str = "contextual_vocab_choice_5",
) -> str | None:
    normalized = " ".join(value.split())
    if not is_short_english_lexical_choice(normalized):
        return "Choice is not a short readable English lexical choice."
    tokens = _span_tokens(normalized)
    if not tokens:
        return "Choice is empty."
    if span_crosses_punctuation(normalized):
        return "Choice crosses punctuation and is not a clean lexical option."

    if subtype_key == "contextual_vocab_best_paraphrase_choice_5":
        if _looks_grammarish_choice_text(normalized):
            return "Choice is grammar-heavy rather than a content-bearing paraphrase candidate."
        if _content_word_count(tokens) < 1:
            return "Choice is too function-word heavy for a paraphrase candidate."

    if subtype_key == "contextual_vocab_phrase_choice_5":
        if len(tokens) < 2:
            return "Choice is not multiword enough for a phrase-level option."
        if _phrase_choice_text_is_weak(normalized):
            return "Choice is not phrase-like enough semantically for contextual_vocab_phrase_choice_5."
        if _content_word_count(tokens) < 2:
            return "Choice is too function-word heavy for a phrase-level option."

    return None


def vocab_target_is_polarity_scope_eligible(span: SpanUnit) -> bool:
    tokens = _span_tokens(span.text)
    if not tokens:
        return False
    token_set = set(tokens)
    return bool(token_set & (_POLARITY_SCOPE_CUE_WORDS | _POLARITY_SCOPE_DIRECTIONAL_WORDS))


def vocab_target_strength(span: SpanUnit) -> tuple[int, int]:
    return (vocab_choice_target_cue_count(span), span.priority_score)


def vocab_target_strength_score(span: SpanUnit) -> int:
    cue_count, priority_score = vocab_target_strength(span)
    return cue_count * 10 + priority_score


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
    if _has_summary_leadin(span):
        bonus += 4
    bonus += min(span.sentence_index or 0, 3)
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


def _vocab_best_paraphrase_sort_key(span: SpanUnit) -> tuple[int, int, int, int, int]:
    tags = set(span.heuristic_tags)
    token_count = len(_span_tokens(span.text))
    bonus = vocab_choice_target_cue_count(span)
    if {"abstract_term", "claim_bearing"} & tags:
        bonus += 4
    if "antonym_invertible" in tags:
        bonus += 2
    if token_count == 1:
        bonus += 2
    if _looks_grammarish_choice_text(span.text):
        bonus -= 6
    return (-(span.priority_score + bonus), token_count - 1, span.char_start, span.char_end - span.char_start, span.char_end)


def _vocab_phrase_choice_sort_key(span: SpanUnit) -> tuple[int, int, int, int, int]:
    tags = set(span.heuristic_tags)
    token_count = len(_span_tokens(span.text))
    bonus = vocab_choice_target_cue_count(span)
    if "phrase_frame" in tags:
        bonus += 4
    if {"claim_bearing", "abstract_term"} & tags:
        bonus += 2
    if "embedded_phrase" in tags:
        bonus -= 2
    if _phrase_target_is_weak_fragment(span):
        bonus -= 6
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


def _fill_blank_contextual_anchor_count(span: SpanUnit) -> int:
    return int(_context_has_semantic_anchor(span.context_before)) + int(_context_has_semantic_anchor(span.context_after))


def _fill_blank_echoed_content_count(span: SpanUnit) -> int:
    span_content_tokens = {token for token in _span_tokens(span.text) if token not in _FUNCTION_WORDS}
    if not span_content_tokens:
        return 0
    context_tokens = set(_span_tokens(f"{span.context_before or ''} {span.context_after or ''}"))
    return len(span_content_tokens & context_tokens)


def _has_explicit_relation_cue(text: str) -> bool:
    normalized = normalize_text(text).lower()
    return any(token in _RELATION_CUE_WORDS for token in _span_tokens(text)) or any(
        phrase in normalized for phrase in _RELATION_CUE_PHRASES
    )


def _has_summary_leadin(span: SpanUnit) -> bool:
    before = normalize_text(span.context_before or "").lower()
    text = normalize_text(span.text).lower()
    return any(phrase in before for phrase in _SUMMARY_LEADIN_PHRASES) or text.startswith("not that ")


def _select_distinct_fill_blank_target(
    inventory: list[SpanUnit],
    reference_span: SpanUnit | None,
    *,
    prefer_sentence_change: bool,
) -> SpanUnit | None:
    if not inventory:
        return None
    if reference_span is None:
        return inventory[0]
    distinct_candidates = [span for span in inventory if span.id != reference_span.id]
    if not distinct_candidates:
        return None
    if prefer_sentence_change:
        for span in distinct_candidates:
            if span.sentence_index != reference_span.sentence_index:
                return span
    return distinct_candidates[0]


def _neighbor_first_token(text: str | None) -> str:
    if not text:
        return ""
    match = _TOKEN_RE.search(text)
    if match is None:
        return ""
    return normalize_english_word(match.group(0))


def _neighbor_last_token(text: str | None) -> str:
    if not text:
        return ""
    matches = list(_TOKEN_RE.finditer(text))
    if not matches:
        return ""
    return normalize_english_word(matches[-1].group(0))


def _context_has_semantic_anchor(text: str | None) -> bool:
    if not text:
        return False
    tokens = _span_tokens(text)
    content_tokens = [token for token in tokens if token not in _FUNCTION_WORDS]
    if len(content_tokens) >= 2:
        return True
    return any(token in _DISCOURSE_CUE_WORDS for token in tokens)


def _has_strong_content_profile(tags: set[str]) -> bool:
    return bool({"abstract_term", "claim_bearing", "antonym_invertible"} & tags)


def _looks_grammarish_choice_text(text: str) -> bool:
    tokens = _span_tokens(text)
    if len(tokens) != 1:
        return False
    token = tokens[0]
    return token in _GRAMMARISH_SINGLE_WORDS or token in _DISCOURSE_CUE_WORDS or token in _PROPOSITION_CUE_WORDS


def _phrase_target_is_weak_fragment(span: SpanUnit) -> bool:
    tokens = _span_tokens(span.text)
    if len(tokens) < 2:
        return True
    first_token = tokens[0]
    if first_token in _WEAK_PHRASE_LEADERS:
        return True
    if tokens[-1] in _INCOMPLETE_EDGE_WORDS:
        return True
    if tokens[0] in _FUNCTION_WORDS and "phrase_frame" not in span.heuristic_tags:
        return True
    if tokens[-1] in _WEAK_PHRASE_HEADS and "claim_bearing" not in span.heuristic_tags:
        return True
    return False


def _phrase_choice_text_is_weak(text: str) -> bool:
    tokens = _span_tokens(text)
    if len(tokens) < 2:
        return True
    if tokens[0] in _WEAK_PHRASE_LEADERS:
        return True
    if tokens[-1] in _INCOMPLETE_EDGE_WORDS:
        return True
    if tokens[-1] in _WEAK_PHRASE_HEADS:
        return True
    return False


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


def _is_collocation_partner_token(token: str) -> bool:
    return bool(token and token not in _FUNCTION_WORDS and token not in _POLARITY_SCOPE_CUE_WORDS)


def _context_content_token_count(text: str | None) -> int:
    return sum(1 for token in _span_tokens(text or "") if token not in _FUNCTION_WORDS)


def _collocation_partner_count(span: SpanUnit) -> int:
    return sum(
        1
        for token in (_neighbor_last_token(span.context_before), _neighbor_first_token(span.context_after))
        if _is_collocation_partner_token(token)
    )


def _collocation_frame_support_score(span: SpanUnit) -> int:
    tags = set(span.heuristic_tags)
    score = _collocation_partner_count(span)
    if _context_content_token_count(span.context_before) >= 2:
        score += 1
    if _context_content_token_count(span.context_after) >= 2:
        score += 1
    if "phrase_frame" in tags:
        score += 2
    if "antonym_invertible" in tags:
        score += 1
    if "claim_bearing" in tags:
        score += 1
    return score


def vocab_corruption_is_collocation_like(span: SpanUnit, replacement_text: str) -> bool:
    if not vocab_target_is_collocation_eligible(span):
        return False
    if vocab_corruption_is_polarity_scope_like(span.text, replacement_text):
        return False
    if is_near_synonym_choice(span.text, replacement_text):
        return False
    original_tokens = _span_tokens(span.text)
    replacement_tokens = _span_tokens(replacement_text)
    if not original_tokens or not replacement_tokens:
        return False
    if len(original_tokens) != len(replacement_tokens):
        return False
    if len(original_tokens) == 1 and normalize_english_word(original_tokens[0]) == normalize_english_word(replacement_tokens[0]):
        return False
    tags = set(span.heuristic_tags)
    if "abstract_term" in tags and not ({"phrase_frame", "claim_bearing", "antonym_invertible"} & tags):
        return False
    if _collocation_frame_support_score(span) < 4 and "phrase_frame" not in tags:
        return False
    return True


def vocab_target_is_antonym_invertible(span: SpanUnit) -> bool:
    """Return True if the span carries the ``antonym_invertible`` heuristic tag."""
    return "antonym_invertible" in span.heuristic_tags


def vocab_target_is_collocation_eligible(span: SpanUnit) -> bool:
    tokens = _span_tokens(span.text)
    if len(tokens) != 1:
        return False
    if vocab_target_is_polarity_scope_eligible(span):
        return False
    if span.priority_score < 6 or vocab_choice_target_cue_count(span) < 3:
        return False
    tags = set(span.heuristic_tags)
    if not ({"phrase_frame", "antonym_invertible", "claim_bearing"} & tags):
        return False
    partner_count = _collocation_partner_count(span)
    if partner_count < 1:
        return False
    if partner_count == 1 and not ({"phrase_frame", "antonym_invertible", "claim_bearing"} & tags):
        return False
    if "abstract_term" in tags and partner_count < 2 and "phrase_frame" not in tags:
        return False
    return _collocation_frame_support_score(span) >= 3


def vocab_target_supports_soft_corruption(span: SpanUnit) -> bool:
    tags = set(span.heuristic_tags)
    cue_count = vocab_choice_target_cue_count(span)
    if cue_count < 2 or span.priority_score < 5:
        return False
    if "abstract_term" in tags and not (
        {"phrase_frame", "claim_bearing", "antonym_invertible"} & tags
        or vocab_target_is_polarity_scope_eligible(span)
        or vocab_target_is_collocation_eligible(span)
    ):
        return False
    if vocab_target_is_polarity_scope_eligible(span) or vocab_target_is_collocation_eligible(span):
        return True
    if "antonym_invertible" in tags:
        return True
    if _context_content_token_count(span.context_before) >= 1 and _context_content_token_count(span.context_after) >= 1:
        return True
    if "phrase_frame" in tags and _collocation_partner_count(span) >= 1:
        return True
    if (
        "claim_bearing" in tags
        and _context_content_token_count(span.context_before) >= 2
        and _context_content_token_count(span.context_after) >= 2
    ):
        return True
    return False


def vocab_correct_among_4_bundle_error(
    selected_spans: list[SpanUnit] | tuple[SpanUnit, ...],
    answer_span_id: str,
) -> str | None:
    if len(selected_spans) != 5:
        return "requires a five-target bundle."
    selected_by_id = {span.id: span for span in selected_spans}
    if answer_span_id not in selected_by_id:
        return "requires an answer_span_id drawn from the locked bundle."
    non_answer_spans = [span for span in selected_spans if span.id != answer_span_id]
    if len(non_answer_spans) != 4:
        return "requires exactly four non-answer targets to corrupt."
    if any(not vocab_target_supports_soft_corruption(span) for span in non_answer_spans):
        return (
            "requires four corruption-friendly non-answer targets so the wrong items do not collapse "
            "into obvious absurdities."
        )
    return None


def vocab_correct_among_4_corruption_error(span: SpanUnit, replacement_text: str) -> str | None:
    replacement_tokens = _span_tokens(replacement_text)
    if not replacement_tokens:
        return "requires readable lexical corruptions, not empty replacements."
    if len(replacement_tokens) == 1:
        replacement = replacement_tokens[0]
        if replacement in _FUNCTION_WORDS or is_auxiliary_like(replacement):
            return "requires lexical corruptions, not function-word or auxiliary swaps."
        if _looks_grammarish_choice_text(replacement_text):
            return "requires lexical corruptions, not grammar-like swaps."
        if replacement in _LOW_VALUE_FACTUAL_WORDS and (
            _has_strong_content_profile(set(span.heuristic_tags))
            or vocab_choice_target_cue_count(span) >= 3
        ):
            return (
                "requires local contextual distortions, not low-value factual swaps that make the "
                "wrong item obviously absurd."
            )
    return None


def _correct_among_3_answer_like_profile_count(span: SpanUnit) -> int:
    tags = set(span.heuristic_tags)
    cue_count = vocab_choice_target_cue_count(span)
    profile_count = 0
    if {"abstract_term", "claim_bearing"} & tags:
        profile_count += 1
    if "dense_lexis" in tags:
        profile_count += 1
    if cue_count >= 3:
        profile_count += 1
    if span.priority_score >= 8:
        profile_count += 1
    return profile_count


def vocab_correct_among_3_survivor_pair_error(
    answer_span: SpanUnit,
    untouched_distractor_span: SpanUnit,
) -> str | None:
    answer_cues, _ = vocab_target_strength(answer_span)
    distractor_cues, _ = vocab_target_strength(untouched_distractor_span)
    if answer_cues <= distractor_cues:
        return "must lock an answer_span_id with clearly stronger contextual cue support than the untouched distractor."
    if answer_span.priority_score <= untouched_distractor_span.priority_score:
        return "must lock an answer_span_id with a stronger priority profile than the untouched distractor."
    if _correct_among_3_answer_like_profile_count(untouched_distractor_span) >= 2:
        return "must not leave an extra untouched distractor that is still too central or answer-like under the passage heuristics."
    return None


def _correct_among_3_distractor_sort_key(span: SpanUnit) -> tuple[int, int, int, int]:
    cue_count, _ = vocab_target_strength(span)
    return (
        _correct_among_3_answer_like_profile_count(span),
        cue_count,
        span.priority_score,
        span.char_start,
    )


def _strongest_bundle_span_id(selected_spans: tuple[SpanUnit, ...]) -> str:
    return max(
        selected_spans,
        key=lambda span: (vocab_target_strength_score(span), -span.char_start),
    ).id


def _hard_bundle_signature(span: SpanUnit) -> tuple[str, str]:
    return (_neighbor_last_token(span.context_before), _neighbor_first_token(span.context_after))


def _hard_bundle_window_score(selected_spans: list[SpanUnit]) -> tuple[int, int, int, int, int]:
    strength_scores = [vocab_target_strength_score(span) for span in selected_spans]
    distinct_sentences = len({span.sentence_unit_id for span in selected_spans if span.sentence_unit_id is not None})
    repeated_signatures = len(selected_spans) - len({_hard_bundle_signature(span) for span in selected_spans})
    repeated_surface_heads = len(selected_spans) - len({_span_tokens(span.text)[-1] for span in selected_spans if _span_tokens(span.text)})
    char_spread = selected_spans[-1].char_start - selected_spans[0].char_start if len(selected_spans) > 1 else 0
    return (
        min(strength_scores),
        distinct_sentences,
        -repeated_signatures,
        -repeated_surface_heads,
        char_spread,
    )


def _bundle_is_stable_for_generic_hard_vocab(selected_spans: list[SpanUnit]) -> bool:
    if len(selected_spans) < 5:
        return False
    distinct_sentences = len({span.sentence_unit_id for span in selected_spans if span.sentence_unit_id is not None})
    repeated_signatures = len(selected_spans) - len({_hard_bundle_signature(span) for span in selected_spans})
    repeated_surface_heads = len(selected_spans) - len({_span_tokens(span.text)[-1] for span in selected_spans if _span_tokens(span.text)})
    return distinct_sentences >= 3 and repeated_signatures <= 1 and repeated_surface_heads <= 1


def _best_generic_hard_bundle(inventory: list[SpanUnit]) -> tuple[SpanUnit, ...] | None:
    if len(inventory) < 5:
        return None
    ranked = sorted(
        [inventory[start : start + 5] for start in range(len(inventory) - 4)],
        key=lambda spans: _hard_bundle_window_score(spans),
        reverse=True,
    )
    for bundle in ranked:
        if _bundle_is_stable_for_generic_hard_vocab(bundle):
            return tuple(bundle)
    return None


def _best_hard_bundle_with_eligible(
    inventory: list[SpanUnit],
    *,
    predicate,
) -> tuple[SpanUnit, ...] | None:
    if len(inventory) < 5:
        return None
    ranked = sorted(
        [inventory[start : start + 5] for start in range(len(inventory) - 4)],
        key=lambda spans: _hard_bundle_window_score(spans),
        reverse=True,
    )
    for bundle in ranked:
        if not _bundle_is_stable_for_generic_hard_vocab(bundle):
            continue
        if any(predicate(span) for span in bundle):
            return tuple(bundle)
    return None


def _best_correct_among_4_bundle(inventory: list[SpanUnit]) -> VocabHardBundle | None:
    if len(inventory) < 5:
        return None
    ranked = sorted(
        [inventory[start : start + 5] for start in range(len(inventory) - 4)],
        key=lambda spans: _hard_bundle_window_score(spans),
        reverse=True,
    )
    for bundle in ranked:
        if not _bundle_is_stable_for_generic_hard_vocab(bundle):
            continue
        answer_span_id = _strongest_bundle_span_id(tuple(bundle))
        if vocab_correct_among_4_bundle_error(bundle, answer_span_id) is None:
            return VocabHardBundle(
                selected_spans=tuple(bundle),
                answer_span_id=answer_span_id,
            )
    return None


def _build_correct_among_3_bundle(selected_spans: list[SpanUnit]) -> VocabHardBundle | None:
    ranked = sorted(
        selected_spans,
        key=lambda span: (vocab_target_strength_score(span), -span.char_start),
        reverse=True,
    )
    if len(ranked) < 5:
        return None
    if vocab_target_strength_score(ranked[0]) <= vocab_target_strength_score(ranked[1]) + 1:
        return None
    answer_span = ranked[0]
    weakest = min(
        (span for span in selected_spans if span.id != answer_span.id),
        key=_correct_among_3_distractor_sort_key,
    )
    pair_error = vocab_correct_among_3_survivor_pair_error(answer_span, weakest)
    if pair_error is not None:
        return None
    return VocabHardBundle(
        selected_spans=tuple(selected_spans),
        answer_span_id=answer_span.id,
        untouched_distractor_span_id=weakest.id,
    )
