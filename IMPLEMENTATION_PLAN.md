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

## Wave 4: Multi-Type Expansion

- [x] Add additional registered question types beyond `sentence_insertion`.
- [x] Add broad registry keys plus `format_key`-level first supported formats for Wave 4 types.
- [ ] Use `mood_atmosphere` as the registry key for the 심경·분위기 family.
- [x] Reuse the same planner-renderer-validator architecture per new type.
- [x] Introduce `qtype_incompatibility_error` for passages that are valid inputs but not suitable for a given question type.
- [x] Ensure "all registered types" automatically expands as the registry grows.
- [x] Keep type-specific failure modes readable in shared exports.
- [x] Split source provenance from internal deterministic row identity so `OriginalQuestionNumber` can remain an opaque label and `BatchRowId` can drive internal ordering behavior.
- [x] Keep exported explanations teacher-facing by rejecting internal `S#` / `G#` notation and schema-mechanics language.
- [x] Separate teacher-facing explanation generation from structural planning so explanation writing can use post-render textual evidence rather than planner-internal notation.
- [ ] Once Wave 4 formats are fully implemented and their contents have been absorbed into durable docs/specs, ask for explicit confirmation before deleting `QuestionTypeDump`.

## Acceptance Checklist

- [x] The backend package can execute a full question pipeline with an injected runner.
- [x] Batch execution can emit machine-readable review artifacts.
- [x] Batch execution captures per-row failure without aborting the full run.
- [ ] A Colab user can run the system end-to-end using Drive-backed inputs and `api_key.txt`.
- [x] The launcher attempts all registered question types without manual type selection.
- [x] CSV and JSON are both produced for debugging runs.
- [x] Failed type/passage combinations remain visible and readable in exported results.
- [x] `qtype_incompatibility_error` is distinguishable from malformed-source failure and planner malfunction in exported results.

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
