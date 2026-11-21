"""A plot in one call, for those coming from Plotly Express or ``df.plot``.

* ``at.line(df, x="year", y="pop", wrap="country")`` is ``Trellis(df, wrap="country")
  .line(x="year", y="pop")``: each argument goes to ``Trellis()`` or to the mark, by its
  name. There is one for each common mark (``SHORTCUTS``).
* ``plot(df, kind="scatter", x=..., y=...)``: the same, by a kind's name, pandas' names
  too (``scatter``, ``bar``, ``barh``, ``kde``) and pandas' arguments (``by=``, ``logy=``,
  ``xlabel=``). It is the pandas plotting backend: ``pd.options.plotting.backend =
  "anytrellis"`` makes ``df.plot(...)`` an anytrellis plot. No x: the index; no y (or a
  list): every number column, as one coloured series each.
* ``df.trellis.line(...)``: the shortcuts as a table's methods, after ``import
  anytrellis.pandas`` or ``import anytrellis.polars`` (``Accessor``).
"""

from __future__ import annotations

import difflib
import inspect
from collections.abc import Callable
from typing import Any

from anytrellis.plot import Trellis

SHORTCUTS = ("line", "points", "bars", "area", "hist", "density", "box", "violin", "ecdf",
             "hexbin")  # fmt: skip
"""The marks with a shortcut: ``at.line(df, ...)`` and so on."""

KINDS = {
    **{name: name for name in SHORTCUTS},
    "scatter": "points",
    "bar": "bars",
    "barh": "bars",
    "kde": "density",
}
"""``plot()``'s kinds: the shortcuts' names, and pandas' for the same marks."""

ONE_AXIS = ("hist", "density", "ecdf")
"""Marks of one column, on x: several columns go in as one, coloured by column."""


def _names(mark: str) -> tuple[set[str], set[str]]:
    """The names ``Trellis()`` takes, and those the mark takes (its own ``data`` aside)."""
    made = set(inspect.signature(Trellis).parameters) - {"data"}
    drawn = set(inspect.signature(getattr(Trellis, mark)).parameters) - {"self", "data"}
    return made, drawn


def _split(mark: str, kwargs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """``kwargs`` for ``Trellis()`` and for the mark, by name; an unknown one is an error
    that says what was meant."""
    made, drawn = _names(mark)
    plot: dict[str, Any] = {}
    layer: dict[str, Any] = {}
    for name, value in kwargs.items():
        if name in drawn:
            layer[name] = value
        elif name in made:
            plot[name] = value
        else:
            near = difflib.get_close_matches(name, sorted(made | drawn), n=1)
            hint = f"; did you mean {near[0]!r}?" if near else ""
            raise TypeError(f"{mark}() takes Trellis()'s arguments and .{mark}()'s, "
                            f"not {name!r}{hint}")  # fmt: skip
    return plot, layer


def _shortcut(mark: str) -> Callable[..., Trellis]:
    def shortcut(data: Any, /, **kwargs: Any) -> Trellis:
        plot, layer = _split(mark, kwargs)
        return getattr(Trellis(data, **plot), mark)(**layer)

    method = getattr(Trellis, mark)
    params = [inspect.Parameter("data", inspect.Parameter.POSITIONAL_ONLY)]
    seen = {"data"}
    for source in (inspect.signature(method), inspect.signature(Trellis)):
        for p in source.parameters.values():
            if p.name in seen or p.name == "self" or p.kind is p.VAR_KEYWORD:
                continue
            seen.add(p.name)
            params.append(p.replace(kind=inspect.Parameter.KEYWORD_ONLY))
    shortcut.__name__ = shortcut.__qualname__ = mark
    shortcut.__module__ = "anytrellis"
    # help() and the notebook's Shift+Tab list every argument it takes
    setattr(shortcut, "__signature__", inspect.Signature(params, return_annotation="Trellis"))  # noqa: B010 (ty: a function has none)
    first = (method.__doc__ or "").strip().split("\n\n")[0]
    shortcut.__doc__ = (
        f"``Trellis(data, ...).{mark}(...)`` in one call: each argument goes to "
        f"``Trellis()`` or to ``{mark}()`` by its name.\n\n"
        f'```python\nat.{mark}(df, x=..., wrap="group")\n```\n\n{mark}(): {first}'
    )
    return shortcut


line = _shortcut("line")
points = _shortcut("points")
bars = _shortcut("bars")
area = _shortcut("area")
hist = _shortcut("hist")
density = _shortcut("density")
box = _shortcut("box")
violin = _shortcut("violin")
ecdf = _shortcut("ecdf")
hexbin = _shortcut("hexbin")


# ---- plot(): by a kind's name, and pandas' df.plot -----------------------------------------


def plot(data: Any, kind: str = "line", x: Any = None, y: Any = None, **kwargs: Any) -> Trellis:
    """A plot of ``kind`` in one call, as ``at.<kind>(data, ...)``; the pandas plotting
    backend (``pd.options.plotting.backend = "anytrellis"``, then ``df.plot(...)``).

    ```python
    at.shortcuts.plot(cars, kind="scatter", x="weight", y="mpg", by="origin")
    df.plot(x="date", y=["temp_min", "temp_max"])   # with the backend: one line each
    ```

    Args:
        data: Any table ``Trellis`` takes; a pandas Series as a one-column table.
        kind: A shortcut's name (``"line"``, ``"points"``, ...) or pandas'
            (``"scatter"``, ``"bar"``, ``"barh"``, ``"kde"``).
        x: The x column. A pandas table without one: its index.
        y: The y column, or several: one series each, coloured by column (``"column"``,
            their values ``"value"``). None: every number column but x. A histogram,
            density or ECDF draws y's columns along x, as pandas does.
        **kwargs: ``Trellis()``'s and the mark's arguments, and pandas' ``by=`` (as
            ``wrap=``), ``logx=``, ``logy=``, ``loglog=``, ``xlabel=``, ``ylabel=``,
            ``legend=False``, ``stacked=`` and ``figsize=`` (its height).
    """
    mark = KINDS.get(kind)
    if mark is None:
        raise ValueError(f"kind must be one of {sorted(KINDS)}, got {kind!r}")
    # pandas passes its own arguments (s, c, bw_method, ...) as None when not given
    known = set().union(*_names(mark))
    kwargs = _from_pandas({k: v for k, v in kwargs.items() if v is not None or k in known})
    stacked = kwargs.pop("stacked", None)  # pandas': on areas, and bars if asked
    if stacked is not None and mark in ("area", "bars"):
        side = "dodge" if mark == "bars" else "identity"
        kwargs.setdefault("position", "stack" if stacked else side)
    data = _frame(data)

    def series(skip: list[Any]) -> list[str]:  # y's columns: given, or every number one
        cols = _numbers(data, skip=[*skip, *_used(kwargs)]) if y is None else y
        cols = [cols] if isinstance(cols, str) else list(cols)
        if not cols:
            raise ValueError("no number column to plot: give y=")
        return cols

    if mark in ONE_AXIS:  # along x: x, else y's columns, coloured by column
        if x is None:
            cols = series([])
            if len(cols) > 1:
                data = _longer(data, cols)
                kwargs.setdefault("color", "column")
            x = "value" if len(cols) > 1 else cols[0]
        return _shortcut(mark)(data, x=x, **kwargs)
    if mark == "box" and x is None:  # a box a column, as pandas' df.plot.box()
        cols = series([])
        if len(cols) > 1:
            return box(_longer(data, cols), x="column", y="value", **kwargs)
        return box(data, y=cols[0], **kwargs)
    if x is None and _is_pandas(data):
        data, x = _with_index(data)
    cols = series([x])
    if len(cols) > 1:  # one series a column: long, coloured by column
        data = _longer(data, cols)
        kwargs.setdefault("color", "column")
    y_col = "value" if len(cols) > 1 else cols[0]
    if kind == "barh":  # the categories (x in pandas) up the side
        return bars(data, x=y_col, y=x, **kwargs)
    return _shortcut(mark)(data, x=x, y=y_col, **kwargs)


def _from_pandas(kwargs: dict[str, Any]) -> dict[str, Any]:
    """pandas' names for what ``Trellis`` calls otherwise."""
    out = dict(kwargs)
    if (by := out.pop("by", None)) is not None:
        out.setdefault("wrap", by)
    if out.pop("loglog", False):
        out.update(x_scale="log", y_scale="log")
    if out.pop("logx", False):
        out["x_scale"] = "log"
    if out.pop("logy", False):
        out["y_scale"] = "log"
    for theirs, ours in (("xlabel", "x_title"), ("ylabel", "y_title")):
        if theirs in out:
            out[ours] = out.pop(theirs)
    legend = out.pop("legend", None)
    if legend is False:
        out["legend"] = "none"
    elif legend is not None and legend is not True:
        out["legend"] = legend
    if (size := out.pop("figsize", None)) is not None:
        out.setdefault("height", float(size[1]) * 96)  # inches, as matplotlib's
    return out


def _is_pandas(data: Any) -> bool:
    return type(data).__module__.split(".")[0] == "pandas"


def _frame(data: Any) -> Any:
    """A pandas Series as a one-column table (its name, else ``"value"``)."""
    if _is_pandas(data) and hasattr(data, "to_frame") and not hasattr(data, "columns"):
        return data.to_frame(name=data.name if data.name is not None else "value")
    return data


def _with_index(data: Any) -> tuple[Any, str]:
    """A pandas table with its index as a column, and that column's name."""
    name = data.index.name if data.index.name is not None else "index"
    if name in data.columns:
        return data, name
    return data.reset_index(names=name), name


def _used(kwargs: dict[str, Any]) -> list[str]:
    """Columns ``kwargs`` name (facets, colour, group): not series of their own."""
    out: list[str] = []
    for key in ("wrap", "row", "col", "color", "group", "page", "link"):
        value = kwargs.get(key)
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list | tuple):
            out += [v for v in value if isinstance(v, str)]
    return out


def _numbers(data: Any, skip: list[Any]) -> list[str]:
    """The table's number columns, but those in ``skip``."""
    import narwhals as nw

    frame = nw.from_native(data, eager_only=False)
    schema = frame.collect_schema() if hasattr(frame, "collect_schema") else frame.schema
    return [name for name, dtype in schema.items()
            if dtype.is_numeric() and name not in skip]  # fmt: skip


def _longer(data: Any, columns: list[str]) -> Any:
    """``columns`` stacked into ``column`` (the name) and ``value``, the others kept."""
    import narwhals as nw

    frame = nw.from_native(data, eager_only=False)
    names = frame.collect_schema().names() if hasattr(frame, "collect_schema") else frame.columns
    missing = [c for c in columns if c not in names]
    if missing:
        raise ValueError(f"no column {missing[0]!r}; the table has {names}")
    keep = [n for n in names if n not in columns]
    long = frame.unpivot(on=columns, index=keep, variable_name="column", value_name="value")
    return nw.to_native(long)


# ---- df.trellis: the shortcuts as a table's methods ----------------------------------------


class Accessor:
    """``df.trellis``: ``df.trellis.line(x=..., wrap=...)`` is ``at.line(df, ...)``, and
    ``df.trellis(kind=..., ...)`` is ``plot(df, ...)``. Registered by ``import
    anytrellis.pandas`` (pandas tables and Series) and ``import anytrellis.polars`` (Polars
    DataFrames and LazyFrames)."""

    def __init__(self, data: Any) -> None:
        self._data = data

    def __call__(self, kind: str = "line", x: Any = None, y: Any = None, **kwargs: Any) -> Trellis:
        return plot(self._data, kind=kind, x=x, y=y, **kwargs)

    def __dir__(self) -> list[str]:
        return [*SHORTCUTS, *object.__dir__(self)]

    def __getattr__(self, name: str) -> Callable[..., Trellis]:
        if name not in SHORTCUTS:
            raise AttributeError(f"df.trellis has the shortcuts {list(SHORTCUTS)}, not {name!r}")

        def method(**kwargs: Any) -> Trellis:  # plot(): a Series, and x or y left out
            return plot(self._data, kind=name, **kwargs)

        method.__name__ = name
        method.__doc__ = globals()[name].__doc__
        return method
