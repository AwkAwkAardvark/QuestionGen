from __future__ import annotations

from typing import Any

from .parsers import normalize_text
from .question_types import QUESTION_TYPES, QuestionTypeSpec
from .renderers import MARKER_CHOICES
from .schemas import GeneratedQuestion, PreparedSource, QuestionState, SentenceInsertionPlan


def input_check(state: QuestionState) -> dict[str, Any]:
    errors: list[str] = []
    if state["QuestionTypeKey"] not in QUESTION_TYPES:
        errors.append(f"Unknown QuestionTypeKey: {state['QuestionTypeKey']}")
    if not isinstance(state["OriginalQuestionNumber"], int):
        errors.append("OriginalQuestionNumber must be an integer.")
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

    errors = validate_prepared_source(prepared_source, min_source_units=type_spec.min_source_units)
    if errors:
        return {
            "status": "source_error",
            "errors": errors,
        }
    return {
        "status": "source_passed",
        "errors": [],
    }


def validate_prepared_source(
    prepared_source: PreparedSource,
    *,
    min_source_units: int | None = None,
) -> list[str]:
    errors: list[str] = []
    sentence_units = prepared_source.sentence_units
    gap_units = prepared_source.gap_units

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

    return errors


def validate_generated_question(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]
    generated = state["generated"]

    if prepared_source is None:
        return {
            "status": "validation_error",
            "errors": ["PreparedSource is missing for validation."],
        }
    if not isinstance(plan, SentenceInsertionPlan):
        return {
            "status": "validation_error",
            "errors": ["SentenceInsertionPlan is missing for validation."],
        }
    if not isinstance(generated, GeneratedQuestion):
        return {
            "status": "validation_error",
            "errors": ["GeneratedQuestion is missing for validation."],
        }

    errors = validate_sentence_insertion_output(
        prepared_source=prepared_source,
        plan=plan,
        generated=generated,
        type_spec=type_spec,
    )
    if errors:
        return {
            "status": "validation_error",
            "errors": errors,
        }
    return {
        "status": "validation_passed",
        "errors": [],
    }


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

    if generated.explanation is None or not generated.explanation.strip():
        errors.append("explanation is required.")

    return errors
