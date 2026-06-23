# Pending Question Types

This document is a planning artifact only. It does not change the live runtime registry, notebook behavior, or package exports.

Current live registry:

- `sentence_insertion`
- `paragraph_ordering`
- `underlined_phrase_meaning` (`underlined_phrase_meaning_5_ko` with `[밑줄]...[/밑줄]` export markers)
- `fill_in_the_blank` (`blank_inference_proposition_5_choices` with the `_____` blank marker)
- `vocab` (`contextual_vocab_error_5` with five numbered single-word underlines and one contextual corruption)
- `grammar` (`grammar_error_5` with five numbered single-word verb-form targets and one controlled corruption)

Current product direction:

- Colab-first launcher
- Google Drive-backed runtime data and `api_key.txt`
- launcher runs all registered question types automatically
- valid but poor-fit passage/type pairs should surface as `qtype_incompatibility_error`
- `gpt-5-mini` is the single default model for the current MVP
- per-type model-tier routing is intentionally deferred until after live-pipeline stabilization

Because the launcher runs every registered type, only `mood_atmosphere` remains outside the live registry. The remaining sections below are retained mainly as planning history and subtype notes rather than as a live-status checklist.

Latest gating lessons from sample review:

- abbreviation-safe sentence parsing matters for sentence-based families; `U.S.` / `U.K.` style splits can otherwise create fake sentence units and malformed live items
- a smaller residual parser/source false positive still matters: complete clauses like the row-9 `they’d ever been to` sentence should not be rejected as fragments
- the updated `sample_data/generated_questions.json` is now quota-clean enough to act as a real live-quality baseline: 39 rows, 17 `validation_passed`, 14 `planning_error`, and 8 `qtype_incompatibility_error`
- the main current signal is live-family quality, not operations:
  - `sentence_insertion` still leaks schema-invalid or collapse-prone target choices
  - `paragraph_ordering` still accepts too many weak-adjacency passages into planning
  - `underlined_phrase_meaning` still lets some weak-centrality span picks survive too long before failing
- the next live-quality pass should therefore harden the current live families again before `fill_in_the_blank` expands the registry
- current live families should reject weak items more aggressively before `fill_in_the_blank` expands the registry again
- model-tier specialization is a later optimization problem, not part of the current MVP hardening pass

## Recommended Order

1. `mood_atmosphere` (only after explicit user confirmation, and only after the current live families are materially hardened)

This order is the current engineering-first recommendation, not a claim about long-term pedagogical priority.

Why `mood_atmosphere` is deferred to the end:

- The current affective approach is incomplete and not part of the live rollout.
- The remaining single-span and multi-span families are higher-priority roadmap work because they share the now-live span infrastructure.
- Reintroducing affective generation before those families are finished would reopen a broad suitability and explanation-quality problem that is intentionally postponed.
- Even after the rest of the roadmap is done, `mood_atmosphere` should return only if the user explicitly confirms that it is worth reviving.

Why the remaining order is still span-first rather than registry-first:

- The shared span layer now exists and `underlined_phrase_meaning` is the first live single-span consumer.
- `fill_in_the_blank` still depends on that same span layer, so it remains the next natural consumer before the multi-span corruption families.
- `vocab` and `grammar` both need multiple numbered underlined targets and one intentionally corrupted target, which makes them more demanding than the single-span families.
- `grammar` is the riskiest because grammatical corruption must stay subtle, local, and teacher-explainable.

Why `fill_in_the_blank` is still next, but not yet:

- The safer first consumer has already shipped as `underlined_phrase_meaning`.
- `fill_in_the_blank` remains product-important and is still the next best use of the new span layer, but it is riskier because target selection, recoverability, and distractor policy all become harder at once.
- The current live registry first needs a stronger `gpt-5-mini` baseline on `sentence_insertion`, `paragraph_ordering`, and `underlined_phrase_meaning`, measured by materially fewer real `planning_error` rows on the current mixed batch.
- The remaining multi-span families should still wait until the single-span blank family is stable.

When to intentionally override this order:

- If product priority clearly favors 빈칸 over engineering caution, `fill_in_the_blank` can be pulled forward after the span layer exists.
- If that happens, treat it as a deliberate product-first decision rather than as the default low-risk implementation order.

## Pending Catalog

The following keys are broad registry candidates. The `format_key` values name the first supported house format and should carry the early specificity instead of overloading the broad key.

### `fill_in_the_blank`

- Current rollout policy:
  - do not add this family to the live registry in the current pass
  - resume rollout only after the current `gpt-5-mini` live baseline is acceptable again after another live-family hardening pass
  - keep the broad key locked as `fill_in_the_blank`
  - keep the first format locked as `blank_inference_proposition_5_choices`
  - keep the first release locked as strict proposition-level 빈칸추론
- First format key: `blank_inference_proposition_5_choices`
- Korean stem direction:
  - likely `다음 빈칸에 들어갈 말로 가장 적절한 것은?`
  - treat the first release as 빈칸추론 rather than a generic blank
- Output shape:
  - one source passage
  - one proposition-like span replaced with a blank
  - 5 answer choices
  - marker answer `①`-`⑤`
  - Korean explanation
- Infrastructure:
  - span-based
- Expected incompatibility patterns:
  - no recoverable proposition-like span
  - multiple defensible completions
  - blank target too trivial, too copied, or too long
- Major risks:
  - the shared span-preparation layer now exists, but blank-specific planning and rendering policy are still missing
  - blank rollout would currently stack new blank-specific risk on top of an already shaky `gpt-5-mini` live-family planning baseline
  - distractor quality will likely dominate item quality
  - blank placement may drift away from real 수능/내신 expectations if under-specified
  - the planner may produce vocabulary-style deletion instead of true inference
- User confirmation still needed:
  - when the live `gpt-5-mini` baseline is strong enough to resume blank rollout work

Subtype direction that looks useful for this project:

- `blank_inference`
  - the important first subtype for CSAT-like use
  - blank represents a missing claim, conclusion, mechanism, contrast, limitation, or similar proposition
- possible later subtypes under the same broad family:
  - connective blank
  - summary completion
  - lexical blank
  - grammar blank

Current recommendation on registry shape:

- Do not split this family into multiple live registry keys yet.
- Keep `fill_in_the_blank` as the broad family key for now.
- Put the first supported subtype in `format_key`, starting with `blank_inference_proposition_5_choices`.
- Revisit narrower registry keys only if later product needs distinct launch behavior or clearly different infrastructure.

### `underlined_phrase_meaning` (live reference)

- Live format key: `underlined_phrase_meaning_5_ko`
- Locked v1 shape:
  - one self-selected source span
  - source-preserving passage rendering with `[밑줄]...[/밑줄]`
  - 5 Korean contextual paraphrase choices
  - marker answer `①`-`⑤`
  - Korean teacher-facing explanation
- Locked v1 selection policy:
  - prefer abstract, figurative, evaluative, or claim-bearing phrases
  - reject overly literal or context-free phrases as incompatibility
- Main remaining hardening risks:
  - near-duplicate Korean distractors
  - weak phrase-centrality heuristics on mixed batches
  - future CSV-specified target-span control, which is still intentionally deferred

### `vocab`

- First format key: `contextual_vocab_error_5`
- Korean stem direction:
  - likely `다음 글의 밑줄 친 부분 중, 문맥상 낱말의 쓰임이 적절하지 않은 것은?`
  - treat the first release as contextual lexical-fit rather than vocabulary-definition recall
- Output shape:
  - original passage with 5 numbered underlined targets
  - one target deterministically replaced with a grammatically possible but contextually wrong word or short phrase
  - marker answer `①`-`⑤`
  - Korean explanation
- Infrastructure:
  - span-based, multi-target
- Expected incompatibility patterns:
  - fewer than 5 good lexical targets
  - no candidate word strongly constrained by passage logic
  - replacement becomes too obvious or too arbitrary
  - vocabulary profile too technical or too flat
  - inserted corruption creates more than one arguable wrong answer
- Major risks:
  - needs stronger span prep than the single-target types
  - wrong replacement must remain plausible
  - validation likely needs lexical-quality and grammar-preservation checks beyond current deterministic rules
- User confirmation still needed:
  - whether short phrases are allowed as first-release targets or only single words

Possible later variants under the same broad family:

- contextual vocab error
- contextual vocab choice
- narrower failure modes such as polarity, semantic-role, scope, or collocation errors

Current recommendation on registry shape:

- Do not split this family into multiple live registry keys yet.
- Keep `vocab` as the broad family key for now.
- Put the first supported subtype in `format_key`, starting with `contextual_vocab_error_5`.
- Revisit narrower registry keys only if later product needs clearly different launch behavior or evaluation surfaces.

### `grammar`

- First format key: `grammar_error_5`
- Korean stem direction:
  - likely `다음 글의 밑줄 친 부분 중, 어법상 틀린 것은?`
  - treat the first release as sentence-structure integrity rather than isolated rule recall
- Output shape:
  - original passage with 5 numbered underlined grammar-bearing targets
  - one target replaced with a plausible-looking but structurally wrong form
  - marker answer `①`-`⑤`
  - Korean explanation
- Infrastructure:
  - span-based, multi-target
- Expected incompatibility patterns:
  - fewer than 5 clean grammar targets
  - no clearly constrained structure suitable for one provable corruption
  - multiple valid corrections
  - corruption becomes too obvious or rewrites meaning too much
  - corruption drifts into vocabulary meaning change instead of grammar
- Major risks:
  - subtle error generation is hard
  - explanation quality will be unforgiving
  - highest chance of producing fake-but-bad exam items
  - validation needs stronger readability and uniqueness checks than current types
- User confirmation still needed:
  - whether the first release should narrow to a small grammar-error family

Useful first-pass grammar families:

- subject-verb agreement
- finite vs nonfinite form
- active vs passive participle / modifier relation
- relative clause structure
- noun-clause introducers such as `what`
- parallel structure
- conjunction vs preposition

Current recommendation on registry shape:

- Do not split this family into multiple live registry keys yet.
- Keep `grammar` as the broad family key for now.
- Put the first supported subtype in `format_key`, starting with `grammar_error_5`.
- Revisit narrower registry keys only if later product needs clearly different launch behavior or evaluation surfaces.

## Boundary Notes

- `sentence_insertion` and `paragraph_ordering` are already live and should not be duplicated as pending entries.
- `underlined_phrase_meaning` is now live as the first span-based family.
- `mood_atmosphere` is intentionally inactive in the live registry; the current affective draft remains planning-only future work.
- The shared span-preparation layer now exists inside `PreparedSource`; remaining pending span families should build on that layer rather than redefining it.
- Pending specs should stay outside `src/questiongen/` until the implementation path is ready.
- Once these pending specs have been worked into the durable implementation docs and the corresponding types are live, ask for explicit confirmation before deleting the local `QuestionTypeDump`.

## Planning Direction

The remaining workflow should be treated as:

1. stabilize parser and structural validation for live sentence/span families
2. harden current live families under the shared `gpt-5-mini` default
3. harden the current live families so more weak cases fail as `qtype_incompatibility_error` or succeed cleanly instead of leaking into `planning_error`
4. rerun the same mixed sample and confirm the live-family status mix improves
5. use the live span layer to ship the blank family only after the live baseline recovers
6. move to multi-span corruption families
7. reconsider `mood_atmosphere` only at the very end, and only after explicit user confirmation

This is safer than thinking in terms of question-type names alone because the next real architectural boundary is no longer basic span preparation itself, but how far the live span contract can be pushed without breaking mixed-batch quality.

## Live Type Refinement Notes

The same planning area can also store refinement guidance for already live types, as long as it stays outside the runtime registry.

### `sentence_insertion`

Useful parts of the external feedback for this project:

- Keep the current format, but think of it as a coherence-repair task rather than a connector-matching task.
- Prefer target sentences with two-sided evidence:
  - something in the target depends on the left context
  - something in the right context is better explained by the target
- Treat connector-only targets as low quality unless they also have stronger referential, lexical, or discourse support.
- Improve teacher-facing explanations so they cite actual textual evidence from both sides instead of talking about internal `G#`/`S#` mechanics.
- Treat first-sentence and last-sentence targets as suspicious by default because they often lack one side of the required evidence.

Useful later, but not yet stable enough to adopt as schema truth:

- a fully expanded evidence object model with cue taxonomies
- mandatory wrong-gap notes for every distractor
- explicit difficulty scoring in the plan schema
- strict quoted-phrase validation tied to a future evidence-first planner output

Current recommendation:

- Use these ideas first as planner-prompt and validation-quality direction, not as a large immediate schema rewrite.
- The near-term goal should be better target selection and cleaner exported explanations.
- The safest structural next step is a separate post-render explanation stage that uses left/right textual evidence rather than planner-internal IDs.

### `paragraph_ordering`

Useful parts of the external feedback for this project:

- Keep the current `paragraph_ordering` format, but think of it as adjacency reconstruction rather than generic topic matching.
- Prefer block splits where the intro strongly leads into one specific first block.
- Prefer passages where each correct edge is defensible:
  - intro -> first block
  - first block -> second block
  - second block -> third block
- Treat parallel examples, interchangeable subpoints, and independently movable chunks as incompatibility or low-quality signals.
- Improve teacher-facing explanations so they explain the order edge by edge rather than only summarizing the original paragraph.
- Treat connector-only sequencing as weak unless it is reinforced by reference, lexical chain, or a clearer discourse relation.

Useful later, but not yet stable enough to adopt as schema truth:

- a fully structured adjacency-evidence schema
- mandatory feedback for every wrong ordering choice
- difficulty scores and quality flags in the live plan schema
- a separate live `sentence_ordering` key alongside `paragraph_ordering`
- deterministic omission of the "least plausible" permutation, since that still needs project-specific policy

Current recommendation:

- Use these ideas first to tighten planner selection and explanation standards for the existing `paragraph_ordering` type.
- The near-term goal should be fewer mechanically valid but weak block partitions, plus clearer exported reasoning for why the correct order is forced.
- The safest structural next step is a separate post-render explanation stage that explains block-to-block adjacency in teacher-facing prose rather than reusing planner-internal inventories.

## Explanation Architecture Direction

Recommended project-wide direction:

- keep the current backbone of `prepare -> plan -> deterministic render -> validate`
- do not expand live plan schemas mainly for user-facing explanation fields yet
- treat planner rationale as internal or intermediate
- build a type-specific `explanation_context` after rendering
- generate or rewrite the final teacher-facing Korean explanation from that explanation context

Why this direction is safer:

- it fits current live types and pending passage/span families without forcing one planner schema style across all of them
- it prevents planner-internal notation such as `S#` / `G#` from leaking directly into exported explanations
- it scales better to future span-based types, where explanation should talk about selected text and context rather than preparation IDs
- it avoids a large immediate schema rewrite that may need to be revised again once the deferred affective family is reconsidered

Recommended near-term shape:

- `sentence_insertion`: explanation context should expose distinct left/right textual anchors and the final correct marker, without treating the given sentence itself as the primary evidence anchor
- `paragraph_ordering`: explanation context should expose intro text, displayed blocks, correct ordering, and the specific edge-by-edge reasons that force that ordering
- future span types: explanation context should expose chosen span text, surrounding context, and the specific reason the correct option is supported
- deferred `mood_atmosphere`: explanation context should expose cue phrases, tonal progression, and the dominant emotional or atmospheric signal if the family is revisited later

## Pending Family Refinement Notes

### `mood_atmosphere`

Useful parts of the external feedback for this project:

- Treat this family as affective inference rather than generic sentiment classification.
- Separate the reasoning for:
  - character emotion state
  - emotional change
  - overall atmosphere
- Require evidence-based answer selection from concrete cues such as reactions, thoughts, actions, setting details, sensory detail, and turning events.
- Treat near-synonym answer sets as a serious quality risk.
- Treat "no real emotional change" as incompatibility for `emotion_shift`, not as a weak pass.
- Keep atmosphere separate from a character's private feeling even if both live under the same broad family.

Useful later, but not yet stable enough to adopt as schema truth:

- a fully structured affect-evidence schema
- mandatory quoted evidence fields in the live plan schema
- wrong-choice notes for every distractor
- difficulty scoring and polarity/intensity metadata
- splitting the family into three live registry keys right away

Current recommendation:

- Keep the broad key `mood_atmosphere` for now.
- Treat the current implementation as incomplete and inactive rather than as a live v1 rollout.
- If this family is ever revived, start with an emotion-shift-specific stem under the broad family key rather than a generic family stem.
- If this family is ever revived, keep English adjective-pair choices as the first draft choice format.
- If this family is ever revived, allow writer/narrator or one clearly identifiable character as the feeling-holder, but reject ambiguous-holder passages as incompatibility.
- Do not revisit `atmosphere` or `emotion_state` until after the rest of the roadmap is complete, the live families are optimized, and the user explicitly confirms a return to affective generation.

### `fill_in_the_blank`

Useful parts of the external feedback for this project:

- Treat the first blank type as missing-proposition reconstruction rather than generic phrase deletion.
- Prefer blanks that function as a claim, conclusion, reason, effect, contrast, mechanism, limitation, or similar discourse role.
- Require support from multiple textual clues rather than one nearby hint.
- Treat paraphrase recovery as a quality signal: the answer should usually be inferable, not copied directly.
- Make distractors diagnostic by varying polarity, scope, relation, and paraphrase accuracy rather than writing unrelated wrong answers.
- Keep blank feedback focused on what the missing idea must mean, not just where it appears.

Useful later, but not yet stable enough to adopt as schema truth:

- a fully structured blank-evidence schema
- mandatory wrong-choice notes for every distractor
- explicit polarity and scope fields in the live plan schema
- splitting blank families into multiple live registry keys immediately

Current recommendation:

- Keep the broad key `fill_in_the_blank` for now.
- Treat the first implementation as `blank_inference`, encoded through `format_key` rather than a separate live registry key.
- Use prompt tightening to force proposition-level target selection before doing any major schema rewrite.

### `underlined_phrase_meaning`

Useful parts of the external feedback for this project:

- Treat this type as contextual paraphrase, not literal translation.
- Prefer phrases that have both:
  - a surface image or wording worth interpreting
  - a recoverable bridge to the passage's main claim
- Require evidence that connects the underlined phrase to the broader argument, not just to one nearby sentence.
- Treat pure idiom memorization and pure vocabulary difficulty as failure modes, not as acceptable versions of this type.
- Make distractors diagnostic by including overly literal, wrong-polarity, wrong-scope, or near-topic-but-wrong interpretations.
- Build explanations around the pattern:
  - surface meaning
  - contextual meaning
  - passage evidence that bridges the two

Useful later, but not yet stable enough to adopt as schema truth:

- a fully structured interpretation-evidence schema
- mandatory wrong-choice notes for every distractor
- difficulty scoring and phrase-type taxonomies in the live runtime contract

Current recommendation:

- Keep it as a single broad family key for now.
- Keep the current v1 policy: self-select one claim-bearing span and render it with `[밑줄]...[/밑줄]`.
- Use hardening work to improve phrase selection and Korean distractor quality before considering any deeper schema rewrite.

### `vocab`

Useful parts of the external feedback for this project:

- Treat this type as contextual lexical fit, not vocabulary-definition recall.
- Prefer targets where the expected word meaning is constrained by passage logic, polarity, semantic role, or discourse flow.
- Build the first format around one controlled corruption:
  - original correct word in source
  - one grammatically possible but contextually wrong replacement in the rendered item
  - four other underlined words that are still contextually appropriate
- Treat explanation quality as passage-based:
  - what meaning the context requires
  - why the inserted wrong word contradicts that meaning
  - why the other underlined items remain acceptable
- Treat dictionary-only explanation as a quality failure.

Useful later, but not yet stable enough to adopt as schema truth:

- a fully structured vocab-evidence schema
- mandatory notes for all non-answer underlined items
- explicit failure-type enums in the live plan schema
- splitting vocab families into multiple live registry keys immediately

Current recommendation:

- Keep the broad key `vocab` for now.
- Treat the first implementation as `contextual_vocab_error`, encoded through `format_key` rather than a separate live registry key.
- Use prompt tightening to force context-constrained target selection and controlled wrong-word replacement before doing any major schema rewrite.

### `grammar`

Useful parts of the external feedback for this project:

- Treat this type as sentence-structure integrity, not isolated rule recall.
- Build the first format around one controlled structural corruption:
  - original correct form in source
  - one plausible-looking but structurally wrong replacement in the rendered item
  - four other underlined grammar-bearing parts that remain valid
- Prefer targets whose wrongness is provable from structural cues such as:
  - true subject
  - finite-verb requirement
  - modifier boundary
  - antecedent
  - clause role
  - preposition requirement
  - parallel frame
- Treat grammar-vs-vocab boundary drift as a real failure mode.
- Keep explanations structural: explain why the sentence requires the corrected form, not just what grammar label applies.

Useful later, but not yet stable enough to adopt as schema truth:

- a fully structured grammar-evidence schema
- mandatory notes for all non-answer underlined parts
- explicit grammar-point enums in the live plan schema
- splitting grammar into multiple live registry keys immediately

Current recommendation:

- Keep the broad key `grammar` for now.
- Treat the first implementation as `grammar_error`, encoded through `format_key` rather than a separate live registry key.
- Use prompt tightening to force structure-constrained target selection and controlled corruption before doing any major schema rewrite.
