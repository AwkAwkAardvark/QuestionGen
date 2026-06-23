# QuestionGen Colab Launcher Contract

## Purpose

This document defines the stable runtime contract for running QuestionGen from Google Colab with Google Drive as the user-controlled storage layer.

The launcher is responsible for runtime setup only. Reusable generation logic stays in the package.

## Drive Layout

Use a runtime data folder that is separate from the cloned GitHub repository:

```text
MyDrive/
└── QuestionGenData/
    ├── secrets/
    │   └── api_key.txt
    ├── input/
    │   └── questions.csv
    ├── output/
    └── logs/
```

Rules:

- `QuestionGenData/` is runtime state, not source code.
- The GitHub repo should be cloned into the Colab runtime filesystem, not stored as the working code directory inside `QuestionGenData/`.
- The notebook may live in Drive, including inside `QuestionGenData/`, but it is still a launcher artifact rather than package logic.
- `OriginalQuestionNumber` is treated as an opaque source label, not a numeric-only field.

## Secret Loading

Secrets are user-controlled and stored in Drive as a text file. The launcher reads that file and loads environment variables before building the runner.

Expected `api_key.txt` format:

```txt
OPENAI_API_KEY=sk-...
QUESTIONGEN_MODEL=gpt-5-mini
QUESTIONGEN_TEMPERATURE=0
```

Rules:

- Secret-file loading is a launcher concern only.
- `src/questiongen/` must not read secret files directly.
- Environment variables remain the final runtime interface consumed by the LLM client layer.
- Model and temperature values in the secret file are launcher configuration, not package-owned defaults.
- The current MVP policy is one shared default model, `gpt-5-mini`; launcher overrides still win through `QUESTIONGEN_MODEL` or explicit `model_name`.
- Per-question-type model routing is intentionally deferred until after the live pipeline is stable.

## Package and Launcher Boundary

Package responsibilities:

- expose reusable runner, batch, schema, and registry primitives
- stay notebook-agnostic
- stay Drive-agnostic
- stay secret-source agnostic

Launcher responsibilities:

- mount Drive
- define Drive paths
- load `api_key.txt`
- clone and install the repo
- create the structured LLM-backed runner
- derive the active question types
- run batch generation
- write artifacts back to Drive

Hard constraints:

- do not import `google.colab` inside `src/questiongen/`
- do not hardcode Drive paths inside `src/questiongen/`
- do not move file-based secret loading into `src/questiongen/`
- do not duplicate package business logic inside notebook cells

## Current Package Contract

The current backend contract is:

- build the runner with `compile_question_graph(...)`
- pass that runner into `run_batch_files(...)` as `runner=...`
- pass explicit `question_type_keys`

Current launcher-safe pattern:

```python
from questiongen.batch import run_batch_files
from questiongen.config import create_structured_llm
from questiongen.graph import compile_question_graph
from questiongen.question_types import QUESTION_TYPES

question_type_keys = list(QUESTION_TYPES.keys())

runner = compile_question_graph(
    structured_llm_factory=lambda schema: create_structured_llm(
        schema,
        model_name=model_name,
        temperature=temperature,
    )
)

results = run_batch_files(
    input_csv=...,
    output_csv=...,
    question_type_keys=question_type_keys,
    runner=runner,
    output_markdown=...,
)
```

Notes:

- The user-facing product direction is "run all registered question types."
- The current API still requires explicit `question_type_keys`, so the launcher must derive them from `QUESTION_TYPES`.
- This preserves the current backend API while delivering the intended launcher behavior.
- Internal deterministic behavior such as display shuffling should rely on `BatchRowId`, which is generated from input row order inside the batch layer.
- The live registry currently includes `sentence_insertion`, `paragraph_ordering`, `underlined_phrase_meaning`, `fill_in_the_blank`, `vocab`, and `grammar`.
- This MVP rollout intentionally favors family coverage over item polish for `fill_in_the_blank`, `vocab`, and `grammar`; launcher-derived defaults should still include them because the product direction is to run all registered families.
- The `mood_atmosphere` implementation remains in the codebase as deferred future work, but it is intentionally excluded from `QUESTION_TYPES` and from launcher-derived default selections.

## Output Artifacts

For the current debugging phase, the launcher should write:

- CSV for spreadsheet-style review
- JSON for structured debugging and downstream inspection
- Markdown as an optional human-readable artifact

Rules:

- CSV and JSON must represent the same `BatchResultRow` results.
- Failed type/passage combinations must remain visible in the exported artifacts.
- Expected incompatibility between a valid passage and a specific question type should surface as `qtype_incompatibility_error`, not be collapsed into generic source or planner failure.
- `source_error` should be reserved for malformed inputs, failed source preparation, or broken deterministic prepared-source invariants.
- Deterministic plan violations discovered after LLM planning but before rendering should surface as `planning_error`, not `rendering_error`.
- Upstream LLM service failures, including `insufficient_quota`, should remain `planning_error`; do not introduce a separate exported quota status.
- After the first detected `insufficient_quota` failure in a batch, later row/type combinations may short-circuit to exported `planning_error` rows without further model calls, but the exported row count must still stay complete.
- Quota-driven `planning_error` rows are operational failures rather than live-family quality evidence and should be excluded from mixed-batch quality audits in favor of quota-clean reruns.
- `validation_passed` rows are expected to be structurally intact, including abbreviation-safe sentence preparation and fragment-safe rendered text, not just schema-valid fields.
- `underlined_phrase_meaning` should preserve the original passage exactly except for wrapping the chosen source span as `[밑줄]...[/밑줄]` in exported `student_paragraph`.
- `fill_in_the_blank` should preserve the original passage exactly except for replacing one selected source span with the single blank marker `_____` in exported `student_paragraph`.
- `vocab` and `grammar` should preserve the original passage except for the agreed numbered underline wrappers and exactly one intended corruption among the five numbered targets.
- The deferred `mood_atmosphere` implementation must not appear in default launcher or batch outputs unless it is explicitly reactivated in the live registry later.
- Explanations should be teacher-facing Korean prose. Exported explanations should not mention internal sentence IDs (`S#`), gap IDs (`G#`), schema field names, or renderer mechanics.
- Teacher-facing explanation writing is now treated as a post-render concern rather than as part of structural planning for the live types.
- Planner rationale may remain internal, but exported explanations for the live types are now rewritten from rendered item context and textual evidence rather than copied directly from planner-internal IDs or schema fields.
- The launcher may write JSON directly from `result.model_dump()` payloads until a dedicated package-level JSON exporter is added.
- Exported results should preserve both the original source label (`OriginalQuestionNumber`) and the internal deterministic row handle (`BatchRowId`).
- Model selection remains launcher-controlled for now; the launcher should not assume any live per-type routing policy yet.

## Notebook Shape

The canonical Colab notebook should be launcher-only and limited to these steps:

1. Mount Drive and define paths.
2. Load secrets from `api_key.txt`.
3. Clone and install the GitHub repo.
4. Build the runner and run batch generation.
5. Preview and optionally download outputs.

The notebook should not define:

- schemas
- prompts
- renderers
- validators
- graph internals
- copied package logic
