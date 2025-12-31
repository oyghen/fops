import datetime as dt
import inspect
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

T = TypeVar("T")


def get_caller_name(depth: int = 1) -> str:
    """Return the name of the calling function; depth=1 is the immediate caller."""
    if depth < 1:
        raise ValueError(f"invalid {depth=!r}; expected >= 1")

    frame = inspect.currentframe()
    try:
        caller = frame
        for _ in range(depth):
            caller = caller.f_back if caller is not None else None
        if caller is None:
            raise RuntimeError("expected to be executed within a function")
        return caller.f_code.co_name
    finally:
        del frame


def pipe(value: T, functions: Iterable[Callable[[Any], Any]]) -> Any:
    """Return the result of applying a sequence of functions to the initial value."""
    result: Any = value
    for function in functions:
        result = function(result)
    return result


def utctimestamp() -> str:
    """Return UTC timestamp string."""
    return dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
