from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from questiongen.batch import BatchProgressUpdate
from questiongen.question_types import QUESTION_TYPES
from questiongen.ui.gradio_app import (
    QUESTION_TYPE_CHECKLIST_CSS,
    all_question_type_keys,
    create_app,
    default_api_key_path,
    default_drive_input_csv,
    default_output_dir,
    deselect_all_question_type_flags,
    load_api_keys,
    normalize_question_type_keys,
    question_type_checklist_items,
    resolve_input_csv,
    select_all_question_type_flags,
    selected_question_type_keys_from_flags,
    _running_summary,
    _should_log_progress_update,
)


class GradioAppHelperTests(unittest.TestCase):
    def test_live_registry_excludes_dormant_mood_atmosphere(self) -> None:
        self.assertNotIn("mood_atmosphere", QUESTION_TYPES)

    def test_question_type_selection_helpers_match_registry(self) -> None:
        self.assertEqual(all_question_type_keys(), list(QUESTION_TYPES.keys()))
        items = question_type_checklist_items()
        self.assertEqual([item.key for item in items], list(QUESTION_TYPES.keys()))
        self.assertTrue(all(item.key in item.label for item in items))

    def test_normalize_question_type_keys_defaults_to_registry(self) -> None:
        normalized = normalize_question_type_keys(None)
        self.assertIn("sentence_insertion", normalized)
        self.assertIn("paragraph_ordering", normalized)
        self.assertIn("underlined_phrase_meaning", normalized)
        self.assertIn("fill_in_the_blank", normalized)
        self.assertIn("vocab", normalized)
        self.assertIn("grammar", normalized)
        self.assertNotIn("mood_atmosphere", normalized)

    def test_normalize_question_type_keys_preserves_explicit_empty_selection(self) -> None:
        self.assertEqual(normalize_question_type_keys([]), [])

    def test_select_all_and_deselect_all_flags_match_live_registry(self) -> None:
        self.assertEqual(select_all_question_type_flags(), [True] * len(QUESTION_TYPES))
        self.assertEqual(deselect_all_question_type_flags(), [False] * len(QUESTION_TYPES))
        self.assertEqual(
            selected_question_type_keys_from_flags(select_all_question_type_flags()),
            list(QUESTION_TYPES.keys()),
        )
        self.assertEqual(
            selected_question_type_keys_from_flags(deselect_all_question_type_flags()),
            [],
        )

    def test_question_type_checklist_css_is_scrollable(self) -> None:
        self.assertIn("max-height: 18rem", QUESTION_TYPE_CHECKLIST_CSS)
        self.assertIn("overflow-y: auto", QUESTION_TYPE_CHECKLIST_CSS)

    def test_normalize_question_type_keys_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            normalize_question_type_keys(["sentence_insertion", "unknown_type"])

    def test_resolve_input_csv_uses_uploaded_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "input.csv"
            csv_path.write_text("OriginalQuestionNumber,source_paragraph\n1,\"A. B. C. D. E.\"\n", encoding="utf-8")
            resolved = resolve_input_csv("Upload CSV", str(csv_path), "")
            self.assertEqual(resolved, csv_path)

    def test_resolve_input_csv_uses_drive_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "drive.csv"
            csv_path.write_text("OriginalQuestionNumber,source_paragraph\n1,\"A. B. C. D. E.\"\n", encoding="utf-8")
            resolved = resolve_input_csv("Drive CSV Path", None, str(csv_path))
            self.assertEqual(resolved, csv_path)

    def test_load_api_keys_reads_key_file(self) -> None:
        previous = os.environ.get("QUESTIONGEN_TEST_KEY")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                key_path = Path(tmpdir) / "api_key.txt"
                key_path.write_text("QUESTIONGEN_TEST_KEY=loaded\n", encoding="utf-8")
                load_api_keys(key_path)
                self.assertEqual(os.environ.get("QUESTIONGEN_TEST_KEY"), "loaded")
        finally:
            if previous is None:
                os.environ.pop("QUESTIONGEN_TEST_KEY", None)
            else:
                os.environ["QUESTIONGEN_TEST_KEY"] = previous

    def test_default_paths_follow_notebook_env_overrides(self) -> None:
        previous = {
            key: os.environ.get(key)
            for key in [
                "QUESTIONGEN_DATA_DIR",
                "QUESTIONGEN_API_KEY_PATH",
                "QUESTIONGEN_DRIVE_INPUT_CSV",
                "QUESTIONGEN_OUTPUT_DIR",
            ]
        }
        try:
            os.environ["QUESTIONGEN_DATA_DIR"] = "/tmp/questiongen-data"
            self.assertEqual(
                str(default_api_key_path()),
                "/tmp/questiongen-data/secrets/api_key.txt",
            )
            self.assertEqual(
                str(default_drive_input_csv()),
                "/tmp/questiongen-data/input/questions.csv",
            )
            self.assertEqual(
                str(default_output_dir()),
                "/tmp/questiongen-data/output/gradio",
            )

            os.environ["QUESTIONGEN_API_KEY_PATH"] = "/tmp/custom/api_key.txt"
            os.environ["QUESTIONGEN_DRIVE_INPUT_CSV"] = "/tmp/custom/questions.csv"
            os.environ["QUESTIONGEN_OUTPUT_DIR"] = "/tmp/custom/output"
            self.assertEqual(str(default_api_key_path()), "/tmp/custom/api_key.txt")
            self.assertEqual(str(default_drive_input_csv()), "/tmp/custom/questions.csv")
            self.assertEqual(str(default_output_dir()), "/tmp/custom/output")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_progress_log_filters_routine_success_updates(self) -> None:
        passed_update = BatchProgressUpdate(
            event="item_completed",
            completed_items=1,
            total_items=4,
            current_row_number="10-03",
            batch_row_id=0,
            question_type_key="sentence_insertion",
            question_subtype_key="sentence_insertion_basic",
            status="validation_passed",
        )
        incompatible_update = BatchProgressUpdate(
            event="item_completed",
            completed_items=2,
            total_items=4,
            current_row_number="10-03",
            batch_row_id=0,
            question_type_key="paragraph_ordering",
            question_subtype_key="paragraph_ordering_4_blocks",
            status="qtype_incompatibility_error",
            message="Passage is not suitable for this question type.",
        )
        started_update = BatchProgressUpdate(
            event="started",
            completed_items=0,
            total_items=4,
            message="Starting batch run.",
        )

        self.assertFalse(_should_log_progress_update(passed_update))
        self.assertTrue(_should_log_progress_update(incompatible_update))
        self.assertTrue(_should_log_progress_update(started_update))

    def test_running_summary_keeps_current_item_and_latest_notable_event_separate(self) -> None:
        summary = _running_summary(
            input_mode="Upload CSV",
            input_csv=Path("/tmp/questions.csv"),
            selected_question_types=["sentence_insertion", "paragraph_ordering"],
            expanded_subtype_count=3,
            completed_items=1,
            total_items=6,
            current_item="10-03 / sentence_insertion_basic: validation_passed",
            latest_notable_event="[0/6] Batch run started.",
        )

        self.assertIn("Current item", summary)
        self.assertIn("Latest notable event", summary)
        self.assertIn("10-03 / sentence_insertion_basic: validation_passed", summary)
        self.assertIn("[0/6] Batch run started.", summary)

    def test_create_app_requires_gradio_when_missing(self) -> None:
        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "gradio":
                raise ImportError("mocked gradio import failure")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            sys.modules.pop("gradio", None)
            with self.assertRaises(ImportError):
                create_app()


if __name__ == "__main__":
    unittest.main()
