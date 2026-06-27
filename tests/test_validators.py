from __future__ import annotations

import unittest

from questiongen.parsers import prepare_source
from questiongen.question_types import MOOD_ATMOSPHERE_SPEC, QUESTION_SUBTYPE_SPECS, QUESTION_TYPES, expand_question_type_keys
from questiongen.schemas import (
    ContextualVocabChoicePlan,
    FillInTheBlankPlan,
    GapUnit,
    GeneratedQuestion,
    GrammarPlan,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    PreparedSource,
    SpanUnit,
    UnderlinedVocabDesign,
    UnderlinedVocabPlan,
    VocabChoiceDesign,
    VocabPlan,
    SentenceInsertionPlan,
    SourceUnit,
    UnderlinedPhraseMeaningPlan,
)
from questiongen.targeting import (
    allowed_verb_form_variants,
    fill_blank_target_inventory,
    fill_blank_span_quality_error,
    grammar_target_inventory,
    phrase_span_inventory,
    render_numbered_span_edits,
    underlined_span_quality_error,
    vocab_hard_candidate_inventory,
    vocab_hard_bundle,
    vocab_choice_inventory,
    vocab_choice_target_cue_count,
    vocab_choice_target_quality_error,
    vocab_target_inventory,
)
from questiongen.validators import (
    plan_check,
    source_check,
    validate_fill_in_the_blank_output,
    validate_grammar_output,
    validate_mood_atmosphere_output,
    validate_plan_against_prepared_source,
    validate_prepared_source,
    validate_paragraph_ordering_output,
    validate_question_type_compatibility,
    validate_sentence_insertion_output,
    validate_teacher_facing_explanation,
    validate_underlined_phrase_meaning_output,
    validate_vocab_output,
)


def _manual_prepared_source_with_vocab_spans(
    sentences: list[str],
    span_specs: list[tuple[int, str, list[str], int]],
) -> PreparedSource:
    source = " ".join(sentences)
    sentence_units = [SourceUnit(id=f"S{index}", text=text, index=index) for index, text in enumerate(sentences)]
    gap_units = [
        GapUnit(
            id=f"G{index}",
            index=index,
            before_unit_id=f"S{index - 1}" if index > 0 else None,
            after_unit_id=f"S{index}" if index < len(sentences) else None,
        )
        for index in range(len(sentences) + 1)
    ]
    sentence_starts: list[int] = []
    cursor = 0
    for sentence in sentences:
        sentence_starts.append(cursor)
        cursor += len(sentence) + 1

    span_units: list[SpanUnit] = []
    for span_index, (sentence_index, word, tags, priority_score) in enumerate(span_specs):
        sentence_text = sentences[sentence_index]
        sentence_start = sentence_starts[sentence_index]
        local_start = sentence_text.index(word)
        char_start = sentence_start + local_start
        char_end = char_start + len(word)
        span_units.append(
            SpanUnit(
                id=f"P{span_index}",
                text=word,
                normalized_text=word.lower(),
                char_start=char_start,
                char_end=char_end,
                sentence_unit_id=f"S{sentence_index}",
                sentence_index=sentence_index,
                context_before=sentence_text[:local_start],
                context_after=sentence_text[local_start + len(word) :],
                heuristic_tags=tags,
                priority_score=priority_score,
            )
        )

    return PreparedSource(
        source_text=source,
        sentence_units=sentence_units,
        gap_units=gap_units,
        span_units=span_units,
    )


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.type_spec = QUESTION_TYPES["sentence_insertion"]
        self.prepared = prepare_source("A. B. C. D. E. F.")

    def test_source_check_marks_too_few_sentences_as_incompatibility(self) -> None:
        prepared = prepare_source("A. B. C. D.")
        result = source_check(
            {
                "source_paragraph": "A. B. C. D.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": prepared,
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            self.type_spec,
        )
        self.assertEqual(result["status"], "qtype_incompatibility_error")

    def test_source_check_fails_for_malformed_gap(self) -> None:
        self.prepared.gap_units[1].before_unit_id = "BROKEN"
        result = source_check(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": self.prepared,
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            self.type_spec,
        )
        self.assertEqual(result["status"], "source_error")

    def test_source_check_passes_for_valid_prepared_source(self) -> None:
        result = source_check(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": self.prepared,
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            self.type_spec,
        )
        self.assertEqual(result["status"], "source_passed")

    def test_source_check_accepts_complete_terminal_to_sentence_in_row9_passage(self) -> None:
        source = (
            "Looking forward to cheering for their high school football team, over a thousand people appeared at the field. "
            "There was a long line at the ticket booth that stretched down the street. "
            "The delicious smell of popcorn and hot dogs was everywhere, and the refreshment stand ran out of food before halftime. "
            "Everyone was cheering: the crowd waving flags, the cheerleaders, the band that played loud music, the players, the officials, the parents running the hot dog stand, the policeman, even me! "
            "The cheerleaders were whistling and stomping their feet on the aluminum bleachers, making a loud noise. "
            "The cheerleaders looked up in delighted surprise. "
            "For the first time, they were hearing something come back from the backflips and even a three-tier pyramid. "
            "The old-timers said it was the loudest, most exciting game they’d ever been to."
        )
        result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "9",
                "BatchRowId": 8,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": prepare_source(source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            self.type_spec,
        )
        self.assertEqual(result["status"], "source_passed")

    def test_sentence_insertion_source_check_rejects_passage_without_two_sided_target(self) -> None:
        source = (
            "Plants need water to grow. "
            "Birds build nests in spring. "
            "Winter nights are often cold. "
            "Metal expands when heated. "
            "Rivers slowly carve valleys."
        )
        result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "11-05",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": prepare_source(source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            self.type_spec,
        )
        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("stable sentence-insertion target" in error for error in result["errors"]))

    def test_prepared_source_rejects_fragmentary_sentence_units(self) -> None:
        prepared = PreparedSource(
            source_text="Even now, in the U.S. and U.K., no pizza menu seems complete without it.",
            sentence_units=[
                SourceUnit(id="S0", text="Even now, in the U.S.", index=0),
                SourceUnit(id="S1", text="and U.K., no pizza menu seems complete without it.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[],
        )
        errors = validate_prepared_source(prepared)
        self.assertTrue(any("fragmentary" in error for error in errors))

    def test_mood_atmosphere_source_check_rejects_neutral_passage(self) -> None:
        neutral_source = "Markets respond to prices over time. Producers adjust output when costs rise. Consumers compare alternatives before buying. Public policy can influence incentives in different sectors. Long-term trends often depend on resource allocation."
        result = source_check(
            {
                "source_paragraph": neutral_source,
                "OriginalQuestionNumber": "12-02",
                "BatchRowId": 0,
                "QuestionTypeKey": "mood_atmosphere",
                "prepared_source": prepare_source(neutral_source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            MOOD_ATMOSPHERE_SPEC,
        )
        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("affective cues" in error for error in result["errors"]))

    def test_underlined_phrase_meaning_source_check_rejects_literal_passage(self) -> None:
        literal_source = (
            "The boy picked up the heavy wooden box and carried it across the field. "
            "The dog waited near the fence and watched him. "
            "A truck stopped beside the road before sunset."
        )
        result = source_check(
            {
                "source_paragraph": literal_source,
                "OriginalQuestionNumber": "11-01",
                "BatchRowId": 0,
                "QuestionTypeKey": "underlined_phrase_meaning",
                "prepared_source": prepare_source(literal_source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("too literal" in error for error in result["errors"]))

    def test_underlined_phrase_meaning_source_check_rejects_pizza_passage_as_weak_inventory(self) -> None:
        pizza_source = (
            "Some people love this combination, whereas others can’t seem to stand it. "
            "It can even cause quite heated arguments. "
            "If you haven’t guessed already, it’s the tasty or nasty - depending on your taste - ham and pineapple pizza. "
            "The man who created this pizza was neither Italian nor Hawaiian. "
            "A Greek immigrant from Canada, Sam Panopoulos did not want to stick to the usual ingredients on pizzas, like pepperoni and mushrooms. "
            "He spread canned pineapple and sliced ham onto a pizza and called it “the Hawaiian” as that was what was written on the pineapple can. "
            "Hardly did he know that he had created a classic combination. "
            "Even now, in the U.S. and U.K., no pizza menu seems complete without it. "
            "In Italy, however, most people find pineapple on pizza distasteful. "
            "Why is the Hawaiian pizza so divisive? "
            "The combination is not that odd. "
            "Pineapple and ham is not the only fruit and meat pairing in kitchens around the world. "
            "In France, duck is paired with a sweet orange sauce, and an American Thanksgiving turkey dinner would not be complete without cranberry sauce. "
            "Many people enjoy salty and sweet flavor combinations, while some others prefer keeping those tastes as far from each other as possible."
        )
        result = source_check(
            {
                "source_paragraph": pizza_source,
                "OriginalQuestionNumber": "10-03",
                "BatchRowId": 0,
                "QuestionTypeKey": "underlined_phrase_meaning",
                "prepared_source": prepare_source(pizza_source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("not central enough" in error or "too literal" in error for error in result["errors"]))

    def test_underlined_phrase_meaning_quality_gate_rejects_punctuation_crossing_fragment(self) -> None:
        source = (
            "The committee, after a long delay, announced a new policy. "
            "The reaction, however, remained sharply divided. "
            "Some praised the plan, while others questioned its cost."
        )
        prepared = prepare_source(source)
        bad_span = next(span for span in phrase_span_inventory(prepared) if span.text == "a long delay, announced a")
        self.assertIn("awkward semantic chunk", underlined_span_quality_error(bad_span) or "")

    def test_paragraph_ordering_source_check_rejects_parallel_example_passage_early(self) -> None:
        source = (
            "Researchers use migration stories to compare how birds react to seasonal change. "
            "In Canada, geese travel south when the lakes freeze each winter. "
            "In Europe, storks leave their nesting grounds as temperatures drop. "
            "In Asia, cranes move between wetlands during the dry season. "
            "Each route reflects a local climate pattern. "
            "Together, these cases show how migration follows environmental pressure."
        )
        result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "12-06",
                "BatchRowId": 0,
                "QuestionTypeKey": "paragraph_ordering",
                "prepared_source": prepare_source(source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("strongly forced adjacency boundaries" in error for error in result["errors"]))

    def test_paragraph_ordering_source_check_rejects_generic_advice_flow_early(self) -> None:
        source = (
            "It has been said that most people listen with the intention to reply rather than to understand. "
            "Facilitating your mentee’s thinking, rather than trying to do it for them, is your primary responsibility as a mentor, however tempting that may be. "
            "If during a mentoring session, you realize you're doing most of the talking, then just stop, sit back and listen with a patient mind. "
            "A good part of the mentee’s learning process, which involves dealing with complex ideas, happens when he/she thinks out loud. "
            "Therefore, your mentee should be doing most of the talking. "
            "Listening actively and empathically helps a mentee to have a sense of having their thoughts valued and acknowledged; it is essential that you listen well."
        )
        result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "8",
                "BatchRowId": 0,
                "QuestionTypeKey": "paragraph_ordering",
                "prepared_source": prepare_source(source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("strongly forced adjacency boundaries" in error for error in result["errors"]))

    def test_paragraph_ordering_source_check_accepts_question_turn_partition(self) -> None:
        source = (
            "Some people love this combination, whereas others can’t seem to stand it. "
            "It can even cause quite heated arguments. "
            "If you haven’t guessed already, it’s the tasty or nasty - depending on your taste - ham and pineapple pizza. "
            "The man who created this pizza was neither Italian nor Hawaiian. "
            "A Greek immigrant from Canada, Sam Panopoulos did not want to stick to the usual ingredients on pizzas, like pepperoni and mushrooms. "
            "He spread canned pineapple and sliced ham onto a pizza and called it “the Hawaiian” as that was what was written on the pineapple can. "
            "Hardly did he know that he had created a classic combination. "
            "Even now, in the U.S. and U.K., no pizza menu seems complete without it. "
            "In Italy, however, most people find pineapple on pizza distasteful. "
            "Why is the Hawaiian pizza so divisive? "
            "The combination is not that odd. "
            "Pineapple and ham is not the only fruit and meat pairing in kitchens around the world. "
            "In France, duck is paired with a sweet orange sauce, and an American Thanksgiving turkey dinner would not be complete without cranberry sauce. "
            "Many people enjoy salty and sweet flavor combinations, while some others prefer keeping those tastes as far from each other as possible."
        )
        result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "10",
                "BatchRowId": 0,
                "QuestionTypeKey": "paragraph_ordering",
                "prepared_source": prepare_source(source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertEqual(result["status"], "source_passed")

    def test_plan_check_rejects_collapsed_sentence_insertion_gaps_as_planning_error(self) -> None:
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G3", "G4"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        result = plan_check(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": self.prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            self.type_spec,
        )
        self.assertEqual(result["status"], "planning_error")
        self.assertTrue(any("collapse" in error for error in result["errors"]))

    def test_plan_check_rejects_invalid_paragraph_ordering_coverage(self) -> None:
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2"], ["S4", "S5"]],
            explanation="도입부 이후의 흐름을 세 덩어리로 나누는 것이 자연스럽습니다.",
        )
        result = plan_check(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 0,
                "QuestionTypeKey": "paragraph_ordering",
                "prepared_source": self.prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertEqual(result["status"], "planning_error")
        self.assertTrue(any("cover all sentence IDs" in error for error in result["errors"]))

    def test_paragraph_ordering_plan_rejects_parallel_example_blocks(self) -> None:
        source = (
            "Researchers use migration stories to compare how birds react to seasonal change. "
            "In Canada, geese travel south when the lakes freeze each winter. "
            "In Europe, storks leave their nesting grounds as temperatures drop. "
            "In Asia, cranes move between wetlands during the dry season. "
            "Each route reflects a local climate pattern. "
            "Together, these cases show how migration follows environmental pressure."
        )
        prepared = prepare_source(source)
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2"], ["S3", "S4", "S5"]],
            explanation="도입부 다음에 사례들을 배열하는 흐름입니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertTrue(any("parallel examples" in error or "too weakly forced" in error for error in errors))

    def test_paragraph_ordering_plan_rejects_generic_advice_partition(self) -> None:
        source = (
            "It has been said that most people listen with the intention to reply rather than to understand. "
            "Facilitating your mentee’s thinking, rather than trying to do it for them, is your primary responsibility as a mentor, however tempting that may be. "
            "If during a mentoring session, you realize you're doing most of the talking, then just stop, sit back and listen with a patient mind. "
            "A good part of the mentee’s learning process, which involves dealing with complex ideas, happens when he/she thinks out loud. "
            "Therefore, your mentee should be doing most of the talking. "
            "Listening actively and empathically helps a mentee to have a sense of having their thoughts valued and acknowledged; it is essential that you listen well."
        )
        prepared = prepare_source(source)
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2", "S3"], ["S4", "S5"]],
            explanation="도입부 다음에 멘토의 태도와 실천, 마무리 조언이 이어지는 흐름입니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertTrue(any("too weakly forced" in error for error in errors))

    def test_final_validator_catches_plan_and_rendering_mismatches(self) -> None:
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="8-Analysis",
            BatchRowId=0,
            QuestionType=self.type_spec.label_ko,
            student_paragraph="① A. ② B. ③ D. ④ E. ⑤ F.",
            question_stem=self.type_spec.question_stem,
            given_sentence="C.",
            choices=["①", "②", "③", "④", "⑤"],
            answer="③",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        errors = validate_sentence_insertion_output(
            prepared_source=self.prepared,
            plan=plan,
            generated=generated,
            type_spec=self.type_spec,
        )
        self.assertEqual(errors, [])

        bad_generated = GeneratedQuestion(
            OriginalQuestionNumber="8-Analysis",
            BatchRowId=0,
            QuestionType=self.type_spec.label_ko,
            student_paragraph="① A. ② B. ③ C. ④ D. ⑤ E.",
            question_stem=self.type_spec.question_stem,
            given_sentence="C.",
            choices=["①", "②", "③", "④", "⑤"],
            answer="①",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        errors = validate_sentence_insertion_output(
            prepared_source=self.prepared,
            plan=plan,
            generated=bad_generated,
            type_spec=self.type_spec,
        )
        self.assertTrue(any("Target sentence still appears" in error for error in errors))

    def test_final_validator_rejects_collapsed_gap_positions(self) -> None:
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G3", "G4"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="8-Analysis",
            BatchRowId=0,
            QuestionType=self.type_spec.label_ko,
            student_paragraph="① A. ② B. ③ ④ D. ⑤ E. F.",
            question_stem=self.type_spec.question_stem,
            given_sentence="C.",
            choices=["①", "②", "③", "④", "⑤"],
            answer="③",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        errors = validate_sentence_insertion_output(
            prepared_source=self.prepared,
            plan=plan,
            generated=generated,
            type_spec=self.type_spec,
        )
        self.assertTrue(any("collapse into duplicate rendered positions" in error for error in errors))

    def test_explanation_validator_rejects_internal_sentence_or_gap_ids(self) -> None:
        errors = validate_teacher_facing_explanation(
            "문장 S3은 앞의 내용과 연결되므로 G4에 들어가야 합니다.",
            question_type_key="sentence_insertion",
        )
        self.assertTrue(any("must not mention internal sentence or gap IDs" in error for error in errors))

    def test_explanation_validator_rejects_schema_mechanics_terms(self) -> None:
        errors = validate_teacher_facing_explanation(
            "selected_gap_ids와 correct_gap_id를 다시 확인하면 이 설명이 맞습니다.",
            question_type_key="sentence_insertion",
        )
        self.assertTrue(any("must not mention schema fields or renderer mechanics" in error for error in errors))

    def test_explanation_validator_rejects_malformed_teacher_phrase(self) -> None:
        errors = validate_teacher_facing_explanation(
            "이 자리에는 행동의 의미라는 의미가 들어가야 합니다.",
            question_type_key="fill_in_the_blank",
        )
        self.assertTrue(any("malformed or low-signal" in error for error in errors))

    def test_final_validator_rejects_internal_notation_in_explanation(self) -> None:
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="8-Analysis",
            BatchRowId=0,
            QuestionType=self.type_spec.label_ko,
            student_paragraph="① A. ② B. ③ D. ④ E. ⑤ F.",
            question_stem=self.type_spec.question_stem,
            given_sentence="C.",
            choices=["①", "②", "③", "④", "⑤"],
            answer="③",
            explanation="문장 S2는 G3 위치에 들어가야 자연스럽습니다.",
        )
        errors = validate_sentence_insertion_output(
            prepared_source=self.prepared,
            plan=plan,
            generated=generated,
            type_spec=self.type_spec,
        )
        self.assertTrue(any("must not mention internal sentence or gap IDs" in error for error in errors))

    def test_paragraph_ordering_validator_rejects_internal_notation_in_explanation(self) -> None:
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2", "S3"], ["S4", "S5"]],
            explanation="도입부 이후의 흐름을 세 덩어리로 나누는 것이 자연스럽습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="8-Analysis",
            BatchRowId=1,
            QuestionType=QUESTION_TYPES["paragraph_ordering"].label_ko,
            student_paragraph="[주어진 글] A.\n\n(A) C. D.\n\n(B) E. F.\n\n(C) B.",
            question_stem=QUESTION_TYPES["paragraph_ordering"].question_stem,
            choices=["(A)-(C)-(B)", "(B)-(A)-(C)", "(B)-(C)-(A)", "(C)-(A)-(B)", "(C)-(B)-(A)"],
            answer="②",
            explanation="S0 다음에 S1과 S2가 이어져야 하므로 이 순서가 맞습니다.",
        )
        errors = validate_paragraph_ordering_output(
            prepared_source=self.prepared,
            plan=plan,
            generated=generated,
            type_spec=QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertTrue(any("must not mention internal sentence or gap IDs" in error for error in errors))

    def test_mood_atmosphere_plan_validator_requires_source_evidence_snippets(self) -> None:
        prepared = prepare_source(
            "The child was nervous before the recital. She avoided eye contact and kept checking her hands. "
            "But after the first few notes, she smiled with growing confidence. By the end, she bowed proudly to the audience. "
            "Her parents cheered from the back of the hall."
        )
        plan = MoodAtmospherePlan(
            target_holder="the child",
            initial_emotion="nervous",
            final_emotion="proud",
            choice_pairs=[
                "nervous -> proud",
                "calm -> worried",
                "excited -> ashamed",
                "content -> relieved",
                "curious -> disappointed",
            ],
            correct_choice="nervous -> proud",
            initial_evidence="was nervous before the recital",
            final_evidence="bowed proudly to the audience",
            shift_trigger="after the first few notes",
            explanation="처음에는 긴장하지만 마지막에는 자랑스러워집니다.",
        )
        self.assertEqual(
            validate_plan_against_prepared_source(prepared, plan, MOOD_ATMOSPHERE_SPEC),
            [],
        )

        bad_plan = plan.model_copy(update={"initial_evidence": "not in the passage"})
        errors = validate_plan_against_prepared_source(prepared, bad_plan, MOOD_ATMOSPHERE_SPEC)
        self.assertTrue(any("initial_evidence" in error for error in errors))

    def test_plan_validator_matches_sentence_insertion_constraints(self) -> None:
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G3", "G4"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        errors = validate_plan_against_prepared_source(
            self.prepared,
            plan,
            QUESTION_TYPES["sentence_insertion"],
        )
        self.assertTrue(any("collapse" in error for error in errors))

    def test_sentence_insertion_plan_rejects_one_sided_connector_target(self) -> None:
        source = (
            "Many schools now rely on digital platforms for daily assignments. "
            "Students often check several apps before class even begins. "
            "However, the schedule occasionally changes without warning. "
            "Teachers then post updates across multiple channels. "
            "Parents struggle to follow the latest instructions at home. "
            "Administrators are now looking for a simpler system."
        )
        prepared = prepare_source(source)
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_TYPES["sentence_insertion"],
        )
        self.assertTrue(any("one-sided linkage" in error or "connector cues" in error for error in errors))

    def test_sentence_insertion_plan_accepts_two_sided_target(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        prepared = prepare_source(source)
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G6"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        self.assertEqual(
            validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["sentence_insertion"]),
            [],
        )

    def test_paragraph_ordering_plan_accepts_forced_adjacency_blocks(self) -> None:
        source = (
            "Many museums are rethinking how visitors experience their collections. "
            "First, they replace long wall labels with short questions that invite curiosity. "
            "This curiosity encourages people to look closely before reading an explanation. "
            "Next, curators turn that curiosity into quiet audio guides for visitors who want more detail. "
            "Those guides let each person choose how much background information to hear. "
            "Finally, the feedback gathered through those guides helps museums redesign later exhibits."
        )
        prepared = prepare_source(source)
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1", "S2"], ["S3", "S4"], ["S5"]],
            explanation="도입 뒤에 전개 단계가 순차적으로 이어집니다.",
        )
        self.assertEqual(
            validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["paragraph_ordering"]),
            [],
        )

    def test_underlined_phrase_meaning_plan_validator_requires_known_span_and_exact_text(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        prepared = prepare_source(source)
        selected_span = next(
            span
            for span in prepared.span_units
            if span.text == "resulting inequality brought only discontent"
        )
        plan = UnderlinedPhraseMeaningPlan(
            selected_span_id=selected_span.id,
            selected_span_text=selected_span.text,
            paraphrase_choices_ko=[
                "비교 속에서 상대적 박탈감만 커졌다는 뜻",
                "경제적 격차가 불만을 낳았다는 뜻",
                "보상이 충분해도 만족이 오래가지 않았다는 뜻",
                "경쟁이 심해져 분노가 겉으로 드러났다는 뜻",
                "차이가 커질수록 성취감도 함께 커졌다는 뜻",
            ],
            correct_choice="경제적 격차가 불만을 낳았다는 뜻",
            surface_meaning="오직 불만만을 가져왔다는 말",
            contextual_meaning="상대적 불평등 때문에 만족 대신 불만이 커졌다는 뜻",
            supporting_evidence="the resulting inequality brought only discontent",
            explanation="문맥상 상대적 불평등으로 인한 불만을 뜻합니다.",
        )
        self.assertEqual(
            validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["underlined_phrase_meaning"]),
            [],
        )

        bad_plan = plan.model_copy(update={"selected_span_text": "brought only satisfaction"})
        errors = validate_plan_against_prepared_source(prepared, bad_plan, QUESTION_TYPES["underlined_phrase_meaning"])
        self.assertTrue(any("selected_span_text" in error for error in errors))

    def test_underlined_phrase_meaning_plan_rejects_surface_comparison_span(self) -> None:
        source = (
            "It has been said that most people listen with the intention to reply rather than to understand. "
            "Facilitating your mentee’s thinking, rather than trying to do it for them, is your primary responsibility as a mentor, however tempting that may be. "
            "If during a mentoring session, you realize you're doing most of the talking, then just stop, sit back and listen with a patient mind. "
            "A good part of the mentee’s learning process, which involves dealing with complex ideas, happens when he/she thinks out loud. "
            "Therefore, your mentee should be doing most of the talking. "
            "Listening actively and empathically helps a mentee to have a sense of having their thoughts valued and acknowledged; it is essential that you listen well."
        )
        prepared = prepare_source(source)
        selected_span = next(span for span in prepared.span_units if span.text == "reply rather than to understand")
        self.assertTrue(
            "surface comparison phrase" in (underlined_span_quality_error(selected_span) or "")
        )

    def test_paragraph_ordering_validator_accepts_valid_output(self) -> None:
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2", "S3"], ["S4", "S5"]],
            explanation="도입부 이후의 흐름을 세 덩어리로 나누는 것이 자연스럽습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="8-Analysis",
            BatchRowId=1,
            QuestionType=QUESTION_TYPES["paragraph_ordering"].label_ko,
            student_paragraph="[주어진 글] A.\n\n(A) C. D.\n\n(B) E. F.\n\n(C) B.",
            question_stem=QUESTION_TYPES["paragraph_ordering"].question_stem,
            choices=["(A)-(C)-(B)", "(B)-(A)-(C)", "(B)-(C)-(A)", "(C)-(A)-(B)", "(C)-(B)-(A)"],
            answer="②",
            explanation="원래 흐름대로 이어지도록 배열하면 정답은 다섯 번째입니다.",
        )
        errors = validate_paragraph_ordering_output(
            prepared_source=self.prepared,
            plan=plan,
            generated=generated,
            type_spec=QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertEqual(errors, [])

    def test_mood_atmosphere_validator_accepts_valid_output(self) -> None:
        source = (
            "The child was nervous before the recital. She avoided eye contact and kept checking her hands. "
            "But after the first few notes, she smiled with growing confidence. By the end, she bowed proudly to the audience. "
            "Her parents cheered from the back of the hall."
        )
        prepared = prepare_source(source)
        plan = MoodAtmospherePlan(
            target_holder="the child",
            initial_emotion="nervous",
            final_emotion="proud",
            choice_pairs=[
                "nervous -> proud",
                "calm -> worried",
                "excited -> ashamed",
                "content -> relieved",
                "curious -> disappointed",
            ],
            correct_choice="nervous -> proud",
            initial_evidence="was nervous before the recital",
            final_evidence="bowed proudly to the audience",
            shift_trigger="after the first few notes",
            explanation="처음에는 긴장하지만 마지막에는 자랑스러워집니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="13-03",
            BatchRowId=0,
            QuestionType=MOOD_ATMOSPHERE_SPEC.label_ko,
            student_paragraph=source,
            question_stem=MOOD_ATMOSPHERE_SPEC.question_stem,
            choices=[
                "nervous -> proud",
                "calm -> worried",
                "excited -> ashamed",
                "content -> relieved",
                "curious -> disappointed",
            ],
            answer="①",
            explanation="글에서 the child는 처음에 'was nervous before the recital'에서 드러나듯 nervous한 상태입니다. 이후 'after the first few notes'를 계기로 정서의 방향이 바뀌고, 마지막에는 'bowed proudly to the audience'에서 보이듯 proud한 상태에 이릅니다. 따라서 심경 변화로 가장 적절한 것은 ① nervous -> proud입니다.",
        )
        errors = validate_mood_atmosphere_output(
            prepared_source=prepared,
            plan=plan,
            generated=generated,
            type_spec=MOOD_ATMOSPHERE_SPEC,
        )
        self.assertEqual(errors, [])

    def test_mood_atmosphere_validator_rejects_bad_choices(self) -> None:
        source = (
            "The child was nervous before the recital. She avoided eye contact and kept checking her hands. "
            "But after the first few notes, she smiled with growing confidence. By the end, she bowed proudly to the audience. "
            "Her parents cheered from the back of the hall."
        )
        prepared = prepare_source(source)
        plan = MoodAtmospherePlan(
            target_holder="the child",
            initial_emotion="nervous",
            final_emotion="proud",
            choice_pairs=[
                "nervous -> proud",
                "calm -> worried",
                "excited -> ashamed",
                "content -> relieved",
                "curious -> disappointed",
            ],
            correct_choice="nervous -> proud",
            initial_evidence="was nervous before the recital",
            final_evidence="bowed proudly to the audience",
            shift_trigger="after the first few notes",
            explanation="처음에는 긴장하지만 마지막에는 자랑스러워집니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="13-03",
            BatchRowId=0,
            QuestionType=MOOD_ATMOSPHERE_SPEC.label_ko,
            student_paragraph=source,
            question_stem=MOOD_ATMOSPHERE_SPEC.question_stem,
            choices=[
                "nervous -> proud",
                "calm -> worried",
                "excited -> ashamed",
                "content -> relieved",
                "content -> relieved",
            ],
            answer="②",
            explanation="choice_pairs를 보면 ②가 맞습니다.",
        )
        errors = validate_mood_atmosphere_output(
            prepared_source=prepared,
            plan=plan,
            generated=generated,
            type_spec=MOOD_ATMOSPHERE_SPEC,
        )
        self.assertTrue(any("choices must be unique" in error for error in errors))
        self.assertTrue(any("must not mention schema fields" in error for error in errors))

    def test_underlined_phrase_meaning_validator_accepts_valid_output(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        prepared = prepare_source(source)
        selected_span = next(
            span
            for span in prepared.span_units
            if span.text == "resulting inequality brought only discontent"
        )
        plan = UnderlinedPhraseMeaningPlan(
            selected_span_id=selected_span.id,
            selected_span_text=selected_span.text,
            paraphrase_choices_ko=[
                "비교 속에서 상대적 박탈감만 커졌다는 뜻",
                "경제적 격차가 불만을 낳았다는 뜻",
                "보상이 충분해도 만족이 오래가지 않았다는 뜻",
                "경쟁이 심해져 분노가 겉으로 드러났다는 뜻",
                "차이가 커질수록 성취감도 함께 커졌다는 뜻",
            ],
            correct_choice="경제적 격차가 불만을 낳았다는 뜻",
            surface_meaning="오직 불만만을 가져왔다는 말",
            contextual_meaning="상대적 불평등 때문에 만족 대신 불만이 커졌다는 뜻",
            supporting_evidence="the resulting inequality brought only discontent",
            explanation="문맥상 상대적 불평등으로 인한 불만을 뜻합니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="10-03",
            BatchRowId=0,
            QuestionType=QUESTION_TYPES["underlined_phrase_meaning"].label_ko,
            student_paragraph=source.replace(
                selected_span.text,
                f"[밑줄]{selected_span.text}[/밑줄]",
            ),
            question_stem=QUESTION_TYPES["underlined_phrase_meaning"].question_stem,
            choices=[
                "비교 속에서 상대적 박탈감만 커졌다는 뜻",
                "경제적 격차가 불만을 낳았다는 뜻",
                "보상이 충분해도 만족이 오래가지 않았다는 뜻",
                "경쟁이 심해져 분노가 겉으로 드러났다는 뜻",
                "차이가 커질수록 성취감도 함께 커졌다는 뜻",
            ],
            answer="②",
            explanation=(
                "밑줄 친 'resulting inequality brought only discontent'는 표면적으로는 오직 불만만을 가져왔다는 말입니다. "
                "하지만 이 글에서는 상대적 불평등 때문에 만족 대신 불만이 커졌다는 뜻으로 이해해야 합니다. "
                "특히 'the resulting inequality brought only discontent'라는 내용이 그 해석을 뒷받침하므로 "
                "정답은 ② 경제적 격차가 불만을 낳았다는 뜻입니다."
            ),
        )
        errors = validate_underlined_phrase_meaning_output(
            prepared_source=prepared,
            plan=plan,
            generated=generated,
            type_spec=QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertEqual(errors, [])

    def test_underlined_phrase_meaning_validator_rejects_non_korean_choices_and_broken_wrapper(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        prepared = prepare_source(source)
        selected_span = next(
            span
            for span in prepared.span_units
            if span.text == "resulting inequality brought only discontent"
        )
        plan = UnderlinedPhraseMeaningPlan(
            selected_span_id=selected_span.id,
            selected_span_text=selected_span.text,
            paraphrase_choices_ko=[
                "비교 속에서 상대적 박탈감만 커졌다는 뜻",
                "경제적 격차가 불만을 낳았다는 뜻",
                "보상이 충분해도 만족이 오래가지 않았다는 뜻",
                "경쟁이 심해져 분노가 겉으로 드러났다는 뜻",
                "차이가 커질수록 성취감도 함께 커졌다는 뜻",
            ],
            correct_choice="경제적 격차가 불만을 낳았다는 뜻",
            surface_meaning="오직 불만만을 가져왔다는 말",
            contextual_meaning="상대적 불평등 때문에 만족 대신 불만이 커졌다는 뜻",
            supporting_evidence="the resulting inequality brought only discontent",
            explanation="문맥상 상대적 불평등으로 인한 불만을 뜻합니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="10-03",
            BatchRowId=0,
            QuestionType=QUESTION_TYPES["underlined_phrase_meaning"].label_ko,
            student_paragraph=source.replace(
                "brought only discontent",
                "[밑줄]brought only[/밑줄] discontent",
            ),
            question_stem=QUESTION_TYPES["underlined_phrase_meaning"].question_stem,
            choices=[
                "literal gloss",
                "경제적 격차가 불만을 낳았다는 뜻",
                "보상이 충분해도 만족이 오래가지 않았다는 뜻",
                "경쟁이 심해져 분노가 겉으로 드러났다는 뜻",
                "차이가 커질수록 성취감도 함께 커졌다는 뜻",
            ],
            answer="②",
            explanation="surface_meaning을 보면 ②가 맞습니다.",
        )
        errors = validate_underlined_phrase_meaning_output(
            prepared_source=prepared,
            plan=plan,
            generated=generated,
            type_spec=QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertTrue(any("choices must contain Korean text" in error for error in errors))
        self.assertTrue(any("wrap the selected span text exactly once" in error for error in errors))
        self.assertTrue(any("must not mention schema fields" in error for error in errors))

    def test_fill_in_the_blank_source_check_accepts_workable_span_inventory(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "MVP-01",
                "BatchRowId": 0,
                "QuestionTypeKey": "fill_in_the_blank",
                "prepared_source": prepare_source(source),
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["fill_in_the_blank"],
        )
        self.assertEqual(result["status"], "source_passed")

    def test_fill_in_the_blank_quality_gate_rejects_surface_restoration_fragment(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        prepared = prepare_source(source)
        bad_span = next(span for span in phrase_span_inventory(prepared) if span.text == "use less electricity than the")
        self.assertIn("surface-restoration fragment", fill_blank_span_quality_error(bad_span) or "")

    def test_vocab_and_grammar_source_checks_accept_single_word_targets(self) -> None:
        source = (
            "The city can reduce energy use without raising taxes. "
            "Officials plan to expand the lighting system next month. "
            "Residents say the brighter streets feel safer at night. "
            "Engineers are testing whether the new lamps last longer in winter. "
            "The mayor hopes to show that the project saves money over time. "
            "Teachers report that students now walk home with more confidence."
        )
        prepared = prepare_source(source)
        vocab_result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "MVP-02",
                "BatchRowId": 0,
                "QuestionTypeKey": "vocab",
                "prepared_source": prepared,
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["vocab"],
        )
        grammar_result = source_check(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "MVP-03",
                "BatchRowId": 0,
                "QuestionTypeKey": "grammar",
                "prepared_source": prepared,
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            QUESTION_TYPES["grammar"],
        )
        self.assertEqual(vocab_result["status"], "source_passed")
        self.assertEqual(grammar_result["status"], "source_passed")

    def test_vocab_family_expands_to_four_live_subtypes_in_order(self) -> None:
        self.assertEqual(
            [spec.subtype_key for spec in expand_question_type_keys(["vocab"])],
            [
                "contextual_vocab_choice_5",
                "contextual_vocab_best_paraphrase_choice_5",
                "contextual_vocab_phrase_choice_5",
                "contextual_vocab_correct_among_4_corrupted_5",
                "contextual_vocab_error_1_among_5_5",
                "contextual_vocab_error_1_among_5_polarity_scope_5",
                "contextual_vocab_error_1_among_5_collocation_5",
                "contextual_vocab_correct_among_3_corrupted_5",
            ],
        )

    def test_vocab_quality_gate_accepts_short_phrase_target(self) -> None:
        source = "The report carries moral force in this debate. Repeated exceptions weaken the rule for everyone."
        span_text = "moral force"
        span_start = source.index(span_text)
        span = SpanUnit(
            id="P0",
            text=span_text,
            normalized_text=span_text,
            char_start=span_start,
            char_end=span_start + len(span_text),
            sentence_unit_id="S0",
            sentence_index=0,
            context_before="The report carries ",
            context_after=" in this debate.",
            heuristic_tags=["abstract_term", "phrase_frame"],
            priority_score=7,
        )
        self.assertIsNone(vocab_choice_target_quality_error(span))
        self.assertIsNone(vocab_choice_target_quality_error(span, subtype_key="contextual_vocab_phrase_choice_5"))

    def test_vocab_phrase_choice_quality_gate_rejects_single_word_target(self) -> None:
        source = "Residents show strong support during the winter drive. Teachers discuss the safety map every week."
        span_text = "support"
        span_start = source.index(span_text)
        span = SpanUnit(
            id="P0",
            text=span_text,
            normalized_text=span_text,
            char_start=span_start,
            char_end=span_start + len(span_text),
            sentence_unit_id="S0",
            sentence_index=0,
            context_before="Residents show strong ",
            context_after=" during the winter drive.",
            heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
            priority_score=7,
        )
        self.assertIn(
            "multiword phrase",
            vocab_choice_target_quality_error(span, subtype_key="contextual_vocab_phrase_choice_5") or "",
        )

    def test_vocab_quality_gate_rejects_punctuation_crossing_phrase_target(self) -> None:
        source = "The committee, after a long delay, announced a new policy. Reactions stayed divided afterward."
        span_text = "delay, announced"
        span_start = source.index(span_text)
        span = SpanUnit(
            id="P0",
            text=span_text,
            normalized_text=span_text,
            char_start=span_start,
            char_end=span_start + len(span_text),
            sentence_unit_id="S0",
            sentence_index=0,
            context_before="The committee, after a long ",
            context_after=" a new policy.",
            heuristic_tags=["phrase_frame"],
            priority_score=7,
        )
        self.assertIn("crosses punctuation", vocab_choice_target_quality_error(span) or "")

    def test_vocab_quality_gate_rejects_clause_like_phrase_target(self) -> None:
        source = "The report does more than summarize the delay. It sharply limits a broader claim."
        span_text = "does more than summarize"
        span_start = source.index(span_text)
        span = SpanUnit(
            id="P0",
            text=span_text,
            normalized_text=span_text,
            char_start=span_start,
            char_end=span_start + len(span_text),
            sentence_unit_id="S0",
            sentence_index=0,
            context_before="The report ",
            context_after=" the delay.",
            heuristic_tags=["contextual_cue", "phrase_frame"],
            priority_score=7,
        )
        self.assertIn("clause-like", vocab_choice_target_quality_error(span) or "")

    def test_vocab_quality_gate_rejects_technical_and_function_targets(self) -> None:
        technical_source = "The new LED system reduced costs for the district."
        technical_span = SpanUnit(
            id="P0",
            text="LED",
            normalized_text="LED",
            char_start=technical_source.index("LED"),
            char_end=technical_source.index("LED") + 3,
            sentence_unit_id="S0",
            sentence_index=0,
            context_before="The new ",
            context_after=" system reduced costs for the district.",
            heuristic_tags=["single_word", "vocab_candidate"],
            priority_score=8,
        )
        function_source = "Because the rule weakened, support faded quickly."
        function_span = SpanUnit(
            id="P1",
            text="Because",
            normalized_text="Because",
            char_start=0,
            char_end=len("Because"),
            sentence_unit_id="S0",
            sentence_index=0,
            context_before=None,
            context_after=" the rule weakened, support faded quickly.",
            heuristic_tags=["single_word", "contextual_cue", "vocab_candidate"],
            priority_score=8,
        )
        self.assertIn("technical label", vocab_choice_target_quality_error(technical_span) or "")
        self.assertIn("function target", vocab_choice_target_quality_error(function_span) or "")

    def test_vocab_hard_subtype_compatibility_rejects_weak_single_cue_target(self) -> None:
        source = "The plan offered support to nearby residents. People discussed the idea again the next day."
        support_start = source.index("support")
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="The plan offered support to nearby residents.", index=0),
                SourceUnit(id="S1", text="People discussed the idea again the next day.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text="support",
                    normalized_text="support",
                    char_start=support_start,
                    char_end=support_start + len("support"),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="The plan offered ",
                    context_after=" to nearby residents.",
                    heuristic_tags=["single_word", "vocab_candidate"],
                    priority_score=5,
                )
            ],
        )
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
        )
        self.assertTrue(
            any(
                "workable lexical-slot vocab target" in error or "stable five-target vocab bundle" in error
                for error in errors
            )
        )

    def test_underlined_vocab_schema_uses_structured_replacement_records(self) -> None:
        schema = UnderlinedVocabPlan.model_json_schema()
        self.assertIn("corrupted_replacements", schema["properties"])
        self.assertNotIn("corrupted_replacements_by_span_id", schema["properties"])
        self.assertEqual(schema["properties"]["corrupted_replacements"]["type"], "array")
        replacement_def = schema.get("$defs", {}).get("UnderlinedVocabReplacement", {})
        self.assertIn("span_id", replacement_def.get("properties", {}))
        self.assertIn("replacement_text", replacement_def.get("properties", {}))

    def test_vocab_hard_subtype_compatibility_accepts_five_clean_base_candidates_without_old_hard_gate(self) -> None:
        sentences = [
            "The committee offered steady guidance to new teachers.",
            "Local mentors provide support for new teachers.",
            "City leaders made careful changes after storms.",
            "Brighter signs keep evening crossings safer for children.",
            "Volunteers protect fragile habitats during repairs.",
        ]
        source = " ".join(sentences)
        sentence_units = [SourceUnit(id=f"S{index}", text=text, index=index) for index, text in enumerate(sentences)]
        gap_units = [
            GapUnit(
                id=f"G{index}",
                index=index,
                before_unit_id=f"S{index - 1}" if index > 0 else None,
                after_unit_id=f"S{index}" if index < len(sentences) else None,
            )
            for index in range(len(sentences) + 1)
        ]
        candidate_words = ["steady", "support", "careful", "safer", "protect"]
        span_units: list[SpanUnit] = []
        search_start = 0
        for index, word in enumerate(candidate_words):
            char_start = source.index(word, search_start)
            char_end = char_start + len(word)
            sentence_text = sentences[index]
            sentence_start = source.index(sentence_text)
            sentence_offset = char_start - sentence_start
            span_units.append(
                SpanUnit(
                    id=f"P{index}",
                    text=word,
                    normalized_text=word,
                    char_start=char_start,
                    char_end=char_end,
                    sentence_unit_id=f"S{index}",
                    sentence_index=index,
                    context_before=sentence_text[:sentence_offset],
                    context_after=sentence_text[sentence_offset + len(word) :],
                    heuristic_tags=["single_word", "contextual_cue", "vocab_candidate"],
                    priority_score=5,
                )
            )
            search_start = char_end

        prepared = PreparedSource(
            source_text=source,
            sentence_units=sentence_units,
            gap_units=gap_units,
            span_units=span_units,
        )

        self.assertEqual(len(vocab_hard_candidate_inventory(prepared)), 5)
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
        )
        self.assertEqual(errors, [])

    def test_fill_in_the_blank_validator_accepts_valid_output(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        prepared = prepare_source(source)
        selected_span = next(span for span in fill_blank_target_inventory(prepared) if "improve safety" in span.text)
        plan = FillInTheBlankPlan(
            selected_span_id=selected_span.id,
            selected_span_text=selected_span.text,
            completion_choices=[
                selected_span.text,
                "more confusion among the residents",
                "a weaker plan for nearby roads",
                "fewer reasons to expand the system",
                "higher costs for the city budget",
            ],
            correct_choice=selected_span.text,
            contextual_meaning_ko="원문의 핵심 설명이 복원되어야 한다는 의미",
            supporting_evidence=selected_span.text,
            explanation="문맥상 원문의 핵심 설명이 복원되어야 합니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="MVP-01",
            BatchRowId=0,
            QuestionType=QUESTION_TYPES["fill_in_the_blank"].label_ko,
            student_paragraph=source.replace(selected_span.text, "_____", 1),
            question_stem=QUESTION_TYPES["fill_in_the_blank"].question_stem,
            choices=[
                selected_span.text,
                "more confusion among the residents",
                "a weaker plan for nearby roads",
                "fewer reasons to expand the system",
                "higher costs for the city budget",
            ],
            answer="①",
            explanation=(
                f"빈칸은 원문에서 '{selected_span.text}'에 해당하는 부분으로, "
                "이 자리에는 원문의 핵심 설명이 복원되어야 한다는 의미가 들어가야 합니다. "
                f"특히 '{selected_span.text}'라는 내용이 그 방향을 뒷받침하므로 "
                f"정답은 ① {selected_span.text}입니다."
            ),
        )
        self.assertEqual(
            validate_fill_in_the_blank_output(
                prepared_source=prepared,
                plan=plan,
                generated=generated,
                type_spec=QUESTION_TYPES["fill_in_the_blank"],
            ),
            [],
        )

    def test_vocab_validator_rejects_duplicate_targets(self) -> None:
        source = (
            "The city can reduce energy use without raising taxes. "
            "Officials plan to expand the lighting system next month. "
            "Residents say the brighter streets feel safer at night. "
            "Engineers are testing whether the new lamps last longer in winter. "
            "The mayor hopes to show that the project saves money over time. "
            "Teachers report that students now walk home with more confidence."
        )
        prepared = prepare_source(source)
        targets = sorted(vocab_target_inventory(prepared)[:5], key=lambda span: span.char_start)
        with self.assertRaises(ValueError):
            VocabPlan(
                target_span_ids=[targets[0].id, targets[0].id, targets[2].id, targets[3].id, targets[4].id],
                target_span_texts=[targets[0].text, targets[0].text, targets[2].text, targets[3].text, targets[4].text],
                corrupted_span_id=targets[2].id,
                corrupted_word="heavier",
                correction_basis_ko="문맥상 맞지 않는 단어입니다",
                supporting_evidence="Residents say the brighter streets feel safer at night.",
                explanation="문맥상 해당 단어의 쓰임이 맞지 않습니다.",
            )

    def test_vocab_validator_uses_target_ids_as_source_owned_contract(self) -> None:
        source = (
            "The city can reduce energy use without raising taxes. "
            "Officials plan to expand the lighting system next month. "
            "Residents say the brighter streets feel safer at night. "
            "Engineers are testing whether the new lamps last longer in winter. "
            "The mayor hopes to show that the project saves money over time. "
            "Teachers report that students now walk home with more confidence."
        )
        prepared = prepare_source(source)
        targets = sorted(vocab_target_inventory(prepared)[:5], key=lambda span: span.char_start)
        plan = VocabPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=["alpha", "bravo", "charlie", "delta", "echo"],
            corrupted_span_id=targets[2].id,
            corrupted_word="heavier",
            correction_basis_ko="문맥상 맞지 않는 단어입니다",
            supporting_evidence="Residents say the brighter streets feel safer at night.",
            explanation="문맥상 해당 단어의 쓰임이 맞지 않습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="MVP-02",
            BatchRowId=0,
            QuestionType=QUESTION_TYPES["vocab"].label_ko,
            student_paragraph=render_numbered_span_edits(
                source_text=source,
                selected_spans=targets,
                replacement_by_span_id={targets[2].id: "heavier"},
                markers=["①", "②", "③", "④", "⑤"],
            ),
            question_stem=QUESTION_TYPES["vocab"].question_stem,
            choices=["①", "②", "③", "④", "⑤"],
            answer="③",
            explanation="③의 heavier는 문맥과 맞지 않으므로 정답입니다.",
        )
        self.assertEqual(
            validate_vocab_output(
                prepared_source=prepared,
                plan=plan,
                generated=generated,
                type_spec=QUESTION_TYPES["vocab"],
            ),
            [],
        )

    def test_vocab_choice_output_validator_uses_deterministic_shuffle(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "Residents say the brighter crosswalks feel safer at night."
        )
        prepared = prepare_source(source)
        target = vocab_choice_inventory(prepared, QUESTION_TYPES["vocab"].subtype_key)[0]
        plan = ContextualVocabChoicePlan(
            selected_span_id=target.id,
            selected_span_text=target.text,
            choice_words=["strengthen", "weaken", "ignore", "delay", "worsen"],
            correct_choice="strengthen",
            contextual_meaning_ko="이 자리는 안전을 더 높이는 방향의 표현이 와야 합니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="문맥상 이 자리는 안전을 더 높이는 방향의 표현이 와야 합니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="MVP-02",
            BatchRowId=7,
            QuestionType=QUESTION_TYPES["vocab"].label_ko,
            student_paragraph=source.replace(target.text, "_____", 1),
            question_stem=QUESTION_TYPES["vocab"].question_stem,
            choices=["strengthen", "ignore", "weaken", "delay", "worsen"],
            answer="①",
            explanation="단서를 보면 이 자리에는 안전을 더 높이는 방향의 표현이 와야 하므로 정답은 ① strengthen입니다.",
        )
        self.assertEqual(
            validate_vocab_output(
                prepared_source=prepared,
                plan=plan,
                generated=generated,
                type_spec=QUESTION_TYPES["vocab"],
            ),
            [],
        )

    def test_underlined_vocab_output_validator_accepts_four_corrupted_subtype(self) -> None:
        source = (
            "Leaders cease wasteful spending during droughts. "
            "Engineers expand storage when demand rises. "
            "Families ignore rumors during emergencies. "
            "Stronger pumps reduce pressure loss across the valley. "
            "Volunteers protect the main channel from damage. "
            "Teachers discuss the results every Friday."
        )
        prepared = prepare_source(source)
        targets = sorted(
            vocab_hard_candidate_inventory(prepared)[:5],
            key=lambda span: span.char_start,
        )
        plan = UnderlinedVocabPlan(
            subtype="contextual_correct_among_4_corrupted",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_replacements=[
                {"span_id": targets[0].id, "replacement_text": "weaken"},
                {"span_id": targets[2].id, "replacement_text": "ignore"},
                {"span_id": targets[3].id, "replacement_text": "delay"},
                {"span_id": targets[4].id, "replacement_text": "worsen"},
            ],
            answer_span_id=targets[1].id,
            selection_basis_ko="이 자리만 원래 맥락의 의미를 자연스럽게 유지합니다",
            supporting_evidence="Stronger pumps reduce pressure loss across the valley.",
            explanation="단서를 보면 ②만 원래 의미를 유지하고 다른 밑줄 표현들은 의미를 비틉니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="MVP-02",
            BatchRowId=7,
            QuestionType=QUESTION_TYPES["vocab"].label_ko,
            student_paragraph=render_numbered_span_edits(
                source_text=source,
                selected_spans=targets,
                replacement_by_span_id=plan.corrupted_replacement_map(),
                markers=["①", "②", "③", "④", "⑤"],
            ),
            question_stem=QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"].question_stem,
            choices=["①", "②", "③", "④", "⑤"],
            answer="②",
            explanation="단서를 보면 ②만 원래 의미를 유지하고 다른 밑줄 표현들은 의미를 비틉니다.",
        )
        self.assertEqual(
            validate_vocab_output(
                prepared_source=prepared,
                plan=plan,
                generated=generated,
                type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
            ),
            [],
        )

    def test_underlined_vocab_plan_rejects_non_unique_remaining_item_for_three_corrupted_subtype(self) -> None:
        source = (
            "Leaders cease wasteful spending during droughts. "
            "Engineers expand storage when demand rises. "
            "Families ignore rumors during emergencies. "
            "Stronger pumps reduce pressure loss across the valley. "
            "Volunteers protect the main channel from damage. "
            "Teachers discuss the results every Friday."
        )
        prepared = prepare_source(source)
        targets = sorted(
            vocab_hard_candidate_inventory(prepared)[:5],
            key=lambda span: span.char_start,
        )
        ranked_by_strength = sorted(
            targets,
            key=lambda span: (vocab_choice_target_cue_count(span), span.priority_score),
        )
        answer_span = ranked_by_strength[0]
        untouched_distractor = ranked_by_strength[-1]
        corrupted_targets = [span for span in targets if span.id not in {answer_span.id, untouched_distractor.id}]
        plan = UnderlinedVocabPlan(
            subtype="contextual_correct_among_3_corrupted",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_replacements=[
                {"span_id": corrupted_targets[0].id, "replacement_text": "weaken"},
                {"span_id": corrupted_targets[1].id, "replacement_text": "delay"},
                {"span_id": corrupted_targets[2].id, "replacement_text": "worsen"},
            ],
            answer_span_id=answer_span.id,
            selection_basis_ko="이 자리만 가장 강하게 passage의 핵심 효과를 유지합니다",
            supporting_evidence="Stronger pumps reduce pressure loss across the valley.",
            explanation="문맥상 정답만 가장 강하게 원래 의미를 유지합니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_3_corrupted_5"],
        )
        self.assertTrue(
            any(
                "stronger contextual cue support" in error
                or "stronger priority profile" in error
                or "too central or answer-like" in error
                for error in errors
            )
        )

    def test_vocab_validator_rejects_near_synonym_corruption(self) -> None:
        source = (
            "Residents stick to the marked route during storms. "
            "Helpers assist newcomers at the station each morning. "
            "Teachers discuss the updated safety map every week. "
            "Engineers reduce delays with clearer signs near the bridge. "
            "Leaders expand the shelter behind the library this month. "
            "Families ignore rumors and wait for official updates."
        )
        prepared = prepare_source(source)
        inventory = vocab_target_inventory(prepared)
        stick_span = next(span for span in inventory if span.text.lower() == "stick")
        targets = [stick_span] + [span for span in inventory if span.id != stick_span.id][:4]
        plan = VocabPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_span_id=stick_span.id,
            corrupted_word="adhere",
            correction_basis_ko="원문의 의미를 충분히 바꾸지 못합니다.",
            supporting_evidence="Residents stick to the marked route during storms.",
            explanation="문맥상 원래 의미를 뒤집지 못하는 치환입니다.",
        )

        errors = validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["vocab"])

        self.assertTrue(any("near-synonym" in error for error in errors))

    def test_vocab_validator_allows_clear_contextual_distortion(self) -> None:
        source = (
            "Leaders cease wasteful spending during droughts. "
            "Engineers expand storage when demand rises. "
            "Families ignore rumors during emergencies. "
            "Stronger pumps reduce pressure loss across the valley. "
            "Volunteers protect the main channel from damage. "
            "Teachers discuss the results every Friday."
        )
        prepared = prepare_source(source)
        inventory = vocab_target_inventory(prepared)
        cease_span = next(span for span in inventory if span.text.lower() == "cease")
        targets = [cease_span] + [span for span in inventory if span.id != cease_span.id][:4]
        plan = VocabPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_span_id=cease_span.id,
            corrupted_word="continue",
            correction_basis_ko="원문의 방향과 반대 의미라서 문맥이 어긋납니다.",
            supporting_evidence="Leaders cease wasteful spending during droughts.",
            explanation="문맥상 소비를 멈춘다는 뜻이어야 합니다.",
        )

        self.assertEqual(
            validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["vocab"]),
            [],
        )

    def test_vocab_choice_validator_rejects_near_synonym_distractor(self) -> None:
        source = "Residents show strong support during the winter drive. Teachers discuss the safety map every week."
        support_start = source.index("support")
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="Residents show strong support during the winter drive.", index=0),
                SourceUnit(id="S1", text="Teachers discuss the safety map every week.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text="support",
                    normalized_text="support",
                    char_start=support_start,
                    char_end=support_start + len("support"),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="Residents show strong ",
                    context_after=" during the winter drive.",
                    heuristic_tags=["single_word", "abstract_term", "vocab_candidate"],
                    priority_score=7,
                )
            ],
        )
        plan = ContextualVocabChoicePlan(
            selected_span_id="P0",
            selected_span_text="support",
            choice_words=["support", "assist", "delay", "ignore", "weaken"],
            correct_choice="support",
            contextual_meaning_ko="이 자리는 실제로 뒷받침하는 의미를 가리키는 표현이 와야 한다는 의미",
            supporting_evidence="Residents show strong support during the winter drive.",
            explanation="문맥상 실제로 뒷받침하는 의미를 가리키는 표현이 와야 합니다.",
        )
        errors = validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["vocab"])
        self.assertTrue(any("near-synonyms" in error for error in errors))

    def test_vocab_choice_validator_rejects_slot_width_mismatch(self) -> None:
        source = "The report carries moral force in this debate. Repeated exceptions weaken the rule for everyone."
        span_text = "moral force"
        span_start = source.index(span_text)
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="The report carries moral force in this debate.", index=0),
                SourceUnit(id="S1", text="Repeated exceptions weaken the rule for everyone.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text=span_text,
                    normalized_text=span_text,
                    char_start=span_start,
                    char_end=span_start + len(span_text),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="The report carries ",
                    context_after=" in this debate.",
                    heuristic_tags=["abstract_term", "phrase_frame"],
                    priority_score=7,
                )
            ],
        )
        plan = ContextualVocabChoicePlan(
            selected_span_id="P0",
            selected_span_text=span_text,
            choice_words=["moral force", "deeply misunderstood factual evidence", "delay", "ignore", "weaken"],
            correct_choice="moral force",
            contextual_meaning_ko="이 자리는 주장에 실리는 규범적 무게를 가리키는 표현이 와야 한다는 의미",
            supporting_evidence="The report carries moral force in this debate.",
            explanation="문맥상 주장에 실리는 규범적 무게를 가리키는 표현이 와야 합니다.",
        )
        errors = validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["vocab"])
        self.assertTrue(any("slot width" in error for error in errors))

    def test_best_paraphrase_validator_rejects_identical_correct_choice_and_source_wording(self) -> None:
        source = "Residents show strong support during the winter drive. Teachers discuss the safety map every week."
        support_start = source.index("support")
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="Residents show strong support during the winter drive.", index=0),
                SourceUnit(id="S1", text="Teachers discuss the safety map every week.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text="support",
                    normalized_text="support",
                    char_start=support_start,
                    char_end=support_start + len("support"),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="Residents show strong ",
                    context_after=" during the winter drive.",
                    heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
                    priority_score=7,
                )
            ],
        )
        plan = ContextualVocabChoicePlan(
            subtype="contextual_best_paraphrase_choice",
            selected_span_id="P0",
            selected_span_text="support",
            choice_words=["support", "backing", "delay", "ignore", "weaken"],
            correct_choice="support",
            contextual_meaning_ko="이 자리는 뒷받침의 의미를 다른 표현으로 바꿔 말해야 합니다",
            supporting_evidence="Residents show strong support during the winter drive.",
            explanation="문맥상 같은 뜻을 다른 표현으로 바꿔 말해야 합니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_best_paraphrase_choice_5"],
        )
        self.assertTrue(any("non-identical correct_choice" in error for error in errors))
        self.assertTrue(any("must not include the unchanged source wording" in error for error in errors))

    def test_best_paraphrase_target_quality_rejects_grammarish_anchors(self) -> None:
        for token in ("what", "which", "like", "more"):
            span = SpanUnit(
                id="P0",
                text=token,
                normalized_text=token,
                char_start=0,
                char_end=len(token),
                sentence_unit_id="S0",
                sentence_index=0,
                context_before="People felt ",
                context_after=" secure after the change.",
                heuristic_tags=["single_word", "contextual_cue", "vocab_candidate"],
                priority_score=7,
            )
            error = vocab_choice_target_quality_error(
                span,
                subtype_key="contextual_vocab_best_paraphrase_choice_5",
            ) or ""
            self.assertIn("grammar-heavy anchor", error)

    def test_phrase_choice_validator_rejects_non_phrase_options_and_slot_drift(self) -> None:
        source = "The report carries moral force in this debate. Repeated exceptions weaken the rule for everyone."
        span_text = "moral force"
        span_start = source.index(span_text)
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="The report carries moral force in this debate.", index=0),
                SourceUnit(id="S1", text="Repeated exceptions weaken the rule for everyone.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text=span_text,
                    normalized_text=span_text,
                    char_start=span_start,
                    char_end=span_start + len(span_text),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="The report carries ",
                    context_after=" in this debate.",
                    heuristic_tags=["abstract_term", "phrase_frame"],
                    priority_score=7,
                )
            ],
        )
        plan = ContextualVocabChoicePlan(
            subtype="contextual_phrase_choice",
            selected_span_id="P0",
            selected_span_text=span_text,
            choice_words=["moral force", "ethical weight now", "delay", "ignore", "weaken the rule"],
            correct_choice="moral force",
            contextual_meaning_ko="이 자리는 주장에 실리는 규범적 무게를 가리키는 어구가 와야 합니다",
            supporting_evidence="The report carries moral force in this debate.",
            explanation="문맥상 주장에 실리는 규범적 무게를 가리키는 어구가 와야 합니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_phrase_choice_5"],
        )
        self.assertTrue(any("phrase-level options" in error for error in errors))
        self.assertTrue(any("preserve phrase-slot width exactly" in error for error in errors))

    def test_phrase_choice_target_quality_rejects_weak_fragment(self) -> None:
        span = SpanUnit(
            id="P0",
            text="some change",
            normalized_text="some change",
            char_start=0,
            char_end=len("some change"),
            sentence_unit_id="S0",
            sentence_index=0,
            context_before="The committee described ",
            context_after=" as a temporary response.",
            heuristic_tags=["embedded_phrase", "contextual_cue"],
            priority_score=7,
        )
        error = vocab_choice_target_quality_error(
            span,
            subtype_key="contextual_vocab_phrase_choice_5",
        ) or ""
        self.assertIn("weak phrase fragment", error)

    def test_phrase_choice_compatibility_rejects_only_weak_embedded_phrase(self) -> None:
        source = "The committee described some change as a temporary response. Observers remained cautious."
        phrase_text = "some change"
        phrase_start = source.index(phrase_text)
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="The committee described some change as a temporary response.", index=0),
                SourceUnit(id="S1", text="Observers remained cautious.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text=phrase_text,
                    normalized_text=phrase_text,
                    char_start=phrase_start,
                    char_end=phrase_start + len(phrase_text),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="The committee described ",
                    context_after=" as a temporary response.",
                    heuristic_tags=["embedded_phrase", "contextual_cue"],
                    priority_score=7,
                )
            ],
        )
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_phrase_choice_5"],
        )
        self.assertTrue(any("phrase-frame or collocational vocab target" in error for error in errors))

    def test_vocab_choice_validator_allows_contextual_replacement_answer(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "Residents say the brighter crosswalks feel safer at night."
        )
        improve_start = source.index("brighter")
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(
                    id="S0",
                    text="City planners recently tested brighter LED lights on several downtown blocks.",
                    index=0,
                ),
                SourceUnit(
                    id="S1",
                    text="Residents say the brighter crosswalks feel safer at night.",
                    index=1,
                ),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text="brighter",
                    normalized_text="brighter",
                    char_start=improve_start,
                    char_end=improve_start + len("brighter"),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="City planners recently tested ",
                    context_after=" LED lights on several downtown blocks.",
                    heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
                    priority_score=7,
                )
            ],
        )
        plan = ContextualVocabChoicePlan(
            selected_span_id="P0",
            selected_span_text="brighter",
            choice_words=["stronger", "weaker", "dimmer", "rarer", "heavier"],
            correct_choice="stronger",
            contextual_meaning_ko="이 자리는 가시성과 안전감을 더 높이는 방향의 표현이 와야 합니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="문맥상 이 자리는 가시성과 안전감을 더 높이는 방향의 표현이 와야 합니다.",
        )
        self.assertEqual(
            validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["vocab"]),
            [],
        )

    def test_phrase_choice_validator_accepts_multiword_phrase_options(self) -> None:
        source = "The report carries moral force in this debate. Repeated exceptions weaken the rule for everyone."
        span_text = "moral force"
        span_start = source.index(span_text)
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="The report carries moral force in this debate.", index=0),
                SourceUnit(id="S1", text="Repeated exceptions weaken the rule for everyone.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text=span_text,
                    normalized_text=span_text,
                    char_start=span_start,
                    char_end=span_start + len(span_text),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="The report carries ",
                    context_after=" in this debate.",
                    heuristic_tags=["abstract_term", "phrase_frame"],
                    priority_score=7,
                )
            ],
        )
        plan = ContextualVocabChoicePlan(
            subtype="contextual_phrase_choice",
            selected_span_id="P0",
            selected_span_text=span_text,
            choice_words=[
                "moral force",
                "ethical weight",
                "factual burden",
                "narrow logic",
                "surface detail",
            ],
            correct_choice="moral force",
            contextual_meaning_ko="이 자리는 주장에 실리는 규범적 무게를 가리키는 어구가 와야 합니다",
            supporting_evidence="The report carries moral force in this debate.",
            explanation="문맥상 주장에 실리는 규범적 무게를 가리키는 어구가 와야 합니다.",
        )
        self.assertEqual(
            validate_plan_against_prepared_source(
                prepared,
                plan,
                QUESTION_SUBTYPE_SPECS["contextual_vocab_phrase_choice_5"],
            ),
            [],
        )

    def test_vocab_choice_validator_rejects_original_wording_as_second_defensible_option(self) -> None:
        source = "Residents show strong support during the winter drive. Teachers discuss the safety map every week."
        support_start = source.index("support")
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="Residents show strong support during the winter drive.", index=0),
                SourceUnit(id="S1", text="Teachers discuss the safety map every week.", index=1),
            ],
            gap_units=[
                GapUnit(id="G0", index=0, before_unit_id=None, after_unit_id="S0"),
                GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
                GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id=None),
            ],
            span_units=[
                SpanUnit(
                    id="P0",
                    text="support",
                    normalized_text="support",
                    char_start=support_start,
                    char_end=support_start + len("support"),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="Residents show strong ",
                    context_after=" during the winter drive.",
                    heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
                    priority_score=7,
                )
            ],
        )
        plan = ContextualVocabChoicePlan(
            selected_span_id="P0",
            selected_span_text="support",
            choice_words=["support", "backing", "delay", "ignore", "weaken"],
            correct_choice="backing",
            contextual_meaning_ko="이 자리는 실제로 뒷받침하는 의미를 가리키는 표현이 와야 합니다",
            supporting_evidence="Residents show strong support during the winter drive.",
            explanation="문맥상 실제로 뒷받침하는 의미를 가리키는 표현이 와야 합니다.",
        )
        errors = validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["vocab"])
        self.assertTrue(any("second defensible option" in error for error in errors))

    def test_underlined_vocab_polarity_scope_validator_accepts_direction_drift_and_rejects_collocation_only(self) -> None:
        source = (
            "Leaders cease wasteful spending during droughts. "
            "Engineers expand storage when demand rises. "
            "Families ignore rumors during emergencies. "
            "Stronger pumps reduce pressure loss across the valley. "
            "Volunteers protect the main channel from damage. "
            "Teachers discuss the results every Friday."
        )
        prepared = prepare_source(source)
        inventory = vocab_hard_candidate_inventory(prepared)
        polarity_target = next(span for span in inventory if span.text == "cease")
        targets = sorted(
            [polarity_target] + [span for span in inventory if span.id != polarity_target.id][:4],
            key=lambda span: span.char_start,
        )
        valid_plan = UnderlinedVocabPlan(
            subtype="contextual_error_1_among_5_polarity_scope",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_replacements=[
                {"span_id": targets[0].id, "replacement_text": "continue"},
            ],
            answer_span_id=targets[0].id,
            selection_basis_ko="이 자리는 멈춤이나 축소처럼 방향과 범위가 분명히 제한되어야 합니다",
            supporting_evidence="Leaders cease wasteful spending during droughts.",
            explanation="문맥상 방향과 범위를 어긋나게 만든 표현을 골라야 합니다.",
        )
        invalid_plan = UnderlinedVocabPlan(
            subtype=valid_plan.subtype,
            target_span_ids=valid_plan.target_span_ids,
            target_span_texts=valid_plan.target_span_texts,
            corrupted_replacements=[{"span_id": targets[0].id, "replacement_text": "fragile"}],
            answer_span_id=valid_plan.answer_span_id,
            selection_basis_ko=valid_plan.selection_basis_ko,
            supporting_evidence=valid_plan.supporting_evidence,
            explanation=valid_plan.explanation,
        )
        self.assertEqual(
            validate_plan_against_prepared_source(
                prepared,
                valid_plan,
                QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_polarity_scope_5"],
            ),
            [],
        )
        invalid_errors = validate_plan_against_prepared_source(
            prepared,
            invalid_plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_polarity_scope_5"],
        )
        self.assertTrue(any("direction, degree, or scope" in error for error in invalid_errors))

    def test_polarity_scope_compatibility_rejects_generic_bundle_without_anchor(self) -> None:
        source = "Teachers support. Families discuss. Leaders protect. Workers improve. Students ignore."
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id=f"S{index}", text=text, index=index)
                for index, text in enumerate(
                    [
                        "Teachers support.",
                        "Families discuss.",
                        "Leaders protect.",
                        "Workers improve.",
                        "Students ignore.",
                    ]
                )
            ],
            gap_units=[
                GapUnit(id=f"G{index}", index=index, before_unit_id=None if index == 0 else f"S{index - 1}", after_unit_id=f"S{index}" if index < 5 else None)
                for index in range(6)
            ],
            span_units=[
                SpanUnit(
                    id=f"P{index}",
                    text=text,
                    normalized_text=text,
                    char_start=index * 10,
                    char_end=index * 10 + len(text),
                    sentence_unit_id=f"S{index}",
                    sentence_index=index,
                    context_before="Context before ",
                    context_after=" context after.",
                    heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
                    priority_score=7,
                )
                for index, text in enumerate(["support", "discuss", "protect", "improve", "ignore"])
            ],
        )
        self.assertGreaterEqual(len(vocab_hard_candidate_inventory(prepared)), 5)
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_polarity_scope_5"],
        )
        self.assertTrue(any("none is polarity/scope-eligible" in error for error in errors))

    def test_polarity_scope_plan_against_design_rejects_noneligible_corruption(self) -> None:
        source = "Leaders cease. Families support. Workers improve. Students discuss. Teachers ignore."
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id=f"S{index}", text=text, index=index)
                for index, text in enumerate(
                    [
                        "Leaders cease.",
                        "Families support.",
                        "Workers improve.",
                        "Students discuss.",
                        "Teachers ignore.",
                    ]
                )
            ],
            gap_units=[
                GapUnit(id=f"G{index}", index=index, before_unit_id=None if index == 0 else f"S{index - 1}", after_unit_id=f"S{index}" if index < 5 else None)
                for index in range(6)
            ],
            span_units=[
                SpanUnit(
                    id=f"P{index}",
                    text=text,
                    normalized_text=text,
                    char_start=index * 10,
                    char_end=index * 10 + len(text),
                    sentence_unit_id=f"S{index}",
                    sentence_index=index,
                    context_before="Context before ",
                    context_after=" context after.",
                    heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
                    priority_score=7,
                )
                for index, text in enumerate(["cease", "support", "improve", "discuss", "ignore"])
            ],
        )
        inventory = vocab_hard_candidate_inventory(prepared)[:5]
        eligible_span = next(span for span in inventory if span.text == "cease")
        noneligible_span = next(span for span in inventory if span.id != eligible_span.id)
        design = UnderlinedVocabDesign(
            family_key="vocab",
            subtype_key="contextual_vocab_error_1_among_5_polarity_scope_5",
            subtype="contextual_error_1_among_5_polarity_scope",
            target_span_ids=[span.id for span in inventory],
            target_span_texts=[span.text for span in inventory],
            corruptible_span_ids=[eligible_span.id],
            prompt_payload={},
        )
        plan = UnderlinedVocabPlan(
            subtype="contextual_error_1_among_5_polarity_scope",
            target_span_ids=design.target_span_ids,
            target_span_texts=design.target_span_texts,
            corrupted_replacements=[{"span_id": noneligible_span.id, "replacement_text": "never"}],
            answer_span_id=noneligible_span.id,
            selection_basis_ko="이 자리는 방향과 범위가 유지되어야 합니다",
            supporting_evidence="Leaders cease wasteful spending during droughts.",
            explanation="문맥상 방향과 범위를 어긋나게 만든 표현입니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_polarity_scope_5"],
            design=design,
        )
        self.assertTrue(any("locked design corruptible subset" in error for error in errors))

    def test_underlined_vocab_collocation_validator_accepts_collocation_mismatch_and_rejects_pure_opposite(self) -> None:
        source = (
            "Leaders cease wasteful spending during droughts. "
            "Engineers expand storage when demand rises. "
            "Families ignore rumors during emergencies. "
            "Stronger pumps reduce pressure loss across the valley. "
            "Volunteers protect the main channel from damage. "
            "Teachers discuss the results every Friday."
        )
        prepared = prepare_source(source)
        inventory = vocab_hard_candidate_inventory(prepared)
        collocation_target = next(span for span in inventory if span.text == "ignore")
        targets = sorted(
            [collocation_target] + [span for span in inventory if span.id != collocation_target.id][:4],
            key=lambda span: span.char_start,
        )
        valid_plan = UnderlinedVocabPlan(
            subtype="contextual_error_1_among_5_collocation",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_replacements=[
                {"span_id": collocation_target.id, "replacement_text": "collect"},
            ],
            answer_span_id=collocation_target.id,
            selection_basis_ko="이 자리는 문맥상 자연스러운 어휘 결합과 선택 제약이 유지되어야 합니다",
            supporting_evidence="Families ignore rumors during emergencies.",
            explanation="문맥상 자연스러운 어휘 결합을 깨뜨린 표현을 골라야 합니다.",
        )
        invalid_plan = UnderlinedVocabPlan(
            subtype=valid_plan.subtype,
            target_span_ids=valid_plan.target_span_ids,
            target_span_texts=valid_plan.target_span_texts,
            corrupted_replacements=[{"span_id": collocation_target.id, "replacement_text": "notice"}],
            answer_span_id=valid_plan.answer_span_id,
            selection_basis_ko=valid_plan.selection_basis_ko,
            supporting_evidence=valid_plan.supporting_evidence,
            explanation=valid_plan.explanation,
        )
        self.assertEqual(
            validate_plan_against_prepared_source(
                prepared,
                valid_plan,
                QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_collocation_5"],
            ),
            [],
        )
        invalid_errors = validate_plan_against_prepared_source(
            prepared,
            invalid_plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_collocation_5"],
        )
        self.assertTrue(any("local phrase-frame or selectional mismatch" in error for error in invalid_errors))

    def test_collocation_compatibility_rejects_broad_semantic_substitution_frame(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        prepared = prepare_source(source)
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_collocation_5"],
        )
        self.assertTrue(any("collocation-eligible corruption anchor" in error for error in errors))

    def test_collocation_compatibility_rejects_generic_bundle_without_collocation_anchor(self) -> None:
        source = "Leaders reduce. Families support. Workers improve. Students discuss. Teachers ignore."
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id=f"S{index}", text=text, index=index)
                for index, text in enumerate(
                    [
                        "Leaders reduce.",
                        "Families support.",
                        "Workers improve.",
                        "Students discuss.",
                        "Teachers ignore.",
                    ]
                )
            ],
            gap_units=[
                GapUnit(id=f"G{index}", index=index, before_unit_id=None if index == 0 else f"S{index - 1}", after_unit_id=f"S{index}" if index < 5 else None)
                for index in range(6)
            ],
            span_units=[
                SpanUnit(
                    id=f"P{index}",
                    text=text,
                    normalized_text=text,
                    char_start=index * 10,
                    char_end=index * 10 + len(text),
                    sentence_unit_id=f"S{index}",
                    sentence_index=index,
                    context_before="to ",
                    context_after=" the",
                    heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
                    priority_score=7,
                )
                for index, text in enumerate(["reduce", "support", "improve", "discuss", "ignore"])
            ],
        )
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_collocation_5"],
        )
        self.assertTrue(any("none is collocation-eligible" in error for error in errors))

    def test_collocation_plan_against_design_rejects_noneligible_corruption(self) -> None:
        source = (
            "Families ignore rumors during emergencies. "
            "Teachers support the new shelter each winter. "
            "Workers improve service around town every week. "
            "Students discuss the updated route after class. "
            "Volunteers collect supplies near the station. "
            "Leaders reduce delays before sunrise."
        )
        prepared = prepare_source(source)
        targets = vocab_hard_candidate_inventory(prepared)[:5]
        eligible_span = next(span for span in targets if span.text == "ignore")
        noneligible_span = next(span for span in targets if span.id != eligible_span.id)
        design = UnderlinedVocabDesign(
            family_key="vocab",
            subtype_key="contextual_vocab_error_1_among_5_collocation_5",
            subtype="contextual_error_1_among_5_collocation",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corruptible_span_ids=[eligible_span.id],
            prompt_payload={},
        )
        plan = UnderlinedVocabPlan(
            subtype="contextual_error_1_among_5_collocation",
            target_span_ids=design.target_span_ids,
            target_span_texts=design.target_span_texts,
            corrupted_replacements=[{"span_id": noneligible_span.id, "replacement_text": "collect"}],
            answer_span_id=noneligible_span.id,
            selection_basis_ko="이 자리는 자연스러운 어휘 결합이 유지되어야 합니다",
            supporting_evidence="Families ignore rumors during emergencies.",
            explanation="문맥상 자연스러운 어휘 결합을 깨뜨린 표현입니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_collocation_5"],
            design=design,
        )
        self.assertTrue(any("locked design corruptible subset" in error for error in errors))

    def test_correct_among_4_compatibility_rejects_bundle_without_corruption_ready_distractors(self) -> None:
        sentences = [
            "Community happiness has lasting social value.",
            "Relative wealth has visible symbolic force.",
            "Widening inequality has deep political cost.",
            "Persistent discontent has broad civic impact.",
            "Public dignity has fragile moral weight.",
        ]
        prepared = _manual_prepared_source_with_vocab_spans(
            sentences,
            [
                (0, "happiness", ["single_word", "vocab_candidate", "abstract_term", "contextual_cue"], 8),
                (1, "wealth", ["single_word", "vocab_candidate", "abstract_term", "contextual_cue"], 8),
                (2, "inequality", ["single_word", "vocab_candidate", "abstract_term", "contextual_cue"], 9),
                (3, "discontent", ["single_word", "vocab_candidate", "abstract_term", "contextual_cue"], 8),
                (4, "dignity", ["single_word", "vocab_candidate", "abstract_term", "contextual_cue"], 8),
            ],
        )
        errors = validate_question_type_compatibility(
            prepared.source_text,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
        )
        self.assertTrue(any("corruption-friendly distractors" in error for error in errors))

    def test_correct_among_4_plan_rejects_obvious_low_value_swaps(self) -> None:
        sentences = [
            "Leaders cease wasteful spending during droughts.",
            "Engineers expand storage when demand rises.",
            "Families ignore rumors during emergencies.",
            "Stronger pumps reduce pressure loss across the valley.",
            "Volunteers protect the main channel from damage.",
        ]
        prepared = _manual_prepared_source_with_vocab_spans(
            sentences,
            [
                (0, "cease", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (1, "expand", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (2, "ignore", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (3, "reduce", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (4, "protect", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 9),
            ],
        )
        bundle = vocab_hard_bundle(prepared, "contextual_vocab_correct_among_4_corrupted_5")
        self.assertIsNotNone(bundle)
        assert bundle is not None
        ordered_targets = list(bundle.selected_spans)
        answer_span = next(span for span in ordered_targets if span.id == bundle.answer_span_id)
        plan = UnderlinedVocabPlan(
            subtype="contextual_correct_among_4_corrupted",
            target_span_ids=[span.id for span in ordered_targets],
            target_span_texts=[span.text for span in ordered_targets],
            corrupted_replacements=[
                {"span_id": span.id, "replacement_text": replacement}
                for span, replacement in zip(
                    [span for span in ordered_targets if span.id != answer_span.id],
                    ["teacher", "road", "report", "station"],
                    strict=False,
                )
            ],
            answer_span_id=answer_span.id,
            selection_basis_ko="정답만 문맥을 유지하고 나머지는 모두 틀려야 합니다.",
            supporting_evidence="Volunteers protect the main channel from damage.",
            explanation="문맥상 나머지 표현들은 너무 노골적이라 부적절합니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
        )
        self.assertTrue(any("low-value factual swaps" in error for error in errors))

    def test_correct_among_4_plan_allows_local_contextual_distortions(self) -> None:
        sentences = [
            "Leaders cease wasteful spending during droughts.",
            "Engineers expand storage when demand rises.",
            "Families ignore rumors during emergencies.",
            "Stronger pumps reduce pressure loss across the valley.",
            "Volunteers protect the main channel from damage.",
        ]
        prepared = _manual_prepared_source_with_vocab_spans(
            sentences,
            [
                (0, "cease", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (1, "expand", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (2, "ignore", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (3, "reduce", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 8),
                (4, "protect", ["single_word", "vocab_candidate", "contextual_cue", "antonym_invertible", "claim_bearing"], 9),
            ],
        )
        bundle = vocab_hard_bundle(prepared, "contextual_vocab_correct_among_4_corrupted_5")
        self.assertIsNotNone(bundle)
        assert bundle is not None
        ordered_targets = list(bundle.selected_spans)
        answer_span = next(span for span in ordered_targets if span.id == bundle.answer_span_id)
        plan = UnderlinedVocabPlan(
            subtype="contextual_correct_among_4_corrupted",
            target_span_ids=[span.id for span in ordered_targets],
            target_span_texts=[span.text for span in ordered_targets],
            corrupted_replacements=[
                {"span_id": span.id, "replacement_text": replacement}
                for span, replacement in zip(
                    [span for span in ordered_targets if span.id != answer_span.id],
                    ["continue", "shrink", "notice", "increase"],
                    strict=False,
                )
            ],
            answer_span_id=answer_span.id,
            selection_basis_ko="정답만 원래 의미를 유지합니다.",
            supporting_evidence="Volunteers protect the main channel from damage.",
            explanation="문맥상 정답만 원래 의미를 유지하고 나머지는 문맥을 어긋나게 만듭니다.",
        )
        self.assertEqual(
            validate_plan_against_prepared_source(
                prepared,
                plan,
                QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
            ),
            [],
        )

    def test_correct_among_4_plan_against_design_rejects_changed_survivor(self) -> None:
        source = (
            "Residents praise the durable signal each winter. "
            "Planners discuss the updated route after dinner. "
            "Workers reduce delays around town every week. "
            "Students support the new shelter during storms. "
            "Volunteers collect supplies near the station. "
            "Teachers ignore gossip before exams."
        )
        prepared = prepare_source(source)
        targets = vocab_hard_candidate_inventory(prepared)[:5]
        design_answer = max(targets, key=vocab_choice_target_cue_count)
        plan_answer = next(span for span in targets if span.id != design_answer.id)
        design = UnderlinedVocabDesign(
            family_key="vocab",
            subtype_key="contextual_vocab_correct_among_4_corrupted_5",
            subtype="contextual_correct_among_4_corrupted",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            answer_span_id=design_answer.id,
            prompt_payload={},
        )
        plan = UnderlinedVocabPlan(
            subtype="contextual_correct_among_4_corrupted",
            target_span_ids=design.target_span_ids,
            target_span_texts=design.target_span_texts,
            corrupted_replacements=[
                {"span_id": span.id, "replacement_text": replacement}
                for span, replacement in zip(
                    [span for span in targets if span.id != plan_answer.id],
                    ["weaken", "ignore", "delay", "worsen"],
                    strict=False,
                )
            ],
            answer_span_id=plan_answer.id,
            selection_basis_ko="정답 표현만 원래 의미를 유지합니다",
            supporting_evidence="Residents praise the durable signal each winter.",
            explanation="문맥상 하나만 원래 의미를 유지합니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
            design=design,
        )
        self.assertTrue(any("locked design survivor" in error or "corrupt every non-answer item" in error for error in errors))

    def test_error_1_plan_against_design_rejects_changed_corrupted_target(self) -> None:
        source = (
            "Residents praise the durable signal each winter. "
            "Planners discuss the updated route after dinner. "
            "Workers reduce delays around town every week. "
            "Students support the new shelter during storms. "
            "Volunteers collect supplies near the station. "
            "Teachers ignore gossip before exams."
        )
        prepared = prepare_source(source)
        targets = vocab_hard_candidate_inventory(prepared)[:5]
        design_answer = max(targets, key=vocab_choice_target_cue_count)
        plan_answer = next(span for span in targets if span.id != design_answer.id)
        design = UnderlinedVocabDesign(
            family_key="vocab",
            subtype_key="contextual_vocab_error_1_among_5_5",
            subtype="contextual_error_1_among_5",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            answer_span_id=design_answer.id,
            prompt_payload={},
        )
        plan = UnderlinedVocabPlan(
            subtype="contextual_error_1_among_5",
            target_span_ids=design.target_span_ids,
            target_span_texts=design.target_span_texts,
            corrupted_replacements=[{"span_id": plan_answer.id, "replacement_text": "ignore"}],
            answer_span_id=plan_answer.id,
            selection_basis_ko="원래 표현만 글의 핵심 의미를 유지합니다",
            supporting_evidence="Residents praise the durable signal each winter.",
            explanation="문맥상 하나의 표현만 의미를 어긋나게 만듭니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_5"],
            design=design,
        )
        self.assertTrue(any("locked design corrupted target" in error or "corrupt only the locked design target" in error for error in errors))

    def test_correct_among_3_compatibility_rejects_flat_strength_bundle(self) -> None:
        source = (
            "The city faces moral pressure during the debate. "
            "The committee carries social pressure into the review. "
            "The report adds ethical pressure to the discussion. "
            "The ruling creates public pressure around the case. "
            "The appeal brings civic pressure into focus. "
            "Observers note the repeated pattern."
        )
        pressure_start = source.index("moral pressure")
        phrases = [
            ("P0", "moral pressure", pressure_start),
            ("P1", "social pressure", source.index("social pressure")),
            ("P2", "ethical pressure", source.index("ethical pressure")),
            ("P3", "public pressure", source.index("public pressure")),
            ("P4", "civic pressure", source.index("civic pressure")),
        ]
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="The city faces moral pressure during the debate.", index=0),
                SourceUnit(id="S1", text="The committee carries social pressure into the review.", index=1),
                SourceUnit(id="S2", text="The report adds ethical pressure to the discussion.", index=2),
                SourceUnit(id="S3", text="The ruling creates public pressure around the case.", index=3),
                SourceUnit(id="S4", text="The appeal brings civic pressure into focus.", index=4),
                SourceUnit(id="S5", text="Observers note the repeated pattern.", index=5),
            ],
            gap_units=[
                GapUnit(id=f"G{index}", index=index, before_unit_id=None if index == 0 else f"S{index - 1}", after_unit_id=f"S{index}" if index < 6 else None)
                for index in range(7)
            ],
            span_units=[
                SpanUnit(
                    id=span_id,
                    text=text,
                    normalized_text=text,
                    char_start=start,
                    char_end=start + len(text),
                    sentence_unit_id=f"S{index}",
                    sentence_index=index,
                    context_before="The ",
                    context_after=" during the passage.",
                    heuristic_tags=["abstract_term", "phrase_frame", "contextual_cue"],
                    priority_score=7,
                )
                for index, (span_id, text, start) in enumerate(phrases)
            ],
        )
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_3_corrupted_5"],
        )
        self.assertTrue(any("clear unique-survivor vocab bundle" in error for error in errors))

    def test_correct_among_3_compatibility_rejects_answer_like_extra_survivor(self) -> None:
        source = (
            "People's happiness depends on relative wealth. "
            "People are rarely satisfied once their neighbors pull ahead. "
            "But the resulting inequality brought only discontent. "
            "Communities discuss the pattern each year. "
            "Officials protect local services during downturns."
        )
        prepared = prepare_source(source)
        errors = validate_question_type_compatibility(
            source,
            prepared,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_3_corrupted_5"],
        )
        self.assertTrue(any("clear unique-survivor vocab bundle" in error for error in errors))

    def test_correct_among_3_compatibility_accepts_clear_secondary_untouched_distractor(self) -> None:
        source = (
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods. "
            "Residents say the brighter crosswalks feel safer at night."
        )
        prepared = prepare_source(source)
        self.assertEqual(
            validate_question_type_compatibility(
                source,
                prepared,
                QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_3_corrupted_5"],
            ),
            [],
        )
        bundle = vocab_hard_bundle(prepared, "contextual_vocab_correct_among_3_corrupted_5")
        self.assertIsNotNone(bundle)

    def test_correct_among_3_plan_against_design_rejects_changed_survivor_pair(self) -> None:
        source = (
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods. "
            "Residents say the brighter crosswalks feel safer at night."
        )
        prepared = prepare_source(source)
        bundle = vocab_hard_bundle(prepared, "contextual_vocab_correct_among_3_corrupted_5")
        self.assertIsNotNone(bundle)
        assert bundle is not None
        targets = list(bundle.selected_spans)
        answer_span = next(span for span in targets if span.id == bundle.answer_span_id)
        untouched_span = next(span for span in targets if span.id == bundle.untouched_distractor_span_id)
        design = UnderlinedVocabDesign(
            family_key="vocab",
            subtype_key="contextual_vocab_correct_among_3_corrupted_5",
            subtype="contextual_correct_among_3_corrupted",
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            answer_span_id=answer_span.id,
            untouched_distractor_span_id=untouched_span.id,
            prompt_payload={},
        )
        alternate_untouched = next(
            span for span in targets if span.id not in {answer_span.id, untouched_span.id}
        )
        plan = UnderlinedVocabPlan(
            subtype="contextual_correct_among_3_corrupted",
            target_span_ids=design.target_span_ids,
            target_span_texts=design.target_span_texts,
            corrupted_replacements=[
                {"span_id": span.id, "replacement_text": replacement}
                for span, replacement in zip(
                    [span for span in targets if span.id not in {answer_span.id, alternate_untouched.id}],
                    ["weaken", "delay", "worsen"],
                    strict=False,
                )
            ],
            answer_span_id=answer_span.id,
            selection_basis_ko="정답만 가장 강하게 원래 의미를 유지합니다",
            supporting_evidence="Residents praise the durable signal each winter.",
            explanation="문맥상 정답만 가장 강하게 원래 의미를 유지합니다.",
        )
        errors = validate_plan_against_prepared_source(
            prepared,
            plan,
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_3_corrupted_5"],
            design=design,
        )
        self.assertTrue(any("locked untouched survivor pair" in error for error in errors))

    def test_grammar_validator_accepts_valid_output(self) -> None:
        source = (
            "The city can reduce energy use without raising taxes. "
            "Officials plan to expand the lighting system next month. "
            "Residents say the brighter streets feel safer at night. "
            "Engineers are testing whether the new lamps last longer in winter. "
            "The mayor hopes to show that the project saves money over time. "
            "Teachers report that students now walk home with more confidence."
        )
        prepared = prepare_source(source)
        targets = sorted(grammar_target_inventory(prepared)[:5], key=lambda span: span.char_start)
        replacement = next(iter(sorted(allowed_verb_form_variants(targets[1].text) - {targets[1].text.lower()})))
        plan = GrammarPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_span_id=targets[1].id,
            corrupted_word=replacement,
            correction_basis_ko="이 자리에는 주변 구조에 맞는 원래 동사 형태가 필요합니다",
            supporting_evidence="Officials plan to expand the lighting system next month.",
            explanation="문맥상 이 자리의 동사 형태가 구조와 맞지 않습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="MVP-03",
            BatchRowId=0,
            QuestionType=QUESTION_TYPES["grammar"].label_ko,
            student_paragraph=render_numbered_span_edits(
                source_text=source,
                selected_spans=targets,
                replacement_by_span_id={targets[1].id: replacement},
                markers=["①", "②", "③", "④", "⑤"],
            ),
            question_stem=QUESTION_TYPES["grammar"].question_stem,
            choices=["①", "②", "③", "④", "⑤"],
            answer="②",
            explanation="②의 잘못된 형태는 주변 구조와 맞지 않으므로 원래 형태가 와야 합니다.",
        )
        self.assertEqual(
            validate_grammar_output(
                prepared_source=prepared,
                plan=plan,
                generated=generated,
                type_spec=QUESTION_TYPES["grammar"],
            ),
            [],
        )

    def test_grammar_validator_uses_target_ids_as_source_owned_contract(self) -> None:
        source = (
            "The city can reduce energy use without raising taxes. "
            "Officials plan to expand the lighting system next month. "
            "Residents say the brighter streets feel safer at night. "
            "Engineers are testing whether the new lamps last longer in winter. "
            "The mayor hopes to show that the project saves money over time. "
            "Teachers report that students now walk home with more confidence."
        )
        prepared = prepare_source(source)
        targets = sorted(grammar_target_inventory(prepared)[:5], key=lambda span: span.char_start)
        replacement = next(iter(sorted(allowed_verb_form_variants(targets[1].text) - {targets[1].text.lower()})))
        plan = GrammarPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=["alpha", "bravo", "charlie", "delta", "echo"],
            corrupted_span_id=targets[1].id,
            corrupted_word=replacement,
            correction_basis_ko="문맥상 맞지 않는 형태입니다",
            supporting_evidence="Officials plan to expand the lighting system next month.",
            explanation="문맥상 이 자리의 동사 형태가 구조와 맞지 않습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber="MVP-03",
            BatchRowId=0,
            QuestionType=QUESTION_TYPES["grammar"].label_ko,
            student_paragraph=render_numbered_span_edits(
                source_text=source,
                selected_spans=targets,
                replacement_by_span_id={targets[1].id: replacement},
                markers=["①", "②", "③", "④", "⑤"],
            ),
            question_stem=QUESTION_TYPES["grammar"].question_stem,
            choices=["①", "②", "③", "④", "⑤"],
            answer="②",
            explanation="②의 잘못된 형태는 주변 구조와 맞지 않으므로 정답입니다.",
        )
        self.assertEqual(
            validate_grammar_output(
                prepared_source=prepared,
                plan=plan,
                generated=generated,
                type_spec=QUESTION_TYPES["grammar"],
            ),
            [],
        )

    def test_allowed_verb_form_variants_exclude_malformed_forms(self) -> None:
        self.assertIn("reduced", allowed_verb_form_variants("reduce"))
        self.assertIn("reducing", allowed_verb_form_variants("reduce"))
        self.assertNotIn("reduceed", allowed_verb_form_variants("reduce"))
        self.assertNotIn("reduceing", allowed_verb_form_variants("reduce"))
        self.assertIn("increased", allowed_verb_form_variants("increase"))
        self.assertIn("increasing", allowed_verb_form_variants("increase"))
        self.assertNotIn("increaseed", allowed_verb_form_variants("increase"))
        self.assertNotIn("increaseing", allowed_verb_form_variants("increase"))
        self.assertIn("understood", allowed_verb_form_variants("understand"))
        self.assertNotIn("understanded", allowed_verb_form_variants("understand"))
        self.assertIn("rethought", allowed_verb_form_variants("rethink"))
        self.assertNotIn("rethinked", allowed_verb_form_variants("rethink"))

    def test_grammar_validator_rejects_malformed_pseudoword(self) -> None:
        source = (
            "The city can reduce energy use without raising taxes. "
            "Officials plan to expand the lighting system next month. "
            "Residents say the brighter streets feel safer at night. "
            "Engineers are testing whether the new lamps last longer in winter. "
            "The mayor hopes to show that the project saves money over time. "
            "Teachers report that students now walk home with more confidence."
        )
        prepared = prepare_source(source)
        inventory = grammar_target_inventory(prepared)
        reduce_span = next(span for span in inventory if span.text.lower() == "reduce")
        targets = [reduce_span] + [span for span in inventory if span.id != reduce_span.id][:4]
        plan = GrammarPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_span_id=reduce_span.id,
            corrupted_word="reduceing",
            correction_basis_ko="이 자리는 동사원형이 와야 합니다.",
            supporting_evidence="The city can reduce energy use without raising taxes.",
            explanation="문맥상 올바른 동사 형태가 필요합니다.",
        )

        errors = validate_plan_against_prepared_source(prepared, plan, QUESTION_TYPES["grammar"])

        self.assertTrue(any("malformed pseudo-word" in error for error in errors))

    def test_grammar_compatibility_mentions_verb_form_targets(self) -> None:
        source = "Birds sing softly at dawn. Leaves fall slowly in autumn."
        prepared = prepare_source(source)
        self.assertEqual(
            validate_question_type_compatibility(source, prepared, QUESTION_TYPES["grammar"]),
            ["Passage does not contain five workable verb-form targets for grammar."],
        )


if __name__ == "__main__":
    unittest.main()
