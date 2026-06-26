"""Planning artifact for family refinement and deferred architecture work.

This file is intentionally outside the live runtime registry. It records the
current planning state for live-family hardening, dormant families, and future
architecture work without changing `src/questiongen/QUESTION_TYPES` or any
launcher behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FamilyStatus = Literal["live_refinement", "dormant", "future_candidate"]
InfrastructureKind = Literal["sentence", "block", "span", "multi_span", "passage"]


@dataclass(frozen=True)
class PlanningFamilySpec:
    broad_key: str
    status: FamilyStatus
    label_ko: str
    format_or_scope: str
    infrastructure: InfrastructureKind
    current_role: str
    likely_incompatibility_patterns: tuple[str, ...]
    quality_risks: tuple[str, ...]
    notes: tuple[str, ...] = ()
    requires_user_confirmation: tuple[str, ...] = ()


PLANNING_CONTEXT = {
    "status": "planning_only",
    "do_not_import_into_runtime": True,
    "canonical_doc": "docs/question_types_pending.md",
    "sync_rule": (
        "Keep this file and docs/question_types_pending.md aligned whenever the "
        "planning stance or live-family status changes."
    ),
    "product_direction": (
        "Colab-first launcher, Drive-backed runtime data, run all registered "
        "question types, and preserve valid-but-poor-fit combinations as "
        "qtype_incompatibility_error."
    ),
    "live_question_type_keys": (
        "sentence_insertion",
        "paragraph_ordering",
        "underlined_phrase_meaning",
        "fill_in_the_blank",
        "vocab",
        "grammar",
    ),
    "dormant_implemented_question_type_keys": ("mood_atmosphere",),
    "default_model_policy": "gpt-5-mini shared default; per-type routing deferred.",
    "boundary_policy": (
        "Default future meaning or pragmatics boundary cases to vocab; keep "
        "grammar focused on local structural or form error detection."
    ),
    "review_artifact_policy": (
        "Checked-in review artifacts and ResponseFeedbackDump are useful logic "
        "review and prioritization evidence, but not runtime-contract truth."
    ),
    "next_architecture_gate": (
        "Land planner-stage observability and timeout hardening before starting "
        "the deferred shared intermediate design-layer refactor."
    ),
    "deferred_graph_shape": (
        "prepare -> source gate -> design/candidate stage -> final planner -> "
        "deterministic plan check -> render -> explanation -> final validate"
    ),
    "subagent_default_role": (
        "Read-only design and review helper by default. Subagents may analyze, "
        "summarize, and draft planning artifacts, but they should not edit "
        "runtime code, tests, launcher notebooks, or registry wiring unless the "
        "lead agent assigns that scope explicitly."
    ),
    "subagent_allowed_planning_write_scope": (
        "question_types_pending.py",
        "docs/question_types_pending.md",
        "IMPLEMENTATION_PLAN.md",
        "docs/live_quality_review.md",
        "docs/launcher_contract.md",
    ),
    "subagent_must_not": (
        "commit",
        "push",
        "merge",
        "change QUESTION_TYPES by default",
        "edit src/questiongen by default",
    ),
    "lead_agent_owns": (
        "final integration decisions",
        "doc drift checks",
        "git staging review",
        "commit and push hygiene",
    ),
}


PLANNING_FAMILIES: tuple[PlanningFamilySpec, ...] = (
    PlanningFamilySpec(
        broad_key="sentence_insertion",
        status="live_refinement",
        label_ko="문장 삽입",
        format_or_scope="sentence_insertion_5_gaps",
        infrastructure="sentence",
        current_role="Live family; ongoing quality hardening and observability target.",
        likely_incompatibility_patterns=(
            "Target candidate has only one-sided linkage and does not create a recoverable coherence gap.",
            "Target candidate is first or last in the source order and lacks one side of anchoring evidence.",
            "Target candidate is mostly a connector cue with weak lexical, referential, or discourse support.",
        ),
        quality_risks=(
            "Planner may still overvalue local connector cues instead of two-sided coherence repair evidence.",
            "Accepted explanations can still sound templated even after internal-ID cleanup.",
            "Future candidate-design layering should not start before planner observability and timeout hardening land.",
        ),
        notes=(
            "Treat the family as coherence repair rather than connector matching.",
            "Prefer target sentences with evidence on both the left and right sides.",
            "When the shared design layer is revisited later, sentence_insertion is a likely early adopter after vocab.",
        ),
    ),
    PlanningFamilySpec(
        broad_key="paragraph_ordering",
        status="live_refinement",
        label_ko="글의 순서",
        format_or_scope="abc_ordering_after_intro",
        infrastructure="block",
        current_role="Live family; strongest current hardening target among the older live families.",
        likely_incompatibility_patterns=(
            "Passage can be partitioned into blocks, but the first continuation block is not clearly recoverable after the intro.",
            "Blocks behave like parallel examples or independently movable summaries, so more than one order feels acceptable.",
            "Ordering depends mostly on a single connector cue with weak referential or lexical support across edges.",
        ),
        quality_risks=(
            "Planner may still overaccept mechanically contiguous block splits that are structurally legal but weak as exam items.",
            "Accepted explanations may summarize the passage instead of proving each adjacency edge.",
            "Without better planner logs, long or repeated planning attempts are hard to diagnose from the UI spinner alone.",
        ),
        notes=(
            "Treat the family as adjacency reconstruction rather than topic matching.",
            "Weak-adjacency passages should fail earlier as qtype_incompatibility_error rather than reach late planning_error.",
            "When the shared design layer is revisited later, paragraph_ordering is a likely early adopter after vocab.",
        ),
    ),
    PlanningFamilySpec(
        broad_key="underlined_phrase_meaning",
        status="live_refinement",
        label_ko="밑줄 친 부분 의미",
        format_or_scope="underlined_phrase_meaning_5_ko",
        infrastructure="span",
        current_role="Live reference single-span family; no longer a pending registry candidate.",
        likely_incompatibility_patterns=(
            "Best candidate phrase is too literal and becomes a dictionary-definition target.",
            "Selected phrase is not central enough to the passage claim or argument.",
            "More than one Korean paraphrase remains defensible after rendering.",
        ),
        quality_risks=(
            "Korean distractors may still drift toward near-duplicates.",
            "Span-centrality heuristics can still admit weakly claim-bearing phrases on mixed batches.",
            "Future CSV-driven target selection, if added later, would need a separate contract update.",
        ),
        notes=(
            "Treat the family as contextual paraphrase, not literal translation.",
            "Use it as the stable single-span reference point when evaluating later blank or multi-span work.",
        ),
    ),
    PlanningFamilySpec(
        broad_key="fill_in_the_blank",
        status="live_refinement",
        label_ko="빈칸",
        format_or_scope=(
            "blank_inference_proposition_5_choices, "
            "blank_connective_relation_5_choices, "
            "blank_summary_completion_5_choices"
        ),
        infrastructure="span",
        current_role="Live family; harden subtype quality rather than reopen registry shape.",
        likely_incompatibility_patterns=(
            "No recoverable proposition-like or relation-bearing span can be blanked cleanly.",
            "Blanking the selected span leaves multiple defensible completions.",
            "The best removable unit collapses into easy lexical deletion instead of real inference.",
        ),
        quality_risks=(
            "Distractor quality dominates usefulness and may still be too local or too obvious.",
            "Planner may drift toward source restoration or vocabulary-style deletion unless subtype prompts stay sharp.",
            "Explanation phrasing can still regress into awkward memo-style Korean if not cleaned deterministically.",
        ),
        notes=(
            "Keep the broad key as fill_in_the_blank and keep subtype behavior in format/subtype metadata.",
            "Treat the family as proposition or relation reconstruction, not generic deletion.",
        ),
    ),
    PlanningFamilySpec(
        broad_key="vocab",
        status="live_refinement",
        label_ko="어휘",
        format_or_scope=(
            "contextual_vocab_choice_5; contextual_vocab_best_paraphrase_choice_5; "
            "contextual_vocab_phrase_choice_5; contextual_vocab_correct_among_4_corrupted_5; "
            "contextual_vocab_error_1_among_5_5; contextual_vocab_error_1_among_5_polarity_scope_5; "
            "contextual_vocab_error_1_among_5_collocation_5; contextual_vocab_correct_among_3_corrupted_5"
        ),
        infrastructure="multi_span",
        current_role="Live multi-subtype family and first planned adopter of any future shared design stage.",
        likely_incompatibility_patterns=(
            "Too few clean lexical-slot candidates exist for the requested subtype shape.",
            "The passage does not constrain the target strongly enough to force one best contextual answer.",
            "Hard underlined variants leave more than one plausible survivor or accept wrong corruption classes.",
        ),
        quality_risks=(
            "Blank-choice targets can still be too local or too easy.",
            "Best-paraphrase and correct-among-3-corrupted remain the highest ambiguity-risk branches.",
            "Hard-family rows need continued exam-naturalness review even after the schema rescue.",
        ),
        notes=(
            "Boundary policy: keep meaning, direction, scope, pragmatic force, and best-fit replacement tasks under vocab by default.",
            "Preserve the useful ResponseFeedbackDump lessons that still survive: semantic pressure-point targeting, directional or pragmatic targeting, changed-from-source-but-still-correct design, stem-task alignment, and a future internal design-stage artifact.",
            "Reject stale subtype-pruning claims that were driven by the old hard-vocab schema failure.",
        ),
    ),
    PlanningFamilySpec(
        broad_key="grammar",
        status="live_refinement",
        label_ko="어법",
        format_or_scope=(
            "grammar_error_verb_form_5; grammar_error_subject_verb_agreement_5; "
            "grammar_error_finite_nonfinite_5; grammar_error_participle_voice_5; "
            "grammar_error_relative_clause_5; grammar_error_noun_clause_introducer_5; "
            "grammar_error_parallel_structure_5; grammar_error_conjunction_preposition_5"
        ),
        infrastructure="multi_span",
        current_role="Live multi-subtype family with strict structural-signal ownership.",
        likely_incompatibility_patterns=(
            "Too few clean grammar-bearing targets exist for a five-target item.",
            "No single corruption is provable from local structural cues without creating multiple valid corrections.",
            "The apparent error drifts into meaning-direction or vocabulary judgment instead of structure error.",
        ),
        quality_risks=(
            "Structural corruptions can become too obvious or too semantically disruptive.",
            "Teacher-facing explanations must stay structural rather than devolving into label-only rule naming.",
            "Boundary drift from grammar into vocab remains a recurring design risk for function-word cases.",
        ),
        notes=(
            "Boundary policy: keep grammar focused on local structural and form error detection.",
            "Do not pull modal force, negation scope, causal direction, or pragmatic function-word meaning traps into grammar merely because a function word is involved.",
        ),
    ),
    PlanningFamilySpec(
        broad_key="mood_atmosphere",
        status="dormant",
        label_ko="심경·분위기",
        format_or_scope="emotion_shift_pair_choice_5; emotion_state_choice_5; atmosphere_choice_5",
        infrastructure="passage",
        current_role="Implemented but intentionally dormant outside the live registry.",
        likely_incompatibility_patterns=(
            "Informational or expository passages with no stable affective cues.",
            "Passages with no single clear feeling-holder.",
            "Passages that contain affective language but no real initial-to-final emotional change.",
        ),
        quality_risks=(
            "Choice sets can collapse into near-synonym pairs unless direction and endpoint distinctions stay sharp.",
            "Exported explanations can become generic unless they cite concrete initial and final evidence plus the turning point.",
            "Reactivation now would reopen a broad suitability and explanation-quality problem with weaker ROI than current live-family hardening.",
        ),
        notes=(
            "Keep the implementation code in the repo but keep the family out of QUESTION_TYPES and launcher-derived defaults.",
            "If reactivated later, start from emotion_shift before returning to emotion_state or atmosphere.",
        ),
        requires_user_confirmation=(
            "Revisit this family only after the active families are materially hardened and the user explicitly confirms a return.",
        ),
    ),
)
