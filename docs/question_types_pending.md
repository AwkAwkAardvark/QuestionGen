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

- First format key: `mood_atmosphere_adjective_choice_5`
- Korean stem direction:
  - likely subtype-specific stems rather than one generic stem
  - probably support atmosphere and/or mood change first
- Output shape:
  - preserve the original passage exactly
  - render 5 choices
  - return marker answer `①`-`⑤`
  - export Korean explanation
- Infrastructure:
  - passage-level question
  - may use sentence evidence internally, but does not require gap or span rendering
- Expected incompatibility patterns:
  - informational passages with no stable emotional cue
  - passages with ambiguous or weak atmosphere
  - passages where multiple mood readings would all feel defensible
- Major risks:
  - over-forcing mood labels onto neutral texts
  - low-quality distractors
  - explanations that sound generic instead of evidence-based
- User confirmation still needed:
  - preferred first subtype set
  - whether first-release choices remain in English adjective form

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
