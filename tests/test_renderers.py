from __future__ import annotations

import unittest

from questiongen.parsers import prepare_source
from questiongen.question_types import QUESTION_TYPES
from questiongen.renderers import render_paragraph_ordering, render_sentence_insertion
from questiongen.schemas import ParagraphOrderingPlan, SentenceInsertionPlan


class RendererTests(unittest.TestCase):
    def test_sentence_insertion_renderer_builds_expected_output(self) -> None:
        prepared = prepare_source("A. B. C. D. E. F.")
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        result = render_sentence_insertion(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["sentence_insertion"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.given_sentence, "C.")
        self.assertNotIn("C.", generated.student_paragraph)
        for sentence in ["A.", "B.", "D.", "E.", "F."]:
            self.assertEqual(generated.student_paragraph.count(sentence), 1)
        for marker in ["①", "②", "③", "④", "⑤"]:
            self.assertEqual(generated.student_paragraph.count(marker), 1)
        self.assertEqual(generated.answer, "③")
        self.assertEqual(generated.QuestionType, QUESTION_TYPES["sentence_insertion"].label_ko)
        self.assertEqual(generated.OriginalQuestionNumber, "8-Analysis")
        self.assertEqual(generated.BatchRowId, 0)
        self.assertEqual(generated.student_paragraph, "① A. ② B. ③ D. ④ E. ⑤ F.")

    def test_paragraph_ordering_renderer_builds_expected_output(self) -> None:
        prepared = prepare_source("A. B. C. D. E. F.")
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2", "S3"], ["S4", "S5"]],
            explanation="도입부 다음에 세 덩어리로 배열하는 흐름이 가장 자연스럽습니다.",
        )
        result = render_paragraph_ordering(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 1,
                "QuestionTypeKey": "paragraph_ordering",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.QuestionType, QUESTION_TYPES["paragraph_ordering"].label_ko)
        self.assertEqual(generated.BatchRowId, 1)
        self.assertIn("[주어진 글] A.", generated.student_paragraph)
        self.assertIn("(A)", generated.student_paragraph)
        self.assertEqual(len(generated.choices), 5)
        self.assertIn(generated.answer, ["①", "②", "③", "④", "⑤"])


if __name__ == "__main__":
    unittest.main()
