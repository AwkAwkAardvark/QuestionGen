from __future__ import annotations

from dataclasses import MISSING, dataclass
from typing import Any, ClassVar, get_origin

try:
    from pydantic import BaseModel, Field, ValidationError, model_validator
except ImportError:
    class ValidationError(ValueError):
        """Fallback validation error when pydantic is unavailable."""


    @dataclass(slots=True)
    class _FieldInfo:
        default: Any = MISSING
        default_factory: Any = MISSING
        description: str | None = None


    def Field(
        default: Any = MISSING,
        *,
        default_factory: Any = MISSING,
        description: str | None = None,
    ) -> _FieldInfo:
        return _FieldInfo(
            default=default,
            default_factory=default_factory,
            description=description,
        )


    def model_validator(*, mode: str) -> Any:
        if mode != "after":
            raise NotImplementedError("Fallback model_validator only supports mode='after'.")

        def decorator(func: Any) -> Any:
            func.__model_validator_mode__ = mode
            return func

        return decorator


    class BaseModel:
        __model_validators__: ClassVar[list[Any]]

        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            validators: list[Any] = []
            for base in reversed(cls.__mro__):
                for value in base.__dict__.values():
                    if getattr(value, "__model_validator_mode__", None) == "after":
                        validators.append(value)
            cls.__model_validators__ = validators

        def __init__(self, **kwargs: Any) -> None:
            for name in self._field_names():
                if name in kwargs:
                    value = kwargs[name]
                else:
                    value = self._default_for(name)
                setattr(self, name, value)
            unexpected = set(kwargs) - set(self._field_names())
            if unexpected:
                names = ", ".join(sorted(unexpected))
                raise ValidationError(f"Unexpected fields: {names}")
            self._run_validators()

        @classmethod
        def _field_names(cls) -> list[str]:
            names: list[str] = []
            for base in reversed(cls.__mro__):
                for name, annotation in getattr(base, "__annotations__", {}).items():
                    if name.startswith("_"):
                        continue
                    if get_origin(annotation) is ClassVar:
                        continue
                    names.append(name)
            deduped: list[str] = []
            for name in names:
                if name not in deduped:
                    deduped.append(name)
            return deduped

        @classmethod
        def _default_for(cls, name: str) -> Any:
            if hasattr(cls, name):
                value = getattr(cls, name)
                if isinstance(value, _FieldInfo):
                    if value.default_factory is not MISSING:
                        return value.default_factory()
                    if value.default is not MISSING:
                        return value.default
                else:
                    return value
            raise ValidationError(f"Missing required field: {name}")

        def _run_validators(self) -> None:
            for validator in self.__class__.__model_validators__:
                result = validator(self)
                if result is not None and result is not self:
                    raise ValidationError("Fallback model validators must return self or None.")

        @classmethod
        def model_validate(cls, value: Any) -> Any:
            if isinstance(value, cls):
                return value
            if isinstance(value, dict):
                return cls(**value)
            if hasattr(value, "model_dump"):
                return cls(**value.model_dump())
            raise ValidationError(f"Cannot validate value as {cls.__name__}: {value!r}")

        def model_dump(self) -> dict[str, Any]:
            return {
                name: self._dump_value(getattr(self, name))
                for name in self._field_names()
            }

        def _dump_value(self, value: Any) -> Any:
            if isinstance(value, BaseModel):
                return value.model_dump()
            if isinstance(value, list):
                return [self._dump_value(item) for item in value]
            return value
