from __future__ import annotations

import re

from .paragraph_ordering import (
    paragraph_block_start_hints,
    paragraph_boundary_hints,
    paragraph_candidate_is_stable,
    paragraph_ordering_candidates,
)
from .parsers import content_tokens, normalize_text
from .question_types import QuestionTypeSpec
from .schemas import (
    FillInTheBlankDesign,
    GrammarDesign,
    MoodAtmosphereDesign,
    ParagraphOrderingDesign,
    PreparedSource,
    SentenceInsertionDesign,
    UnderlinedPhraseMeaningDesign,
    UnderlinedVocabDesign,
    UnderlinedVocabPlan,
    VocabChoiceDesign,
    VocabPlan,
)
from .targeting import (
    allowed_verb_form_variants,
    fill_blank_connective_inventory,
    fill_blank_summary_inventory,
    fill_blank_target_inventory,
    grammar_subtype_inventory,
    grammar_target_inventory,
    span_crosses_punctuation,
    span_shape_label,
    underlined_phrase_inventory,
    vocab_hard_candidate_inventory,
    vocab_choice_inventory,
    vocab_choice_target_cue_count,
    vocab_target_inventory,
    vocab_target_is_antonym_invertible,
)

_TRANSITION_STARTERS = {
    "accordingly",
    "because",
    "but",
    "finally",
    "first",
    "however",
    "instead",
    "meanwhile",
    "moreover",
    "next",
    "so",
    "therefore",
    "thus",
}
_REFERENTIAL_CUES = {
    "another",
    "he",
    "it",
    "its",
    "she",
    "such",
    "that",
    "them",
    "their",
    "these",
    "they",
    "this",
    "those",
}

def build_sentence_insertion_prompt(
    *,
    design: SentenceInsertionDesign | None = None,
    source_paragraph: str | None = None,
    prepared_source: PreparedSource | None = None,
    type_spec: QuestionTypeSpec,
) -> str:
    if design is None:
        if source_paragraph is None or prepared_source is None:
            raise TypeError("build_sentence_insertion_prompt requires either design or source_paragraph plus prepared_source.")
        from .designers import build_sentence_insertion_design

        design = build_sentence_insertion_design(source_paragraph, prepared_source, type_spec)
    payload = design.prompt_payload
    return f"""
You are planning an English exam sentence insertion question.

Return only structured data matching the required schema.

Question type:
- Key: sentence_insertion
- Label: {type_spec.family_label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

Locked target sentence:
- {payload["target_unit_id"]}: {payload["target_text"]!r}

Left and right evidence:
- left_context={payload["left_context"]!r}
- right_context={payload["right_context"]!r}

Locked five-gap bundle:
{payload["gap_bundle"]}

Selection reminders:
- The target sentence and five gap options are already locked by the deterministic design stage.
- Do not search for a new target sentence or a new gap bundle.
- Choose `correct_gap_id` only from the locked five-gap bundle above.
""".strip()


def build_sentence_insertion_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- The deterministic design stage already locked the target sentence and the five gap options.
- Do not search for a new target sentence or modify the gap bundle.
- `correct_gap_id` must be exactly one of the locked gap IDs.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that uses the surrounding sentences as evidence rather than the given sentence itself, internal IDs, gap labels, schema field names, or renderer mechanics.
- Return only structured data matching the schema.
""".strip()


def build_paragraph_ordering_prompt(
    *,
    design: ParagraphOrderingDesign | None = None,
    source_paragraph: str | None = None,
    prepared_source: PreparedSource | None = None,
    type_spec: QuestionTypeSpec,
) -> str:
    if design is None:
        if source_paragraph is None or prepared_source is None:
            raise TypeError("build_paragraph_ordering_prompt requires either design or source_paragraph plus prepared_source.")
        from .designers import build_paragraph_ordering_design

        design = build_paragraph_ordering_design(source_paragraph, prepared_source, type_spec)
    payload = design.prompt_payload
    return f"""
You are planning an English exam paragraph ordering question.

Return only structured data matching the required schema.

Question type:
- Key: paragraph_ordering
- Label: {type_spec.family_label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

Locked intro block:
{payload["intro_text"]}

Locked continuation blocks in logical order:
{payload["continuation_blocks"]}

Adjacency rationale payload:
{payload["edge_lines"]}

Selection reminders:
- The deterministic design stage already locked the intro block and the three continuation blocks.
- Do not search for a new partition.
- Use the locked block sequence above and explain why that order is forced.
""".strip()


def build_paragraph_ordering_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- The deterministic design stage already locked the intro block and continuation blocks.
- Do not rebuild the partition.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that explains why one block follows the previous block rather than using internal sentence IDs, block inventories, or schema mechanics.
- Return only structured data matching the schema.
""".strip()


def build_mood_atmosphere_prompt(
    *,
    design: MoodAtmosphereDesign | None = None,
    source_paragraph: str | None = None,
    prepared_source: PreparedSource | None = None,
    type_spec: QuestionTypeSpec,
) -> str:
    if design is None:
        if source_paragraph is None or prepared_source is None:
            raise TypeError("build_mood_atmosphere_prompt requires either design or source_paragraph plus prepared_source.")
        from .designers import build_mood_atmosphere_design

        design = build_mood_atmosphere_design(source_paragraph, prepared_source, type_spec)
    payload = design.prompt_payload
    active_subtype = type_spec.subtype_key.replace("_5", "")
    return f"""
You are planning an English exam mood/atmosphere question.

Return only structured data matching the required schema.

Question type:
- Key: mood_atmosphere
- Label: {type_spec.family_label_ko}
- Active subtype: {active_subtype}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

Sentence units:
{payload["sentence_inventory"]}
""".strip()


def build_mood_atmosphere_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- Keep the subtype required by the active schema and prompt.
- Re-check that `initial_emotion` and `final_emotion` are different.
- Re-check that `choice_pairs` contains exactly five unique readable English choices in the required format for the active subtype.
- Re-check that `correct_choice` is one of `choice_pairs` and matches the active subtype's target emotion or atmosphere field.
- Re-check that the required evidence fields for the active subtype are copied as exact passage snippets.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that uses emotional evidence rather than schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()


def build_underlined_phrase_meaning_prompt(
    *,
    design: UnderlinedPhraseMeaningDesign | None = None,
    source_paragraph: str | None = None,
    prepared_source: PreparedSource | None = None,
    type_spec: QuestionTypeSpec,
) -> str:
    if design is None:
        if source_paragraph is None or prepared_source is None:
            raise TypeError(
                "build_underlined_phrase_meaning_prompt requires either design or source_paragraph plus prepared_source."
            )
        from .designers import build_underlined_phrase_meaning_design

        design = build_underlined_phrase_meaning_design(source_paragraph, prepared_source, type_spec)
    payload = design.prompt_payload
    return f"""
You are planning an English exam underlined phrase meaning question.

Return only structured data matching the required schema.

Question type:
- Key: underlined_phrase_meaning
- Label: {type_spec.family_label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

Locked target span:
{payload["selected_span_line"]}

Selection reminders:
- The deterministic design stage already locked the target span.
- Do not choose a new span.
""".strip()


def build_fill_in_the_blank_prompt(
    *,
    design: FillInTheBlankDesign | None = None,
    source_paragraph: str | None = None,
    prepared_source: PreparedSource | None = None,
    type_spec: QuestionTypeSpec,
) -> str:
    if design is None:
        if source_paragraph is None or prepared_source is None:
            raise TypeError("build_fill_in_the_blank_prompt requires either design or source_paragraph plus prepared_source.")
        from .designers import build_fill_in_the_blank_design

        design = build_fill_in_the_blank_design(source_paragraph, prepared_source, type_spec)
    payload = design.prompt_payload
    return f"""
You are planning an English exam fill-in-the-blank question.

Return only structured data matching the required schema.

Question type:
- Key: fill_in_the_blank
- Label: {type_spec.family_label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

Locked blank target:
{payload["selected_span_line"]}

Selection reminders:
- The deterministic design stage already locked the blank target.
- Do not choose a new span.
""".strip()


def build_fill_in_the_blank_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- Re-check that `completion_choices` contains exactly five unique readable English choices.
- Re-check that `correct_choice` is one of `completion_choices`.
- Re-check that `supporting_evidence` is copied as an exact passage snippet.
- The deterministic design stage already locked `selected_span_id` and `selected_span_text`; do not change them.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that explains what idea the blank must express, without schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()


def build_vocab_prompt(
    *,
    design: VocabChoiceDesign | UnderlinedVocabDesign | None = None,
    source_paragraph: str | None = None,
    prepared_source: PreparedSource | None = None,
    type_spec: QuestionTypeSpec,
) -> str:
    if design is None:
        if source_paragraph is None or prepared_source is None:
            raise TypeError("build_vocab_prompt requires either design or source_paragraph plus prepared_source.")
        from .designers import build_vocab_design

        design = build_vocab_design(source_paragraph, prepared_source, type_spec)
    payload = design.prompt_payload
    if isinstance(design, UnderlinedVocabDesign):
        return f"""
You are planning an English exam contextual vocabulary question.

Return only structured data matching the required schema.

Question type:
- Key: vocab
- Label: {type_spec.family_label_ko}
- Active subtype: {type_spec.subtype_key}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

Locked five-target bundle:
{payload["target_bundle"]}

Locked subtype structure:
- If `corruptible_subset` is present below, only those locked target IDs may be corrupted.
{f"- Polarity/scope-eligible subset:\\n{payload['corruptible_subset']}" if payload.get("corruptible_subset") else "- No extra corruption subset beyond the full locked bundle."}
{f"- Locked answer_span_id: {payload['answer_span_id']}" if payload.get("answer_span_id") else ""}
{f"- Locked weaker untouched distractor id: {payload['untouched_distractor_span_id']}" if payload.get("untouched_distractor_span_id") else ""}

Selection reminders:
- Follow the active subtype exactly and keep subtype identity explicit in the returned schema.
- The deterministic design stage already locked the five targets.
- Return hard-family corruptions as an ordered `corrupted_replacements` list of records with `span_id` and `replacement_text`, not as a free-form mapping.
- Every corrupted replacement must stay readable in the same local slot, while becoming semantically wrong.
- If a locked `answer_span_id` is shown above for this subtype, do not change it; build the corruption pattern around that fixed answer marker.
- If the active subtype is `contextual_vocab_correct_among_4_corrupted_5`, exactly four items must be corrupted and exactly one item must remain clearly correct.
- If the active subtype is `contextual_vocab_error_1_among_5_5`, exactly one item must be corrupted and the other four must remain unchanged. If a locked `answer_span_id` is provided, that is the one item to corrupt.
- If the active subtype is `contextual_vocab_error_1_among_5_polarity_scope_5`, the one wrong item must come from the locked polarity/scope-eligible subset and must fail specifically by polarity, degree, or scope drift.
- If the active subtype is `contextual_vocab_error_1_among_5_collocation_5`, the one wrong item must come from the locked collocation-eligible subset and must fail by collocation or selectional mismatch, not by broad opposite meaning.
- If the active subtype is `contextual_vocab_correct_among_3_corrupted_5`, exactly three items must be corrupted and the only unchanged pair allowed is the locked `answer_span_id` plus the locked weaker untouched distractor.
- If the subtype asks for the correct remaining item, make sure only one answer is defensible from the passage evidence.
""".strip()
    return f"""
You are planning an English exam contextual vocabulary question.

Return only structured data matching the required schema.

Question type:
- Key: vocab
- Label: {type_spec.family_label_ko}
- Active subtype: {type_spec.subtype_key}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

{payload.get("locked_target_label", "Locked target")}:
{payload["selected_span_line"]}

Selection reminders:
- Follow the active subtype exactly and keep subtype identity explicit in the returned schema.
- The deterministic design stage already locked the lexical slot.
- Every option must stay readable in the same local slot.
- `selected_span_text` is the locked original source wording, but `correct_choice` should be the best contextual fit and may differ from the source wording.
- If the active subtype is `contextual_vocab_best_paraphrase_choice_5`, frame the task as choosing the closest lexical restatement of the locked content target, not as grammar repair or source restoration.
- If the active subtype is `contextual_vocab_best_paraphrase_choice_5`, `correct_choice` must be a non-identical best paraphrase and the original wording must not appear in `choice_words`.
- If the active subtype is `contextual_vocab_phrase_choice_5`, frame the task as replacing the locked phrase frame or collocational unit with the best phrase-level alternative, not as generic multiword paraphrase.
- If the active subtype is `contextual_vocab_phrase_choice_5`, the selected target and every choice must stay phrase-level, never single-word, and should preserve phrase-slot width tightly.
- Otherwise prefer a strong non-identical contextual replacement when one exists; exact source wording is allowed but not required.
- The other four options must be contextually wrong, not near-synonymous or jointly defensible.
""".strip()



def build_vocab_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- Re-check the active subtype and return a plan that matches that subtype's schema exactly.
- If the active subtype is a blank-choice vocab item, keep the locked target unchanged and set `correct_choice` to the best contextual lexical fit from `choice_words`.
- If the active subtype is `contextual_vocab_best_paraphrase_choice_5`, `correct_choice` must differ from `selected_span_text` and the unchanged source wording must not appear anywhere in `choice_words`.
- If the active subtype is `contextual_vocab_phrase_choice_5`, re-check that `selected_span_text` and every option are multiword phrases with tight slot-width preservation.
- If the active subtype is an underlined vocab item, do not change the locked target bundle; re-check the corruption count, whether `answer_span_id` matches the stem direction, and whether `corrupted_replacements` is an ordered list of `{{span_id, replacement_text}}` records.
- If the active subtype is `contextual_vocab_error_1_among_5_polarity_scope_5`, re-check that the one corruption is specifically a polarity, degree, or scope distortion.
- If the active subtype is `contextual_vocab_error_1_among_5_collocation_5`, re-check that the one corruption is a collocation or selectional mismatch rather than a broad opposite.
- Re-check that every option stays in the same local slot and remains readable in context.
- Re-check that the wrong options are semantically wrong, not merely rare, ungrammatical, or near-synonymous.
- If the previous error mentions ambiguity or multiple defensible answers, rebuild all distractors from scratch around clearer polarity, scope, collocation, or discourse-role mismatches.
- If the previous error mentions the wrong corruption class, replace the corrupted item from scratch rather than only paraphrasing the same bad replacement.
- If the previous error mentions slot-width drift, choose replacements that better preserve local phrase width and lexical-slot shape.
- If the previous error mentions duplicate rendered targets, rebuild the entire corruption set so all five visible underlined items stay distinct after substitution.
- Re-check that `supporting_evidence` is copied as an exact passage snippet.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose about contextual mismatch, without schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()


def build_grammar_prompt(
    *,
    design: GrammarDesign | None = None,
    source_paragraph: str | None = None,
    prepared_source: PreparedSource | None = None,
    type_spec: QuestionTypeSpec,
) -> str:
    if design is None:
        if source_paragraph is None or prepared_source is None:
            raise TypeError("build_grammar_prompt requires either design or source_paragraph plus prepared_source.")
        from .designers import build_grammar_design

        design = build_grammar_design(source_paragraph, prepared_source, type_spec)
    payload = design.prompt_payload
    return f"""
You are planning an English exam grammar question.

Return only structured data matching the required schema.

Question type:
- Key: grammar
- Label: {type_spec.family_label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{payload["source_paragraph"]}

Locked five-target bundle:
{payload["target_bundle"]}

Locked corruption target:
- {payload["corrupted_target_id"]}: text={payload["corrupted_target_text"]!r}; allowed_variants={payload["allowed_variants"]}

Selection reminders:
- The deterministic design stage already locked the five targets and the one corruption target.
- CRITICAL: The corrupted word MUST be a real, standard English word. NEVER invent pseudo-words.
  - BAD: 'increaseed', 'reduceing', 'understanded', 'emergeed'
  - GOOD: 'increasing', 'reduced', 'understood', 'emerged'
- Keep the corruption inside the active grammar subtype's controlled local family.
- When the target is verb-form-based, use the `allowed_variants` list for the locked corruption target.
""".strip()



def build_grammar_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- The deterministic design stage already locked `target_span_ids`, `target_span_texts`, and `corrupted_span_id`; do not change them.
- Re-check that `corrupted_word` is a single English word and a grammatically-plausible verb-form variant of the original target word.
- CRITICAL: `corrupted_word` must be a REAL English word. NEVER use invented pseudo-words (e.g. 'increaseed', 'reduceing').
  Use only real inflected forms that appear in the locked target's `allowed_variants`.
- Re-check that `supporting_evidence` is copied as an exact passage snippet.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose about the structural cue, without schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()


def build_underlined_phrase_meaning_repair_prompt(
    *,
    base_prompt: str,
    previous_error: str,
) -> str:
    return f"""
{base_prompt}

Your previous answer did not satisfy the required schema.

Previous validation error:
{previous_error}

Repair rules:
- Return a fully corrected answer.
- The deterministic design stage already locked `selected_span_id` and `selected_span_text`; do not change them.
- Re-check that `paraphrase_choices_ko` contains exactly five unique Korean choices.
- Re-check that `correct_choice` is one of `paraphrase_choices_ko`.
- Re-check that `supporting_evidence` is copied as an exact passage snippet.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that explains surface wording, contextual meaning, and passage evidence without schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()


def _build_sentence_insertion_candidate_hints(prepared_source: PreparedSource) -> str:
    units = prepared_source.sentence_units
    ranked_candidates: list[tuple[int, str]] = []

    for unit in units:
        if unit.index == 0 or unit.index == len(units) - 1:
            ranked_candidates.append(
                (
                    -999,
                    f"- {unit.id}: edge_sentence=yes; priority=reject_by_default; "
                    f"reason=missing one side of the required context; text={unit.text!r}",
                )
            )
            continue

        left_text = units[unit.index - 1].text
        right_text = units[unit.index + 1].text
        left_shared = _shared_content_preview(left_text, unit.text)
        right_shared = _shared_content_preview(unit.text, right_text)
        transition_open = _starts_with_any(unit.text, _TRANSITION_STARTERS)
        connector_only = transition_open and len(content_tokens(unit.text)) <= 3
        reference_inside = _contains_reference(unit.text)
        right_reference = _contains_reference(right_text)

        score = len(left_shared) + len(right_shared)
        if left_shared and right_shared:
            score += 3
        if reference_inside:
            score += 1
        if right_reference:
            score += 1
        if transition_open:
            score += 1
        if connector_only:
            score -= 3

        if score >= 7 and not connector_only:
            priority = "strong"
        elif score >= 4 and not connector_only:
            priority = "usable"
        else:
            priority = "weak"

        ranked_candidates.append(
            (
                score,
                (
                    f"- {unit.id}: priority={priority}; left_anchor={left_text!r}; right_anchor={right_text!r}; "
                    f"shared_left={_csv_or_none(left_shared)}; shared_right={_csv_or_none(right_shared)}; "
                    f"opens_with_transition={_yes_no(transition_open)}; contains_reference={_yes_no(reference_inside)}; "
                    f"right_context_refers_back={_yes_no(right_reference)}; connector_only={_yes_no(connector_only)}"
                ),
            )
        )

    ordered_lines = [line for _, line in sorted(ranked_candidates, key=lambda item: item[0], reverse=True)]
    return "\n".join(ordered_lines)


def _build_paragraph_boundary_hints(prepared_source: PreparedSource) -> str:
    return "\n".join(
        (
            f"- {hint.left_unit_id} -> {hint.right_unit_id}: "
            f"boundary_signal={_hint_level(max(hint.boundary_support_score, 0))}; "
            f"split_hint={_hint_level(hint.start_signal_score)}; "
            f"keep_together_hint={_hint_level(hint.local_keep_score)}; "
            f"shared_tokens={_csv_or_none(list(hint.shared_tokens))}; "
            f"cut_reasons={'; '.join(hint.reasons) or 'none'}; "
            f"right_stage_cue={hint.right_stage_cue or 'none'}; "
            f"right_opens_with_reference={_yes_no(hint.right_opens_with_reference)}"
        )
        for hint in paragraph_boundary_hints(prepared_source)
    )


def _build_paragraph_block_start_hints(prepared_source: PreparedSource) -> str:
    return "\n".join(
        (
            f"- {hint.unit_id}: block_start_priority={_hint_level(hint.start_signal_score)}; "
            f"boundary_support={_hint_level(max(hint.boundary_support_score, 0))}; "
            f"reason={'; '.join(hint.reasons) or 'fallback boundary'}; text={hint.text!r}"
        )
        for hint in paragraph_block_start_hints(prepared_source)
    )


def _build_paragraph_partition_candidates(prepared_source: PreparedSource) -> str:
    lines: list[str] = []
    for candidate in paragraph_ordering_candidates(prepared_source)[:5]:
        block_starts = ",".join(block[0] for block in candidate.continuation_blocks)
        lines.append(
            (
                f"- cuts={candidate.cut_positions}; viability={'stable' if paragraph_candidate_is_stable(candidate) else 'watch'}; "
                f"block_starts={block_starts}; edge_scores={candidate.edge_scores}; "
                f"start_signal_total={candidate.block_start_signal_total}; "
                f"negative_boundaries={candidate.negative_boundary_count}"
            )
        )
    return "\n".join(lines)


def _shared_content_preview(left_text: str, right_text: str, *, limit: int = 3) -> list[str]:
    shared = sorted(content_tokens(left_text) & content_tokens(right_text))
    return shared[:limit]


def _gap_edge_label(prepared_source: PreparedSource, unit_id: str | None, *, side: str) -> str:
    if unit_id is None:
        return "START" if side == "before" else "END"
    unit = prepared_source.sentence_units[int(unit_id[1:])]
    return f"{unit_id} ({_sentence_snippet(unit.text)})"


def _neighbor_id(prepared_source: PreparedSource, index: int) -> str:
    if index < 0:
        return "START"
    if index >= len(prepared_source.sentence_units):
        return "END"
    return prepared_source.sentence_units[index].id


def _span_priority_label(score: int) -> str:
    if score >= 7:
        return "top"
    if score >= 5:
        return "strong"
    if score >= 3:
        return "watch"
    return "weak"


def _vocab_hard_preference_label(score: int, cue_count: int) -> str:
    if score >= 7 and cue_count >= 3:
        return "top"
    if score >= 6 and cue_count >= 2:
        return "strong"
    if score >= 4 or cue_count >= 2:
        return "usable"
    return "fallback"


def _span_centrality_label(tags: list[str]) -> str:
    tag_set = set(tags)
    if {"claim_bearing", "abstract_term"} <= tag_set:
        return "claim_bearing"
    if "claim_bearing" in tag_set or "phrase_frame" in tag_set:
        return "contextual"
    if "embedded_phrase" in tag_set:
        return "local"
    return "weak"


def _span_context_window(before: str | None, text: str, after: str | None) -> str:
    left = before or "..."
    right = after or "..."
    return f"{left} [{text}] {right}"


def _stage_cue(text: str) -> str | None:
    normalized = normalize_text(text).lower()
    for cue in ("first", "next", "finally", "to begin with", "to start with"):
        if re.match(rf"^{re.escape(cue)}(?:\b|[^\w])", normalized) is not None:
            return cue
    return None


def _contains_reference(text: str) -> bool:
    lowered = normalize_text(text).lower()
    return any(re.search(rf"\b{re.escape(token)}\b", lowered) is not None for token in _REFERENTIAL_CUES)


def _starts_with_any(text: str, starters: set[str]) -> bool:
    normalized = normalize_text(text).lower()
    return any(re.match(rf"^{re.escape(starter)}(?:\b|[^\w])", normalized) is not None for starter in starters)


def _sentence_snippet(text: str, *, max_words: int = 10) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def _csv_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _hint_level(score: int) -> str:
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    if score >= 1:
        return "low"
    return "none"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
