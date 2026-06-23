from __future__ import annotations

import re
import unittest

from questiongen.graph import compile_question_graph
from questiongen.parsers import prepare_source
from questiongen.planners import (
    PLANNER_QUOTA_EXHAUSTED_ERROR,
    plan_fill_in_the_blank,
    plan_grammar,
    plan_mood_atmosphere,
    plan_paragraph_ordering,
    plan_sentence_insertion,
    plan_underlined_phrase_meaning,
    plan_vocab,
)
from questiongen.prompts import (
    build_fill_in_the_blank_prompt,
    build_grammar_prompt,
    build_paragraph_ordering_prompt,
    build_sentence_insertion_prompt,
    build_underlined_phrase_meaning_prompt,
    build_vocab_prompt,
)
from questiongen.question_types import MOOD_ATMOSPHERE_SPEC, QUESTION_TYPES
from questiongen.schemas import (
    FillInTheBlankPlan,
    GrammarPlan,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
    VocabPlan,
)
from questiongen.targeting import allowed_verb_form_variants, grammar_target_inventory, vocab_target_inventory


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


class _DeterministicSentenceRetryPlanner:
    def __init__(self) -> None:
        self.invocations = 0
        self.last_prompt = ""

    def invoke(self, prompt: str) -> dict[str, object]:
        self.invocations += 1
        if self.invocations == 1:
            return {
                "target_unit_ids": ["S2"],
                "selected_gap_ids": ["G0", "G1", "G2", "G3", "G4"],
                "correct_gap_id": "G2",
                "explanation": "문맥상 이 위치가 가장 자연스럽습니다.",
            }
        self.last_prompt = prompt
        return {
            "target_unit_ids": ["S2"],
            "selected_gap_ids": ["G0", "G1", "G2", "G4", "G5"],
            "correct_gap_id": "G2",
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


class _DeterministicUnderlinedRetryPlanner:
    def __init__(self, weak_span_id: str, weak_span_text: str, strong_span_id: str, strong_span_text: str, evidence: str) -> None:
        self.weak_span_id = weak_span_id
        self.weak_span_text = weak_span_text
        self.strong_span_id = strong_span_id
        self.strong_span_text = strong_span_text
        self.evidence = evidence
        self.invocations = 0
        self.last_prompt = ""

    def invoke(self, prompt: str) -> dict[str, object]:
        self.invocations += 1
        if self.invocations == 1:
            return {
                "selected_span_id": self.weak_span_id,
                "selected_span_text": self.weak_span_text,
                "paraphrase_choices_ko": [
                    "첫 문장의 일부 표현이라는 뜻",
                    "한정된 예시만 가리킨다는 뜻",
                    "앞 문장을 반복한다는 뜻",
                    "주장을 약하게 바꾼다는 뜻",
                    "표현만 바뀌고 의미는 같다는 뜻",
                ],
                "correct_choice": "한정된 예시만 가리킨다는 뜻",
                "surface_meaning": "표면적 의미",
                "contextual_meaning": "문맥적 의미",
                "supporting_evidence": self.evidence,
                "explanation": "초안입니다.",
            }
        self.last_prompt = prompt
        return {
            "selected_span_id": self.strong_span_id,
            "selected_span_text": self.strong_span_text,
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


class _FillInTheBlankPlanner:
    def invoke(self, prompt: str) -> FillInTheBlankPlan:
        match = re.search(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)
        span_id = match.group(1) if match else "P0"
        span_text = match.group(2) if match else "improve safety without raising its energy budget"
        return FillInTheBlankPlan(
            selected_span_id=span_id,
            selected_span_text=span_text,
            completion_choices=[
                span_text,
                "more confusion among the residents",
                "a weaker plan for nearby roads",
                "fewer reasons to expand the system",
                "higher costs for the city budget",
            ],
            correct_choice=span_text,
            contextual_meaning_ko="원문의 핵심 설명이 그대로 복원되어야 한다는 의미",
            supporting_evidence=span_text,
            explanation="문맥상 원문의 핵심 설명이 복원되어야 합니다.",
        )


class _VocabPlanner:
    def invoke(self, prompt: str) -> VocabPlan:
        targets = re.findall(r"- rank \d+: (P\d+); score=\d+; text='([A-Za-z]+)'", prompt)[:5]
        target_ids, target_texts = zip(*targets)
        return VocabPlan(
            target_span_ids=list(target_ids),
            target_span_texts=list(target_texts),
            corrupted_span_id=target_ids[1],
            corrupted_word="heavier",
            correction_basis_ko="이 문맥에서는 원래 단어가 설명하는 기능이 유지되어야 합니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="문맥상 해당 단어의 쓰임이 맞지 않습니다.",
        )


class _VocabDriftPlanner:
    def invoke(self, prompt: str) -> VocabPlan:
        targets = re.findall(r"- rank \d+: (P\d+); score=\d+; text='([A-Za-z]+)'", prompt)[:5]
        target_ids, target_texts = zip(*targets)
        return VocabPlan(
            target_span_ids=list(target_ids),
            target_span_texts=["alpha", "bravo", "charlie", "delta", "echo"],
            corrupted_span_id=target_ids[1],
            corrupted_word="heavier",
            correction_basis_ko="이 문장은 절대 나오면 안 되는 자유서술 설명입니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="문맥상 해당 단어의 쓰임이 맞지 않습니다.",
        )


class _GrammarPlanner:
    def invoke(self, prompt: str) -> GrammarPlan:
        targets = re.findall(r"- rank \d+: (P\d+); score=\d+; text='([A-Za-z]+)'", prompt)[:5]
        target_ids, target_texts = zip(*targets)
        replacement = next(iter(sorted(allowed_verb_form_variants(target_texts[1]) - {target_texts[1].lower()})))
        return GrammarPlan(
            target_span_ids=list(target_ids),
            target_span_texts=list(target_texts),
            corrupted_span_id=target_ids[1],
            corrupted_word=replacement,
            correction_basis_ko="주변 구조에 맞는 동사 형태가 유지되어야 합니다",
            supporting_evidence="Officials now plan to expand the same lighting system to nearby neighborhoods.",
            explanation="문맥상 이 자리의 동사 형태가 구조와 맞지 않습니다.",
        )


class _GrammarDriftPlanner:
    def invoke(self, prompt: str) -> GrammarPlan:
        targets = re.findall(r"- rank \d+: (P\d+); score=\d+; text='([A-Za-z]+)'", prompt)[:5]
        target_ids, target_texts = zip(*targets)
        replacement = next(iter(sorted(allowed_verb_form_variants(target_texts[1]) - {target_texts[1].lower()})))
        return GrammarPlan(
            target_span_ids=list(target_ids),
            target_span_texts=["alpha", "bravo", "charlie", "delta", "echo"],
            corrupted_span_id=target_ids[1],
            corrupted_word=replacement,
            correction_basis_ko="이 문장은 절대 나오면 안 되는 자유서술 문법 해설입니다",
            supporting_evidence="Officials now plan to expand the same lighting system to nearby neighborhoods.",
            explanation="문맥상 이 자리의 동사 형태가 구조와 맞지 않습니다.",
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
        self.mood_type_spec = MOOD_ATMOSPHERE_SPEC
        self.underlined_source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        self.underlined_prepared = prepare_source(self.underlined_source)
        self.underlined_span = next(
            span
            for span in self.underlined_prepared.span_units
            if span.text == "resulting inequality brought only discontent"
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
        self.mvp_source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
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

    def test_planner_retries_after_deterministic_sentence_insertion_failure(self) -> None:
        planner = _DeterministicSentenceRetryPlanner()
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: planner,
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(planner.invocations, 2)
        self.assertIn("collapsed rendered positions", planner.last_prompt)

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
        self.assertIn("Selection reminders", prompt)

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

    def test_underlined_phrase_meaning_planner_retries_after_deterministic_quality_failure(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative to those around them. "
            "But the resulting inequality brought only discontent for the workers who compared salaries each day. "
            "Because those comparisons lingered, even small pay gaps began to feel like a personal insult."
        )
        prepared_source = prepare_source(source)
        weak_span = next(
            span
            for span in prepared_source.span_units
            if span.text == "lingered, even small pay gaps began"
        )
        strong_span = next(
            span for span in prepared_source.span_units if span.text == "resulting inequality brought only discontent"
        )
        underlined_state = {
            **self.state,
            "source_paragraph": source,
            "QuestionTypeKey": "underlined_phrase_meaning",
            "prepared_source": prepared_source,
        }
        planner = _DeterministicUnderlinedRetryPlanner(
            weak_span.id,
            weak_span.text,
            strong_span.id,
            strong_span.text,
            "the resulting inequality brought only discontent for the workers",
        )
        result = plan_underlined_phrase_meaning(
            underlined_state,
            QUESTION_TYPES["underlined_phrase_meaning"],
            structured_llm_factory=lambda schema: planner,
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(planner.invocations, 2)
        self.assertIn("not central enough", planner.last_prompt)

    def test_underlined_phrase_meaning_prompt_exposes_ranked_span_priorities(self) -> None:
        prompt = build_underlined_phrase_meaning_prompt(
            source_paragraph=self.underlined_source,
            prepared_source=self.underlined_prepared,
            type_spec=QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertIn("rank 1", prompt)
        self.assertIn("priority=top", prompt)
        self.assertIn("centrality=claim_bearing", prompt)
        self.assertIn("shape=proposition", prompt)
        self.assertIn("punctuation=clean", prompt)
        self.assertIn("context=", prompt)
        self.assertIn("Selection reminders", prompt)

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

    def test_fill_in_the_blank_planner_output_validates(self) -> None:
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "fill_in_the_blank",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = plan_fill_in_the_blank(
            state,
            QUESTION_TYPES["fill_in_the_blank"],
            structured_llm_factory=lambda schema: _FillInTheBlankPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], FillInTheBlankPlan)

    def test_vocab_planner_output_validates(self) -> None:
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "vocab",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = plan_vocab(
            state,
            QUESTION_TYPES["vocab"],
            structured_llm_factory=lambda schema: _VocabPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], VocabPlan)

    def test_vocab_planner_canonicalizes_target_texts_from_ids(self) -> None:
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "vocab",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = plan_vocab(
            state,
            QUESTION_TYPES["vocab"],
            structured_llm_factory=lambda schema: _VocabDriftPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        expected_texts = [span.text for span in vocab_target_inventory(state["prepared_source"])[:5]]
        self.assertEqual(result["plan"].target_span_texts, expected_texts)

    def test_grammar_planner_output_validates(self) -> None:
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "grammar",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = plan_grammar(
            state,
            QUESTION_TYPES["grammar"],
            structured_llm_factory=lambda schema: _GrammarPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], GrammarPlan)

    def test_grammar_planner_canonicalizes_target_texts_from_ids(self) -> None:
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "grammar",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = plan_grammar(
            state,
            QUESTION_TYPES["grammar"],
            structured_llm_factory=lambda schema: _GrammarDriftPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        expected_texts = [span.text for span in grammar_target_inventory(state["prepared_source"])[:5]]
        self.assertEqual(result["plan"].target_span_texts, expected_texts)

    def test_new_type_prompts_expose_target_inventories(self) -> None:
        prepared = prepare_source(self.mvp_source)
        blank_prompt = build_fill_in_the_blank_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_TYPES["fill_in_the_blank"],
        )
        vocab_prompt = build_vocab_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_TYPES["vocab"],
        )
        grammar_prompt = build_grammar_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_TYPES["grammar"],
        )
        self.assertIn("Phrase-span candidates", blank_prompt)
        self.assertIn("shape=proposition", blank_prompt)
        self.assertIn("Single-word vocab targets", vocab_prompt)
        self.assertIn("authoritative contract", vocab_prompt)
        self.assertIn("Single-word grammar targets", grammar_prompt)
        self.assertIn("allowed_variants=", grammar_prompt)

    def test_graph_rewrites_vocab_explanation_from_source_evidence(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabDriftPlanner())
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "vocab",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = runner.invoke(state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("문맥과 맞지 않습니다", explanation)
        self.assertIn("brighter crosswalks feel safer", explanation)
        self.assertNotIn("자유서술 설명", explanation)

    def test_graph_rewrites_grammar_explanation_from_structural_cue(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _GrammarDriftPlanner())
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "grammar",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = runner.invoke(state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("동사원형", explanation)
        self.assertIn("lighting system to nearby neighborhoods", explanation)
        self.assertNotIn("자유서술 문법 해설", explanation)


if __name__ == "__main__":
    unittest.main()
