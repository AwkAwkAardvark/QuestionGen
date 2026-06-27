from __future__ import annotations

from typing import Any, Callable

from .paragraph_ordering import paragraph_candidate_is_stable, paragraph_ordering_candidates
from .question_types import QuestionTypeSpec
from .renderers import rendered_gap_positions
from .schemas import (
    BaseModel,
    ContextualVocabChoiceDraft,
    ContextualVocabChoicePlan,
    FillInTheBlankDesign,
    FillInTheBlankDraft,
    FillInTheBlankPlan,
    GrammarDesign,
    GrammarDraft,
    GrammarPlan,
    MoodAtmosphereDesign,
    MoodAtmospherePlan,
    ParagraphOrderingDesign,
    ParagraphOrderingDraft,
    ParagraphOrderingPlan,
    PreparedSource,
    QuestionDesign,
    QuestionState,
    SentenceInsertionDesign,
    SentenceInsertionDraft,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningDesign,
    UnderlinedPhraseMeaningDraft,
    UnderlinedPhraseMeaningPlan,
    UnderlinedVocabDesign,
    UnderlinedVocabDraft,
    UnderlinedVocabPlan,
    VocabChoiceDesign,
    coerce_model,
)
from .targeting import (
    allowed_verb_form_variants,
    fill_blank_connective_inventory,
    fill_blank_summary_inventory,
    fill_blank_target_inventory,
    grammar_subtype_inventory,
    vocab_hard_bundle,
    underlined_phrase_inventory,
    vocab_choice_inventory,
    vocab_choice_target_cue_count,
)

DesignBuilder = Callable[[str, PreparedSource, QuestionTypeSpec], QuestionDesign]

_FILL_BLANK_SUBTYPE_BY_KEY = {
    "blank_inference_proposition_5_choices": "proposition_inference",
    "blank_connective_relation_5_choices": "connective_relation",
    "blank_summary_completion_5_choices": "summary_completion",
}
_VOCAB_CHOICE_SUBTYPE_BY_KEY = {
    "contextual_vocab_choice_5": "contextual_choice",
    "contextual_vocab_best_paraphrase_choice_5": "contextual_best_paraphrase_choice",
    "contextual_vocab_phrase_choice_5": "contextual_phrase_choice",
}
_UNDERLINED_VOCAB_SUBTYPE_BY_KEY = {
    "contextual_vocab_correct_among_4_corrupted_5": "contextual_correct_among_4_corrupted",
    "contextual_vocab_error_1_among_5_5": "contextual_error_1_among_5",
    "contextual_vocab_error_1_among_5_polarity_scope_5": "contextual_error_1_among_5_polarity_scope",
    "contextual_vocab_error_1_among_5_collocation_5": "contextual_error_1_among_5_collocation",
    "contextual_vocab_correct_among_3_corrupted_5": "contextual_correct_among_3_corrupted",
}
_GRAMMAR_SUBTYPE_BY_KEY = {
    "grammar_error_verb_form_5": "verb_form",
    "grammar_error_subject_verb_agreement_5": "subject_verb_agreement",
    "grammar_error_finite_nonfinite_5": "finite_nonfinite",
    "grammar_error_participle_voice_5": "participle_voice",
    "grammar_error_relative_clause_5": "relative_clause",
    "grammar_error_noun_clause_introducer_5": "noun_clause_introducer",
    "grammar_error_parallel_structure_5": "parallel_structure",
    "grammar_error_conjunction_preposition_5": "conjunction_preposition",
}


def build_design(state: QuestionState, type_spec: QuestionTypeSpec) -> dict[str, Any]:
    prepared_source = state["prepared_source"]
    if prepared_source is None:
        return {
            "status": "source_error",
            "errors": ["PreparedSource is required before design building."],
        }

    builder = DESIGNERS.get(type_spec.renderer_key)
    if builder is None:
        return {
            "status": "qtype_incompatibility_error",
            "errors": [f"No design builder is registered for {type_spec.renderer_key}."],
        }

    try:
        design = builder(state["source_paragraph"], prepared_source, type_spec)
    except ValueError as exc:
        return {
            "status": "qtype_incompatibility_error",
            "errors": [str(exc)],
        }

    return {
        "design": design,
        "status": "source_passed",
        "errors": [],
    }


def hydrate_plan_from_draft(
    *,
    design: BaseModel | None,
    draft: BaseModel,
    type_spec: QuestionTypeSpec,
) -> BaseModel:
    if type_spec.renderer_key == "sentence_insertion":
        if not isinstance(design, SentenceInsertionDesign) or not isinstance(draft, SentenceInsertionDraft):
            raise TypeError("Sentence insertion hydration requires SentenceInsertionDesign and SentenceInsertionDraft.")
        return SentenceInsertionPlan(
            target_unit_ids=[design.target_unit_id],
            selected_gap_ids=list(design.selected_gap_ids),
            correct_gap_id=draft.correct_gap_id,
            explanation=draft.explanation,
        )

    if type_spec.renderer_key == "paragraph_ordering":
        if not isinstance(design, ParagraphOrderingDesign) or not isinstance(draft, ParagraphOrderingDraft):
            raise TypeError("Paragraph ordering hydration requires ParagraphOrderingDesign and ParagraphOrderingDraft.")
        return ParagraphOrderingPlan(
            intro_unit_ids=list(design.intro_unit_ids),
            continuation_blocks=[list(block) for block in design.continuation_blocks],
            explanation=draft.explanation,
        )

    if type_spec.renderer_key == "underlined_phrase_meaning":
        if not isinstance(design, UnderlinedPhraseMeaningDesign) or not isinstance(draft, UnderlinedPhraseMeaningDraft):
            raise TypeError(
                "Underlined phrase meaning hydration requires UnderlinedPhraseMeaningDesign and UnderlinedPhraseMeaningDraft."
            )
        return UnderlinedPhraseMeaningPlan(
            selected_span_id=design.selected_span_id,
            selected_span_text=design.selected_span_text,
            paraphrase_choices_ko=list(draft.paraphrase_choices_ko),
            correct_choice=draft.correct_choice,
            surface_meaning=draft.surface_meaning,
            contextual_meaning=draft.contextual_meaning,
            supporting_evidence=draft.supporting_evidence,
            explanation=draft.explanation,
        )

    if type_spec.renderer_key == "fill_in_the_blank":
        if not isinstance(design, FillInTheBlankDesign) or not isinstance(draft, FillInTheBlankDraft):
            raise TypeError("Fill-in-the-blank hydration requires FillInTheBlankDesign and FillInTheBlankDraft.")
        return FillInTheBlankPlan(
            subtype=design.subtype,
            selected_span_id=design.selected_span_id,
            selected_span_text=design.selected_span_text,
            completion_choices=list(draft.completion_choices),
            correct_choice=draft.correct_choice,
            contextual_meaning_ko=draft.contextual_meaning_ko,
            supporting_evidence=draft.supporting_evidence,
            explanation=draft.explanation,
        )

    if type_spec.renderer_key == "vocab":
        if isinstance(design, VocabChoiceDesign) and isinstance(draft, ContextualVocabChoiceDraft):
            return ContextualVocabChoicePlan(
                subtype=design.subtype,
                selected_span_id=design.selected_span_id,
                selected_span_text=design.selected_span_text,
                choice_words=list(draft.choice_words),
                correct_choice=draft.correct_choice,
                contextual_meaning_ko=draft.contextual_meaning_ko,
                supporting_evidence=draft.supporting_evidence,
                explanation=draft.explanation,
            )
        if isinstance(design, UnderlinedVocabDesign) and isinstance(draft, UnderlinedVocabDraft):
            return UnderlinedVocabPlan(
                subtype=design.subtype,
                target_span_ids=list(design.target_span_ids),
                target_span_texts=list(design.target_span_texts),
                corrupted_replacements=list(draft.corrupted_replacements),
                answer_span_id=draft.answer_span_id,
                selection_basis_ko=draft.selection_basis_ko,
                supporting_evidence=draft.supporting_evidence,
                explanation=draft.explanation,
            )
        raise TypeError("Vocab hydration requires a matching vocab design and draft schema.")

    if type_spec.renderer_key == "grammar":
        if not isinstance(design, GrammarDesign) or not isinstance(draft, GrammarDraft):
            raise TypeError("Grammar hydration requires GrammarDesign and GrammarDraft.")
        return GrammarPlan(
            subtype=design.subtype,
            target_span_ids=list(design.target_span_ids),
            target_span_texts=list(design.target_span_texts),
            corrupted_span_id=design.corrupted_span_id,
            corrupted_word=draft.corrupted_word,
            correction_basis_ko=draft.correction_basis_ko,
            supporting_evidence=draft.supporting_evidence,
            explanation=draft.explanation,
        )

    return coerce_model(draft, type_spec.plan_schema)


def build_mood_atmosphere_design(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> QuestionDesign:
    sentence_inventory = "\n".join(f"- {unit.id}: {unit.text}" for unit in prepared_source.sentence_units)
    return MoodAtmosphereDesign(
        family_key=type_spec.renderer_key,
        subtype_key=type_spec.subtype_key,
        prompt_payload={
            "source_paragraph": source_paragraph,
            "sentence_inventory": sentence_inventory,
        },
    )


def build_sentence_insertion_design(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> QuestionDesign:
    units = prepared_source.sentence_units
    candidate_units = list(units[2:-1]) + list(units[1:2])
    for unit in candidate_units:
        rendered_positions = rendered_gap_positions(prepared_source, unit.id)
        unique_gap_ids: list[str] = []
        seen_positions: set[tuple[str | None, str | None]] = set()
        for gap in prepared_source.gap_units:
            rendered_position = rendered_positions[gap.id]
            if rendered_position in seen_positions:
                continue
            seen_positions.add(rendered_position)
            unique_gap_ids.append(gap.id)
        if len(unique_gap_ids) < 5:
            continue
        correct_gap_id = f"G{unit.index}"
        if correct_gap_id not in unique_gap_ids:
            continue
        correct_index = unique_gap_ids.index(correct_gap_id)
        start = max(0, min(correct_index - 2, len(unique_gap_ids) - 5))
        selected_gap_ids = unique_gap_ids[start : start + 5]
        prompt_payload = {
            "source_paragraph": source_paragraph,
            "target_unit_id": unit.id,
            "target_text": unit.text,
            "left_context": units[unit.index - 1].text,
            "right_context": units[unit.index + 1].text,
            "gap_bundle": "\n".join(
                f"- {gap_id}: between {_gap_edge_label(rendered_positions[gap_id][0])} and {_gap_edge_label(rendered_positions[gap_id][1])}"
                for gap_id in selected_gap_ids
            ),
        }
        return SentenceInsertionDesign(
            family_key=type_spec.renderer_key,
            subtype_key=type_spec.subtype_key,
            target_unit_id=unit.id,
            selected_gap_ids=selected_gap_ids,
            correct_gap_id=correct_gap_id,
            prompt_payload=prompt_payload,
        )

    raise ValueError(
        "Passage does not contain a stable sentence-insertion target with five distinct rendered positions."
    )


def build_paragraph_ordering_design(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> QuestionDesign:
    candidate = next(
        (item for item in paragraph_ordering_candidates(prepared_source) if paragraph_candidate_is_stable(item)),
        None,
    )
    if candidate is None:
        candidate = next(iter(paragraph_ordering_candidates(prepared_source)), None)
    if candidate is None:
        raise ValueError("Passage does not contain a workable paragraph_ordering partition.")

    sentence_map = {unit.id: unit.text for unit in prepared_source.sentence_units}
    intro_text = " ".join(sentence_map[unit_id] for unit_id in candidate.intro_unit_ids)
    continuation_blocks = [list(block) for block in candidate.continuation_blocks]
    edge_lines: list[str] = []
    ordered_segments = [
        ("주어진 글", list(candidate.intro_unit_ids)),
        ("A", continuation_blocks[0]),
        ("B", continuation_blocks[1]),
        ("C", continuation_blocks[2]),
    ]
    for left, right in zip(ordered_segments, ordered_segments[1:]):
        edge_lines.append(
            f"- {left[0]} -> {right[0]}: {sentence_map[left[1][-1]]!r} -> {sentence_map[right[1][0]]!r}"
        )

    return ParagraphOrderingDesign(
        family_key=type_spec.renderer_key,
        subtype_key=type_spec.subtype_key,
        intro_unit_ids=list(candidate.intro_unit_ids),
        continuation_blocks=continuation_blocks,
        prompt_payload={
            "source_paragraph": source_paragraph,
            "intro_text": intro_text,
            "continuation_blocks": "\n".join(
                f"- {label}: {' '.join(sentence_map[unit_id] for unit_id in block)}"
                for label, block in zip(("A", "B", "C"), continuation_blocks)
            ),
            "edge_lines": "\n".join(edge_lines),
        },
    )


def build_underlined_phrase_meaning_design(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> QuestionDesign:
    spans = underlined_phrase_inventory(prepared_source)
    if not spans:
        raise ValueError("Passage has no suitable contextual phrase candidate for underlined_phrase_meaning.")
    span = spans[0]
    return UnderlinedPhraseMeaningDesign(
        family_key=type_spec.renderer_key,
        subtype_key=type_spec.subtype_key,
        selected_span_id=span.id,
        selected_span_text=span.text,
        prompt_payload={
            "source_paragraph": source_paragraph,
            "selected_span_id": span.id,
            "selected_span_text": span.text,
            "selected_span_line": (
                f"- rank 1: {span.id}; score={span.priority_score}; text={span.text!r}; "
                f"tags={','.join(span.heuristic_tags) or 'none'}; context={_span_context(span)}"
            ),
            "support_context": _span_context(span),
            "tags": ", ".join(span.heuristic_tags) or "none",
        },
    )


def build_fill_in_the_blank_design(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> QuestionDesign:
    if type_spec.subtype_key == "blank_connective_relation_5_choices":
        inventory = fill_blank_connective_inventory(prepared_source)
    elif type_spec.subtype_key == "blank_summary_completion_5_choices":
        inventory = fill_blank_summary_inventory(prepared_source)
    else:
        inventory = fill_blank_target_inventory(prepared_source)
    if not inventory:
        raise ValueError(f"Passage has no suitable contextual span for {type_spec.subtype_key}.")
    span = inventory[0]
    return FillInTheBlankDesign(
        family_key=type_spec.renderer_key,
        subtype_key=type_spec.subtype_key,
        subtype=_FILL_BLANK_SUBTYPE_BY_KEY[type_spec.subtype_key],
        selected_span_id=span.id,
        selected_span_text=span.text,
        prompt_payload={
            "source_paragraph": source_paragraph,
            "selected_span_id": span.id,
            "selected_span_text": span.text,
            "selected_span_line": (
                f"- rank 1: {span.id}; score={span.priority_score}; text={span.text!r}; "
                f"tags={','.join(span.heuristic_tags) or 'none'}; context={_span_context(span)}"
            ),
            "support_context": _span_context(span),
            "tags": ", ".join(span.heuristic_tags) or "none",
        },
    )


def build_vocab_design(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> QuestionDesign:
    if type_spec.plan_schema is ContextualVocabChoicePlan:
        inventory = vocab_choice_inventory(prepared_source, type_spec.subtype_key)
        if not inventory:
            if type_spec.subtype_key == "contextual_vocab_phrase_choice_5":
                raise ValueError(
                    "Passage does not contain a workable phrase-frame or collocational vocab target for contextual_vocab_phrase_choice_5."
                )
            raise ValueError(f"Passage does not contain a workable lexical-slot vocab target for {type_spec.subtype_key}.")
        span = inventory[0]
        locked_target_label = "Locked phrase-frame target"
        if type_spec.subtype_key == "contextual_vocab_best_paraphrase_choice_5":
            locked_target_label = "Locked content target"
        elif type_spec.subtype_key == "contextual_vocab_choice_5":
            locked_target_label = "Locked target"
        return VocabChoiceDesign(
            family_key=type_spec.renderer_key,
            subtype_key=type_spec.subtype_key,
            subtype=_VOCAB_CHOICE_SUBTYPE_BY_KEY[type_spec.subtype_key],
            selected_span_id=span.id,
            selected_span_text=span.text,
            prompt_payload={
                "source_paragraph": source_paragraph,
                "selected_span_id": span.id,
                "selected_span_text": span.text,
                "cue_count": str(vocab_choice_target_cue_count(span)),
                "selected_span_line": (
                    f"- rank 1: {span.id}; score={span.priority_score}; cues={vocab_choice_target_cue_count(span)}; "
                    f"text={span.text!r}; tags={','.join(span.heuristic_tags) or 'none'}; context={_span_context(span)}"
                ),
                "locked_target_label": locked_target_label,
                "support_context": _span_context(span),
                "tags": ", ".join(span.heuristic_tags) or "none",
            },
        )

    bundle = vocab_hard_bundle(prepared_source, type_spec.subtype_key)
    if bundle is None:
        if type_spec.subtype_key == "contextual_vocab_error_1_among_5_polarity_scope_5":
            raise ValueError(
                "Passage does not contain a five-target vocab bundle with a polarity/scope-eligible corruption anchor."
            )
        if type_spec.subtype_key == "contextual_vocab_error_1_among_5_collocation_5":
            raise ValueError(
                "Passage does not contain a five-target vocab bundle with a collocation-eligible corruption anchor."
            )
        if type_spec.subtype_key == "contextual_vocab_correct_among_3_corrupted_5":
            raise ValueError(
                "Passage does not contain a clear unique-survivor vocab bundle for contextual_vocab_correct_among_3_corrupted_5."
            )
        if type_spec.subtype_key == "contextual_vocab_correct_among_4_corrupted_5":
            raise ValueError(
                "Passage does not contain a stable five-target vocab bundle with four corruption-friendly distractors for contextual_vocab_correct_among_4_corrupted_5."
            )
        if type_spec.subtype_key == "contextual_vocab_error_1_among_5_5":
            raise ValueError(f"Passage does not contain a stable five-target vocab bundle for {type_spec.subtype_key}.")
        raise ValueError(f"Passage does not contain five workable lexical-slot vocab targets for {type_spec.subtype_key}.")
    selected_spans = list(bundle.selected_spans)
    selected_by_id = {span.id: span for span in selected_spans}
    eligible_lines = "\n".join(
        (
            f"- {span_id}: {selected_by_id[span_id].text!r}; cues={vocab_choice_target_cue_count(selected_by_id[span_id])}; "
            f"context={_span_context(selected_by_id[span_id])}"
        )
        for span_id in bundle.corruptible_span_ids
        if span_id in selected_by_id
    )
    return UnderlinedVocabDesign(
        family_key=type_spec.renderer_key,
        subtype_key=type_spec.subtype_key,
        subtype=_UNDERLINED_VOCAB_SUBTYPE_BY_KEY[type_spec.subtype_key],
        target_span_ids=[span.id for span in selected_spans],
        target_span_texts=[span.text for span in selected_spans],
        corruptible_span_ids=list(bundle.corruptible_span_ids),
        answer_span_id=bundle.answer_span_id,
        untouched_distractor_span_id=bundle.untouched_distractor_span_id,
        prompt_payload={
            "source_paragraph": source_paragraph,
            "target_bundle": "\n".join(
                (
                    f"- rank {rank}: {span.id}; score={span.priority_score}; cues={vocab_choice_target_cue_count(span)}; "
                    f"text={span.text!r}; context={_span_context(span)}"
                )
                for rank, span in enumerate(selected_spans, start=1)
            ),
            "corruptible_subset": eligible_lines,
            "answer_span_id": bundle.answer_span_id or "",
            "untouched_distractor_span_id": bundle.untouched_distractor_span_id or "",
        },
    )


def build_grammar_design(
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> QuestionDesign:
    inventory = grammar_subtype_inventory(prepared_source, type_spec.subtype_key)
    if len(inventory) < 5:
        raise ValueError(f"Passage does not contain five workable grammar targets for {type_spec.subtype_key}.")
    selected_spans = inventory[:5]
    corrupted_span = selected_spans[1]
    allowed_variants = sorted(allowed_verb_form_variants(corrupted_span.text) - {corrupted_span.text.lower()})
    return GrammarDesign(
        family_key=type_spec.renderer_key,
        subtype_key=type_spec.subtype_key,
        subtype=_GRAMMAR_SUBTYPE_BY_KEY[type_spec.subtype_key],
        target_span_ids=[span.id for span in selected_spans],
        target_span_texts=[span.text for span in selected_spans],
        corrupted_span_id=corrupted_span.id,
        prompt_payload={
            "source_paragraph": source_paragraph,
            "target_bundle": "\n".join(
                (
                    f"- rank {rank}: {span.id}; score={span.priority_score}; text={span.text!r}; "
                    f"context={_span_context(span)}"
                )
                for rank, span in enumerate(selected_spans, start=1)
            ),
            "corrupted_target_id": corrupted_span.id,
            "corrupted_target_text": corrupted_span.text,
            "allowed_variants": ", ".join(allowed_variants) or "none",
        },
    )


DESIGNERS: dict[str, DesignBuilder] = {
    "sentence_insertion": build_sentence_insertion_design,
    "paragraph_ordering": build_paragraph_ordering_design,
    "mood_atmosphere": build_mood_atmosphere_design,
    "underlined_phrase_meaning": build_underlined_phrase_meaning_design,
    "fill_in_the_blank": build_fill_in_the_blank_design,
    "vocab": build_vocab_design,
    "grammar": build_grammar_design,
}


def _gap_edge_label(unit_id: str | None) -> str:
    if unit_id is None:
        return "START/END"
    return unit_id


def _span_context(span: Any) -> str:
    before = (span.context_before or "").strip()
    after = (span.context_after or "").strip()
    return f"{before} <<{span.text}>> {after}".strip()
