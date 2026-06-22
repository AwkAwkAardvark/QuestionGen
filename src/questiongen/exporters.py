from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .schemas import BatchResultRow

CSV_FIELDS = [
    "OriginalQuestionNumber",
    "BatchRowId",
    "QuestionTypeKey",
    "QuestionType",
    "status",
    "errors",
    "source_paragraph",
    "student_paragraph",
    "question_stem",
    "given_sentence",
    "choices",
    "answer",
    "explanation",
]


def batch_results_to_dicts(results: Iterable[BatchResultRow]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in results:
        payload = result.model_dump()
        payload["errors"] = json.dumps(payload["errors"], ensure_ascii=False)
        payload["choices"] = (
            json.dumps(payload["choices"], ensure_ascii=False)
            if payload["choices"] is not None
            else None
        )
        rows.append(payload)
    return rows


def write_results_csv(results: Iterable[BatchResultRow], output_path: str | Path) -> None:
    rows = batch_results_to_dicts(results)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def batch_results_to_markdown(results: Iterable[BatchResultRow]) -> str:
    lines = ["# QuestionGen Batch Results", ""]
    for result in results:
        lines.append(
            f"## row {result.BatchRowId} / {result.OriginalQuestionNumber} / {result.QuestionTypeKey} / {result.status}"
        )
        lines.append(f"- BatchRowId: {result.BatchRowId}")
        if result.errors:
            lines.append(f"- Errors: {' | '.join(result.errors)}")
        else:
            lines.append("- Errors: none")
        lines.append(f"- Source: {result.source_paragraph}")
        if result.student_paragraph:
            lines.append(f"- Student Paragraph: {result.student_paragraph}")
        if result.given_sentence:
            lines.append(f"- Given Sentence: {result.given_sentence}")
        if result.answer:
            lines.append(f"- Answer: {result.answer}")
        if result.explanation:
            lines.append(f"- Explanation: {result.explanation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_results_markdown(results: Iterable[BatchResultRow], output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(batch_results_to_markdown(results), encoding="utf-8")
