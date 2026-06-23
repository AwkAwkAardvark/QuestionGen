from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from questiongen.ui.gradio_app import (
    create_app,
    load_api_keys,
    normalize_question_type_keys,
    resolve_input_csv,
)


class GradioAppHelperTests(unittest.TestCase):
    def test_normalize_question_type_keys_defaults_to_registry(self) -> None:
        normalized = normalize_question_type_keys([])
        self.assertIn("sentence_insertion", normalized)
        self.assertIn("paragraph_ordering", normalized)
        self.assertIn("mood_atmosphere", normalized)

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

    def test_create_app_requires_gradio_when_missing(self) -> None:
        with self.assertRaises(ImportError):
            create_app()


if __name__ == "__main__":
    unittest.main()
