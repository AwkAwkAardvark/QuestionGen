# Pending Question Types

This document is a planning artifact only. It does not change the live runtime registry, notebook behavior, or package exports.

Current live registry:

- `sentence_insertion`
- `paragraph_ordering`

Current product direction:

- Colab-first launcher
- Google Drive-backed runtime data and `api_key.txt`
- launcher runs all registered question types automatically
- valid but poor-fit passage/type pairs should surface as `qtype_incompatibility_error`

Because the launcher runs every registered type, new types should not be added to the live registry until they are implementation-complete enough to tolerate mixed-source batches.

## Recommended Order

1. `mood_atmosphere`
2. `fill_in_the_blank`
3. `phrase_translation`
4. `vocab`
5. `grammar`

Why `mood_atmosphere` should come next:

- It does not require the future span-preparation layer.
- It will directly exercise the new `qtype_incompatibility_error` path, which is already an explicit product requirement.
- It lets the project improve planner quality, explanation quality, and suitability gating before taking on more expensive span infrastructure.
- It is also the type most likely to fail often for legitimate pedagogical reasons, so it is a good stress test for exported failure semantics.

Why the remaining order is span-first rather than registry-first:

- `fill_in_the_blank` and `phrase_translation` need a single target span, so they are the most natural first consumers of a new span layer.
- `vocab` and `grammar` both need multiple numbered underlined targets and one intentionally corrupted target, which makes them more demanding than the single-span families.
- `grammar` is the riskiest because grammatical corruption must stay subtle, local, and teacher-explainable.

## Pending Catalog

The following keys are broad registry candidates. The `format_key` values name the first supported house format and should carry the early specificity instead of overloading the broad key.

### `mood_atmosphere`

- First format key: `emotion_shift_pair_choice_5`
- Korean stem direction:
  - treat the family as subtype-specific rather than as generic sentiment
  - use different Korean stems for `emotion_state`, `emotion_shift`, and `atmosphere`
  - recommended first rollout is `emotion_shift`, with `atmosphere` next
- Output shape:
  - preserve the original passage exactly
  - render 5 subtype-appropriate choices
  - return marker answer `①`-`⑤`
  - export Korean explanation
- Infrastructure:
  - passage-level question
  - may use sentence evidence internally, but does not require gap or span rendering
- Expected incompatibility patterns:
  - informational passages with no stable emotional cue
  - unclear target character or unclear scene target
  - passages with ambiguous or weak atmosphere
  - passages where no real emotional change occurs
  - passages where multiple mood readings would all feel defensible
- Major risks:
  - over-forcing mood labels onto neutral texts
  - low-quality distractors or near-synonym choice sets
  - confusing atmosphere with a character's private feeling
  - explanations that sound generic instead of evidence-based
- User confirmation still needed:
  - whether first rollout under the broad key should support only `emotion_shift` or both `emotion_shift` and `atmosphere`
  - whether `emotion_state` should wait for a later pass
  - whether first-release choices remain in English adjective form

Subtype direction that looks useful for this project:

- `emotion_state`
  - asks for one character's dominant feeling
  - strongest when the target character is obvious and the final affect is well-supported
- `emotion_shift`
  - asks for initial feeling -> final feeling
  - currently looks like the best first subtype because it tends to produce clearer evidence and more objective recovery
- `atmosphere`
  - asks for the scene mood rather than one character's private emotion
  - should stay separate from character-feeling logic even if it shares the same broad key

Current recommendation on registry shape:

- Do not split this family into three live registry keys yet.
- Keep `mood_atmosphere` as the broad family key for now.
- Differentiate the family through subtype-aware prompts and, when needed, additional `format_key` variants such as:
  - `emotion_shift_pair_choice_5`
  - `atmosphere_adjective_pair_choice_5`
  - `emotion_state_adjective_choice_5`
- Revisit separate registry keys only if later product needs distinct analytics, filtering, or launch behavior per subtype.

### `fill_in_the_blank`

- First format key: `blank_best_fit_5_choices`
- Korean stem direction:
  - likely `다음 빈칸에 들어갈 말로 가장 적절한 것은?`
- Output shape:
  - one source passage
  - one span replaced with a blank
  - 5 answer choices
  - marker answer `①`-`⑤`
  - Korean explanation
- Infrastructure:
  - span-based
- Expected incompatibility patterns:
  - no clean inferable span
  - multiple defensible completions
  - blank target too trivial or too long
- Major risks:
  - current package has no span-preparation layer yet
  - distractor quality will likely dominate item quality
  - blank placement may drift away from real 수능/내신 expectations if under-specified
- User confirmation still needed:
  - whether the broad key should stay `fill_in_the_blank` or use the shorter historical `blank`
  - what the first removable unit should be

### `phrase_translation`

- First format key: `underlined_phrase_translation_5_ko`
- Korean stem direction:
  - likely `다음 글의 밑줄 친 부분의 의미로 가장 적절한 것은?`
- Output shape:
  - original passage with one underlined English span
  - 5 Korean choices
  - marker answer `①`-`⑤`
  - Korean explanation
- Infrastructure:
  - span-based
- Expected incompatibility patterns:
  - no good contextual phrase target
  - many equally acceptable Korean paraphrases
  - phrase too literal or too context-free to be worth asking
- Major risks:
  - dictionary-style translation instead of contextual meaning
  - duplicate or near-duplicate Korean distractors
  - possible future demand for CSV-specified target spans, which should stay out of v1 unless explicitly chosen

### `vocab`

- First format key: `vocab_incorrect_contextual_usage_5`
- Korean stem direction:
  - likely `다음 글의 밑줄 친 부분 중, 문맥상 낱말의 쓰임이 적절하지 않은 것은?`
- Output shape:
  - original passage with 5 numbered underlined targets
  - one target deterministically replaced with a wrong-but-plausible word or phrase
  - marker answer `①`-`⑤`
  - Korean explanation
- Infrastructure:
  - span-based, multi-target
- Expected incompatibility patterns:
  - fewer than 5 good lexical targets
  - replacement becomes too obvious or too arbitrary
  - vocabulary profile too technical or too flat
- Major risks:
  - needs stronger span prep than the single-target types
  - wrong replacement must remain plausible
  - validation likely needs lexical-quality checks beyond current deterministic rules
- User confirmation still needed:
  - whether short phrases are allowed as first-release targets or only single words

### `grammar`

- First format key: `grammar_incorrect_underlined_form_5`
- Korean stem direction:
  - likely `다음 글의 밑줄 친 부분 중, 어법상 틀린 것은?`
- Output shape:
  - original passage with 5 numbered underlined targets
  - one target replaced with a grammatically wrong form
  - marker answer `①`-`⑤`
  - Korean explanation
- Infrastructure:
  - span-based, multi-target
- Expected incompatibility patterns:
  - fewer than 5 clean grammar targets
  - multiple valid corrections
  - corruption becomes too obvious or rewrites meaning too much
- Major risks:
  - subtle error generation is hard
  - explanation quality will be unforgiving
  - highest chance of producing fake-but-bad exam items
- User confirmation still needed:
  - whether the first release should narrow to a small grammar-error family

## Boundary Notes

- `sentence_insertion` and `paragraph_ordering` are already live and should not be duplicated as pending entries.
- Span-based types should wait for a real span-preparation layer in `PreparedSource` or an equivalent planning structure.
- Pending specs should stay outside `src/questiongen/` until the implementation path is ready.
- Once these pending specs have been worked into the durable implementation docs and the corresponding types are live, ask for explicit confirmation before deleting the local `QuestionTypeDump`.

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
- it avoids a large immediate schema rewrite that may need to be revised again once `mood_atmosphere` and span-based types are live

Recommended near-term shape:

- `sentence_insertion`: explanation context should expose left textual anchor, target sentence text, right textual anchor, and the final correct marker
- `paragraph_ordering`: explanation context should expose intro text, displayed blocks, correct ordering, and the specific edge-by-edge reasons that force that ordering
- future span types: explanation context should expose chosen span text, surrounding context, and the specific reason the correct option is supported
- `mood_atmosphere`: explanation context should expose cue phrases, tonal progression, and the dominant emotional or atmospheric signal

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
- Use subtype-aware prompt tightening and validation heuristics before considering a registry split.
- Favor `emotion_shift` as the first live subtype because it is usually the easiest to make objective and teacher-explainable.
