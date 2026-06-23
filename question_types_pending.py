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
    "live_type_refinement_note": (
        "The same PendingQuestionTypeSpec shape may also be used to capture "
        "non-runtime refinement guidance for already live types. Those notes "
        "are planning aids only and must not be treated as pending registry "
        "entries."
    ),
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
        format_key="emotion_shift_pair_choice_5",
        stem_direction_ko=(
            "Treat this family as subtype-driven affective inference rather "
            "than generic sentiment. Exact Korean stems should be selected by "
            "subtype, not hardcoded to a single generic stem."
        ),
        expected_output_shape=(
            "Original passage preserved unchanged; five subtype-appropriate "
            "answer choices; marker answer ①-⑤; Korean explanation grounded "
            "in affective textual cues."
        ),
        infrastructure="passage",
        likely_incompatibility_patterns=(
            "Informational or expository passages with no stable emotional signal.",
            "Passages where the target character or scene is unclear.",
            "Passages where atmosphere is too diffuse to support one best answer.",
            "Passages that hint at mood but not clearly enough for five-way choice quality.",
            "Passages that do not contain a real emotional shift even if the surface situation changes.",
            "Passages with multiple plausible near-synonym answers because the affective evidence is too weak or too mixed.",
        ),
        implementation_risks=(
            "High false-positive risk if the planner forces mood onto neutral passages.",
            "Choice quality is largely LLM-dependent and may need subtype-specific validation to avoid near-synonym clusters.",
            "Atmosphere can be confused with a character's private emotion if subtype targeting is weak.",
            "Teacher-facing explanations must avoid internal engine notation and vague sentiment labels.",
        ),
        requires_user_confirmation=(
            "Confirm whether the first live rollout under this broad key should support only emotion_shift or both emotion_shift and atmosphere.",
            "Confirm whether emotion_state should wait until after the first subtype rollout or be included from the start.",
            "Confirm whether answer choices should stay in English adjective form for the first release.",
        ),
        notes=(
            "Best next implementation candidate because it exercises qtype_incompatibility_error without requiring span preparation.",
            "Expected to yield a relatively high incompatibility rate in real mixed-source batches.",
            "Useful external guidance: model this family as affective inference, not positive-versus-negative sentiment.",
            "Useful subtype split: emotion_state, emotion_shift, and atmosphere differ in target selection, evidence shape, and choice construction.",
            "Recommended broad-key policy for now: keep one broad key, `mood_atmosphere`, and differentiate early support through subtype-aware prompts and later format_key variants rather than three live registry keys immediately.",
            "Recommended first rollout: emotion_shift first, then atmosphere; emotion_state can follow once target-clarity and answer-choice distinctiveness are reliable.",
            "Useful explanation standard: cite concrete cue phrases such as reactions, setting details, or turning events rather than only naming the final affect label.",
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


LIVE_TYPE_REFINEMENTS: tuple[PendingQuestionTypeSpec, ...] = (
    PendingQuestionTypeSpec(
        broad_key="sentence_insertion",
        label_ko="문장 삽입",
        format_key="sentence_insertion_5_gaps",
        stem_direction_ko=(
            "Keep the current Korean stem, but move explanation quality away "
            "from generic '흐름상 자연스럽다' phrasing and toward explicit "
            "left-context plus right-context evidence."
        ),
        expected_output_shape=(
            "Current rendered shape remains valid: removed target sentence as "
            "given sentence, five marker positions, marker answer ①-⑤, Korean "
            "explanation."
        ),
        infrastructure="sentence",
        likely_incompatibility_patterns=(
            "Target candidate has only one-sided linkage and does not create a recoverable coherence gap.",
            "Target candidate is first or last in the source order and lacks one side of anchoring evidence.",
            "Target candidate is mostly a connector cue with weak lexical or referential support.",
        ),
        implementation_risks=(
            "Current planner may overvalue local connector cues instead of two-sided coherence repair evidence.",
            "Current explanations may leak engine mechanics such as gap IDs instead of teacher-facing textual reasoning.",
            "If future quality gates become too strict too early, valid but simpler sentence-insertion items may be over-rejected.",
        ),
        notes=(
            "Useful external guidance: treat sentence insertion as a coherence-repair task, not a connector-matching task.",
            "Useful next-step heuristic: require at least one left anchor and one right anchor when selecting strong target sentences.",
            "Useful explanation standard: cite concrete phrases or discourse links on both sides of the insertion point.",
            "Useful low-quality signal: connector-only evidence without stronger referential, lexical, or discourse support.",
            "Not yet adopted as schema truth: full evidence object taxonomies, difficulty scoring, or mandatory wrong-gap notes for every distractor.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="paragraph_ordering",
        label_ko="글의 순서",
        format_key="abc_ordering_after_intro",
        stem_direction_ko=(
            "Keep the current Korean stem, but improve explanation quality so "
            "it explains why the intro leads into the first block and why each "
            "subsequent block follows through adjacency evidence."
        ),
        expected_output_shape=(
            "Current rendered shape remains valid: fixed intro, three shuffled "
            "continuation blocks labeled (A)(B)(C), five ordering choices, "
            "marker answer ①-⑤, Korean explanation."
        ),
        infrastructure="block",
        likely_incompatibility_patterns=(
            "Passage can be partitioned into blocks, but the first continuation block is not clearly recoverable after the intro.",
            "Blocks behave like parallel examples or independently movable summaries, so more than one order feels acceptable.",
            "Ordering depends mostly on a single connector cue with weak referential or lexical support across edges.",
        ),
        implementation_risks=(
            "Current planner may overaccept mechanically contiguous block splits that are structurally legal but weak as exam items.",
            "Current explanations may summarize the original order without showing why each adjacency link is forced.",
            "If future quality gates demand too much explicit evidence too soon, simpler but valid ordering items may be rejected.",
        ),
        notes=(
            "Useful external guidance: treat ordering as adjacency reconstruction rather than generic topic matching.",
            "Useful next-step heuristic: require a clear intro-to-first-block link plus evidence for each correct block-to-block edge.",
            "Useful low-quality signal: chunk sets that look like parallel examples or interchangeable subpoints.",
            "Useful explanation standard: explain the order edge by edge instead of only restating that the whole sequence is natural.",
            "Useful rendering direction to consider later: choose wrong options more diagnostically rather than omitting one permutation arbitrarily.",
            "Not yet adopted as schema truth: structured adjacency-evidence objects, per-wrong-order notes, difficulty scoring, or a separate live sentence_ordering registry key.",
        ),
    ),
)
