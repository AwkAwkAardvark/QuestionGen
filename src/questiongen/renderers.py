from __future__ import annotations

from typing import Any

from .parsers import normalize_text
from .question_types import QuestionTypeSpec
from .schemas import GeneratedQuestion, PreparedSource, QuestionState, SentenceInsertionPlan

MARKER_CHOICES = ["①", "②", "③", "④", "⑤"]


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
    original_question_number: int,
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
        QuestionType=type_spec.label_ko,
        student_paragraph=student_paragraph,
        question_stem=type_spec.question_stem,
        given_sentence=sentence_map[target_id].text,
        choices=MARKER_CHOICES[: type_spec.choice_count],
        answer=answer,
        explanation=plan.explanation,
    )


RENDERERS = {
    "sentence_insertion": render_sentence_insertion,
}
