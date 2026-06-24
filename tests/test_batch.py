from __future__ import annotations

import csv
import re
import tempfile
import unittest
from pathlib import Path

from questiongen.batch import run_batch_dataframe, run_batch_files, run_batch_rows
from questiongen.graph import compile_question_graph
from questiongen.planners import PLANNER_QUOTA_EXHAUSTED_BATCH_ERROR, PLANNER_QUOTA_EXHAUSTED_ERROR
from questiongen.schemas import (
    BatchInputRow,
    FillInTheBlankPlan,
    GrammarPlan,
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
    VocabPlan,
)
from questiongen.targeting import allowed_verb_form_variants


class _StubPlanner:
    def __init__(
        self,
        output_schema: type[
            SentenceInsertionPlan
            | ParagraphOrderingPlan
            | UnderlinedPhraseMeaningPlan
            | FillInTheBlankPlan
            | VocabPlan
            | GrammarPlan
        ],
    ) -> None:
        self.output_schema = output_schema

    def invoke(
        self, prompt: str
    ) -> (
        SentenceInsertionPlan
        | ParagraphOrderingPlan
        | UnderlinedPhraseMeaningPlan
        | FillInTheBlankPlan
        | VocabPlan
        | GrammarPlan
    ):
        if self.output_schema is SentenceInsertionPlan:
            return self.output_schema(
                target_unit_ids=["S2"],
                selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
                correct_gap_id="G2",
                explanation="문장 S2는 G2 위치에 들어가야 자연스럽습니다.",
            )
        if self.output_schema is ParagraphOrderingPlan:
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
        if self.output_schema is FillInTheBlankPlan:
            match = re.search(r"- rank \d+: (P\d+);.*text='([^']+)'", prompt)
            selected_span_id = match.group(1) if match else "P0"
            selected_span_text = match.group(2) if match else "less electricity than the older"
            return self.output_schema(
                selected_span_id=selected_span_id,
                selected_span_text=selected_span_text,
                completion_choices=[
                    selected_span_text,
                    "more confusion among the residents",
                    "a weaker plan for nearby roads",
                    "fewer reasons to expand the system",
                    "higher costs for the city budget",
                ],
                correct_choice=selected_span_text,
                contextual_meaning_ko="원문의 핵심 설명이 복원되어야 한다는 의미",
                supporting_evidence=selected_span_text,
                explanation="문맥상 원문의 핵심 설명이 복원되어야 합니다.",
            )
        if self.output_schema is VocabPlan:
            targets = _extract_ranked_single_word_targets(prompt)
            target_ids, target_texts = zip(*targets[:5])
            return self.output_schema(
                target_span_ids=list(target_ids),
                target_span_texts=list(target_texts),
                corrupted_span_id=target_ids[1],
                corrupted_word="heavier",
                correction_basis_ko="이 문맥에서는 밝기와 안전 효과를 설명하는 흐름이라 원래 단어가 더 자연스럽습니다",
                supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
                explanation="문맥상 해당 단어의 뜻이 글의 흐름과 맞지 않습니다.",
            )
        if self.output_schema is GrammarPlan:
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


def _extract_ranked_single_word_targets(prompt: str) -> list[tuple[str, str]]:
    return re.findall(r"- rank \d+: (P\d+); score=\d+; text='([A-Za-z]+)'", prompt)


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
        self.runner = compile_question_graph(structured_llm_factory=lambda schema: _StubPlanner(schema))
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
        self.assertEqual(len(results), 17)
        by_subtype = {result.QuestionSubtypeKey: result for result in results}
        self.assertEqual(by_subtype["sentence_insertion_5_gaps"].status, "validation_passed")
        self.assertEqual(by_subtype["abc_ordering_after_intro"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["underlined_phrase_meaning_5_ko"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["blank_inference_proposition_5_choices"].status, "validation_passed")
        self.assertEqual(by_subtype["blank_connective_relation_5_choices"].status, "validation_passed")
        self.assertEqual(by_subtype["blank_summary_completion_5_choices"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["contextual_vocab_error_5"].status, "validation_passed")
        self.assertEqual(by_subtype["contextual_vocab_choice_5"].status, "planning_error")
        self.assertEqual(by_subtype["grammar_error_verb_form_5"].status, "validation_passed")
        self.assertEqual(by_subtype["grammar_error_subject_verb_agreement_5"].status, "qtype_incompatibility_error")
        self.assertEqual(by_subtype["grammar_error_finite_nonfinite_5"].status, "validation_passed")
        self.assertEqual(results[-1].status, "input_error")

    def test_per_row_failure_is_captured(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], _FailingRunner())
        self.assertEqual(results[0].status, "planning_error")
        self.assertTrue(results[0].errors)

    def test_qtype_incompatibility_is_preserved(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], _IncompatibleRunner())
        self.assertEqual(results[0].status, "qtype_incompatibility_error")
        self.assertTrue(any("not suitable" in error for error in results[0].errors))

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

    def test_short_valid_passage_becomes_qtype_incompatibility(self) -> None:
        short_rows = [BatchInputRow(OriginalQuestionNumber="8-01", BatchRowId=0, source_paragraph="A. B. C. D.")]
        results = run_batch_rows(short_rows, ["sentence_insertion"], self.runner)
        self.assertEqual(results[0].status, "qtype_incompatibility_error")
        self.assertTrue(any("at least 5 sentence units" in error for error in results[0].errors))

    def test_weak_paragraph_ordering_row_is_rejected_before_planning(self) -> None:
        weak_row = BatchInputRow(
            OriginalQuestionNumber="8",
            BatchRowId=0,
            source_paragraph=(
                "It has been said that most people listen with the intention to reply rather than to understand. "
                "Facilitating your mentee’s thinking, rather than trying to do it for them, is your primary responsibility as a mentor, however tempting that may be. "
                "If during a mentoring session, you realize you're doing most of the talking, then just stop, sit back and listen with a patient mind. "
                "A good part of the mentee’s learning process, which involves dealing with complex ideas, happens when he/she thinks out loud. "
                "Therefore, your mentee should be doing most of the talking. "
                "Listening actively and empathically helps a mentee to have a sense of having their thoughts valued and acknowledged; it is essential that you listen well."
            ),
        )
        results = run_batch_rows([weak_row], ["paragraph_ordering"], self.runner)
        self.assertEqual(results[0].status, "qtype_incompatibility_error")
        self.assertTrue(any("strongly forced adjacency boundaries" in error for error in results[0].errors))

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
