from __future__ import annotations

import re
from typing import Any

from .renderers import DISPLAY_PERMUTATIONS, MARKER_CHOICES, rendered_gap_positions
from .schemas import (
    ContextualVocabChoicePlan,
    FillInTheBlankPlan,
    GrammarDesign,
    GrammarPlan,
    GeneratedQuestion,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    PreparedSource,
    QuestionState,
    SentenceInsertionPlan,
    UnderlinedVocabDesign,
    UnderlinedVocabPlan,
    UnderlinedPhraseMeaningPlan,
    VocabChoiceDesign,
    VocabPlan,
)
from .targeting import (
    fill_blank_inventory_for_subtype,
    grammar_target_inventory,
    phrase_span_inventory,
    vocab_choice_inventory,
    vocab_target_inventory,
)


def build_explanation_context(state: QuestionState) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    design = state.get("design")
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

    if question_type_key == "fill_in_the_blank":
        if not isinstance(plan, FillInTheBlankPlan):
            return {
                "status": "rendering_error",
                "errors": ["FillInTheBlankPlan is required before explanation generation."],
            }
        return {
            "explanation_context": _build_fill_in_the_blank_context(
                plan,
                generated,
                prepared_source=prepared_source,
                question_subtype_key=generated.QuestionSubtypeKey or state.get("QuestionSubtypeKey"),
            ),
            "status": "rendered",
            "errors": [],
        }

    if question_type_key == "vocab":
        if not isinstance(plan, (ContextualVocabChoicePlan, UnderlinedVocabPlan, VocabPlan)):
            return {
                "status": "rendering_error",
                "errors": ["A vocab plan is required before explanation generation."],
            }
        return {
            "explanation_context": _build_vocab_context(
                plan,
                generated,
                design=design,
                prepared_source=prepared_source,
                question_subtype_key=generated.QuestionSubtypeKey or state.get("QuestionSubtypeKey"),
            ),
            "status": "rendered",
            "errors": [],
        }

    if question_type_key == "grammar":
        if not isinstance(plan, GrammarPlan):
            return {
                "status": "rendering_error",
                "errors": ["GrammarPlan is required before explanation generation."],
            }
        return {
            "explanation_context": _build_grammar_context(prepared_source, plan, design=design),
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
    elif question_type_key == "fill_in_the_blank":
        explanation = _write_fill_in_the_blank_explanation(explanation_context)
    elif question_type_key == "vocab":
        explanation = _write_vocab_explanation(explanation_context)
    elif question_type_key == "grammar":
        explanation = _write_grammar_explanation(explanation_context)
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
    target_id = plan.target_unit_ids[0]
    correct_marker = MARKER_CHOICES[plan.selected_gap_ids.index(plan.correct_gap_id)]
    rendered_positions = rendered_gap_positions(prepared_source, target_id)
    before_unit_id, after_unit_id = rendered_positions[plan.correct_gap_id]

    before_text = sentence_map.get(before_unit_id) if before_unit_id else None
    after_text = sentence_map.get(after_unit_id) if after_unit_id else None

    return {
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
    logical_blocks = [[sentence_map[unit_id] for unit_id in block] for block in plan.continuation_blocks]
    permutation = DISPLAY_PERMUTATIONS[batch_row_id % len(DISPLAY_PERMUTATIONS)]
    displayed_blocks = [" ".join(logical_blocks[index]) for index in permutation]
    label_by_logical_index = {
        logical_index: label
        for label, logical_index in zip(("A", "B", "C"), permutation)
    }
    correct_sequence = tuple(label_by_logical_index[index] for index in range(3))
    ordered_segments = [
        ("주어진 글", [sentence_map[unit_id] for unit_id in plan.intro_unit_ids]),
        *((label_by_logical_index[index], logical_blocks[index]) for index in range(3)),
    ]
    edges = [
        {
            "from_label": ordered_segments[index][0],
            "to_label": ordered_segments[index + 1][0],
            "from_tail": ordered_segments[index][1][-1],
            "to_head": ordered_segments[index + 1][1][0],
        }
        for index in range(len(ordered_segments) - 1)
    ]

    return {
        "intro_text": " ".join(sentence_map[unit_id] for unit_id in plan.intro_unit_ids),
        "displayed_blocks": {
            "A": displayed_blocks[0],
            "B": displayed_blocks[1],
            "C": displayed_blocks[2],
        },
        "correct_sequence": correct_sequence,
        "edges": edges,
    }


def _build_mood_atmosphere_context(
    plan: MoodAtmospherePlan,
    generated: GeneratedQuestion,
) -> dict[str, str | None]:
    correct_marker = generated.answer
    correct_choice = generated.choices[["①", "②", "③", "④", "⑤"].index(correct_marker)] if generated.choices else plan.correct_choice
    return {
        "subtype": plan.subtype,
        "target_holder": plan.target_holder,
        "initial_emotion": plan.initial_emotion,
        "final_emotion": plan.final_emotion,
        "state_emotion": plan.state_emotion,
        "atmosphere_label": plan.atmosphere_label,
        "initial_evidence": plan.initial_evidence,
        "final_evidence": plan.final_evidence,
        "shift_trigger": plan.shift_trigger,
        "state_evidence": plan.state_evidence,
        "atmosphere_evidence": plan.atmosphere_evidence,
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


def _build_fill_in_the_blank_context(
    plan: FillInTheBlankPlan,
    generated: GeneratedQuestion,
    *,
    prepared_source: PreparedSource,
    question_subtype_key: str | None = None,
) -> dict[str, str]:
    choice_index = MARKER_CHOICES.index(generated.answer)
    correct_choice = generated.choices[choice_index] if generated.choices else plan.correct_choice
    subtype_key = question_subtype_key or "blank_inference_proposition_5_choices"
    span_inventory = {span.id: span for span in fill_blank_inventory_for_subtype(prepared_source, subtype_key)}
    sentence_map = {unit.id: unit.text for unit in prepared_source.sentence_units}
    selected_span = span_inventory.get(plan.selected_span_id)
    source_sentence = sentence_map.get(selected_span.sentence_unit_id or "", "") if selected_span is not None else ""
    support_quote = plan.supporting_evidence
    if selected_span is not None and " ".join(plan.supporting_evidence.split()).lower() == " ".join(plan.selected_span_text.split()).lower():
        support_quote = source_sentence.replace(plan.selected_span_text, "_____", 1) if source_sentence else plan.supporting_evidence
    return {
        "selected_span_text": plan.selected_span_text,
        "contextual_meaning_ko": plan.contextual_meaning_ko,
        "supporting_evidence": support_quote,
        "correct_marker": generated.answer,
        "correct_choice": correct_choice,
    }


def _build_vocab_context(
    plan: VocabPlan | ContextualVocabChoicePlan | UnderlinedVocabPlan,
    generated: GeneratedQuestion,
    *,
    design: object | None = None,
    prepared_source: PreparedSource | None = None,
    question_subtype_key: str | None = None,
) -> dict[str, str]:
    sentence_map = (
        {unit.id: unit.text for unit in prepared_source.sentence_units}
        if prepared_source is not None
        else {}
    )
    if isinstance(plan, VocabPlan):
        if prepared_source is None:
            raise ValueError("PreparedSource is required for legacy VocabPlan explanation context.")
        inventory = {span.id: span for span in vocab_target_inventory(prepared_source)}
        ordered_spans = sorted(
            [inventory[span_id] for span_id in plan.target_span_ids if span_id in inventory],
            key=lambda span: (span.char_start, span.char_end),
        )
        ordered_ids = [span.id for span in ordered_spans]
        corrupted_span = inventory[plan.corrupted_span_id]
        correct_marker = MARKER_CHOICES[ordered_ids.index(plan.corrupted_span_id)]
        return {
            "subtype": "contextual_error",
            "original_word": corrupted_span.text,
            "corrupted_word": plan.corrupted_word,
            "source_sentence": sentence_map.get(corrupted_span.sentence_unit_id or "", ""),
            "supporting_evidence": plan.supporting_evidence,
            "correction_basis_ko": plan.correction_basis_ko,
            "correct_marker": correct_marker,
        }

    if isinstance(plan, ContextualVocabChoicePlan):
        subtype_key = question_subtype_key or "contextual_vocab_choice_5"
        if isinstance(design, VocabChoiceDesign) and design.selected_span_id == plan.selected_span_id:
            selected_span_text = design.selected_span_text
        else:
            if prepared_source is None:
                raise ValueError("PreparedSource is required for contextual vocab explanation fallback.")
            inventory = {span.id: span for span in vocab_choice_inventory(prepared_source, subtype_key)}
            selected_span_text = inventory[plan.selected_span_id].text
        choice_index = MARKER_CHOICES.index(generated.answer)
        correct_choice = generated.choices[choice_index] if generated.choices else plan.correct_choice
        return {
            "subtype": plan.subtype,
            "question_subtype_key": subtype_key,
            "selected_span_text": selected_span_text,
            "original_word": selected_span_text,
            "correct_choice": correct_choice,
            "source_sentence": "",
            "supporting_evidence": plan.supporting_evidence,
            "correct_marker": generated.answer,
            "contextual_meaning_ko": plan.contextual_meaning_ko,
        }

    if prepared_source is not None:
        span_map = {span.id: span for span in prepared_source.span_units}
        ordered_spans = sorted(
            [span_map[span_id] for span_id in plan.target_span_ids if span_id in span_map],
            key=lambda span: (span.char_start, span.char_end),
        )
        ordered_ids = [span.id for span in ordered_spans]
        answer_span_text = span_map[plan.answer_span_id].text
    elif isinstance(design, UnderlinedVocabDesign):
        ordered_ids = list(design.target_span_ids)
        answer_span_text = dict(zip(design.target_span_ids, design.target_span_texts, strict=False))[plan.answer_span_id]
    else:
        raise ValueError("PreparedSource is required for underlined vocab explanation fallback.")
    answer_marker = MARKER_CHOICES[ordered_ids.index(plan.answer_span_id)]
    replacement_by_span_id = plan.corrupted_replacement_map()
    wrong_markers = [
        f"{marker}의 '{replacement_by_span_id[span_id]}'"
        for marker, span_id in zip(MARKER_CHOICES, ordered_ids)
        if span_id in replacement_by_span_id
    ]
    return {
        "subtype": plan.subtype,
        "question_subtype_key": question_subtype_key or generated.QuestionSubtypeKey or "",
        "answer_span_text": answer_span_text,
        "supporting_evidence": plan.supporting_evidence,
        "correct_marker": answer_marker,
        "selection_basis_ko": plan.selection_basis_ko,
        "wrong_markers": ", ".join(wrong_markers),
    }


def _build_grammar_context(
    prepared_source: PreparedSource,
    plan: GrammarPlan,
    *,
    design: object | None = None,
) -> dict[str, str]:
    sentence_map = {unit.id: unit.text for unit in prepared_source.sentence_units}
    if isinstance(design, GrammarDesign):
        ordered_ids = list(design.target_span_ids)
        corrupted_span_text = dict(zip(design.target_span_ids, design.target_span_texts, strict=False))[plan.corrupted_span_id]
    else:
        inventory = {span.id: span for span in grammar_target_inventory(prepared_source)}
        ordered_spans = sorted(
            [inventory[span_id] for span_id in plan.target_span_ids if span_id in inventory],
            key=lambda span: (span.char_start, span.char_end),
        )
        ordered_ids = [span.id for span in ordered_spans]
        corrupted_span_text = inventory[plan.corrupted_span_id].text
    correct_marker = MARKER_CHOICES[ordered_ids.index(plan.corrupted_span_id)]
    original_word = corrupted_span_text
    return {
        "original_word": original_word,
        "corrupted_word": plan.corrupted_word,
        "grammar_cue_ko": _grammar_structure_cue(corrupted_span_text, []),
        "correction_basis_ko": plan.correction_basis_ko,
        "source_sentence": "",
        "supporting_evidence": plan.supporting_evidence,
        "correct_marker": correct_marker,
    }


def _write_sentence_insertion_explanation(context: dict[str, str | None]) -> str:
    before_text = context["before_text"]
    after_text = context["after_text"]
    correct_marker = context["correct_marker"]

    if before_text and after_text:
        return (
            f"앞의 {_sentence_snippet(before_text)} 뒤에서 내용이 한 번 더 이어져야 하고, "
            f"그다음에는 {_sentence_snippet(after_text)}로 넘어가야 흐름이 자연스럽습니다. "
            f"즉, 주어진 문장이 앞문장의 내용을 받아 뒤문장으로 연결하는 다리 역할을 하므로 "
            f"따라서 {correct_marker} 위치에 들어가는 것이 가장 적절합니다."
        )

    if before_text:
        return (
            f"앞의 {_sentence_snippet(before_text)} 다음에 주어진 문장이 덧붙어야 "
            f"핵심 내용이 자연스럽게 이어집니다. "
            f"따라서 {correct_marker} 위치에 들어가는 것이 가장 적절합니다."
        )

    if after_text:
        return (
            f"주어진 문장이 먼저 제시된 뒤에 {_sentence_snippet(after_text)}로 이어져야 "
            f"문맥이 자연스럽게 연결됩니다. "
            f"따라서 {correct_marker} 위치에 들어가는 것이 가장 적절합니다."
        )

    return f"주어진 문장은 글의 전체 흐름을 보완하는 역할을 하므로, {correct_marker} 위치에 들어가는 것이 가장 적절합니다."


def _write_paragraph_ordering_explanation(context: dict[str, Any]) -> str:
    first_label, second_label, third_label = context["correct_sequence"]
    first_edge, second_edge, third_edge = context["edges"]

    return (
        f"{first_edge['from_label']}의 {_sentence_snippet(first_edge['from_tail'])} 뒤에는 "
        f"({first_label})의 {_sentence_snippet(first_edge['to_head'])}가 이어져야 합니다. "
        f"이어 ({first_label})의 {_sentence_snippet(second_edge['from_tail'])} 다음에는 "
        f"({second_label})의 {_sentence_snippet(second_edge['to_head'])}가 와야 하고, "
        f"마지막으로 ({second_label})의 {_sentence_snippet(third_edge['from_tail'])} 뒤에 "
        f"({third_label})의 {_sentence_snippet(third_edge['to_head'])}가 놓일 때 전개가 완성됩니다. "
        f"순서는 ({first_label})-({second_label})-({third_label})가 가장 적절합니다."
    )


def _write_mood_atmosphere_explanation(context: dict[str, str | None]) -> str:
    subtype = context.get("subtype") or "emotion_shift"
    target_holder = context["target_holder"] or "중심 인물"
    initial_emotion = context["initial_emotion"] or "initial"
    final_emotion = context["final_emotion"] or "final"
    state_emotion = context.get("state_emotion") or "state"
    atmosphere_label = context.get("atmosphere_label") or "atmosphere"
    initial_evidence = context["initial_evidence"] or ""
    final_evidence = context["final_evidence"] or ""
    shift_trigger = context["shift_trigger"]
    state_evidence = context.get("state_evidence") or ""
    atmosphere_evidence = context.get("atmosphere_evidence") or ""
    correct_marker = context["correct_marker"] or "①"
    correct_choice = context["correct_choice"] or f"{initial_emotion} -> {final_emotion}"

    if subtype == "emotion_state":
        return (
            f"글에서 {target_holder}의 중심 심경은 '{state_evidence}'에서 드러나듯 {state_emotion}한 상태입니다. "
            f"이 정서가 passage 전체에서 가장 안정적으로 유지되므로 정답은 {correct_marker} {correct_choice}입니다."
        )

    if subtype == "atmosphere":
        return (
            f"글 전체 분위기는 '{atmosphere_evidence}'에서 드러나듯 {atmosphere_label}한 쪽으로 읽는 것이 가장 자연스럽습니다. "
            f"한 인물의 순간 감정보다 passage 전반의 tone을 묻는 문항이므로 정답은 {correct_marker} {correct_choice}입니다."
        )

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


def _write_fill_in_the_blank_explanation(context: dict[str, str]) -> str:
    idea = _clean_teacher_note(context["contextual_meaning_ko"]) or "글의 핵심 내용을 복원하는 설명"
    return (
        f"빈칸 앞뒤를 보면 '{context['supporting_evidence']}'라는 흐름이 핵심 단서입니다. "
        f"따라서 이 자리에는 \"{idea}\"에 해당하는 내용이 들어가야 하므로 "
        f"정답은 {context['correct_marker']} {context['correct_choice']}입니다."
    )


def _write_vocab_explanation(context: dict[str, str]) -> str:
    if context.get("subtype") in {
        "contextual_choice",
        "contextual_best_paraphrase_choice",
        "contextual_phrase_choice",
    }:
        meaning = _prefer_teacher_note(
            context.get("contextual_meaning_ko"),
            "앞뒤 문맥과 맞는 뜻",
        )
        source_wording = context["selected_span_text"]
        correct_choice = context["correct_choice"]
        subtype = context.get("subtype")
        if subtype == "contextual_best_paraphrase_choice":
            return _polish_teacher_explanation(
                (
                    f"문맥상 이 자리는 \"{meaning}\"을 가장 가깝게 바꿔 말한 표현이 와야 합니다. "
                    f"특히 '{context['supporting_evidence']}'라는 단서가 그 해석을 뒷받침합니다. "
                    f"원문의 '{source_wording}'를 그대로 복원하는 문제가 아니라, "
                    f"정답인 '{correct_choice}'가 그 의미를 가장 정확한 문맥상 바꿔쓰기로 살립니다. "
                    "다른 선택지들은 의미 방향이나 범위가 어긋나므로 "
                    f"정답은 {context['correct_marker']} {context['correct_choice']}입니다."
                )
            )
        if subtype == "contextual_phrase_choice":
            return _polish_teacher_explanation(
                (
                    f"문맥상 이 자리는 한 단어가 아니라 \"{meaning}\"에 해당하는 어구 단위가 들어가야 합니다. "
                    f"특히 '{context['supporting_evidence']}'라는 단서가 그 어구 의미를 뒷받침합니다. "
                    f"정답인 '{correct_choice}'가 그 의미와 어구 단위를 함께 가장 자연스럽게 맞추고, "
                    "다른 선택지들은 의미나 어구 결합이 어긋납니다. "
                    f"따라서 정답은 {context['correct_marker']} {context['correct_choice']}입니다."
                )
            )
        source_note = (
            f"원문의 '{source_wording}'도 같은 자리에 놓일 수 있는 표현이지만, "
            if correct_choice != source_wording
            else ""
        )
        return _polish_teacher_explanation(
            (
                f"문맥상 이 자리는 \"{meaning}\"에 해당하는 표현이 와야 합니다. "
                f"특히 '{context['supporting_evidence']}'라는 단서가 그 판단의 근거가 됩니다. "
                f"{source_note}정답인 '{correct_choice}'가 그 의미를 가장 정확하게 살립니다. "
                "다른 선택지들은 문맥의 방향이나 범위, 평가를 어긋나게 만듭니다. "
                f"따라서 정답은 {context['correct_marker']} {context['correct_choice']}입니다."
            )
        )
    if context.get("subtype") in {
        "contextual_correct_among_4_corrupted",
        "contextual_error_1_among_5",
        "contextual_error_1_among_5_polarity_scope",
        "contextual_error_1_among_5_collocation",
        "contextual_correct_among_3_corrupted",
    }:
        basis = _prefer_teacher_note(
            context.get("selection_basis_ko"),
            "이 자리의 문맥을 가장 자연스럽게 유지하는 표현",
        )
        if context["subtype"] == "contextual_error_1_among_5_polarity_scope":
            return _polish_teacher_explanation(
                (
                    f"문맥상 {basis}. "
                    f"특히 '{context['supporting_evidence']}'라는 단서가 원래 표현의 방향과 범위를 고정합니다. "
                    f"따라서 {context['correct_marker']}의 표현은 방향, 정도, 또는 적용 범위를 어긋나게 만들어 문맥상 틀립니다."
                )
            )
        if context["subtype"] == "contextual_error_1_among_5_collocation":
            return _polish_teacher_explanation(
                (
                    f"문맥상 {basis}. "
                    f"특히 '{context['supporting_evidence']}'라는 단서가 이 자리의 자연스러운 어휘 결합을 보여 줍니다. "
                    f"따라서 {context['correct_marker']}의 표현은 문법만 그럴듯할 뿐, 이 자리에서 자연스럽게 결합하는 어휘 선택이 아닙니다."
                )
            )
        if context["subtype"] == "contextual_error_1_among_5":
            return _polish_teacher_explanation(
                (
                    f"문맥상 {basis}. "
                    f"특히 '{context['supporting_evidence']}'라는 단서가 그 기준을 분명히 보여 줍니다. "
                    f"따라서 {context['correct_marker']}의 표현만 문맥에 어긋나고, "
                    "나머지 밑줄 어휘들은 글의 기본 의미를 유지합니다."
                )
            )
        return _polish_teacher_explanation(
            (
                f"문맥상 {basis}. "
                f"특히 '{context['supporting_evidence']}'라는 단서가 정답 표현의 의미를 뒷받침합니다. "
                f"따라서 {context['correct_marker']}의 '{context['answer_span_text']}'만 문맥을 유지하고, "
                f"{context['wrong_markers']}는 각각 의미의 방향이나 범위를 어긋나게 만듭니다."
            )
        )
    basis = _prefer_teacher_note(
        context.get("correction_basis_ko"),
        "이 자리에는 앞뒤 내용과 맞는 뜻의 낱말이 와야 합니다",
    )
    return _polish_teacher_explanation(
        (
            f"문맥상 {basis}. "
            f"특히 '{context['supporting_evidence']}'라는 단서가 원래 표현의 의미를 뒷받침합니다. "
            f"따라서 {context['correct_marker']}의 '{context['corrupted_word']}'는 문맥에 맞지 않고, "
            f"원래 '{context['original_word']}'가 와야 합니다."
        )
    )


def _write_grammar_explanation(context: dict[str, str]) -> str:
    basis = _prefer_teacher_note(
        context.get("correction_basis_ko"),
        context["grammar_cue_ko"],
    )
    return (
        f"'{context['supporting_evidence']}'라는 구조를 보면 {basis}. "
        f"따라서 {context['correct_marker']}의 '{context['corrupted_word']}'는 맞지 않고 "
        f"원래 '{context['original_word']}'가 와야 합니다."
    )


def _clean_teacher_note(note: str | None) -> str:
    if note is None:
        return ""
    cleaned = " ".join(note.split()).strip()
    cleaned = cleaned.rstrip(". ")
    cleaned = re.sub(r"(이 자리에는)(?:\s+\1)+", r"\1", cleaned)
    cleaned = re.sub(r"(이 자리는)(?:\s+\1)+", r"\1", cleaned)
    for prefix in ("이 자리에는 ", "이 자리는 ", "빈칸에는 ", "빈칸은 "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].lstrip()
    if cleaned.endswith("다는 의미"):
        cleaned = cleaned[: -len("는 의미")].rstrip()
    for suffix in ("라는 의미", "이라는 의미"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].rstrip()
    return cleaned


def _polish_teacher_explanation(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    cleaned = re.sub(r"(이 자리에는)(?:\s+\1)+", r"\1", cleaned)
    cleaned = re.sub(r"(이 자리는)(?:\s+\1)+", r"\1", cleaned)
    cleaned = cleaned.replace("이 자리에는 이 자리는", "이 자리는")
    cleaned = re.sub(r"([\"'])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([\"'])", r"\1", cleaned)
    return cleaned


def _prefer_teacher_note(note: str | None, fallback: str) -> str:
    cleaned = _clean_teacher_note(note)
    if not cleaned:
        return fallback

    lowered = cleaned.lower()
    if any(fragment in lowered for fragment in ("자유서술", "schema", "renderer", "selected_", "절대 나오면 안 되는")):
        return fallback
    if cleaned in {
        "문맥상 맞지 않는 단어입니다",
        "문맥상 맞지 않는 형태입니다",
        "문맥상 맞지 않습니다",
        "글의 흐름과 맞지 않습니다",
    }:
        return fallback
    return cleaned


def _sentence_snippet(text: str, *, max_words: int = 12) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def _grammar_structure_cue(original_word: str, heuristic_tags: list[str]) -> str:
    lowered = original_word.strip().lower()
    tag_set = set(heuristic_tags)

    if "to_infinitive_context" in tag_set:
        return "to 뒤에는 동사원형이 와야 합니다"
    if "modal_context" in tag_set:
        return "조동사 뒤에는 동사원형이 와야 합니다"
    if "be_context" in tag_set and lowered.endswith("ing"):
        return "be동사 뒤에서는 진행형을 이루는 현재분사가 와야 합니다"
    if lowered in {"been", "gone", "known", "shown", "taken", "written"} or lowered.endswith("en"):
        return "주변 구조상 이 자리에는 과거분사 형태가 유지되어야 합니다"
    if lowered.endswith("ed"):
        return "주변 구조상 이 자리에는 과거형 또는 과거분사형이 유지되어야 합니다"
    if lowered.endswith("s"):
        return "주어와 시제에 맞는 동사 형태가 유지되어야 합니다"
    return "주변 문장 구조가 요구하는 동사 형태가 유지되어야 합니다"
