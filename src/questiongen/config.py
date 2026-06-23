from __future__ import annotations

from typing import Any


def create_llm(
    *,
    model_name: str | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name or "gpt-5-mini",
        temperature=0.0 if temperature is None else temperature,
        **kwargs,
    )


def create_structured_llm(
    output_schema: type,
    *,
    model_name: str | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> Any:
    llm = create_llm(model_name=model_name, temperature=temperature, **kwargs)
    return llm.with_structured_output(output_schema)
