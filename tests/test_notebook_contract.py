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

        self.assertIn("# ## 1. Mount Drive And Define Standard Paths", source)
        self.assertIn("# ## 5. Bootstrap, Refresh, And Launch Gradio", source)
        self.assertIn("langgraph", source)
        self.assertIn("langchain-openai", source)
        self.assertIn("Auto-bootstrapped missing runtime dependencies:", source)
        self.assertIn("missing_runtime_packages(", source)
        self.assertIn("ensure_runtime_modules(", source)
        self.assertIn("UI_RUNTIME_DEPENDENCIES", source)
        self.assertIn("QUESTIONGEN_RUNTIME_RESTART_REQUIRED", source)
        self.assertIn("BOOTSTRAP_ENV=True", source)
        self.assertIn("f\"refs/heads/{REPO_BRANCH}:refs/remotes/origin/{REPO_BRANCH}\"", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"checkout\", REPO_BRANCH]", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"checkout\", \"-b\", REPO_BRANCH, f\"origin/{REPO_BRANCH}\"]", source)
        self.assertIn("\"merge\", \"--ff-only\", f\"origin/{REPO_BRANCH}\"", source)
        self.assertIn("existing clone was already at the selected pushed commit", source)

    def test_runner_debug_validates_runtime_dependencies_before_batch_and_ui_launch(self) -> None:
        source = _notebook_source(REPO_ROOT / "notebooks" / "runner_debug.ipynb")

        self.assertIn("# ## 7. Run The Current Batch Pipeline", source)
        self.assertIn("# ## 9. Optional Gradio Hook", source)
        self.assertIn("# from questiongen.ui.gradio_app import create_app", source)
        self.assertIn("# files.download(str(OUTPUT_CSV))", source)
        self.assertIn("files.download(str(OUTPUT_JSON))", source)
        self.assertIn("# print(OUTPUT_MD.read_text(encoding=\"utf-8\")[:3000])", source)
        self.assertIn("langgraph", source)
        self.assertIn("langchain-openai", source)
        self.assertIn("Auto-bootstrapped missing runtime dependencies:", source)
        self.assertIn("missing_runtime_packages(", source)
        self.assertIn("ensure_runtime_modules(", source)
        self.assertIn("RUNTIME_DEPENDENCIES", source)
        self.assertIn("QUESTIONGEN_RUNTIME_RESTART_REQUIRED", source)
        self.assertIn("from questiongen.config import create_structured_llm", source)
        self.assertIn("BOOTSTRAP_ENV=True", source)
        self.assertIn("f\"refs/heads/{REPO_BRANCH}:refs/remotes/origin/{REPO_BRANCH}\"", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"checkout\", REPO_BRANCH]", source)
        self.assertIn("[\"git\", \"-C\", str(REPO_DIR), \"checkout\", \"-b\", REPO_BRANCH, f\"origin/{REPO_BRANCH}\"]", source)
        self.assertIn("\"merge\", \"--ff-only\", f\"origin/{REPO_BRANCH}\"", source)
        self.assertIn("RESET_REPO=True for a clean refresh", source)


if __name__ == "__main__":
    unittest.main()
