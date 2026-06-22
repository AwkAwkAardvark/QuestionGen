from __future__ import annotations

import unittest

from questiongen.parsers import prepare_source
from questiongen.planners import plan_sentence_insertion
from questiongen.question_types import QUESTION_TYPES
from questiongen.schemas import SentenceInsertionPlan


class _ValidPlanner:
    def invoke(self, prompt: str) -> SentenceInsertionPlan:
        return SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )


class _InvalidPlanner:
    def invoke(self, prompt: str) -> dict[str, object]:
        return {
            "target_unit_ids": ["S2", "S3"],
            "selected_gap_ids": ["G0"],
            "correct_gap_id": "G9",
            "explanation": "invalid",
        }


class _RetryPlanner:
    def __init__(self) -> None:
        self.invocations = 0

    def invoke(self, prompt: str) -> dict[str, object]:
        self.invocations += 1
        if self.invocations == 1:
            return {
                "target_unit_ids": ["S4"],
                "selected_gap_ids": ["G0", "G1", "G2", "G3", "G4"],
                "correct_gap_id": "G6",
                "explanation": "문맥상 이 위치를 선택했습니다.",
            }
        self.last_prompt = prompt
        return {
            "target_unit_ids": ["S4"],
            "selected_gap_ids": ["G0", "G1", "G2", "G4", "G6"],
            "correct_gap_id": "G6",
            "explanation": "문맥상 이 위치가 가장 자연스럽습니다.",
        }


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {
            "source_paragraph": "A. B. C. D. E. F.",
            "OriginalQuestionNumber": 1,
            "QuestionTypeKey": "sentence_insertion",
            "prepared_source": prepare_source("A. B. C. D. E. F."),
            "plan": None,
            "generated": None,
            "status": "source_passed",
            "errors": [],
        }
        self.type_spec = QUESTION_TYPES["sentence_insertion"]

    def test_planner_output_validates(self) -> None:
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: _ValidPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], SentenceInsertionPlan)

    def test_invalid_planner_payload_fails(self) -> None:
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: _InvalidPlanner(),
        )
        self.assertEqual(result["status"], "planning_error")
        self.assertTrue(
            any(
                "SentenceInsertionPlan requires exactly one target_unit_id." in error
                for error in result["errors"]
            )
        )

    def test_planner_retries_once_after_schema_failure(self) -> None:
        planner = _RetryPlanner()
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: planner,
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(planner.invocations, 2)
        self.assertIn("correct_gap_id", planner.last_prompt)


if __name__ == "__main__":
    unittest.main()
