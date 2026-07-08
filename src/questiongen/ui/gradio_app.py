from __future__ import annotations

import json
import os
import queue
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ..batch import BatchProgressUpdate, run_batch_files
from ..console_progress import ConsoleProgressRenderer, chain_progress_callbacks, is_notable_progress_update
from ..config import (
    create_structured_llm,
    ensure_runtime_dependencies,
    resolve_planner_elapsed_log_interval_seconds,
    resolve_planner_timeout_seconds,
    resolve_verbose_planner_logging,
)
from ..graph import compile_question_graph
from ..question_types import QUESTION_TYPE_SPECS_BY_FAMILY, QUESTION_TYPES

DEFAULT_DATA_DIR = Path("/content/drive/MyDrive/QuestionGenData")
DEFAULT_API_KEY_PATH = DEFAULT_DATA_DIR / "secrets" / "api_key.txt"
DEFAULT_DRIVE_INPUT_CSV = DEFAULT_DATA_DIR / "input" / "questions.csv"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "output" / "gradio"

QUESTION_TYPE_CHECKLIST_CSS = """
#question-type-checklist {
    max-height: 18rem;
    overflow-y: auto;
    border: 1px solid var(--block-border-color);
    border-radius: 12px;
    padding: 0.5rem 0.75rem;
}
"""


@dataclass(frozen=True)
class QuestionTypeChecklistItem:
    key: str
    label: str


def default_data_dir() -> Path:
    return Path(os.getenv("QUESTIONGEN_DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser()


def default_api_key_path() -> Path:
    return Path(
        os.getenv(
            "QUESTIONGEN_API_KEY_PATH",
            str(default_data_dir() / "secrets" / "api_key.txt"),
        )
    ).expanduser()


def default_drive_input_csv() -> Path:
    return Path(
        os.getenv(
            "QUESTIONGEN_DRIVE_INPUT_CSV",
            str(default_data_dir() / "input" / "questions.csv"),
        )
    ).expanduser()


def default_output_dir() -> Path:
    return Path(
        os.getenv(
            "QUESTIONGEN_OUTPUT_DIR",
            str(default_data_dir() / "output" / "gradio"),
        )
    ).expanduser()


def all_question_type_keys() -> list[str]:
    return list(QUESTION_TYPES.keys())


def question_type_checklist_items() -> list[QuestionTypeChecklistItem]:
    return [
        QuestionTypeChecklistItem(
            key=key,
            label=f"{type_spec.label_ko} ({key})",
        )
        for key, type_spec in QUESTION_TYPES.items()
    ]


def select_all_question_type_flags() -> list[bool]:
    return [True] * len(question_type_checklist_items())


def deselect_all_question_type_flags() -> list[bool]:
    return [False] * len(question_type_checklist_items())


def create_app():
    try:
        import gradio as gr
    except ImportError as exc:
        raise ImportError(
            "Gradio is not installed. Install the UI extra with "
            "`pip install -e .[ui]` or install `gradio` separately."
        ) from exc

    question_type_items = question_type_checklist_items()
    api_key_path_default = default_api_key_path()
    drive_csv_default = default_drive_input_csv()
    output_dir_default = default_output_dir()

    def _toggle_input_mode(input_mode: str):
        upload_visible = input_mode == "Upload CSV"
        return gr.update(visible=upload_visible), gr.update(visible=not upload_visible)

    with gr.Blocks(title="QuestionGen Gradio Runner", css=QUESTION_TYPE_CHECKLIST_CSS) as app:
        gr.Markdown(
            """
            # QuestionGen Gradio Runner

            This app stays on the current batch pipeline. It lets you either upload a CSV directly
            or point the app at a CSV already available in mounted Google Drive.

            Drive mode expects Drive to already be mounted in the Colab runtime. In the Colab
            launcher notebooks, upload-vs-Drive-path selection happens here in the UI rather than
            in notebook cells.
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
                    value=str(drive_csv_default),
                    visible=False,
                )
                api_key_path = gr.Textbox(
                    label="API Key File Path",
                    value=str(api_key_path_default),
                    info="Leave as-is for the standard Drive layout, or clear it to use existing env vars.",
                )
                output_dir = gr.Textbox(
                    label="Output Directory",
                    value=str(output_dir_default),
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
                gr.Markdown("### Question Types")
                gr.Markdown("All registered question families are selected by default.")
                question_type_checkboxes: list[object] = []
                with gr.Column(elem_id="question-type-checklist"):
                    for item in question_type_items:
                        question_type_checkboxes.append(
                            gr.Checkbox(
                                label=item.label,
                                value=True,
                            )
                        )
                with gr.Row():
                    select_all_button = gr.Button("Select All")
                    deselect_all_button = gr.Button("Deselect All")
                run_button = gr.Button("Run QuestionGen", variant="primary")

            with gr.Column(scale=2):
                summary = gr.Markdown(label="Run Summary")
                run_log = gr.Textbox(
                    label="Run Log",
                    lines=12,
                    max_lines=18,
                    interactive=False,
                    show_copy_button=True,
                )
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

        select_all_button.click(
            lambda: select_all_question_type_flags(),
            outputs=question_type_checkboxes,
        )
        deselect_all_button.click(
            lambda: deselect_all_question_type_flags(),
            outputs=question_type_checkboxes,
        )

        def _run_from_ui_with_progress(
            input_mode: str,
            uploaded_csv_path: str | None,
            drive_csv_path: str,
            api_key_path: str,
            output_dir: str,
            model_name: str,
            temperature: float,
            *question_type_flags: bool,
            progress=gr.Progress(track_tqdm=False),
        ):
            question_type_keys = selected_question_type_keys_from_flags(question_type_flags)
            yield from _run_from_ui(
                input_mode,
                uploaded_csv_path,
                drive_csv_path,
                api_key_path,
                output_dir,
                model_name,
                temperature,
                question_type_keys,
                progress=progress,
            )

        run_button.click(
            _run_from_ui_with_progress,
            inputs=[
                input_mode,
                upload_csv,
                drive_csv_path,
                api_key_path,
                output_dir,
                model_name,
                temperature,
                *question_type_checkboxes,
            ],
            outputs=[
                summary,
                run_log,
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
    if question_type_keys is None:
        return all_question_type_keys()

    normalized = list(question_type_keys)
    unknown = [key for key in normalized if key not in QUESTION_TYPES]
    if unknown:
        raise ValueError(f"Unknown question types: {', '.join(unknown)}")
    return normalized


def selected_question_type_keys_from_flags(question_type_flags: Sequence[bool]) -> list[str]:
    items = question_type_checklist_items()
    flags = list(question_type_flags)
    if len(flags) != len(items):
        raise ValueError("Question type selection is out of sync with the live registry.")
    return [item.key for item, selected in zip(items, flags) if selected]


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
    progress=None,
):
    console_progress = ConsoleProgressRenderer()
    try:
        run_log_lines: list[str] = []

        if api_key_path.strip():
            load_api_keys(api_key_path)
        elif not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not set. Provide an api_key.txt path or pre-load the env var.")

        selected_question_types = normalize_question_type_keys(question_type_keys)
        if not selected_question_types:
            raise ValueError("Select at least one question type before running QuestionGen.")
        expanded_subtype_count = sum(
            len(QUESTION_TYPE_SPECS_BY_FAMILY[family_key])
            for family_key in selected_question_types
            if family_key in QUESTION_TYPE_SPECS_BY_FAMILY
        )
        input_csv = resolve_input_csv(input_mode, uploaded_csv_path, drive_csv_path)
        output_csv, output_json, output_markdown = _artifact_paths(output_dir, input_csv)
        ensure_runtime_dependencies(
            bootstrap_hint=(
                "In Colab, rerun the setup cell once with `BOOTSTRAP_ENV=True`, "
                "then restart the runtime if `questiongen` was already imported."
            )
        )
        current_item = "Waiting for the batch worker to start."
        latest_notable_event = "Preparing batch run..."
        running_summary = _running_summary(
            input_mode=input_mode,
            input_csv=input_csv,
            selected_question_types=selected_question_types,
            expanded_subtype_count=expanded_subtype_count,
            completed_items=0,
            total_items=0,
            current_item=current_item,
            latest_notable_event=latest_notable_event,
        )
        yield _ui_outputs(
            summary=running_summary,
            run_log="",
        )

        verbose_planner_logging = resolve_verbose_planner_logging()
        planner_timeout_seconds = resolve_planner_timeout_seconds()
        planner_elapsed_log_interval_seconds = resolve_planner_elapsed_log_interval_seconds()
        console_progress.start()
        runner = compile_question_graph(
            structured_llm_factory=lambda schema, model_role="default": create_structured_llm(
                schema,
                model_name=model_name.strip() or None,
                model_role=model_role,
                temperature=float(temperature),
                request_timeout_seconds=planner_timeout_seconds,
            ),
            runtime_logger=console_progress.log_message if verbose_planner_logging else None,
            verbose_runtime=verbose_planner_logging,
            planner_timeout_seconds=planner_timeout_seconds,
            planner_elapsed_log_interval_seconds=planner_elapsed_log_interval_seconds,
        )
        progress_queue: queue.Queue[BatchProgressUpdate] = queue.Queue()
        worker_state: dict[str, object] = {"results": None, "error": None}

        def on_progress(update: BatchProgressUpdate) -> None:
            progress_queue.put(update)

        def execute_batch() -> None:
            try:
                results = run_batch_files(
                    input_csv=str(input_csv),
                    output_csv=str(output_csv),
                    question_type_keys=selected_question_types,
                    runner=runner,
                    output_markdown=str(output_markdown),
                    progress_callback=chain_progress_callbacks(on_progress, console_progress.callback),
                )
                _write_json_results(results, output_json)
                worker_state["results"] = results
            except Exception as exc:  # pragma: no cover - exercised through generator path
                worker_state["error"] = exc

        worker = threading.Thread(target=execute_batch, daemon=True)
        worker.start()

        while worker.is_alive() or not progress_queue.empty():
            try:
                update = progress_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if update.event == "started":
                line = update.message or "Batch run started."
                current_item = "Starting batch run."
                latest_notable_event = line
            elif update.event == "completed":
                line = update.message or "Batch run completed."
                current_item = "Batch run complete."
                latest_notable_event = line
            elif update.event == "item_started":
                line = _format_progress_line(update)
                current_item = _current_progress_item(update)
            else:
                line = _format_progress_line(update)
                current_item = _current_progress_item(update)

            if _should_log_progress_update(update):
                latest_notable_event = line
                run_log_lines.append(line)
                if len(run_log_lines) > 200:
                    del run_log_lines[:-200]

            if progress is not None:
                total = update.total_items or 1
                progress(
                    min(update.completed_items / total, 1.0),
                    desc=_progress_description(update),
                )

            running_summary = _running_summary(
                input_mode=input_mode,
                input_csv=input_csv,
                selected_question_types=selected_question_types,
                expanded_subtype_count=expanded_subtype_count,
                completed_items=update.completed_items,
                total_items=update.total_items,
                current_item=current_item,
                latest_notable_event=latest_notable_event,
            )
            yield _ui_outputs(
                summary=running_summary,
                run_log="\n".join(run_log_lines),
            )

        worker.join()
        if worker_state["error"] is not None:
            raise worker_state["error"]  # type: ignore[misc]

        results = worker_state["results"]
        if results is None:
            raise RuntimeError("Batch run finished without results.")
        results = results  # help type checkers locally
        console_progress.stop(success=True)

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
                f"- Progress: `{len(results)}/{len(results)}`",
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

        yield (
            summary,
            "\n".join(run_log_lines),
            preview,
            output_json.read_text(encoding="utf-8")[:12000],
            output_markdown.read_text(encoding="utf-8")[:12000],
            str(output_csv),
            str(output_json),
            str(output_markdown),
        )
    except Exception as exc:
        console_progress.stop(success=False, message=f"Run failed: {exc}")
        yield (
            "## Run Failed\n\n"
            f"- Error: `{exc}`",
            f"Run failed: {exc}",
            [],
            "",
            "",
            None,
            None,
            None,
        )


def _progress_description(update: BatchProgressUpdate) -> str:
    if update.event == "started":
        return "Starting batch run"
    if update.event == "completed":
        return "Batch run complete"
    subtype = update.question_subtype_key or update.question_type_key or "unknown"
    row_label = update.current_row_number or f"row {update.batch_row_id}"
    return f"{update.completed_items}/{max(update.total_items, 1)} | {row_label} | {subtype}"


def _format_progress_line(update: BatchProgressUpdate) -> str:
    subtype = update.question_subtype_key or update.question_type_key or "unknown"
    row_label = update.current_row_number or f"row {update.batch_row_id}"
    message = f" | {update.message}" if update.message else ""
    return (
        f"[{update.completed_items}/{max(update.total_items, 1)}] "
        f"{row_label} :: {subtype} -> {update.status}{message}"
    )


def _running_summary(
    *,
    input_mode: str,
    input_csv: Path,
    selected_question_types: Sequence[str],
    expanded_subtype_count: int,
    completed_items: int,
    total_items: int,
    current_item: str,
    latest_notable_event: str,
) -> str:
    progress_text = f"{completed_items}/{total_items}" if total_items else "preparing"
    return "\n".join(
        [
            "## Run In Progress",
            "",
            f"- Input mode: `{input_mode}`",
            f"- Input CSV: `{input_csv}`",
            f"- Question families: `{', '.join(selected_question_types)}`",
            f"- Expanded subtypes: `{expanded_subtype_count}`",
            f"- Progress: `{progress_text}`",
            f"- Current item: `{current_item}`",
            f"- Latest notable event: `{latest_notable_event}`",
        ]
    )


def _current_progress_item(update: BatchProgressUpdate) -> str:
    subtype = update.question_subtype_key or update.question_type_key or "unknown"
    row_label = update.current_row_number or f"row {update.batch_row_id}"
    status = update.status or "unknown"
    return f"{row_label} / {subtype}: {status}"


def _should_log_progress_update(update: BatchProgressUpdate) -> bool:
    return is_notable_progress_update(update)


def _ui_outputs(
    *,
    summary: str,
    run_log: str,
):
    return (
        summary,
        run_log,
        [],
        "",
        "",
        None,
        None,
        None,
    )
