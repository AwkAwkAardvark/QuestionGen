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


def _normalize_choice_pair(value: str) -> str:
    left, right = [part.strip().lower() for part in value.split("->", 1)]
    return f"{left} -> {right}"


class MoodAtmospherePlan(BaseModel):
    subtype: Literal["emotion_shift"] = "emotion_shift"
    target_holder: str
    initial_emotion: str
    final_emotion: str
    choice_pairs: list[str] = Field(default_factory=list)
    correct_choice: str
    initial_evidence: str
    final_evidence: str
    shift_trigger: str | None = None
    explanation: str

    @model_validator(mode="after")
    def _validate_plan(self) -> MoodAtmospherePlan:
        if not self.target_holder or not self.target_holder.strip():
            raise ValueError("MoodAtmospherePlan target_holder is required.")
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


class GeneratedQuestion(BaseModel):
    OriginalQuestionNumber: str
    BatchRowId: int
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
) -> QuestionState:
    return {
        "source_paragraph": source_paragraph,
        "OriginalQuestionNumber": original_question_number,
        "BatchRowId": batch_row_id,
        "QuestionTypeKey": question_type_key,
        "prepared_source": None,
        "plan": None,
        "explanation_context": None,
        "generated": None,
        "status": "pending",
        "errors": [],
    }


def coerce_model(value: Any, schema: type[BaseModel]) -> BaseModel:
    return schema.model_validate(value)
