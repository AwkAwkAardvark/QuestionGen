# Live Quality Review

This document records durable review findings from checked-in sample artifacts. It is about logic quality and gating policy, not about redefining the export contract.

## Current Review Corpus

- Active review artifact: `sample_data/generated_questions.json`
- Review role: logic-quality baseline for the current branch
- Non-role: authoritative export-shape specification

Current branch snapshot reviewed on `hail-mary-finish-everything`:

- total rows: `78`
- status mix:
  - `63` `validation_passed`
  - `8` `qtype_incompatibility_error`
  - `7` `planning_error`

## `paragraph_ordering` Review

Current sample slice:

- total rows: `13`
- status mix:
  - `6` `validation_passed`
  - `5` `planning_error`
  - `2` `qtype_incompatibility_error`

Observed buckets:

1. Should fail earlier as `qtype_incompatibility_error`

- `OriginalQuestionNumber` `1`, `2`, `8`, `9`, `17`
- Current failure text: `ParagraphOrderingPlan adjacency is too weakly forced to support a stable ordering item.`
- Durable reading:
  - these passages do not really contain a stable four-block ordering problem
  - they read more like emotional accumulation, continuous event narration, generic advice flow, or loose analogy extension than like forced block-to-block adjacency reconstruction
  - they should be rejected before LLM planning instead of reaching late deterministic plan failure

2. Already rejected for the right broad reason

- `OriginalQuestionNumber` `7`, `서술형 4`
- Current failure text: prepared source has only `5` sentence units
- Durable reading:
  - this is already the desired early incompatibility path
  - min-unit gating is not the current problem for these rows

3. Accepted, but planner inventories still need stronger adjacency cues

- `OriginalQuestionNumber` `23`
  - still leans on a generic "limitations -> more limitations" progression
  - should stay acceptable only if boundary hints can better expose why the earthquake limitation block must precede the policy-inequity block
- `OriginalQuestionNumber` `서술형 5`
  - the current split works, but the item quality depends on preserving the instruction -> observed effect -> generalization chain
  - planner-facing block-start notes should make that chain more explicit so the item does not drift into arbitrary chunking

4. Structurally valid, but still mechanically partitioned enough to keep as review warnings

- `OriginalQuestionNumber` `16`
  - reads as values definition -> case discussion -> maxim
  - structurally valid, but still close to a broad rhetorical outline rather than sharply forced adjacency on every edge
- `OriginalQuestionNumber` `19`
  - reads as biography setup -> quoted evidence -> concluding inference
  - acceptable for now, but still a useful warning example for overly summary-like block partitioning

5. Stronger accepted reference rows

- `OriginalQuestionNumber` `10`
- `OriginalQuestionNumber` `18`
- Durable reading:
  - these are the better reference rows for the current format because each next block is motivated by a clearer question, contrast, or explanation edge

## Hardening Direction

Next hardening target for the live branch:

- move weak-adjacency `paragraph_ordering` passages out of late `planning_error` and into earlier `qtype_incompatibility_error`
- keep deterministic plan validation strict rather than rescuing weak passages by loosening the validator
- improve planner-facing boundary and block-start inventories so accepted passages surface stronger edge-by-edge adjacency evidence
- treat mechanically partitioned but still schema-valid passes as ongoing review warnings, not as proof that the family is fully hardened
