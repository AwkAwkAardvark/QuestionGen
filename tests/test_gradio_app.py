from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from questiongen.question_types import QUESTION_TYPES
from questiongen.ui.gradio_app import (
    all_question_type_keys,
    create_app,
    default_api_key_path,
    default_drive_input_csv,
    default_output_dir,
    deselect_all_question_type_keys,
    load_api_keys,
    normalize_question_type_keys,
    resolve_input_csv,
)


class GradioAppHelperTests(unittest.TestCase):
    def test_live_registry_excludes_dormant_mood_atmosphere(self) -> None:
        self.assertNotIn("mood_atmosphere", QUESTION_TYPES)

    def test_question_type_selection_helpers_match_registry(self) -> None:
        self.assertEqual(all_question_type_keys(), list(QUESTION_TYPES.keys()))
        self.assertEqual(deselect_all_question_type_keys(), [])

    def test_normalize_question_type_keys_defaults_to_registry(self) -> None:
        normalized = normalize_question_type_keys([])
        self.assertIn("sentence_insertion", normalized)
        self.assertIn("paragraph_ordering", normalized)
        self.assertIn("underlined_phrase_meaning", normalized)
        self.assertIn("fill_in_the_blank", normalized)
        self.assertIn("vocab", normalized)
        self.assertIn("grammar", normalized)
        self.assertNotIn("mood_atmosphere", normalized)

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

    def test_create_app_requires_gradio_when_missing(self) -> None:
        with self.assertRaises(ImportError):
            create_app()


if __name__ == "__main__":
    unittest.main()
