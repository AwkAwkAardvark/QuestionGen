"""Pending question-type planning artifact.

This file is intentionally outside the live runtime registry. It exists to
catalog candidate question types and implementation notes without changing
`src/questiongen/QUESTION_TYPES` or any launcher behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

InfrastructureKind = Literal["sentence", "block", "span", "passage"]


@dataclass(frozen=True)
class PendingQuestionTypeSpec:
    broad_key: str
    label_ko: str
    format_key: str
    stem_direction_ko: str
    expected_output_shape: str
    infrastructure: InfrastructureKind
    likely_incompatibility_patterns: tuple[str, ...]
    implementation_risks: tuple[str, ...]
    requires_user_confirmation: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


PENDING_CATALOG_CONTEXT = {
    "status": "planning_only",
    "do_not_import_into_runtime": True,
    "colab_first_launcher": True,
    "drive_backed_runtime": True,
    "run_all_registered_types": True,
    "incompatibility_status": "qtype_incompatibility_error",
    "live_question_type_keys": ("sentence_insertion", "paragraph_ordering"),
    "pending_only_note": (
        "Entries below are candidate specs only. They are not live registry "
        "entries and must not be wired into QUESTION_TYPES until their "
        "planner, renderer, validator, and suitability gates are ready."
    ),
}


PENDING_QUESTION_TYPES: tuple[PendingQuestionTypeSpec, ...] = (
    PendingQuestionTypeSpec(
        broad_key="mood_atmosphere",
        label_ko="심경·분위기",
        format_key="mood_atmosphere_adjective_choice_5",
        stem_direction_ko=(
            "First implementation should support only clearly evidenced "
            "subtypes, likely either overall atmosphere or mood change. "
            "Exact Korean stems should be selected by subtype, not hardcoded "
            "to a single generic stem."
        ),
        expected_output_shape=(
            "Original passage preserved unchanged; five answer choices; "
            "marker answer ①-⑤; Korean explanation grounded in textual cues."
        ),
        infrastructure="passage",
        likely_incompatibility_patterns=(
            "Informational or expository passages with no stable emotional signal.",
            "Passages where atmosphere is too diffuse to support one best answer.",
            "Passages that hint at mood but not clearly enough for five-way choice quality.",
        ),
        implementation_risks=(
            "High false-positive risk if the planner forces mood onto neutral passages.",
            "Choice quality is largely LLM-dependent and may need subtype-specific validation.",
            "Teacher-facing explanations must avoid internal engine notation and vague sentiment labels.",
        ),
        requires_user_confirmation=(
            "Confirm first supported subtype priority: mood change, atmosphere, or both.",
            "Confirm whether answer choices should stay in English adjective form for the first release.",
        ),
        notes=(
            "Best next implementation candidate because it exercises qtype_incompatibility_error without requiring span preparation.",
            "Expected to yield a relatively high incompatibility rate in real mixed-source batches.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="fill_in_the_blank",
        label_ko="빈칸",
        format_key="blank_best_fit_5_choices",
        stem_direction_ko=(
            "Likely first stem: '다음 빈칸에 들어갈 말로 가장 적절한 것은?' "
            "Keep the exact blank shape open until the first supported span "
            "granularity is confirmed."
        ),
        expected_output_shape=(
            "One source passage with one selected span replaced by a blank; "
            "five answer choices; marker answer ①-⑤; Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages with no single removable span that remains inferable from context.",
            "Passages where blanking a span creates multiple defensible answers.",
            "Passages whose best removable unit is too long or too trivial for exam use.",
        ),
        implementation_risks=(
            "Needs a real span-preparation layer before planning is trustworthy.",
            "Distractor quality will dominate item usefulness and may require extra deterministic checks.",
            "Blank placement must match 수능/내신 expectations rather than arbitrary deletion.",
        ),
        requires_user_confirmation=(
            "Confirm the preferred broad key: fill_in_the_blank versus the shorter historical blank label.",
            "Confirm the first removable unit target: phrase, clause, or sentence-length span.",
        ),
        notes=(
            "Do not force this into the current sentence/gap pipeline.",
            "Depends on span IDs and span-preserving rendering.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="phrase_translation",
        label_ko="밑줄 친 부분 의미",
        format_key="underlined_phrase_translation_5_ko",
        stem_direction_ko=(
            "Likely first stem: '다음 글의 밑줄 친 부분의 의미로 가장 적절한 것은?'"
        ),
        expected_output_shape=(
            "Original passage with one underlined English span; five Korean "
            "choice glosses; marker answer ①-⑤; Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages whose best candidate span is either too literal or too context-free.",
            "Passages with multiple acceptable Korean paraphrases and weak one-best-answer pressure.",
            "Idiomatic or compressed spans whose distractors would become arbitrary without stronger guidance.",
        ),
        implementation_risks=(
            "Needs span selection that respects contextual meaning rather than dictionary glossing.",
            "Korean answer choices need normalization rules to avoid near-duplicate valid answers.",
            "Future optional CSV-driven target-span input may change the interface, so keep v1 assumptions explicit.",
        ),
        requires_user_confirmation=(
            "Confirm whether the first release should always self-select the underlined span from the source paragraph.",
        ),
        notes=(
            "Span-based but usually simpler than vocab or grammar because only one target is rendered.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="vocab",
        label_ko="어휘",
        format_key="vocab_incorrect_contextual_usage_5",
        stem_direction_ko=(
            "Likely first stem: '다음 글의 밑줄 친 부분 중, 문맥상 낱말의 쓰임이 "
            "적절하지 않은 것은?'"
        ),
        expected_output_shape=(
            "Original passage with five numbered underlined targets; one "
            "target deterministically replaced with a wrong-but-plausible word "
            "or phrase; marker answer ①-⑤; Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages without five clean lexical targets worth underlining.",
            "Passages where a wrong replacement becomes obviously impossible rather than plausibly testable.",
            "Passages whose key vocabulary is too technical, culture-bound, or semantically flat for this format.",
        ),
        implementation_risks=(
            "Requires multi-span preparation and deterministic replacement rendering.",
            "Replacement candidates must be plausible enough for exam quality but still clearly wrong in context.",
            "Validation likely needs stronger lexical sanity checks than current types.",
        ),
        requires_user_confirmation=(
            "Confirm whether the first release should allow short phrases as well as single-word targets.",
        ),
        notes=(
            "Should come after phrase-level span tooling is stable.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="grammar",
        label_ko="어법",
        format_key="grammar_incorrect_underlined_form_5",
        stem_direction_ko=(
            "Likely first stem: '다음 글의 밑줄 친 부분 중, 어법상 틀린 것은?'"
        ),
        expected_output_shape=(
            "Original passage with five numbered underlined grammar targets; "
            "one target replaced with a grammatically wrong form; marker "
            "answer ①-⑤; Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages without five stable grammar targets suitable for underlining.",
            "Passages where a wrong inflection or construction would sound too obviously broken.",
            "Passages where multiple grammar points compete and reduce one-best-answer clarity.",
        ),
        implementation_risks=(
            "Most fragile of the current span-based candidates because the error must be subtle, local, and explainable.",
            "Requires grammar-aware replacement planning, not just surface word substitution.",
            "High risk of accidental semantic distortion or multiple valid corrections.",
        ),
        requires_user_confirmation=(
            "Confirm the preferred first grammar error family, if the release should narrow scope initially.",
        ),
        notes=(
            "Likely the last of the currently discussed candidates to implement.",
        ),
    ),
)
