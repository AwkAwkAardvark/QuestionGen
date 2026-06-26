from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _notebook_source(path: Path) -> str:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])


class NotebookContractTests(unittest.TestCase):
    def test_runner_ui_validates_runtime_dependencies_before_app_launch(self) -> None:
        source = _notebook_source(REPO_ROOT / "notebooks" / "runner_ui.ipynb")

        self.assertIn("langchain-openai", source)
        self.assertIn("from questiongen.config import ensure_runtime_dependencies", source)
        self.assertIn("ensure_runtime_dependencies(", source)
        self.assertIn("BOOTSTRAP_ENV=True", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"fetch\", \"origin\"]", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"checkout\", REPO_BRANCH]", source)
        self.assertIn("\"merge\", \"--ff-only\", f\"origin/{REPO_BRANCH}\"", source)
        self.assertIn("existing clone was already at the selected pushed commit", source)

    def test_runner_debug_validates_runtime_dependencies_before_batch_and_ui_launch(self) -> None:
        source = _notebook_source(REPO_ROOT / "notebooks" / "runner_debug.ipynb")

        self.assertIn("langchain-openai", source)
        self.assertIn("from questiongen.config import create_structured_llm, ensure_runtime_dependencies", source)
        self.assertGreaterEqual(source.count("ensure_runtime_dependencies("), 2)
        self.assertIn("BOOTSTRAP_ENV=True", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"fetch\", \"origin\"]", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"checkout\", REPO_BRANCH]", source)
        self.assertIn("\"merge\", \"--ff-only\", f\"origin/{REPO_BRANCH}\"", source)
        self.assertIn("RESET_REPO=True for a clean refresh", source)


if __name__ == "__main__":
    unittest.main()
