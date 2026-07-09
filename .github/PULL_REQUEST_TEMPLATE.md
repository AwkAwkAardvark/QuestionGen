## Summary

One short paragraph describing what this branch changed.

## Why Now

Why this work belongs in this branch now.

## Current Graph Shape

Show the current graph or stage path when this PR touches graph-backed or staged runtime flow. Use plain ASCII and mark impacted nodes inline.

Examples:

```text
input_check -> prepare_source -> source_check -> design -> [changed] planner -> plan_check -> render -> build_explanation_context -> write_explanation -> validate_generated_question
```

```text
N/A - this PR does not change graph or staged runtime flow.
```

If graph shape is unchanged but logic inside an existing node changed, say that directly and name the node.

## Runtime / Contract Changes

Call out user-visible behavior, APIs, statuses, exports, launcher behavior, or say `None`.

## Docs Updated

List durable docs updated in this work cycle, or say `None`.

## Verification

List the exact commands you ran, what they covered, and any gaps.

```text
python -m unittest tests.test_graph
python -m unittest discover -s tests
```

If something relevant was not run, say so directly.

## Colab / Notebook Validation

Record factual notebook validation details when relevant: branch used, date, notebook used, artifacts reviewed, restart or bootstrap implications, or `N/A`.

## Known Risks / Follow-Ups

List intentional non-blocking follow-ups or known risks, or say `None`.
