from __future__ import annotations

import re
from typing import Any

from .parsers import normalize_text
from .question_types import QuestionTypeSpec
from .schemas import (
    FillInTheBlankPlan,
    GrammarPlan,
    GeneratedQuestion,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    PreparedSource,
    QuestionState,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
    VocabPlan,
)
from .targeting import (
    BLANK_MARKER,
    grammar_target_inventory,
    normalize_english_choice,
    numbered_underline_close,
    numbered_underline_open,
    phrase_span_inventory,
    render_numbered_span_edits,
    vocab_target_inventory,
)

MARKER_CHOICES = ["①", "②", "③", "④", "⑤"]
UNDERLINE_OPEN = "[밑줄]"
UNDERLINE_CLOSE = "[/밑줄]"
ORDERING_CHOICES = [
    ("A", "B", "C"),
    ("A", "C", "B"),
    ("B", "A", "C"),
    ("B", "C", "A"),
    ("C", "A", "B"),
    ("C", "B", "A"),
]
DISPLAY_PERMUTATIONS = [
    (0, 2, 1),
    (1, 0, 2),
    (1, 2, 0),
    (2, 0, 1),
    (2, 1, 0),
]
_CHOICE_PAIR_SPACING_RE = re.compile(r"\s*->\s*")


def render_sentence_insertion(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]

    if prepared_source is None or not isinstance(plan, SentenceInsertionPlan):
        return {
            "status": "rendering_error",
            "errors": ["PreparedSource and SentenceInsertionPlan are required for rendering."],
        }

    try:
        generated = _build_sentence_insertion_question(
            original_question_number=state["OriginalQuestionNumber"],
            batch_row_id=state["BatchRowId"],
            prepared_source=prepared_source,
            plan=plan,
            type_spec=type_spec,
        )
    except Exception as exc:
        return {
            "status": "rendering_error",
            "errors": [f"Renderer failed: {exc}"],
        }

    return {
        "generated": generated,
        "status": "rendered",
        "errors": [],
    }


def render_paragraph_ordering(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]

    if prepared_source is None or not isinstance(plan, ParagraphOrderingPlan):
        return {
            "status": "rendering_error",
            "errors": ["PreparedSource and ParagraphOrderingPlan are required for rendering."],
        }

    try:
        generated = _build_paragraph_ordering_question(
            original_question_number=state["OriginalQuestionNumber"],
            batch_row_id=state["BatchRowId"],
            prepared_source=prepared_source,
            plan=plan,
            type_spec=type_spec,
        )
    except Exception as exc:
        return {
            "status": "rendering_error",
            "errors": [f"Renderer failed: {exc}"],
        }

    return {
        "generated": generated,
        "status": "rendered",
        "errors": [],
    }


def render_mood_atmosphere(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    plan = state["plan"]

    if not isinstance(plan, MoodAtmospherePlan):
        return {
            "status": "rendering_error",
            "errors": ["MoodAtmospherePlan is required for rendering."],
        }

    try:
        generated = _build_mood_atmosphere_question(
            original_question_number=state["OriginalQuestionNumber"],
            batch_row_id=state["BatchRowId"],
            source_paragraph=state["source_paragraph"],
            plan=plan,
            type_spec=type_spec,
        )
    except Exception as exc:
        return {
            "status": "rendering_error",
            "errors": [f"Renderer failed: {exc}"],
        }

    return {
        "generated": generated,
        "status": "rendered",
        "errors": [],
    }


def render_underlined_phrase_meaning(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]

    if prepared_source is None or not isinstance(plan, UnderlinedPhraseMeaningPlan):
        return {
            "status": "rendering_error",
            "errors": ["PreparedSource and UnderlinedPhraseMeaningPlan are required for rendering."],
        }

    try:
        generated = _build_underlined_phrase_meaning_question(
            original_question_number=state["OriginalQuestionNumber"],
            batch_row_id=state["BatchRowId"],
            source_paragraph=state["source_paragraph"],
            prepared_source=prepared_source,
            plan=plan,
            type_spec=type_spec,
        )
    except Exception as exc:
        return {
            "status": "rendering_error",
            "errors": [f"Renderer failed: {exc}"],
        }

    return {
        "generated": generated,
        "status": "rendered",
        "errors": [],
    }


def render_fill_in_the_blank(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]

    if prepared_source is None or not isinstance(plan, FillInTheBlankPlan):
        return {
            "status": "rendering_error",
            "errors": ["PreparedSource and FillInTheBlankPlan are required for rendering."],
        }

    try:
        generated = _build_fill_in_the_blank_question(
            original_question_number=state["OriginalQuestionNumber"],
            batch_row_id=state["BatchRowId"],
            source_paragraph=state["source_paragraph"],
            prepared_source=prepared_source,
            plan=plan,
            type_spec=type_spec,
        )
    except Exception as exc:
        return {
            "status": "rendering_error",
            "errors": [f"Renderer failed: {exc}"],
        }

    return {
        "generated": generated,
        "status": "rendered",
        "errors": [],
    }


def render_vocab(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]

    if prepared_source is None or not isinstance(plan, VocabPlan):
        return {
            "status": "rendering_error",
            "errors": ["PreparedSource and VocabPlan are required for rendering."],
        }

    try:
        generated = _build_vocab_question(
            original_question_number=state["OriginalQuestionNumber"],
            batch_row_id=state["BatchRowId"],
            source_paragraph=state["source_paragraph"],
            prepared_source=prepared_source,
            plan=plan,
            type_spec=type_spec,
        )
    except Exception as exc:
        return {
            "status": "rendering_error",
            "errors": [f"Renderer failed: {exc}"],
        }

    return {
        "generated": generated,
        "status": "rendered",
        "errors": [],
    }


def render_grammar(
    state: QuestionState,
    type_spec: QuestionTypeSpec,
) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]

    if prepared_source is None or not isinstance(plan, GrammarPlan):
        return {
            "status": "rendering_error",
            "errors": ["PreparedSource and GrammarPlan are required for rendering."],
        }

    try:
        generated = _build_grammar_question(
            original_question_number=state["OriginalQuestionNumber"],
            batch_row_id=state["BatchRowId"],
            source_paragraph=state["source_paragraph"],
            prepared_source=prepared_source,
            plan=plan,
            type_spec=type_spec,
        )
    except Exception as exc:
        return {
            "status": "rendering_error",
            "errors": [f"Renderer failed: {exc}"],
        }

    return {
        "generated": generated,
        "status": "rendered",
        "errors": [],
    }


def _build_sentence_insertion_question(
    *,
    original_question_number: str,
    batch_row_id: int,
    prepared_source: PreparedSource,
    plan: SentenceInsertionPlan,
    type_spec: QuestionTypeSpec,
) -> GeneratedQuestion:
    sentence_map = {unit.id: unit for unit in prepared_source.sentence_units}
    target_id = plan.target_unit_ids[0]
    if target_id not in sentence_map:
        raise ValueError(f"Unknown target sentence ID: {target_id}")

    if type_spec.choice_count != len(MARKER_CHOICES):
        raise ValueError("Wave-1 renderer expects exactly five choices.")

    rendered_positions = rendered_gap_positions(prepared_source, plan.target_unit_ids[0])
    if len({rendered_positions[gap_id] for gap_id in plan.selected_gap_ids}) != len(plan.selected_gap_ids):
        raise ValueError(
            "Selected gaps collapse into the same rendered position after removing the target sentence."
        )

    marker_by_gap = {
        gap_id: MARKER_CHOICES[index]
        for index, gap_id in enumerate(plan.selected_gap_ids)
    }

    segments: list[str] = []
    for gap in prepared_source.gap_units:
        marker = marker_by_gap.get(gap.id)
        if marker:
            segments.append(marker)
        if gap.index < len(prepared_source.sentence_units):
            sentence = prepared_source.sentence_units[gap.index]
            if sentence.id != target_id:
                segments.append(sentence.text)

    student_paragraph = normalize_text(" ".join(segments))
    answer = marker_by_gap[plan.correct_gap_id]

    return GeneratedQuestion(
        OriginalQuestionNumber=original_question_number,
        BatchRowId=batch_row_id,
        QuestionType=type_spec.label_ko,
        student_paragraph=student_paragraph,
        question_stem=type_spec.question_stem,
        given_sentence=sentence_map[target_id].text,
        choices=MARKER_CHOICES[: type_spec.choice_count],
        answer=answer,
        explanation=plan.explanation,
    )


def _build_paragraph_ordering_question(
    *,
    original_question_number: str,
    batch_row_id: int,
    prepared_source: PreparedSource,
    plan: ParagraphOrderingPlan,
    type_spec: QuestionTypeSpec,
) -> GeneratedQuestion:
    sentence_map = {unit.id: unit for unit in prepared_source.sentence_units}
    sentence_ids = [unit.id for unit in prepared_source.sentence_units]
    all_block_ids = plan.intro_unit_ids + [
        unit_id
        for block in plan.continuation_blocks
        for unit_id in block
    ]
    if all_block_ids != sentence_ids:
        raise ValueError("ParagraphOrderingPlan blocks must cover all sentence IDs exactly once in source order.")

    intro_text = " ".join(sentence_map[unit_id].text for unit_id in plan.intro_unit_ids)
    logical_blocks = [
        " ".join(sentence_map[unit_id].text for unit_id in block)
        for block in plan.continuation_blocks
    ]
    permutation = DISPLAY_PERMUTATIONS[batch_row_id % len(DISPLAY_PERMUTATIONS)]
    displayed_blocks = [logical_blocks[index] for index in permutation]

    label_by_logical_index = {
        logical_index: label
        for label, logical_index in zip(("A", "B", "C"), permutation)
    }
    correct_sequence = tuple(label_by_logical_index[index] for index in range(3))

    choice_sequences = list(ORDERING_CHOICES)
    for index, sequence in enumerate(choice_sequences):
        if sequence != correct_sequence:
            del choice_sequences[index]
            break

    choices = [f"({first})-({second})-({third})" for first, second, third in choice_sequences]
    answer = MARKER_CHOICES[choice_sequences.index(correct_sequence)]

    student_paragraph = (
        f"[주어진 글] {intro_text}\n\n"
        f"(A) {displayed_blocks[0]}\n\n"
        f"(B) {displayed_blocks[1]}\n\n"
        f"(C) {displayed_blocks[2]}"
    )

    return GeneratedQuestion(
        OriginalQuestionNumber=original_question_number,
        BatchRowId=batch_row_id,
        QuestionType=type_spec.label_ko,
        student_paragraph=student_paragraph,
        question_stem=type_spec.question_stem,
        choices=choices,
        answer=answer,
        explanation=plan.explanation,
    )


def _build_mood_atmosphere_question(
    *,
    original_question_number: str,
    batch_row_id: int,
    source_paragraph: str,
    plan: MoodAtmospherePlan,
    type_spec: QuestionTypeSpec,
) -> GeneratedQuestion:
    if type_spec.choice_count != len(MARKER_CHOICES):
        raise ValueError("Mood/atmosphere renderer expects exactly five choices.")

    if plan.correct_choice not in plan.choice_pairs:
        raise ValueError("MoodAtmospherePlan correct_choice must be included in choice_pairs.")

    choices = [_normalize_choice_pair(choice) for choice in plan.choice_pairs]
    answer = MARKER_CHOICES[choices.index(_normalize_choice_pair(plan.correct_choice))]

    return GeneratedQuestion(
        OriginalQuestionNumber=original_question_number,
        BatchRowId=batch_row_id,
        QuestionType=type_spec.label_ko,
        student_paragraph=normalize_text(source_paragraph),
        question_stem=type_spec.question_stem,
        given_sentence=None,
        choices=choices,
        answer=answer,
        explanation=plan.explanation,
    )


def _build_underlined_phrase_meaning_question(
    *,
    original_question_number: str,
    batch_row_id: int,
    source_paragraph: str,
    prepared_source: PreparedSource,
    plan: UnderlinedPhraseMeaningPlan,
    type_spec: QuestionTypeSpec,
) -> GeneratedQuestion:
    if type_spec.choice_count != len(MARKER_CHOICES):
        raise ValueError("Underlined phrase meaning renderer expects exactly five choices.")

    span_map = {span.id: span for span in prepared_source.span_units}
    selected_span = span_map.get(plan.selected_span_id)
    if selected_span is None:
        raise ValueError(f"Unknown selected span ID: {plan.selected_span_id}")
    if plan.selected_span_text != selected_span.text:
        raise ValueError("selected_span_text must exactly match the selected span text.")

    wrapped_paragraph = (
        source_paragraph[: selected_span.char_start]
        + f"{UNDERLINE_OPEN}{selected_span.text}{UNDERLINE_CLOSE}"
        + source_paragraph[selected_span.char_end :]
    )

    choices = [_normalize_korean_choice(choice) for choice in plan.paraphrase_choices_ko]
    correct_choice = _normalize_korean_choice(plan.correct_choice)
    if correct_choice not in choices:
        raise ValueError("correct_choice must be included in paraphrase_choices_ko.")
    answer = MARKER_CHOICES[choices.index(correct_choice)]

    return GeneratedQuestion(
        OriginalQuestionNumber=original_question_number,
        BatchRowId=batch_row_id,
        QuestionType=type_spec.label_ko,
        student_paragraph=wrapped_paragraph,
        question_stem=type_spec.question_stem,
        given_sentence=None,
        choices=choices,
        answer=answer,
        explanation=plan.explanation,
    )


def _build_fill_in_the_blank_question(
    *,
    original_question_number: str,
    batch_row_id: int,
    source_paragraph: str,
    prepared_source: PreparedSource,
    plan: FillInTheBlankPlan,
    type_spec: QuestionTypeSpec,
) -> GeneratedQuestion:
    if type_spec.choice_count != len(MARKER_CHOICES):
        raise ValueError("Fill-in-the-blank renderer expects exactly five choices.")

    span_map = {span.id: span for span in phrase_span_inventory(prepared_source)}
    selected_span = span_map.get(plan.selected_span_id)
    if selected_span is None:
        raise ValueError(f"Unknown selected span ID: {plan.selected_span_id}")
    if plan.selected_span_text != selected_span.text:
        raise ValueError("selected_span_text must exactly match the selected span text.")

    student_paragraph = (
        source_paragraph[: selected_span.char_start]
        + BLANK_MARKER
        + source_paragraph[selected_span.char_end :]
    )
    choices = [normalize_english_choice(choice) for choice in plan.completion_choices]
    correct_choice = normalize_english_choice(plan.correct_choice)
    if correct_choice not in choices:
        raise ValueError("correct_choice must be included in completion_choices.")
    answer = MARKER_CHOICES[choices.index(correct_choice)]

    return GeneratedQuestion(
        OriginalQuestionNumber=original_question_number,
        BatchRowId=batch_row_id,
        QuestionType=type_spec.label_ko,
        student_paragraph=student_paragraph,
        question_stem=type_spec.question_stem,
        given_sentence=None,
        choices=choices,
        answer=answer,
        explanation=plan.explanation,
    )


def _build_vocab_question(
    *,
    original_question_number: str,
    batch_row_id: int,
    source_paragraph: str,
    prepared_source: PreparedSource,
    plan: VocabPlan,
    type_spec: QuestionTypeSpec,
) -> GeneratedQuestion:
    if type_spec.choice_count != len(MARKER_CHOICES):
        raise ValueError("Vocab renderer expects exactly five targets.")

    inventory = {span.id: span for span in vocab_target_inventory(prepared_source)}
    selected_spans = _ordered_target_spans(
        inventory=inventory,
        target_span_ids=plan.target_span_ids,
        target_span_texts=plan.target_span_texts,
    )
    if plan.corrupted_span_id not in plan.target_span_ids:
        raise ValueError("corrupted_span_id must be included in target_span_ids.")

    student_paragraph = render_numbered_span_edits(
        source_text=source_paragraph,
        selected_spans=selected_spans,
        replacement_by_span_id={plan.corrupted_span_id: plan.corrupted_word.strip()},
        markers=MARKER_CHOICES[: type_spec.choice_count],
    )
    ordered_ids = [span.id for span in selected_spans]
    answer = MARKER_CHOICES[ordered_ids.index(plan.corrupted_span_id)]

    return GeneratedQuestion(
        OriginalQuestionNumber=original_question_number,
        BatchRowId=batch_row_id,
        QuestionType=type_spec.label_ko,
        student_paragraph=student_paragraph,
        question_stem=type_spec.question_stem,
        given_sentence=None,
        choices=MARKER_CHOICES[: type_spec.choice_count],
        answer=answer,
        explanation=plan.explanation,
    )


def _build_grammar_question(
    *,
    original_question_number: str,
    batch_row_id: int,
    source_paragraph: str,
    prepared_source: PreparedSource,
    plan: GrammarPlan,
    type_spec: QuestionTypeSpec,
) -> GeneratedQuestion:
    if type_spec.choice_count != len(MARKER_CHOICES):
        raise ValueError("Grammar renderer expects exactly five targets.")

    inventory = {span.id: span for span in grammar_target_inventory(prepared_source)}
    selected_spans = _ordered_target_spans(
        inventory=inventory,
        target_span_ids=plan.target_span_ids,
        target_span_texts=plan.target_span_texts,
    )
    if plan.corrupted_span_id not in plan.target_span_ids:
        raise ValueError("corrupted_span_id must be included in target_span_ids.")

    student_paragraph = render_numbered_span_edits(
        source_text=source_paragraph,
        selected_spans=selected_spans,
        replacement_by_span_id={plan.corrupted_span_id: plan.corrupted_word.strip()},
        markers=MARKER_CHOICES[: type_spec.choice_count],
    )
    ordered_ids = [span.id for span in selected_spans]
    answer = MARKER_CHOICES[ordered_ids.index(plan.corrupted_span_id)]

    return GeneratedQuestion(
        OriginalQuestionNumber=original_question_number,
        BatchRowId=batch_row_id,
        QuestionType=type_spec.label_ko,
        student_paragraph=student_paragraph,
        question_stem=type_spec.question_stem,
        given_sentence=None,
        choices=MARKER_CHOICES[: type_spec.choice_count],
        answer=answer,
        explanation=plan.explanation,
    )


def rendered_gap_positions(prepared_source: PreparedSource, target_id: str) -> dict[str, tuple[str | None, str | None]]:
    positions: dict[str, tuple[str | None, str | None]] = {}
    sentence_ids = [unit.id for unit in prepared_source.sentence_units]
    target_index = sentence_ids.index(target_id)
    previous_unit_id = sentence_ids[target_index - 1] if target_index > 0 else None
    next_unit_id = sentence_ids[target_index + 1] if target_index + 1 < len(sentence_ids) else None

    for gap in prepared_source.gap_units:
        before_unit_id = gap.before_unit_id
        after_unit_id = gap.after_unit_id

        if before_unit_id == target_id:
            before_unit_id = previous_unit_id
        if after_unit_id == target_id:
            after_unit_id = next_unit_id

        positions[gap.id] = (before_unit_id, after_unit_id)

    return positions


RENDERERS = {
    "sentence_insertion": render_sentence_insertion,
    "paragraph_ordering": render_paragraph_ordering,
    "mood_atmosphere": render_mood_atmosphere,
    "underlined_phrase_meaning": render_underlined_phrase_meaning,
    "fill_in_the_blank": render_fill_in_the_blank,
    "vocab": render_vocab,
    "grammar": render_grammar,
}


def _normalize_choice_pair(value: str) -> str:
    return _CHOICE_PAIR_SPACING_RE.sub(" -> ", value.strip())


def _normalize_korean_choice(value: str) -> str:
    return normalize_text(value)


def _ordered_target_spans(
    *,
    inventory: dict[str, object],
    target_span_ids: list[str],
    target_span_texts: list[str],
) -> list[object]:
    if len(target_span_ids) != len(target_span_texts):
        raise ValueError("target_span_ids and target_span_texts must have the same length.")
    selected_spans = []
    for span_id, expected_text in zip(target_span_ids, target_span_texts):
        span = inventory.get(span_id)
        if span is None:
            raise ValueError(f"Unknown target span ID: {span_id}")
        if getattr(span, "text") != expected_text:
            raise ValueError(f"target_span_texts must exactly match the source text for {span_id}.")
        selected_spans.append(span)
    return sorted(selected_spans, key=lambda span: (span.char_start, span.char_end))
