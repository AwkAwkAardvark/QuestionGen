from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from questiongen.batch import run_batch_files
from questiongen.config import create_structured_llm
from questiongen.graph import compile_question_graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a small real sentence-insertion batch with an injected structured LLM."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("sample_data/real_sentence_insertion_batch.csv"),
        help="CSV with OriginalQuestionNumber as a source label plus source_paragraph.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/real_sentence_insertion_batch"),
        help="Directory for CSV and Markdown batch outputs.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI chat model to use for structured planning.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for the real batch acceptance run.")

    output_csv = args.output_dir / "results.csv"
    output_markdown = args.output_dir / "results.md"

    runner = compile_question_graph(
        structured_llm_factory=lambda schema: create_structured_llm(
            schema,
            model_name=args.model,
            temperature=0,
        )
    )

    results = run_batch_files(
        args.input_csv,
        output_csv,
        ["sentence_insertion"],
        runner,
        output_markdown=output_markdown,
    )

    counts = Counter(result.status for result in results)
    summary = {
        "model": args.model,
        "input_csv": str(args.input_csv),
        "output_csv": str(output_csv),
        "output_markdown": str(output_markdown),
        "status_counts": dict(counts),
        "rows": [
            {
                "OriginalQuestionNumber": result.OriginalQuestionNumber,
                "BatchRowId": result.BatchRowId,
                "status": result.status,
                "errors": result.errors,
                "answer": result.answer,
            }
            for result in results
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
