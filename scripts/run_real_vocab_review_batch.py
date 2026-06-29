from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from questiongen.batch import run_batch_files
from questiongen.config import create_structured_llm
from questiongen.graph import compile_question_graph


DEFAULT_INPUT_CSV = Path("sample_data/Olymforce_cleaned_final.csv")
DEFAULT_OUTPUT_DIR = Path("artifacts/real_vocab_review_batch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a fresh real vocab-only batch on the checked-in 34-passage "
            "review corpus and write CSV, JSON, Markdown, and summary artifacts."
        )
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help="CSV with OriginalQuestionNumber and source_paragraph columns.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for review artifacts.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-mini",
        help="OpenAI chat model to use for structured planning.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the structured planner.",
    )
    return parser.parse_args()


def build_summary(*, input_csv: Path, output_dir: Path, model: str, results: list[object]) -> dict[str, object]:
    status_counts = Counter(result.status for result in results)
    subtype_status_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    accepted_rows_by_subtype: dict[str, list[str]] = defaultdict(list)
    planning_error_examples: dict[str, list[dict[str, object]]] = defaultdict(list)

    for result in results:
        subtype_key = result.QuestionSubtypeKey or result.QuestionTypeKey
        subtype_status_counts[subtype_key][result.status] += 1
        if result.status == "validation_passed":
            accepted_rows_by_subtype[subtype_key].append(result.OriginalQuestionNumber)
        if result.status == "planning_error" and len(planning_error_examples[subtype_key]) < 3:
            planning_error_examples[subtype_key].append(
                {
                    "OriginalQuestionNumber": result.OriginalQuestionNumber,
                    "errors": result.errors,
                }
            )

    return {
        "model": model,
        "input_csv": str(input_csv),
        "output_dir": str(output_dir),
        "row_count": len(results),
        "status_counts": dict(status_counts),
        "subtype_status_counts": {
            subtype_key: dict(counts)
            for subtype_key, counts in sorted(subtype_status_counts.items())
        },
        "accepted_row_ids_by_subtype": {
            subtype_key: row_ids
            for subtype_key, row_ids in sorted(accepted_rows_by_subtype.items())
        },
        "planning_error_examples": {
            subtype_key: rows
            for subtype_key, rows in sorted(planning_error_examples.items())
        },
    }


def main() -> None:
    args = parse_args()

    if not args.input_csv.exists():
        raise SystemExit(f"Input CSV does not exist: {args.input_csv}")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is required for the real vocab review batch. "
            "Provide it in the environment before running this script."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_dir / "results.csv"
    output_markdown = args.output_dir / "results.md"
    output_json = args.output_dir / "results.json"
    summary_json = args.output_dir / "summary.json"

    runner = compile_question_graph(
        structured_llm_factory=lambda schema: create_structured_llm(
            schema,
            model_name=args.model,
            temperature=args.temperature,
        )
    )

    results = run_batch_files(
        args.input_csv,
        output_csv,
        ["vocab"],
        runner,
        output_markdown=output_markdown,
    )

    output_json.write_text(
        json.dumps([result.model_dump() for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = build_summary(
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        model=args.model,
        results=results,
    )
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
