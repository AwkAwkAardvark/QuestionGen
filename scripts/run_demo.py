from __future__ import annotations

import json

from questiongen.batch import run_batch_rows
from questiongen.demo import DEMO_PARAGRAPH, build_structured_llm
from questiongen.graph import compile_question_graph
from questiongen.schemas import BatchInputRow


def main() -> None:
    runner = compile_question_graph(structured_llm_factory=build_structured_llm)
    rows = [BatchInputRow(OriginalQuestionNumber="demo-1", BatchRowId=0, source_paragraph=DEMO_PARAGRAPH)]
    results = run_batch_rows(rows, ["sentence_insertion"], runner)
    print(json.dumps([row.model_dump() for row in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
