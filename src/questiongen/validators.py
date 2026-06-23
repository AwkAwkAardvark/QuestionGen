from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from .parsers import content_tokens, looks_fragmentary_sentence, looks_hanging_phrase, normalize_text
from .question_types import QUESTION_TYPES, QuestionTypeSpec
from .renderers import (
    DISPLAY_PERMUTATIONS,
    MARKER_CHOICES,
    ORDERING_CHOICES,
    UNDERLINE_CLOSE,
    UNDERLINE_OPEN,
    rendered_gap_positions,
)
from .schemas import (
    GeneratedQuestion,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    PreparedSource,
    QuestionState,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
)

_INTERNAL_EXPLANATION_ID_RE = re.compile(r"[SGP]\d+")
_HANGUL_RE = re.compile(r"[가-힣]")
_MOOD_CHOICE_PAIR_RE = re.compile(r"^[A-Za-z][A-Za-z '\-/]*(?:\s*->\s*)[A-Za-z][A-Za-z '\-/]*$")
_AFFECTIVE_CUE_RE = re.compile(
    r"\b("
    r"afraid|angry|annoyed|anxious|ashamed|calm|confident|confidence|confused|content|curious|"
    r"delighted|discouraged|disappointed|distressed|eager|embarrassed|enraged|excited|"
    r"frustrated|glad|grateful|guilty|happy|hopeful|jealous|lonely|miserable|nervous|"
    r"panicked|pleased|proud|proudly|regretful|relieved|sad|satisfied|scared|shocked|surprised|"
    r"tense|uneasy|upset|worried"
    r")\b",
    re.IGNORECASE,
)
_HOLDER_CUE_RE = re.compile(
    r"\b("
    r"i|me|my|mine|we|us|our|ours|he|him|his|she|her|hers|they|them|their|theirs|"
    r"person|people|child|children|student|students|teacher|teachers|employee|employees|"
    r"manager|managers|worker|workers|resident|residents|boy|girl|farmer|narrator|writer|"
    r"monkey|monkeys"
    r")\b",
    re.IGNORECASE,
)
_INTERNAL_EXPLANATION_TERM_PATTERNS = (
    "selected_gap_ids",
    "correct_gap_id",
    "target_unit_ids",
    "continuation_blocks",
    "intro_unit_ids",
    "choice_pairs",
    "correct_choice",
    "initial_emotion",
    "final_emotion",
    "target_holder",
    "selected_span_id",
    "selected_span_text",
    "paraphrase_choices_ko",
    "surface_meaning",
    "contextual_meaning",
    "supporting_evidence",
    "렌더",
    "renderer",
    "schema",
    "스키마",
    "gap id",
    "sentence id",
)
_TRANSITION_STARTERS = {
    "accordingly",
    "as",
    "because",
    "but",
    "consequently",
    "for",
    "however",
    "instead",
    "meanwhile",
    "moreover",
    "so",
    "therefore",
    "thus",
    "while",
}
_REFERENTIAL_CUES = {
    "another",
    "he",
    "it",
    "its",
    "she",
    "such",
    "that",
    "theirs",
    "them",
    "these",
    "they",
    "this",
    "those",
}
_PARALLEL_BLOCK_STARTERS = {
    "for example",
    "for instance",
    "in",
    "another",
    "similarly",
}


def input_check(
    state: QuestionState,
    question_types: Mapping[str, QuestionTypeSpec] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    registry = question_types or QUESTION_TYPES
    if state["QuestionTypeKey"] not in registry:
        errors.append(f"Unknown QuestionTypeKey: {state['QuestionTypeKey']}")
    if not isinstance(state["OriginalQuestionNumber"], str) or not state["OriginalQuestionNumber"].strip():
        errors.append("OriginalQuestionNumber must be a non-empty string.")
    if not isinstance(state["BatchRowId"], int) or state["BatchRowId"] < 0:
        errors.append("BatchRowId must be a non-negative integer.")
    if not isinstance(state["source_paragraph"], str) or not state["source_paragraph"].strip():
        errors.append("source_paragraph must be a non-empty string.")

    if errors:
        return {
            "status": "input_error",
            "errors": errors,
        }
    return {
        "status": "input_passed",
        "errors": [],
    }


def source_check(state: QuestionState, type_spec: QuestionTypeSpec) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    if prepared_source is None:
        return {
            "status": "source_error",
            "errors": ["PreparedSource is missing."],
        }

    if type_spec.min_source_units is not None and len(prepared_source.sentence_units) < type_spec.min_source_units:
        return {
            "status": "qtype_incompatibility_error",
            "errors": [
                f"PreparedSource requires at least {type_spec.min_source_units} sentence units, "
                f"but found {len(prepared_source.sentence_units)}."
            ],
        }

    errors = validate_prepared_source(prepared_source, min_source_units=None)
    if errors:
        return {
            "status": "source_error",
            "errors": errors,
        }

    compatibility_errors = validate_question_type_compatibility(state["source_paragraph"], prepared_source, type_spec)
    if compatibility_errors:
        return {
            "status": "qtype_incompatibility_error",
            "errors": compatibility_errors,
        }
    return {
        "status": "source_passed",
        "errors": [],
    }


def plan_check(state: QuestionState, type_spec: QuestionTypeSpec) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]

    if prepared_source is None:
        return {
            "status": "planning_error",
            "errors": ["PreparedSource is required before deterministic plan checks."],
        }

    errors = validate_plan_against_prepared_source(prepared_source, plan, type_spec)
    if errors:
        return {
            "status": "planning_error",
            "errors": errors,
        }
    return {
        "status": "planned",
        "errors": [],
    }


def validate_prepared_source(
    prepared_source: PreparedSource,
    *,
    min_source_units: int | None = None,
) -> list[str]:
    errors: list[str] = []
    source_text = prepared_source.source_text
    sentence_units = prepared_source.sentence_units
    gap_units = prepared_source.gap_units
    span_units = prepared_source.span_units

    if not source_text or not source_text.strip():
        errors.append("PreparedSource.source_text is required.")

    if min_source_units is not None and len(sentence_units) < min_source_units:
        errors.append(
            f"PreparedSource requires at least {min_source_units} sentence units, "
            f"but found {len(sentence_units)}."
        )

    for index, unit in enumerate(sentence_units):
        expected_id = f"S{index}"
        if unit.id != expected_id:
            errors.append(f"Sentence unit at index {index} should have id {expected_id}, got {unit.id}.")
        if unit.kind != "sentence":
            errors.append(f"Sentence unit {unit.id} must have kind 'sentence'.")
        if unit.index != index:
            errors.append(f"Sentence unit {unit.id} should have index {index}, got {unit.index}.")
        previous_text = sentence_units[index - 1].text if index > 0 else None
        if looks_fragmentary_sentence(unit.text, previous_text=previous_text):
            errors.append(
                f"Sentence unit {unit.id} appears fragmentary after deterministic parsing: {unit.text}"
            )

    expected_gap_count = len(sentence_units) + 1
    if len(gap_units) != expected_gap_count:
        errors.append(f"Expected {expected_gap_count} gap units, found {len(gap_units)}.")

    for index, gap in enumerate(gap_units):
        expected_id = f"G{index}"
        expected_before = f"S{index - 1}" if index > 0 else None
        expected_after = f"S{index}" if index < len(sentence_units) else None

        if gap.id != expected_id:
            errors.append(f"Gap unit at index {index} should have id {expected_id}, got {gap.id}.")
        if gap.kind != "gap":
            errors.append(f"Gap unit {gap.id} must have kind 'gap'.")
        if gap.index != index:
            errors.append(f"Gap unit {gap.id} should have index {index}, got {gap.index}.")
        if gap.before_unit_id != expected_before:
            errors.append(
                f"Gap unit {gap.id} should have before_unit_id {expected_before}, got {gap.before_unit_id}."
            )
        if gap.after_unit_id != expected_after:
            errors.append(
                f"Gap unit {gap.id} should have after_unit_id {expected_after}, got {gap.after_unit_id}."
            )

    sentence_id_set = {unit.id for unit in sentence_units}
    for index, span in enumerate(span_units):
        expected_id = f"P{index}"
        if span.id != expected_id:
            errors.append(f"Span unit at index {index} should have id {expected_id}, got {span.id}.")
        if span.kind != "span":
            errors.append(f"Span unit {span.id} must have kind 'span'.")
        if span.char_start < 0 or span.char_end > len(source_text) or span.char_end <= span.char_start:
            errors.append(f"Span unit {span.id} has invalid character bounds {span.char_start}:{span.char_end}.")
            continue
        if source_text[span.char_start : span.char_end] != span.text:
            errors.append(f"Span unit {span.id} text does not match PreparedSource.source_text at its character range.")
        if span.normalized_text != normalize_text(span.text):
            errors.append(f"Span unit {span.id} normalized_text does not match normalized span text.")
        if span.sentence_unit_id is not None and span.sentence_unit_id not in sentence_id_set:
            errors.append(f"Span unit {span.id} references unknown sentence_unit_id {span.sentence_unit_id}.")
        if span.sentence_index is not None and (
            span.sentence_index < 0 or span.sentence_index >= len(sentence_units)
        ):
            errors.append(f"Span unit {span.id} has out-of-range sentence_index {span.sentence_index}.")

    return errors


def validate_teacher_facing_explanation(
    explanation: str | None,
    *,
    question_type_key: str,
) -> list[str]:
    errors: list[str] = []
    if explanation is None or not explanation.strip():
        errors.append("explanation is required.")
        return errors

    if not any("\uac00" <= char <= "\ud7a3" for char in explanation):
        errors.append("explanation must contain Korean text.")

    if _INTERNAL_EXPLANATION_ID_RE.search(explanation):
        errors.append(
            f"{question_type_key} explanation must not mention internal sentence or gap IDs or internal span IDs like S0, G3, or P2."
        )

    lowered = explanation.lower()
    if any(pattern in lowered for pattern in _INTERNAL_EXPLANATION_TERM_PATTERNS):
        errors.append(
            f"{question_type_key} explanation must not mention schema fields or renderer mechanics."
        )

    return errors


def validate_plan_against_prepared_source(
    prepared_source: PreparedSource,
    plan: object,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    if type_spec.validator_key == "sentence_insertion":
        return _validate_sentence_insertion_plan(prepared_source, plan)
    if type_spec.validator_key == "paragraph_ordering":
        return _validate_paragraph_ordering_plan(prepared_source, plan)
    if type_spec.validator_key == "mood_atmosphere":
        return _validate_mood_atmosphere_plan(prepared_source, plan)
    if type_spec.validator_key == "underlined_phrase_meaning":
        return _validate_underlined_phrase_meaning_plan(prepared_source, plan)
    return [f"No deterministic plan validator is registered for {type_spec.validator_key}."]


def validate_question_type_compatibility(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    if type_spec.validator_key == "sentence_insertion":
        return _validate_sentence_insertion_compatibility(prepared_source)
    if type_spec.validator_key == "paragraph_ordering":
        return _validate_paragraph_ordering_compatibility(prepared_source)
    if type_spec.validator_key == "mood_atmosphere":
        return _validate_mood_atmosphere_compatibility(source_paragraph, prepared_source)
    if type_spec.validator_key == "underlined_phrase_meaning":
        return _validate_underlined_phrase_meaning_compatibility(prepared_source)
    return []


def _validate_sentence_insertion_plan(prepared_source: PreparedSource, plan: object) -> list[str]:
    if not isinstance(plan, SentenceInsertionPlan):
        return ["SentenceInsertionPlan is missing for deterministic plan checks."]

    errors: list[str] = []
    sentence_units = prepared_source.sentence_units
    sentence_ids = [unit.id for unit in sentence_units]
    sentence_map = {unit.id: unit for unit in sentence_units}
    gap_ids = {gap.id for gap in prepared_source.gap_units}
    target_id = plan.target_unit_ids[0] if plan.target_unit_ids else None

    if target_id not in sentence_ids:
        errors.append(f"Unknown target sentence ID: {target_id}")
        return errors

    unknown_gap_ids = [gap_id for gap_id in plan.selected_gap_ids if gap_id not in gap_ids]
    if unknown_gap_ids:
        errors.append(f"Unknown gap IDs: {', '.join(unknown_gap_ids)}")
        return errors

    rendered_positions = rendered_gap_positions(prepared_source, target_id)
    unique_positions = {rendered_positions[gap_id] for gap_id in plan.selected_gap_ids}
    if len(unique_positions) != len(plan.selected_gap_ids):
        errors.append(
            "SentenceInsertionPlan selected_gap_ids collapse into duplicate rendered positions "
            "after removing the target sentence."
        )

    target_unit = sentence_map[target_id]
    target_index = target_unit.index
    if looks_fragmentary_sentence(
        target_unit.text,
        previous_text=sentence_units[target_index - 1].text if target_index > 0 else None,
    ):
        errors.append("SentenceInsertionPlan target sentence is fragmentary and should be rejected.")

    if _should_apply_live_quality_gates(sentence_units):
        if target_index == 0 or target_index == len(sentence_units) - 1:
            errors.append(
                "SentenceInsertionPlan target sentence must have both left and right source context for a stable item."
            )
            return errors

        before_text = sentence_units[target_index - 1].text
        after_text = sentence_units[target_index + 1].text
        left_score = _adjacency_score(before_text, target_unit.text)
        right_score = _adjacency_score(target_unit.text, after_text)
        if left_score < 2 or right_score < 2:
            errors.append(
                "SentenceInsertionPlan target sentence needs distinct left-context and right-context evidence, not one-sided linkage."
            )
        if _looks_connector_only_sentence(target_unit.text) and left_score <= 2 and right_score <= 2:
            errors.append(
                "SentenceInsertionPlan target sentence relies too heavily on surface connector cues without stronger textual anchors."
            )

    return errors


def _validate_paragraph_ordering_plan(prepared_source: PreparedSource, plan: object) -> list[str]:
    if not isinstance(plan, ParagraphOrderingPlan):
        return ["ParagraphOrderingPlan is missing for deterministic plan checks."]

    sentence_ids = [unit.id for unit in prepared_source.sentence_units]
    flattened = plan.intro_unit_ids + [unit_id for block in plan.continuation_blocks for unit_id in block]
    if flattened != sentence_ids:
        return ["ParagraphOrderingPlan must cover all sentence IDs exactly once in source order."]
    if not _should_apply_live_quality_gates(prepared_source.sentence_units):
        return []

    sentence_map = {unit.id: unit.text for unit in prepared_source.sentence_units}
    intro_text = " ".join(sentence_map[unit_id] for unit_id in plan.intro_unit_ids)
    logical_blocks = [
        " ".join(sentence_map[unit_id] for unit_id in block)
        for block in plan.continuation_blocks
    ]
    ordered_segments = [intro_text, *logical_blocks]
    edge_scores = [
        _adjacency_score(ordered_segments[index], ordered_segments[index + 1])
        for index in range(len(ordered_segments) - 1)
    ]
    if any(score < 2 for score in edge_scores):
        return ["ParagraphOrderingPlan adjacency is too weakly forced to support a stable ordering item."]

    if _looks_like_parallel_blocks(logical_blocks) and max(edge_scores, default=0) <= 3:
        return ["ParagraphOrderingPlan continuation blocks behave like parallel examples rather than forced adjacency."]
    return []


def _validate_mood_atmosphere_plan(prepared_source: PreparedSource, plan: object) -> list[str]:
    if not isinstance(plan, MoodAtmospherePlan):
        return ["MoodAtmospherePlan is missing for deterministic plan checks."]

    errors: list[str] = []
    source_text = normalize_text(" ".join(unit.text for unit in prepared_source.sentence_units))
    for field_name in ("initial_evidence", "final_evidence"):
        evidence = getattr(plan, field_name)
        if normalize_text(evidence) not in source_text:
            errors.append(f"MoodAtmospherePlan {field_name} must be copied from the source passage.")
    if plan.shift_trigger and normalize_text(plan.shift_trigger) not in source_text:
        errors.append("MoodAtmospherePlan shift_trigger must be copied from the source passage.")
    return errors


def _validate_mood_atmosphere_compatibility(
    source_paragraph: str,
    prepared_source: PreparedSource,
) -> list[str]:
    source_text = normalize_text(source_paragraph)
    affective_cues = {match.group(0).lower() for match in _AFFECTIVE_CUE_RE.finditer(source_text)}
    if len(affective_cues) < 2:
        return ["Passage does not contain enough clear affective cues for an emotion-shift item."]

    if _HOLDER_CUE_RE.search(source_text) is None:
        return ["Passage does not provide a clear feeling-holder cue for an emotion-shift item."]

    if len(prepared_source.sentence_units) < 2:
        return ["Passage does not contain enough sentence-level development for an emotion-shift item."]

    return []


def _validate_sentence_insertion_compatibility(prepared_source: PreparedSource) -> list[str]:
    sentence_units = prepared_source.sentence_units
    if not _should_apply_live_quality_gates(sentence_units):
        return []

    viable_targets = 0
    for target_unit in sentence_units[1:-1]:
        rendered_positions = rendered_gap_positions(prepared_source, target_unit.id)
        if len(set(rendered_positions.values())) < 5:
            continue

        before_text = sentence_units[target_unit.index - 1].text
        after_text = sentence_units[target_unit.index + 1].text
        left_score = _adjacency_score(before_text, target_unit.text)
        right_score = _adjacency_score(target_unit.text, after_text)
        if left_score < 2 or right_score < 2:
            continue
        if _looks_connector_only_sentence(target_unit.text) and left_score <= 2 and right_score <= 2:
            continue
        viable_targets += 1

    if viable_targets == 0:
        return [
            "Passage does not contain a stable sentence-insertion target with five distinct rendered positions and two-sided context evidence."
        ]
    return []


def _validate_paragraph_ordering_compatibility(prepared_source: PreparedSource) -> list[str]:
    sentence_units = prepared_source.sentence_units
    if not _should_apply_live_quality_gates(sentence_units):
        return []

    sentence_texts = [unit.text for unit in sentence_units]
    sentence_count = len(sentence_texts)
    for first_cut in range(1, sentence_count - 2):
        for second_cut in range(first_cut + 1, sentence_count - 1):
            for third_cut in range(second_cut + 1, sentence_count):
                intro_text = " ".join(sentence_texts[:first_cut])
                block_a = " ".join(sentence_texts[first_cut:second_cut])
                block_b = " ".join(sentence_texts[second_cut:third_cut])
                block_c = " ".join(sentence_texts[third_cut:])
                ordered_segments = [intro_text, block_a, block_b, block_c]
                edge_scores = [
                    _adjacency_score(ordered_segments[index], ordered_segments[index + 1])
                    for index in range(len(ordered_segments) - 1)
                ]
                if any(score < 2 for score in edge_scores):
                    continue
                if _looks_like_parallel_blocks([block_a, block_b, block_c]) and max(edge_scores, default=0) <= 3:
                    continue
                return []

    return ["Passage does not contain strongly forced adjacency boundaries for a stable paragraph_ordering item."]


def _validate_underlined_phrase_meaning_plan(prepared_source: PreparedSource, plan: object) -> list[str]:
    if not isinstance(plan, UnderlinedPhraseMeaningPlan):
        return ["UnderlinedPhraseMeaningPlan is missing for deterministic plan checks."]

    errors: list[str] = []
    span_map = {span.id: span for span in prepared_source.span_units}
    selected_span = span_map.get(plan.selected_span_id)
    if selected_span is None:
        return [f"Unknown selected span ID: {plan.selected_span_id}"]

    if plan.selected_span_text != selected_span.text:
        errors.append("UnderlinedPhraseMeaningPlan selected_span_text must exactly match the selected span text.")

    normalized_choices = [_normalize_korean_choice(choice) for choice in plan.paraphrase_choices_ko]
    if len(normalized_choices) != 5:
        errors.append("UnderlinedPhraseMeaningPlan must contain exactly five Korean choices.")
    if len(set(normalized_choices)) != len(normalized_choices):
        errors.append("UnderlinedPhraseMeaningPlan Korean choices must be unique.")
    if any(_HANGUL_RE.search(choice) is None for choice in normalized_choices):
        errors.append("UnderlinedPhraseMeaningPlan Korean choices must contain Hangul text.")
    if _normalize_korean_choice(plan.correct_choice) not in normalized_choices:
        errors.append("UnderlinedPhraseMeaningPlan correct_choice must be included in paraphrase_choices_ko.")

    if prepared_source.source_text[selected_span.char_start : selected_span.char_end] != plan.selected_span_text:
        errors.append("UnderlinedPhraseMeaningPlan selected span text does not match PreparedSource.source_text.")

    if normalize_text(plan.supporting_evidence) not in normalize_text(prepared_source.source_text):
        errors.append("UnderlinedPhraseMeaningPlan supporting_evidence must be copied from the source passage.")

    if _should_apply_live_quality_gates(prepared_source.sentence_units):
        span_quality_error = _underlined_span_quality_error(selected_span.text, selected_span.heuristic_tags, selected_span.priority_score)
        if span_quality_error is not None:
            errors.append(span_quality_error)

    return errors


def _validate_underlined_phrase_meaning_compatibility(prepared_source: PreparedSource) -> list[str]:
    span_units = prepared_source.span_units
    if not span_units:
        return ["Passage has no suitable contextual phrase candidate for underlined_phrase_meaning."]

    viable_spans = [
        span
        for span in span_units
        if _underlined_span_quality_error(span.text, span.heuristic_tags, span.priority_score) is None
    ]
    if not viable_spans:
        return ["Available phrase candidates are too literal, fragmentary, or weakly central for underlined_phrase_meaning."]

    top_score = max(span.priority_score for span in viable_spans)
    if top_score < 5:
        return ["Available phrase candidates are too literal for an underlined_phrase_meaning item."]

    claim_bearing_spans = [
        span
        for span in viable_spans
        if {"abstract_term", "claim_bearing", "contextual_cue", "phrase_frame"} & set(span.heuristic_tags)
    ]
    if not claim_bearing_spans:
        return ["Available phrase candidates are not central enough to the passage claim for underlined_phrase_meaning."]

    equally_ranked = [span for span in claim_bearing_spans if span.priority_score == top_score]
    if top_score <= 6 and len(equally_ranked) >= 6:
        return ["Passage contains too many equally defensible contextual phrase targets for a stable Korean paraphrase item."]

    return []


def validate_generated_question(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    validator = GENERATED_QUESTION_VALIDATORS[type_spec.validator_key]
    errors = validator(state, type_spec)
    if errors:
        return {
            "status": "validation_error",
            "errors": errors,
        }
    return {
        "status": "validation_passed",
        "errors": [],
    }


def _validate_sentence_insertion_state(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]
    generated = state["generated"]

    if prepared_source is None:
        return ["PreparedSource is missing for validation."]
    if not isinstance(plan, SentenceInsertionPlan):
        return ["SentenceInsertionPlan is missing for validation."]
    if not isinstance(generated, GeneratedQuestion):
        return ["GeneratedQuestion is missing for validation."]
    if generated.OriginalQuestionNumber != state["OriginalQuestionNumber"]:
        return ["GeneratedQuestion OriginalQuestionNumber must match the state."]
    if generated.BatchRowId != state["BatchRowId"]:
        return ["GeneratedQuestion BatchRowId must match the state."]

    return validate_sentence_insertion_output(
        prepared_source=prepared_source,
        plan=plan,
        generated=generated,
        type_spec=type_spec,
    )


def validate_sentence_insertion_output(
    *,
    prepared_source: PreparedSource,
    plan: SentenceInsertionPlan,
    generated: GeneratedQuestion,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    errors: list[str] = []
    sentence_map = {unit.id: unit for unit in prepared_source.sentence_units}
    gap_ids = {gap.id for gap in prepared_source.gap_units}

    target_id = plan.target_unit_ids[0] if plan.target_unit_ids else None
    if target_id not in sentence_map:
        errors.append(f"Unknown target sentence ID: {target_id}")
        return errors

    if len(plan.selected_gap_ids) != len(set(plan.selected_gap_ids)):
        errors.append("selected_gap_ids contain duplicates.")

    unknown_gap_ids = [gap_id for gap_id in plan.selected_gap_ids if gap_id not in gap_ids]
    if unknown_gap_ids:
        errors.append(f"Unknown gap IDs: {', '.join(unknown_gap_ids)}")

    if plan.correct_gap_id not in plan.selected_gap_ids:
        errors.append("correct_gap_id must be included in selected_gap_ids.")

    if not unknown_gap_ids:
        rendered_positions = rendered_gap_positions(prepared_source, target_id)
        unique_positions = {rendered_positions[gap_id] for gap_id in plan.selected_gap_ids}
        if len(unique_positions) != len(plan.selected_gap_ids):
            errors.append(
                "selected_gap_ids collapse into duplicate rendered positions after removing the target sentence."
            )

    expected_choices = MARKER_CHOICES[: type_spec.choice_count]
    if generated.QuestionType != type_spec.label_ko:
        errors.append(f"QuestionType should be '{type_spec.label_ko}', got '{generated.QuestionType}'.")
    if generated.question_stem != type_spec.question_stem:
        errors.append("question_stem does not match the question type metadata.")
    if generated.choices != expected_choices:
        errors.append(f"choices must be exactly {expected_choices}.")

    target_sentence = sentence_map[target_id].text
    if generated.given_sentence != target_sentence:
        errors.append("given_sentence must exactly match the selected target sentence.")
    if looks_fragmentary_sentence(target_sentence):
        errors.append("given_sentence must not be a fragmentary sentence unit.")

    marker_counts = {marker: generated.student_paragraph.count(marker) for marker in expected_choices}
    for marker, count in marker_counts.items():
        if count != 1:
            errors.append(f"Marker {marker} appears {count} times, expected exactly once.")

    expected_answer = expected_choices[plan.selected_gap_ids.index(plan.correct_gap_id)]
    if generated.answer != expected_answer:
        errors.append(
            f"answer should map to correct_gap_id {plan.correct_gap_id} as {expected_answer}, got {generated.answer}."
        )

    normalized_student = normalize_text(generated.student_paragraph)
    if normalize_text(target_sentence) in normalized_student:
        errors.append("Target sentence still appears in student_paragraph.")

    preserved_sentences = [
        unit.text
        for unit in prepared_source.sentence_units
        if unit.id != target_id
    ]
    last_pos = -1
    for sentence in preserved_sentences:
        normalized_sentence = normalize_text(sentence)
        occurrence_count = normalized_student.count(normalized_sentence)
        if occurrence_count != 1:
            errors.append(f"Preserved sentence must appear exactly once: {sentence}")
            continue
        position = normalized_student.find(normalized_sentence)
        if position < last_pos:
            errors.append("Preserved sentences are not in original order.")
            break
        last_pos = position

    errors.extend(
        validate_teacher_facing_explanation(
            generated.explanation,
            question_type_key="sentence_insertion",
        )
    )

    return errors


def _validate_paragraph_ordering_state(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]
    generated = state["generated"]

    if prepared_source is None:
        return ["PreparedSource is missing for validation."]
    if not isinstance(plan, ParagraphOrderingPlan):
        return ["ParagraphOrderingPlan is missing for validation."]
    if not isinstance(generated, GeneratedQuestion):
        return ["GeneratedQuestion is missing for validation."]
    if generated.OriginalQuestionNumber != state["OriginalQuestionNumber"]:
        return ["GeneratedQuestion OriginalQuestionNumber must match the state."]
    if generated.BatchRowId != state["BatchRowId"]:
        return ["GeneratedQuestion BatchRowId must match the state."]

    return validate_paragraph_ordering_output(
        prepared_source=prepared_source,
        plan=plan,
        generated=generated,
        type_spec=type_spec,
    )


def _validate_mood_atmosphere_state(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]
    generated = state["generated"]

    if prepared_source is None:
        return ["PreparedSource is missing for validation."]
    if not isinstance(plan, MoodAtmospherePlan):
        return ["MoodAtmospherePlan is missing for validation."]
    if not isinstance(generated, GeneratedQuestion):
        return ["GeneratedQuestion is missing for validation."]
    if generated.OriginalQuestionNumber != state["OriginalQuestionNumber"]:
        return ["GeneratedQuestion OriginalQuestionNumber must match the state."]
    if generated.BatchRowId != state["BatchRowId"]:
        return ["GeneratedQuestion BatchRowId must match the state."]

    return validate_mood_atmosphere_output(
        prepared_source=prepared_source,
        plan=plan,
        generated=generated,
        type_spec=type_spec,
    )


def _validate_underlined_phrase_meaning_state(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]
    generated = state["generated"]

    if prepared_source is None:
        return ["PreparedSource is missing for validation."]
    if not isinstance(plan, UnderlinedPhraseMeaningPlan):
        return ["UnderlinedPhraseMeaningPlan is missing for validation."]
    if not isinstance(generated, GeneratedQuestion):
        return ["GeneratedQuestion is missing for validation."]
    if generated.OriginalQuestionNumber != state["OriginalQuestionNumber"]:
        return ["GeneratedQuestion OriginalQuestionNumber must match the state."]
    if generated.BatchRowId != state["BatchRowId"]:
        return ["GeneratedQuestion BatchRowId must match the state."]

    return validate_underlined_phrase_meaning_output(
        prepared_source=prepared_source,
        plan=plan,
        generated=generated,
        type_spec=type_spec,
    )


def validate_paragraph_ordering_output(
    *,
    prepared_source: PreparedSource,
    plan: ParagraphOrderingPlan,
    generated: GeneratedQuestion,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    errors: list[str] = []
    sentence_map = {unit.id: unit for unit in prepared_source.sentence_units}
    sentence_ids = [unit.id for unit in prepared_source.sentence_units]
    flattened = plan.intro_unit_ids + [unit_id for block in plan.continuation_blocks for unit_id in block]
    if flattened != sentence_ids:
        errors.append("ParagraphOrderingPlan must cover all sentence IDs exactly once in source order.")
        return errors

    if generated.QuestionType != type_spec.label_ko:
        errors.append(f"QuestionType should be '{type_spec.label_ko}', got '{generated.QuestionType}'.")
    if generated.question_stem != type_spec.question_stem:
        errors.append("question_stem does not match the question type metadata.")

    if generated.given_sentence is not None:
        errors.append("given_sentence must be None for paragraph_ordering.")

    if generated.choices is None or len(generated.choices) != type_spec.choice_count:
        errors.append(f"choices must contain exactly {type_spec.choice_count} items.")
    else:
        if len(set(generated.choices)) != len(generated.choices):
            errors.append("choices must be unique.")
        if not generated.answer or generated.answer not in MARKER_CHOICES[: len(generated.choices)]:
            errors.append("answer must be one of the rendered marker choices.")

        permutation = DISPLAY_PERMUTATIONS[generated.BatchRowId % len(DISPLAY_PERMUTATIONS)]
        label_by_logical_index = {
            logical_index: label
            for label, logical_index in zip(("A", "B", "C"), permutation)
        }
        correct_sequence = tuple(label_by_logical_index[index] for index in range(3))
        expected_sequences = list(ORDERING_CHOICES)
        for index, sequence in enumerate(expected_sequences):
            if sequence != correct_sequence:
                del expected_sequences[index]
                break
        expected_choices = [
            f"({first})-({second})-({third})"
            for first, second, third in expected_sequences
        ]
        if generated.choices != expected_choices:
            errors.append(f"choices must be exactly {expected_choices}.")
        else:
            expected_answer = MARKER_CHOICES[expected_choices.index(f"({correct_sequence[0]})-({correct_sequence[1]})-({correct_sequence[2]})")]
            if generated.answer != expected_answer:
                errors.append(
                    f"answer should map to the correct ordering as {expected_answer}, got {generated.answer}."
                )

    intro_text = " ".join(sentence_map[unit_id].text for unit_id in plan.intro_unit_ids)
    for fragment in [intro_text, "(A)", "(B)", "(C)"]:
        if fragment not in generated.student_paragraph:
            errors.append(f"student_paragraph must include {fragment}.")

    preserved_sentences = [sentence_map[unit_id].text for unit_id in sentence_ids]
    normalized_student = normalize_text(generated.student_paragraph)
    for sentence in preserved_sentences:
        if normalized_student.count(normalize_text(sentence)) != 1:
            errors.append(f"Preserved sentence must appear exactly once: {sentence}")

    errors.extend(
        validate_teacher_facing_explanation(
            generated.explanation,
            question_type_key="paragraph_ordering",
        )
    )

    return errors


def validate_mood_atmosphere_output(
    *,
    prepared_source: PreparedSource,
    plan: MoodAtmospherePlan,
    generated: GeneratedQuestion,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    errors: list[str] = []
    expected_choices = [_normalize_choice_pair(choice) for choice in plan.choice_pairs]
    source_text = normalize_text(" ".join(unit.text for unit in prepared_source.sentence_units))

    if generated.QuestionType != type_spec.label_ko:
        errors.append(f"QuestionType should be '{type_spec.label_ko}', got '{generated.QuestionType}'.")
    if generated.question_stem != type_spec.question_stem:
        errors.append("question_stem does not match the question type metadata.")
    if generated.given_sentence is not None:
        errors.append("given_sentence must be None for mood_atmosphere.")
    if normalize_text(generated.student_paragraph) != source_text:
        errors.append("student_paragraph must preserve the original passage for mood_atmosphere.")

    if generated.choices is None or len(generated.choices) != type_spec.choice_count:
        errors.append(f"choices must contain exactly {type_spec.choice_count} items.")
    else:
        normalized_choices = [_normalize_choice_pair(choice) for choice in generated.choices]
        if len(set(normalized_choices)) != len(normalized_choices):
            errors.append("choices must be unique.")
        if any(_MOOD_CHOICE_PAIR_RE.match(choice) is None for choice in normalized_choices):
            errors.append("choices must use English 'emotion -> emotion' format.")
        if normalized_choices != expected_choices:
            errors.append(f"choices must be exactly {expected_choices}.")
        if generated.answer not in MARKER_CHOICES[: len(generated.choices)]:
            errors.append("answer must be one of the rendered marker choices.")
        else:
            expected_answer = MARKER_CHOICES[expected_choices.index(_normalize_choice_pair(plan.correct_choice))]
            if generated.answer != expected_answer:
                errors.append(
                    f"answer should map to the correct emotion shift as {expected_answer}, got {generated.answer}."
                )

    if plan.initial_emotion.strip().lower() == plan.final_emotion.strip().lower():
        errors.append("initial_emotion and final_emotion must differ.")

    for field_name in ("initial_evidence", "final_evidence"):
        evidence = getattr(plan, field_name)
        if normalize_text(evidence) not in source_text:
            errors.append(f"{field_name} must appear in the source passage.")
    if plan.shift_trigger and normalize_text(plan.shift_trigger) not in source_text:
        errors.append("shift_trigger must appear in the source passage.")

    errors.extend(
        validate_teacher_facing_explanation(
            generated.explanation,
            question_type_key="mood_atmosphere",
        )
    )

    return errors


def validate_underlined_phrase_meaning_output(
    *,
    prepared_source: PreparedSource,
    plan: UnderlinedPhraseMeaningPlan,
    generated: GeneratedQuestion,
    type_spec: QuestionTypeSpec,
) -> list[str]:
    errors: list[str] = []
    span_map = {span.id: span for span in prepared_source.span_units}
    selected_span = span_map.get(plan.selected_span_id)
    normalized_choices = [_normalize_korean_choice(choice) for choice in plan.paraphrase_choices_ko]

    if selected_span is None:
        errors.append(f"Unknown selected span ID: {plan.selected_span_id}")
        return errors

    if generated.QuestionType != type_spec.label_ko:
        errors.append(f"QuestionType should be '{type_spec.label_ko}', got '{generated.QuestionType}'.")
    if generated.question_stem != type_spec.question_stem:
        errors.append("question_stem does not match the question type metadata.")
    if generated.given_sentence is not None:
        errors.append("given_sentence must be None for underlined_phrase_meaning.")

    if generated.choices is None or len(generated.choices) != type_spec.choice_count:
        errors.append(f"choices must contain exactly {type_spec.choice_count} items.")
    else:
        normalized_generated_choices = [_normalize_korean_choice(choice) for choice in generated.choices]
        if len(set(normalized_generated_choices)) != len(normalized_generated_choices):
            errors.append("choices must be unique.")
        if any(_HANGUL_RE.search(choice) is None for choice in normalized_generated_choices):
            errors.append("choices must contain Korean text.")
        if normalized_generated_choices != normalized_choices:
            errors.append(f"choices must be exactly {normalized_choices}.")
        if generated.answer not in MARKER_CHOICES[: len(generated.choices)]:
            errors.append("answer must be one of the rendered marker choices.")
        else:
            expected_answer = MARKER_CHOICES[normalized_choices.index(_normalize_korean_choice(plan.correct_choice))]
            if generated.answer != expected_answer:
                errors.append(
                    f"answer should map to the correct Korean paraphrase as {expected_answer}, got {generated.answer}."
                )

    if plan.selected_span_text != selected_span.text:
        errors.append("selected_span_text must exactly match the selected span text.")

    wrapped_text = f"{UNDERLINE_OPEN}{selected_span.text}{UNDERLINE_CLOSE}"
    if generated.student_paragraph.count(UNDERLINE_OPEN) != 1 or generated.student_paragraph.count(UNDERLINE_CLOSE) != 1:
        errors.append("student_paragraph must contain exactly one underlined span wrapper pair.")
    if generated.student_paragraph.count(wrapped_text) != 1:
        errors.append("student_paragraph must wrap the selected span text exactly once with the agreed marker.")

    unwrapped = generated.student_paragraph.replace(UNDERLINE_OPEN, "", 1).replace(UNDERLINE_CLOSE, "", 1)
    if unwrapped != prepared_source.source_text:
        errors.append(
            "student_paragraph must preserve the original passage exactly except for the [밑줄]...[/밑줄] wrapper."
        )

    if normalize_text(plan.supporting_evidence) not in normalize_text(prepared_source.source_text):
        errors.append("supporting_evidence must appear in the source passage.")

    errors.extend(
        validate_teacher_facing_explanation(
            generated.explanation,
            question_type_key="underlined_phrase_meaning",
        )
    )

    return errors


def _should_apply_live_quality_gates(sentence_units: list[object]) -> bool:
    long_sentences = 0
    for unit in sentence_units:
        text = getattr(unit, "text", "")
        if len(text.split()) >= 4:
            long_sentences += 1
    return long_sentences >= 3


def _adjacency_score(left_text: str, right_text: str) -> int:
    score = 0
    shared = content_tokens(left_text) & content_tokens(right_text)
    if shared:
        score += min(3, len(shared) + 1)

    right_lower = normalize_text(right_text).lower()
    left_lower = normalize_text(left_text).lower()
    if left_text.rstrip().endswith("?"):
        score += 2
    if _starts_with_any(right_lower, _TRANSITION_STARTERS):
        score += 1
    if _contains_any(right_lower, _REFERENTIAL_CUES):
        score += 1
    if any(token in right_lower for token in ("this", "these", "such", "therefore", "however")) and left_lower:
        score += 1
    return score


def _looks_connector_only_sentence(text: str) -> bool:
    normalized = normalize_text(text).lower()
    if not normalized:
        return False
    starts_with_connector = _starts_with_any(normalized, _TRANSITION_STARTERS)
    content = content_tokens(text)
    return starts_with_connector and len(content) <= 3


def _looks_like_parallel_blocks(blocks: list[str]) -> bool:
    parallel_count = 0
    for block in blocks:
        normalized = normalize_text(block).lower()
        if _starts_with_any(normalized, _PARALLEL_BLOCK_STARTERS):
            parallel_count += 1
    return parallel_count >= 2


def _underlined_span_quality_error(text: str, tags: list[str], priority_score: int) -> str | None:
    tag_set = set(tags)
    if looks_hanging_phrase(text):
        return "Selected span is fragmentary and leaves a dangling phrase boundary."
    if priority_score < 5:
        return "Selected span is too literal or weak for underlined_phrase_meaning."
    if "surface_comparison" in tag_set and "abstract_term" not in tag_set:
        return "Selected span is a surface comparison phrase, not a central contextual target."
    if not {"abstract_term", "claim_bearing", "phrase_frame"} & tag_set:
        return "Selected span is not central enough to the passage claim for underlined_phrase_meaning."
    return None


def _starts_with_any(text: str, phrases: set[str]) -> bool:
    return any(text.startswith(f"{phrase} ") or text == phrase for phrase in phrases)


def _contains_any(text: str, tokens: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(token)}\b", text) is not None for token in tokens)


GENERATED_QUESTION_VALIDATORS = {
    "sentence_insertion": _validate_sentence_insertion_state,
    "paragraph_ordering": _validate_paragraph_ordering_state,
    "mood_atmosphere": _validate_mood_atmosphere_state,
    "underlined_phrase_meaning": _validate_underlined_phrase_meaning_state,
}


def _normalize_choice_pair(value: str) -> str:
    left, right = [part.strip().lower() for part in value.split("->", 1)]
    return f"{left} -> {right}"


def _normalize_korean_choice(value: str) -> str:
    return normalize_text(value)
