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
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
)


class _StubPlanner:
    def __init__(
        self,
        output_schema: type[SentenceInsertionPlan | ParagraphOrderingPlan | UnderlinedPhraseMeaningPlan],
    ) -> None:
        self.output_schema = output_schema

    def invoke(self, prompt: str) -> SentenceInsertionPlan | ParagraphOrderingPlan | UnderlinedPhraseMeaningPlan:
        if self.output_schema is SentenceInsertionPlan:
            return self.output_schema(
                target_unit_ids=["S2"],
                selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
                correct_gap_id="G2",
                explanation="문장 S2는 G2 위치에 들어가야 자연스럽습니다.",
            )
        if self.output_schema is ParagraphOrderingPlan:
            return self.output_schema(
                intro_unit_ids=["S0", "S1"],
                continuation_blocks=[["S2", "S3"], ["S4", "S5"], ["S6", "S7", "S8"]],
                explanation="도입부 다음에 원인과 결과가 이어지는 흐름입니다.",
            )
        match = re.search(r"- (P\d+): text='one end of the spectrum'", prompt)
        selected_span_id = match.group(1) if match else "P0"
        return self.output_schema(
            selected_span_id=selected_span_id,
            selected_span_text="one end of the spectrum",
            paraphrase_choices_ko=[
                "여러 변화 양상 가운데 한 극단을 가리킨다는 뜻",
                "중간 지점을 대표하는 예시라는 뜻",
                "전체 변화가 거의 일어나지 않았다는 뜻",
                "한 가지 재배법만 허용되었다는 뜻",
                "자연 성장과 무관한 예외 사례라는 뜻",
            ],
            correct_choice="여러 변화 양상 가운데 한 극단을 가리킨다는 뜻",
            surface_meaning="연속선의 한쪽 끝이라는 말",
            contextual_meaning="농업 변화 방식들 중 한 극단적 사례를 가리킨다는 뜻",
            supporting_evidence="At one end of the spectrum of transformations was the forest gardening",
            explanation="문맥상 여러 농업 변화 방식 가운데 한쪽 극단을 뜻합니다.",
        )


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

    def test_one_row_one_type(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], self.runner)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "validation_passed")
        self.assertNotIn("S2", results[0].explanation or "")
        self.assertNotIn("G2", results[0].explanation or "")

    def test_one_row_multiple_types(self) -> None:
        mixed_rows = [self._load_fixture_row("10-03")]
        results = run_batch_rows(
            mixed_rows,
            ["sentence_insertion", "paragraph_ordering", "underlined_phrase_meaning", "unknown_type"],
            self.runner,
        )
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].status, "validation_passed")
        self.assertEqual(results[1].status, "validation_passed")
        self.assertEqual(results[2].status, "validation_passed")
        self.assertEqual(results[3].status, "input_error")

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
