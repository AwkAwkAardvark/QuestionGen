from __future__ import annotations

import os
from typing import Any

DEFAULT_PLANNER_TIMEOUT_SECONDS = 180.0
DEFAULT_PLANNER_ELAPSED_LOG_INTERVAL_SECONDS = 30.0
_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}


def resolve_verbose_planner_logging(enabled: bool | None = None) -> bool:
    if enabled is not None:
        return enabled
    raw_value = os.getenv("QUESTIONGEN_VERBOSE_PLANNER", "").strip().lower()
    return raw_value in _TRUE_ENV_VALUES


def resolve_planner_timeout_seconds(timeout_seconds: float | None = None) -> float | None:
    if timeout_seconds is not None:
        _validate_positive_timeout(timeout_seconds, env_name="planner_timeout_seconds")
        return timeout_seconds
    raw_value = os.getenv("QUESTIONGEN_PLANNER_TIMEOUT_SECONDS", "").strip()
    if not raw_value:
        return DEFAULT_PLANNER_TIMEOUT_SECONDS
    try:
        resolved = float(raw_value)
    except ValueError as exc:
        raise ValueError("QUESTIONGEN_PLANNER_TIMEOUT_SECONDS must be a positive number.") from exc
    _validate_positive_timeout(resolved, env_name="QUESTIONGEN_PLANNER_TIMEOUT_SECONDS")
    return resolved


def resolve_planner_elapsed_log_interval_seconds(interval_seconds: float | None = None) -> float:
    if interval_seconds is not None:
        _validate_positive_timeout(interval_seconds, env_name="planner_elapsed_log_interval_seconds")
        return interval_seconds
    raw_value = os.getenv("QUESTIONGEN_PLANNER_ELAPSED_LOG_SECONDS", "").strip()
    if not raw_value:
        return DEFAULT_PLANNER_ELAPSED_LOG_INTERVAL_SECONDS
    try:
        resolved = float(raw_value)
    except ValueError as exc:
        raise ValueError("QUESTIONGEN_PLANNER_ELAPSED_LOG_SECONDS must be a positive number.") from exc
    _validate_positive_timeout(resolved, env_name="QUESTIONGEN_PLANNER_ELAPSED_LOG_SECONDS")
    return resolved


def create_llm(
    *,
    model_name: str | None = None,
    temperature: float | None = None,
    request_timeout_seconds: float | None = None,
    **kwargs: Any,
) -> Any:
    from langchain_openai import ChatOpenAI

    if "request_timeout" not in kwargs:
        resolved_timeout = resolve_planner_timeout_seconds(request_timeout_seconds)
        if resolved_timeout is not None:
            kwargs["request_timeout"] = resolved_timeout

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
    request_timeout_seconds: float | None = None,
    **kwargs: Any,
) -> Any:
    llm = create_llm(
        model_name=model_name,
        temperature=temperature,
        request_timeout_seconds=request_timeout_seconds,
        **kwargs,
    )
    return llm.with_structured_output(output_schema)


def _validate_positive_timeout(value: float, *, env_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{env_name} must be greater than zero.")
