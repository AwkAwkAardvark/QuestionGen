from __future__ import annotations

PLACEHOLDER_MESSAGE = (
    "Gradio UI is intentionally out of scope for wave 1. "
    "Use the batch or demo entry points instead."
)


def create_app() -> None:
    raise NotImplementedError(PLACEHOLDER_MESSAGE)
