from __future__ import annotations

from typing import Any

from .renderers import DISPLAY_PERMUTATIONS, MARKER_CHOICES
from .schemas import (
    GeneratedQuestion,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    PreparedSource,
    QuestionState,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
)


def build_explanation_context(state: QuestionState) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    plan = state["plan"]
    generated = state["generated"]
    question_type_key = state["QuestionTypeKey"]

    if prepared_source is None or not isinstance(generated, GeneratedQuestion):
        return {
            "status": "rendering_error",
            "errors": ["PreparedSource and GeneratedQuestion are required before explanation generation."],
        }

    if question_type_key == "sentence_insertion":
        if not isinstance(plan, SentenceInsertionPlan):
            return {
                "status": "rendering_error",
                "errors": ["SentenceInsertionPlan is required before explanation generation."],
            }
        return {
            "explanation_context": _build_sentence_insertion_context(prepared_source, plan),
            "status": "rendered",
            "errors": [],
        }

    if question_type_key == "paragraph_ordering":
        if not isinstance(plan, ParagraphOrderingPlan):
            return {
                "status": "rendering_error",
                "errors": ["ParagraphOrderingPlan is required before explanation generation."],
            }
        return {
            "explanation_context": _build_paragraph_ordering_context(prepared_source, plan, generated.BatchRowId),
            "status": "rendered",
            "errors": [],
        }

    if question_type_key == "mood_atmosphere":
        if not isinstance(plan, MoodAtmospherePlan):
            return {
                "status": "rendering_error",
                "errors": ["MoodAtmospherePlan is required before explanation generation."],
            }
        return {
            "explanation_context": _build_mood_atmosphere_context(plan, generated),
            "status": "rendered",
            "errors": [],
        }

    if question_type_key == "underlined_phrase_meaning":
        if not isinstance(plan, UnderlinedPhraseMeaningPlan):
            return {
                "status": "rendering_error",
                "errors": ["UnderlinedPhraseMeaningPlan is required before explanation generation."],
            }
        return {
            "explanation_context": _build_underlined_phrase_meaning_context(plan, generated),
            "status": "rendered",
            "errors": [],
        }

    return {
        "status": "rendering_error",
        "errors": [f"No explanation-context builder is registered for {question_type_key}."],
    }


def write_teacher_facing_explanation(state: QuestionState) -> dict[str, Any]:
    generated = state["generated"]
    explanation_context = state["explanation_context"]
    question_type_key = state["QuestionTypeKey"]

    if not isinstance(generated, GeneratedQuestion) or explanation_context is None:
        return {
            "status": "rendering_error",
            "errors": ["GeneratedQuestion and explanation_context are required before explanation writing."],
        }

    if question_type_key == "sentence_insertion":
        explanation = _write_sentence_insertion_explanation(explanation_context)
    elif question_type_key == "paragraph_ordering":
        explanation = _write_paragraph_ordering_explanation(explanation_context)
    elif question_type_key == "mood_atmosphere":
        explanation = _write_mood_atmosphere_explanation(explanation_context)
    elif question_type_key == "underlined_phrase_meaning":
        explanation = _write_underlined_phrase_meaning_explanation(explanation_context)
    else:
        return {
            "status": "rendering_error",
            "errors": [f"No explanation writer is registered for {question_type_key}."],
        }

    return {
        "generated": generated.model_copy(update={"explanation": explanation}),
        "status": "rendered",
        "errors": [],
    }


def _build_sentence_insertion_context(
    prepared_source: PreparedSource,
    plan: SentenceInsertionPlan,
) -> dict[str, str | None]:
    sentence_map = {unit.id: unit.text for unit in prepared_source.sentence_units}
    gap_map = {gap.id: gap for gap in prepared_source.gap_units}
    target_id = plan.target_unit_ids[0]
    correct_gap = gap_map[plan.correct_gap_id]
    correct_marker = MARKER_CHOICES[plan.selected_gap_ids.index(plan.correct_gap_id)]

    before_text = sentence_map.get(correct_gap.before_unit_id) if correct_gap.before_unit_id else None
    after_text = sentence_map.get(correct_gap.after_unit_id) if correct_gap.after_unit_id else None

    return {
        "target_text": sentence_map[target_id],
        "before_text": before_text,
        "after_text": after_text,
        "correct_marker": correct_marker,
    }


def _build_paragraph_ordering_context(
    prepared_source: PreparedSource,
    plan: ParagraphOrderingPlan,
    batch_row_id: int,
) -> dict[str, Any]:
    sentence_map = {unit.id: unit.text for unit in prepared_source.sentence_units}
    logical_blocks = [
        " ".join(sentence_map[unit_id] for unit_id in block)
        for block in plan.continuation_blocks
    ]
    permutation = DISPLAY_PERMUTATIONS[batch_row_id % len(DISPLAY_PERMUTATIONS)]
    displayed_blocks = [logical_blocks[index] for index in permutation]
    label_by_logical_index = {
        logical_index: label
        for label, logical_index in zip(("A", "B", "C"), permutation)
    }
    correct_sequence = tuple(label_by_logical_index[index] for index in range(3))

    return {
        "intro_text": " ".join(sentence_map[unit_id] for unit_id in plan.intro_unit_ids),
        "displayed_blocks": {
            "A": displayed_blocks[0],
            "B": displayed_blocks[1],
            "C": displayed_blocks[2],
        },
        "correct_sequence": correct_sequence,
    }


def _build_mood_atmosphere_context(
    plan: MoodAtmospherePlan,
    generated: GeneratedQuestion,
) -> dict[str, str | None]:
    correct_marker = generated.answer
    correct_choice = generated.choices[["①", "②", "③", "④", "⑤"].index(correct_marker)] if generated.choices else plan.correct_choice
    return {
        "target_holder": plan.target_holder,
        "initial_emotion": plan.initial_emotion,
        "final_emotion": plan.final_emotion,
        "initial_evidence": plan.initial_evidence,
        "final_evidence": plan.final_evidence,
        "shift_trigger": plan.shift_trigger,
        "correct_marker": correct_marker,
        "correct_choice": correct_choice,
    }


def _build_underlined_phrase_meaning_context(
    plan: UnderlinedPhraseMeaningPlan,
    generated: GeneratedQuestion,
) -> dict[str, str]:
    correct_marker = generated.answer
    choice_index = ["①", "②", "③", "④", "⑤"].index(correct_marker)
    correct_choice = generated.choices[choice_index] if generated.choices else plan.correct_choice
    return {
        "selected_span_text": plan.selected_span_text,
        "surface_meaning": plan.surface_meaning,
        "contextual_meaning": plan.contextual_meaning,
        "supporting_evidence": plan.supporting_evidence,
        "correct_marker": correct_marker,
        "correct_choice": correct_choice,
    }


def _write_sentence_insertion_explanation(context: dict[str, str | None]) -> str:
    target_text = _sentence_snippet(context["target_text"])
    before_text = context["before_text"]
    after_text = context["after_text"]
    correct_marker = context["correct_marker"]

    if before_text and after_text:
        return (
            f"주어진 문장은 {target_text}에 관한 내용을 담고 있습니다. "
            f"앞에서는 {_sentence_snippet(before_text)}을 말하고, "
            f"뒤에서는 {_sentence_snippet(after_text)}을 이어 설명하므로 "
            f"이 문장이 두 내용을 자연스럽게 연결합니다. "
            f"따라서 {correct_marker} 위치에 들어가는 것이 가장 적절합니다."
        )

    if before_text:
        return (
            f"주어진 문장은 {target_text}에 관한 내용을 덧붙이며 "
            f"앞의 {_sentence_snippet(before_text)}을 자연스럽게 이어 줍니다. "
            f"따라서 {correct_marker} 위치에 들어가는 것이 가장 적절합니다."
        )

    if after_text:
        return (
            f"주어진 문장은 {target_text}에 관한 내용을 먼저 제시한 뒤 "
            f"뒤의 {_sentence_snippet(after_text)}으로 이어지는 흐름을 만듭니다. "
            f"따라서 {correct_marker} 위치에 들어가는 것이 가장 적절합니다."
        )

    return f"주어진 문장은 글의 전체 흐름을 보완하는 역할을 하므로, {correct_marker} 위치에 들어가는 것이 가장 적절합니다."


def _write_paragraph_ordering_explanation(context: dict[str, Any]) -> str:
    intro_text = _sentence_snippet(context["intro_text"])
    displayed_blocks = context["displayed_blocks"]
    first_label, second_label, third_label = context["correct_sequence"]
    first_block = _sentence_snippet(displayed_blocks[first_label])
    second_block = _sentence_snippet(displayed_blocks[second_label])
    third_block = _sentence_snippet(displayed_blocks[third_label])

    return (
        f"주어진 글은 {intro_text}로 핵심 화제를 제시합니다. "
        f"그다음에는 ({first_label})의 {first_block}이 가장 자연스럽게 이어지며, "
        f"이후 ({second_label})의 {second_block}이 앞내용을 확장합니다. "
        f"마지막으로 ({third_label})의 {third_block}이 글을 마무리하므로 "
        f"순서는 ({first_label})-({second_label})-({third_label})가 가장 적절합니다."
    )


def _write_mood_atmosphere_explanation(context: dict[str, str | None]) -> str:
    target_holder = context["target_holder"] or "중심 인물"
    initial_emotion = context["initial_emotion"] or "initial"
    final_emotion = context["final_emotion"] or "final"
    initial_evidence = context["initial_evidence"] or ""
    final_evidence = context["final_evidence"] or ""
    shift_trigger = context["shift_trigger"]
    correct_marker = context["correct_marker"] or "①"
    correct_choice = context["correct_choice"] or f"{initial_emotion} -> {final_emotion}"

    if shift_trigger:
        return (
            f"글에서 {target_holder}는 처음에 '{initial_evidence}'에서 드러나듯 {initial_emotion}한 상태입니다. "
            f"이후 '{shift_trigger}'를 계기로 정서의 방향이 바뀌고, "
            f"마지막에는 '{final_evidence}'에서 보이듯 {final_emotion}한 상태에 이릅니다. "
            f"따라서 심경 변화로 가장 적절한 것은 {correct_marker} {correct_choice}입니다."
        )

    return (
        f"글에서 {target_holder}는 처음에 '{initial_evidence}'에서 드러나듯 {initial_emotion}한 상태입니다. "
        f"반면 마지막에는 '{final_evidence}'에서 보이듯 {final_emotion}한 상태로 바뀝니다. "
        f"따라서 심경 변화로 가장 적절한 것은 {correct_marker} {correct_choice}입니다."
    )


def _write_underlined_phrase_meaning_explanation(context: dict[str, str]) -> str:
    selected_span_text = context["selected_span_text"]
    surface_meaning = context["surface_meaning"]
    contextual_meaning = context["contextual_meaning"]
    supporting_evidence = context["supporting_evidence"]
    correct_marker = context["correct_marker"]
    correct_choice = context["correct_choice"]

    return (
        f"밑줄 친 '{selected_span_text}'는 표면적으로는 {surface_meaning}라는 표현입니다. "
        f"하지만 이 글에서는 {contextual_meaning}라는 뜻으로 이해해야 합니다. "
        f"특히 '{supporting_evidence}'라는 내용이 그 해석을 뒷받침하므로 "
        f"정답은 {correct_marker} {correct_choice}입니다."
    )


def _sentence_snippet(text: str, *, max_words: int = 12) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."
