from __future__ import annotations

from dataclasses import dataclass

from .schemas import (
    ContextualVocabChoiceDraft,
    ContextualVocabChoicePlan,
    FillInTheBlankDraft,
    FillInTheBlankPlan,
    GrammarDraft,
    GrammarPlan,
    MoodAtmospherePlan,
    ParagraphOrderingDraft,
    ParagraphOrderingPlan,
    SentenceInsertionDraft,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningDraft,
    UnderlinedVocabPlan,
    UnderlinedVocabDraft,
    UnderlinedPhraseMeaningPlan,
    VocabPlan,
)

SENTENCE_INSERTION_STEM = "글의 흐름으로 보아, 주어진 문장이 들어가기에 가장 적절한 곳은?"
PARAGRAPH_ORDERING_STEM = "주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?"
MOOD_SHIFT_STEM = "다음 글에 나타난 심경 변화로 가장 적절한 것은?"
MOOD_STATE_STEM = "다음 글의 인물의 심경으로 가장 적절한 것은?"
ATMOSPHERE_STEM = "다음 글의 분위기로 가장 적절한 것은?"
UNDERLINED_PHRASE_MEANING_STEM = "다음 글의 밑줄 친 부분의 의미로 가장 적절한 것은?"
FILL_IN_THE_BLANK_STEM = "다음 빈칸에 들어갈 말로 가장 적절한 것은?"
VOCAB_ERROR_STEM = "다음 글의 밑줄 친 부분 중, 문맥상 낱말의 쓰임이 적절하지 않은 것은?"
VOCAB_CHOICE_STEM = "다음 글의 빈칸에 들어갈 표현으로 가장 적절한 것은?"
VOCAB_CORRECT_AMONG_4_STEM = "다음 글의 밑줄 친 부분 중, 문맥상 가장 적절한 것은?"
VOCAB_ERROR_1_AMONG_5_STEM = "다음 글의 밑줄 친 부분 중, 문맥상 적절하지 않은 것은?"
VOCAB_CORRECT_AMONG_3_STEM = "다음 글의 밑줄 친 부분 중, 문맥상 옳은 것은?"
GRAMMAR_STEM = "다음 글의 밑줄 친 부분 중, 어법상 틀린 것은?"

SENTENCE_INSERTION_PLANNER_PROMPT = """
- Select exactly one target sentence ID from the sentence inventory.
- Select exactly five unique gap IDs from the gap inventory.
- Use the ranked target-candidate notes to choose the best available strong target, not merely any schema-valid sentence.
- Treat weak or reject-by-default target hints as a sign to choose a different target rather than forcing the item.
- Do not select both gaps that sit immediately before and after the target sentence, because they collapse into one rendered position once the target sentence is removed.
- Before returning, verify that the five selected gap IDs still map to five distinct rendered positions after removing the target sentence from the paragraph.
- First finalize `selected_gap_ids`, then choose `correct_gap_id` from that exact five-item list only.
- Set correct_gap_id to the gap where the target sentence best fits back into the paragraph.
- Prefer target sentences with distinct evidence on both sides: the left context should make the target sentence necessary, and the right context should read better because the target sentence is present.
- Good target shape: a sentence whose wording is prepared by the sentence before it and whose consequence, explanation, or reference is completed by the sentence after it.
- Bad target shape: a sentence that only begins with However/Therefore/But and could fit anywhere once that connector is ignored.
- Reject first-sentence, last-sentence, fragmentary, or connector-only targets instead of forcing a weak item.
- Do not treat the given sentence itself as the main explanation evidence. Use the surrounding sentences as the evidence anchors.
- The target sentence text must remain unchanged.
- Use only IDs that appear in the inventories.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the textual flow using sentence meaning, not internal IDs, schema fields, gap labels, or renderer mechanics.
- Do not generate final student-facing paragraph text.
""".strip()

PARAGRAPH_ORDERING_PLANNER_PROMPT = """
- Partition the full sentence inventory into exactly four contiguous non-empty blocks in original order.
- The first block is the intro section shown before (A), (B), (C).
- The remaining three blocks are the continuation blocks that must follow the intro in their original logical order.
- Use every sentence exactly once across the intro block and the three continuation blocks.
- Before returning, verify that flattening the intro block followed by the three continuation blocks reproduces the full sentence inventory in exactly the original order.
- Use the boundary hints and candidate block-start notes to choose the strongest available partition, not just any contiguous four-block split.
- Treat weak boundary hints or parallel-example block starts as a sign to rebuild the partition rather than forcing a generic four-block answer.
- Prefer block boundaries whose adjacency is forced by the passage, not just by a generic start-middle-end outline.
- Good partition shape: one block clearly raises a stage, question, or step that the next block directly continues or answers.
- Bad partition shape: three case-example blocks that look parallel enough to be swapped without changing the broad summary.
- Reject partitions where the continuation blocks behave like parallel examples or interchangeable subpoints.
- In the explanation, justify why one block follows the previous block, not just that the text starts, develops, and ends.
- Do not generate final student-facing paragraph text.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the thematic or logical progression, not internal sentence IDs, block inventories, or schema mechanics.
""".strip()

MOOD_SHIFT_PLANNER_PROMPT = """
- Use the source passage unchanged; do not remove, reorder, or underline any text.
- Only create an item if the passage contains one clear feeling-holder such as the writer, narrator, or a single clearly identifiable character.
- Reject neutral, informational, or weakly affective passages rather than forcing an emotion question onto them.
- Identify a real emotional change from an initial state to a different final state.
- Set `subtype` to `emotion_shift`.
- Set `target_holder` to a short natural label for that one clear holder.
- Set `initial_emotion` and `final_emotion` to distinct English emotion adjectives or short adjective phrases.
- Create exactly five unique English answer choices in `emotion -> emotion` format.
- Set `correct_choice` to the one choice that exactly matches `initial_emotion -> final_emotion`.
- Use distractors that are plausible but clearly wrong in direction, endpoint, or nuance.
- Copy `initial_evidence` and `final_evidence` as short exact snippets from the passage that support the initial and final emotional states.
- `shift_trigger` may be omitted, but if present it must be a short exact snippet from the passage that helps explain the change.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the emotional movement using textual evidence, not schema fields, internal labels, or mechanics.
""".strip()

MOOD_STATE_PLANNER_PROMPT = """
- Use the source passage unchanged; do not remove, reorder, or underline any text.
- Only create an item if the passage contains one clear feeling-holder and a stable dominant emotional state.
- Reject passages whose emotional direction is mixed, weak, or holder-ambiguous.
- Set `subtype` to `emotion_state`.
- Set `target_holder` to a short natural label for the one clear holder.
- Set `state_emotion` to the best English adjective or short adjective phrase naming the holder's dominant state.
- Create exactly five unique English answer choices as single-state adjectives or short adjective phrases.
- Set `correct_choice` to the one option that matches `state_emotion`.
- Copy `state_evidence` as a short exact passage snippet showing that dominant feeling.
- Write the explanation entirely in Korean.
- The explanation must explain the stable feeling state from passage evidence rather than a before/after change arc.
""".strip()

ATMOSPHERE_PLANNER_PROMPT = """
- Use the source passage unchanged; do not remove, reorder, or underline any text.
- Create an item only if the passage has a strong passage-level atmosphere or tone that is distinct from one person's private feeling.
- Reject passages where the evidence is mainly one holder's emotion or where multiple incompatible atmospheres compete.
- Set `subtype` to `atmosphere`.
- Set `atmosphere_label` to the best English adjective or short phrase naming the passage-level atmosphere.
- Create exactly five unique English answer choices as atmosphere adjectives or short adjective phrases.
- Set `correct_choice` to the one option that matches `atmosphere_label`.
- Copy `atmosphere_evidence` as a short exact passage snippet showing the passage-level mood or tone.
- Write the explanation entirely in Korean.
- The explanation must focus on atmosphere or tone cues in the passage, not on a single holder's private emotion unless the whole passage atmosphere depends on it.
""".strip()

UNDERLINED_PHRASE_MEANING_PLANNER_PROMPT = """
- Self-select exactly one span candidate from the provided span inventory.
- Use the ranked span inventory and prefer the strongest claim-bearing or proposition-bearing target unless it is clearly unusable.
- Treat weak or local centrality hints as a sign to pick a different span rather than forcing a merely valid phrase boundary.
- Prefer abstract, figurative, evaluative, or claim-bearing phrases whose meaning must be inferred from the passage.
- Reject literal dictionary-gloss phrases, dangling phrase fragments, punctuation-crossing chunks that are not complete clause-level units, surface comparison phrases, and weak targets that are not central to the passage claim.
- Prefer propositionally or argumentatively central spans over easy surface-paraphrase fragments.
- Good target shape: a phrase that carries the passage's conclusion, mechanism, evaluation, contrast, or limitation.
- Bad target shape: a merely local wording fragment that is easy to gloss without understanding the passage claim.
- Copy the selected span ID into `selected_span_id` and the exact source text into `selected_span_text`.
- Do not alter the source passage text or generate final student-facing paragraph text.
- Create exactly five unique Korean contextual paraphrase choices in `paraphrase_choices_ko`.
- Set `correct_choice` to the one clear best Korean paraphrase from that five-item list.
- Use distractors that stay close to the topic but are wrong in implication, scope, tone, or inference.
- Set `surface_meaning` to a short Korean explanation of the phrase's literal or surface wording.
- Set `contextual_meaning` to a short Korean explanation of what the phrase means in this passage.
- Copy `supporting_evidence` as a short exact snippet from the passage that best supports the contextual interpretation.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the phrase through passage evidence, not schema fields, internal IDs, or mechanics.
""".strip()

FILL_PROPOSITION_PLANNER_PROMPT = """
- Set `subtype` to `proposition_inference`.
- Self-select exactly one span candidate from the provided phrase-span inventory.
- Prefer a proposition-like, clause-level, claim-bearing, reason-bearing, effect-bearing, contrast-bearing, or limitation-bearing span.
- If no strongly proposition-like span exists, still prefer the most readable clause-sized contextual span rather than falling back to a local phrase fragment.
- Do not generate a trivial lexical blank or a pure grammar blank.
- Reject punctuation-crossing chunks unless the selected span remains a complete clause-level unit.
- Reject blanks that mainly restore a short surface phrase, connective fragment, or mechanically copied wording.
- Copy the selected span ID into `selected_span_id` and the exact source text into `selected_span_text`.
- Do not alter the source passage text or generate final student-facing paragraph text.
- Create exactly five unique English completion choices in `completion_choices`.
- Set `correct_choice` to the one option that best restores the original passage meaning.
- Keep distractors readable English and broadly on-topic while changing claim, scope, polarity, or relation.
- Set `contextual_meaning_ko` to a short Korean teacher-facing note describing what idea the blank must convey.
- Write `contextual_meaning_ko` as natural Korean explanation material, not as a memo fragment. Avoid endings such as `...라는 의미` or bare noun phrases that will sound awkward when inserted into a full explanation sentence.
- Copy `supporting_evidence` as a short exact snippet from the passage that best supports the correct completion.
- Write the explanation entirely in Korean.
""".strip()

FILL_CONNECTIVE_PLANNER_PROMPT = """
- Set `subtype` to `connective_relation`.
- Self-select exactly one short relation-bearing span from the provided connective-oriented span inventory.
- Prefer spans whose core work is to restore contrast, cause, concession, condition, consequence, or emphasis between adjacent clauses.
- Reject long summary-like spans, lexical-only blanks, or blanks that are recoverable without discourse relation reading.
- Copy the selected span ID into `selected_span_id` and the exact source text into `selected_span_text`.
- Do not alter the source passage text or generate final student-facing paragraph text.
- Create exactly five unique English completion choices.
- Exactly one choice should preserve the original discourse relation; distractors should stay readable but shift relation, polarity, or logical direction.
- Set `correct_choice` to the one option that restores the intended relation.
- Set `contextual_meaning_ko` to a short Korean note naming the relation the blank must restore.
- Write `contextual_meaning_ko` as natural Korean explanation material, not as a memo fragment. Avoid endings such as `...라는 의미`.
- Copy `supporting_evidence` as a short exact snippet from the surrounding passage that reveals that relation.
- Write the explanation entirely in Korean.
""".strip()

FILL_SUMMARY_PLANNER_PROMPT = """
- Set `subtype` to `summary_completion`.
- Self-select exactly one summary-worthy span from the provided summary-oriented span inventory.
- Prefer conclusion-like, compression-friendly, claim-bearing, or passage-payoff spans, especially near the end of the passage.
- Reject short connectives, local phrase fragments, or spans that only restore a surface wording detail.
- Copy the selected span ID into `selected_span_id` and the exact source text into `selected_span_text`.
- Do not alter the source passage text or generate final student-facing paragraph text.
- Create exactly five unique English completion choices.
- Exactly one choice should best complete the passage-level takeaway; distractors should stay passage-relevant but distort the main point, scope, or conclusion.
- Set `correct_choice` to the one option that restores the intended summary/compression.
- Set `contextual_meaning_ko` to a short Korean note describing the passage-level takeaway the blank must complete.
- Write `contextual_meaning_ko` as natural Korean explanation material, not as a memo fragment. Avoid endings such as `...라는 의미`.
- Copy `supporting_evidence` as a short exact snippet that anchors that takeaway.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_ERROR_PLANNER_PROMPT = """
- Set `subtype` to `contextual_error`.
- Select exactly five unique single-word target IDs from the provided vocab-target inventory.
- Treat `target_span_ids` as the authoritative source-owned contract; `target_span_texts` should simply mirror those selected IDs.
- Choose exactly one of those five targets as `corrupted_span_id`.
- Replace only that one target with one single English word in `corrupted_word`.
- Prefer targets whose corruption can reverse or clearly distort the passage meaning, not flat content words with weak semantic pressure.
- The corrupted word should remain grammatically readable in the sentence, but it must reverse or clearly distort the passage meaning.
- Do not use a near-synonym or near-paraphrase of the original word.
- Keep the other four target words unchanged from the source.
- Set `correction_basis_ko` to a short Korean note explaining why the corrupted word does not fit and what meaning the original word supports instead.
- Make `correction_basis_ko` specific to the local textual evidence. Avoid generic notes such as `문맥상 맞지 않는다` without saying what passage meaning or contrast the original word preserves.
- Copy `supporting_evidence` as a short exact snippet from the passage that helps show why the original word fits the context.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_CHOICE_PLANNER_PROMPT = """
- Set `subtype` to `contextual_choice`.
- Select exactly one target ID from the provided lexical-slot vocab inventory.
- The target may be one English word or one short lexical phrase, but it must stay within a single lexical slot rather than a clause.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and grammar-only function words.
- Prefer targets that are abstract, evaluative, stance-bearing, contrastive, causal, or central to passage interpretation.
- Choose a target only when at least two independent contextual cues make the correct answer recoverable.
- Treat `selected_span_id` as the authoritative source-owned contract and set `selected_span_text` to the exact source wording.
- Create exactly five unique English lexical choices in `choice_words`.
- Every option must fit the same local slot and remain readable in context.
- Set `correct_choice` to the best contextual lexical fit, not automatically to the exact source wording.
- The exact source wording may remain correct, but prefer a strong non-identical contextual replacement when one is clearly better.
- Keep distractors readable, passage-relevant, and clearly wrong for a semantic reason such as polarity reversal, scope distortion, discourse-role mismatch, collocation mismatch, or evaluative drift.
- Do not use near-synonyms, loose paraphrases, or multiple defensible answers.
- Set `contextual_meaning_ko` to a short Korean teacher-facing note describing the meaning the target position must carry.
- Write `contextual_meaning_ko` as natural Korean explanation material, not as a memo fragment or `...라는 의미` note.
- Copy `supporting_evidence` as a short exact passage snippet that supports the correct lexical choice.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_BEST_PARAPHRASE_CHOICE_PLANNER_PROMPT = """
- Set `subtype` to `contextual_best_paraphrase_choice`.
- Select exactly one target ID from the provided lexical-slot vocab inventory.
- The target may be one English word or one short lexical phrase, but it must stay within a single lexical slot rather than a clause.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and grammar-only function words.
- Prefer targets that are abstract, evaluative, stance-bearing, contrastive, causal, or central to passage interpretation.
- Choose a target only when at least two independent contextual cues make the best paraphrase recoverable.
- Treat `selected_span_id` as the authoritative source-owned contract and set `selected_span_text` to the exact source wording.
- Create exactly five unique English lexical choices in `choice_words`.
- Every option must fit the same local slot and remain readable in context.
- Set `correct_choice` to the closest contextual paraphrase, not to source restoration.
- `correct_choice` must differ from `selected_span_text`, and the unchanged original wording must not appear anywhere in `choice_words`.
- The other four options must stay semantically wrong in context, not near-synonymous or jointly defensible.
- Do not use near-synonyms, loose paraphrases, or multiple defensible answers.
- Set `contextual_meaning_ko` to a short Korean teacher-facing note describing the meaning the target position must carry.
- Write `contextual_meaning_ko` as natural Korean explanation material, not as a memo fragment or `...라는 의미` note.
- Copy `supporting_evidence` as a short exact passage snippet that supports the best contextual paraphrase.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_PHRASE_CHOICE_PLANNER_PROMPT = """
- Set `subtype` to `contextual_phrase_choice`.
- Select exactly one multiword target ID from the provided phrase-only lexical-slot vocab inventory.
- The target must be a short English lexical phrase, never a single word and never a clause-sized chunk.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and dangling phrase fragments.
- Prefer phrase targets that are abstract, evaluative, stance-bearing, contrastive, causal, or central to passage interpretation.
- Choose a target only when at least two independent contextual cues make the phrase-level answer recoverable.
- Treat `selected_span_id` as the authoritative source-owned contract and set `selected_span_text` to the exact source wording.
- Create exactly five unique English phrase-level choices in `choice_words`.
- Every option must remain a short multiword lexical phrase, fit the same local slot, and preserve phrase-slot width tightly.
- The correct answer may preserve the original phrase or may be a contextual replacement, but it must stay phrase-level.
- Do not collapse the task into single-word synonym play, clause deletion, or broad sentence paraphrase.
- Keep distractors readable, passage-relevant, and clearly wrong for a semantic reason such as polarity reversal, scope distortion, collocation mismatch, or evaluative drift.
- Do not use near-synonyms, loose paraphrases, or multiple defensible answers.
- Set `contextual_meaning_ko` to a short Korean teacher-facing note describing the phrase-level meaning the slot must carry.
- Write `contextual_meaning_ko` as natural Korean explanation material, not as a memo fragment or `...라는 의미` note.
- Copy `supporting_evidence` as a short exact passage snippet that supports the correct phrase-level choice.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_CORRECT_AMONG_4_CORRUPTED_PLANNER_PROMPT = """
- Set `subtype` to `contextual_correct_among_4_corrupted`.
- Select exactly five unique target IDs from the provided lexical-slot vocab inventory.
- The targets may be English words or short lexical phrases, but each must stay within a single lexical slot rather than a clause.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and grammar-only function words.
- Prefer high-centrality targets with strong cue counts and keep the five targets separated enough that each remains readable when underlined in passage order.
- Treat `target_span_ids` as the authoritative source-owned contract and let `target_span_texts` mirror those IDs exactly.
- Build `corrupted_replacements` as an ordered list of `{span_id, replacement_text}` records so exactly four of the five selected targets are contextually corrupted.
- Set `answer_span_id` to the one remaining underlined item that still fits the passage.
- Every corrupted replacement must stay locally readable and slot-compatible, while failing semantically by polarity reversal, scope distortion, discourse-role mismatch, collocation mismatch, selectional-restriction mismatch, or evaluative stance drift.
- Do not use near-synonyms, loose paraphrases, rare-word difficulty alone, or replacements that become ungrammatical instead of semantically wrong.
- The one remaining correct item must be defensible from passage meaning, not just because it is the only untouched-looking surface form.
- Set `selection_basis_ko` to a short Korean teacher-facing note describing what meaning or role the correct remaining item preserves in context.
- Copy `supporting_evidence` as a short exact passage snippet that supports the correct lexical choice.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_ERROR_1_AMONG_5_PLANNER_PROMPT = """
- Set `subtype` to `contextual_error_1_among_5`.
- Select exactly five unique target IDs from the provided lexical-slot vocab inventory.
- The targets may be English words or short lexical phrases, but each must stay within a single lexical slot rather than a clause.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and grammar-only function words.
- Prefer targets with clear contextual recoverability and stable local readability after substitution.
- Treat `target_span_ids` as the authoritative source-owned contract and let `target_span_texts` mirror those IDs exactly.
- Build `corrupted_replacements` as an ordered list of `{span_id, replacement_text}` records so exactly one of the five selected targets is corrupted.
- Set `answer_span_id` to that one corrupted underlined item.
- The corrupted replacement must remain locally readable and slot-compatible, but fail semantically by polarity reversal, scope distortion, discourse-role mismatch, collocation mismatch, selectional-restriction mismatch, or evaluative stance drift.
- Keep the other four underlined items unchanged from the source.
- Do not use a near-synonym, loose paraphrase, rare-word difficulty alone, or an ungrammatical replacement.
- Set `selection_basis_ko` to a short Korean teacher-facing note describing what meaning the correct original wording should preserve in context.
- Copy `supporting_evidence` as a short exact passage snippet that supports the diagnosis.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_ERROR_1_AMONG_5_POLARITY_SCOPE_PLANNER_PROMPT = """
- Set `subtype` to `contextual_error_1_among_5_polarity_scope`.
- Select exactly five unique target IDs from the provided lexical-slot vocab inventory.
- The targets may be English words or short lexical phrases, but each must stay within a single lexical slot rather than a clause.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and grammar-only function words.
- Prefer targets with strong contextual recoverability, especially where polarity, degree, or scope is tightly constrained by passage logic.
- Treat `target_span_ids` as the authoritative source-owned contract and let `target_span_texts` mirror those IDs exactly.
- Build `corrupted_replacements` as an ordered list of `{span_id, replacement_text}` records so exactly one of the five selected targets is corrupted.
- Set `answer_span_id` to that one corrupted underlined item.
- The corrupted replacement must remain locally readable and slot-compatible, but it must fail specifically by polarity reversal, degree drift, or scope distortion.
- Do not use collocation-only errors, discourse-role-only errors, rare-word difficulty alone, or an ungrammatical replacement.
- Keep the other four underlined items unchanged from the source.
- Set `selection_basis_ko` to a short Korean teacher-facing note describing the direction, degree, or range that the original wording should preserve.
- Copy `supporting_evidence` as a short exact passage snippet that supports the diagnosis.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_ERROR_1_AMONG_5_COLLOCATION_PLANNER_PROMPT = """
- Set `subtype` to `contextual_error_1_among_5_collocation`.
- Select exactly five unique target IDs from the provided lexical-slot vocab inventory.
- The targets may be English words or short lexical phrases, but each must stay within a single lexical slot rather than a clause.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and grammar-only function words.
- Prefer targets whose original wording forms a natural local combination that can be made subtly wrong through collocation or selectional-restriction mismatch.
- Treat `target_span_ids` as the authoritative source-owned contract and let `target_span_texts` mirror those IDs exactly.
- Build `corrupted_replacements` as an ordered list of `{span_id, replacement_text}` records so exactly one of the five selected targets is corrupted.
- Set `answer_span_id` to that one corrupted underlined item.
- The corrupted replacement must remain grammatically readable and slot-compatible, but it must become wrong through collocation mismatch or selectional-restriction mismatch.
- Do not use pure polarity reversal, broad semantic opposites, rare-word difficulty alone, or an ungrammatical replacement.
- Keep the other four underlined items unchanged from the source.
- Set `selection_basis_ko` to a short Korean teacher-facing note describing why the original wording is the only natural local combination in context.
- Copy `supporting_evidence` as a short exact passage snippet that supports the diagnosis.
- Write the explanation entirely in Korean.
""".strip()

VOCAB_CORRECT_AMONG_3_CORRUPTED_PLANNER_PROMPT = """
- Set `subtype` to `contextual_correct_among_3_corrupted`.
- Select exactly five unique target IDs from the provided lexical-slot vocab inventory.
- The targets may be English words or short lexical phrases, but each must stay within a single lexical slot rather than a clause.
- Reject punctuation-crossing chunks, finite-clause chunks, proper nouns, technical labels, low-value factual terms, and grammar-only function words.
- Prefer high-centrality targets whose meaning is recoverable from at least two independent contextual cues.
- Treat `target_span_ids` as the authoritative source-owned contract and let `target_span_texts` mirror those IDs exactly.
- Build `corrupted_replacements` as an ordered list of `{span_id, replacement_text}` records so exactly three of the five selected targets are contextually corrupted.
- Exactly two underlined items will remain uncorrupted; set `answer_span_id` to the one that is most strongly and uniquely supported by the passage.
- Use the extra uncorrupted item only if it is clearly weaker or less central than the answer under the passage evidence.
- Every corrupted replacement must stay locally readable and slot-compatible, while failing semantically by polarity reversal, scope distortion, discourse-role mismatch, collocation mismatch, selectional-restriction mismatch, or evaluative stance drift.
- Do not use near-synonyms, loose paraphrases, rare-word difficulty alone, or replacements that become ungrammatical instead of semantically wrong.
- Set `selection_basis_ko` to a short Korean teacher-facing note describing why the answer item alone remains the best contextual fit.
- Copy `supporting_evidence` as a short exact passage snippet that supports that judgment.
- Write the explanation entirely in Korean.
""".strip()

GRAMMAR_BASE_PLANNER_PROMPT = """
- Select exactly five unique single-word target IDs from the provided grammar-target inventory.
- Treat `target_span_ids` as the authoritative source-owned contract; `target_span_texts` should simply mirror those selected IDs.
- Choose exactly one of those five targets as `corrupted_span_id`.
- Replace only that one target with one single English word in `corrupted_word`.
- Keep the other four target words unchanged from the source.
- Set `correction_basis_ko` to a short Korean note explaining what structural cue makes the original form correct and the corrupted form wrong.
- Make `correction_basis_ko` specific to the local structure, such as a governing auxiliary, infinitive marker, agreement cue, or clause pattern. Avoid generic notes such as `문맥상 맞지 않는 형태`.
- Copy `supporting_evidence` as a short exact snippet from the passage that helps show the governing structural cue.
- Write the explanation entirely in Korean.
- The explanation must be teacher-facing: explain the structural mismatch, not schema fields or renderer mechanics.
""".strip()

GRAMMAR_SUBTYPE_PROMPTS: dict[str, str] = {
    "grammar_error_verb_form_5": (
        "- Set `subtype` to `verb_form`.\n"
        "- Keep the corruption inside the controlled verb-form family only.\n"
        "- The corrupted word must be a real English verb form chosen from the deterministic allowed family for the original target.\n"
        "- Never invent malformed pseudo-words such as `increaseed`, `reduceing`, `understanded`, or `rethinked`."
    ),
    "grammar_error_subject_verb_agreement_5": (
        "- Set `subtype` to `subject_verb_agreement`.\n"
        "- Choose targets whose form is controlled by subject-verb agreement.\n"
        "- Corrupt the original so the resulting verb clashes with singular/plural agreement while staying a real English word."
    ),
    "grammar_error_finite_nonfinite_5": (
        "- Set `subtype` to `finite_nonfinite`.\n"
        "- Choose targets whose form is controlled by infinitive, gerund, participle, or finite-vs-nonfinite selection.\n"
        "- Corrupt the original so it violates that finite/nonfinite requirement while staying a real English word."
    ),
    "grammar_error_participle_voice_5": (
        "- Set `subtype` to `participle_voice`.\n"
        "- Choose targets whose form is controlled by participle choice or voice-sensitive participial structure.\n"
        "- Corrupt the original into a wrong participial or voice-related form while staying a real English word."
    ),
    "grammar_error_relative_clause_5": (
        "- Set `subtype` to `relative_clause`.\n"
        "- Choose targets whose local clause link or clause-internal form is anchored by a relative-clause structure.\n"
        "- Corrupt the target so the resulting wording clashes with the relative-clause pattern while staying readable English."
    ),
    "grammar_error_noun_clause_introducer_5": (
        "- Set `subtype` to `noun_clause_introducer`.\n"
        "- Choose targets whose local structure depends on an appropriate noun-clause introducer or clause-selecting form.\n"
        "- Corrupt the target so the resulting clause selection becomes structurally wrong while staying readable English."
    ),
    "grammar_error_parallel_structure_5": (
        "- Set `subtype` to `parallel_structure`.\n"
        "- Choose targets participating in a local parallel structure.\n"
        "- Corrupt one target so the parallel series no longer matches in form while staying readable English."
    ),
    "grammar_error_conjunction_preposition_5": (
        "- Set `subtype` to `conjunction_preposition`.\n"
        "- Choose targets whose local role depends on conjunction/preposition choice.\n"
        "- Corrupt one target into a wrong conjunction/preposition-type form or role while staying readable English."
    ),
}


@dataclass(frozen=True)
class QuestionFamilySpec:
    label_ko: str
    family_label_ko: str | None = None
    subtype_key: str | None = None
    subtype_label_ko: str | None = None
    format_key: str | None = None
    planner_prompt: str | None = None
    question_stem: str | None = None
    unit_level: str | None = None
    renderer_key: str | None = None
    validator_key: str | None = None
    plan_schema: type | None = None
    draft_schema: type | None = None
    min_source_units: int | None = None
    choice_count: int | None = None


@dataclass(frozen=True)
class QuestionTypeSpec:
    family_key: str
    family_label_ko: str
    subtype_key: str
    subtype_label_ko: str
    format_key: str
    planner_prompt: str
    question_stem: str
    unit_level: str
    renderer_key: str
    validator_key: str
    plan_schema: type
    draft_schema: type
    min_source_units: int | None = None
    choice_count: int | None = None

    @property
    def label_ko(self) -> str:
        return self.family_label_ko


QUESTION_FAMILY_SPECS: dict[str, QuestionFamilySpec] = {
    "sentence_insertion": QuestionFamilySpec(label_ko="문장 삽입"),
    "paragraph_ordering": QuestionFamilySpec(label_ko="글의 순서"),
    "mood_atmosphere": QuestionFamilySpec(label_ko="심경·분위기"),
    "underlined_phrase_meaning": QuestionFamilySpec(label_ko="밑줄 친 부분 의미"),
    "fill_in_the_blank": QuestionFamilySpec(label_ko="빈칸 추론"),
    "vocab": QuestionFamilySpec(label_ko="어휘"),
    "grammar": QuestionFamilySpec(label_ko="어법"),
}


def _spec(
    *,
    family_key: str,
    subtype_key: str,
    subtype_label_ko: str,
    format_key: str,
    planner_prompt: str,
    question_stem: str,
    unit_level: str,
    renderer_key: str,
    validator_key: str,
    plan_schema: type,
    draft_schema: type,
    min_source_units: int | None,
    choice_count: int | None,
) -> QuestionTypeSpec:
    return QuestionTypeSpec(
        family_key=family_key,
        family_label_ko=QUESTION_FAMILY_SPECS[family_key].label_ko,
        subtype_key=subtype_key,
        subtype_label_ko=subtype_label_ko,
        format_key=format_key,
        planner_prompt=planner_prompt,
        question_stem=question_stem,
        unit_level=unit_level,
        renderer_key=renderer_key,
        validator_key=validator_key,
        plan_schema=plan_schema,
        draft_schema=draft_schema,
        min_source_units=min_source_units,
        choice_count=choice_count,
    )


CONTEXTUAL_VOCAB_ERROR_SPEC = _spec(
    family_key="vocab",
    subtype_key="contextual_vocab_error_5",
    subtype_label_ko="어휘 오류 찾기",
    format_key="contextual_vocab_error_5",
    planner_prompt=VOCAB_ERROR_PLANNER_PROMPT,
    question_stem=VOCAB_ERROR_STEM,
    unit_level="span",
    renderer_key="vocab",
    validator_key="vocab",
    plan_schema=VocabPlan,
    draft_schema=VocabPlan,
    min_source_units=2,
    choice_count=5,
)


QUESTION_TYPE_SPECS_BY_FAMILY: dict[str, tuple[QuestionTypeSpec, ...]] = {
    "sentence_insertion": (
        _spec(
            family_key="sentence_insertion",
            subtype_key="sentence_insertion_5_gaps",
            subtype_label_ko="5개 위치 문장 삽입",
            format_key="sentence_insertion_5_gaps",
            planner_prompt=SENTENCE_INSERTION_PLANNER_PROMPT,
            question_stem=SENTENCE_INSERTION_STEM,
            unit_level="sentence",
            renderer_key="sentence_insertion",
            validator_key="sentence_insertion",
            plan_schema=SentenceInsertionPlan,
            draft_schema=SentenceInsertionDraft,
            min_source_units=5,
            choice_count=5,
        ),
    ),
    "paragraph_ordering": (
        _spec(
            family_key="paragraph_ordering",
            subtype_key="abc_ordering_after_intro",
            subtype_label_ko="도입 후 이어지는 글 순서",
            format_key="abc_ordering_after_intro",
            planner_prompt=PARAGRAPH_ORDERING_PLANNER_PROMPT,
            question_stem=PARAGRAPH_ORDERING_STEM,
            unit_level="sentence",
            renderer_key="paragraph_ordering",
            validator_key="paragraph_ordering",
            plan_schema=ParagraphOrderingPlan,
            draft_schema=ParagraphOrderingDraft,
            min_source_units=6,
            choice_count=5,
        ),
    ),
    "mood_atmosphere": (
        _spec(
            family_key="mood_atmosphere",
            subtype_key="emotion_shift_pair_choice_5",
            subtype_label_ko="심경 변화",
            format_key="emotion_shift_pair_choice_5",
            planner_prompt=MOOD_SHIFT_PLANNER_PROMPT,
            question_stem=MOOD_SHIFT_STEM,
            unit_level="passage",
            renderer_key="mood_atmosphere",
            validator_key="mood_atmosphere",
            plan_schema=MoodAtmospherePlan,
            draft_schema=MoodAtmospherePlan,
            min_source_units=5,
            choice_count=5,
        ),
        _spec(
            family_key="mood_atmosphere",
            subtype_key="emotion_state_choice_5",
            subtype_label_ko="심경 상태",
            format_key="emotion_state_choice_5",
            planner_prompt=MOOD_STATE_PLANNER_PROMPT,
            question_stem=MOOD_STATE_STEM,
            unit_level="passage",
            renderer_key="mood_atmosphere",
            validator_key="mood_atmosphere",
            plan_schema=MoodAtmospherePlan,
            draft_schema=MoodAtmospherePlan,
            min_source_units=4,
            choice_count=5,
        ),
        _spec(
            family_key="mood_atmosphere",
            subtype_key="atmosphere_choice_5",
            subtype_label_ko="분위기",
            format_key="atmosphere_choice_5",
            planner_prompt=ATMOSPHERE_PLANNER_PROMPT,
            question_stem=ATMOSPHERE_STEM,
            unit_level="passage",
            renderer_key="mood_atmosphere",
            validator_key="mood_atmosphere",
            plan_schema=MoodAtmospherePlan,
            draft_schema=MoodAtmospherePlan,
            min_source_units=4,
            choice_count=5,
        ),
    ),
    "underlined_phrase_meaning": (
        _spec(
            family_key="underlined_phrase_meaning",
            subtype_key="underlined_phrase_meaning_5_ko",
            subtype_label_ko="문맥상 밑줄 의미 파악",
            format_key="underlined_phrase_meaning_5_ko",
            planner_prompt=UNDERLINED_PHRASE_MEANING_PLANNER_PROMPT,
            question_stem=UNDERLINED_PHRASE_MEANING_STEM,
            unit_level="span",
            renderer_key="underlined_phrase_meaning",
            validator_key="underlined_phrase_meaning",
            plan_schema=UnderlinedPhraseMeaningPlan,
            draft_schema=UnderlinedPhraseMeaningDraft,
            min_source_units=2,
            choice_count=5,
        ),
    ),
    "fill_in_the_blank": (
        _spec(
            family_key="fill_in_the_blank",
            subtype_key="blank_inference_proposition_5_choices",
            subtype_label_ko="명제 복원 빈칸 추론",
            format_key="blank_inference_proposition_5_choices",
            planner_prompt=FILL_PROPOSITION_PLANNER_PROMPT,
            question_stem=FILL_IN_THE_BLANK_STEM,
            unit_level="span",
            renderer_key="fill_in_the_blank",
            validator_key="fill_in_the_blank",
            plan_schema=FillInTheBlankPlan,
            draft_schema=FillInTheBlankDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="fill_in_the_blank",
            subtype_key="blank_connective_relation_5_choices",
            subtype_label_ko="연결 관계 복원 빈칸",
            format_key="blank_connective_relation_5_choices",
            planner_prompt=FILL_CONNECTIVE_PLANNER_PROMPT,
            question_stem=FILL_IN_THE_BLANK_STEM,
            unit_level="span",
            renderer_key="fill_in_the_blank",
            validator_key="fill_in_the_blank",
            plan_schema=FillInTheBlankPlan,
            draft_schema=FillInTheBlankDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="fill_in_the_blank",
            subtype_key="blank_summary_completion_5_choices",
            subtype_label_ko="요약 완성 빈칸",
            format_key="blank_summary_completion_5_choices",
            planner_prompt=FILL_SUMMARY_PLANNER_PROMPT,
            question_stem=FILL_IN_THE_BLANK_STEM,
            unit_level="span",
            renderer_key="fill_in_the_blank",
            validator_key="fill_in_the_blank",
            plan_schema=FillInTheBlankPlan,
            draft_schema=FillInTheBlankDraft,
            min_source_units=2,
            choice_count=5,
        ),
    ),
    "vocab": (
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_choice_5",
            subtype_label_ko="문맥상 어휘 선택",
            format_key="contextual_vocab_choice_5",
            planner_prompt=VOCAB_CHOICE_PLANNER_PROMPT,
            question_stem=VOCAB_CHOICE_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=ContextualVocabChoicePlan,
            draft_schema=ContextualVocabChoiceDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_best_paraphrase_choice_5",
            subtype_label_ko="문맥상 최적 바꿔쓰기 선택",
            format_key="contextual_vocab_best_paraphrase_choice_5",
            planner_prompt=VOCAB_BEST_PARAPHRASE_CHOICE_PLANNER_PROMPT,
            question_stem=VOCAB_CHOICE_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=ContextualVocabChoicePlan,
            draft_schema=ContextualVocabChoiceDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_phrase_choice_5",
            subtype_label_ko="문맥상 어구 선택",
            format_key="contextual_vocab_phrase_choice_5",
            planner_prompt=VOCAB_PHRASE_CHOICE_PLANNER_PROMPT,
            question_stem=VOCAB_CHOICE_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=ContextualVocabChoicePlan,
            draft_schema=ContextualVocabChoiceDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_correct_among_4_corrupted_5",
            subtype_label_ko="문맥상 옳은 어휘 선택",
            format_key="contextual_vocab_correct_among_4_corrupted_5",
            planner_prompt=VOCAB_CORRECT_AMONG_4_CORRUPTED_PLANNER_PROMPT,
            question_stem=VOCAB_CORRECT_AMONG_4_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=UnderlinedVocabPlan,
            draft_schema=UnderlinedVocabDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_error_1_among_5_5",
            subtype_label_ko="문맥상 어휘 오류 찾기",
            format_key="contextual_vocab_error_1_among_5_5",
            planner_prompt=VOCAB_ERROR_1_AMONG_5_PLANNER_PROMPT,
            question_stem=VOCAB_ERROR_1_AMONG_5_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=UnderlinedVocabPlan,
            draft_schema=UnderlinedVocabDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_error_1_among_5_polarity_scope_5",
            subtype_label_ko="문맥상 어휘 오류 찾기(극성·범위)",
            format_key="contextual_vocab_error_1_among_5_polarity_scope_5",
            planner_prompt=VOCAB_ERROR_1_AMONG_5_POLARITY_SCOPE_PLANNER_PROMPT,
            question_stem=VOCAB_ERROR_1_AMONG_5_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=UnderlinedVocabPlan,
            draft_schema=UnderlinedVocabDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_error_1_among_5_collocation_5",
            subtype_label_ko="문맥상 어휘 오류 찾기(결합 관계)",
            format_key="contextual_vocab_error_1_among_5_collocation_5",
            planner_prompt=VOCAB_ERROR_1_AMONG_5_COLLOCATION_PLANNER_PROMPT,
            question_stem=VOCAB_ERROR_1_AMONG_5_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=UnderlinedVocabPlan,
            draft_schema=UnderlinedVocabDraft,
            min_source_units=2,
            choice_count=5,
        ),
        _spec(
            family_key="vocab",
            subtype_key="contextual_vocab_correct_among_3_corrupted_5",
            subtype_label_ko="문맥상 남는 어휘 선택",
            format_key="contextual_vocab_correct_among_3_corrupted_5",
            planner_prompt=VOCAB_CORRECT_AMONG_3_CORRUPTED_PLANNER_PROMPT,
            question_stem=VOCAB_CORRECT_AMONG_3_STEM,
            unit_level="span",
            renderer_key="vocab",
            validator_key="vocab",
            plan_schema=UnderlinedVocabPlan,
            draft_schema=UnderlinedVocabDraft,
            min_source_units=2,
            choice_count=5,
        ),
    ),
    "grammar": tuple(
        _spec(
            family_key="grammar",
            subtype_key=subtype_key,
            subtype_label_ko=subtype_label_ko,
            format_key=subtype_key,
            planner_prompt=f"{GRAMMAR_BASE_PLANNER_PROMPT}\n{GRAMMAR_SUBTYPE_PROMPTS[subtype_key]}",
            question_stem=GRAMMAR_STEM,
            unit_level="span",
            renderer_key="grammar",
            validator_key="grammar",
            plan_schema=GrammarPlan,
            draft_schema=GrammarDraft,
            min_source_units=2,
            choice_count=5,
        )
        for subtype_key, subtype_label_ko in (
            ("grammar_error_verb_form_5", "동사 형태"),
            ("grammar_error_subject_verb_agreement_5", "수 일치"),
            ("grammar_error_finite_nonfinite_5", "정형/비정형"),
            ("grammar_error_participle_voice_5", "분사/태"),
            ("grammar_error_relative_clause_5", "관계절"),
            ("grammar_error_noun_clause_introducer_5", "명사절 연결"),
            ("grammar_error_parallel_structure_5", "병렬 구조"),
            ("grammar_error_conjunction_preposition_5", "접속사/전치사"),
        )
    ),
}

QUESTION_SUBTYPE_SPECS: dict[str, QuestionTypeSpec] = {
    spec.subtype_key: spec
    for specs in QUESTION_TYPE_SPECS_BY_FAMILY.values()
    for spec in specs
}
QUESTION_SUBTYPE_SPECS[CONTEXTUAL_VOCAB_ERROR_SPEC.subtype_key] = CONTEXTUAL_VOCAB_ERROR_SPEC

QUESTION_TYPES = {
    family_key: QuestionFamilySpec(
        label_ko=family_spec.label_ko,
        family_label_ko=family_spec.label_ko,
        subtype_key=specs[0].subtype_key,
        subtype_label_ko=specs[0].subtype_label_ko,
        format_key=specs[0].format_key,
        planner_prompt=specs[0].planner_prompt,
        question_stem=specs[0].question_stem,
        unit_level=specs[0].unit_level,
        renderer_key=specs[0].renderer_key,
        validator_key=specs[0].validator_key,
        plan_schema=specs[0].plan_schema,
        draft_schema=specs[0].draft_schema,
        min_source_units=specs[0].min_source_units,
        choice_count=specs[0].choice_count,
    )
    for family_key, (family_spec, specs) in (
        (family_key, (QUESTION_FAMILY_SPECS[family_key], specs))
        for family_key, specs in QUESTION_TYPE_SPECS_BY_FAMILY.items()
        if family_key != "mood_atmosphere"
    )
}

MOOD_ATMOSPHERE_SPEC = QUESTION_SUBTYPE_SPECS["emotion_shift_pair_choice_5"]


def resolve_question_type_spec(question_type_key: str, question_subtype_key: str | None = None) -> QuestionTypeSpec | None:
    specs = QUESTION_TYPE_SPECS_BY_FAMILY.get(question_type_key)
    if not specs:
        return None
    if question_subtype_key is None:
        return specs[0]
    live_spec = next((spec for spec in specs if spec.subtype_key == question_subtype_key), None)
    if live_spec is not None:
        return live_spec
    dormant_spec = QUESTION_SUBTYPE_SPECS.get(question_subtype_key)
    if dormant_spec is not None and dormant_spec.family_key == question_type_key:
        return dormant_spec
    return None


def expand_question_type_keys(question_type_keys: list[str] | tuple[str, ...]) -> list[QuestionTypeSpec]:
    expanded: list[QuestionTypeSpec] = []
    for family_key in question_type_keys:
        specs = QUESTION_TYPE_SPECS_BY_FAMILY.get(family_key)
        if specs:
            expanded.extend(specs)
    return expanded
