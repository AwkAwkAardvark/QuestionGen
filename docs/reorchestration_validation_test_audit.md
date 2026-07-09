# Reorchestration Validation Test Audit

## Purpose

This audit reviews the current validation and batch test surfaces with one assumption: exported statuses and result/export shapes stay stable, while the internal orchestration implementation changes again when LangGraph is restored.

This document is intentionally prescriptive and future-facing. It does not propose status-policy changes, registry changes, or export-schema changes.

## Stable Assumptions For The Refactor

- Preserve the current exported status vocabulary, especially `validation_passed`, `qtype_incompatibility_error`, `source_error`, `planning_error`, and `input_error`.
- Preserve complete row export even when a row/type combination fails.
- Preserve the current batch adapters and result writers as the public batch surface unless a separate contract change is approved.
- Treat LangGraph restoration as an internal orchestration change, not as permission to relax deterministic validation or move failure classes across status boundaries.

## Current Test Surface Summary

- [`tests/test_validators.py`](/home/ebene/project/QuestionGen/tests/test_validators.py) is already the main durable contract suite. Most of it exercises pure deterministic checks directly: source validation, compatibility gates, plan validation, output validation, and explanation hygiene.
- [`tests/test_batch.py`](/home/ebene/project/QuestionGen/tests/test_batch.py) mixes three concerns:
  - true batch-contract tests around `run_batch_rows(...)`, adapters, and exports
  - end-to-end pipeline tests that currently use `compile_question_graph(...)` as a harness
  - a few orchestration-placement assertions that are standing in for missing graph transition tests
- There is currently no dedicated orchestration graph test suite. That is the main gap the LangGraph restoration should close.

## Classification

### Survives Unchanged After Reorchestration

These tests are already anchored to stable contracts rather than to the current `LocalQuestionGraphRunner` implementation.

- In `tests/test_validators.py`, keep the direct validator and compatibility tests unchanged:
  - source/prepared-source checks such as `test_source_check_marks_too_few_sentences_as_incompatibility`, `test_source_check_fails_for_malformed_gap`, `test_prepared_source_rejects_fragmentary_sentence_units`
  - direct plan validation such as `test_plan_check_rejects_collapsed_sentence_insertion_gaps_as_planning_error`, `test_plan_check_rejects_invalid_paragraph_ordering_coverage`, `test_sentence_insertion_plan_accepts_two_sided_target`, `test_paragraph_ordering_plan_accepts_forced_adjacency_blocks`
  - output validators such as `test_final_validator_catches_plan_and_rendering_mismatches`, `test_fill_in_the_blank_validator_accepts_valid_output`, `test_underlined_vocab_output_validator_accepts_four_corrupted_subtype`, `test_grammar_validator_accepts_valid_output`
  - explanation hygiene tests such as `test_explanation_validator_rejects_internal_sentence_or_gap_ids`, `test_explanation_validator_rejects_schema_mechanics_terms`, `test_explanation_validator_rejects_malformed_teacher_phrase`
- In `tests/test_batch.py`, keep the true batch-contract tests unchanged:
  - `test_per_row_failure_is_captured`
  - `test_qtype_incompatibility_is_preserved`
  - `test_quota_failure_triggers_batch_global_fail_fast`
  - `test_non_quota_planning_error_does_not_trigger_fail_fast`
  - `test_file_runner_writes_csv_and_markdown`
  - `test_invalid_runner_fails_clearly`
  - `test_dataframe_adapter_matches_row_execution`
  - `test_dataframe_adapter_assigns_batch_row_id_when_missing`

Why: these tests assert status classification, row preservation, adapter behavior, and export behavior. Those are still required after LangGraph returns.

### Needs Harness Adaptation Only

These tests should survive semantically, but their current harness is tied to the local compiled runner plus prompt-parsing fake planners.

- `tests/test_batch.py`
  - `test_one_row_one_type`
  - `test_one_row_multiple_types`
  - `test_fill_blank_weak_subtypes_surface_as_qtype_incompatibility`
  - `test_vocab_hardening_rejections_surface_as_qtype_incompatibility`
  - `test_correct_among_3_hardening_rejection_surfaces_as_qtype_incompatibility`
  - `test_correct_among_4_hardening_rejection_surfaces_as_qtype_incompatibility`
  - `test_short_valid_passage_becomes_qtype_incompatibility`
  - `test_weak_paragraph_ordering_row_is_rejected_before_planning`

Required adaptation:

- Replace prompt-shape-sensitive doubles like `_StubPlanner` with LangGraph-compatible planner fakes or node-level dependency injection.
- Keep the assertions on final `BatchResultRow` statuses, subtype expansion, and exported fields.
- Do not rewrite these as graph-internals tests unless the test is really about transition placement rather than final row outcomes.

Why: the intent is durable, but the current harness assumes the exact prompt text and synchronous local runner implementation.

### Depends On Current Imperative-Runner Behavior

These tests are coupled to the present serial batch loop or to the exact current lifecycle event cadence.

- `tests/test_batch.py`
  - `test_progress_callback_reports_batch_lifecycle`
  - `test_console_progress_renderer_can_consume_batch_updates_unchanged`
  - `test_hard_vocab_subtypes_produce_passes_on_inline_reaudit`

Prescriptive handling:

- Keep the progress tests only if `BatchProgressUpdate` event ordering remains an explicit public batch contract.
- If LangGraph restoration introduces finer-grained per-node events, do not silently weaken these tests. Split them into:
  - one batch-level contract test that still checks `started -> item_started -> item_completed -> completed`
  - separate graph-runtime tests for any new node-level progress surface
- Move `test_hard_vocab_subtypes_produce_passes_on_inline_reaudit` out of the current batch-style role. It directly invokes the compiled runner and is effectively using the runner as an orchestration surrogate.

Why: these tests are not just checking final statuses. They assume the exact outer control flow and invocation pattern of the current imperative execution path.

### Should Become Explicit Node/Transition Tests Once LangGraph Returns

These are the current tests whose real intent is transition placement, not just final validation.

- `tests/test_batch.py`
  - `test_fill_blank_weak_subtypes_surface_as_qtype_incompatibility`
  - `test_vocab_hardening_rejections_surface_as_qtype_incompatibility`
  - `test_correct_among_3_hardening_rejection_surfaces_as_qtype_incompatibility`
  - `test_correct_among_4_hardening_rejection_surfaces_as_qtype_incompatibility`
  - `test_weak_paragraph_ordering_row_is_rejected_before_planning`
- `tests/test_validators.py`
  - the `source_check` and compatibility tests for early rejection are still worth keeping as pure validator tests, but they should no longer be the only evidence for orchestration placement

Required promotion after LangGraph restoration:

- Add graph tests that prove these rows terminate on the intended node or edge:
  - source-stage incompatibility stops before `design`
  - design-stage incompatibility stops before `planner`
  - late deterministic plan failure stops before `render`
- Keep the existing validator tests alongside them. The validator tests should prove the rule; the new graph tests should prove the edge routing.

Why: today the repo proves many compatibility rules, but it does not prove that the restored graph routes those failures at the correct stage.

## Missing Transition-Level Coverage To Add

LangGraph restoration should add a dedicated orchestration test file that checks node visitation and terminal routing directly. The minimum missing coverage is:

1. Happy-path node sequence
   - Prove one successful row visits `input_check -> prepare_source -> source_check -> design -> planner -> plan_check -> render -> build_explanation_context -> write_explanation -> validate_generated_question`.
   - Assert that `generated` stays absent before render and present at terminal success.

2. Early terminal edges
   - `input_error` stops before source preparation.
   - `source_error` stops before design.
   - `qtype_incompatibility_error` from source compatibility stops before design and planner.
   - `qtype_incompatibility_error` from deterministic design stops before planner.

3. Post-planner failure edges
   - `planning_error` from planner output or repair exhaustion stops before render.
   - `planning_error` from `plan_check` stops before render even if planning itself succeeded.
   - `rendering_error` stops before explanation writing and final validation.

4. Explanation and final-validation edges
   - Explanation-context failure or explanation-writing failure stops before final validation.
   - Final validation failure reaches the expected terminal status without mutating earlier state fields.

5. Retry and repair transitions
   - A recoverable planner schema failure takes the repair/retry edge and can still reach success.
   - A non-recoverable planner failure reaches terminal `planning_error` without entering render.
   - A quota-classified planner failure propagates a batch-visible `planning_error` signal that the batch layer can use for later-item fail-fast.

6. State propagation across nodes
   - `BatchRowId`, `OriginalQuestionNumber`, `QuestionTypeKey`, `QuestionFormatKey`, and `QuestionSubtypeKey` survive unchanged through all visited nodes.
   - `prepared_source`, `design`, `plan`, and `generated` appear only after their owning node succeeds.

7. Batch/graph boundary
   - Unknown question types bypass graph execution entirely and still export `input_error`.
   - A graph that terminates early still yields one completed batch item and one exported result row.

## Recommended Split After LangGraph Restoration

- Keep `tests/test_validators.py` as the rule-level deterministic suite.
- Keep `tests/test_batch.py` focused on batch fan-out, fail-fast, adapters, exports, and progress contracts.
- Add a new graph-orchestration suite for node visitation, transition routing, and retry behavior.

That split is the cleanest way to preserve the existing status/export contract while making the LangGraph restoration testable as orchestration rather than as a side effect of batch tests.
