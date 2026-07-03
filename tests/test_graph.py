from __future__ import annotations

import unittest
from unittest import mock

from questiongen.batch import run_batch_rows
from questiongen.graph import compile_question_graph
from questiongen.schemas import (
    BatchInputRow,
    GapUnit,
    GeneratedQuestion,
    PreparedSource,
    SourceUnit,
    make_initial_state,
)


def _prepared_source() -> PreparedSource:
    return PreparedSource(
        source_text="S0. S1. S2. S3. S4. S5.",
        sentence_units=[
            SourceUnit(id="S0", text="S0.", index=0),
            SourceUnit(id="S1", text="S1.", index=1),
            SourceUnit(id="S2", text="S2.", index=2),
            SourceUnit(id="S3", text="S3.", index=3),
            SourceUnit(id="S4", text="S4.", index=4),
            SourceUnit(id="S5", text="S5.", index=5),
        ],
        gap_units=[
            GapUnit(id="G0", index=0, after_unit_id="S0"),
            GapUnit(id="G1", index=1, before_unit_id="S0", after_unit_id="S1"),
            GapUnit(id="G2", index=2, before_unit_id="S1", after_unit_id="S2"),
            GapUnit(id="G3", index=3, before_unit_id="S2", after_unit_id="S3"),
            GapUnit(id="G4", index=4, before_unit_id="S3", after_unit_id="S4"),
            GapUnit(id="G5", index=5, before_unit_id="S4", after_unit_id="S5"),
            GapUnit(id="G6", index=6, before_unit_id="S5"),
        ],
    )


def _generated_question() -> GeneratedQuestion:
    return GeneratedQuestion(
        OriginalQuestionNumber="10-03",
        BatchRowId=0,
        QuestionFormatKey="sentence_insertion_5_gaps",
        QuestionSubtypeKey="sentence_insertion_5_gaps",
        QuestionSubtype="문장 삽입",
        QuestionType="문장 삽입",
        student_paragraph="Rendered student paragraph",
        question_stem="다음 문장이 들어갈 가장 적절한 곳을 고르시오.",
        given_sentence="Inserted sentence.",
        choices=["(1)", "(2)", "(3)", "(4)", "(5)"],
        answer="3",
        explanation="최종 해설",
    )


class QuestionGraphRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = compile_question_graph(structured_llm_factory=lambda schema: None)
        self.state = make_initial_state(
            source_paragraph="S0. S1. S2. S3. S4. S5.",
            original_question_number="10-03",
            batch_row_id=0,
            question_type_key="sentence_insertion",
            question_format_key="sentence_insertion_5_gaps",
            question_subtype_key="sentence_insertion_5_gaps",
        )

    def test_input_error_stops_before_source_preparation(self) -> None:
        with (
            mock.patch(
                "questiongen.graph.input_check",
                return_value={"status": "input_error", "errors": ["bad input"]},
            ),
            mock.patch("questiongen.graph.prepare_source") as prepare_source_mock,
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "input_error")
        self.assertEqual(result["errors"], ["bad input"])
        prepare_source_mock.assert_not_called()

    def test_source_error_stops_before_planning(self) -> None:
        planner_mock = mock.Mock()
        with (
            mock.patch(
                "questiongen.graph.input_check",
                return_value={"status": "input_passed", "errors": []},
            ),
            mock.patch("questiongen.graph.prepare_source", return_value=_prepared_source()),
            mock.patch(
                "questiongen.graph.source_check",
                return_value={"status": "source_error", "errors": ["bad source"]},
            ),
            mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": planner_mock}),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "source_error")
        self.assertEqual(result["errors"], ["bad source"])
        planner_mock.assert_not_called()

    def test_qtype_incompatibility_stops_before_planning(self) -> None:
        planner_mock = mock.Mock()
        with (
            mock.patch(
                "questiongen.graph.input_check",
                return_value={"status": "input_passed", "errors": []},
            ),
            mock.patch("questiongen.graph.prepare_source", return_value=_prepared_source()),
            mock.patch(
                "questiongen.graph.source_check",
                return_value={
                    "status": "qtype_incompatibility_error",
                    "errors": ["not suitable for this subtype"],
                },
            ),
            mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": planner_mock}),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertEqual(result["errors"], ["not suitable for this subtype"])
        planner_mock.assert_not_called()

    def test_planning_error_stops_before_rendering(self) -> None:
        planner_mock = mock.Mock(return_value={"status": "planning_error", "errors": ["planner failed"]})
        render_mock = mock.Mock()
        with (
            mock.patch(
                "questiongen.graph.input_check",
                return_value={"status": "input_passed", "errors": []},
            ),
            mock.patch("questiongen.graph.prepare_source", return_value=_prepared_source()),
            mock.patch(
                "questiongen.graph.source_check",
                return_value={"status": "source_passed", "errors": []},
            ),
            mock.patch(
                "questiongen.graph.build_design",
                return_value={"design": mock.sentinel.design, "status": "source_passed", "errors": []},
            ),
            mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": planner_mock}),
            mock.patch.dict("questiongen.graph.RENDERERS", {"sentence_insertion": render_mock}),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "planning_error")
        self.assertEqual(result["errors"], ["planner failed"])
        render_mock.assert_not_called()

    def test_rendering_error_stops_before_explanation_and_final_validation(self) -> None:
        render_mock = mock.Mock(return_value={"status": "rendering_error", "errors": ["renderer failed"]})
        explanation_context_mock = mock.Mock()
        explanation_writer_mock = mock.Mock()
        validation_mock = mock.Mock()
        with (
            mock.patch(
                "questiongen.graph.input_check",
                return_value={"status": "input_passed", "errors": []},
            ),
            mock.patch("questiongen.graph.prepare_source", return_value=_prepared_source()),
            mock.patch(
                "questiongen.graph.source_check",
                return_value={"status": "source_passed", "errors": []},
            ),
            mock.patch(
                "questiongen.graph.build_design",
                return_value={"design": mock.sentinel.design, "status": "source_passed", "errors": []},
            ),
            mock.patch.dict(
                "questiongen.graph.PLANNERS",
                {"sentence_insertion": mock.Mock(return_value={"plan": mock.sentinel.plan, "status": "planned", "errors": []})},
            ),
            mock.patch(
                "questiongen.graph.plan_check",
                return_value={"status": "planned", "errors": []},
            ),
            mock.patch.dict("questiongen.graph.RENDERERS", {"sentence_insertion": render_mock}),
            mock.patch("questiongen.graph.build_explanation_context", explanation_context_mock),
            mock.patch("questiongen.graph.write_teacher_facing_explanation", explanation_writer_mock),
            mock.patch("questiongen.graph.validate_generated_question", validation_mock),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "rendering_error")
        self.assertEqual(result["errors"], ["renderer failed"])
        explanation_context_mock.assert_not_called()
        explanation_writer_mock.assert_not_called()
        validation_mock.assert_not_called()

    def test_validation_passed_reaches_final_validation_and_preserves_export_payload_shape(self) -> None:
        generated = _generated_question()
        validation_mock = mock.Mock(
            return_value={"generated": generated, "status": "validation_passed", "errors": []}
        )
        runner = compile_question_graph(structured_llm_factory=lambda schema: None)
        row = BatchInputRow(
            OriginalQuestionNumber="10-03",
            BatchRowId=0,
            source_paragraph="S0. S1. S2. S3. S4. S5.",
        )
        with (
            mock.patch(
                "questiongen.graph.input_check",
                return_value={"status": "input_passed", "errors": []},
            ),
            mock.patch("questiongen.graph.prepare_source", return_value=_prepared_source()),
            mock.patch(
                "questiongen.graph.source_check",
                return_value={"status": "source_passed", "errors": []},
            ),
            mock.patch(
                "questiongen.graph.build_design",
                return_value={"design": mock.sentinel.design, "status": "source_passed", "errors": []},
            ),
            mock.patch.dict(
                "questiongen.graph.PLANNERS",
                {"sentence_insertion": mock.Mock(return_value={"plan": mock.sentinel.plan, "status": "planned", "errors": []})},
            ),
            mock.patch(
                "questiongen.graph.plan_check",
                return_value={"status": "planned", "errors": []},
            ),
            mock.patch.dict(
                "questiongen.graph.RENDERERS",
                {"sentence_insertion": mock.Mock(return_value={"generated": generated, "status": "rendered", "errors": []})},
            ),
            mock.patch(
                "questiongen.graph.build_explanation_context",
                return_value={"explanation_context": {"anchor": "context"}, "status": "rendered", "errors": []},
            ),
            mock.patch(
                "questiongen.graph.write_teacher_facing_explanation",
                return_value={"generated": generated, "status": "rendered", "errors": []},
            ),
            mock.patch("questiongen.graph.validate_generated_question", validation_mock),
        ):
            results = run_batch_rows([row], ["sentence_insertion"], runner)

        validation_mock.assert_called_once()
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.status, "validation_passed")
        self.assertEqual(result.QuestionTypeKey, "sentence_insertion")
        self.assertEqual(result.QuestionFormatKey, "sentence_insertion_5_gaps")
        self.assertEqual(result.QuestionSubtypeKey, "sentence_insertion_5_gaps")
        self.assertEqual(result.student_paragraph, "Rendered student paragraph")
        self.assertEqual(result.question_stem, "다음 문장이 들어갈 가장 적절한 곳을 고르시오.")
        self.assertEqual(result.given_sentence, "Inserted sentence.")
        self.assertEqual(result.choices, ["(1)", "(2)", "(3)", "(4)", "(5)"])
        self.assertEqual(result.answer, "3")
        self.assertEqual(result.explanation, "최종 해설")


if __name__ == "__main__":
    unittest.main()
