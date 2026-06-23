# QuestionGen Implementation Plan

## Core Direction

- [x] Keep the backend centered on `planning -> deterministic rendering -> validation`.
- [x] Keep `src/questiongen/` notebook-agnostic and Drive-agnostic.
- [x] Keep model construction outside the batch layer through an injected runner.
- [x] Treat Colab as the primary user-facing launcher surface.
- [x] Treat Google Drive as the user-controlled storage layer for inputs, outputs, and `api_key.txt`.
- [x] Keep Gradio out of the current implementation scope.
- [x] Design the user-facing flow around "run all registered question types" rather than manual type selection.
- [x] Preserve failed type/passage combinations as exported results with readable `status` and `errors`.
- [x] Treat question-type incompatibility as a first-class expected outcome rather than forcing it into generic planner/source failure labels.
- [x] Use CSV and JSON as the primary debug artifacts once orchestration/export work is complete.
- [x] Ship one cheaper default model first: `gpt-5-mini`.
- [x] Defer per-question-type model routing until after the live pipeline is stable.
- [x] Keep the current batch execution path synchronous and serial; defer async or concurrent orchestration as a later performance-only track.
- [x] Keep broad family keys as the launcher/UI selection surface while expanding execution into concrete subtype rows underneath each family.
- [x] Preserve subtype metadata in runtime state and exports through `QuestionFormatKey`, `QuestionSubtypeKey`, and `QuestionSubtype`.

## Wave 1: Backend Foundation

### Package and pipeline

- [x] Create the installable package skeleton and `pyproject.toml`.
- [x] Define typed schemas for source units, gaps, plans, generated questions, batch rows, and pipeline state.
- [x] Implement sentence parsing, normalization, and explicit gap construction.
- [x] Implement shallow input validation and prepared-source eligibility checks.
- [x] Implement `sentence_insertion` planning with structured output.
- [x] Implement deterministic `sentence_insertion` rendering.
- [x] Implement final output validation for `sentence_insertion`.
- [x] Build a generic graph runner driven by question type metadata.
- [x] Expose question graph compilation with injected structured LLM creation.

### Batch and exports

- [x] Implement row-based batch execution with an injected runner.
- [x] Implement DataFrame and file-based batch adapters.
- [x] Implement CSV export for batch results.
- [x] Implement Markdown export for human review.
- [x] Add script-level demo and real-batch runner entrypoints.

### Verification

- [x] Add unit coverage for parser behavior.
- [x] Add unit coverage for planner behavior.
- [x] Add unit coverage for renderer behavior.
- [x] Add unit coverage for validator behavior.
- [x] Add unit coverage for batch behavior and per-row failure capture.

## Wave 2: Colab Product Launcher

### Launcher responsibilities

- [x] Create the canonical Colab notebook launcher.
- [x] Mount Google Drive from the notebook layer only.
- [x] Load `api_key.txt` from Drive and populate environment variables in the notebook layer only.
- [x] Define notebook-level input and output Drive paths.
- [x] Construct the structured LLM-backed runner from the notebook layer.

### Separation guarantees

- [x] Keep `google.colab` imports out of `src/questiongen/`.
- [x] Keep Drive path assumptions out of `src/questiongen/`.
- [x] Keep secret-file loading out of `src/questiongen/`.
- [x] Document the launcher contract so the Drive-backed secret model is explicit.

## Wave 3: User-Facing Orchestration and Debug Exports

### Orchestration

- [x] Add a thin orchestration layer that derives all registered question types automatically.
- [x] Run every registered question type for every input passage.
- [x] Preserve unsupported or poor-fit type/passage combinations as explicit failed results.
- [x] Keep the low-level batch API explicit even after the higher-level launcher flow exists.

### Export surface

- [x] Add JSON export using the same `BatchResultRow` payloads used for CSV.
- [x] Keep CSV as the operator-friendly spreadsheet artifact.
- [x] Keep Markdown optional and secondary during debugging.
- [x] Ensure failed rows remain diagnosable from exported artifacts without hidden filtering.

## Wave 4: Live Type Expansion and Hardening

### Shared multi-type groundwork

- [x] Add additional registered question types beyond `sentence_insertion`.
- [x] Add broad registry keys plus `format_key`-level first supported formats for Wave 4 types.
- [x] Reuse the same planner-renderer-validator architecture per new type.
- [x] Introduce `qtype_incompatibility_error` for passages that are valid inputs but not suitable for a given question type.
- [x] Ensure "all registered types" automatically expands as the registry grows.
- [x] Keep type-specific failure modes readable in shared exports.
- [x] Split source provenance from internal deterministic row identity so `OriginalQuestionNumber` can remain an opaque label and `BatchRowId` can drive internal ordering behavior.
- [x] Keep exported explanations teacher-facing by rejecting internal `S#` / `G#` notation and schema-mechanics language.
- [x] Separate teacher-facing explanation generation from structural planning so explanation writing can use post-render textual evidence rather than planner-internal notation.
- [x] Make sentence parsing abbreviation-safe and reject fragmentary sentence units before they leak into live question families.
- [x] Harden `sentence_insertion` so weak one-sided targets fail deterministically and explanations rely on left/right context rather than on the given sentence itself.
- [x] Harden `paragraph_ordering` so weakly forced or parallel-example block splits fail deterministically and explanations justify adjacency edge by edge.
- [x] Harden `underlined_phrase_meaning` so literal, fragmentary, and weakly central spans fail earlier in the pipeline.
- [x] Refine fragment detection so complete finite clauses with terminal stranded prepositions do not surface as false `source_error` rows.
- [x] Recalibrate live planner prompt surfaces for `gpt-5-mini` so inventories expose ranked evidence rather than raw IDs alone.
- [x] Keep upstream LLM service failures, including `insufficient_quota`, under `planning_error` without adding a new exported status.
- [x] Stop further batch-wide LLM planning attempts after the first detected `insufficient_quota` while still exporting every row/type combination.
- [x] Treat quota-driven `planning_error` rows as operational failures rather than as live-family quality evidence during mixed-batch audits.

### Live families already shipped

- [x] `sentence_insertion`
  - status: live
  - first supported format: `sentence_insertion_5_gaps`
  - remaining hardening focus: stronger two-sided evidence selection and less templated explanation prose
- [x] `paragraph_ordering`
  - status: live
  - first supported format: `abc_ordering_after_intro`
  - remaining hardening focus: better semantic suitability gating and more edge-by-edge ordering explanations

### Remaining registry work

- [x] Once Wave 4 formats are fully implemented and their contents have been absorbed into durable docs/specs, ask for explicit confirmation before deleting `QuestionTypeDump`.


## Wave 5: Span Infrastructure

### Shared span-preparation layer

- [x] Introduce a real span-oriented preparation layer that can support both single-span selection and later multi-span rendering.
- [x] Keep the span layer notebook-agnostic and question-type agnostic in the same way the current sentence/gap preparation is package-local and reusable.
- [x] Define deterministic span identity, source-preserving rendering rules, and validation surfaces before live registration of additional span-based types.
- [x] Preserve the current status boundary:
  - malformed preparation remains `source_error`
  - valid-but-poor-fit passages remain `qtype_incompatibility_error`
  - deterministic post-plan violations remain `planning_error`

### Span-layer acceptance

- [x] Single-span types can render a chosen span without damaging surrounding text.
- [x] Multi-span types can later mark multiple targets deterministically without redefining the base preparation contract.
- [x] Exported explanations can refer to chosen span text and surrounding evidence rather than preparation internals.

## Wave 6: Single-Span Types

### Recommended implementation order

- [x] `underlined_phrase_meaning`
  - reason for order: safest first consumer of the span layer because it needs one selected span and contextual interpretation, but not deletion-based rendering or multi-target corruption
  - first supported format: `underlined_phrase_meaning_5_ko`
  - first-release target: contextual paraphrase / 함축 의미 추론, not literal translation
  - shipped v1 policy: self-select one phrase, prefer abstract or claim-bearing spans, use Korean contextual paraphrase choices, and render `[밑줄]...[/밑줄]` in exports
- [x] `fill_in_the_blank`
  - rollout policy: live now for MVP, even if distractor quality and semantic recoverability remain rough
  - live subtype set:
    - `blank_inference_proposition_5_choices`
    - `blank_connective_relation_5_choices`
    - `blank_summary_completion_5_choices`
  - shipped policy: selected broad-family runs expand to multiple blank subtypes, each with subtype-specific inventories and incompatibility gates

### Single-span acceptance

- [ ] Each family has explicit incompatibility gates beyond raw sentence count.
- [x] Each family has explicit incompatibility gates beyond raw sentence count.
- [x] Each family has one clearly scoped v1 format before any subtype expansion.
- [ ] Each family can pass real mixed-batch review without collapsing into generic planner failures or low-quality choice sets.

## Wave 7: Multi-Span Corruption Types

### Recommended implementation order

- [x] `vocab`
  - rollout policy: live now with broad-key preservation and subtype fan-out
  - live subtype set:
    - `contextual_vocab_error_5`
    - `contextual_vocab_choice_5`
  - shipped policy: broad-family runs now produce both the five-target corruption item and the single-target lexical choice item
  - current hardening policy: renderer, validator, and explanation writer resolve exact source words from selected target IDs, prefer opposition-capable targets through conservative planner hints, and deterministically reject obvious near-synonym corruptions
- [x] `grammar`
  - rollout policy: live now with subtype-specific compatibility gates and batch fan-out
  - live subtype set:
    - `grammar_error_verb_form_5`
    - `grammar_error_subject_verb_agreement_5`
    - `grammar_error_finite_nonfinite_5`
    - `grammar_error_participle_voice_5`
    - `grammar_error_relative_clause_5`
    - `grammar_error_noun_clause_introducer_5`
    - `grammar_error_parallel_structure_5`
    - `grammar_error_conjunction_preposition_5`
  - shipped policy: the broad `grammar` family now expands into multiple controlled subtype rows instead of one generic verb-form row

### Multi-span acceptance

- [ ] The span layer can support numbered multi-target rendering without destabilizing earlier single-span types.
- [x] The validator can prove there is exactly one structurally rendered corruption.
- [ ] Real-batch outputs remain diagnostically readable in CSV/JSON when passages do not fit these families.

## Wave 8: Affective Family

- [x] `mood_atmosphere`
  - status: reactivated in the live registry
  - live subtype set:
    - `emotion_shift_pair_choice_5`
    - `emotion_state_choice_5`
    - `atmosphere_choice_5`
  - shipped policy: broad-family selection stays stable while execution expands into multiple mood/atmosphere subtype rows

## Acceptance Checklist

- [x] The backend package can execute a full question pipeline with an injected runner.
- [x] Batch execution can emit machine-readable review artifacts.
- [x] Batch execution captures per-row failure without aborting the full run.
- [ ] A Colab user can run the system end-to-end using Drive-backed inputs and `api_key.txt`.
- [x] The launcher attempts all registered question types without manual type selection.
- [x] CSV and JSON are both produced for debugging runs.
- [x] Failed type/passage combinations remain visible and readable in exported results.
- [x] The live registry includes `mood_atmosphere`, `fill_in_the_blank`, `vocab`, and `grammar` under subtype-expanded broad families.
- [x] `qtype_incompatibility_error` is distinguishable from malformed-source failure and planner malfunction in exported results.
- [x] `planning_error` continues to cover both planner-quality defects and upstream LLM service failures; quota exhaustion does not introduce a new `PipelineStatus`.

## Stable Interface Commitments

- [x] `run_batch_rows(rows, question_type_keys, runner) -> list[BatchResultRow]`
- [x] `run_batch_dataframe(df, question_type_keys, runner) -> DataFrame`
- [x] `run_batch_files(input_csv, output_csv, question_type_keys, runner, output_markdown=None) -> list[BatchResultRow]`
- [x] `BatchResultRow` remains the canonical exported result model.
- [x] Environment variables remain the final runtime interface to the LLM client.
- [x] Secret acquisition remains a launcher concern, not a package concern.
- [x] `OriginalQuestionNumber` is source provenance, not an internal numeric key.
- [x] `BatchRowId` is the deterministic internal row identifier generated from batch row order and preserved in exports.
- [x] `source_error` remains reserved for malformed or broken prepared sources, while valid-but-unsuitable passages surface as `qtype_incompatibility_error`.
- [x] Invalid deterministic plans surface as `planning_error` before rendering rather than leaking into `rendering_error`.
- [x] Planner rationale and exported explanation do not need to share the same generation step.
- [x] Future Wave 4 registry entries should keep broad `QuestionTypeKey` values and move exact first supported shapes into `format_key`.
- [x] Broad-family launcher selections may now expand into multiple subtype rows; exported results preserve both the broad family key and the concrete subtype metadata.
- [x] Batch execution may short-circuit further LLM attempts after the first `insufficient_quota` failure, but exported result counts must still equal input rows times active question types.
- [x] Future async exploration, if any, should start at the batch or row/type orchestration layer without changing current question-type semantics or exported row counts.
- [x] After the current hardening baseline, reopen qtype-specific refinement planning with priority on `grammar` and `vocab`.
