from __future__ import annotations

import unittest

from questiongen.graph import compile_question_graph
from questiongen.parsers import prepare_source
from questiongen.planners import plan_mood_atmosphere, plan_paragraph_ordering, plan_sentence_insertion
from questiongen.question_types import QUESTION_TYPES
from questiongen.schemas import MoodAtmospherePlan, ParagraphOrderingPlan, SentenceInsertionPlan


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


class _ParagraphOrderingPlanner:
    def invoke(self, prompt: str) -> ParagraphOrderingPlan:
        return ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1", "S2"], ["S3", "S4"], ["S5"]],
            explanation="S0 다음에 S1과 S2가 이어지는 흐름입니다.",
        )


class _CollapsedGapPlanner:
    def invoke(self, prompt: str) -> SentenceInsertionPlan:
        return SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G3", "G4"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )


class _InvalidOrderingCoveragePlanner:
    def invoke(self, prompt: str) -> ParagraphOrderingPlan:
        return ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2"], ["S4", "S5"]],
            explanation="도입부 이후 흐름을 나누었다고 판단했습니다.",
        )


class _MoodAtmospherePlanner:
    def invoke(self, prompt: str) -> MoodAtmospherePlan:
        return MoodAtmospherePlan(
            target_holder="the monkey",
            initial_emotion="content",
            final_emotion="angry",
            choice_pairs=[
                "content -> angry",
                "anxious -> relieved",
                "confident -> embarrassed",
                "curious -> disappointed",
                "proud -> grateful",
            ],
            correct_choice="content -> angry",
            initial_evidence="were initially perfectly content with a reward of cucumbers",
            final_evidence="became enraged",
            shift_trigger="when one monkey receiving plain old cucumbers",
            explanation="초반에는 만족하지만 이후 상황 변화로 분노하게 됩니다.",
        )


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {
            "source_paragraph": "A. B. C. D. E. F.",
            "OriginalQuestionNumber": "8-Analysis",
            "BatchRowId": 0,
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

    def test_paragraph_ordering_planner_output_validates(self) -> None:
        result = plan_paragraph_ordering(
            self.state,
            QUESTION_TYPES["paragraph_ordering"],
            structured_llm_factory=lambda schema: _ParagraphOrderingPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], ParagraphOrderingPlan)

    def test_graph_reclassifies_collapsed_gap_plan_as_planning_error(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _CollapsedGapPlanner())
        result = runner.invoke(self.state)
        self.assertEqual(result["status"], "planning_error")
        self.assertTrue(any("collapse" in error for error in result["errors"]))

    def test_graph_reclassifies_invalid_ordering_plan_as_planning_error(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _InvalidOrderingCoveragePlanner())
        paragraph_state = {
            **self.state,
            "QuestionTypeKey": "paragraph_ordering",
        }
        result = runner.invoke(paragraph_state)
        self.assertEqual(result["status"], "planning_error")
        self.assertTrue(any("cover all sentence IDs" in error for error in result["errors"]))

    def test_graph_rewrites_internal_paragraph_ordering_explanation(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _ParagraphOrderingPlanner())
        paragraph_state = {
            **self.state,
            "QuestionTypeKey": "paragraph_ordering",
        }
        result = runner.invoke(paragraph_state)
        self.assertEqual(result["status"], "validation_passed")
        self.assertNotIn("S0", result["generated"].explanation or "")

    def test_mood_atmosphere_planner_output_validates(self) -> None:
        mood_state = {
            **self.state,
            "source_paragraph": (
                "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
                "to those around them. In one experiment, two capuchin monkeys were initially perfectly content "
                "with a reward of cucumbers when they successfully performed a task. But when one monkey receiving "
                "plain old cucumbers became enraged, angrily throwing the previously satisfactory salad vegetable "
                "at its handler. The monkey's economy had grown, since grapes are better than cucumbers. "
                "But the resulting inequality brought only discontent."
            ),
            "QuestionTypeKey": "mood_atmosphere",
            "prepared_source": prepare_source(
                "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
                "to those around them. In one experiment, two capuchin monkeys were initially perfectly content "
                "with a reward of cucumbers when they successfully performed a task. But when one monkey receiving "
                "plain old cucumbers became enraged, angrily throwing the previously satisfactory salad vegetable "
                "at its handler. The monkey's economy had grown, since grapes are better than cucumbers. "
                "But the resulting inequality brought only discontent."
            ),
        }
        result = plan_mood_atmosphere(
            mood_state,
            QUESTION_TYPES["mood_atmosphere"],
            structured_llm_factory=lambda schema: _MoodAtmospherePlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], MoodAtmospherePlan)

    def test_graph_rewrites_mood_atmosphere_explanation(self) -> None:
        mood_source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. In one experiment, two capuchin monkeys were initially perfectly content "
            "with a reward of cucumbers when they successfully performed a task. But when one monkey receiving "
            "plain old cucumbers became enraged, angrily throwing the previously satisfactory salad vegetable "
            "at its handler. The monkey's economy had grown, since grapes are better than cucumbers. "
            "But the resulting inequality brought only discontent."
        )
        runner = compile_question_graph(structured_llm_factory=lambda schema: _MoodAtmospherePlanner())
        mood_state = {
            **self.state,
            "source_paragraph": mood_source,
            "QuestionTypeKey": "mood_atmosphere",
            "prepared_source": prepare_source(mood_source),
        }
        result = runner.invoke(mood_state)
        self.assertEqual(result["status"], "validation_passed")
        self.assertIn("the monkey", result["generated"].explanation or "")
        self.assertNotIn("choice_pairs", result["generated"].explanation or "")


if __name__ == "__main__":
    unittest.main()
