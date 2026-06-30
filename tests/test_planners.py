from __future__ import annotations

import re
import time
import unittest

from questiongen.explanations import build_explanation_context, write_teacher_facing_explanation
from questiongen.graph import compile_question_graph
from questiongen.parsers import prepare_source
from questiongen.designers import build_design, hydrate_plan_from_draft
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
from questiongen.question_types import MOOD_ATMOSPHERE_SPEC, QUESTION_SUBTYPE_SPECS, QUESTION_TYPES
from questiongen.renderers import render_grammar, render_vocab
from questiongen.schemas import (
    ContextualVocabChoiceDraft,
    ContextualVocabChoicePlan,
    FillInTheBlankDraft,
    FillInTheBlankPlan,
    GrammarDesign,
    GrammarPlan,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    PreparedSource,
    GapUnit,
    SentenceInsertionPlan,
    SourceUnit,
    SpanUnit,
    UnderlinedVocabDesign,
    UnderlinedVocabPlan,
    UnderlinedPhraseMeaningPlan,
)
from questiongen.targeting import allowed_verb_form_variants, grammar_target_inventory, vocab_choice_inventory


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


class _SleepingPlanner:
    def __init__(self, sleep_seconds: float) -> None:
        self.sleep_seconds = sleep_seconds
        self.invocations = 0

    def invoke(self, prompt: str) -> SentenceInsertionPlan:
        self.invocations += 1
        time.sleep(self.sleep_seconds)
        return SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )


class _RetryPlanner:
    def __init__(self) -> None:
        self.invocations = 0

    def invoke(self, prompt: str) -> dict[str, object]:
        self.invocations += 1
        if self.invocations == 1:
            return {
                "correct_gap_id": "G1",
                "explanation": "문맥상 이 위치를 선택했습니다.",
            }
        self.last_prompt = prompt
        return {
            "correct_gap_id": "G2",
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
                "correct_gap_id": "G1",
                "explanation": "문맥상 이 위치가 가장 자연스럽습니다.",
            }
        self.last_prompt = prompt
        return {
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
                "supporting_evidence": "invented evidence",
                "explanation": "초안입니다.",
            }
        self.last_prompt = prompt
        return {
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
        subtype_match = re.search(r"Active subtype: ([A-Za-z0-9_]+)", prompt)
        active_subtype = subtype_match.group(1) if subtype_match else "blank_inference_proposition_5_choices"
        if active_subtype == "blank_connective_relation_5_choices":
            return FillInTheBlankPlan(
                subtype="connective_relation",
                selected_span_id=span_id,
                selected_span_text=span_text,
                completion_choices=[
                    "as a result",
                    "for example",
                    "in contrast",
                    "even so",
                    "meanwhile",
                ],
                correct_choice="as a result",
                contextual_meaning_ko="이 빈칸은 앞선 원인에서 뒤의 결과로 이어지는 관계를 복원해야 합니다",
                supporting_evidence="Because the lights use less electricity",
                explanation="문맥상 앞선 원인에서 뒤의 결과로 이어지는 관계가 복원되어야 합니다.",
            )
        if active_subtype == "blank_summary_completion_5_choices":
            return FillInTheBlankPlan(
                subtype="summary_completion",
                selected_span_id=span_id,
                selected_span_text=span_text,
                completion_choices=[
                    "opportunity must be shared widely to preserve social peace",
                    "economic rewards should remain concentrated in a few hands",
                    "public distrust naturally strengthens every reform effort",
                    "innovation matters more than any concern about inequality",
                    "social peace depends on reducing every form of ambition",
                ],
                correct_choice="opportunity must be shared widely to preserve social peace",
                contextual_meaning_ko="이 빈칸은 글의 최종 교훈을 압축해 완성해야 합니다",
                supporting_evidence="The lesson is",
                explanation="문맥상 글의 최종 교훈을 압축해 완성해야 합니다.",
            )
        return FillInTheBlankPlan(
            subtype="proposition_inference",
            selected_span_id=span_id,
            selected_span_text=span_text,
            completion_choices=[
                "improve safety while keeping the energy budget unchanged",
                "create more confusion among the residents",
                "slow the expansion of nearby neighborhoods",
                "raise costs without improving crosswalk visibility",
                "reduce safety to cut the energy budget",
            ],
            correct_choice="improve safety while keeping the energy budget unchanged",
            contextual_meaning_ko="이 빈칸은 에너지 예산을 늘리지 않으면서 안전을 높인다는 핵심 효과를 복원해야 합니다",
            supporting_evidence="Because the lights use less electricity",
            explanation="문맥상 에너지 예산을 늘리지 않으면서 안전을 높인다는 핵심 효과가 복원되어야 합니다.",
        )


class _VocabPlanner:
    def invoke(self, prompt: str) -> ContextualVocabChoicePlan | UnderlinedVocabPlan:
        targets = re.findall(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)
        target_text_by_id = dict(targets[:5])
        locked_corruptible_ids = _extract_locked_corruptible_ids(prompt)
        locked_answer_id = _extract_locked_answer_span_id(prompt)
        locked_untouched_id = _extract_locked_untouched_distractor_id(prompt)
        subtype_match = re.search(r"Active subtype: ([A-Za-z0-9_]+)", prompt)
        active_subtype = subtype_match.group(1) if subtype_match else ""
        if active_subtype == "contextual_vocab_error_1_among_5_polarity_scope_5":
            target_ids, target_texts = zip(*targets[:5])
            if locked_corruptible_ids:
                polarity_target_id = locked_corruptible_ids[0]
            elif "cease" in target_texts:
                polarity_target_id = target_ids[target_texts.index("cease")]
            else:
                polarity_target_id = target_ids[0]
            polarity_text = target_text_by_id[polarity_target_id]
            polarity_replacement = "continue" if polarity_text == "cease" else "reduce" if polarity_text == "expand" else "more"
            return UnderlinedVocabPlan(
                subtype="contextual_error_1_among_5_polarity_scope",
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_replacements=[
                    {"span_id": polarity_target_id, "replacement_text": polarity_replacement},
                ],
                answer_span_id=polarity_target_id,
                selection_basis_ko="이 자리는 멈춤이나 축소처럼 방향과 범위가 분명히 제한되어야 합니다",
                supporting_evidence="Leaders cease wasteful spending during droughts.",
                explanation="문맥상 방향과 범위를 어긋나게 만든 하나의 표현을 골라야 합니다.",
            )
        if active_subtype == "contextual_vocab_error_1_among_5_collocation_5":
            target_ids, target_texts = zip(*targets[:5])
            if locked_answer_id:
                collocation_target_id = locked_answer_id
            elif locked_corruptible_ids:
                collocation_target_id = locked_corruptible_ids[0]
            else:
                collocation_target_id = target_ids[target_texts.index("ignore")] if "ignore" in target_texts else target_ids[-1]
            return UnderlinedVocabPlan(
                subtype="contextual_error_1_among_5_collocation",
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_replacements=[
                    {"span_id": collocation_target_id, "replacement_text": "collect"},
                ],
                answer_span_id=collocation_target_id,
                selection_basis_ko="이 자리는 문맥상 자연스러운 어휘 결합과 선택 제약이 유지되어야 합니다",
                supporting_evidence="Families ignore rumors during emergencies.",
                explanation="문맥상 자연스러운 어휘 결합을 깨뜨린 표현을 골라야 합니다.",
            )
        if active_subtype == "contextual_vocab_correct_among_4_corrupted_5":
            target_ids, target_texts = zip(*targets[:5])
            answer_span_id = locked_answer_id or target_ids[1]
            return UnderlinedVocabPlan(
                subtype="contextual_correct_among_4_corrupted",
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_replacements=[
                    {"span_id": span_id, "replacement_text": replacement}
                    for span_id, replacement in zip(
                        [span_id for span_id in target_ids if span_id != answer_span_id],
                        ["weaken", "ignore", "delay", "worsen"],
                        strict=False,
                    )
                ],
                answer_span_id=answer_span_id,
                selection_basis_ko="이 자리는 원문이 유지한 효과를 가장 자연스럽게 이어 주는 표현이어야 합니다",
                supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
                explanation="문맥상 하나만 원래 의미를 유지하고 나머지는 의미를 비틀고 있습니다.",
            )
        if active_subtype == "contextual_vocab_error_1_among_5_5":
            target_ids, target_texts = zip(*targets[:5])
            answer_span_id = locked_answer_id or target_ids[2]
            return UnderlinedVocabPlan(
                subtype="contextual_error_1_among_5",
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_replacements=[
                    {"span_id": answer_span_id, "replacement_text": "ignore"},
                ],
                answer_span_id=answer_span_id,
                selection_basis_ko="이 자리는 원래 표현만 글의 핵심 의미를 유지합니다",
                supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
                explanation="문맥상 하나의 표현만 의미를 어긋나게 만든 경우를 골라야 합니다.",
            )
        if active_subtype == "contextual_vocab_correct_among_3_corrupted_5":
            target_ids, target_texts = zip(*targets[:5])
            answer_span_id = locked_answer_id or target_ids[1]
            untouched_id = locked_untouched_id or target_ids[0]
            return UnderlinedVocabPlan(
                subtype="contextual_correct_among_3_corrupted",
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_replacements=[
                    {"span_id": span_id, "replacement_text": replacement}
                    for span_id, replacement in zip(
                        [span_id for span_id in target_ids if span_id not in {answer_span_id, untouched_id}],
                        ["weaken", "delay", "worsen"],
                        strict=False,
                    )
                ],
                answer_span_id=answer_span_id,
                selection_basis_ko="문맥상 정답 표현만 가장 강하게 원래 의미를 유지합니다",
                supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
                explanation="문맥상 정답만 가장 강하게 원래 의미를 유지합니다.",
            )
        if active_subtype == "contextual_vocab_best_paraphrase_choice_5":
            selected_span_id = targets[0][0] if targets else "P0"
            selected_span_text = targets[0][1] if targets else "brighter"
            return ContextualVocabChoicePlan(
                subtype="contextual_best_paraphrase_choice",
                selected_span_id=selected_span_id,
                selected_span_text=selected_span_text,
                choice_words=[
                    "stronger",
                    "weaker",
                    "narrower",
                    "riskier",
                    "costlier",
                ],
                correct_choice="stronger",
                contextual_meaning_ko="이 자리는 원문의 표현을 그대로 복원하는 것이 아니라 더 강한 긍정 방향의 바꿔쓰기가 와야 합니다",
                supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
                explanation="문맥상 더 강한 긍정 방향의 바꿔쓰기가 와야 합니다.",
            )
        if active_subtype == "contextual_vocab_phrase_choice_5":
            selected_span_id = targets[0][0] if targets else "P0"
            selected_span_text = targets[0][1] if targets else "improve safety"
            return ContextualVocabChoicePlan(
                subtype="contextual_phrase_choice",
                selected_span_id=selected_span_id,
                selected_span_text=selected_span_text,
                choice_words=[
                    selected_span_text,
                    "ethical weight",
                    "factual burden",
                    "narrow logic",
                    "surface detail",
                ],
                correct_choice=selected_span_text,
                contextual_meaning_ko="이 자리는 주장에 실리는 규범적 무게를 가리키는 어구가 와야 합니다",
                supporting_evidence=selected_span_text,
                explanation="문맥상 주장에 실리는 규범적 무게를 가리키는 어구가 와야 합니다.",
            )
        selected_span_id = targets[0][0] if targets else "P0"
        selected_span_text = targets[0][1] if targets else "improve"
        return ContextualVocabChoicePlan(
            selected_span_id=selected_span_id,
            selected_span_text=selected_span_text,
            choice_words=[
                "strengthen",
                "weaken",
                "ignore",
                "delay",
                "worsen",
            ],
            correct_choice="strengthen",
            contextual_meaning_ko="이 자리는 안전을 더 높이는 방향의 표현이 와야 한다는 뜻입니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="문맥상 이 자리는 안전을 더 높이는 방향의 표현이 와야 합니다.",
        )


class _VocabDriftPlanner:
    def invoke(self, prompt: str) -> dict[str, object]:
        match = re.search(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)
        selected_span_id = match.group(1) if match else "P0"
        selected_span_text = match.group(2) if match else "improve"
        return {
            "selected_span_id": selected_span_id,
            "selected_span_text": "alpha",
            "choice_words": [
                "alpha",
                "weaken",
                "ignore",
                "delay",
                "worsen",
            ],
            "correct_choice": "alpha",
            "contextual_meaning_ko": "이 문장은 절대 나오면 안 되는 자유서술 설명입니다",
            "supporting_evidence": "Residents say the brighter crosswalks feel safer at night.",
            "explanation": "문맥상 해당 표현의 쓰임이 맞지 않습니다.",
        }


def _extract_locked_corruptible_ids(prompt: str) -> list[str]:
    return re.findall(r"^- (P\d+): ", prompt, re.MULTILINE)


def _extract_locked_answer_span_id(prompt: str) -> str | None:
    match = re.search(r"- Locked answer_span_id: (P\d+)", prompt)
    return match.group(1) if match else None


def _extract_locked_untouched_distractor_id(prompt: str) -> str | None:
    match = re.search(r"- Locked weaker untouched distractor id: (P\d+)", prompt)
    return match.group(1) if match else None


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
        self.phrase_choice_source = (
            "The report carries moral force in this debate. "
            "Repeated exceptions weaken the rule for everyone."
        )

    def test_planner_output_validates(self) -> None:
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: _ValidPlanner(),
        )
        self.assertEqual(result["status"], "planned")
        self.assertIsInstance(result["plan"], SentenceInsertionPlan)

    def test_design_stage_locks_sentence_insertion_bundle(self) -> None:
        state = {
            **self.state,
            "source_paragraph": self.contextual_insertion_source,
            "prepared_source": prepare_source(self.contextual_insertion_source),
            "design": None,
        }
        result = build_design(state, QUESTION_TYPES["sentence_insertion"])
        self.assertEqual(result["status"], "source_passed")
        self.assertEqual(result["design"].target_unit_id, "S2")
        self.assertEqual(result["design"].selected_gap_ids, ["G0", "G1", "G2", "G4", "G5"])

    def test_design_stage_reports_incompatibility_when_no_viable_blank_design_exists(self) -> None:
        state = {
            **self.state,
            "source_paragraph": self.phrase_choice_source,
            "QuestionTypeKey": "fill_in_the_blank",
            "QuestionSubtypeKey": "blank_connective_relation_5_choices",
            "QuestionFormatKey": "blank_connective_relation_5_choices",
            "prepared_source": prepare_source(self.phrase_choice_source),
            "design": None,
        }
        result = build_design(state, QUESTION_SUBTYPE_SPECS["blank_connective_relation_5_choices"])
        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(result["errors"])

    def test_fill_in_the_blank_design_diversifies_or_rejects_weaker_subtypes(self) -> None:
        source = (
            "People often remember the rewards of economic competition and the innovation it can inspire. "
            "Yet when the gains are concentrated in only a few hands, the resulting inequality brought only discontent. "
            "Workers who felt excluded from the benefits became less willing to trust public institutions. "
            "As this distrust spread, even reforms that might have helped were greeted with suspicion. "
            "The lesson is not that ambition should vanish, but that opportunity must be shared widely enough to sustain social peace."
        )
        prepared = prepare_source(source)
        proposition_result = build_design(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "fill_in_the_blank",
                "QuestionSubtypeKey": "blank_inference_proposition_5_choices",
                "QuestionFormatKey": "blank_inference_proposition_5_choices",
                "prepared_source": prepared,
                "design": None,
            },
            QUESTION_TYPES["fill_in_the_blank"],
        )
        summary_result = build_design(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "fill_in_the_blank",
                "QuestionSubtypeKey": "blank_summary_completion_5_choices",
                "QuestionFormatKey": "blank_summary_completion_5_choices",
                "prepared_source": prepared,
                "design": None,
            },
            QUESTION_SUBTYPE_SPECS["blank_summary_completion_5_choices"],
        )
        connective_result = build_design(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "fill_in_the_blank",
                "QuestionSubtypeKey": "blank_connective_relation_5_choices",
                "QuestionFormatKey": "blank_connective_relation_5_choices",
                "prepared_source": prepared,
                "design": None,
            },
            QUESTION_SUBTYPE_SPECS["blank_connective_relation_5_choices"],
        )
        self.assertEqual(proposition_result["status"], "source_passed")
        self.assertEqual(summary_result["status"], "source_passed")
        self.assertNotEqual(
            proposition_result["design"].selected_span_id,
            summary_result["design"].selected_span_id,
        )
        self.assertEqual(connective_result["status"], "qtype_incompatibility_error")

    def test_hydration_preserves_locked_vocab_target(self) -> None:
        prepared = prepare_source(self.mvp_source)
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "vocab",
            "prepared_source": prepared,
            "design": None,
        }
        design_result = build_design(state, QUESTION_TYPES["vocab"])
        design = design_result["design"]
        draft = ContextualVocabChoiceDraft(
            choice_words=["strengthen", "weaken", "ignore", "delay", "worsen"],
            correct_choice="strengthen",
            contextual_meaning_ko="이 자리는 안전을 더 높이는 방향의 표현이 와야 한다는 뜻입니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="문맥상 이 자리는 안전을 더 높이는 방향의 표현이 와야 합니다.",
        )
        plan = hydrate_plan_from_draft(design=design, draft=draft, type_spec=QUESTION_TYPES["vocab"])
        self.assertIsInstance(plan, ContextualVocabChoicePlan)
        self.assertEqual(plan.selected_span_id, design.selected_span_id)
        self.assertEqual(plan.selected_span_text, design.selected_span_text)

    def test_invalid_planner_payload_fails(self) -> None:
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: _InvalidPlanner(),
        )
        self.assertEqual(result["status"], "planning_error")
        self.assertTrue(
            any(
                "SentenceInsertionDraft" in error or "correct_gap_id" in error
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

    def test_planner_timeout_surfaces_readable_planning_error(self) -> None:
        planner = _SleepingPlanner(0.05)
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: planner,
            planner_timeout_seconds=0.01,
        )
        self.assertEqual(result["status"], "planning_error")
        self.assertEqual(planner.invocations, 1)
        self.assertTrue(result["errors"])
        self.assertIn("timed out after 0.0s", result["errors"][0])
        self.assertIn("8-Analysis / sentence_insertion_5_gaps", result["errors"][0])

    def test_planner_retries_once_after_schema_failure(self) -> None:
        planner = _RetryPlanner()
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: planner,
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(planner.invocations, 2)
        self.assertIn("locked design answer", planner.last_prompt)

    def test_planner_retries_after_deterministic_sentence_insertion_failure(self) -> None:
        planner = _DeterministicSentenceRetryPlanner()
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: planner,
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(planner.invocations, 2)
        self.assertIn("locked design answer", planner.last_prompt)

    def test_verbose_planner_logging_reports_start_elapsed_and_finish(self) -> None:
        planner = _SleepingPlanner(0.03)
        logs: list[str] = []
        result = plan_sentence_insertion(
            self.state,
            self.type_spec,
            structured_llm_factory=lambda schema: planner,
            runtime_logger=logs.append,
            planner_timeout_seconds=0.2,
            planner_elapsed_log_interval_seconds=0.01,
        )
        self.assertEqual(result["status"], "planned")
        self.assertTrue(any("attempt 1/2 start (initial)" in message for message in logs))
        self.assertTrue(any("still running after" in message for message in logs))
        self.assertTrue(any("attempt 1/2 finished in" in message for message in logs))

    def test_graph_verbose_logging_marks_stage_boundaries(self) -> None:
        logs: list[str] = []
        runner = compile_question_graph(
            structured_llm_factory=lambda schema: _ValidPlanner(),
            runtime_logger=logs.append,
        )
        result = runner.invoke(self.state)
        self.assertEqual(result["status"], "validation_passed")
        self.assertTrue(any("| input_check start |" in message for message in logs))
        self.assertTrue(any("| planner finish | status=planned" in message for message in logs))
        self.assertTrue(any("| render finish | status=rendered" in message for message in logs))
        self.assertTrue(any("| validate_generated_question finish | status=validation_passed" in message for message in logs))

    def test_sentence_insertion_prompt_exposes_ranked_target_hints(self) -> None:
        prompt = build_sentence_insertion_prompt(
            source_paragraph=self.contextual_insertion_source,
            prepared_source=prepare_source(self.contextual_insertion_source),
            type_spec=QUESTION_TYPES["sentence_insertion"],
        )
        self.assertIn("Locked target sentence", prompt)
        self.assertIn("Locked five-gap bundle", prompt)
        self.assertNotIn("Ranked target candidates", prompt)
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
        self.assertIn("Locked intro block", prompt)
        self.assertIn("Locked continuation blocks in logical order", prompt)
        self.assertIn("Adjacency rationale payload", prompt)
        self.assertNotIn("Boundary hints", prompt)

    def test_graph_ignores_planner_override_of_locked_gap_bundle(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _CollapsedGapPlanner())
        result = runner.invoke(self.state)
        self.assertEqual(result["status"], "validation_passed")

    def test_graph_ignores_planner_override_of_locked_ordering_partition(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _InvalidOrderingCoveragePlanner())
        paragraph_state = {
            **self.state,
            "QuestionTypeKey": "paragraph_ordering",
        }
        result = runner.invoke(paragraph_state)
        self.assertEqual(result["status"], "validation_passed")

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
        self.assertIn("supporting_evidence", planner.last_prompt)

    def test_underlined_phrase_meaning_prompt_exposes_ranked_span_priorities(self) -> None:
        prompt = build_underlined_phrase_meaning_prompt(
            source_paragraph=self.underlined_source,
            prepared_source=self.underlined_prepared,
            type_spec=QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertIn("rank 1", prompt)
        self.assertIn("Locked target span", prompt)
        self.assertNotIn("priority=top", prompt)
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
        self.assertIsInstance(result["plan"], ContextualVocabChoicePlan)

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
        expected_text = vocab_choice_inventory(state["prepared_source"], QUESTION_TYPES["vocab"].subtype_key)[0].text
        self.assertEqual(result["plan"].selected_span_text, expected_text)

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
        best_paraphrase_prompt = build_vocab_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_best_paraphrase_choice_5"],
        )
        with self.assertRaisesRegex(ValueError, "phrase-frame or collocational vocab target"):
            build_vocab_prompt(
                source_paragraph=self.phrase_choice_source,
                prepared_source=prepare_source(self.phrase_choice_source),
                type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_phrase_choice_5"],
            )
        polarity_prompt = build_vocab_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_polarity_scope_5"],
        )
        collocation_prompt = build_vocab_prompt(
            source_paragraph=(
                "Leaders cease wasteful spending during droughts. "
                "Engineers expand storage when demand rises. "
                "Families ignore rumors during emergencies. "
                "Stronger pumps reduce pressure loss across the valley. "
                "Volunteers protect the main channel from damage. "
                "Teachers discuss the results every Friday."
            ),
            prepared_source=prepare_source(
                "Leaders cease wasteful spending during droughts. "
                "Engineers expand storage when demand rises. "
                "Families ignore rumors during emergencies. "
                "Stronger pumps reduce pressure loss across the valley. "
                "Volunteers protect the main channel from damage. "
                "Teachers discuss the results every Friday."
            ),
            type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_collocation_5"],
        )
        grammar_prompt = build_grammar_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_TYPES["grammar"],
        )
        self.assertIn("Locked blank target", blank_prompt)
        self.assertIn("Active subtype: blank_inference_proposition_5_choices", blank_prompt)
        self.assertIn("Locked design facts", blank_prompt)
        self.assertIn("non-identical wording", blank_prompt)
        self.assertIn("Locked target", vocab_prompt)
        self.assertIn("Active subtype: contextual_vocab_choice_5", vocab_prompt)
        self.assertIn("same local slot", vocab_prompt)
        self.assertIn("correct_choice` should be the best contextual fit", vocab_prompt)
        self.assertIn("must be a non-identical best paraphrase", best_paraphrase_prompt)
        self.assertIn("must not appear in `choice_words`", best_paraphrase_prompt)
        self.assertIn("closest lexical restatement", best_paraphrase_prompt)
        self.assertIn("polarity, degree, or scope drift", polarity_prompt)
        self.assertIn("Polarity/scope-eligible subset", polarity_prompt)
        self.assertIn("local phrase-frame or selectional mismatch", collocation_prompt)
        self.assertIn("Locked five-target bundle", grammar_prompt)
        self.assertIn("allowed_variants=", grammar_prompt)
        self.assertIn("real, standard English word", grammar_prompt)
        self.assertNotIn("role=", grammar_prompt)
        self.assertNotIn("preposition[", grammar_prompt)
        self.assertNotIn("conjunction[", grammar_prompt)

    def test_best_paraphrase_design_prefers_content_target_over_grammarish_candidate(self) -> None:
        source = "Residents felt what support meant after the winter drive. Teachers discuss the safety map every week."
        prepared = PreparedSource(
            source_text=source,
            sentence_units=[
                SourceUnit(id="S0", text="Residents felt what support meant after the winter drive.", index=0),
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
                    text="what",
                    normalized_text="what",
                    char_start=source.index("what"),
                    char_end=source.index("what") + len("what"),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="Residents felt ",
                    context_after=" support meant after the winter drive.",
                    heuristic_tags=["single_word", "contextual_cue", "vocab_candidate"],
                    priority_score=9,
                ),
                SpanUnit(
                    id="P1",
                    text="support",
                    normalized_text="support",
                    char_start=source.index("support"),
                    char_end=source.index("support") + len("support"),
                    sentence_unit_id="S0",
                    sentence_index=0,
                    context_before="Residents felt what ",
                    context_after=" meant after the winter drive.",
                    heuristic_tags=["single_word", "abstract_term", "contextual_cue", "vocab_candidate"],
                    priority_score=7,
                ),
            ],
        )
        result = build_design(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "vocab",
                "QuestionSubtypeKey": "contextual_vocab_best_paraphrase_choice_5",
                "QuestionFormatKey": "contextual_vocab_best_paraphrase_choice_5",
                "prepared_source": prepared,
            },
            QUESTION_SUBTYPE_SPECS["contextual_vocab_best_paraphrase_choice_5"],
        )
        self.assertEqual(result["status"], "source_passed")
        self.assertEqual(result["design"].selected_span_id, "P1")

    def test_correct_among_3_prompt_exposes_locked_survivor_pair(self) -> None:
        prepared = prepare_source(self.mvp_source)
        prompt = build_vocab_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_3_corrupted_5"],
        )
        self.assertIn("Locked answer_span_id", prompt)
        self.assertIn("Locked weaker untouched distractor id", prompt)
        self.assertIn("only unchanged pair allowed", prompt)
        self.assertIn("do not invent a second plausible correct item", prompt)

    def test_correct_among_4_prompt_exposes_locked_survivor(self) -> None:
        prepared = prepare_source(self.mvp_source)
        prompt = build_vocab_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
        )
        self.assertIn("Locked answer_span_id", prompt)
        self.assertIn("fixed answer marker", prompt)

    def test_error_1_prompt_exposes_locked_corrupted_target(self) -> None:
        prepared = prepare_source(self.mvp_source)
        prompt = build_vocab_prompt(
            source_paragraph=self.mvp_source,
            prepared_source=prepared,
            type_spec=QUESTION_SUBTYPE_SPECS["contextual_vocab_error_1_among_5_5"],
        )
        self.assertIn("Locked answer_span_id", prompt)
        self.assertIn("that is the one item to corrupt", prompt)

    def test_graph_rewrites_best_paraphrase_explanation_as_non_restoration(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabPlanner())
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "vocab",
            "QuestionSubtypeKey": "contextual_vocab_best_paraphrase_choice_5",
            "QuestionFormatKey": "contextual_vocab_best_paraphrase_choice_5",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = runner.invoke(state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("바꿔 말한 표현", explanation)
        self.assertIn("그대로 복원하는 문제가 아니라", explanation)
        self.assertNotIn("selected_span_id", explanation)

    def test_graph_rewrites_phrase_choice_explanation_as_phrase_level_fit(self) -> None:
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
            explanation="초안입니다.",
        )
        rendered = render_vocab(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "vocab",
                "QuestionSubtypeKey": "contextual_vocab_phrase_choice_5",
                "QuestionFormatKey": "contextual_vocab_phrase_choice_5",
                "prepared_source": prepared,
                "plan": plan,
            },
            QUESTION_SUBTYPE_SPECS["contextual_vocab_phrase_choice_5"],
        )
        context_result = build_explanation_context({**self.state, **rendered, "prepared_source": prepared, "plan": plan, "QuestionTypeKey": "vocab"})
        rewrite_result = write_teacher_facing_explanation({**self.state, **rendered, **context_result, "prepared_source": prepared, "plan": plan, "QuestionTypeKey": "vocab"})
        explanation = rewrite_result["generated"].explanation or ""
        self.assertIn("어구 단위", explanation)
        self.assertIn("어구 결합", explanation)

    def test_graph_rewrites_vocab_explanation_cleans_duplicate_slot_phrase(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        prepared = prepare_source(source)
        selected_span = next(span for span in prepared.span_units if span.text == "improve")
        plan = ContextualVocabChoicePlan(
            subtype="contextual_choice",
            selected_span_id=selected_span.id,
            selected_span_text=selected_span.text,
            choice_words=["strengthen", "weaken", "ignore", "delay", "worsen"],
            correct_choice="strengthen",
            contextual_meaning_ko="이 자리에는 이 자리에는 안전을 더 높이는 방향의 표현이 와야 합니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="초안입니다.",
        )
        rendered = render_vocab(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "vocab",
                "QuestionSubtypeKey": "contextual_vocab_choice_5",
                "QuestionFormatKey": "contextual_vocab_choice_5",
                "prepared_source": prepared,
                "plan": plan,
            },
            QUESTION_SUBTYPE_SPECS["contextual_vocab_choice_5"],
        )
        context_result = build_explanation_context(
            {**self.state, **rendered, "prepared_source": prepared, "plan": plan, "QuestionTypeKey": "vocab"}
        )
        rewrite_result = write_teacher_facing_explanation(
            {**self.state, **rendered, **context_result, "prepared_source": prepared, "plan": plan, "QuestionTypeKey": "vocab"}
        )
        explanation = rewrite_result["generated"].explanation or ""
        self.assertNotIn("이 자리에는 이 자리에는", explanation)
        self.assertFalse(explanation.startswith("'"))

    def test_graph_rewrites_polarity_scope_explanation_with_direction_language(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabPlanner())
        state = {
            **self.state,
            "source_paragraph": (
                "Leaders cease wasteful spending during droughts. "
                "Engineers expand storage when demand rises. "
                "Families ignore rumors during emergencies. "
                "Stronger pumps reduce pressure loss across the valley. "
                "Volunteers protect the main channel from damage. "
                "Teachers discuss the results every Friday."
            ),
            "QuestionTypeKey": "vocab",
            "QuestionSubtypeKey": "contextual_vocab_error_1_among_5_polarity_scope_5",
            "QuestionFormatKey": "contextual_vocab_error_1_among_5_polarity_scope_5",
            "prepared_source": prepare_source(
                "Leaders cease wasteful spending during droughts. "
                "Engineers expand storage when demand rises. "
                "Families ignore rumors during emergencies. "
                "Stronger pumps reduce pressure loss across the valley. "
                "Volunteers protect the main channel from damage. "
                "Teachers discuss the results every Friday."
            ),
        }
        result = runner.invoke(state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("방향, 정도, 또는 적용 범위", explanation)

    def test_graph_rewrites_collocation_explanation_with_natural_combination_language(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabPlanner())
        state = {
            **self.state,
            "source_paragraph": (
                "Leaders cease wasteful spending during droughts. "
                "Engineers expand storage when demand rises. "
                "Families ignore rumors during emergencies. "
                "Stronger pumps reduce pressure loss across the valley. "
                "Volunteers protect the main channel from damage. "
                "Teachers discuss the results every Friday."
            ),
            "QuestionTypeKey": "vocab",
            "QuestionSubtypeKey": "contextual_vocab_error_1_among_5_collocation_5",
            "QuestionFormatKey": "contextual_vocab_error_1_among_5_collocation_5",
            "prepared_source": prepare_source(
                "Leaders cease wasteful spending during droughts. "
                "Engineers expand storage when demand rises. "
                "Families ignore rumors during emergencies. "
                "Stronger pumps reduce pressure loss across the valley. "
                "Volunteers protect the main channel from damage. "
                "Teachers discuss the results every Friday."
            ),
        }
        result = runner.invoke(state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("자연스럽게 결합", explanation)

    def test_underlined_vocab_explanation_uses_rendered_source_order_marker(self) -> None:
        source = (
            "People's happiness depends on relative wealth. "
            "Workers compare salaries with peers. "
            "Inequality often brings discontent. "
            "Satisfied employees stay longer. "
            "Calmer teams cooperate better. "
            "Managers review the pattern each year."
        )
        prepared = prepare_source(source)
        span_map = {span.text: span for span in prepared.span_units}
        targets = [
            span_map["happiness"],
            span_map["wealth"],
            span_map["Inequality"],
            span_map["discontent"],
            span_map["Satisfied"],
        ]
        answer_span = span_map["Inequality"]
        plan = UnderlinedVocabPlan(
            subtype="contextual_correct_among_4_corrupted",
            target_span_ids=[targets[2].id, targets[0].id, targets[4].id, targets[1].id, targets[3].id],
            target_span_texts=[targets[2].text, targets[0].text, targets[4].text, targets[1].text, targets[3].text],
            corrupted_replacements=[
                {"span_id": targets[0].id, "replacement_text": "productivity"},
                {"span_id": targets[1].id, "replacement_text": "education"},
                {"span_id": targets[3].id, "replacement_text": "contentment"},
                {"span_id": targets[4].id, "replacement_text": "restless"},
            ],
            answer_span_id=answer_span.id,
            selection_basis_ko="이 자리만 원래 맥락의 의미를 자연스럽게 유지합니다",
            supporting_evidence="Inequality often brings discontent.",
            explanation="초안입니다.",
        )
        design = UnderlinedVocabDesign(
            family_key="vocab",
            subtype_key="contextual_vocab_correct_among_4_corrupted_5",
            subtype="contextual_correct_among_4_corrupted",
            target_span_ids=plan.target_span_ids,
            target_span_texts=plan.target_span_texts,
            answer_span_id=plan.answer_span_id,
        )
        rendered = render_vocab(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "vocab",
                "QuestionSubtypeKey": "contextual_vocab_correct_among_4_corrupted_5",
                "QuestionFormatKey": "contextual_vocab_correct_among_4_corrupted_5",
                "prepared_source": prepared,
                "plan": plan,
            },
            QUESTION_SUBTYPE_SPECS["contextual_vocab_correct_among_4_corrupted_5"],
        )
        self.assertEqual(rendered["generated"].answer, "③")
        context_result = build_explanation_context(
            {
                **self.state,
                **rendered,
                "prepared_source": prepared,
                "plan": plan,
                "design": design,
                "QuestionTypeKey": "vocab",
            }
        )
        rewrite_result = write_teacher_facing_explanation(
            {
                **self.state,
                **rendered,
                **context_result,
                "prepared_source": prepared,
                "plan": plan,
                "design": design,
                "QuestionTypeKey": "vocab",
            }
        )
        explanation = rewrite_result["generated"].explanation or ""
        self.assertIn("따라서 ③의'Inequality'만 문맥을 유지하고", explanation)
        self.assertNotIn("따라서 ①의'Inequality'", explanation)

    def test_grammar_explanation_uses_rendered_source_order_marker(self) -> None:
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
        span_map = {span.text.lower(): span for span in inventory}
        targets = [
            span_map["testing"],
            span_map["reduce"],
            span_map["expand"],
            span_map["show"],
            span_map["raising"],
        ]
        corrupted_span = span_map["show"]
        plan = GrammarPlan(
            subtype="verb_form",
            target_span_ids=[targets[3].id, targets[1].id, targets[4].id, targets[0].id, targets[2].id],
            target_span_texts=[targets[3].text, targets[1].text, targets[4].text, targets[0].text, targets[2].text],
            corrupted_span_id=corrupted_span.id,
            corrupted_word="showed",
            correction_basis_ko="이 자리는 조동사 뒤이므로 동사원형이 유지되어야 합니다",
            supporting_evidence="The mayor hopes to show that the project saves money over time.",
            explanation="초안입니다.",
        )
        design = GrammarDesign(
            family_key="grammar",
            subtype_key="grammar_error_verb_form_5",
            subtype="verb_form",
            target_span_ids=plan.target_span_ids,
            target_span_texts=plan.target_span_texts,
            corrupted_span_id=plan.corrupted_span_id,
            prompt_payload={},
        )
        rendered = render_grammar(
            {
                **self.state,
                "source_paragraph": source,
                "QuestionTypeKey": "grammar",
                "QuestionSubtypeKey": "grammar_error_verb_form_5",
                "QuestionFormatKey": "grammar_error_verb_form_5",
                "prepared_source": prepared,
                "plan": plan,
            },
            QUESTION_SUBTYPE_SPECS["grammar_error_verb_form_5"],
        )
        self.assertEqual(rendered["generated"].answer, "⑤")
        context_result = build_explanation_context(
            {
                **self.state,
                **rendered,
                "prepared_source": prepared,
                "plan": plan,
                "design": design,
                "QuestionTypeKey": "grammar",
            }
        )
        rewrite_result = write_teacher_facing_explanation(
            {
                **self.state,
                **rendered,
                **context_result,
                "prepared_source": prepared,
                "plan": plan,
                "design": design,
                "QuestionTypeKey": "grammar",
            }
        )
        explanation = rewrite_result["generated"].explanation or ""
        self.assertIn("따라서 ⑤의'showed'는 맞지 않고", explanation)
        self.assertNotIn("따라서 ①의'showed'는 맞지 않고", explanation)

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
        self.assertTrue(explanation.startswith("문맥상"))
        self.assertIn("brighter crosswalks feel safer", explanation)
        self.assertIn("다른 선택지들은", explanation)
        self.assertFalse(explanation.startswith("'"))
        self.assertNotIn("그 방향을 뒷받침", explanation)
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
        self.assertNotIn("그 구조를 보여 주므로", explanation)
        self.assertNotIn("자유서술 문법 해설", explanation)

    def test_graph_rewrites_fill_explanation_as_teacher_facing_note(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _FillInTheBlankPlanner())
        state = {
            **self.state,
            "source_paragraph": self.mvp_source,
            "QuestionTypeKey": "fill_in_the_blank",
            "prepared_source": prepare_source(self.mvp_source),
        }
        result = runner.invoke(state)
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("핵심 단서", explanation)
        self.assertNotIn("라는 의미라는 의미", explanation)


if __name__ == "__main__":
    unittest.main()
