# QuestionGen Implementation Plan

## Core Direction

- [x] Keep the backend centered on `planning -> deterministic rendering -> validation`.
- [x] Keep `src/questiongen/` notebook-agnostic and Drive-agnostic.
- [x] Keep model construction outside the batch layer through an injected runner.
- [x] Keep the public runner and batch contract stable while internal orchestration uses explicit LangGraph-backed stage routing.
- [x] Treat Colab as the primary user-facing launcher surface.
- [x] Treat Google Drive as the user-controlled storage layer for inputs, outputs, and `api_key.txt`.
- [x] Keep `main` as the stable default branch, not as a live implementation branch.
- [x] Start all new mutating work from a feature branch cut from `main`, and push that branch before using Colab to validate it.
- [x] Keep `questiongen.ui.gradio_app` as the single source of truth for UI behavior while keeping notebooks thin launcher/debug surfaces.
- [x] Design the user-facing flow around "run all registered question types" rather than manual type selection.
- [x] Preserve failed type/passage combinations as exported results with readable `status` and `errors`.
- [x] Treat question-type incompatibility as a first-class expected outcome rather than forcing it into generic planner/source failure labels.
- [x] Use CSV and JSON as the primary debug artifacts once orchestration/export work is complete.
- [x] Keep Colab repo-code loading separate from one-time third-party dependency bootstrap, and prefer source-path loading plus fresh-subprocess tests over repeated editable reinstalls in the same kernel.
- [x] Ship one cheaper default model first: `gpt-5-mini`.
- [x] Defer per-question-type model routing until after the live pipeline is stable.
- [x] Keep any near-term model routing narrowly planner-local: normal planner drafts may use `QUESTIONGEN_MODEL_PLANNER`, while Tier 1 blank adjudication may use `QUESTIONGEN_MODEL_LIGHT` without turning the runtime into a broad per-type routing matrix.
- [x] Keep the current batch execution path synchronous and serial; defer async or concurrent orchestration as a later performance-only track.
- [x] Keep broad family keys as the launcher/UI selection surface while expanding execution into concrete subtype rows underneath each family.
- [x] Preserve subtype metadata in runtime state and exports through `QuestionFormatKey`, `QuestionSubtypeKey`, and `QuestionSubtype`.
- [x] Default future meaning/pragmatics boundary cases to `vocab`, while keeping `grammar` focused on local structural or form error detection.
- [x] Treat checked-in review artifacts and `ResponseFeedbackDump` as quality/prioritization evidence rather than as export-schema or runtime-contract truth.
- [x] Review relevant durable docs before each commit, and update matching docs in the same work cycle whenever runtime behavior changes.
- [x] If the worktree is in a shippable state, finish the same work cycle with a reviewed commit and push rather than leaving durable doc or policy changes unpushed.

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
- [x] Restore explicit graph-backed orchestration while preserving the current runner and batch/export public surface.
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
- [x] Split the launcher surface into `runner_ui.ipynb` for staff UI launch and `runner_debug.ipynb` for batch/debug work.
- [x] Mount Google Drive from the notebook layer only.
- [x] Load `api_key.txt` from Drive and populate environment variables in the notebook layer only.
- [x] Define notebook-level input and output Drive paths.
- [x] Expose notebook-side `REPO_BRANCH_OPTIONS` under Advanced Settings, default `REPO_BRANCH` to `main`, validate the selection against the allowlist, and clone the selected pushed branch with `git clone --branch REPO_BRANCH --single-branch ...`.
- [x] Add notebook-side `BOOTSTRAP_ENV`, `RESET_REPO`, and `RUN_REPO_TESTS` controls so routine reruns can skip package reinstall churn while branch validation can still refresh pushed code safely.
- [x] Keep third-party dependency bootstrap separate from repo refresh, and keep local repo-code loading on `REPO_DIR / "src"` rather than on routine `%pip install -e ...` reruns.
- [x] Auto-bootstrap missing third-party runtime dependencies on a clean kernel before the first `questiongen` import, while keeping `BOOTSTRAP_ENV=True` as a force-reinstall path.
- [x] Probe raw runtime modules before any `questiongen` import in the maintained notebooks, and persist restart-required state across reruns after bootstrap or repo refresh touches an already-imported kernel.
- [x] Sync an existing Colab runtime clone to the latest pushed commit on the selected branch instead of blindly reusing a stale `/content/QuestionGen` checkout.
- [x] Fail fast with a restart-required message if the notebook kernel already imported `questiongen` and the user requests a repo refresh or environment bootstrap.
- [x] Fail fast on missing third-party runtime imports such as `langchain_openai` before starting batch execution or Gradio launch, instead of exporting row-by-row `planning_error` noise.
- [x] Provide a fresh-subprocess test path for pushed-branch validation in Colab, with `PYTHONPATH` pointed at `REPO_DIR / "src"`.
- [x] Construct the structured LLM-backed runner from the notebook layer.
- [x] Launch the primary staff notebook directly into Gradio without pre-running batch-generation cells.
- [x] Keep direct batch generation, preview, and artifact inspection in the separate debug notebook.
- [x] Keep the debug notebook JSON-first for routine inspection, with CSV/Markdown and optional Gradio helper code left commented nearby for occasional manual use.
- [x] Keep `notebooks/legacy/runner.ipynb` and `notebooks/legacy/runner_pending.ipynb` as archival notebooks until a later confirmed removal pass.

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
- [x] Keep broad-family notebook/UI selection rooted in `QUESTION_TYPES` while actual execution fans out into subtype rows underneath each selected family.

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
- [x] Re-baseline `paragraph_ordering` against `sample_data/generated_questions.json` as a logic-review artifact and move weak-adjacency rows from late `planning_error` to earlier `qtype_incompatibility_error` without loosening deterministic validation.

### Live families already shipped

- [x] `sentence_insertion`
  - status: live
  - first supported format: `sentence_insertion_5_gaps`
  - remaining hardening focus: stronger two-sided evidence selection and less templated explanation prose
- [x] `paragraph_ordering`
  - status: live
  - first supported format: `abc_ordering_after_intro`
  - current hardening policy: require a stable candidate partition with strong continuation-start signals before planning, expose ranked partition candidates to the planner, keep deterministic validation strict, and continue reviewing mechanically partitioned passes as warning examples

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
  - rollout policy: live now, but only when the locked target supports inference-style completion rather than literal source restoration
  - live subtype set:
    - `blank_inference_proposition_5_choices`
    - `blank_connective_relation_5_choices`
    - `blank_summary_completion_5_choices`
  - shipped policy: selected broad-family runs expand to multiple blank subtypes, each with subtype-specific inventories and incompatibility gates
  - current hardening policy:
    - design should lock a target whose recovery requires broader passage reasoning, not immediate source restoration
    - proposition and summary blanks must use a non-identical `correct_choice`
    - proposition and summary completion readability should stay aligned with schema-level English-choice acceptance, including otherwise readable sentence-final `.`
    - `blank_connective_relation_5_choices` should admit only short connective-style completions; clause stubs or sentence fragments should fail earlier as `qtype_incompatibility_error`
    - if a weaker blank subtype can only reuse the same restoration-style span, it should fail early as `qtype_incompatibility_error` rather than ship a redundant row
    - Tier 1 planner-local semantic adjudication now runs only for `blank_inference_proposition_5_choices` and `blank_summary_completion_5_choices`, after draft hydration plus deterministic plan checks and before the graph leaves `planner`
    - that extra pass is fail-fast only, uses the lightweight model route by default, and does not add a new graph node, plan rewrite loop, or broad second LLM pass for other subtypes
  - completed structural rescue:
    - the anti-restoration hardening pass is the completed structural rescue for this family
    - the next cycle should not reopen blank-family subtype pruning, registry reshaping, or export-schema redesign unless a later deliberate policy decision says otherwise
  - current explanation policy: rewrite exported explanations from supporting evidence plus cleaned Korean meaning notes, and reject malformed memo-style phrasing rather than exporting awkward `...라는 의미` boilerplate

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
    - `contextual_vocab_choice_5`
    - `contextual_vocab_best_paraphrase_choice_5`
    - `contextual_vocab_phrase_choice_5`
    - `contextual_vocab_correct_among_4_corrupted_5`
    - `contextual_vocab_error_1_among_5_5`
    - `contextual_vocab_error_1_among_5_polarity_scope_5`
    - `contextual_vocab_error_1_among_5_collocation_5`
    - `contextual_vocab_correct_among_3_corrupted_5`
  - shipped policy: broad-family runs now produce three blank-choice contextual substitution subtypes plus five underlined multi-target corruption/diagnosis subtypes
  - current hardening policy: the blank-choice branch now distinguishes baseline contextual substitution, strict non-restoration best-paraphrase selection, and phrase-only lexical substitution; renderer choice order remains deterministically shuffled from `BatchRowId` and subtype key; the hard family now uses structured-output-safe ordered `corrupted_replacements` records instead of a dict-shaped field; validators reject weak targets, unchanged-source best-paraphrase answers, phrase-width drift, wrong corruption class, near-synonym drift, rendered-underline collisions, and non-unique remaining answers
  - current subtype-hardening pass: ambiguity control for four live vocab subtypes now happens earlier in deterministic design rather than relying on the planner to repair weak bundles later
  - current hard-family admission and prompting policy:
    - [x] keep all five hard underlined vocab subtypes live with the structured-output-safe ordered replacement-record collection
    - [x] update planner canonicalization, deterministic validators, renderers, explanation-context assembly, and tests together around that new replacement shape
    - [x] allow hard-family planning whenever at least five clean lexical-slot candidates exist from the broader hard-candidate inventory, rather than requiring old parser-top-tier thresholds
    - [x] keep parser-derived scores, cue counts, and source anchors visible to the planner as ranked hints rather than as a hard admission veto
    - [x] keep subtype-specific post-plan checks strict: corruption counts, source-order uniqueness, slot compatibility, no near-synonym corruption, rendered uniqueness, one-best-answer behavior, polarity/scope-only checks, collocation-only checks, and uniquely stronger surviving-answer checks for `contextual_vocab_correct_among_3_corrupted_5`
    - [x] tighten the hard-vocab planner and repair prompts so retries explicitly react to insufficient distinct targets, ambiguity between surviving answers, wrong corruption class, slot-width drift, and duplicate rendered targets
    - [x] for `contextual_vocab_error_1_among_5_polarity_scope_5`, lock a five-target bundle that includes an explicit polarity/scope-eligible corruption subset and fail early as `qtype_incompatibility_error` when no such anchor exists
    - [x] for `contextual_vocab_error_1_among_5_collocation_5`, lock one stable collocation target in design rather than letting the planner drift across a wider eligible subset, and fail early as `qtype_incompatibility_error` when no unique local phrase-frame or selectional anchor exists
    - [x] for `contextual_vocab_correct_among_4_corrupted_5` and `contextual_vocab_error_1_among_5_5`, replace the raw “first five” lock with a stable-bundle selector that penalizes clustered frames and locks the answer marker in design
    - [x] for `contextual_vocab_correct_among_4_corrupted_5`, require four locally anchored corruption-friendly distractors so the accepted row does not collapse into “spot the absurd one”
    - [x] for `contextual_vocab_correct_among_3_corrupted_5`, lock both the intended answer span and the weaker untouched distractor in design and reject both flat-strength bundles and answer-like extra survivors as `qtype_incompatibility_error`
    - [x] clean exported `vocab` explanations in the same pass so they do not open with raw quoted English evidence and they strip duplicated Korean memo boilerplate such as repeated `이 자리에는 ...`
    - [x] keep regression coverage that re-audits checked-in `sample_data/output/Olymforce_cleaned_spellchecked_nobom_20260625_111945.csv` source passages and requires every hard `vocab` subtype to produce at least some `validation_passed` rows with no schema-shaped `planning_error`
  - next quality-pass priorities on top of the hard-schema rescue:
    - [x] record the checked-in `2026-06-25` sample-output CSVs and `ResponseFeedbackDump` as review evidence rather than as contract truth
    - [x] keep treating `ResponseFeedbackDump` as review evidence only: phrase-choice rejection and polarity/scope directionality were healthy signals, while `correct_among_3` survivor ambiguity and broad collocation drift required stricter deterministic gates
    - [x] document that the old `35` hard-family `400` rows in `111945` are stale schema artifacts, not current-code subtype verdicts
    - [x] re-audit current deterministic compatibility on those same `34` checked-in `vocab` source passages to separate post-fix behavior from stale pre-fix CSV evidence
    - [ ] rerun a fresh live `vocab` sample export on current code so artifact review is no longer anchored to pre-fix planner output
    - [ ] re-baseline hard `vocab` subtype pass/fail quality on that fresh export, especially whether accepted rows still feel exam-natural rather than like "pick the absurd one"
    - [ ] harden explanation quality across `vocab`, `fill_in_the_blank`, and `grammar` after the fresh `vocab` review identifies recurring weak-but-valid patterns
    - [ ] run a fresh mixed-batch audit after those `vocab` plus explanation-quality passes
    - [x] tighten blank-choice target quality against too-local / too-easy targets without regressing subtype coverage
    - [x] scrutinize ambiguity risk in `contextual_vocab_best_paraphrase_choice_5` and `contextual_vocab_correct_among_3_corrupted_5` by moving more rejection logic into deterministic design and compatibility gates
  - immediate next-cycle boundary:
    - use fresh current-code exports as the truth surface for the next `vocab` review cycle, with older checked-in CSVs and `ResponseFeedbackDump` kept only as historical comparison artifacts
    - keep the broad-family registry and export contract stable while refining subtype-level design gates, prompts, validators, and explanation writers
    - do not treat the next cycle as subtype pruning, registry reshaping, or export-schema redesign
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
  - current hardening policy:
    - keep the live family restricted to controlled structural corruption and reject pseudo-word outputs such as malformed inflectional inventions before they can pass validation
    - prefer earlier `qtype_incompatibility_error` when a would-be verb-family target is not a real controlled verb-form anchor
    - keep explanation marker references aligned with the rendered answer numbering
  - current explanation policy: prefer local structural-cue explanations that name the governing evidence, and reject malformed memo-style Korean notes before export

### Multi-span acceptance

- [ ] The span layer can support numbered multi-target rendering without destabilizing earlier single-span types.
- [x] The validator can prove subtype-specific corruption counts and a unique answer contract for the live multi-span vocab and grammar families.
- [ ] Real-batch outputs remain diagnostically readable in CSV/JSON when passages do not fit these families.

## Wave 8: Dormant Affective Family

- [x] `mood_atmosphere`
  - status: implemented but intentionally dormant outside the live registry
  - dormant subtype set:
    - `emotion_shift_pair_choice_5`
    - `emotion_state_choice_5`
    - `atmosphere_choice_5`
  - dormant policy: keep the implementation code in the repo, but keep `QUESTION_TYPES` and launcher/UI defaults focused on the other live families until their quality work stabilizes
  - reactivation policy: revisit this family only after the active families are hardened further and the user explicitly confirms that the affective family is worth reactivating

## Active `v0.3.0` Work: Graph-Backed Orchestration

### Planner observability and timeout hardening first

- [x] Add verbose planner-stage lifecycle logging before any shared graph refactor.
- [x] Log planner attempt start, finish, retry, and elapsed time with subtype-aware context so a single stuck row is traceable in Colab and Gradio server logs.
- [x] Add planner-call timeout policy that surfaces readable exported `planning_error` rows instead of opaque hangs.
- [x] Document clearly that the current spinner/progress surfaces are not sufficient to diagnose a single long or stuck planner call.
- [x] Keep timeout failures as explicit exported errors rather than silent stalls or hidden retries.

Landed hardening contract:

- `QUESTIONGEN_PLANNER_TIMEOUT_SECONDS` now defaults to `180` seconds if unset.
- The same timeout is applied both to `ChatOpenAI(request_timeout=...)` construction and to a local planner-attempt watchdog so a single stuck call cannot block the batch indefinitely.
- `QUESTIONGEN_VERBOSE_PLANNER=1` now enables subtype-aware graph-stage and planner-attempt logs on launcher stdout.
- `QUESTIONGEN_PLANNER_ELAPSED_LOG_SECONDS` now controls periodic "still running" planner logs and defaults to `30` seconds.
- Planner timeouts now export readable `planning_error` rows instead of presenting as silent spinner stalls.

### Shared design layer and restored graph runtime

- [x] Treat the shared design layer as the foundation for a `v0.3.0`-scale internal architectural change.
- [x] Use the internal graph shape:
  - `prepare -> source gate -> design -> final planner -> deterministic plan check -> render -> explanation -> final validate`
- [x] Treat explicit LangGraph-backed orchestration as the active internal execution contract for that stage sequence.
- [x] Keep the public batch/export/notebook interfaces unchanged while refactoring internal graph stages and planner contracts.
- [x] Add first-class `QuestionState.design` and deterministic family-specific design builders.
- [x] Split live-family planning into `design -> draft -> hydrate final plan`.
- [x] Treat the design stage as a reusable family pattern across the live families rather than as a `vocab`-only special case.
- [x] Migrate the live families in this order:
  - `vocab`
  - `sentence_insertion`
  - `paragraph_ordering`
  - `fill_in_the_blank`
  - `underlined_phrase_meaning`
  - `grammar`
- [x] Move source-owned text selection out of LLM authority for the migrated live families.
- [x] Treat subtype-critical ambiguity control as design-stage state when a live family cannot safely rely on planner free choice.
- [x] Keep the public invocation surfaces unchanged while the graph runtime is explicit again:
  - `compile_question_graph(...)`
  - `runner.invoke(state)`
  - `run_batch_rows(..., runner=...)`
  - `BatchResultRow`
  - exported status vocabulary
- [x] Keep final runtime integration, doc reconciliation, and commit/push responsibility with the lead agent even when subagents assist.

## Stable Workflow Commitments

- [x] `main` remains the stable default branch for notebooks, not the branch where new implementation work is performed.
- [x] New implementation work starts on a feature branch before any mutating repo changes.
- [x] Colab can validate only pushed branches; unpushed local workspace changes are never part of the Colab contract.
- [x] Branch validation in Colab should prefer repo refresh plus fresh-subprocess tests over repeated editable package reinstalls in the active kernel.

## Acceptance Checklist

- [x] The backend package can execute a full question pipeline with an injected runner.
- [x] Batch execution can emit machine-readable review artifacts.
- [x] Batch execution captures per-row failure without aborting the full run.
- [ ] A Colab user can run the system end-to-end using Drive-backed inputs and `api_key.txt`.
- [x] The launcher attempts all registered question types without manual type selection.
- [x] CSV and JSON are both produced for debugging runs.
- [x] Failed type/passage combinations remain visible and readable in exported results.
- [x] The live registry includes `fill_in_the_blank`, `vocab`, and `grammar` under subtype-expanded broad families.
- [x] `mood_atmosphere` remains implemented but excluded from the live default registry until later reactivation work is explicitly approved.
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
- [x] `QUESTION_TYPES` remains the live default-registry surface, while dormant implemented families such as `mood_atmosphere` stay outside it until later reactivation work.
- [x] Batch execution may short-circuit further LLM attempts after the first `insufficient_quota` failure, but exported result counts must still equal input rows times active question types.
- [x] Future async exploration, if any, should start at the batch or row/type orchestration layer without changing current question-type semantics or exported row counts.
- [x] After the current hardening baseline, reopen qtype-specific refinement planning with priority on fresh `vocab` live-quality re-baselining, then explanation hardening across `vocab`, `fill_in_the_blank`, and `grammar`.
