from __future__ import annotations

import csv
import json
import re
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from questiongen.batch import BatchProgressUpdate, run_batch_dataframe, run_batch_files, run_batch_rows
from questiongen.console_progress import ConsoleProgressRenderer, chain_progress_callbacks
from questiongen.graph import compile_question_graph
from questiongen.parsers import prepare_source
from questiongen.planners import PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR, PLANNER_QUOTA_EXHAUSTED_ERROR
from questiongen.schemas import (
    BatchInputRow,
    ContextualVocabChoiceDraft,
    ContextualVocabChoicePlan,
    FillInTheBlankDraft,
    FillInTheBlankPlan,
    GrammarDraft,
    GrammarPlan,
    ParagraphOrderingDraft,
    ParagraphOrderingPlan,
    SentenceInsertionDraft,
    SentenceInsertionPlan,
    UnderlinedVocabDraft,
    UnderlinedVocabPlan,
    UnderlinedPhraseMeaningDraft,
    UnderlinedPhraseMeaningPlan,
    VocabPlan,
)
from questiongen.targeting import allowed_verb_form_variants


class _StubPlanner:
    def __init__(
        self,
        output_schema: type[
            SentenceInsertionPlan
            | SentenceInsertionDraft
            | ParagraphOrderingPlan
            | ParagraphOrderingDraft
            | UnderlinedPhraseMeaningPlan
            | UnderlinedPhraseMeaningDraft
            | FillInTheBlankPlan
            | FillInTheBlankDraft
            | ContextualVocabChoicePlan
            | ContextualVocabChoiceDraft
            | UnderlinedVocabPlan
            | UnderlinedVocabDraft
            | VocabPlan
            | GrammarPlan
            | GrammarDraft
        ],
    ) -> None:
        self.output_schema = output_schema

    def invoke(
        self, prompt: str
    ) -> (
        SentenceInsertionPlan
        | SentenceInsertionDraft
        | ParagraphOrderingPlan
        | ParagraphOrderingDraft
        | UnderlinedPhraseMeaningPlan
        | UnderlinedPhraseMeaningDraft
        | FillInTheBlankPlan
        | FillInTheBlankDraft
        | ContextualVocabChoicePlan
        | ContextualVocabChoiceDraft
        | UnderlinedVocabPlan
        | UnderlinedVocabDraft
        | VocabPlan
        | GrammarPlan
        | GrammarDraft
    ):
        if self.output_schema.__name__ == "PlannerSemanticAdjudicationResult":
            return self.output_schema(
                fits_discourse_role=True,
                visible_frame_semantically_valid=True,
                failure_reason=None,
            )
        if self.output_schema in {SentenceInsertionPlan, SentenceInsertionDraft}:
            return self.output_schema(
                target_unit_ids=["S2"],
                selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
                correct_gap_id="G2",
                explanation="문장 S2는 G2 위치에 들어가야 자연스럽습니다.",
            )
        if self.output_schema in {ParagraphOrderingPlan, ParagraphOrderingDraft}:
            sentence_ids = re.findall(r"- (S\d+): text=", prompt)
            return self.output_schema(
                intro_unit_ids=[sentence_ids[0]],
                continuation_blocks=[
                    sentence_ids[1:3],
                    sentence_ids[3:5],
                    sentence_ids[5:],
                ],
                explanation="도입부 다음에 원인과 결과가 이어지는 흐름입니다.",
            )
        if self.output_schema in {FillInTheBlankPlan, FillInTheBlankDraft}:
            match = re.search(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)
            selected_span_id = match.group(1) if match else "P0"
            selected_span_text = match.group(2) if match else "less electricity than the older"
            subtype_match = re.search(r"Active subtype: ([A-Za-z0-9_]+)", prompt)
            active_subtype = subtype_match.group(1) if subtype_match else "blank_inference_proposition_5_choices"
            if active_subtype == "blank_connective_relation_5_choices":
                return self.output_schema(
                    subtype="connective_relation",
                    selected_span_id=selected_span_id,
                    selected_span_text=selected_span_text,
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
                return self.output_schema(
                    subtype="summary_completion",
                    selected_span_id=selected_span_id,
                    selected_span_text=selected_span_text,
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
            return self.output_schema(
                subtype="proposition_inference",
                selected_span_id=selected_span_id,
                selected_span_text=selected_span_text,
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
        if self.output_schema in {ContextualVocabChoicePlan, ContextualVocabChoiceDraft}:
            match = re.search(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)
            selected_span_id = match.group(1) if match else "P0"
            selected_span_text = match.group(2) if match else "improve"
            subtype_match = re.search(r"Active subtype: ([A-Za-z0-9_]+)", prompt)
            active_subtype = subtype_match.group(1) if subtype_match else ""
            if active_subtype == "contextual_vocab_best_paraphrase_choice_5":
                return self.output_schema(
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
                    explanation="문맥상 안전을 더 높이는 방향의 바꿔쓰기가 와야 합니다.",
                )
            if active_subtype == "contextual_vocab_phrase_choice_5":
                return self.output_schema(
                    subtype="contextual_phrase_choice",
                    selected_span_id=selected_span_id,
                    selected_span_text=selected_span_text,
                    choice_words=[
                        selected_span_text,
                        "higher safety risks",
                        "slower repair cycles",
                        "narrow budget pressure",
                        "weaker public trust",
                    ],
                    correct_choice=selected_span_text,
                    contextual_meaning_ko="이 자리는 안전 향상과 비용 유지라는 핵심 효과를 함께 담는 어구가 와야 합니다",
                    supporting_evidence="Because the lights use less electricity, the city can improve safety without raising its energy budget.",
                    explanation="문맥상 안전 향상과 비용 유지라는 핵심 효과를 함께 담는 어구가 와야 합니다.",
                )
            return self.output_schema(
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
        if self.output_schema in {UnderlinedVocabPlan, UnderlinedVocabDraft}:
            targets = _extract_ranked_lexical_targets(prompt)
            target_ids, target_texts = zip(*targets[:5])
            target_text_by_id = dict(zip(target_ids, target_texts, strict=False))
            locked_corruptible_ids = _extract_locked_corruptible_ids(prompt)
            locked_answer_id = _extract_locked_answer_span_id(prompt)
            locked_untouched_id = _extract_locked_untouched_distractor_id(prompt)
            subtype_match = re.search(r"Active subtype: ([A-Za-z0-9_]+)", prompt)
            active_subtype = subtype_match.group(1) if subtype_match else ""
            subtype = (
                "contextual_correct_among_4_corrupted"
                if active_subtype == "contextual_vocab_correct_among_4_corrupted_5"
                else "contextual_error_1_among_5"
                if active_subtype == "contextual_vocab_error_1_among_5_5"
                else "contextual_error_1_among_5_polarity_scope"
                if active_subtype == "contextual_vocab_error_1_among_5_polarity_scope_5"
                else "contextual_error_1_among_5_collocation"
                if active_subtype == "contextual_vocab_error_1_among_5_collocation_5"
                else "contextual_correct_among_3_corrupted"
            )
            if subtype == "contextual_correct_among_4_corrupted":
                answer_span_id = locked_answer_id or target_ids[1]
                replacements = {
                    span_id: replacement
                    for span_id, replacement in zip(
                        [span_id for span_id in target_ids if span_id != answer_span_id],
                        ["weaken", "ignore", "delay", "worsen"],
                        strict=False,
                    )
                }
            elif subtype == "contextual_error_1_among_5":
                answer_span_id = locked_answer_id or target_ids[2]
                replacements = {answer_span_id: "ignore"}
            elif subtype == "contextual_error_1_among_5_polarity_scope":
                polarity_target_id = locked_corruptible_ids[0] if locked_corruptible_ids else target_ids[0]
                polarity_text = target_text_by_id[polarity_target_id]
                if polarity_text == "cease":
                    polarity_replacement = "continue"
                elif polarity_text == "expand":
                    polarity_replacement = "reduce"
                elif polarity_text == "less":
                    polarity_replacement = "more"
                else:
                    polarity_replacement = "never"
                replacements = {polarity_target_id: polarity_replacement}
                answer_span_id = polarity_target_id
            elif subtype == "contextual_error_1_among_5_collocation":
                collocation_target_id = locked_answer_id or (
                    locked_corruptible_ids[0] if locked_corruptible_ids else (
                    target_ids[target_texts.index("ignore")] if "ignore" in target_texts else target_ids[-1]
                    )
                )
                replacements = {collocation_target_id: "collect"}
                answer_span_id = collocation_target_id
            else:
                answer_span_id = locked_answer_id or target_ids[1]
                untouched_id = locked_untouched_id or target_ids[0]
                replacements = {
                    span_id: replacement
                    for span_id, replacement in zip(
                        [span_id for span_id in target_ids if span_id not in {answer_span_id, untouched_id}],
                        ["weaken", "delay", "worsen"],
                        strict=False,
                    )
                }
            return self.output_schema(
                subtype=subtype,
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_replacements=[
                    {"span_id": span_id, "replacement_text": replacement_text}
                    for span_id, replacement_text in replacements.items()
                ],
                answer_span_id=answer_span_id,
                selection_basis_ko="문맥상 주민 안전을 높이는 원래 기능을 가장 자연스럽게 유지하는 표현이어야 합니다",
                supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
                explanation="문맥상 정답만 원래 의미를 유지하고 나머지는 의미를 비틀고 있습니다.",
            )
        if self.output_schema in {GrammarPlan, GrammarDraft}:
            targets = _extract_ranked_single_word_targets(prompt)
            target_ids, target_texts = zip(*targets[:5])
            original_word = target_texts[1]
            replacement = next(iter(sorted(allowed_verb_form_variants(original_word) - {original_word.lower()})))
            return self.output_schema(
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_span_id=target_ids[1],
                corrupted_word=replacement,
                correction_basis_ko="이 자리에는 주변 구조에 맞는 원래의 동사 형태가 필요합니다",
                supporting_evidence="Officials now plan to expand the same lighting system to nearby neighborhoods.",
                explanation="문맥상 이 자리의 동사 형태가 구조와 맞지 않습니다.",
            )
        match = re.search(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)
        selected_span_id = match.group(1) if match else "P0"
        selected_span_text = match.group(2) if match else "one end of the spectrum"
        return self.output_schema(
            selected_span_id=selected_span_id,
            selected_span_text=selected_span_text,
            paraphrase_choices_ko=[
                "글의 핵심 판단이나 설명을 보여 주는 표현이라는 뜻",
                "단순한 시간 순서만 알려 주는 표현이라는 뜻",
                "주변 사례를 무작위로 나열한 표현이라는 뜻",
                "문맥과 무관한 고유명사만 강조한 표현이라는 뜻",
                "반대 의미를 직접적으로 확정한 표현이라는 뜻",
            ],
            correct_choice="글의 핵심 판단이나 설명을 보여 주는 표현이라는 뜻",
            surface_meaning="해당 영어 표현의 표면적 wording",
            contextual_meaning="글의 흐름에서 핵심 판단이나 설명을 드러내는 뜻",
            supporting_evidence=selected_span_text,
            explanation="문맥상 이 표현은 글의 핵심 판단이나 설명을 보여 줍니다.",
        )


_HARD_GENERIC_REPLACEMENTS = {
    "ability": "inability",
    "actually": "barely",
    "cease": "continue",
    "complex": "simple",
    "composed": "copied",
    "destroy": "preserve",
    "expand": "reduce",
    "happiness": "misery",
    "heated": "calm",
    "improve": "weaken",
    "inequity": "fairness",
    "necessary": "optional",
    "open": "close",
    "possible": "impossible",
    "protect": "damage",
    "reduce": "increase",
    "sacrosanct": "negotiable",
}

_HARD_POLARITY_REPLACEMENTS = {
    "actually": "barely",
    "cease": "continue",
    "expand": "reduce",
    "improve": "weaken",
    "less": "more",
    "necessary": "optional",
    "open": "close",
    "possible": "impossible",
    "protect": "damage",
    "reduce": "increase",
}

_HARD_COLLOCATION_REPLACEMENTS = {
    "ability": "machinery",
    "acknowledged": "collect",
    "complex": "wooden",
    "composed": "collect",
    "destroy": "collect",
    "expand": "collect",
    "happiness": "machinery",
    "heated": "wooden",
    "ignore": "collect",
    "improve": "collect",
    "inequity": "machinery",
    "necessary": "wooden",
    "open": "wooden",
    "possible": "wooden",
    "protect": "collect",
    "reduce": "collect",
}

_HARD_GENERIC_FALLBACKS = {
    1: ["distort", "worsen", "narrow", "fragile", "static"],
    2: ["far weaker", "less stable", "more narrow", "deeply fragile"],
    3: ["far less stable", "much more narrow", "markedly less coherent"],
}

_HARD_POLARITY_FALLBACKS = {
    1: ["less", "more", "never", "always"],
    2: ["far less", "far more", "not fully", "only partly"],
    3: ["much less often", "far more often", "not at all"],
}

_HARD_COLLOCATION_FALLBACKS = {
    1: ["wooden", "metallic", "machinery", "textile"],
    2: ["wooden signal", "metallic belief", "textile judgment"],
    3: ["wooden social signal", "metallic moral judgment"],
}


class _HardVocabAuditPlanner:
    def __init__(self, output_schema: type[UnderlinedVocabPlan | UnderlinedVocabDraft]) -> None:
        self.output_schema = output_schema

    def invoke(self, prompt: str) -> UnderlinedVocabPlan | UnderlinedVocabDraft:
        target_infos = _extract_ranked_lexical_target_infos(prompt)[:5]
        target_ids = tuple(info["span_id"] for info in target_infos)
        target_texts = tuple(info["text"] for info in target_infos)
        locked_corruptible_ids = _extract_locked_corruptible_ids(prompt)
        locked_answer_id = _extract_locked_answer_span_id(prompt)
        locked_untouched_id = _extract_locked_untouched_distractor_id(prompt)
        subtype_match = re.search(r"Active subtype: ([A-Za-z0-9_]+)", prompt)
        active_subtype = subtype_match.group(1) if subtype_match else ""

        if active_subtype == "contextual_vocab_error_1_among_5_polarity_scope_5":
            corruption_index, replacement_text = self._pick_first_replacement(
                tuple(
                    info["text"]
                    for info in target_infos
                    if not locked_corruptible_ids or info["span_id"] in set(locked_corruptible_ids)
                ),
                _HARD_POLARITY_REPLACEMENTS,
                _HARD_POLARITY_FALLBACKS,
                fallback="more",
            )
            eligible_infos = [
                info for info in target_infos if not locked_corruptible_ids or info["span_id"] in set(locked_corruptible_ids)
            ]
            corruption_target_id = str(eligible_infos[corruption_index]["span_id"])
            subtype = "contextual_error_1_among_5_polarity_scope"
            replacements = [
                {"span_id": corruption_target_id, "replacement_text": replacement_text},
            ]
            answer_span_id = corruption_target_id
            selection_basis_ko = "문맥상 원래 표현의 방향이나 정도가 유지되어야 합니다"
        elif active_subtype == "contextual_vocab_error_1_among_5_collocation_5":
            corruption_index, replacement_text = self._pick_first_replacement(
                tuple(
                    info["text"]
                    for info in target_infos
                    if not locked_corruptible_ids or info["span_id"] in set(locked_corruptible_ids)
                ),
                _HARD_COLLOCATION_REPLACEMENTS,
                _HARD_COLLOCATION_FALLBACKS,
                fallback="collect",
            )
            eligible_infos = [
                info for info in target_infos if not locked_corruptible_ids or info["span_id"] in set(locked_corruptible_ids)
            ]
            corruption_target_id = locked_answer_id or str(eligible_infos[corruption_index]["span_id"])
            subtype = "contextual_error_1_among_5_collocation"
            replacements = [
                {"span_id": corruption_target_id, "replacement_text": replacement_text},
            ]
            answer_span_id = corruption_target_id
            selection_basis_ko = "문맥상 이 자리는 자연스러운 어휘 결합이 유지되어야 합니다"
        elif active_subtype == "contextual_vocab_error_1_among_5_5":
            corruption_index, replacement_text = self._pick_first_replacement(
                target_texts,
                _HARD_GENERIC_REPLACEMENTS,
                _HARD_GENERIC_FALLBACKS,
                fallback="worsen",
            )
            subtype = "contextual_error_1_among_5"
            corruption_target_id = locked_answer_id or target_ids[corruption_index]
            replacements = [
                {"span_id": corruption_target_id, "replacement_text": replacement_text},
            ]
            answer_span_id = corruption_target_id
            selection_basis_ko = "문맥상 원래 표현만 글의 핵심 의미를 유지합니다"
        elif active_subtype == "contextual_vocab_correct_among_3_corrupted_5":
            subtype = "contextual_correct_among_3_corrupted"
            if locked_answer_id is not None and locked_untouched_id is not None:
                answer_index = target_ids.index(locked_answer_id)
                untouched_index = target_ids.index(locked_untouched_id)
            else:
                answer_index, untouched_index = self._pick_strongest_and_weakest_indices(target_infos)
            used_replacements: list[str] = []
            replacements = [
                {
                    "span_id": target_ids[index],
                    "replacement_text": self._replacement_for(
                        target_texts[index],
                        target_texts,
                        used_replacements,
                        _HARD_GENERIC_REPLACEMENTS,
                        _HARD_GENERIC_FALLBACKS,
                        fallback="worsen",
                    ),
                }
                for index in range(len(target_ids))
                if index not in {answer_index, untouched_index}
            ]
            answer_span_id = target_ids[answer_index]
            selection_basis_ko = "문맥상 정답 표현만 가장 강하게 원래 의미를 유지합니다"
        else:
            subtype = "contextual_correct_among_4_corrupted"
            used_replacements = []
            answer_span_id = locked_answer_id or target_ids[0]
            replacements = [
                {
                    "span_id": target_ids[index],
                    "replacement_text": self._replacement_for(
                        target_texts[index],
                        target_texts,
                        used_replacements,
                        _HARD_GENERIC_REPLACEMENTS,
                        _HARD_GENERIC_FALLBACKS,
                        fallback="worsen",
                    ),
                }
                for index in range(len(target_ids))
                if target_ids[index] != answer_span_id
            ]
            selection_basis_ko = "문맥상 정답 표현만 원래 의미를 자연스럽게 유지합니다"

        return self.output_schema(
            subtype=subtype,
            target_span_ids=list(target_ids),
            target_span_texts=list(target_texts),
            corrupted_replacements=replacements,
            answer_span_id=answer_span_id,
            selection_basis_ko=selection_basis_ko,
            supporting_evidence=target_texts[0],
            explanation="문맥상 정답과 오답의 의미 차이를 구분해야 합니다.",
        )

    @staticmethod
    def _replacement_for(
        text: str,
        target_texts: tuple[str, ...],
        used_replacements: list[str],
        replacements: dict[str, str],
        fallback_replacements: dict[int, list[str]],
        *,
        fallback: str,
    ) -> str:
        token_count = len(text.split())
        taken = {_normalize_lexical_text(target_text) for target_text in target_texts}
        taken.update(_normalize_lexical_text(replacement) for replacement in used_replacements)
        candidates: list[str] = []
        mapped = replacements.get(text.lower())
        if mapped is not None:
            candidates.append(mapped)
        candidates.extend(fallback_replacements.get(token_count, []))
        candidates.append(fallback)
        for candidate in candidates:
            if _normalize_lexical_text(candidate) not in taken:
                used_replacements.append(candidate)
                return candidate
        used_replacements.append(fallback)
        return fallback

    @classmethod
    def _pick_first_replacement(
        cls,
        target_texts: tuple[str, ...],
        replacements: dict[str, str],
        fallback_replacements: dict[int, list[str]],
        *,
        fallback: str,
    ) -> tuple[int, str]:
        used_replacements: list[str] = []
        for index, text in enumerate(target_texts):
            replacement = cls._replacement_for(
                text,
                target_texts,
                used_replacements,
                replacements,
                fallback_replacements,
                fallback=fallback,
            )
            if replacement:
                return index, replacement
        return 0, fallback

    @staticmethod
    def _pick_strongest_and_weakest_indices(target_infos: list[dict[str, int | str]]) -> tuple[int, int]:
        ranked = sorted(
            range(len(target_infos)),
            key=lambda index: (
                int(target_infos[index]["cues"]),
                int(target_infos[index]["score"]),
                -index,
            ),
            reverse=True,
        )
        answer_index = ranked[0]
        weakest_ranked = sorted(
            (index for index in range(len(target_infos)) if index != answer_index),
            key=lambda index: (
                int(target_infos[index]["cues"]),
                int(target_infos[index]["score"]),
                index,
            ),
        )
        return answer_index, weakest_ranked[0]


def _extract_ranked_single_word_targets(prompt: str) -> list[tuple[str, str]]:
    return re.findall(r"- rank \d+: (P\d+); score=\d+; text='([A-Za-z]+)'", prompt)


def _extract_ranked_lexical_targets(prompt: str) -> list[tuple[str, str]]:
    return re.findall(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)


def _extract_ranked_lexical_target_infos(prompt: str) -> list[dict[str, int | str]]:
    return [
        {
            "span_id": span_id,
            "score": int(score),
            "cues": int(cues),
            "text": text,
        }
        for span_id, score, cues, text in re.findall(
            r"- rank \d+: (P\d+); score=(\d+); cues=(\d+); .*text='([^']+)'",
            prompt,
        )
    ]


def _extract_locked_corruptible_ids(prompt: str) -> list[str]:
    return re.findall(r"^- (P\d+): ", prompt, re.MULTILINE)


def _extract_locked_answer_span_id(prompt: str) -> str | None:
    match = re.search(r"- Locked answer_span_id: (P\d+)", prompt)
    return match.group(1) if match else None


def _extract_locked_untouched_distractor_id(prompt: str) -> str | None:
    match = re.search(r"- Locked weaker untouched distractor id: (P\d+)", prompt)
    return match.group(1) if match else None


def _normalize_lexical_text(text: str) -> str:
    return " ".join(text.lower().split())


class _FailingRunner:
    def invoke(self, state):
        raise RuntimeError("boom")


class _IncompatibleRunner:
    def invoke(self, state):
        return {
            **state,
            "status": "qtype_incompatibility_error",
            "errors": ["Passage is not suitable for this question type."],
        }


class _QuotaThenUnexpectedRunner:
    def __init__(self) -> None:
        self.invocations = 0

    def invoke(self, state):
        self.invocations += 1
        if self.invocations == 1:
            return {
                **state,
                "status": "planning_error",
                "errors": [PLANNER_QUOTA_EXHAUSTED_ERROR],
            }
        return {
            **state,
            "status": "validation_passed",
            "errors": ["runner should not have been invoked again"],
        }


class _NonQuotaPlanningErrorRunner:
    def __init__(self) -> None:
        self.invocations = 0

    def invoke(self, state):
        self.invocations += 1
        return {
            **state,
            "status": "planning_error",
            "errors": [f"Planner failed: schema mismatch on call {self.invocations}"],
        }


class BatchTests(unittest.TestCase):
    _HARD_VOCAB_REAUDIT_SCENARIOS = [
        {
            "row": BatchInputRow(
                OriginalQuestionNumber="VOC-HARD-01",
                BatchRowId=0,
                source_paragraph=(
                    "City planners recently tested brighter LED lights on several downtown blocks. "
                    "The new lights make crosswalks easier to see after sunset. "
                    "They also use less electricity than the older lights. "
                    "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
                    "Residents say the brighter crosswalks feel safer at night. "
                    "Officials now plan to expand the same lighting system to nearby neighborhoods."
                ),
            ),
            "subtypes": [
                "contextual_vocab_correct_among_4_corrupted_5",
                "contextual_vocab_error_1_among_5_5",
                "contextual_vocab_error_1_among_5_polarity_scope_5",
                "contextual_vocab_correct_among_3_corrupted_5",
            ],
        },
        {
            "row": BatchInputRow(
                OriginalQuestionNumber="VOC-HARD-02",
                BatchRowId=1,
                source_paragraph=(
                    "Volunteers collect medical supplies before each storm. "
                    "Nurses protect emergency access around the clinic. "
                    "Drivers reduce speed near the narrow bridge. "
                    "Teachers improve safety drills during the winter term. "
                    "Engineers expand backup power for the shelter. "
                    "Families open extra rooms for displaced neighbors."
                ),
            ),
            "subtypes": [
                "contextual_vocab_error_1_among_5_collocation_5",
            ],
        },
    ]

    @staticmethod
    def _load_fixture_row(question_number: str) -> BatchInputRow:
        fixture_path = Path(__file__).resolve().parents[1] / "sample_data" / "sample_question.csv"
        with fixture_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["OriginalQuestionNumber"] == question_number:
                    return BatchInputRow(
                        OriginalQuestionNumber=row["OriginalQuestionNumber"],
                        BatchRowId=0,
                        source_paragraph=row["source_paragraph"],
                    )
        raise AssertionError(f"Fixture row {question_number} was not found in {fixture_path}.")

    def setUp(self) -> None:
        self.runner = compile_question_graph(
            structured_llm_factory=lambda schema, model_role="default": _StubPlanner(schema)
        )
        self.rows = [BatchInputRow(OriginalQuestionNumber="8-Analysis", BatchRowId=0, source_paragraph="A. B. C. D. E. F.")]
        self.mixed_family_row = BatchInputRow(
            OriginalQuestionNumber="MVP-01",
            BatchRowId=0,
            source_paragraph=(
                "City planners recently tested brighter LED lights on several downtown blocks. "
                "The new lights make crosswalks easier to see after sunset. "
                "They also use less electricity than the older lights. "
                "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
                "Residents say the brighter crosswalks feel safer at night. "
                "Officials now plan to expand the same lighting system to nearby neighborhoods."
            ),
        )

    def test_one_row_one_type(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], self.runner)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "validation_passed")
        self.assertNotIn("S2", results[0].explanation or "")
        self.assertNotIn("G2", results[0].explanation or "")

    def test_one_row_multiple_types(self) -> None:
        mixed_rows = [self.mixed_family_row]
        results = run_batch_rows(
            mixed_rows,
            [
                "sentence_insertion",
                "paragraph_ordering",
                "underlined_phrase_meaning",
                "fill_in_the_blank",
                "vocab",
                "grammar",
                "unknown_type",
            ],
            self.runner,
        )
        self.assertEqual(len(results), 23)
        by_subtype = {result.QuestionSubtypeKey: result for result in results}
        self.assertEqual(by_subtype["sentence_insertion_5_gaps"].status, "validation_passed")
        self.assertEqual(by_subtype["abc_ordering_after_intro"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["underlined_phrase_meaning_5_ko"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["blank_inference_proposition_5_choices"].status, "validation_passed")
        self.assertEqual(by_subtype["blank_connective_relation_5_choices"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["blank_summary_completion_5_choices"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["contextual_vocab_choice_5"].status, "validation_passed")
        self.assertEqual(by_subtype["contextual_vocab_best_paraphrase_choice_5"].status, "validation_passed")
        self.assertEqual(by_subtype["contextual_vocab_phrase_choice_5"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["contextual_vocab_correct_among_4_corrupted_5"].status, "validation_passed")
        self.assertEqual(by_subtype["contextual_vocab_error_1_among_5_5"].status, "validation_passed")
        self.assertEqual(by_subtype["contextual_vocab_error_1_among_5_polarity_scope_5"].status, "validation_passed")
        self.assertEqual(by_subtype["contextual_vocab_error_1_among_5_collocation_5"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["contextual_vocab_correct_among_3_corrupted_5"].status, "validation_passed")
        self.assertEqual(by_subtype["grammar_error_verb_form_5"].status, "validation_passed")
        self.assertEqual(by_subtype["grammar_error_subject_verb_agreement_5"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["grammar_error_finite_nonfinite_5"].status, "validation_passed")
        self.assertEqual(results[-1].status, "input_error")

    def test_fill_blank_weak_subtypes_surface_as_qtype_incompatibility(self) -> None:
        results = run_batch_rows([self.mixed_family_row], ["fill_in_the_blank"], self.runner)
        by_subtype = {result.QuestionSubtypeKey: result for result in results}
        self.assertEqual(by_subtype["blank_inference_proposition_5_choices"].status, "validation_passed")
        self.assertEqual(by_subtype["blank_connective_relation_5_choices"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["blank_summary_completion_5_choices"].status, "qtype_incompatibility_error")
        self.assertNotEqual(by_subtype["blank_connective_relation_5_choices"].status, "planning_error")
        self.assertNotEqual(by_subtype["blank_summary_completion_5_choices"].status, "planning_error")

    def test_per_row_failure_is_captured(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], _FailingRunner())
        self.assertEqual(results[0].status, "planning_error")
        self.assertTrue(results[0].errors)

    def test_qtype_incompatibility_is_preserved(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], _IncompatibleRunner())
        self.assertEqual(results[0].status, "qtype_incompatibility_error")
        self.assertTrue(any("not suitable" in error for error in results[0].errors))

    def test_vocab_hardening_rejections_surface_as_qtype_incompatibility(self) -> None:
        rows = [
            BatchInputRow(
                OriginalQuestionNumber="POL-01",
                BatchRowId=0,
                source_paragraph=(
                    "Teachers support the plan every year. "
                    "Families discuss the route after dinner. "
                    "Leaders protect the park during storms. "
                    "Workers improve service around town. "
                    "Students ignore gossip before exams. "
                    "Volunteers collect supplies near the station."
                ),
            ),
        ]

        results = run_batch_rows(rows, ["vocab"], self.runner)
        by_row_and_subtype = {
            (result.OriginalQuestionNumber, result.QuestionSubtypeKey): result
            for result in results
        }

        polarity_result = by_row_and_subtype[("POL-01", "contextual_vocab_error_1_among_5_polarity_scope_5")]
        self.assertEqual(polarity_result.status, "qtype_incompatibility_error")
        self.assertNotEqual(polarity_result.status, "planning_error")

    def test_correct_among_3_hardening_rejection_surfaces_as_qtype_incompatibility(self) -> None:
        rows = [
            BatchInputRow(
                OriginalQuestionNumber="VOC-03",
                BatchRowId=0,
                source_paragraph=(
                    "People's happiness depends on relative wealth. "
                    "People are rarely satisfied once their neighbors pull ahead. "
                    "But the resulting inequality brought only discontent. "
                    "Communities discuss the pattern each year. "
                    "Officials protect local services during downturns."
                ),
            ),
        ]

        results = run_batch_rows(rows, ["vocab"], self.runner)
        by_row_and_subtype = {
            (result.OriginalQuestionNumber, result.QuestionSubtypeKey): result
            for result in results
        }

        correct3_result = by_row_and_subtype[("VOC-03", "contextual_vocab_correct_among_3_corrupted_5")]
        self.assertEqual(correct3_result.status, "qtype_incompatibility_error")
        self.assertNotEqual(correct3_result.status, "planning_error")

    def test_correct_among_4_hardening_rejection_surfaces_as_qtype_incompatibility(self) -> None:
        rows = [
            BatchInputRow(
                OriginalQuestionNumber="VOC-04",
                BatchRowId=0,
                source_paragraph=(
                    "Community happiness has lasting social value. "
                    "Relative wealth has visible symbolic force. "
                    "Widening inequality has deep political cost. "
                    "Persistent discontent has broad civic impact. "
                    "Public dignity has fragile moral weight."
                ),
            ),
        ]

        results = run_batch_rows(rows, ["vocab"], self.runner)
        by_row_and_subtype = {
            (result.OriginalQuestionNumber, result.QuestionSubtypeKey): result
            for result in results
        }

        correct4_result = by_row_and_subtype[("VOC-04", "contextual_vocab_correct_among_4_corrupted_5")]
        self.assertEqual(correct4_result.status, "qtype_incompatibility_error")
        self.assertNotEqual(correct4_result.status, "planning_error")

    def test_hard_vocab_subtypes_produce_passes_on_inline_reaudit(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _HardVocabAuditPlanner(schema))
        hard_subtypes = [
            "contextual_vocab_correct_among_4_corrupted_5",
            "contextual_vocab_error_1_among_5_5",
            "contextual_vocab_error_1_among_5_polarity_scope_5",
            "contextual_vocab_error_1_among_5_collocation_5",
            "contextual_vocab_correct_among_3_corrupted_5",
        ]

        results = []
        for scenario in self._HARD_VOCAB_REAUDIT_SCENARIOS:
            row = scenario["row"]
            for subtype in scenario["subtypes"]:
                prepared = prepare_source(row.source_paragraph)
                results.append(
                    runner.invoke(
                        {
                            "OriginalQuestionNumber": row.OriginalQuestionNumber,
                            "BatchRowId": row.BatchRowId,
                            "source_paragraph": row.source_paragraph,
                            "QuestionTypeKey": "vocab",
                            "QuestionSubtypeKey": subtype,
                            "QuestionFormatKey": subtype,
                            "prepared_source": prepared,
                            "plan": None,
                            "generated": None,
                            "status": "source_prepared",
                            "errors": [],
                        }
                    )
                )

        for subtype in hard_subtypes:
            subtype_results = [result for result in results if result["QuestionSubtypeKey"] == subtype]
            self.assertTrue(subtype_results, msg=f"Expected inline re-audit rows for {subtype}.")
            self.assertTrue(
                any(result["status"] == "validation_passed" for result in subtype_results),
                msg=f"Expected at least one validation_passed inline re-audit row for {subtype}.",
            )
            self.assertFalse(
                any(
                    result["status"] == "planning_error"
                    and any(
                        "corrupted_replacements_by_span_id" in error
                        or "corrupted_replacements span_id values" in error
                        or "schema" in error.lower()
                        for error in (result.get("errors") or [])
                    )
                    for result in subtype_results
                ),
                msg=f"Did not expect schema-shaped planning_error rows for {subtype} in inline re-audit.",
            )

    def test_quota_failure_triggers_batch_global_fail_fast(self) -> None:
        runner = _QuotaThenUnexpectedRunner()
        mixed_rows = [
            BatchInputRow(OriginalQuestionNumber="8-01", BatchRowId=0, source_paragraph="A. B. C. D. E. F."),
            BatchInputRow(OriginalQuestionNumber="8-02", BatchRowId=1, source_paragraph="G. H. I. J. K. L."),
        ]
        results = run_batch_rows(
            mixed_rows,
            ["sentence_insertion", "paragraph_ordering"],
            runner,
        )
        self.assertEqual(len(results), 4)
        self.assertEqual(runner.invocations, 1)
        self.assertEqual(results[0].errors, [PLANNER_QUOTA_EXHAUSTED_ERROR])
        for result in results[1:]:
            self.assertEqual(result.status, "planning_error")
            self.assertEqual(result.errors, [PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR])

    def test_non_quota_planning_error_does_not_trigger_fail_fast(self) -> None:
        runner = _NonQuotaPlanningErrorRunner()
        mixed_rows = [
            BatchInputRow(OriginalQuestionNumber="8-01", BatchRowId=0, source_paragraph="A. B. C. D. E. F."),
            BatchInputRow(OriginalQuestionNumber="8-02", BatchRowId=1, source_paragraph="G. H. I. J. K. L."),
        ]
        results = run_batch_rows(
            mixed_rows,
            ["sentence_insertion", "paragraph_ordering"],
            runner,
        )
        self.assertEqual(len(results), 4)
        self.assertEqual(runner.invocations, 4)
        self.assertTrue(all(result.status == "planning_error" for result in results))
        self.assertTrue(all("schema mismatch" in result.errors[0] for result in results))

    def test_file_runner_writes_csv_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_csv = Path(tmpdir) / "input.csv"
            output_csv = Path(tmpdir) / "output.csv"
            output_md = Path(tmpdir) / "output.md"
            with input_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["OriginalQuestionNumber", "source_paragraph"])
                writer.writeheader()
                writer.writerow(
                    {
                        "OriginalQuestionNumber": "8-Analysis",
                        "source_paragraph": "A. B. C. D. E. F.",
                    }
                )

            results = run_batch_files(
                input_csv,
                output_csv,
                ["sentence_insertion"],
                self.runner,
                output_markdown=output_md,
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].OriginalQuestionNumber, "8-Analysis")
            self.assertEqual(results[0].BatchRowId, 0)
            self.assertTrue(output_csv.exists())
            self.assertTrue(output_md.exists())
            self.assertIn("BatchRowId", output_csv.read_text(encoding="utf-8"))
            self.assertIn("row 0 / 8-Analysis", output_md.read_text(encoding="utf-8"))

    def test_progress_callback_reports_batch_lifecycle(self) -> None:
        updates: list[BatchProgressUpdate] = []
        results = run_batch_rows(
            self.rows,
            ["sentence_insertion"],
            self.runner,
            progress_callback=updates.append,
        )
        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(len(updates), 3)
        self.assertEqual(updates[0].event, "started")
        self.assertEqual(updates[0].completed_items, 0)
        self.assertEqual(updates[1].event, "item_started")
        self.assertEqual(updates[1].completed_items, 0)
        self.assertEqual(updates[1].total_items, 1)
        self.assertEqual(updates[1].status, "running")
        self.assertEqual(updates[1].current_row_number, "8-Analysis")
        self.assertEqual(updates[2].event, "item_completed")
        self.assertEqual(updates[2].completed_items, 1)
        self.assertEqual(updates[2].total_items, 1)
        self.assertEqual(updates[2].status, "validation_passed")
        self.assertEqual(updates[2].current_row_number, "8-Analysis")
        self.assertEqual(updates[-1].event, "completed")
        self.assertEqual(updates[-1].completed_items, 1)
        self.assertEqual(updates[-1].total_items, 1)

    def test_console_progress_renderer_can_consume_batch_updates_unchanged(self) -> None:
        stream = StringIO()
        renderer = ConsoleProgressRenderer(stream=stream, live_updates=False)
        updates: list[BatchProgressUpdate] = []

        renderer.start()
        results = run_batch_rows(
            self.rows,
            ["sentence_insertion"],
            self.runner,
            progress_callback=chain_progress_callbacks(updates.append, renderer.callback),
        )
        renderer.stop(success=True)

        self.assertEqual(len(results), 1)
        self.assertEqual([update.event for update in updates], ["started", "item_started", "item_completed", "completed"])
        self.assertIn("Starting batch run", stream.getvalue())
        self.assertIn("Completed batch run with 1 exported rows.", stream.getvalue())

    def test_invalid_runner_fails_clearly(self) -> None:
        with self.assertRaises(ValueError):
            run_batch_rows(self.rows, ["sentence_insertion"], runner=None)  # type: ignore[arg-type]

    def test_dataframe_adapter_matches_row_execution(self) -> None:
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas is not installed")

        frame = pd.DataFrame([row.model_dump() for row in self.rows])
        df_results = run_batch_dataframe(frame, ["sentence_insertion"], self.runner)
        row_results = run_batch_rows(self.rows, ["sentence_insertion"], self.runner)
        self.assertEqual(df_results.to_dict(orient="records")[0]["status"], row_results[0].status)
        self.assertEqual(df_results.to_dict(orient="records")[0]["BatchRowId"], 0)

    def test_dataframe_adapter_assigns_batch_row_id_when_missing(self) -> None:
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas is not installed")

        frame = pd.DataFrame(
            [
                {
                    "OriginalQuestionNumber": "8-Analysis",
                    "source_paragraph": "A. B. C. D. E. F.",
                }
            ]
        )
        df_results = run_batch_dataframe(frame, ["sentence_insertion"], self.runner)
        record = df_results.to_dict(orient="records")[0]
        self.assertEqual(record["OriginalQuestionNumber"], "8-Analysis")
        self.assertEqual(record["BatchRowId"], 0)


if __name__ == "__main__":
    unittest.main()
