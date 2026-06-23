from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ..batch import run_batch_files
from ..config import create_structured_llm
from ..graph import compile_question_graph
from ..question_types import QUESTION_TYPE_SPECS_BY_FAMILY, QUESTION_TYPES

DEFAULT_DATA_DIR = Path("/content/drive/MyDrive/QuestionGenData")
DEFAULT_API_KEY_PATH = DEFAULT_DATA_DIR / "secrets" / "api_key.txt"
DEFAULT_DRIVE_INPUT_CSV = DEFAULT_DATA_DIR / "input" / "questions.csv"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "output" / "gradio"


def create_app():
    try:
        import gradio as gr
    except ImportError as exc:
        raise ImportError(
            "Gradio is not installed. Install the UI extra with "
            "`pip install -e .[ui]` or install `gradio` separately."
        ) from exc

    question_type_choices = list(QUESTION_TYPES.keys())

    def _toggle_input_mode(input_mode: str):
        upload_visible = input_mode == "Upload CSV"
        return gr.update(visible=upload_visible), gr.update(visible=not upload_visible)

    with gr.Blocks(title="QuestionGen Gradio Runner") as app:
        gr.Markdown(
            """
            # QuestionGen Gradio Runner

            This app stays on the current batch pipeline. It lets you either upload a CSV directly
            or point the app at a CSV already available in mounted Google Drive.

            Drive mode expects Drive to already be mounted in the Colab runtime.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                input_mode = gr.Radio(
                    choices=["Upload CSV", "Drive CSV Path"],
                    value="Upload CSV",
                    label="Input Mode",
                )
                upload_csv = gr.File(
                    label="Upload CSV",
                    file_count="single",
                    type="filepath",
                    visible=True,
                )
                drive_csv_path = gr.Textbox(
                    label="Drive CSV Path",
                    value=str(DEFAULT_DRIVE_INPUT_CSV),
                    visible=False,
                )
                api_key_path = gr.Textbox(
                    label="API Key File Path",
                    value=str(DEFAULT_API_KEY_PATH),
                    info="Leave as-is for the standard Drive layout, or clear it to use existing env vars.",
                )
                output_dir = gr.Textbox(
                    label="Output Directory",
                    value=str(DEFAULT_OUTPUT_DIR),
                )
                model_name = gr.Textbox(
                    label="Model Name",
                    value=os.getenv("QUESTIONGEN_MODEL", "gpt-5-mini"),
                )
                temperature = gr.Number(
                    label="Temperature",
                    value=float(os.getenv("QUESTIONGEN_TEMPERATURE", "0")),
                    precision=2,
                )
                question_type_keys = gr.CheckboxGroup(
                    choices=question_type_choices,
                    value=question_type_choices,
                    label="Question Types",
                    info="All registered types are selected by default.",
                )
                run_button = gr.Button("Run QuestionGen", variant="primary")

            with gr.Column(scale=2):
                summary = gr.Markdown(label="Run Summary")
                preview = gr.Dataframe(label="CSV Preview")
                json_preview = gr.Code(label="JSON Preview", language="json")
                markdown_preview = gr.Code(label="Markdown Preview", language="markdown")
                csv_file = gr.File(label="CSV Output")
                json_file = gr.File(label="JSON Output")
                markdown_file = gr.File(label="Markdown Output")

        input_mode.change(
            _toggle_input_mode,
            inputs=[input_mode],
            outputs=[upload_csv, drive_csv_path],
        )

        run_button.click(
            _run_from_ui,
            inputs=[
                input_mode,
                upload_csv,
                drive_csv_path,
                api_key_path,
                output_dir,
                model_name,
                temperature,
                question_type_keys,
            ],
            outputs=[
                summary,
                preview,
                json_preview,
                markdown_preview,
                csv_file,
                json_file,
                markdown_file,
            ],
        )

    return app


def load_api_keys(filepath: str | Path) -> None:
    key_path = Path(filepath)
    if not key_path.exists():
        raise FileNotFoundError(
            f"API key file not found: {key_path}. "
            "Mount Drive first or provide a valid api_key.txt path."
        )

    with key_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()


def resolve_input_csv(
    input_mode: str,
    uploaded_csv_path: str | None,
    drive_csv_path: str,
) -> Path:
    if input_mode == "Upload CSV":
        if not uploaded_csv_path:
            raise ValueError("Upload CSV mode requires an uploaded CSV file.")
        csv_path = Path(uploaded_csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Uploaded CSV path does not exist: {csv_path}")
        return csv_path

    if not drive_csv_path or not drive_csv_path.strip():
        raise ValueError("Drive CSV Path mode requires a file path.")

    csv_path = Path(drive_csv_path).expanduser()
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Drive CSV path does not exist: {csv_path}. "
            "If you are in Colab, mount Drive before launching the Gradio app."
        )
    return csv_path


def normalize_question_type_keys(question_type_keys: Sequence[str] | None) -> list[str]:
    if not question_type_keys:
        return list(QUESTION_TYPES.keys())

    normalized = list(question_type_keys)
    unknown = [key for key in normalized if key not in QUESTION_TYPES]
    if unknown:
        raise ValueError(f"Unknown question types: {', '.join(unknown)}")
    return normalized


def _artifact_paths(output_dir: str | Path, input_csv_path: Path) -> tuple[Path, Path, Path]:
    output_root = Path(output_dir).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = input_csv_path.stem or "questions"
    base = f"{stem}_{stamp}"
    return (
        output_root / f"{base}.csv",
        output_root / f"{base}.json",
        output_root / f"{base}.md",
    )


def _write_json_results(results, output_json: Path) -> None:
    output_json.write_text(
        json.dumps([result.model_dump() for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _run_from_ui(
    input_mode: str,
    uploaded_csv_path: str | None,
    drive_csv_path: str,
    api_key_path: str,
    output_dir: str,
    model_name: str,
    temperature: float,
    question_type_keys: Sequence[str] | None,
):
    try:
        if api_key_path.strip():
            load_api_keys(api_key_path)
        elif not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not set. Provide an api_key.txt path or pre-load the env var.")

        selected_question_types = normalize_question_type_keys(question_type_keys)
        expanded_subtype_count = sum(
            len(QUESTION_TYPE_SPECS_BY_FAMILY[family_key])
            for family_key in selected_question_types
            if family_key in QUESTION_TYPE_SPECS_BY_FAMILY
        )
        input_csv = resolve_input_csv(input_mode, uploaded_csv_path, drive_csv_path)
        output_csv, output_json, output_markdown = _artifact_paths(output_dir, input_csv)

        runner = compile_question_graph(
            structured_llm_factory=lambda schema: create_structured_llm(
                schema,
                model_name=model_name.strip() or None,
                temperature=float(temperature),
            )
        )

        results = run_batch_files(
            input_csv=str(input_csv),
            output_csv=str(output_csv),
            question_type_keys=selected_question_types,
            runner=runner,
            output_markdown=str(output_markdown),
        )
        _write_json_results(results, output_json)

        status_counts = Counter(result.status for result in results)
        summary = "\n".join(
            [
                "## Run Complete",
                "",
                f"- Input mode: `{input_mode}`",
                f"- Input CSV: `{input_csv}`",
                f"- Question families: `{', '.join(selected_question_types)}`",
                f"- Expanded subtypes: `{expanded_subtype_count}`",
                f"- Total rows: `{len(results)}`",
                f"- Status counts: `{dict(status_counts)}`",
                f"- CSV: `{output_csv}`",
                f"- JSON: `{output_json}`",
                f"- Markdown: `{output_markdown}`",
            ]
        )

        try:
            import pandas as pd

            preview = pd.read_csv(output_csv)
        except Exception:
            preview = [result.model_dump() for result in results]

        return (
            summary,
            preview,
            output_json.read_text(encoding="utf-8")[:12000],
            output_markdown.read_text(encoding="utf-8")[:12000],
            str(output_csv),
            str(output_json),
            str(output_markdown),
        )
    except Exception as exc:
        return (
            "## Run Failed\n\n"
            f"- Error: `{exc}`",
            [],
            "",
            "",
            None,
            None,
            None,
        )
