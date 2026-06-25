from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from ._compat import BaseModel, Field, model_validator

PipelineStatus = Literal[
    "pending",
    "input_error",
    "input_passed",
    "source_prepared",
    "source_error",
    "qtype_incompatibility_error",
    "source_passed",
    "planning_error",
    "planned",
    "rendering_error",
    "rendered",
    "validation_error",
    "validation_passed",
]

_HANGUL_RE = re.compile(r"[가-힣]")


class SourceUnit(BaseModel):
    id: str
    kind: Literal["sentence"] = "sentence"
    text: str
    index: int

    @model_validator(mode="after")
    def _validate_source_unit(self) -> SourceUnit:
        if self.kind != "sentence":
            raise ValueError("SourceUnit.kind must be 'sentence'.")
        if not self.id:
            raise ValueError("SourceUnit.id is required.")
        if self.index < 0:
            raise ValueError("SourceUnit.index must be non-negative.")
        if not self.text or not self.text.strip():
            raise ValueError("SourceUnit.text is required.")
        return self


class GapUnit(BaseModel):
    id: str
    kind: Literal["gap"] = "gap"
    index: int
    before_unit_id: str | None = None
    after_unit_id: str | None = None

    @model_validator(mode="after")
    def _validate_gap_unit(self) -> GapUnit:
        if self.kind != "gap":
            raise ValueError("GapUnit.kind must be 'gap'.")
        if not self.id:
            raise ValueError("GapUnit.id is required.")
        if self.index < 0:
            raise ValueError("GapUnit.index must be non-negative.")
        return self


class SpanUnit(BaseModel):
    id: str
    kind: Literal["span"] = "span"
    text: str
    normalized_text: str
    char_start: int
    char_end: int
    sentence_unit_id: str | None = None
    sentence_index: int | None = None
    context_before: str | None = None
    context_after: str | None = None
    heuristic_tags: list[str] = Field(default_factory=list)
    priority_score: int = 0

    @model_validator(mode="after")
    def _validate_span_unit(self) -> SpanUnit:
        if self.kind != "span":
            raise ValueError("SpanUnit.kind must be 'span'.")
        if not self.id:
            raise ValueError("SpanUnit.id is required.")
        if not self.text or not self.text.strip():
            raise ValueError("SpanUnit.text is required.")
        if self.normalized_text != " ".join(self.text.split()):
            raise ValueError("SpanUnit.normalized_text must match normalized SpanUnit.text.")
        if self.char_start < 0:
            raise ValueError("SpanUnit.char_start must be non-negative.")
        if self.char_end <= self.char_start:
            raise ValueError("SpanUnit.char_end must be greater than char_start.")
        if self.sentence_index is not None and self.sentence_index < 0:
            raise ValueError("SpanUnit.sentence_index must be non-negative when provided.")
        if self.priority_score < 0:
            raise ValueError("SpanUnit.priority_score must be non-negative.")
        return self


class PreparedSource(BaseModel):
    source_text: str
    sentence_units: list[SourceUnit] = Field(default_factory=list)
    gap_units: list[GapUnit] = Field(default_factory=list)
    span_units: list[SpanUnit] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_prepared_source(self) -> PreparedSource:
        if not self.source_text or not self.source_text.strip():
            raise ValueError("PreparedSource.source_text is required.")
        return self


class SentenceInsertionPlan(BaseModel):
    target_unit_ids: list[str] = Field(default_factory=list)
    selected_gap_ids: list[str] = Field(default_factory=list)
    correct_gap_id: str
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> SentenceInsertionPlan:
        if len(self.target_unit_ids) != 1:
            raise ValueError("SentenceInsertionPlan requires exactly one target_unit_id.")
        if len(self.selected_gap_ids) != 5:
            raise ValueError("SentenceInsertionPlan requires exactly five selected_gap_ids.")
        if len(set(self.selected_gap_ids)) != 5:
            raise ValueError("SentenceInsertionPlan selected_gap_ids must be unique.")
        if self.correct_gap_id not in self.selected_gap_ids:
            raise ValueError("SentenceInsertionPlan correct_gap_id must be in selected_gap_ids.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("SentenceInsertionPlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("SentenceInsertionPlan explanation must contain Korean text.")
        return self


class ParagraphOrderingPlan(BaseModel):
    intro_unit_ids: list[str] = Field(default_factory=list)
    continuation_blocks: list[list[str]] = Field(default_factory=list)
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> ParagraphOrderingPlan:
        if not self.intro_unit_ids:
            raise ValueError("ParagraphOrderingPlan requires at least one intro_unit_id.")
        if len(self.continuation_blocks) != 3:
            raise ValueError("ParagraphOrderingPlan requires exactly three continuation blocks.")
        if any(not block for block in self.continuation_blocks):
            raise ValueError("ParagraphOrderingPlan continuation blocks must all be non-empty.")

        flattened = [unit_id for block in [self.intro_unit_ids, *self.continuation_blocks] for unit_id in block]
        if len(flattened) != len(set(flattened)):
            raise ValueError("ParagraphOrderingPlan unit IDs must be unique across all blocks.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("ParagraphOrderingPlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("ParagraphOrderingPlan explanation must contain Korean text.")
        return self


_CHOICE_PAIR_RE = re.compile(r"^[A-Za-z][A-Za-z '\-/]*(?:\s*->\s*)[A-Za-z][A-Za-z '\-/]*$")
_ENGLISH_CHOICE_RE = re.compile(r"^[A-Za-z][A-Za-z '\-/,;:()]*[A-Za-z.]$")
_ENGLISH_WORD_RE = re.compile(r"^[A-Za-z]+(?:[-'’][A-Za-z]+)*$")
_ENGLISH_LEXICAL_CHOICE_RE = re.compile(
    r"^[A-Za-z]+(?:[-'’][A-Za-z]+)*(?: [A-Za-z]+(?:[-'’][A-Za-z]+)*){0,3}$"
)


def _is_short_english_lexical_choice(value: str) -> bool:
    normalized = " ".join(value.split())
    if not normalized or _ENGLISH_LEXICAL_CHOICE_RE.fullmatch(normalized) is None:
        return False
    return 1 <= len(normalized.split()) <= 4


def _normalize_choice_pair(value: str) -> str:
    left, right = [part.strip().lower() for part in value.split("->", 1)]
    return f"{left} -> {right}"


class MoodAtmospherePlan(BaseModel):
    subtype: Literal["emotion_shift", "emotion_state", "atmosphere"] = "emotion_shift"
    target_holder: str | None = None
    initial_emotion: str | None = None
    final_emotion: str | None = None
    state_emotion: str | None = None
    atmosphere_label: str | None = None
    choice_pairs: list[str] = Field(default_factory=list)
    correct_choice: str
    initial_evidence: str | None = None
    final_evidence: str | None = None
    shift_trigger: str | None = None
    state_evidence: str | None = None
    atmosphere_evidence: str | None = None
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> MoodAtmospherePlan:
        if self.subtype in {"emotion_shift", "emotion_state"}:
            if not self.target_holder or not self.target_holder.strip():
                raise ValueError("MoodAtmospherePlan target_holder is required.")
        if self.subtype == "emotion_shift":
            if not self.initial_emotion or not self.initial_emotion.strip():
                raise ValueError("MoodAtmospherePlan initial_emotion is required.")
            if not self.final_emotion or not self.final_emotion.strip():
                raise ValueError("MoodAtmospherePlan final_emotion is required.")
            if self.initial_emotion.strip().lower() == self.final_emotion.strip().lower():
                raise ValueError("MoodAtmospherePlan initial_emotion and final_emotion must differ.")
            if len(self.choice_pairs) != 5:
                raise ValueError("MoodAtmospherePlan requires exactly five choice_pairs.")
            if len({_normalize_choice_pair(choice) for choice in self.choice_pairs}) != 5:
                raise ValueError("MoodAtmospherePlan choice_pairs must be unique.")
            if any(not _CHOICE_PAIR_RE.match(choice.strip()) for choice in self.choice_pairs):
                raise ValueError("MoodAtmospherePlan choice_pairs must use English 'emotion -> emotion' format.")
            if self.correct_choice not in self.choice_pairs:
                raise ValueError("MoodAtmospherePlan correct_choice must be included in choice_pairs.")
            correct_pair = f"{self.initial_emotion.strip()} -> {self.final_emotion.strip()}"
            if _normalize_choice_pair(self.correct_choice) != _normalize_choice_pair(correct_pair):
                raise ValueError("MoodAtmospherePlan correct_choice must match initial_emotion -> final_emotion.")
            if not self.initial_evidence or not self.initial_evidence.strip():
                raise ValueError("MoodAtmospherePlan initial_evidence is required.")
            if not self.final_evidence or not self.final_evidence.strip():
                raise ValueError("MoodAtmospherePlan final_evidence is required.")
        else:
            if len(self.choice_pairs) != 5:
                raise ValueError("MoodAtmospherePlan requires exactly five choice_pairs.")
            normalized_choices = [" ".join(choice.split()) for choice in self.choice_pairs]
            if len(set(normalized_choices)) != 5:
                raise ValueError("MoodAtmospherePlan choice_pairs must be unique.")
            if any(_ENGLISH_CHOICE_RE.fullmatch(choice) is None for choice in normalized_choices):
                raise ValueError("MoodAtmospherePlan choice_pairs must be readable English choices.")
            if " ".join(self.correct_choice.split()) not in normalized_choices:
                raise ValueError("MoodAtmospherePlan correct_choice must be included in choice_pairs.")
            if self.subtype == "emotion_state":
                if not self.state_emotion or not self.state_emotion.strip():
                    raise ValueError("MoodAtmospherePlan state_emotion is required for emotion_state.")
                if " ".join(self.correct_choice.split()).lower() != " ".join(self.state_emotion.split()).lower():
                    raise ValueError("MoodAtmospherePlan correct_choice must match state_emotion.")
                if not self.state_evidence or not self.state_evidence.strip():
                    raise ValueError("MoodAtmospherePlan state_evidence is required for emotion_state.")
            if self.subtype == "atmosphere":
                if not self.atmosphere_label or not self.atmosphere_label.strip():
                    raise ValueError("MoodAtmospherePlan atmosphere_label is required for atmosphere.")
                if " ".join(self.correct_choice.split()).lower() != " ".join(self.atmosphere_label.split()).lower():
                    raise ValueError("MoodAtmospherePlan correct_choice must match atmosphere_label.")
                if not self.atmosphere_evidence or not self.atmosphere_evidence.strip():
                    raise ValueError("MoodAtmospherePlan atmosphere_evidence is required for atmosphere.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("MoodAtmospherePlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("MoodAtmospherePlan explanation must contain Korean text.")
        return self


class UnderlinedPhraseMeaningPlan(BaseModel):
    selected_span_id: str
    selected_span_text: str
    paraphrase_choices_ko: list[str] = Field(default_factory=list)
    correct_choice: str
    surface_meaning: str
    contextual_meaning: str
    supporting_evidence: str
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> UnderlinedPhraseMeaningPlan:
        if not self.selected_span_id:
            raise ValueError("UnderlinedPhraseMeaningPlan selected_span_id is required.")
        if not self.selected_span_text or not self.selected_span_text.strip():
            raise ValueError("UnderlinedPhraseMeaningPlan selected_span_text is required.")
        if len(self.paraphrase_choices_ko) != 5:
            raise ValueError("UnderlinedPhraseMeaningPlan requires exactly five paraphrase_choices_ko.")
        normalized_choices = [" ".join(choice.split()) for choice in self.paraphrase_choices_ko]
        if len(set(normalized_choices)) != 5:
            raise ValueError("UnderlinedPhraseMeaningPlan paraphrase_choices_ko must be unique.")
        if any(not _HANGUL_RE.search(choice) for choice in normalized_choices):
            raise ValueError("UnderlinedPhraseMeaningPlan paraphrase_choices_ko must contain Korean text.")
        if " ".join(self.correct_choice.split()) not in normalized_choices:
            raise ValueError("UnderlinedPhraseMeaningPlan correct_choice must be included in paraphrase_choices_ko.")
        if not self.surface_meaning or not self.surface_meaning.strip():
            raise ValueError("UnderlinedPhraseMeaningPlan surface_meaning is required.")
        if not _HANGUL_RE.search(self.surface_meaning):
            raise ValueError("UnderlinedPhraseMeaningPlan surface_meaning must contain Korean text.")
        if not self.contextual_meaning or not self.contextual_meaning.strip():
            raise ValueError("UnderlinedPhraseMeaningPlan contextual_meaning is required.")
        if not _HANGUL_RE.search(self.contextual_meaning):
            raise ValueError("UnderlinedPhraseMeaningPlan contextual_meaning must contain Korean text.")
        if not self.supporting_evidence or not self.supporting_evidence.strip():
            raise ValueError("UnderlinedPhraseMeaningPlan supporting_evidence is required.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("UnderlinedPhraseMeaningPlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("UnderlinedPhraseMeaningPlan explanation must contain Korean text.")
        return self


class FillInTheBlankPlan(BaseModel):
    subtype: Literal["proposition_inference", "connective_relation", "summary_completion"] = "proposition_inference"
    selected_span_id: str
    selected_span_text: str
    completion_choices: list[str] = Field(default_factory=list)
    correct_choice: str
    contextual_meaning_ko: str
    supporting_evidence: str
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> FillInTheBlankPlan:
        if not self.selected_span_id:
            raise ValueError("FillInTheBlankPlan selected_span_id is required.")
        if not self.selected_span_text or not self.selected_span_text.strip():
            raise ValueError("FillInTheBlankPlan selected_span_text is required.")
        if len(self.completion_choices) != 5:
            raise ValueError("FillInTheBlankPlan requires exactly five completion_choices.")
        normalized_choices = [" ".join(choice.split()) for choice in self.completion_choices]
        if len(set(normalized_choices)) != 5:
            raise ValueError("FillInTheBlankPlan completion_choices must be unique.")
        if any(_ENGLISH_CHOICE_RE.fullmatch(choice) is None for choice in normalized_choices):
            raise ValueError("FillInTheBlankPlan completion_choices must be readable English text.")
        if " ".join(self.correct_choice.split()) not in normalized_choices:
            raise ValueError("FillInTheBlankPlan correct_choice must be included in completion_choices.")
        if not self.contextual_meaning_ko or not self.contextual_meaning_ko.strip():
            raise ValueError("FillInTheBlankPlan contextual_meaning_ko is required.")
        if not _HANGUL_RE.search(self.contextual_meaning_ko):
            raise ValueError("FillInTheBlankPlan contextual_meaning_ko must contain Korean text.")
        if not self.supporting_evidence or not self.supporting_evidence.strip():
            raise ValueError("FillInTheBlankPlan supporting_evidence is required.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("FillInTheBlankPlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("FillInTheBlankPlan explanation must contain Korean text.")
        return self


class VocabPlan(BaseModel):
    subtype: Literal["contextual_error"] = "contextual_error"
    target_span_ids: list[str] = Field(default_factory=list)
    target_span_texts: list[str] = Field(default_factory=list)
    corrupted_span_id: str
    corrupted_word: str
    correction_basis_ko: str
    supporting_evidence: str
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> VocabPlan:
        if len(self.target_span_ids) != 5:
            raise ValueError("VocabPlan requires exactly five target_span_ids.")
        if len(set(self.target_span_ids)) != 5:
            raise ValueError("VocabPlan target_span_ids must be unique.")
        if len(self.target_span_texts) != 5:
            raise ValueError("VocabPlan requires exactly five target_span_texts.")
        normalized_texts = [text.strip().lower() for text in self.target_span_texts]
        if len(set(normalized_texts)) != 5:
            raise ValueError("VocabPlan target_span_texts must be unique.")
        if any(_ENGLISH_WORD_RE.fullmatch(text.strip()) is None for text in self.target_span_texts):
            raise ValueError("VocabPlan target_span_texts must all be single English words.")
        if self.corrupted_span_id not in self.target_span_ids:
            raise ValueError("VocabPlan corrupted_span_id must be included in target_span_ids.")
        if _ENGLISH_WORD_RE.fullmatch(self.corrupted_word.strip()) is None:
            raise ValueError("VocabPlan corrupted_word must be a single English word.")
        if not self.correction_basis_ko or not self.correction_basis_ko.strip():
            raise ValueError("VocabPlan correction_basis_ko is required.")
        if not _HANGUL_RE.search(self.correction_basis_ko):
            raise ValueError("VocabPlan correction_basis_ko must contain Korean text.")
        if not self.supporting_evidence or not self.supporting_evidence.strip():
            raise ValueError("VocabPlan supporting_evidence is required.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("VocabPlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("VocabPlan explanation must contain Korean text.")
        return self


class ContextualVocabChoicePlan(BaseModel):
    subtype: Literal["contextual_choice"] = "contextual_choice"
    selected_span_id: str
    selected_span_text: str
    choice_words: list[str] = Field(default_factory=list)
    correct_choice: str
    contextual_meaning_ko: str
    supporting_evidence: str
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> ContextualVocabChoicePlan:
        if not self.selected_span_id:
            raise ValueError("ContextualVocabChoicePlan selected_span_id is required.")
        if not self.selected_span_text or not self.selected_span_text.strip():
            raise ValueError("ContextualVocabChoicePlan selected_span_text is required.")
        if len(self.choice_words) != 5:
            raise ValueError("ContextualVocabChoicePlan requires exactly five choice_words.")
        normalized_choices = [" ".join(text.split()).lower() for text in self.choice_words]
        if len(set(normalized_choices)) != 5:
            raise ValueError("ContextualVocabChoicePlan choice_words must be unique.")
        if any(not _is_short_english_lexical_choice(choice) for choice in self.choice_words):
            raise ValueError("ContextualVocabChoicePlan choice_words must be short readable English lexical choices.")
        normalized_correct = " ".join(self.correct_choice.split()).lower()
        if normalized_correct not in normalized_choices:
            raise ValueError("ContextualVocabChoicePlan correct_choice must be included in choice_words.")
        if not self.contextual_meaning_ko or not self.contextual_meaning_ko.strip():
            raise ValueError("ContextualVocabChoicePlan contextual_meaning_ko is required.")
        if not _HANGUL_RE.search(self.contextual_meaning_ko):
            raise ValueError("ContextualVocabChoicePlan contextual_meaning_ko must contain Korean text.")
        if not self.supporting_evidence or not self.supporting_evidence.strip():
            raise ValueError("ContextualVocabChoicePlan supporting_evidence is required.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("ContextualVocabChoicePlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("ContextualVocabChoicePlan explanation must contain Korean text.")
        return self


class UnderlinedVocabPlan(BaseModel):
    subtype: Literal[
        "contextual_correct_among_4_corrupted",
        "contextual_error_1_among_5",
        "contextual_correct_among_3_corrupted",
    ]
    target_span_ids: list[str] = Field(default_factory=list)
    target_span_texts: list[str] = Field(default_factory=list)
    corrupted_replacements_by_span_id: dict[str, str] = Field(default_factory=dict)
    answer_span_id: str
    selection_basis_ko: str
    supporting_evidence: str
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> UnderlinedVocabPlan:
        if len(self.target_span_ids) != 5:
            raise ValueError("UnderlinedVocabPlan requires exactly five target_span_ids.")
        if len(set(self.target_span_ids)) != 5:
            raise ValueError("UnderlinedVocabPlan target_span_ids must be unique.")
        if len(self.target_span_texts) != 5:
            raise ValueError("UnderlinedVocabPlan requires exactly five target_span_texts.")
        normalized_texts = [" ".join(text.split()).lower() for text in self.target_span_texts]
        if len(set(normalized_texts)) != 5:
            raise ValueError("UnderlinedVocabPlan target_span_texts must be unique.")
        if any(not _is_short_english_lexical_choice(text) for text in self.target_span_texts):
            raise ValueError("UnderlinedVocabPlan target_span_texts must be short readable English lexical choices.")
        if self.answer_span_id not in self.target_span_ids:
            raise ValueError("UnderlinedVocabPlan answer_span_id must be included in target_span_ids.")

        corrupted_ids = list(self.corrupted_replacements_by_span_id.keys())
        if len(set(corrupted_ids)) != len(corrupted_ids):
            raise ValueError("UnderlinedVocabPlan corrupted_replacements_by_span_id keys must be unique.")
        if any(span_id not in self.target_span_ids for span_id in corrupted_ids):
            raise ValueError("UnderlinedVocabPlan corrupted_replacements_by_span_id keys must be included in target_span_ids.")
        if any(not _is_short_english_lexical_choice(text) for text in self.corrupted_replacements_by_span_id.values()):
            raise ValueError("UnderlinedVocabPlan corrupted replacements must be short readable English lexical choices.")

        expected_corruption_count = {
            "contextual_correct_among_4_corrupted": 4,
            "contextual_error_1_among_5": 1,
            "contextual_correct_among_3_corrupted": 3,
        }[self.subtype]
        if len(self.corrupted_replacements_by_span_id) != expected_corruption_count:
            raise ValueError(
                f"UnderlinedVocabPlan requires exactly {expected_corruption_count} corrupted replacements for {self.subtype}."
            )
        if self.subtype == "contextual_error_1_among_5" and self.answer_span_id not in self.corrupted_replacements_by_span_id:
            raise ValueError("UnderlinedVocabPlan answer_span_id must be the corrupted item for contextual_error_1_among_5.")
        if self.subtype != "contextual_error_1_among_5" and self.answer_span_id in self.corrupted_replacements_by_span_id:
            raise ValueError("UnderlinedVocabPlan answer_span_id must remain uncorrupted for pick-the-correct vocab subtypes.")

        if not self.selection_basis_ko or not self.selection_basis_ko.strip():
            raise ValueError("UnderlinedVocabPlan selection_basis_ko is required.")
        if not _HANGUL_RE.search(self.selection_basis_ko):
            raise ValueError("UnderlinedVocabPlan selection_basis_ko must contain Korean text.")
        if not self.supporting_evidence or not self.supporting_evidence.strip():
            raise ValueError("UnderlinedVocabPlan supporting_evidence is required.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("UnderlinedVocabPlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("UnderlinedVocabPlan explanation must contain Korean text.")
        return self


class GrammarPlan(BaseModel):
    subtype: Literal[
        "verb_form",
        "subject_verb_agreement",
        "finite_nonfinite",
        "participle_voice",
        "relative_clause",
        "noun_clause_introducer",
        "parallel_structure",
        "conjunction_preposition",
    ] = "verb_form"
    target_span_ids: list[str] = Field(default_factory=list)
    target_span_texts: list[str] = Field(default_factory=list)
    corrupted_span_id: str
    corrupted_word: str
    correction_basis_ko: str
    supporting_evidence: str
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> GrammarPlan:
        if len(self.target_span_ids) != 5:
            raise ValueError("GrammarPlan requires exactly five target_span_ids.")
        if len(set(self.target_span_ids)) != 5:
            raise ValueError("GrammarPlan target_span_ids must be unique.")
        if len(self.target_span_texts) != 5:
            raise ValueError("GrammarPlan requires exactly five target_span_texts.")
        normalized_texts = [text.strip().lower() for text in self.target_span_texts]
        if len(set(normalized_texts)) != 5:
            raise ValueError("GrammarPlan target_span_texts must be unique.")
        if any(_ENGLISH_WORD_RE.fullmatch(text.strip()) is None for text in self.target_span_texts):
            raise ValueError("GrammarPlan target_span_texts must all be single English words.")
        if self.corrupted_span_id not in self.target_span_ids:
            raise ValueError("GrammarPlan corrupted_span_id must be included in target_span_ids.")
        if _ENGLISH_WORD_RE.fullmatch(self.corrupted_word.strip()) is None:
            raise ValueError("GrammarPlan corrupted_word must be a single English word.")
        if not self.correction_basis_ko or not self.correction_basis_ko.strip():
            raise ValueError("GrammarPlan correction_basis_ko is required.")
        if not _HANGUL_RE.search(self.correction_basis_ko):
            raise ValueError("GrammarPlan correction_basis_ko must contain Korean text.")
        if not self.supporting_evidence or not self.supporting_evidence.strip():
            raise ValueError("GrammarPlan supporting_evidence is required.")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("GrammarPlan explanation is required.")
        if not _HANGUL_RE.search(self.explanation):
            raise ValueError("GrammarPlan explanation must contain Korean text.")
        return self


class GeneratedQuestion(BaseModel):
    OriginalQuestionNumber: str
    BatchRowId: int
    QuestionFormatKey: str | None = None
    QuestionSubtypeKey: str | None = None
    QuestionSubtype: str | None = None
    QuestionType: str
    student_paragraph: str
    question_stem: str
    given_sentence: str | None = None
    choices: list[str] | None = None
    answer: str
    explanation: str | None = None


class BatchInputRow(BaseModel):
    OriginalQuestionNumber: str
    BatchRowId: int
    source_paragraph: str

    @model_validator(mode="after")
    def _validate_input_row(self) -> BatchInputRow:
        if not isinstance(self.OriginalQuestionNumber, str) or not self.OriginalQuestionNumber.strip():
            raise ValueError("OriginalQuestionNumber must be a non-empty string.")
        if not isinstance(self.BatchRowId, int) or self.BatchRowId < 0:
            raise ValueError("BatchRowId must be a non-negative integer.")
        if not isinstance(self.source_paragraph, str) or not self.source_paragraph.strip():
            raise ValueError("source_paragraph must be a non-empty string.")
        return self


class BatchResultRow(BaseModel):
    OriginalQuestionNumber: str
    BatchRowId: int
    QuestionTypeKey: str
    QuestionFormatKey: str | None = None
    QuestionSubtypeKey: str | None = None
    QuestionSubtype: str | None = None
    QuestionType: str | None = None
    status: PipelineStatus
    errors: list[str] = Field(default_factory=list)
    source_paragraph: str
    student_paragraph: str | None = None
    question_stem: str | None = None
    given_sentence: str | None = None
    choices: list[str] | None = None
    answer: str | None = None
    explanation: str | None = None


class QuestionState(TypedDict):
    source_paragraph: str
    OriginalQuestionNumber: str
    BatchRowId: int
    QuestionTypeKey: str
    QuestionFormatKey: str | None
    QuestionSubtypeKey: str | None
    prepared_source: PreparedSource | None
    plan: BaseModel | None
    explanation_context: dict[str, object] | None
    generated: GeneratedQuestion | None
    status: PipelineStatus
    errors: list[str]


def make_initial_state(
    source_paragraph: str,
    original_question_number: str,
    batch_row_id: int,
    question_type_key: str,
    question_format_key: str | None = None,
    question_subtype_key: str | None = None,
) -> QuestionState:
    return {
        "source_paragraph": source_paragraph,
        "OriginalQuestionNumber": original_question_number,
        "BatchRowId": batch_row_id,
        "QuestionTypeKey": question_type_key,
        "QuestionFormatKey": question_format_key,
        "QuestionSubtypeKey": question_subtype_key,
        "prepared_source": None,
        "plan": None,
        "explanation_context": None,
        "generated": None,
        "status": "pending",
        "errors": [],
    }


def coerce_model(value: Any, schema: type[BaseModel]) -> BaseModel:
    return schema.model_validate(value)
