# QuestionGen Colab Launcher Contract

## Purpose

This document defines the stable runtime contract for running QuestionGen from Google Colab with Google Drive as the user-controlled storage layer.

The launcher is responsible for runtime setup only. Reusable generation logic stays in the package.

## Notebook Roles

- `notebooks/runner_ui.ipynb` is the primary staff-facing launcher.
- `notebooks/runner_ui.ipynb` mounts Drive, defines standard paths, loads secrets, exposes minimal settings plus Advanced Settings, defaults branch selection to `main` through a notebook-side allowlist, clones the selected allowlisted pushed branch, and launches `questiongen.ui.gradio_app.create_app()` immediately.
- `notebooks/runner_ui.ipynb` does not run direct batch-generation cells before launching Gradio.
- `notebooks/runner_debug.ipynb` is the batch/debug notebook.
- `notebooks/runner_debug.ipynb` keeps direct `run_batch_files(...)`, output preview, and artifact inspection in notebook cells, with Gradio available only as an optional debugging add-on.
- `notebooks/runner.ipynb` and `notebooks/runner_pending.ipynb` remain in the repo for archival reference only until a later cleanup pass removes them with explicit confirmation.
- Archival notebooks are not part of the active compatibility contract and may lag behind current launcher rules or UI behavior.
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
- expose notebook-level minimal settings and Advanced Settings, including notebook-side `REPO_BRANCH_OPTIONS` plus `REPO_BRANCH`
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
- The live registry currently includes `sentence_insertion`, `paragraph_ordering`, `underlined_phrase_meaning`, `fill_in_the_blank`, `vocab`, and `grammar`.
- Launcher-derived defaults should include all of those broad families because the product direction is to run all registered families.
- `mood_atmosphere` remains implemented in code as dormant future work, but it is intentionally excluded from `QUESTION_TYPES` and from launcher-derived default selections.
- Subtype metadata is now part of the exported contract: `QuestionFormatKey`, `QuestionSubtypeKey`, and `QuestionSubtype`.

## Gradio UI Behavior

- The broad-family selector in Gradio should stay a vertically scrollable checklist rather than a compressed tag-style selector.
- The checklist defaults to all live `QUESTION_TYPES` families selected, with explicit `Select All` and `Deselect All` controls adjacent to it.
- The dormant `mood_atmosphere` family remains excluded because it is not part of `QUESTION_TYPES`.
- Gradio's progress bar is the primary live progress surface.
- The summary panel should stay compact and focus on progress, the current item, and the latest notable event.
- The run log should be lower-volume: keep start/completion, errors, and notable incompatibility or planning failures, but do not mirror every routine successful subtype completion.

## Deferred Batch Modes

- Provider-side batch-job APIs are intentionally deferred from the current UI pass.
- They are not just a slower version of the current synchronous planner flow; they require a separate submit-and-return workflow, persisted job metadata, and later result retrieval.
- Keep the current Gradio and batch path serial and synchronous for now.
- If throughput becomes the next bottleneck later, first evaluate limited concurrent normal API requests in the batch orchestration layer before attempting provider batch jobs or heavier service infrastructure.

## Output Artifacts

For the current debugging phase, the launcher should write:

- CSV for spreadsheet-style review
- JSON for structured debugging and downstream inspection
- Markdown as an optional human-readable artifact

Rules:

- CSV and JSON must represent the same `BatchResultRow` results.
- The checked-in `sample_data/generated_questions.json` file is a branch review artifact for logic quality, not the sole source of truth for the export contract.
- `QuestionTypeKey` remains the broad family key, while `QuestionFormatKey` and `QuestionSubtypeKey` identify the concrete runnable subtype row.
- Failed type/passage combinations must remain visible in the exported artifacts.
- Expected incompatibility between a valid passage and a specific question type should surface as `qtype_incompatibility_error`, not be collapsed into generic source or planner failure.
- `source_error` should be reserved for malformed inputs, failed source preparation, or broken deterministic prepared-source invariants.
- Deterministic plan violations discovered after LLM planning but before rendering should surface as `planning_error`, not `rendering_error`.
- Current `paragraph_ordering` policy is to reject passages before planning when no candidate four-block partition shows both strong adjacency and strong continuation-start signals; the planner prompt now receives ranked partition candidates rather than only raw boundary notes.
- Upstream LLM service failures, including `insufficient_quota`, should remain `planning_error`; do not introduce a separate exported quota status.
- After the first detected `insufficient_quota` failure in a batch, later row/type combinations may short-circuit to exported `planning_error` rows without further model calls, but the exported row count must still stay complete.
- Quota-driven `planning_error` rows are operational failures rather than live-family quality evidence and should be excluded from mixed-batch quality audits in favor of quota-clean reruns.
- `validation_passed` rows are expected to be structurally intact, including abbreviation-safe sentence preparation and fragment-safe rendered text, not just schema-valid fields.
- `underlined_phrase_meaning` should preserve the original passage exactly except for wrapping the chosen source span as `[밑줄]...[/밑줄]` in exported `student_paragraph`.
- `fill_in_the_blank` should preserve the original passage exactly except for replacing one selected source span with the single blank marker `_____` in exported `student_paragraph`.
- `vocab` now fans out into eight concrete live subtype rows under the broad family key:
  - `contextual_vocab_choice_5`
  - `contextual_vocab_best_paraphrase_choice_5`
  - `contextual_vocab_phrase_choice_5`
  - `contextual_vocab_correct_among_4_corrupted_5`
  - `contextual_vocab_error_1_among_5_5`
  - `contextual_vocab_error_1_among_5_polarity_scope_5`
  - `contextual_vocab_error_1_among_5_collocation_5`
  - `contextual_vocab_correct_among_3_corrupted_5`
- The three blank-choice vocab subtypes should preserve the passage except for one `_____` blank, and their choices should be exported in deterministic shuffled order keyed by `BatchRowId` plus subtype key.
- `contextual_vocab_best_paraphrase_choice_5` should forbid the unchanged source wording as both the correct answer and as a distractor, because the task is closest contextual paraphrase rather than source restoration.
- `contextual_vocab_phrase_choice_5` should use only multiword phrase-level targets and phrase-level options with tight slot-width preservation.
- The five hard vocab subtypes should preserve source-order numbered underlines in passage text and export marker answers `①`-`⑤` that point to the underlined target, not to a choice-list lexical option.
- `contextual_vocab_error_1_among_5_polarity_scope_5` should restrict its one corruption to polarity, degree, or scope drift.
- `contextual_vocab_error_1_among_5_collocation_5` should restrict its one corruption to collocation or selectional-restriction mismatch rather than broad opposite meaning.
- `grammar` now fans out into multiple controlled subtype rows under the broad family key, with subtype-specific compatibility gating.
- `mood_atmosphere` remains implemented but dormant. Its current subtype work stays out of default launcher and batch outputs until the other live families and output-quality work stabilize and it is explicitly reactivated later.
- Explanations should be teacher-facing Korean prose. Exported explanations should not mention internal sentence IDs (`S#`), gap IDs (`G#`), schema field names, or renderer mechanics.
- For `fill_in_the_blank`, `vocab`, and `grammar`, exported explanations should also avoid malformed memo fragments such as duplicated `...의미` wording and should lead with local supporting evidence rather than generic boilerplate.
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

Only `runner_ui.ipynb` and `runner_debug.ipynb` are maintained compatibility surfaces. `runner.ipynb` and `runner_pending.ipynb` may still be useful as historical reference, but they should not be used as acceptance targets for current launcher or UI behavior.

`runner_ui.ipynb` should be limited to these steps:

1. Mount Drive and define standard paths.
2. Load secrets from `api_key.txt`.
3. Expose minimal settings plus Advanced Settings, with `REPO_BRANCH_OPTIONS` currently limited to `main`, and default `REPO_BRANCH` to `main`.
4. Validate `REPO_BRANCH` against that allowlist, then clone and install the selected pushed branch with `git clone --branch REPO_BRANCH --single-branch ...`.
5. Launch `questiongen.ui.gradio_app.create_app()` immediately.

`runner_debug.ipynb` should be limited to these steps:

1. Mount Drive and define standard paths.
2. Load secrets from `api_key.txt`.
3. Expose minimal settings plus Advanced Settings, with `REPO_BRANCH_OPTIONS` currently limited to `main`, and default `REPO_BRANCH` to `main`.
4. Validate `REPO_BRANCH` against that allowlist, then clone and install the selected pushed branch with `git clone --branch REPO_BRANCH --single-branch ...`.
5. Build the runner and run direct batch generation.
6. Preview artifacts and optionally launch Gradio only as a debugging add-on.

Branch-selection notes:

- Colab can pull only branches that have already been pushed to the remote repository.
- Colab cannot automatically pull unpushed local-only workspace changes.
- The active launcher notebooks currently expose only `main` through `REPO_BRANCH_OPTIONS`.
- Expand that allowlist only when there is an intentional need to test another pushed branch from Colab.
- Broad family selection still starts from `QUESTION_TYPES`, while actual execution expands into subtype rows underneath each selected family.

The notebooks should not define:

- schemas
- prompts
- renderers
- validators
- graph internals
- copied package logic
- duplicate Gradio UI controls
