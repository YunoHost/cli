#!/usr/bin/env python3

from typing import Any, Generic, TypeVar

_T = TypeVar("_T")


class Singleton(type, Generic[_T]):
    _instances: dict["Singleton[_T]", _T] = {}  # noqa: RUF012

    def __call__(cls, *args: Any, **kwargs: Any) -> _T:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
