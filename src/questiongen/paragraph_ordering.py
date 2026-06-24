from __future__ import annotations

from dataclasses import dataclass
import re

from .parsers import content_tokens, normalize_text
from .schemas import PreparedSource

_TRANSITION_STARTERS = (
    "however",
    "therefore",
    "thus",
    "nonetheless",
    "moreover",
    "furthermore",
    "instead",
    "meanwhile",
    "consequently",
)
_STAGE_STARTERS = (
    "first",
    "next",
    "finally",
    "to begin with",
    "to start with",
)
_WEAK_FRAME_STARTERS = (
    "if you haven't guessed already",
    "for the first time",
    "but that",
    "if during",
)
_MEDIUM_FRAME_PATTERNS = (
    "after ",
    "but before ",
    "if you want ",
)
_REFERENTIAL_BRIDGES = (
    "there is good reason for this",
    "he continued as follows",
    "they represent",
    "this policy",
    "he told me",
    "cases in which",
)
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
_PARALLEL_STARTERS = (
    "for example",
    "for instance",
    "another",
    "similarly",
)


@dataclass(frozen=True)
class ParagraphBoundaryHint:
    left_unit_id: str
    right_unit_id: str
    shared_tokens: tuple[str, ...]
    right_stage_cue: str | None
    right_opens_with_reference: bool
    start_signal_score: int
    local_keep_score: int
    boundary_support_score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ParagraphBlockStartHint:
    unit_id: str
    text: str
    start_signal_score: int
    boundary_support_score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ParagraphOrderingCandidate:
    intro_unit_ids: tuple[str, ...]
    continuation_blocks: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]
    cut_positions: tuple[int, int, int]
    edge_scores: tuple[int, int, int]
    block_start_scores: tuple[int, int, int]
    boundary_support_scores: tuple[int, int, int]
    strong_start_count: int
    block_start_signal_total: int
    negative_boundary_count: int
    total_score: int


def adjacency_score(left_text: str, right_text: str) -> int:
    score = 0
    shared = content_tokens(left_text) & content_tokens(right_text)
    if shared:
        score += min(3, len(shared) + 1)

    right_lower = normalize_text(right_text).lower()
    left_lower = normalize_text(left_text).lower()
    if left_text.rstrip().endswith("?"):
        score += 2
    if _starts_with_any(right_lower, _TRANSITION_STARTERS + _STAGE_STARTERS):
        score += 1
    if _contains_reference(right_text):
        score += 1
    if any(token in right_lower for token in ("this", "these", "such", "therefore", "however")) and left_lower:
        score += 1
    return score


def looks_like_parallel_example_start(text: str) -> bool:
    normalized = normalize_text(text).lower()
    if _starts_with_any(normalized, _PARALLEL_STARTERS):
        return True
    if re.match(r"^in [a-z]+,", normalized) is not None and not _has_transition_near_start(normalized):
        return True
    return False


def looks_like_parallel_blocks(blocks: list[str]) -> bool:
    return sum(1 for block in blocks if looks_like_parallel_example_start(block)) >= 2


def paragraph_boundary_hints(prepared_source: PreparedSource) -> list[ParagraphBoundaryHint]:
    hints: list[ParagraphBoundaryHint] = []
    for left_unit, right_unit in zip(prepared_source.sentence_units, prepared_source.sentence_units[1:]):
        shared_tokens = tuple(sorted(content_tokens(left_unit.text) & content_tokens(right_unit.text))[:3])
        start_signal_score, reasons = block_start_signal(previous_text=left_unit.text, next_text=right_unit.text)
        local_keep_score = len(shared_tokens) + (1 if _contains_reference(right_unit.text) else 0)
        if looks_like_parallel_example_start(right_unit.text):
            local_keep_score += 1
        hints.append(
            ParagraphBoundaryHint(
                left_unit_id=left_unit.id,
                right_unit_id=right_unit.id,
                shared_tokens=shared_tokens,
                right_stage_cue=stage_cue(right_unit.text),
                right_opens_with_reference=_contains_reference(right_unit.text),
                start_signal_score=start_signal_score,
                local_keep_score=local_keep_score,
                boundary_support_score=start_signal_score - local_keep_score,
                reasons=tuple(reasons),
            )
        )
    return hints


def paragraph_block_start_hints(prepared_source: PreparedSource) -> list[ParagraphBlockStartHint]:
    boundaries = paragraph_boundary_hints(prepared_source)
    units = prepared_source.sentence_units
    by_unit_id = {boundary.right_unit_id: boundary for boundary in boundaries}
    hints: list[ParagraphBlockStartHint] = []
    for unit in units[1:]:
        boundary = by_unit_id[unit.id]
        hints.append(
            ParagraphBlockStartHint(
                unit_id=unit.id,
                text=unit.text,
                start_signal_score=boundary.start_signal_score,
                boundary_support_score=boundary.boundary_support_score,
                reasons=boundary.reasons,
            )
        )
    return sorted(
        hints,
        key=lambda hint: (
            hint.start_signal_score,
            hint.boundary_support_score,
            -len(hint.text),
        ),
        reverse=True,
    )


def paragraph_ordering_candidates(prepared_source: PreparedSource) -> list[ParagraphOrderingCandidate]:
    sentence_units = prepared_source.sentence_units
    sentence_ids = [unit.id for unit in sentence_units]
    sentence_texts = [unit.text for unit in sentence_units]
    boundary_map = {
        boundary.right_unit_id: boundary
        for boundary in paragraph_boundary_hints(prepared_source)
    }
    candidates: list[ParagraphOrderingCandidate] = []

    for first_cut in range(1, len(sentence_units) - 2):
        for second_cut in range(first_cut + 1, len(sentence_units) - 1):
            for third_cut in range(second_cut + 1, len(sentence_units)):
                intro_unit_ids = tuple(sentence_ids[:first_cut])
                continuation_blocks = (
                    tuple(sentence_ids[first_cut:second_cut]),
                    tuple(sentence_ids[second_cut:third_cut]),
                    tuple(sentence_ids[third_cut:]),
                )
                ordered_segments = [
                    " ".join(sentence_texts[:first_cut]),
                    " ".join(sentence_texts[first_cut:second_cut]),
                    " ".join(sentence_texts[second_cut:third_cut]),
                    " ".join(sentence_texts[third_cut:]),
                ]
                edge_scores = tuple(
                    adjacency_score(ordered_segments[index], ordered_segments[index + 1])
                    for index in range(3)
                )
                block_start_scores = tuple(
                    boundary_map[block[0]].start_signal_score
                    for block in continuation_blocks
                )
                boundary_support_scores = tuple(
                    boundary_map[block[0]].boundary_support_score
                    for block in continuation_blocks
                )
                candidates.append(
                    ParagraphOrderingCandidate(
                        intro_unit_ids=intro_unit_ids,
                        continuation_blocks=continuation_blocks,
                        cut_positions=(first_cut, second_cut, third_cut),
                        edge_scores=edge_scores,
                        block_start_scores=block_start_scores,
                        boundary_support_scores=boundary_support_scores,
                        strong_start_count=sum(1 for score in block_start_scores if score >= 2),
                        block_start_signal_total=sum(block_start_scores),
                        negative_boundary_count=sum(1 for score in boundary_support_scores if score < 0),
                        total_score=sum(edge_scores) + sum(boundary_support_scores),
                    )
                )

    return sorted(
        candidates,
        key=lambda candidate: (
            1 if paragraph_candidate_is_stable(candidate) else 0,
            candidate.total_score,
            min(candidate.edge_scores),
            candidate.block_start_signal_total,
            -candidate.negative_boundary_count,
        ),
        reverse=True,
    )


def paragraph_candidate_is_stable(candidate: ParagraphOrderingCandidate) -> bool:
    if any(score < 2 for score in candidate.edge_scores):
        return False
    if candidate.strong_start_count < 2 and candidate.block_start_signal_total < 5:
        return False
    if candidate.negative_boundary_count >= 2 and candidate.block_start_signal_total < 6:
        return False
    return True


def paragraph_candidate_from_plan(
    prepared_source: PreparedSource,
    intro_unit_ids: list[str],
    continuation_blocks: list[list[str]],
) -> ParagraphOrderingCandidate:
    sentence_map = {unit.id: unit.text for unit in prepared_source.sentence_units}
    boundary_map = {
        boundary.right_unit_id: boundary
        for boundary in paragraph_boundary_hints(prepared_source)
    }
    ordered_segments = [
        " ".join(sentence_map[unit_id] for unit_id in intro_unit_ids),
        *(
            " ".join(sentence_map[unit_id] for unit_id in block)
            for block in continuation_blocks
        ),
    ]
    block_start_scores = tuple(
        boundary_map[block[0]].start_signal_score
        for block in continuation_blocks
    )
    boundary_support_scores = tuple(
        boundary_map[block[0]].boundary_support_score
        for block in continuation_blocks
    )
    return ParagraphOrderingCandidate(
        intro_unit_ids=tuple(intro_unit_ids),
        continuation_blocks=tuple(tuple(block) for block in continuation_blocks),
        cut_positions=(
            len(intro_unit_ids),
            len(intro_unit_ids) + len(continuation_blocks[0]),
            len(intro_unit_ids) + len(continuation_blocks[0]) + len(continuation_blocks[1]),
        ),
        edge_scores=tuple(
            adjacency_score(ordered_segments[index], ordered_segments[index + 1])
            for index in range(3)
        ),
        block_start_scores=block_start_scores,
        boundary_support_scores=boundary_support_scores,
        strong_start_count=sum(1 for score in block_start_scores if score >= 2),
        block_start_signal_total=sum(block_start_scores),
        negative_boundary_count=sum(1 for score in boundary_support_scores if score < 0),
        total_score=sum(
            adjacency_score(ordered_segments[index], ordered_segments[index + 1])
            for index in range(3)
        ) + sum(boundary_support_scores),
    )


def block_start_signal(previous_text: str, next_text: str) -> tuple[int, list[str]]:
    normalized = normalize_text(next_text).lower()
    reasons: list[str] = []
    score = 0

    if previous_text.rstrip().endswith("?"):
        score += 3
        reasons.append("after_question")
    if _starts_with_any(normalized, _STAGE_STARTERS):
        score += 3
        reasons.append(f"explicit_stage={stage_cue(next_text) or 'stage'}")
    if _has_transition_near_start(normalized):
        score += 3
        reasons.append("discourse_marker")
    if normalized.startswith(_MEDIUM_FRAME_PATTERNS):
        score += 2
        reasons.append("frame_shift")
    if normalized.startswith(_REFERENTIAL_BRIDGES):
        score += 2
        reasons.append("referential_bridge")
    if normalized.startswith(_WEAK_FRAME_STARTERS):
        score += 1
        reasons.append("weak_frame")
    if _starts_with_reference(normalized):
        score += 1
        reasons.append("opens_by_referring_back")

    return score, reasons


def stage_cue(text: str) -> str | None:
    normalized = normalize_text(text).lower()
    for cue in _STAGE_STARTERS:
        if re.match(rf"^{re.escape(cue)}(?:\b|[^\w])", normalized) is not None:
            return cue
    return None


def _contains_reference(text: str) -> bool:
    lowered = normalize_text(text).lower()
    return any(re.search(rf"\b{re.escape(token)}\b", lowered) is not None for token in _REFERENTIAL_CUES)


def _starts_with_reference(normalized_text: str) -> bool:
    for cue in _REFERENTIAL_CUES:
        if re.match(rf"^{re.escape(cue)}(?:\b|[^\w])", normalized_text) is not None:
            return True
    return False


def _starts_with_any(text: str, starters: tuple[str, ...]) -> bool:
    return any(re.match(rf"^{re.escape(starter)}(?:\b|[^\w])", text) is not None for starter in starters)


def _has_transition_near_start(normalized_text: str) -> bool:
    start_words = re.findall(r"[a-z]+", normalized_text)[:4]
    return any(starter in start_words for starter in _TRANSITION_STARTERS)
