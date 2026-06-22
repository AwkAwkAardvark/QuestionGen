from __future__ import annotations

import unittest

from questiongen.parsers import prepare_source
from questiongen.question_types import QUESTION_TYPES
from questiongen.schemas import GeneratedQuestion, SentenceInsertionPlan
from questiongen.validators import source_check, validate_sentence_insertion_output


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.type_spec = QUESTION_TYPES["sentence_insertion"]
        self.prepared = prepare_source("A. B. C. D. E. F.")

    def test_source_check_fails_for_too_few_sentences(self) -> None:
        prepared = prepare_source("A. B. C. D.")
        result = source_check(
            {
                "source_paragraph": "A. B. C. D.",
                "OriginalQuestionNumber": 1,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": prepared,
                "plan": None,
                "generated": None,
                "status": "source_prepared",
                "errors": [],
            },
            self.type_spec,
        )
        self.assertEqual(result["status"], "source_error")

    def test_source_check_fails_for_malformed_gap(self) -> None:
        self.prepared.gap_units[1].before_unit_id = "BROKEN"
        result = source_check(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": 1,
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
                "OriginalQuestionNumber": 1,
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

    def test_final_validator_catches_plan_and_rendering_mismatches(self) -> None:
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        generated = GeneratedQuestion(
            OriginalQuestionNumber=1,
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
            OriginalQuestionNumber=1,
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
            OriginalQuestionNumber=1,
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


if __name__ == "__main__":
    unittest.main()
