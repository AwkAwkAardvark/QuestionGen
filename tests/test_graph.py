from __future__ import annotations

import unittest
from unittest import mock

from questiongen.batch import run_batch_rows
from questiongen.graph import compile_question_graph
from questiongen.parsers import prepare_source
from questiongen.question_types import MOOD_ATMOSPHERE_SPEC, QUESTION_SUBTYPE_SPECS, QUESTION_TYPES
from questiongen.schemas import (
    BatchInputRow,
    GapUnit,
    GeneratedQuestion,
    PreparedSource,
    SourceUnit,
    make_initial_state,
)
from tests.test_planners import (
    _AdjacencyParagraphPlanner,
    _CollapsedGapPlanner,
    _ContextAnchoredInsertionPlanner,
    _FillInTheBlankPlanner,
    _GrammarDriftPlanner,
    _InvalidOrderingCoveragePlanner,
    _MoodAtmospherePlanner,
    _ParagraphOrderingPlanner,
    _UnderlinedPhraseMeaningPlanner,
    _VocabDriftPlanner,
    _VocabPlanner,
)


CONTEXTUAL_INSERTION_SOURCE = (
    "City planners recently tested brighter LED lights on several downtown blocks. "
    "The new lights make crosswalks easier to see after sunset. "
    "They also use less electricity than the older lights. "
    "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
    "Residents say the brighter crosswalks feel safer at night. "
    "Officials now plan to expand the same lighting system to nearby neighborhoods."
)

ORDERING_SOURCE = (
    "Many museums are rethinking how visitors experience their collections. "
    "First, they replace long wall labels with short questions that invite curiosity. "
    "This curiosity encourages people to look closely before reading an explanation. "
    "Next, curators turn that curiosity into quiet audio guides for visitors who want more detail. "
    "Those guides let each person choose how much background information to hear. "
    "Finally, the feedback gathered through those guides helps museums redesign later exhibits."
)

UNDERLINED_SOURCE = (
    "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
    "to those around them. But the resulting inequality brought only discontent."
)

MVP_SOURCE = CONTEXTUAL_INSERTION_SOURCE

POLARITY_SOURCE = (
    "Leaders cease wasteful spending during droughts. "
    "Engineers expand storage when demand rises. "
    "Families ignore rumors during emergencies. "
    "Stronger pumps reduce pressure loss across the valley. "
    "Volunteers protect the main channel from damage. "
    "Teachers discuss the results every Friday."
)

MOOD_SOURCE = (
    "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
    "to those around them. In one experiment, two capuchin monkeys were initially perfectly content "
    "with a reward of cucumbers when they successfully performed a task. But when one monkey receiving "
    "plain old cucumbers became enraged, angrily throwing the previously satisfactory salad vegetable "
    "at its handler. The monkey's economy had grown, since grapes are better than cucumbers. "
    "But the resulting inequality brought only discontent."
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
        self.state = self._make_state("sentence_insertion", "S0. S1. S2. S3. S4. S5.")

    def _make_state(
        self,
        question_type_key: str,
        source_paragraph: str,
        *,
        question_format_key: str | None = None,
        question_subtype_key: str | None = None,
    ) -> dict[str, object]:
        type_spec = QUESTION_TYPES.get(question_type_key)
        return make_initial_state(
            source_paragraph=source_paragraph,
            original_question_number="10-03",
            batch_row_id=0,
            question_type_key=question_type_key,
            question_format_key=question_format_key if question_format_key is not None else getattr(type_spec, "format_key", None),
            question_subtype_key=question_subtype_key if question_subtype_key is not None else getattr(type_spec, "subtype_key", None),
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
        self.assertNotIn("_graph_route", result)
        prepare_source_mock.assert_not_called()

    def test_source_error_stops_before_design_and_planning(self) -> None:
        planner_mock = mock.Mock()
        build_design_mock = mock.Mock()
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
            mock.patch("questiongen.graph.build_design", build_design_mock),
            mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": planner_mock}),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "source_error")
        self.assertEqual(result["errors"], ["bad source"])
        build_design_mock.assert_not_called()
        planner_mock.assert_not_called()

    def test_qtype_incompatibility_stops_before_design_and_planning(self) -> None:
        planner_mock = mock.Mock()
        build_design_mock = mock.Mock()
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
            mock.patch("questiongen.graph.build_design", build_design_mock),
            mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": planner_mock}),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertEqual(result["errors"], ["not suitable for this subtype"])
        build_design_mock.assert_not_called()
        planner_mock.assert_not_called()

    def test_unknown_subtype_stops_before_planning_with_input_error(self) -> None:
        planner_mock = mock.Mock()
        unknown_state = self._make_state(
            "sentence_insertion",
            "S0. S1. S2. S3. S4. S5.",
            question_format_key="mystery_format",
            question_subtype_key="mystery_subtype",
        )
        with mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": planner_mock}):
            result = self.runner.invoke(unknown_state)

        self.assertEqual(result["status"], "input_error")
        self.assertTrue(any("Unknown QuestionSubtypeKey" in error for error in result["errors"]))
        planner_mock.assert_not_called()

    def test_plan_check_error_stops_before_rendering(self) -> None:
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
            mock.patch.dict(
                "questiongen.graph.PLANNERS",
                {"sentence_insertion": mock.Mock(return_value={"plan": mock.sentinel.plan, "status": "planned", "errors": []})},
            ),
            mock.patch(
                "questiongen.graph.plan_check",
                return_value={"status": "planning_error", "errors": ["locked design mismatch"]},
            ),
            mock.patch.dict("questiongen.graph.RENDERERS", {"sentence_insertion": render_mock}),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "planning_error")
        self.assertEqual(result["errors"], ["locked design mismatch"])
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

    def test_happy_path_visits_full_linear_sequence(self) -> None:
        visited: list[str] = []
        generated = _generated_question()

        def mark(stage_name: str, result: dict[str, object]) -> mock.Mock:
            def _inner(*args: object, **kwargs: object) -> dict[str, object]:
                visited.append(stage_name)
                return result

            return mock.Mock(side_effect=_inner)

        with (
            mock.patch("questiongen.graph.input_check", mark("input_check", {"status": "input_passed", "errors": []})),
            mock.patch("questiongen.graph.prepare_source", mark("prepare_source", _prepared_source())),
            mock.patch("questiongen.graph.source_check", mark("source_check", {"status": "source_passed", "errors": []})),
            mock.patch(
                "questiongen.graph.build_design",
                mark("design", {"design": mock.sentinel.design, "status": "source_passed", "errors": []}),
            ),
            mock.patch.dict(
                "questiongen.graph.PLANNERS",
                {"sentence_insertion": mark("planner", {"plan": mock.sentinel.plan, "status": "planned", "errors": []})},
            ),
            mock.patch("questiongen.graph.plan_check", mark("plan_check", {"status": "planned", "errors": []})),
            mock.patch.dict(
                "questiongen.graph.RENDERERS",
                {"sentence_insertion": mark("render", {"generated": generated, "status": "rendered", "errors": []})},
            ),
            mock.patch(
                "questiongen.graph.build_explanation_context",
                mark("build_explanation_context", {"explanation_context": {"anchor": "context"}, "status": "rendered", "errors": []}),
            ),
            mock.patch(
                "questiongen.graph.write_teacher_facing_explanation",
                mark("write_explanation", {"generated": generated, "status": "rendered", "errors": []}),
            ),
            mock.patch(
                "questiongen.graph.validate_generated_question",
                mark("validate_generated_question", {"generated": generated, "status": "validation_passed", "errors": []}),
            ),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(
            visited,
            [
                "input_check",
                "prepare_source",
                "source_check",
                "design",
                "planner",
                "plan_check",
                "render",
                "build_explanation_context",
                "write_explanation",
                "validate_generated_question",
            ],
        )
        self.assertEqual(result["status"], "validation_passed")

    def test_stage_outputs_propagate_across_graph(self) -> None:
        generated = _generated_question()

        def source_check_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertIsNotNone(state.get("prepared_source"))
            self.assertIsNone(state.get("design"))
            self.assertIsNone(state.get("plan"))
            self.assertIsNone(state.get("generated"))
            return {"status": "source_passed", "errors": []}

        def design_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertIsNotNone(state.get("prepared_source"))
            return {"design": mock.sentinel.design, "status": "source_passed", "errors": []}

        def planner_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertIs(state.get("design"), mock.sentinel.design)
            self.assertIsNone(state.get("plan"))
            return {"plan": mock.sentinel.plan, "status": "planned", "errors": []}

        def plan_check_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertIs(state.get("plan"), mock.sentinel.plan)
            return {"status": "planned", "errors": []}

        def render_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertIs(state.get("plan"), mock.sentinel.plan)
            return {"generated": generated, "status": "rendered", "errors": []}

        def explanation_context_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertIs(state.get("generated"), generated)
            return {"explanation_context": {"anchor": "context"}, "status": "rendered", "errors": []}

        def write_explanation_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertEqual(state.get("explanation_context"), {"anchor": "context"})
            return {"generated": generated, "status": "rendered", "errors": []}

        def validate_side_effect(state: dict[str, object], *_args: object) -> dict[str, object]:
            self.assertIs(state.get("generated"), generated)
            return {"generated": generated, "status": "validation_passed", "errors": []}

        with (
            mock.patch("questiongen.graph.input_check", return_value={"status": "input_passed", "errors": []}),
            mock.patch("questiongen.graph.prepare_source", return_value=_prepared_source()),
            mock.patch("questiongen.graph.source_check", side_effect=source_check_side_effect),
            mock.patch("questiongen.graph.build_design", side_effect=design_side_effect),
            mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": mock.Mock(side_effect=planner_side_effect)}),
            mock.patch("questiongen.graph.plan_check", side_effect=plan_check_side_effect),
            mock.patch.dict("questiongen.graph.RENDERERS", {"sentence_insertion": mock.Mock(side_effect=render_side_effect)}),
            mock.patch("questiongen.graph.build_explanation_context", side_effect=explanation_context_side_effect),
            mock.patch("questiongen.graph.write_teacher_facing_explanation", side_effect=write_explanation_side_effect),
            mock.patch("questiongen.graph.validate_generated_question", side_effect=validate_side_effect),
        ):
            result = self.runner.invoke(self.state)

        self.assertEqual(result["status"], "validation_passed")

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

    def test_graph_verbose_logging_marks_stage_boundaries(self) -> None:
        logs: list[str] = []
        runner = compile_question_graph(
            structured_llm_factory=lambda schema: _ContextAnchoredInsertionPlanner(),
            runtime_logger=logs.append,
        )
        result = runner.invoke(self._make_state("sentence_insertion", CONTEXTUAL_INSERTION_SOURCE))
        self.assertEqual(result["status"], "validation_passed")
        self.assertTrue(any("| input_check start |" in message for message in logs))
        self.assertTrue(any("| planner finish | status=planned" in message for message in logs))
        self.assertTrue(any("| render finish | status=rendered" in message for message in logs))
        self.assertTrue(any("| validate_generated_question finish | status=validation_passed" in message for message in logs))

    def test_short_valid_passage_stops_as_qtype_incompatibility_before_planning(self) -> None:
        short_state = self._make_state("sentence_insertion", "A. B. C. D.")
        planner_mock = mock.Mock()
        runner = compile_question_graph(structured_llm_factory=lambda schema: None)
        with mock.patch.dict("questiongen.graph.PLANNERS", {"sentence_insertion": planner_mock}):
            result = runner.invoke(short_state)

        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("at least 5 sentence units" in error for error in result["errors"]))
        planner_mock.assert_not_called()

    def test_weak_paragraph_ordering_row_is_rejected_before_planning(self) -> None:
        source = (
            "It has been said that most people listen with the intention to reply rather than to understand. "
            "Facilitating your mentee’s thinking, rather than trying to do it for them, is your primary responsibility as a mentor, however tempting that may be. "
            "If during a mentoring session, you realize you're doing most of the talking, then just stop, sit back and listen with a patient mind. "
            "A good part of the mentee’s learning process, which involves dealing with complex ideas, happens when he/she thinks out loud. "
            "Therefore, your mentee should be doing most of the talking. "
            "Listening actively and empathically helps a mentee to have a sense of having their thoughts valued and acknowledged; it is essential that you listen well."
        )
        planner_mock = mock.Mock()
        state = self._make_state("paragraph_ordering", source)
        runner = compile_question_graph(structured_llm_factory=lambda schema: None)
        with mock.patch.dict("questiongen.graph.PLANNERS", {"paragraph_ordering": planner_mock}):
            result = runner.invoke(state)

        self.assertEqual(result["status"], "qtype_incompatibility_error")
        self.assertTrue(any("strongly forced adjacency boundaries" in error for error in result["errors"]))
        planner_mock.assert_not_called()


class QuestionGraphBehaviorTests(unittest.TestCase):
    def _make_state(
        self,
        question_type_key: str,
        source_paragraph: str,
        *,
        question_format_key: str | None = None,
        question_subtype_key: str | None = None,
    ) -> dict[str, object]:
        type_spec = QUESTION_TYPES.get(question_type_key)
        return make_initial_state(
            source_paragraph=source_paragraph,
            original_question_number="8-Analysis",
            batch_row_id=0,
            question_type_key=question_type_key,
            question_format_key=question_format_key if question_format_key is not None else getattr(type_spec, "format_key", None),
            question_subtype_key=question_subtype_key if question_subtype_key is not None else getattr(type_spec, "subtype_key", None),
        )

    def test_graph_ignores_planner_override_of_locked_gap_bundle(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _CollapsedGapPlanner())
        result = runner.invoke(self._make_state("sentence_insertion", "A. B. C. D. E. F."))
        self.assertEqual(result["status"], "validation_passed")

    def test_graph_ignores_planner_override_of_locked_ordering_partition(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _InvalidOrderingCoveragePlanner())
        result = runner.invoke(self._make_state("paragraph_ordering", ORDERING_SOURCE))
        self.assertEqual(result["status"], "validation_passed")

    def test_graph_rewrites_internal_paragraph_ordering_explanation(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _ParagraphOrderingPlanner())
        result = runner.invoke(self._make_state("paragraph_ordering", ORDERING_SOURCE))
        self.assertEqual(result["status"], "validation_passed")
        self.assertNotIn("S0", result["generated"].explanation or "")

    def test_graph_rewrites_sentence_insertion_explanation_from_surrounding_context(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _ContextAnchoredInsertionPlanner())
        result = runner.invoke(self._make_state("sentence_insertion", CONTEXTUAL_INSERTION_SOURCE))
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertNotIn("The new lights also use less electricity than the older fixtures.", explanation)
        self.assertIn("new lights", explanation)
        self.assertIn("Because the lights use less electricity", explanation)

    def test_graph_rewrites_paragraph_ordering_explanation_as_edge_chain(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _AdjacencyParagraphPlanner())
        result = runner.invoke(self._make_state("paragraph_ordering", ORDERING_SOURCE))
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertNotIn("핵심 화제 제시", explanation)
        self.assertIn("뒤에는", explanation)
        self.assertIn("다음에는", explanation)

    def test_graph_rewrites_mood_atmosphere_explanation(self) -> None:
        runner = compile_question_graph(
            structured_llm_factory=lambda schema: _MoodAtmospherePlanner(),
            question_types={**QUESTION_SUBTYPE_SPECS, "emotion_shift_pair_choice_5": MOOD_ATMOSPHERE_SPEC},
        )
        state = self._make_state(
            "mood_atmosphere",
            MOOD_SOURCE,
            question_format_key=MOOD_ATMOSPHERE_SPEC.format_key,
            question_subtype_key=MOOD_ATMOSPHERE_SPEC.subtype_key,
        )
        result = runner.invoke(state)
        self.assertEqual(result["status"], "validation_passed")
        self.assertIn("the monkey", result["generated"].explanation or "")
        self.assertNotIn("choice_pairs", result["generated"].explanation or "")

    def test_graph_rewrites_underlined_phrase_meaning_explanation(self) -> None:
        prepared = prepare_source(UNDERLINED_SOURCE)
        span = next(span for span in prepared.span_units if span.text == "resulting inequality brought only discontent")
        runner = compile_question_graph(
            structured_llm_factory=lambda schema: _UnderlinedPhraseMeaningPlanner(
                span.id,
                span.text,
                "the resulting inequality brought only discontent",
            )
        )
        result = runner.invoke(self._make_state("underlined_phrase_meaning", UNDERLINED_SOURCE))
        self.assertEqual(result["status"], "validation_passed")
        self.assertIn("brought only discontent", result["generated"].explanation or "")
        self.assertNotIn("surface_meaning", result["generated"].explanation or "")

    def test_graph_rewrites_best_paraphrase_explanation_as_non_restoration(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabPlanner())
        result = runner.invoke(
            self._make_state(
                "vocab",
                MVP_SOURCE,
                question_format_key="contextual_vocab_best_paraphrase_choice_5",
                question_subtype_key="contextual_vocab_best_paraphrase_choice_5",
            )
        )
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("바꿔 말한 표현", explanation)
        self.assertIn("그대로 복원하는 문제가 아니라", explanation)
        self.assertNotIn("selected_span_id", explanation)

    def test_graph_rewrites_polarity_scope_explanation_with_direction_language(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabPlanner())
        result = runner.invoke(
            self._make_state(
                "vocab",
                POLARITY_SOURCE,
                question_format_key="contextual_vocab_error_1_among_5_polarity_scope_5",
                question_subtype_key="contextual_vocab_error_1_among_5_polarity_scope_5",
            )
        )
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("방향, 정도, 또는 적용 범위", explanation)

    def test_graph_rewrites_collocation_explanation_with_natural_combination_language(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabPlanner())
        result = runner.invoke(
            self._make_state(
                "vocab",
                POLARITY_SOURCE,
                question_format_key="contextual_vocab_error_1_among_5_collocation_5",
                question_subtype_key="contextual_vocab_error_1_among_5_collocation_5",
            )
        )
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("자연스럽게 결합", explanation)

    def test_graph_rewrites_vocab_explanation_from_source_evidence(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _VocabDriftPlanner())
        result = runner.invoke(self._make_state("vocab", MVP_SOURCE))
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
        result = runner.invoke(self._make_state("grammar", MVP_SOURCE))
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("동사원형", explanation)
        self.assertIn("lighting system to nearby neighborhoods", explanation)
        self.assertNotIn("그 구조를 보여 주므로", explanation)
        self.assertNotIn("자유서술 문법 해설", explanation)

    def test_graph_rewrites_fill_explanation_as_teacher_facing_note(self) -> None:
        runner = compile_question_graph(structured_llm_factory=lambda schema: _FillInTheBlankPlanner())
        result = runner.invoke(self._make_state("fill_in_the_blank", MVP_SOURCE))
        self.assertEqual(result["status"], "validation_passed")
        explanation = result["generated"].explanation or ""
        self.assertIn("핵심 단서", explanation)
        self.assertNotIn("라는 의미라는 의미", explanation)


if __name__ == "__main__":
    unittest.main()
