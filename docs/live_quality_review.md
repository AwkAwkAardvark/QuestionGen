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

## `ResponseFeedbackDump` After The `fill_in_the_blank` Rescue

`ResponseFeedbackDump` was re-read after the `fill_in_the_blank` anti-restoration hardening pass landed. It remains useful review evidence, but it is not authoritative anywhere it assumes an older live schema, older registry shape, or older export/status surface.

Signals from that dump that still survive as current review guidance:

- restoration-style blank rows were a real issue and justified the completed `fill_in_the_blank` structural rescue
- `contextual_vocab_choice_5` remains the strongest demonstrated `vocab` branch
- hard `vocab` subtypes still need fresh exam-naturalness review now that the schema rescue is in place
- `contextual_vocab_best_paraphrase_choice_5` and `contextual_vocab_correct_among_3_corrupted_5` remain the clearest ambiguity-risk surfaces
- explanation phrasing quality still needs cleanup in high-pass families, especially `vocab`, `fill_in_the_blank`, and `grammar`

Conclusions from that dump to reject as stale:

- subtype deactivation or pruning advice
- claims derived from the old hard-`vocab` schema failures
- any judgment that assumes an older registry layout, output shape, or status vocabulary is still current repo truth

Immediate review target from this reread:

- a fresh live export review on current code must replace reliance on stale checked-in artifacts when judging current `vocab` quality and post-hardening `fill_in_the_blank`

## 2026-06-25 Checked-In CSV Audit

The two checked-in CSV review artifacts under `sample_data/output/` are evidence for quality review only. They are not the runtime contract, and they were generated before the current hard-vocab rescue landed on `main`.

`Olymforce_cleaned_spellchecked_nobom_20260625_104227.csv`

- shape: `34` source passages expanded across `3` live families for `102` exported rows
- families present: `sentence_insertion`, `paragraph_ordering`, `underlined_phrase_meaning`
- status mix:
  - `44` `validation_passed`
  - `54` `qtype_incompatibility_error`
  - `3` `source_error`
  - `1` `planning_error`
- family mix:
  - `sentence_insertion`: `22` passed, `10` incompatibility, `1` source error, `1` planning error
  - `paragraph_ordering`: `1` passed, `32` incompatibility, `1` source error
  - `underlined_phrase_meaning`: `21` passed, `12` incompatibility, `1` source error

`Olymforce_cleaned_spellchecked_nobom_20260625_111945.csv`

- shape: `34` source passages expanded across all `8` live `vocab` subtypes for `272` exported rows
- status mix:
  - `68` `validation_passed`
  - `160` `qtype_incompatibility_error`
  - `36` `planning_error`
  - `8` `source_error`
- subtype mix:
  - `contextual_vocab_choice_5`: `33` passed, `1` source error
  - `contextual_vocab_best_paraphrase_choice_5`: `32` passed, `1` planning error, `1` source error
  - `contextual_vocab_phrase_choice_5`: `3` passed, `30` incompatibility, `1` source error
  - each of the five hard underlined `vocab` subtypes: `7` planning errors, `26` incompatibility, `1` source error

How to interpret the `111945` hard-family failures now:

- the `35` hard-family `planning_error` rows are stale pre-fix artifacts from the old dict-shaped `UnderlinedVocabPlan` field `corrupted_replacements_by_span_id`
- those rows should be treated as historical schema-contract failures, not as evidence that the five hard subtypes are intrinsically poor fits for the same passages
- the remaining `1` `planning_error` in that CSV belongs to `contextual_vocab_best_paraphrase_choice_5` and is a separate old choice-quality issue, not part of the hard-family schema failure

Current-code re-audit on `2026-06-25` of the same `34` checked-in `vocab` source passages:

- this was a deterministic compatibility re-audit on current code, not a fresh live-model generation run
- current code now admits all `34/34` passages for:
  - `contextual_vocab_choice_5`
  - `contextual_vocab_best_paraphrase_choice_5`
  - `contextual_vocab_correct_among_4_corrupted_5`
  - `contextual_vocab_error_1_among_5_5`
  - `contextual_vocab_error_1_among_5_polarity_scope_5`
  - `contextual_vocab_error_1_among_5_collocation_5`
  - `contextual_vocab_correct_among_3_corrupted_5`
- `contextual_vocab_phrase_choice_5` remains intentionally narrow at `3/34` compatible passages

`ResponseFeedbackDump` still has useful prioritization signal, but it is stale in two important ways:

- it assumes only a subset of `vocab` subtypes were active in the review artifact
- it interprets the old hard-family `400` schema failures as subtype weakness rather than as a now-fixed schema-contract problem

How to treat that dump now:

- useful as pedagogical and prioritization evidence
- not current subtype-quality truth by itself
- not current export-schema truth
- not current runtime-contract truth

Repo-truth takeaways that still survive from that dump:

- `contextual_vocab_choice_5` is the strongest currently demonstrated branch
- the hard underlined `vocab` branches remain the highest-value next runtime-quality surface now that the schema blocker is gone
- `contextual_vocab_correct_among_3_corrupted_5` is still the most ambiguity-prone subtype and should receive extra scrutiny before it earns long-term confidence
- restoration-style `fill_in_the_blank` rows were a real failure mode, but that family's anti-restoration rescue is now the completed structural response rather than an open schema-direction question
- blank-choice target quality still needs pressure against too-local or too-easy targets
- `best_paraphrase` and `correct_among_3_corrupted` remain the biggest ambiguity-risk branches inside the current live `vocab` set
- current runtime policy is now to resolve more of that ambiguity in deterministic design rather than by hoping the planner picks the right survivor or corruption anchor later

Specific ideas worth preserving from the dump:

- semantic pressure-point target selection
- directional or pragmatic target selection
- "changed from source but still correct" as a valid design mode
- stem and task alignment
- the idea of a future internal design-stage artifact for `vocab`

Conclusions to reject as current repo truth:

- stale subtype-pruning advice drawn from pre-fix artifacts
- current-runtime judgments inferred from the old hard-vocab schema failures
- any claim that the old checked-in artifacts alone define the present subtype contract

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

This `paragraph_ordering` hardening target has now landed on the current branch:

- move weak-adjacency `paragraph_ordering` passages out of late `planning_error` and into earlier `qtype_incompatibility_error`
- keep deterministic plan validation strict rather than rescuing weak passages by loosening the validator
- improve planner-facing boundary and block-start inventories so accepted passages surface stronger edge-by-edge adjacency evidence
- treat mechanically partitioned but still schema-valid passes as ongoing review warnings, not as proof that the family is fully hardened

## Landed `paragraph_ordering` Policy

The current live branch now applies the following policy for `paragraph_ordering`:

- pre-planning compatibility now searches ranked contiguous four-block candidates rather than allowing any adjacency-valid split
- a passage must expose at least one stable candidate partition with both:
  - edge-by-edge adjacency support
  - enough continuation-start signal to distinguish real block turns from generic narration or advice flow
- when no such candidate exists, the row should fail as `qtype_incompatibility_error` before planning
- the planner prompt now exposes boundary signals, ranked block starts, and ranked partition candidates so accepted passages are biased toward stronger partitions
- deterministic plan validation remains strict after planning, so this change is an earlier gate and prompt refinement, not a validator relaxation

## `vocab` Hard-Family Rescue Status

This hardening pass is now checked in:

- review artifact for checked-in regression coverage: `sample_data/output/Olymforce_cleaned_spellchecked_nobom_20260625_111945.csv`
- target family: the five live hard underlined `vocab` subtypes

Resolved failure classes from the sample-driven rescue pass:

1. Structured-output schema failure before real planning

- the underlined hard-vocab planner shape no longer uses a dict-typed corruption field
- `UnderlinedVocabPlan` now carries an ordered `corrupted_replacements` record list, which is safe for structured-output planning
- planner canonicalization, validators, renderers, explanation-context assembly, and test stubs were all updated together to consume the new shape

2. Parser heuristics acting as a near-hard pre-planning veto

- the hard-family compatibility path no longer requires parser-top-tier targets before planning
- all five hard subtypes now admit passages whenever at least five clean lexical-slot candidates exist in the broader hard-candidate inventory
- parser-derived scores, cue counts, and anchors remain visible to the planner as ranked hints and source anchors rather than as the primary admission veto

3. Follow-up subtype hardening moved ambiguity control earlier into deterministic design

- `contextual_vocab_error_1_among_5_polarity_scope_5` no longer reuses a generic five-target bundle unchanged
- it now requires a five-target bundle with at least one explicit polarity/scope-eligible anchor and exports that eligible subset into design/prompt state
- if a passage has five generic hard-vocab targets but none is genuinely directional, degree-bearing, or scope-bearing, the row should fail as `qtype_incompatibility_error` before planning
- `contextual_vocab_error_1_among_5_collocation_5` now follows the same earlier-gate pattern with a locked collocation-eligible subset rather than letting any generic same-width replacement count as a collocation item
- phrase-choice rejection and polarity/scope directionality from `ResponseFeedbackDump` were healthy signals; keep using that dump as review evidence rather than as contract truth
- if a passage has five generic hard-vocab targets but none has a strong local phrase-frame or selectional anchor, the row should fail as `qtype_incompatibility_error` before planning
- semantic-frame-adjacent but still natural substitutions such as broad near-domain noun swaps should also fail this subtype as `qtype_incompatibility_error` rather than stretching collocation to cover them
- `contextual_vocab_correct_among_4_corrupted_5` and `contextual_vocab_error_1_among_5_5` now use a deterministic stable-bundle selector instead of blindly locking the first five clean hard candidates
- those easier hard subtypes now also lock their answer marker in design so the planner cannot silently drift to a different survivor or corrupted target
- `contextual_vocab_correct_among_3_corrupted_5` now locks both the intended answer span and the weaker untouched distractor during design
- flat-strength, near-flat, or answer-like extra-survivor bundles for that subtype should now fail as `qtype_incompatibility_error` instead of reaching late ambiguity or survivor-selection `planning_error`
- `contextual_vocab_best_paraphrase_choice_5` now rejects weak grammar-heavy anchors earlier and reranks toward stronger content-bearing targets
- `contextual_vocab_phrase_choice_5` remains intentionally narrow and now rejects fragmentary determiner-led phrase targets earlier

4. Explanation export quality still needs deterministic cleanup on the `vocab` branch

- exported explanations no longer open with raw quoted English evidence as the first move
- awkward Korean memo fragments such as duplicated `이 자리에는` phrasing are now cleaned deterministically before export

Current acceptance boundary for this rescue:

- keep all five hard `vocab` subtypes live in default expansion
- eliminate schema-shaped `planning_error` for the hard family
- reserve `qtype_incompatibility_error` for true candidate-inventory failure rather than for missing five parser-top-tier targets
- keep regression coverage that re-audits the checked-in `sample_data/output/Olymforce_cleaned_spellchecked_nobom_20260625_111945.csv` source passages and requires that each hard subtype produces at least some `validation_passed` rows rather than remaining stuck at zero-pass default incompatibility

## Current `contextual_vocab_correct_among_4_corrupted_5` Target

- keep this subtype live; review artifacts such as `ResponseFeedbackDump` remain prioritization evidence only, not subtype-pruning authority
- current quality problem to harden: reject bundles or draft plans that collapse into "find the only absurd underline" behavior
- current repo-truth boundary: the four corrupted targets should still look like locally plausible lexical-slot competitors, not semantically loud, unrelated, or giveaway-absurd replacements
- when no such bundle exists for a passage, prefer `qtype_incompatibility_error` over shipping an easy survivor item

## Explanation Quality Policy For High-Pass Families

Current explanation hardening target after `paragraph_ordering`:

- `fill_in_the_blank`
- `vocab`
- `grammar`

Landed policy:

- `fill_in_the_blank` should reject restoration-only targets before planning rather than exporting easy "put back the deleted phrase" rows
- exported explanations should begin from local supporting evidence, not from generic stock phrases alone
- planner-owned Korean notes such as `contextual_meaning_ko` and `correction_basis_ko` should be cleaned before export rather than copied as awkward memo fragments
- malformed phrases such as duplicated `...의미` wording should fail deterministic explanation validation instead of shipping as `validation_passed`
- when a planner-supplied note is too generic or obviously bad, the post-render explanation writer should prefer deterministic family-specific fallback phrasing
