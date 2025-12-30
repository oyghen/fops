import datetime as dt
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

T = TypeVar("T")


def pipe(value: T, functions: Iterable[Callable[[Any], Any]]) -> Any:
    """Return the result of applying a sequence of functions to the initial value."""
    result: Any = value
    for function in functions:
        result = function(result)
    return result


def utctimestamp() -> str:
    """Return UTC timestamp string."""
    return dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
