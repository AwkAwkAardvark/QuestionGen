from __future__ import annotations

import unittest

from questiongen.graph import compile_question_graph
from questiongen.parsers import prepare_source
from questiongen.planners import (
    PLANNER_QUOTA_EXHAUSTED_ERROR,
    plan_mood_atmosphere,
    plan_paragraph_ordering,
    plan_sentence_insertion,
    plan_underlined_phrase_meaning,
)
from questiongen.prompts import (
    build_paragraph_ordering_prompt,
    build_sentence_insertion_prompt,
    build_underlined_phrase_meaning_prompt,
)
from questiongen.question_types import MOOD_ATMOSPHERE_SPEC, QUESTION_TYPES
from questiongen.schemas import (
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
)


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


class _QuotaPlanner:
    def invoke(self, prompt: str) -> dict[str, object]:
        raise RuntimeError(
            "Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan "
            "and billing details.', 'type': 'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}}"
        )


class _GenericServicePlanner:
    def invoke(self, prompt: str) -> dict[str, object]:
        raise RuntimeError("Error code: 500 - {'error': {'message': 'Internal server error.'}}")


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


class _ContextAnchoredInsertionPlanner:
    def invoke(self, prompt: str) -> SentenceInsertionPlan:
        return SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G6"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )


class _AdjacencyParagraphPlanner:
    def invoke(self, prompt: str) -> ParagraphOrderingPlan:
        return ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1", "S2"], ["S3", "S4"], ["S5"]],
            explanation="도입부 다음에 각 전개 단계를 배열하는 흐름입니다.",
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


class _UnderlinedPhraseMeaningPlanner:
    def __init__(self, span_id: str, span_text: str, evidence: str) -> None:
        self.span_id = span_id
        self.span_text = span_text
        self.evidence = evidence

    def invoke(self, prompt: str) -> UnderlinedPhraseMeaningPlan:
        return UnderlinedPhraseMeaningPlan(
            selected_span_id=self.span_id,
            selected_span_text=self.span_text,
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
            supporting_evidence=self.evidence,
            explanation="밑줄 친 표현은 불평등 때문에 불만이 커졌다는 뜻입니다.",
        )


class _UnderlinedRetryPlanner:
    def __init__(self, span_id: str, span_text: str, evidence: str) -> None:
        self.span_id = span_id
        self.span_text = span_text
        self.evidence = evidence
        self.invocations = 0
        self.last_prompt = ""

    def invoke(self, prompt: str) -> dict[str, object]:
        self.invocations += 1
        if self.invocations == 1:
            return {
                "selected_span_id": "P999",
                "selected_span_text": self.span_text,
                "paraphrase_choices_ko": [
                    "문맥상 맞는 뜻",
                    "문맥상 맞는 뜻",
                    "다른 뜻",
                    "또 다른 뜻",
                    "잘못된 뜻",
                ],
                "correct_choice": "문맥상 맞는 뜻",
                "surface_meaning": "표면적 의미",
                "contextual_meaning": "문맥적 의미",
                "supporting_evidence": self.evidence,
                "explanation": "초안입니다.",
            }
        self.last_prompt = prompt
        return {
            "selected_span_id": self.span_id,
            "selected_span_text": self.span_text,
            "paraphrase_choices_ko": [
                "비교 속에서 상대적 박탈감만 커졌다는 뜻",
                "경제적 격차가 불만을 낳았다는 뜻",
                "보상이 충분해도 만족이 오래가지 않았다는 뜻",
                "경쟁이 심해져 분노가 겉으로 드러났다는 뜻",
                "차이가 커질수록 성취감도 함께 커졌다는 뜻",
            ],
            "correct_choice": "경제적 격차가 불만을 낳았다는 뜻",
            "surface_meaning": "오직 불만만을 가져왔다는 말",
            "contextual_meaning": "상대적 불평등 때문에 만족 대신 불만이 커졌다는 뜻",
            "supporting_evidence": self.evidence,
            "explanation": "문맥을 다시 반영한 수정안입니다.",
        }


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
        self.mood_type_spec = MOOD_ATMOSPHERE_SPEC
        self.underlined_source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        self.underlined_prepared = prepare_source(self.underlined_source)
        self.underlined_span = next(
            span
            for span in self.underlined_prepared.span_units
            if span.text == "brought only discontent"
        )
        self.contextual_insertion_source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        self.ordering_source = (
            "Many museums are rethinking how visitors experience their collections. "
            "First, they replace long wall labels with short questions that invite curiosity. "
            "This curiosity encourages people to look closely before reading an explanation. "
            "Next, curators turn that curiosity into quiet audio guides for visitors who want more detail. "
            "Those guides let each person choose how much background information to hear. "
            "Finally, the feedback gathered through those guides helps museums redesign later exhibits."
        )

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

    def test_quota_planner_failure_is_normalized_as_service_quota(self) -> None:
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: _QuotaPlanner(),
        )
        self.assertEqual(result["status"], "planning_error")
        self.assertEqual(result["errors"], [PLANNER_QUOTA_EXHAUSTED_ERROR])

    def test_non_quota_service_failure_keeps_service_prefix_without_quota_normalization(self) -> None:
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: _GenericServicePlanner(),
        )
        self.assertEqual(result["status"], "planning_error")
        self.assertTrue(result["errors"])
        self.assertTrue(result["errors"][0].startswith("Planner service failed:"))
        self.assertNotIn("insufficient_quota", result["errors"][0])

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

    def test_sentence_insertion_prompt_exposes_ranked_target_hints(self) -> None:
        prompt = build_sentence_insertion_prompt(
            source_paragraph=self.contextual_insertion_source,
            prepared_source=prepare_source(self.contextual_insertion_source),
            type_spec=QUESTION_TYPES["sentence_insertion"],
        )
        self.assertIn("Ranked target candidates", prompt)
        self.assertIn("priority=strong", prompt)
        self.assertIn("connector_only=", prompt)
        self.assertIn("between S1", prompt)

    def test_paragraph_ordering_planner_output_validates(self) -> None:
        result = plan_paragraph_ordering(
            self.state,
            QUESTION_TYPES["paragraph_ordering"],
            structured_llm_factory=lambda schema: _ParagraphOrderingPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], ParagraphOrderingPlan)

    def test_paragraph_ordering_prompt_exposes_boundary_and_block_start_hints(self) -> None:
        prompt = build_paragraph_ordering_prompt(
            source_paragraph=self.ordering_source,
            prepared_source=prepare_source(self.ordering_source),
            type_spec=QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertIn("Boundary hints", prompt)
        self.assertIn("Candidate continuation-block starts", prompt)
        self.assertIn("right_stage_cue=next", prompt.lower())
        self.assertIn("block_start_priority=high", prompt)

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

    def test_graph_rewrites_sentence_insertion_explanation_from_surrounding_context(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _ContextAnchoredInsertionPlanner())
        insertion_state = {
            **self.state,
            "source_paragraph": self.contextual_insertion_source,
            "QuestionTypeKey": "sentence_insertion",
            "prepared_source": prepare_source(self.contextual_insertion_source),
        }
        result = runner.invoke(insertion_state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertNotIn("The new lights also use less electricity than the older fixtures.", explanation)
        self.assertIn("new lights", explanation)
        self.assertIn("Because the lights use less electricity", explanation)

    def test_graph_rewrites_paragraph_ordering_explanation_as_edge_chain(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _AdjacencyParagraphPlanner())
        paragraph_state = {
            **self.state,
            "source_paragraph": self.ordering_source,
            "QuestionTypeKey": "paragraph_ordering",
            "prepared_source": prepare_source(self.ordering_source),
        }
        result = runner.invoke(paragraph_state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertNotIn("핵심 화제 제시", explanation)
        self.assertIn("뒤에는", explanation)
        self.assertIn("다음에는", explanation)

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
            self.mood_type_spec,
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
        runner = compile_question_graph(
            structured_llm_factory=lambda schema: _MoodAtmospherePlanner(),
            question_types={**QUESTION_TYPES, "mood_atmosphere": self.mood_type_spec},
        )
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

    def test_underlined_phrase_meaning_planner_output_validates(self) -> None:
        underlined_state = {
            **self.state,
            "source_paragraph": self.underlined_source,
            "QuestionTypeKey": "underlined_phrase_meaning",
            "prepared_source": self.underlined_prepared,
        }
        result = plan_underlined_phrase_meaning(
            underlined_state,
            QUESTION_TYPES["underlined_phrase_meaning"],
            structured_llm_factory=lambda schema: _UnderlinedPhraseMeaningPlanner(
                self.underlined_span.id,
                self.underlined_span.text,
                "the resulting inequality brought only discontent",
            ),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], UnderlinedPhraseMeaningPlan)

    def test_underlined_phrase_meaning_planner_retries_after_schema_failure(self) -> None:
        planner = _UnderlinedRetryPlanner(
            self.underlined_span.id,
            self.underlined_span.text,
            "the resulting inequality brought only discontent",
        )
        underlined_state = {
            **self.state,
            "source_paragraph": self.underlined_source,
            "QuestionTypeKey": "underlined_phrase_meaning",
            "prepared_source": self.underlined_prepared,
        }
        result = plan_underlined_phrase_meaning(
            underlined_state,
            QUESTION_TYPES["underlined_phrase_meaning"],
            structured_llm_factory=lambda schema: planner,
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(planner.invocations, 2)
        self.assertIn("selected_span_id", planner.last_prompt)

    def test_underlined_phrase_meaning_prompt_exposes_ranked_span_priorities(self) -> None:
        prompt = build_underlined_phrase_meaning_prompt(
            source_paragraph=self.underlined_source,
            prepared_source=self.underlined_prepared,
            type_spec=QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertIn("rank 1", prompt)
        self.assertIn("priority=top", prompt)
        self.assertIn("centrality=claim_bearing", prompt)
        self.assertIn("context=", prompt)

    def test_graph_rewrites_underlined_phrase_meaning_explanation(self) -> None:
        runner = compile_question_graph(
            structured_llm_factory=lambda schema: _UnderlinedPhraseMeaningPlanner(
                self.underlined_span.id,
                self.underlined_span.text,
                "the resulting inequality brought only discontent",
            )
        )
        underlined_state = {
            **self.state,
            "source_paragraph": self.underlined_source,
            "QuestionTypeKey": "underlined_phrase_meaning",
            "prepared_source": self.underlined_prepared,
        }
        result = runner.invoke(underlined_state)
        self.assertEqual(result["status"], "validation_passed")
        self.assertIn("brought only discontent", result["generated"].explanation or "")
        self.assertNotIn("surface_meaning", result["generated"].explanation or "")


if __name__ == "__main__":
    unittest.main()
