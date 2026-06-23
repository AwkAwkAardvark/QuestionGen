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
    "live_question_type_keys": ("sentence_insertion", "paragraph_ordering", "underlined_phrase_meaning"),
    "next_registry_gate": (
        "Do not add fill_in_the_blank to the live registry until the current "
        "gpt-5-mini baseline for sentence_insertion, paragraph_ordering, and "
        "underlined_phrase_meaning is stable again on mixed-batch review."
    ),
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
        broad_key="fill_in_the_blank",
        label_ko="빈칸",
        format_key="blank_inference_proposition_5_choices",
        stem_direction_ko=(
            "Likely first stem: '다음 빈칸에 들어갈 말로 가장 적절한 것은?' "
            "Treat the first implementation as 빈칸추론 rather than a generic "
            "blank. Keep the exact blank span shape open until the first "
            "supported proposition granularity is confirmed."
        ),
        expected_output_shape=(
            "One source passage with one selected proposition-like span "
            "replaced by a blank; five answer choices; marker answer ①-⑤; "
            "Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages with no recoverable proposition that can be reconstructed from context.",
            "Passages where blanking a span creates multiple defensible answers.",
            "Passages whose best removable unit is too short and becomes vocabulary-like rather than inferential.",
            "Passages whose best removable unit is too long or too structurally messy for a clean one-blank format.",
            "Passages where the answer would be copied too directly from nearby text instead of requiring paraphrase or inference.",
        ),
        implementation_risks=(
            "The shared span-preparation layer now exists, but blank-specific planner calibration for gpt-5-mini is still pending.",
            "Distractor quality will dominate item usefulness and may require explicit polarity, scope, and logic-aware validation.",
            "Blank placement must match 수능/내신 expectations rather than arbitrary deletion.",
            "The planner may drift toward easy lexical deletion unless the prompt anchors it to proposition reconstruction.",
        ),
        requires_user_confirmation=(
            "Confirm when the current gpt-5-mini live baseline is strong enough to resume blank rollout work.",
        ),
        notes=(
            "Current locked next-pass direction: keep the broad key as `fill_in_the_blank`.",
            "Current locked first format: `blank_inference_proposition_5_choices`.",
            "Current locked first release scope: strict proposition-level 빈칸추론 only.",
            "Do not add this family to QUESTION_TYPES during the current stabilization pass.",
            "Do not force this into the current sentence/gap pipeline.",
            "Depends on span IDs and span-preserving rendering.",
            "Useful external guidance: treat the first blank type as missing-proposition reconstruction, not generic word deletion.",
            "Useful role model: blank targets should usually act as a claim, conclusion, mechanism, contrast, limitation, or similar discourse function.",
            "Useful evidence standard: support the answer with multiple clues, ideally including evidence before and after the blank.",
            "Useful choice-quality direction: distractors should often be near-topic but wrong in polarity, scope, relation, or paraphrase accuracy.",
            "Recommended broad-key policy for now: keep one broad key, `fill_in_the_blank`, and place the first supported subtype in `format_key` rather than splitting into multiple live registry keys immediately.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="underlined_phrase_meaning",
        label_ko="밑줄 친 부분 의미",
        format_key="underlined_phrase_meaning_5_ko",
        stem_direction_ko=(
            "Likely first stem: '다음 글의 밑줄 친 부분의 의미로 가장 적절한 것은?' "
            "Treat this as contextual meaning / 함축 의미 추론 rather than "
            "literal translation."
        ),
        expected_output_shape=(
            "Original passage with one underlined English phrase; five Korean "
            "contextual paraphrase choices; marker answer ①-⑤; Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages whose best candidate phrase is too literal and becomes a dictionary-definition target.",
            "Passages whose underlined phrase is not central to the passage claim or argument.",
            "Passages with multiple acceptable Korean paraphrases and weak one-best-answer pressure.",
            "Idiomatic or figurative phrases whose interpretation depends mainly on outside knowledge rather than passage evidence.",
        ),
        implementation_risks=(
            "Needs span selection that respects contextual meaning rather than dictionary glossing.",
            "Korean answer choices need normalization rules to avoid near-duplicate valid answers.",
            "The planner may drift toward pure vocabulary or idiom-memory questions unless the prompt anchors interpretation to passage-level evidence.",
            "Future optional CSV-driven target-span input may change the interface, so keep v1 assumptions explicit.",
        ),
        requires_user_confirmation=(
            "Confirm whether the pending family should be renamed from the older phrase_translation draft to underlined_phrase_meaning before implementation begins.",
            "Confirm whether the first release should always self-select the underlined phrase from the source paragraph.",
            "Confirm whether the first release should prioritize metaphorical / abstract phrases over simpler evaluative phrases.",
        ),
        notes=(
            "Useful external guidance: this type is a contextual paraphrase task, not a literal translation task.",
            "Useful target standard: choose a phrase with a recoverable bridge from surface wording to passage-level meaning.",
            "Useful explanation standard: explain 'surface image -> contextual meaning -> supporting evidence' rather than giving a bare gloss.",
            "Recommended family rename before implementation: `underlined_phrase_meaning` fits the intended Korean exam task better than `phrase_translation`.",
            "Span-based but usually simpler than vocab or grammar because only one target is rendered.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="vocab",
        label_ko="어휘",
        format_key="contextual_vocab_error_5",
        stem_direction_ko=(
            "Likely first stem: '다음 글의 밑줄 친 부분 중, 문맥상 낱말의 쓰임이 "
            "적절하지 않은 것은?' Treat the first implementation as a "
            "contextual lexical-fit task, not a definition task."
        ),
        expected_output_shape=(
            "Original passage with five numbered underlined targets; one "
            "target deterministically replaced with a grammatically possible "
            "but contextually wrong word or short phrase; marker answer ①-⑤; "
            "Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages without five clean lexical targets worth underlining.",
            "Passages where no candidate word is strongly constrained by passage logic.",
            "Passages where a wrong replacement becomes obviously impossible rather than plausibly testable.",
            "Passages whose key vocabulary is too technical, culture-bound, or semantically flat for this format.",
            "Passages where multiple underlined words could plausibly be disputed once one corruption is inserted.",
        ),
        implementation_risks=(
            "Requires multi-span preparation and deterministic replacement rendering.",
            "Replacement candidates must be plausible enough for exam quality but still clearly wrong in context.",
            "The planner may drift toward dictionary-difficulty words unless the prompt anchors it to passage-level logic and expected meaning.",
            "Validation likely needs lexical and grammatical sanity checks beyond current types, including part-of-speech preservation and single-answer uniqueness.",
        ),
        requires_user_confirmation=(
            "Confirm whether the first release should allow short phrases as well as single-word targets.",
        ),
        notes=(
            "Useful external guidance: treat this as contextual lexical-fit, not vocabulary-definition recall.",
            "Useful first-format direction: one underlined item should be intentionally corrupted while four other underlined items remain contextually appropriate.",
            "Useful evidence standard: prove the expected meaning from polarity, logic, semantic role, or broader discourse flow rather than from a bare dictionary gloss.",
            "Recommended broad-key policy for now: keep one broad key, `vocab`, and place the first supported subtype in `format_key` rather than splitting into multiple live registry keys immediately.",
            "Should come after phrase-level span tooling is stable.",
        ),
    ),
    PendingQuestionTypeSpec(
        broad_key="grammar",
        label_ko="어법",
        format_key="grammar_error_5",
        stem_direction_ko=(
            "Likely first stem: '다음 글의 밑줄 친 부분 중, 어법상 틀린 것은?' "
            "Treat the first implementation as sentence-structure integrity, "
            "not isolated rule recall."
        ),
        expected_output_shape=(
            "Original passage with five numbered underlined grammar-bearing "
            "targets; one target replaced with a plausible-looking but "
            "structurally wrong form; marker answer ①-⑤; Korean explanation."
        ),
        infrastructure="span",
        likely_incompatibility_patterns=(
            "Passages without five stable grammar targets suitable for underlining.",
            "Passages where no grammar-bearing structure is constrained clearly enough for one provable corruption.",
            "Passages where a wrong inflection or construction would sound too obviously broken.",
            "Passages where multiple grammar points compete and reduce one-best-answer clarity.",
            "Passages where the corruption would drift into vocabulary meaning change rather than structure error.",
        ),
        implementation_risks=(
            "Most fragile of the current span-based candidates because the error must be subtle, local, and explainable.",
            "Requires grammar-aware replacement planning, not just surface word substitution.",
            "Validation will likely need explicit checks for readability, unique correction, and grammar-versus-vocab boundary.",
            "High risk of accidental semantic distortion or multiple valid corrections.",
        ),
        requires_user_confirmation=(
            "Confirm the preferred first grammar error family, if the release should narrow scope initially.",
        ),
        notes=(
            "Useful external guidance: treat this as sentence-structure integrity, not rule-quiz memorization.",
            "Useful first-format direction: introduce one controlled structural corruption while four other underlined grammar-bearing parts remain valid.",
            "Useful target families for the first pass include subject-verb agreement, finite versus nonfinite form, participle/voice relation, relative-clause structure, noun-clause introducers, parallel structure, and conjunction-versus-preposition contrasts.",
            "Useful evidence standard: explanations should point to the true subject, clause role, modifier boundary, antecedent, or other structural cue rather than only naming a grammar rule.",
            "Recommended broad-key policy for now: keep one broad key, `grammar`, and place the first supported subtype in `format_key` rather than splitting into multiple live registry keys immediately.",
            "Likely the last of the currently discussed candidates to implement.",
        ),
    ),
)


LIVE_TYPE_REFINEMENTS: tuple[PendingQuestionTypeSpec, ...] = (
    PendingQuestionTypeSpec(
        broad_key="mood_atmosphere",
        label_ko="심경·분위기",
        format_key="emotion_shift_pair_choice_5",
        stem_direction_ko=(
            "Keep the broad family key, but make the first live rollout "
            "subtype-specific: use an emotion-shift stem rather than a generic "
            "심경·분위기 stem."
        ),
        expected_output_shape=(
            "Current live shape for v1: original passage preserved unchanged, "
            "five English emotion-shift pair choices, marker answer ①-⑤, and "
            "teacher-facing Korean explanation."
        ),
        infrastructure="passage",
        likely_incompatibility_patterns=(
            "Informational or expository passages with no stable affective cues.",
            "Passages with no single clear feeling-holder.",
            "Passages that contain affective language but no real initial-to-final emotional change.",
        ),
        implementation_risks=(
            "Planner may still force emotion labels onto weakly affective passages unless incompatibility gating stays strict.",
            "Choice sets can collapse into near-synonym pairs unless prompt and validation keep direction and endpoint distinctions sharp.",
            "Exported explanations can become generic unless they cite concrete initial/final evidence and the turning point.",
        ),
        notes=(
            "Chosen first-rollout policy: broad key stays `mood_atmosphere`, live subtype is only `emotion_shift` for now.",
            "Chosen v1 choice policy: use English adjective-pair choices such as `anxious -> relieved`.",
            "Chosen target policy: allow writer/narrator or one clearly identifiable character, but reject passages with ambiguous holders.",
            "Deferred subtypes: `atmosphere` and `emotion_state` stay out of the live registry until v1 suitability and explanation quality are stable.",
        ),
    ),
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
