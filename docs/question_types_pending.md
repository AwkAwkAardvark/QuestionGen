# Question Type Status And Planning Notes

This document is a planning and status reference. It does not override the live runtime registry in `src/questiongen/question_types.py`, the launcher contract, or the implementation plan.

Status snapshot: `2026-07-09`

## Live Families

The current live registry is:

- `sentence_insertion`
- `paragraph_ordering`
- `underlined_phrase_meaning`
  - `underlined_phrase_meaning_5_ko`
- `fill_in_the_blank`
  - `blank_inference_proposition_5_choices`
  - `blank_connective_relation_5_choices`
  - `blank_summary_completion_5_choices`
- `vocab`
  - `contextual_vocab_choice_5`
  - `contextual_vocab_best_paraphrase_choice_5`
  - `contextual_vocab_phrase_choice_5`
  - `contextual_vocab_correct_among_4_corrupted_5`
  - `contextual_vocab_error_1_among_5_5`
  - `contextual_vocab_error_1_among_5_polarity_scope_5`
  - `contextual_vocab_error_1_among_5_collocation_5`
  - `contextual_vocab_correct_among_3_corrupted_5`
- `grammar`
  - `grammar_error_verb_form_5`
  - `grammar_error_subject_verb_agreement_5`
  - `grammar_error_finite_nonfinite_5`
  - `grammar_error_participle_voice_5`
  - `grammar_error_relative_clause_5`
  - `grammar_error_noun_clause_introducer_5`
  - `grammar_error_parallel_structure_5`
  - `grammar_error_conjunction_preposition_5`

## Dormant Implemented Family

- `mood_atmosphere`
  - implemented in code
  - intentionally excluded from the live default registry
  - should stay dormant until the active live families stabilize further and the user explicitly confirms reactivation

## Current Product Direction

- Treat Colab as the primary launcher surface.
- Treat Google Drive as the user-controlled storage layer for inputs, outputs, and `api_key.txt`.
- Keep `src/questiongen/` notebook-agnostic, Drive-agnostic, and secret-source agnostic.
- Keep launcher behavior centered on running all registered live families automatically.
- Surface valid but poor-fit passage/type combinations as `qtype_incompatibility_error`.
- Keep the current quality stance quality-first rather than coverage-first; it is acceptable for pass rates to drop when ambiguous or unsafe rows are converted into explicit failures.
- Keep `gpt-5-mini` as the current default model, with only narrow planner-local routing where already documented elsewhere.

## Family Boundary Notes

### `vocab` vs `grammar`

Use this ownership rule consistently:

- `vocab` owns contextual meaning, semantic direction, pragmatic force, best-fit replacement, polarity/scope drift, and similar lexical-interpretation tasks.
- `grammar` owns local structural or form-error detection such as agreement, finite/nonfinite control, participle/voice, clause linkage, and parallelism.

Default boundary examples:

- Keep modal-force contrasts such as `must`, `must not`, `don't have to`, `should`, and `may` under `vocab` when the task is about contextual force rather than formal licensing.
- Keep negation, scope, and degree contrasts under `vocab` when the point is semantic direction.
- Keep conjunction or preposition governance under `grammar` only when the failure is mainly structural rather than semantic-force-based.

## Current Planning Focus

The remaining planning focus is not new family expansion. It is live-family hardening and review quality.

Current priorities:

1. Keep pushing weak live items into earlier deterministic rejection rather than late planner noise.
2. Re-baseline `vocab`, `fill_in_the_blank`, and `grammar` against fresh current-code exports rather than stale historical artifacts.
3. Keep explanation cleanup tied to rendered evidence and subtype-specific contracts instead of planner memo text.
4. Avoid reopening registry reshaping or export-schema redesign during routine quality passes.

## Deferred Expansion Notes

These are future directions only. They are not pending activation checklists.

### `fill_in_the_blank`

Potential later expansion areas:

- additional connective or discourse-role variants
- narrower summary variants
- lexical or grammar-adjacent blank modes only if they justify distinct infrastructure or launch behavior

Keep the broad family key as `fill_in_the_blank` unless future product requirements clearly need separate launcher behavior.

### `vocab`

Potential later expansion areas:

- stronger phrase-focused contextual substitution beyond the current phrase-choice subtype
- narrower hard underlined corruption families if one subtype eventually needs a distinct runtime contract
- stricter best-paraphrase variants if later review shows a recurring need for them

Keep `vocab` as the broad family key and keep subtype behavior in `QuestionSubtypeKey` unless a new family truly needs different launcher treatment.

### `grammar`

Potential later expansion areas:

- further hardening within the current live subtype set before any broader grammar-family redesign
- additional controlled subtypes only if they stay subtle, teacher-explainable, and structurally grounded

Keep `grammar` as the broad family key and avoid reintroducing the old single-format `grammar_error_5` framing.

### `mood_atmosphere`

Reactivation conditions:

- only after the current live families are materially more stable
- only after the user explicitly confirms it is worth reviving
- only with clear explanation-quality expectations and suitability gates

## Planning Artifact Role

- This file should stay current on live family status, dormant family status, boundary policy, and deferred-direction notes.
- Historical rollout narration and completed milestone detail belong in `IMPLEMENTATION_PLAN.md`.
- Review evidence and artifact interpretation belong in `docs/live_quality_review.md`.
- Launcher and Colab/Drive behavior belong in `docs/launcher_contract.md`.

If this file starts accumulating branch-specific history again, move that history into the implementation plan or a dated review doc instead of letting this status reference drift.
