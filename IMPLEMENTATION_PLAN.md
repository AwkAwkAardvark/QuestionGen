# QuestionGen Refactor Plan v4

  ## Summary

  Refactor the current notebook-derived prototype into an installable package built around a **planning → deterministic rendering → validation** pipeline with an
  explicit split between shallow row validation and prepared-source eligibility.

  Wave 1 is strictly limited to:
  - `sentence_insertion`
  - real batch execution
  - CSV and Markdown export
  - notebook runner
  - Gradio placeholder only, with no real UI implementation

  Core rule:
  - **LLM selects / annotates**
  - **code renders**
  - **validators enforce**

  ## Key Changes

  ### Architecture and package layout

  Use this structure:

  ```text
  QuestionGen/
  ├── pyproject.toml
  ├── src/questiongen/
  │   ├── __init__.py
  │   ├── config.py
  │   ├── schemas.py
  │   ├── question_types.py
  │   ├── prompts.py
  │   ├── parsers.py
  │   ├── planners.py
  │   ├── renderers.py
  │   ├── validators.py
  │   ├── graph.py
  │   ├── batch.py
  │   ├── exporters.py
  │   └── ui/
  │       ├── __init__.py
  │       └── gradio_app.py
  ├── scripts/run_demo.py
  ├── notebooks/runner.ipynb
  └── tests/
  ```

  Responsibilities:
  - `schemas.py`: typed models, statuses, and state helpers
  - `question_types.py`: `sentence_insertion` registry metadata only in wave 1
  - `prompts.py`: planner prompts only
  - `parsers.py`: sentence parsing, gap construction, normalization
  - `planners.py`: structured planner calls for `sentence_insertion`
  - `renderers.py`: deterministic rendering for `sentence_insertion`
  - `validators.py`: source eligibility and final output validation
  - `graph.py`: graph construction and runner wiring only
  - `batch.py`: row-based batch execution plus DataFrame/file adapters
  - `exporters.py`: CSV/Markdown serialization
  - `ui/gradio_app.py`: placeholder only

  ### Graph design

  Use this graph:

  ```text
  input_check
  → source_prep
  → source_check
  → plan_question
  → render_question
  → validate_question
  ```

  Stage meanings:
  - `input_check`: shallow row/type validation only
  - `source_prep`: parse the paragraph into sentence and gap units
  - `source_check`: eligibility checks that require `PreparedSource`
  - `plan_question`: call planner LLM with a type-specific plan schema
  - `render_question`: deterministically build the final question
  - `validate_question`: verify consistency between source, plan, and rendered output

  Required statuses:

  ```python
  PipelineStatus = Literal[
      "pending",
      "input_error",
      "input_passed",
      "source_prepared",
      "source_error",
      "source_passed",
      "planning_error",
      "planned",
      "rendering_error",
      "rendered",
      "validation_error",
      "validation_passed",
  ]
  ```

  Routing rules:
  - `input_check` failure ends the graph
  - `source_check` failure ends the graph
  - `plan_question` failure ends the graph
  - `render_question` failure ends the graph
  - `validate_question` always ends the graph

  Keep `graph.py` generic and driven by `QuestionTypeSpec`, but only register `sentence_insertion` in wave 1.

  ### Core schemas and interfaces

  Use these wave-1 models:

  ```python
  class SourceUnit(BaseModel):
      id: str
      kind: Literal["sentence"]
      text: str
      index: int

  class GapUnit(BaseModel):
      id: str
      kind: Literal["gap"]
      index: int
      before_unit_id: str | None
      after_unit_id: str | None

  class PreparedSource(BaseModel):
      sentence_units: list[SourceUnit]
      gap_units: list[GapUnit]

  class SentenceInsertionPlan(BaseModel):
      target_unit_ids: list[str]
      selected_gap_ids: list[str]
      correct_gap_id: str
      explanation: str
  ```

  Wave 1 `SentenceInsertionPlan` rules:
  - exactly one sentence ID in `target_unit_ids`
  - exactly 5 unique gap IDs in `selected_gap_ids`
  - `correct_gap_id` must be one of `selected_gap_ids`
  - `explanation` must be Korean

  Rendered artifact:

  ```python
  class GeneratedQuestion(BaseModel):
      OriginalQuestionNumber: int
      QuestionType: str
      student_paragraph: str
      question_stem: str
      given_sentence: str | None = None
      choices: list[str] | None = None
      answer: str
      explanation: str | None = None
  ```

  State:

  ```python
  class QuestionState(TypedDict):
      source_paragraph: str
      OriginalQuestionNumber: int
      QuestionTypeKey: str
      prepared_source: PreparedSource | None
      plan: BaseModel | None
      generated: GeneratedQuestion | None
      status: PipelineStatus
      errors: list[str]
  ```

  Add:

  ```python
  def make_initial_state(
      source_paragraph: str,
      original_question_number: int,
      question_type_key: str,
  ) -> QuestionState:
      ...
  ```

  Use `Field(default_factory=list)` for all list defaults.

  ### Question type registry and config

  Use:

  ```python
  @dataclass(frozen=True)
  class QuestionTypeSpec:
      label_ko: str
      planner_prompt: str
      question_stem: str
      unit_level: str
      renderer_key: str
      validator_key: str
      plan_schema: type[BaseModel]
      min_source_units: int | None = None
      choice_count: int | None = None
  ```

  Wave 1 `sentence_insertion` metadata must include:
  - Korean label
  - static Korean stem
  - planner prompt
  - renderer key
  - validator key
  - `SentenceInsertionPlan`
  - minimum sentence count
  - choice count = 5

  `config.py` must expose:
  - `create_llm(...)`
  - `create_structured_llm(output_schema, model_name=None, temperature=None)`

  Do not:
  - import `google.colab`
  - hardcode Drive paths
  - create runtime-dependent model globals at import time

  ### Batch and export surface

  Use typed row models:

  ```python
  class BatchInputRow(BaseModel):
      OriginalQuestionNumber: int
      source_paragraph: str

  class BatchResultRow(BaseModel):
      OriginalQuestionNumber: int
      QuestionTypeKey: str
      QuestionType: str | None = None
      status: PipelineStatus
      errors: list[str] = Field(default_factory=list)
      source_paragraph: str
      student_paragraph: str | None = None
      question_stem: str | None = None
      given_sentence: str | None = None
      choices: list[str] | None = None
      answer: str | None = None
      explanation: str | None = None
  ```

  Batch execution must accept a compiled graph or runner dependency. It must not construct model state implicitly inside the batch API.

  Required shape:
  - `run_batch_rows(rows, question_type_keys, runner) -> list[BatchResultRow]`
  - `run_batch_dataframe(df, question_type_keys, runner) -> pd.DataFrame`
  - `run_batch_files(input_csv, output_csv, question_type_keys, runner, output_markdown=None) -> list[BatchResultRow]`

  Runner contract:
  - accept a fully initialized dependency capable of executing one item for one question type
  - the simplest wave-1 form is a compiled LangGraph object with `.invoke(state)`
  - alternatively allow a callable adapter with equivalent behavior, but pick one contract and use it consistently across all batch APIs

  Recommended wave-1 choice:
  - standardize on a compiled graph object as `runner`
  - `batch.py` builds initial state and invokes `runner.invoke(...)`
  - model creation and graph compilation happen outside batch execution, in the notebook/script layer or a thin factory helper in `graph.py`

  `run_batch_files(...)` must:
  - read CSV
  - convert rows into typed input models
  - run execution through the provided runner
  - write CSV output
  - optionally write Markdown output
  - return typed result rows

  Exporters must consume `BatchResultRow` objects and provide:
  - CSV serialization
  - Markdown serialization for staff review

  ## Implementation Sequence

  1. Create package skeleton and `pyproject.toml`.
  2. Extract `schemas.py`, `question_types.py`, and `parsers.py`.
  3. Fix notebook-order artifacts during the extraction.
  4. Add `PreparedSource`, `SentenceInsertionPlan`, batch row models, `PipelineStatus`, and `make_initial_state(...)`.
  5. Implement sentence parsing and explicit gap construction in `parsers.py`.
  6. Implement `input_check` for shallow row/type validation only.
  7. Implement `source_check` for sentence/gap eligibility after `PreparedSource` exists.
  8. Implement the sentence-insertion planner schema and planner call.
  9. Implement deterministic sentence-insertion rendering.
  10. Implement sentence-insertion validation.
  11. Build generic graph wiring with the six-stage flow and metadata-based dispatch.
  12. Expose graph compilation from `graph.py`, with dependencies injected from `config.py`.
  13. Implement row-based batch execution that requires a provided compiled graph/runner.
  14. Add DataFrame and file-based adapters.
  15. Add CSV and Markdown exporters.
  16. Move sample execution into `scripts/run_demo.py`.
  17. Create a thin Colab notebook that clones, installs, creates the runner, and calls demo or batch entry points.
  18. Add `ui/gradio_app.py` as a placeholder module only, with no substantive UI logic.

  ## Test Plan

  Parser tests:
  - sentences become ordered `S0...Sn`
  - gaps become `G0...Gn`
  - gap adjacency is correct at start, middle, and end
  - normalization is stable

  Source check tests:
  - too few sentences fails after `PreparedSource` exists
  - malformed sentence/gap structures fail with `source_error`
  - valid prepared source transitions to `source_passed`

  Planner tests:
  - planner output validates against `SentenceInsertionPlan`
  - invalid planner payloads fail as `planning_error`

  Renderer tests:
  - selected sentence becomes `given_sentence`
  - target sentence is removed from `student_paragraph`
  - all non-target sentences are preserved exactly once and in order
  - exactly five selected gaps are rendered as markers
  - each marker appears exactly once
  - answer marker maps correctly from `correct_gap_id`
  - `QuestionType`, `question_stem`, and `choices` come from metadata

  Validator tests:
  - unknown target sentence ID fails
  - unknown gap IDs fail
  - duplicate selected gap IDs fail
  - `correct_gap_id` outside `selected_gap_ids` fails
  - missing preserved sentence fails
  - marker count mismatch fails
  - invalid answer or choice set fails

  Batch tests:
  - one row × one type produces one result
  - one row × multiple types produces multiple results
  - per-row failure is captured without aborting the whole batch
  - DataFrame adapter matches row-based execution
  - file-based runner writes CSV and optional Markdown consistently
  - batch APIs fail clearly if no valid runner/compiled graph is provided

  ## Assumptions and defaults

  - Wave 1 supports only `sentence_insertion`.
  - `SourceUnit` is sentence-only; gaps are first-class parallel units.
  - The planner returns IDs and explanation only, never final student-facing text.
  - Batch APIs are dependency-injected and must not create their own model/graph state.
  - The runner dependency will be a compiled graph object in wave 1 unless repo exploration reveals a better existing abstraction.
  - Colab is a launcher only; package code remains notebook-agnostic.
  - pandas is an adapter dependency, not the core execution contract.
  - Gradio remains a placeholder and is explicitly out of implementation scope for wave 1.