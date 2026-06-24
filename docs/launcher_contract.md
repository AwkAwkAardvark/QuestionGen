# QuestionGen Colab Launcher Contract

## Purpose

This document defines the stable runtime contract for running QuestionGen from Google Colab with Google Drive as the user-controlled storage layer.

The launcher is responsible for runtime setup only. Reusable generation logic stays in the package.

## Notebook Roles

- `notebooks/runner_ui.ipynb` is the primary staff-facing launcher.
- `notebooks/runner_ui.ipynb` mounts Drive, defines standard paths, loads secrets, exposes minimal settings plus Advanced Settings, keeps temporary branch selection in a small notebook-side allowlist, clones the selected allowlisted pushed branch, and launches `questiongen.ui.gradio_app.create_app()` immediately.
- `notebooks/runner_ui.ipynb` does not run direct batch-generation cells before launching Gradio.
- `notebooks/runner_debug.ipynb` is the batch/debug notebook.
- `notebooks/runner_debug.ipynb` keeps direct `run_batch_files(...)`, output preview, and artifact inspection in notebook cells, with Gradio available only as an optional debugging add-on.
- `notebooks/runner.ipynb` and `notebooks/runner_pending.ipynb` remain in the repo for archival reference only until a later cleanup pass removes them with explicit confirmation.
- Upload-vs-Drive-path selection belongs inside the Gradio UI, not in notebook-specific UI logic.

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
- expose notebook-level minimal settings and Advanced Settings, including temporary notebook-side `REPO_BRANCH_OPTIONS` plus `REPO_BRANCH`
- validate the selected branch against that allowlist before clone/install
- clone and install the selected allowlisted pushed repo branch
- launch the Gradio UI from `runner_ui.ipynb`
- create the structured LLM-backed runner for batch/debug flows
- derive the active question types
- run batch generation in the debug flow or inside the Gradio app
- write artifacts back to Drive

Hard constraints:

- do not import `google.colab` inside `src/questiongen/`
- do not hardcode Drive paths inside `src/questiongen/`
- do not move file-based secret loading into `src/questiongen/`
- do not duplicate package business logic inside notebook cells
- do not duplicate Gradio UI behavior in notebook cells

## Current Package Contract

The current backend contract is:

- build the runner with `compile_question_graph(...)`
- pass that runner into `run_batch_files(...)` as `runner=...`
- pass explicit broad-family `question_type_keys`

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
- The current API still requires explicit broad-family `question_type_keys`, so the launcher must derive them from `QUESTION_TYPES`.
- Each selected broad family now expands into one or more live concrete subtype runs inside the batch layer.
- Exported row counts therefore scale with `input rows x enabled subtype count`, not merely `input rows x broad family count`.
- This preserves the current backend API while delivering the intended launcher behavior.
- Internal deterministic behavior such as display shuffling should rely on `BatchRowId`, which is generated from input row order inside the batch layer.
- The live registry currently includes `sentence_insertion`, `paragraph_ordering`, `mood_atmosphere`, `underlined_phrase_meaning`, `fill_in_the_blank`, `vocab`, and `grammar`.
- Launcher-derived defaults should include all of those broad families because the product direction is to run all registered families.
- Subtype metadata is now part of the exported contract: `QuestionFormatKey`, `QuestionSubtypeKey`, and `QuestionSubtype`.

## Output Artifacts

For the current debugging phase, the launcher should write:

- CSV for spreadsheet-style review
- JSON for structured debugging and downstream inspection
- Markdown as an optional human-readable artifact

Rules:

- CSV and JSON must represent the same `BatchResultRow` results.
- `QuestionTypeKey` remains the broad family key, while `QuestionFormatKey` and `QuestionSubtypeKey` identify the concrete runnable subtype row.
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
- `vocab` now includes both a five-target contextual error subtype and a single-target five-choice lexical selection subtype.
- `grammar` now fans out into multiple controlled subtype rows under the broad family key, with subtype-specific compatibility gating.
- `mood_atmosphere` is live again and currently expands into three concrete subtype rows.
- Explanations should be teacher-facing Korean prose. Exported explanations should not mention internal sentence IDs (`S#`), gap IDs (`G#`), schema field names, or renderer mechanics.
- Teacher-facing explanation writing is now treated as a post-render concern rather than as part of structural planning for the live types.
- Planner rationale may remain internal, but exported explanations for the live types are now rewritten from rendered item context and textual evidence rather than copied directly from planner-internal IDs or schema fields.
- The launcher may write JSON directly from `result.model_dump()` payloads until a dedicated package-level JSON exporter is added.
- Exported results should preserve both the original source label (`OriginalQuestionNumber`) and the internal deterministic row handle (`BatchRowId`).
- Model selection remains launcher-controlled for now; the launcher should not assume any live per-type routing policy yet.

## Notebook Shape

The current Colab surface is intentionally split:

1. `runner_ui.ipynb`
2. `runner_debug.ipynb`
3. archival notebooks kept only for reference

`runner_ui.ipynb` should be limited to these steps:

1. Mount Drive and define standard paths.
2. Load secrets from `api_key.txt`.
3. Expose minimal settings plus Advanced Settings, with a temporary manual `REPO_BRANCH_OPTIONS` allowlist of `hail-mary-finish-everything`, `ui-launcher-cleanup`, and `main`, and default `REPO_BRANCH` to `hail-mary-finish-everything`.
4. Validate `REPO_BRANCH` against that allowlist, then clone and install the selected pushed branch with `git clone --branch REPO_BRANCH --single-branch ...`.
5. Launch `questiongen.ui.gradio_app.create_app()` immediately.

`runner_debug.ipynb` should be limited to these steps:

1. Mount Drive and define standard paths.
2. Load secrets from `api_key.txt`.
3. Expose minimal settings plus Advanced Settings, with a temporary manual `REPO_BRANCH_OPTIONS` allowlist of `hail-mary-finish-everything`, `ui-launcher-cleanup`, and `main`, and default `REPO_BRANCH` to `hail-mary-finish-everything`.
4. Validate `REPO_BRANCH` against that allowlist, then clone and install the selected pushed branch with `git clone --branch REPO_BRANCH --single-branch ...`.
5. Build the runner and run direct batch generation.
6. Preview artifacts and optionally launch Gradio only as a debugging add-on.

Branch-selection notes:

- Colab can pull only branches that have already been pushed to the remote repository.
- Colab cannot automatically pull unpushed local-only workspace changes.
- The active launcher notebooks intentionally expose only a small manually maintained `REPO_BRANCH_OPTIONS` allowlist while branch churn is still high.
- The current temporary allowlist is `hail-mary-finish-everything`, `ui-launcher-cleanup`, and `main`.
- Refresh that allowlist before commit/push whenever the active pushed branch set changes.
- Broad family selection still starts from `QUESTION_TYPES`, while actual execution expands into subtype rows underneath each selected family.

The notebooks should not define:

- schemas
- prompts
- renderers
- validators
- graph internals
- copied package logic
- duplicate Gradio UI controls
