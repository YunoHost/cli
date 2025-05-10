#!/usr/bin/env python3

from typing import Any, Type

class Singleton(type):
    _instances: dict[Type, Any] = {}
    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
