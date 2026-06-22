from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from questiongen.batch import run_batch_dataframe, run_batch_files, run_batch_rows
from questiongen.graph import compile_question_graph
from questiongen.schemas import BatchInputRow, SentenceInsertionPlan


class _StubPlanner:
    def __init__(self, output_schema: type[SentenceInsertionPlan]) -> None:
        self.output_schema = output_schema

    def invoke(self, prompt: str) -> SentenceInsertionPlan:
        return self.output_schema(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
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


class BatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = compile_question_graph(structured_llm_factory=lambda schema: _StubPlanner(schema))
        self.rows = [BatchInputRow(OriginalQuestionNumber="8-Analysis", BatchRowId=0, source_paragraph="A. B. C. D. E. F.")]

    def test_one_row_one_type(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], self.runner)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "validation_passed")

    def test_one_row_multiple_types(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion", "unknown_type"], self.runner)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].status, "validation_passed")
        self.assertEqual(results[1].status, "input_error")

    def test_per_row_failure_is_captured(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], _FailingRunner())
        self.assertEqual(results[0].status, "planning_error")
        self.assertTrue(results[0].errors)

    def test_qtype_incompatibility_is_preserved(self) -> None:
        results = run_batch_rows(self.rows, ["sentence_insertion"], _IncompatibleRunner())
        self.assertEqual(results[0].status, "qtype_incompatibility_error")
        self.assertTrue(any("not suitable" in error for error in results[0].errors))

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
