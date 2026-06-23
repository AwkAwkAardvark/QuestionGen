from __future__ import annotations

import re

from .parsers import content_tokens, normalize_text
from .question_types import QuestionTypeSpec
from .schemas import PreparedSource

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
_PARALLEL_STARTERS = {
    "another",
    "for example",
    "for instance",
    "in",
    "similarly",
}


def build_sentence_insertion_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        (
            f"- {unit.id}: text={unit.text!r}; "
            f"left_context={_neighbor_id(prepared_source, unit.index - 1)}; "
            f"right_context={_neighbor_id(prepared_source, unit.index + 1)}"
        )
        for unit in prepared_source.sentence_units
    )
    gap_inventory = "\n".join(
        (
            f"- {gap.id}: between "
            f"{_gap_edge_label(prepared_source, gap.before_unit_id, side='before')} and "
            f"{_gap_edge_label(prepared_source, gap.after_unit_id, side='after')}"
        )
        for gap in prepared_source.gap_units
    )
    ranked_candidates = _build_sentence_insertion_candidate_hints(prepared_source)
    return f"""
You are planning an English exam sentence insertion question.

Return only structured data matching the required schema.

Question type:
- Key: sentence_insertion
- Label: {type_spec.label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}

Gap units:
{gap_inventory}

Ranked target candidates (best available strong target first):
{ranked_candidates}

Selection reminders:
- Choose the target only from candidates with clear two-sided support and avoid `priority=weak` or `priority=reject_by_default`.
- Exclude the target's collapsed gap pair and never return both sides of that pair inside `selected_gap_ids`.
- Before returning, re-check that `correct_gap_id` is one of the exact five `selected_gap_ids`.
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
- `correct_gap_id` must be exactly one of the IDs listed in `selected_gap_ids`.
- Re-check that `selected_gap_ids` contains exactly five unique gap IDs.
- Re-check that you did not choose both gaps immediately before and after the target sentence.
- Re-check that the five selected gap IDs still map to five distinct rendered positions after removing the target sentence.
- If the previous error mentions collapsed rendered positions, rebuild the five-gap set from scratch instead of editing only one ID.
- Re-check the ranked target-candidate notes and prefer the best remaining sentence with two-sided support, not merely a sentence with a valid surface shape.
- Re-check that the target sentence is not fragmentary, first-only, last-only, or supported by only one side of the context.
- Re-check that `correct_gap_id` is copied from the final five-item `selected_gap_ids` list after every other field is finalized.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that uses the surrounding sentences as evidence rather than the given sentence itself, internal IDs, gap labels, schema field names, or renderer mechanics.
- Return only structured data matching the schema.
""".strip()


def build_paragraph_ordering_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        (
            f"- {unit.id}: text={unit.text!r}; "
            f"stage_cue={_stage_cue(unit.text) or 'none'}; "
            f"opens_with_reference={_yes_no(_contains_reference(unit.text))}"
        )
        for unit in prepared_source.sentence_units
    )
    boundary_hints = _build_paragraph_boundary_hints(prepared_source)
    block_start_hints = _build_paragraph_block_start_hints(prepared_source)
    return f"""
You are planning an English exam paragraph ordering question.

Return only structured data matching the required schema.

Question type:
- Key: paragraph_ordering
- Label: {type_spec.label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}

Boundary hints:
{boundary_hints}

Candidate continuation-block starts (best first):
{block_start_hints}

Selection reminders:
- Choose a partition only if every block boundary is supported by real adjacency evidence, not just by a generic topic outline.
- Avoid block starts marked as weak or dominated by parallel-example risk when a stronger boundary exists.
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
- The intro block and continuation blocks must together cover every sentence exactly once.
- Re-check that flattening the intro block followed by the three continuation blocks reproduces the full sentence inventory in exactly the original order.
- Keep exactly three continuation blocks.
- Keep each block non-empty.
- Re-check the block-start hints and choose boundaries that create the strongest forced adjacency, not just three plausible chunks.
- Re-check that the ordering is forced by adjacency, not just by a generic intro-middle-end summary or interchangeable examples.
- If the previous error mentions weak adjacency, rebuild the whole partition around stronger boundaries rather than only moving one sentence.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that explains why one block follows the previous block rather than using internal sentence IDs, block inventories, or schema mechanics.
- Return only structured data matching the schema.
""".strip()


def build_mood_atmosphere_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        f"- {unit.id}: {unit.text}"
        for unit in prepared_source.sentence_units
    )
    return f"""
You are planning an English exam mood/atmosphere question.

Return only structured data matching the required schema.

Question type:
- Key: mood_atmosphere
- Label: {type_spec.label_ko}
- Active subtype: emotion_shift
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}
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
- Keep the subtype as emotion_shift.
- Re-check that `initial_emotion` and `final_emotion` are different.
- Re-check that `choice_pairs` contains exactly five unique English `emotion -> emotion` choices.
- Re-check that `correct_choice` is one of `choice_pairs` and exactly matches `initial_emotion -> final_emotion`.
- Re-check that `initial_evidence`, `final_evidence`, and optional `shift_trigger` are copied as exact passage snippets.
- Keep the explanation in Korean.
- Rewrite the explanation as teacher-facing Korean prose that uses emotional evidence rather than schema fields or mechanics.
- Return only structured data matching the schema.
""".strip()


def build_underlined_phrase_meaning_prompt(
    *,
    source_paragraph: str,
    prepared_source: PreparedSource,
    type_spec: QuestionTypeSpec,
) -> str:
    sentence_inventory = "\n".join(
        f"- {unit.id}: {unit.text}"
        for unit in prepared_source.sentence_units
    )
    span_inventory = "\n".join(
        (
            f"- rank {rank}: {span.id}; score={span.priority_score}; "
            f"priority={_span_priority_label(span.priority_score)}; "
            f"centrality={_span_centrality_label(span.heuristic_tags)}; "
            f"text={span.text!r}; sentence={span.sentence_unit_id or 'NONE'}; "
            f"tags={','.join(span.heuristic_tags) or 'none'}; "
            f"context={_span_context_window(span.context_before, span.text, span.context_after)}"
        )
        for rank, span in enumerate(
            sorted(
                prepared_source.span_units,
                key=lambda span: (-span.priority_score, span.char_start, span.char_end),
            ),
            start=1,
        )
    )
    return f"""
You are planning an English exam underlined phrase meaning question.

Return only structured data matching the required schema.

Question type:
- Key: underlined_phrase_meaning
- Label: {type_spec.label_ko}
- Student-facing stem: {type_spec.question_stem}

Planning rules:
{type_spec.planner_prompt}

Source paragraph:
{source_paragraph}

Sentence units:
{sentence_inventory}

Span candidates:
{span_inventory}

Selection reminders:
- Prefer candidates marked `priority=top` or `priority=strong` and avoid `centrality=weak` or `centrality=local` when a stronger candidate exists.
- Never choose a span just because its boundaries are valid; the span must still carry a central claim, mechanism, evaluation, contrast, or limitation.
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
- Re-check that `selected_span_id` is one of the provided span IDs.
- Re-check that `selected_span_text` exactly matches the source text for that selected span.
- Re-check that `paraphrase_choices_ko` contains exactly five unique Korean choices.
- Re-check that `correct_choice` is one of `paraphrase_choices_ko`.
- Re-check that `supporting_evidence` is copied as an exact passage snippet.
- Re-check the ranked span inventory and prefer the strongest claim-bearing or proposition-bearing span, not a merely local phrase with valid boundaries.
- Re-check that the selected span is not a dangling fragment, a surface comparison phrase, or a weakly central literal phrase.
- If the previous error says the span is not central enough, choose a new higher-centrality candidate instead of reusing the same span.
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
    units = prepared_source.sentence_units
    lines: list[str] = []
    for left_unit, right_unit in zip(units, units[1:]):
        shared = _shared_content_preview(left_unit.text, right_unit.text)
        stage_cue = _stage_cue(right_unit.text)
        right_reference = _contains_reference(right_unit.text)
        split_score = 3 if stage_cue else 0
        keep_score = len(shared) + (1 if right_reference else 0)
        if _starts_with_any(right_unit.text, _PARALLEL_STARTERS):
            split_score += 1
        lines.append(
            (
                f"- {left_unit.id} -> {right_unit.id}: split_hint={_hint_level(split_score)}; "
                f"keep_together_hint={_hint_level(keep_score)}; "
                f"shared_tokens={_csv_or_none(shared)}; "
                f"right_stage_cue={stage_cue or 'none'}; "
                f"right_opens_with_reference={_yes_no(right_reference)}"
            )
        )
    return "\n".join(lines)


def _build_paragraph_block_start_hints(prepared_source: PreparedSource) -> str:
    units = prepared_source.sentence_units
    candidates: list[tuple[int, str]] = []
    for unit in units[1:]:
        previous = units[unit.index - 1]
        stage_cue = _stage_cue(unit.text)
        shared = _shared_content_preview(previous.text, unit.text)
        right_reference = _contains_reference(unit.text)
        score = 0
        reasons: list[str] = []
        if stage_cue:
            score += 6
            reasons.append(f"explicit_stage={stage_cue}")
        if _starts_with_any(unit.text, _PARALLEL_STARTERS):
            score -= 2
            reasons.append("parallel_example_risk")
        if shared:
            score -= 1
            reasons.append(f"shared_with_previous={_csv_or_none(shared)}")
        if right_reference:
            score -= 1
            reasons.append("opens_by_referring_back")
        candidates.append(
            (
                score,
                f"- {unit.id}: block_start_priority={_hint_level(max(score, 0))}; reason={'; '.join(reasons) or 'fallback boundary'}; text={unit.text!r}",
            )
        )
    return "\n".join(line for _, line in sorted(candidates, key=lambda item: item[0], reverse=True))


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
