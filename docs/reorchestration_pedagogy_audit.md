# Reorchestration Pedagogy Audit

## Purpose

This audit reviews the current live families against the durable review corpus and recent feedback artifacts, then assigns the next pedagogical fixes to explicit post-reorchestration stages.

It assumes the future runtime is organized around visible stage boundaries:

1. source gate
2. targeting/design
3. planner prompt
4. plan validation
5. render
6. explanation context/writer
7. final generated-question validation

It does **not** recommend registry pruning, export-schema redesign, or new ad hoc statuses. The main recommendation is clearer ownership: weak items should fail in the earliest stage that can justify the rejection, and accepted items should be made stronger by the stage that actually owns the defect.

## Review Corpus

- Live-family inventory from `docs/question_types_pending.md` and `src/questiongen/question_types.py`:
  - `sentence_insertion`
  - `paragraph_ordering`
  - `underlined_phrase_meaning`
  - `fill_in_the_blank`
  - `vocab`
  - `grammar`
- Current durable logic baseline from `docs/live_quality_review.md`:
  - `sample_data/generated_questions.json` reviewed as `78` rows
  - `63` `validation_passed`
  - `8` `qtype_incompatibility_error`
  - `7` `planning_error`
- Historical but still useful evidence:
  - `FeedbackDumps/ResponseFeedbackDump`
  - `FeedbackDumps/StructureFeedbackDump`
  - `sample_data/output/Olymforce_cleaned_spellchecked_nobom_20260625_104227.csv`
  - `sample_data/output/Olymforce_cleaned_spellchecked_nobom_20260625_111945.csv`

Durable reading of the corpus:

- `paragraph_ordering` already has the right directional policy: reject weak adjacency early instead of rescuing it late.
- `fill_in_the_blank`, `vocab`, and `grammar` now have stronger structural contracts, but their remaining failures are mostly pedagogical rather than schema-shaped.
- Old hard-`vocab` schema failures in `111945` are stale and should not drive current subtype judgments.
- `ResponseFeedbackDump` remains valuable for item-quality signals, especially blank-frame fit, vocab subtlety, explanation quality, and grammar realism.
- `StructureFeedbackDump` correctly identifies orchestration opacity as a separate problem: without explicit stage-level artifacts, some quality failures are hard to assign cleanly to design, prompt, or validation.

## High-Level Findings

### What is already subtype-local

- `sentence_insertion` still needs stronger two-sided target selection and less templated reasoning.
- `underlined_phrase_meaning` still admits some targets that are too literal or too low-value.
- `fill_in_the_blank` still has answer-uniqueness and frame-fit problems.
- `vocab` is the strongest family overall, but several subtypes still accept locally obvious or over-clustered items.
- `grammar` is structurally improving, but still risks easy duplicates and pseudo-pedagogical corruption.

### What is blocked by orchestration opacity

- It is still too hard to tell whether some failures are caused by bad target locking, overbroad prompt freedom, or late validator overreach.
- Cross-subtype repetition within the same passage is visible in review artifacts, but the current review surface does not make sibling-run design choices easy to compare stage by stage.
- Explanation problems are easier to spot than to attribute: some should be fixed by better explanation context, while others are really target-selection failures that explanation should not try to rescue.

After reorchestration, those blocked areas should be addressed by making design artifacts, planner drafts, plan checks, and final validation outcomes inspectable per stage internally. That is an internal auditability requirement, not an export-contract change.

## Stage Ownership Rules

Use these rules consistently after reorchestration:

- If the passage should never have produced the item shape, the fix belongs in `targeting/design`.
- If the shape is right but the LLM keeps drafting the wrong content inside that locked shape, the fix belongs in `planner prompt`.
- If the planner can still return formally valid but pedagogically invalid drafts, the fix belongs in `plan validation`.
- If the item is structurally right but the explanation is weak, generic, or memo-like, the fix belongs in `explanation context/writer`.
- If the final item still passes despite ambiguity, local absurdity, or answer non-uniqueness, the fix belongs in `final generated-question validation`.

## Audit By Family

### `sentence_insertion`

| Issue | Classification | Primary owner after reorchestration | Prescription |
| --- | --- | --- | --- |
| Connector-only or one-sided target sentences still feel weak even when structurally valid. | subtype-local | targeting/design | Lock only targets with explicit left and right evidence. Do not rely on the planner to infer that a weak target should be avoided. |
| Some passed items still explain the answer generically instead of naming the actual left/right coherence cues. | subtype-local | explanation context/writer | Build explanation context from the locked left anchor, right anchor, and final marker. Explanation prose should justify the fit from those anchors, not from stock flow language. |
| Residual late plan failures around target/gap consistency should remain rare and concrete, not a place to discover weak pedagogy. | subtype-local | plan validation | Keep deterministic checks narrow: the plan must respect the locked target and gap bundle, and must not collapse rendered positions. Do not use plan validation as a substitute for weak-target rejection. |

### `paragraph_ordering`

| Issue | Classification | Primary owner after reorchestration | Prescription |
| --- | --- | --- | --- |
| Mechanically partitioned but not genuinely forced passages can still look acceptable on structure alone. | subtype-local | targeting/design | Keep ranking candidate partitions before planning and reject passages without strongly forced edge-by-edge adjacency. This belongs before the planner. |
| Some acceptable items still explain order as a broad outline instead of proving each edge. | subtype-local | explanation context/writer | Explanation context should include the intro, displayed blocks, correct order, and one reason per edge. Writer output should talk through `intro -> first`, `first -> second`, `second -> third`. |
| If a planner draft can still restate the locked partition without showing why the order is forced, that is not a design failure. | subtype-local | planner prompt | Prompt the planner to justify adjacency, not topic progression. The draft should be thin and reason-focused because block selection is already locked. |

### `underlined_phrase_meaning`

| Issue | Classification | Primary owner after reorchestration | Prescription |
| --- | --- | --- | --- |
| Some accepted underlined phrases are too literal or already say exactly what they mean. | subtype-local | targeting/design | Reject spans that lack a real surface-to-context bridge. Centrality and interpretive compression belong in span selection, not in later explanation repair. |
| Distractors can still cluster too close to literal paraphrase or stay too near the correct reading. | subtype-local | final generated-question validation | Add a final uniqueness and wrongness check for Korean paraphrases: at least one wrong-scope or wrong-implication distractor should exist, and near-duplicate paraphrases should fail. |
| Explanations sometimes sound mechanically split into “surface meaning” and “contextual meaning” without a clean bridge. | subtype-local | explanation context/writer | Build explanation context as a three-part bridge: source wording, contextual claim, and the passage evidence that connects them. |

### `fill_in_the_blank`

| Issue | Classification | Primary owner after reorchestration | Prescription |
| --- | --- | --- | --- |
| The validator can reject pedagogically strong completions because it is not sufficiently aware of the blank frame. | subtype-local | final generated-question validation | Make validation frame-aware. A sentence-completion blank, clause-completion blank, and phrase-completion blank should not share one readability test. |
| Summary/proposition blanks can pass with distractors that are all near-paraphrases of the same answer. | subtype-local | final generated-question validation | Require stronger answer uniqueness. Reject option sets where multiple choices preserve the same proposition with only cosmetic wording changes. |
| Some blanks still risk drifting back toward source restoration instead of inference. | subtype-local | targeting/design | Lock only targets that require passage-level recovery. If the blank can be solved mainly by putting back the deleted wording, reject the target before planning. |
| Once the target is locked correctly, the planner still needs better wrongness diversity across options. | subtype-local | planner prompt | Demand distractor families that differ by polarity, scope, relation, or causal reading rather than five versions of the same paraphrase. |
| Explanation prose for passed blanks still tends to be generic. | subtype-local | explanation context/writer | Explanations should start from the local frame plus the broader supporting evidence, not from a stock “this blank means…” template. |

### `vocab`

| Issue | Classification | Primary owner after reorchestration | Prescription |
| --- | --- | --- | --- |
| The family is strong structurally, but many passed items are still too easy because the wrong answers are locally absurd. | subtype-local | final generated-question validation | Reject hard-family outputs whose wrong choices are eliminable from phrase awkwardness alone. Local smoothness plus contextual wrongness should be mandatory. |
| `contextual_vocab_correct_among_4_corrupted_5` still risks collapsing into “find the only normal underline.” | subtype-local | targeting/design | Bundle selection should prefer sets where all five underlined targets look locally plausible and the answer survives by passage meaning, not by surface normality. |
| `contextual_vocab_correct_among_3_corrupted_5` remains the clearest ambiguity-risk subtype. | subtype-local | final generated-question validation | Preserve a hard unique-survivor gate. If the extra untouched item is still too answer-like, fail the item rather than exporting it. |
| `contextual_vocab_error_1_among_5_collocation_5` still tends to drift toward blunt semantic mismatch instead of narrow phrase-frame mismatch. | subtype-local | targeting/design | Lock a real collocation or selectional anchor before planning. If no such anchor exists, reject early rather than asking the planner to improvise “collocation.” |
| `contextual_vocab_best_paraphrase_choice_5` can still over-admit weak anchors or multiple defensible paraphrases. | subtype-local | final generated-question validation | Keep a strict best-answer uniqueness screen. Near-synonym clusters should fail late even if the planner draft is fluent. |
| The same passage can overproduce items from one semantic pressure point such as `inequality/disparity/equality`. | blocked by orchestration opacity today | targeting/design | After reorchestration, design should have sibling-run visibility per passage and avoid reusing the same pressure point across multiple `vocab` subtype rows when stronger unused hinges exist. |
| `vocab` explanations can still sound like dictionary glosses instead of passage-based reasoning. | subtype-local | explanation context/writer | Explain the contextual requirement first, then the mismatch or fit. Do not lead with quoted English alone. |

### `grammar`

| Issue | Classification | Primary owner after reorchestration | Prescription |
| --- | --- | --- | --- |
| Grammar quality improves whenever the corruption is a real English form, and degrades when the family slips toward pseudo-words or fake morphology. | subtype-local | final generated-question validation | Reject any corrupted form that is not a real English form in the intended subtype family. This should stay a hard late gate. |
| Different grammar subtypes can still collapse onto the same underlying corruption in one passage. | blocked by orchestration opacity today | targeting/design | After reorchestration, design should compare sibling grammar runs for the same passage and avoid exporting multiple subtype rows that test the same structural event unless the subtype distinction is genuinely visible. |
| Boundary drift from semantic-force tasks into `grammar` remains a risk. | subtype-local | targeting/design | Keep grammar targets anchored in structural cues such as agreement, finite/nonfinite control, clause linkage, and parallelism. Meaning-direction traps belong elsewhere. |
| Explanations must stay structural and marker-aligned even when design target order differs from render order. | subtype-local | explanation context/writer | Build explanations from the rendered marker, governing cue, and corrected form, not from internal design order. |

## Cross-Family Priority Issues

### 1. Earlier rejection is still preferable to late rescue

This remains the right project-wide discipline:

- weak passage/type fits belong in `targeting/design`
- valid locked designs with bad LLM wording belong in `planner prompt`
- formally valid but pedagogically weak drafts belong in `plan validation` or `final generated-question validation`, depending on whether the defect is draft-internal or final-item-visible

Do **not** move weak pedagogy downstream by default. The audit corpus repeatedly shows that the best quality gains came from earlier deterministic gates, especially for `paragraph_ordering`, `fill_in_the_blank`, and the hard `vocab` subtypes.

### 2. Explanation quality should not be repaired in planner space

For the high-pass families, explanation quality now belongs primarily to `explanation context/writer`, not to the planner prompt.

Use the planner only for lightweight, evidence-aware notes. The final teacher-facing prose should be built from rendered artifacts and locked evidence, because:

- explanation failures often survive even when structural planning is correct
- explanation repair should not force plan-schema growth
- explanation quality is easier to standardize after the answer and rendered markers are known

### 3. Final validation should become explicitly pedagogical, not merely structural

The next late-stage validator responsibilities should be:

- answer uniqueness
- local plausibility of wrong choices
- frame fit for blank completions
- real-form enforcement for grammar corruption
- rejection of easy survivor items in hard `vocab`
- rejection of near-duplicate or too-literal paraphrase sets

That is still compatible with the current export contract. It is a better final gate, not a new output surface.

## Prescriptive Priority Order After Reorchestration

1. Make `fill_in_the_blank` final validation frame-aware.
2. Tighten `vocab` final validation against locally absurd wrong answers and non-unique survivors.
3. Add sibling-aware target diversity in `vocab` and `grammar` design for multiple subtype rows generated from the same passage.
4. Tighten `underlined_phrase_meaning` design so low-value literal spans fail earlier.
5. Keep `sentence_insertion` and `paragraph_ordering` explanation writing explicitly evidence-based and edge-based rather than generic.

## Bottom Line

The main future-facing lesson is not that the live families need one more generic prompt pass. The stronger lesson is that pedagogical defects are now separable by stage, and the repo should treat them that way after reorchestration.

- `sentence_insertion` and `paragraph_ordering` mainly need better locked evidence selection and explanation writing.
- `underlined_phrase_meaning` mainly needs stricter target value and late paraphrase-quality rejection.
- `fill_in_the_blank` mainly needs frame-aware final validation plus stronger distractor diversity.
- `vocab` mainly needs stronger late subtlety gates and sibling-aware pressure-point diversity.
- `grammar` mainly needs real-form enforcement and cross-subtype deduplication.

The items that remain genuinely blocked today are not subtype ideas. They are auditability problems caused by orchestration opacity. Once stage boundaries are explicit again, the remaining quality work should be assigned to the owning stage above rather than debated at the level of whole-family reputation.
