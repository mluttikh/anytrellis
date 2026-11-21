"""The Python that makes a plot (``Trellis.code``, the settings panel's "Copy as Python"):
the calls that made it, as they were recorded, with what was changed since by hand (in
the settings panel, the page bar, on a panel) written in.

``recorded`` wraps the methods that build a plot: each call is kept with its arguments,
and the layer it added. A call made by another recorded call (``pairs`` adding its
layers) is not kept: running the outer one makes it again.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import math
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any

from anytrellis.theme import Theme


@dataclass
class Call:
    """A recorded call: the method's name, its arguments, and the layer it added."""

    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    layer: Any = None


def recorded[F: Callable[..., Any]](method: F) -> F:
    """Keep each call of ``method`` (on ``self._calls``), unless another recorded call
    made it."""

    name = getattr(method, "__name__", "")

    @functools.wraps(method)
    def call(self: Any, *args: Any, **kwargs: Any) -> Any:
        if self._recording:
            return method(self, *args, **kwargs)
        self._recording = True
        before = len(self._layers)
        try:
            out = method(self, *args, **kwargs)
        finally:
            self._recording = False
        layer = self._layers[before] if len(self._layers) > before else None
        self._calls.append(Call(name, args, dict(kwargs), layer))
        self._sync_code()
        return out

    return call  # ty: ignore[invalid-return-type]


def recorded_init[F: Callable[..., Any]](init: F) -> F:
    """Keep the arguments a plot was made with (``self._given``); the calls ``__init__``
    makes are not kept."""

    @functools.wraps(init)
    def call(self: Any, *args: Any, **kwargs: Any) -> None:
        if getattr(self, "_recording", False):  # a subclass's __init__ calling this one
            init(self, *args, **kwargs)
            return
        self._given = Call(type(self).__name__, args, dict(kwargs))
        self._calls = []
        self._recording = True
        try:
            init(self, *args, **kwargs)
        finally:
            self._recording = False

    return call  # ty: ignore[invalid-return-type]


def source_name(obj: Any) -> str:
    """The name a notebook gave ``obj`` (its first variable holding this very object),
    else ``"data"``."""
    spaces: list[Mapping[str, Any]] = []
    try:
        from IPython import get_ipython

        shell = get_ipython()
        if shell is not None:
            spaces.append(shell.user_ns)
    except ImportError:
        pass
    main = sys.modules.get("__main__")
    if main is not None:
        spaces.append(vars(main))
    for space in spaces:
        for name, value in list(space.items()):
            if value is obj and not name.startswith("_"):
                return name
    return "data"


def literal(value: Any) -> str:
    """``value`` as Python source: a table as the name it has in the notebook."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if hasattr(value, "item") and callable(value.item) and getattr(value, "shape", None) == ():
        value = value.item()  # a numpy scalar
    if isinstance(value, int):
        return repr(value)
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else f'float("{value}")'
    if isinstance(value, tuple):
        inner = ", ".join(literal(v) for v in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, list):
        return "[" + ", ".join(literal(v) for v in value) + "]"
    if isinstance(value, Mapping):
        return "{" + ", ".join(f"{literal(k)}: {literal(v)}" for k, v in value.items()) + "}"
    if isinstance(value, Theme):
        return _theme(value)
    if isinstance(value, dt.datetime | dt.date):
        return repr(value)
    return source_name(value)


def _theme(theme: Theme) -> str:
    """A theme as its base and the settings it changes."""
    base = Theme(theme.base)
    changed = [f"{f.name}={literal(getattr(theme, f.name))}" for f in fields(Theme)
               if f.name != "base" and getattr(theme, f.name) != getattr(base, f.name)]  # fmt: skip
    return "Theme(" + ", ".join([literal(theme.base), *changed]) + ")"


def call_text(name: str, args: Sequence[Any], kwargs: Mapping[str, Any]) -> str:
    """``name(arg, key=value, ...)``."""
    parts = [literal(a) for a in args] + [f"{k}={literal(v)}" for k, v in kwargs.items()]
    return f"{name}({', '.join(parts)})"


def chained(head: str, calls: Sequence[str]) -> str:
    """The plot's expression: its first call, then each method on a line of its own."""
    if not calls:
        return head
    return "(\n    " + head + "".join(f"\n    .{c}" for c in calls) + "\n)"
