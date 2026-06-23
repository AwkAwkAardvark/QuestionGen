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


class PreparedSource(BaseModel):
    sentence_units: list[SourceUnit] = Field(default_factory=list)
    gap_units: list[GapUnit] = Field(default_factory=list)


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
