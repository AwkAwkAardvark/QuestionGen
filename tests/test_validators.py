from __future__ import annotations

import unittest

from questiongen.parsers import prepare_source
from questiongen.question_types import MOOD_ATMOSPHERE_SPEC, QUESTION_TYPES
from questiongen.schemas import (
    GeneratedQuestion,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
)
from questiongen.validators import (
    plan_check,
    source_check,
    validate_mood_atmosphere_output,
    validate_plan_against_prepared_source,
    validate_paragraph_ordering_output,
    validate_sentence_insertion_output,
    validate_teacher_facing_explanation,
    validate_underlined_phrase_meaning_output,
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

    def test_underlined_phrase_meaning_plan_validator_requires_known_span_and_exact_text(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        prepared = prepare_source(source)
        selected_span = next(span for span in prepared.span_units if span.text == "brought only discontent")
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
        selected_span = next(span for span in prepared.span_units if span.text == "brought only discontent")
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
                "[밑줄]brought only discontent[/밑줄]",
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
                "밑줄 친 'brought only discontent'는 표면적으로는 오직 불만만을 가져왔다는 말입니다. "
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
        selected_span = next(span for span in prepared.span_units if span.text == "brought only discontent")
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


if __name__ == "__main__":
    unittest.main()
