"""A plot's description for screen readers, made from what it shows: its marks, what they
plot, the panels, the colours and other channels, the rows, and the axes' ranges.

    Scatter of mpg against weight, one panel per origin (3), coloured by cylinders.
    398 rows. mpg from 9 to 46.6; weight from 1,613 to 5,140.

The browser gives it to the plot (role="figure", aria-label); saved images carry it as
their title and description.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from anytrellis.layers import Layer

NOUNS: dict[str, str] = {
    "line": "lines",
    "points": "points",
    "bars": "bars",
    "barstat": "bars",
    "area": "areas",
    "band": "bands",
    "rect": "rectangles",
    "segment": "segments",
    "hexbin": "hexagonal bins",
    "contour": "density contours",
    "rug": "a rug",
    "text": "text",
    "hist": "histogram",
    "box": "box plots",
    "density": "densities",
    "smooth": "smoothed lines",
    "violin": "violins",
    "errorbar": "error bars",
    "horizon": "horizon bands",
    "ecdf": "ECDF",
}
"""Each mark, as a noun (``rule``: none, lines drawn across)."""


@dataclass
class Axis:
    """An axis as described: its title, kind, categories, and the data's range on it."""

    title: str
    kind: str
    levels: Sequence[str] | None
    lo: float | None
    hi: float | None
    format: Callable[[float], str] | None = None


def describe(
    layers: Sequence[Layer],
    label: Callable[[str], str],
    facets: str,
    rows: int | None,
    x: Axis,
    y: Axis,
) -> str:
    """The description: what is plotted, in what panels, coloured how; the rows; the
    ranges."""
    drawn = [lr for lr in layers if lr.mark != "rule"]
    if not drawn:
        return "An empty plot."
    first = drawn[0]
    nouns = list(dict.fromkeys(NOUNS[lr.mark] for lr in drawn))
    scatter = first.mark == "points" and x.kind != "band" and y.kind != "band"
    if scatter:
        nouns[0] = "scatter"
    what = _joined(nouns)
    what = what[0].upper() + what[1:]
    if first.y is None or first.mark in ("hist", "density", "ecdf"):
        of = f" of {_title(x, first.x, label)}" if first.x else ""
    elif first.x is None:
        of = f" of {_title(y, first.y, label)}"
    elif x.kind == "band" and y.kind != "band":  # a value per category: by it
        of = f" of {_title(y, first.y, label)} by {_title(x, first.x, label)}"
    elif y.kind == "band" and x.kind != "band":
        of = f" of {_title(x, first.x, label)} by {_title(y, first.y, label)}"
    else:
        of = f" of {_title(y, first.y, label)} against {_title(x, first.x, label)}"
    parts = [what + of]
    if facets:
        parts.append(facets)
    channels = _channels(drawn, label)
    if channels:
        parts.append(channels)
    out = ", ".join(parts) + "."
    if rows is not None:
        out += f" {rows:,} row{'s' if rows != 1 else ''}."
    ranges = [r for r in (_range(y, first.y, label), _range(x, first.x, label)) if r]
    if ranges:
        out += " " + "; ".join(ranges) + "."
    return out


def facet_phrase(
    label: Callable[[str], str],
    wrap: Sequence[str],
    row: Sequence[str],
    col: Sequence[str],
    page: Sequence[str],
    panels: int,
    rows: int,
    cols: int,
    per_page: int | None,
) -> str:
    """The panels: one per level of the wrap columns, or rows and columns of a grid; the
    pages."""
    names = lambda cs: " and ".join(label(c) for c in cs)  # noqa: E731
    out = ""
    if wrap:
        out = f"one panel per {names(wrap)} ({panels})"
    elif row and col:
        out = f"panels by {names(row)} ({rows} rows) and {names(col)} ({cols} columns)"
    elif row:
        out = f"a row of panels per {names(row)} ({rows})"
    elif col:
        out = f"a column of panels per {names(col)} ({cols})"
    if page:
        out += f"{', ' if out else ''}a page per {names(page)}"
    elif per_page is not None and per_page < panels:
        out += f", {per_page} a page"
    return out


def _channels(layers: Sequence[Layer], label: Callable[[str], str]) -> str:
    """What the colour, shape, dash and size columns are, together where they're one."""
    by: dict[str, list[str]] = {}
    for lr in layers:
        for verb, name in (("coloured", lr.color), ("shaped", lr.shape), ("dashed", lr.dash_by),
                           ("sized", lr.size_by)):  # fmt: skip
            if name is None or (verb == "coloured" and name.startswith("#")):
                continue
            verbs = by.setdefault(name, [])
            if verb not in verbs:
                verbs.append(verb)
    return ", ".join(f"{_joined(verbs)} by {label(name)}" for name, verbs in by.items())


def _title(axis: Axis, column: str | None, label: Callable[[str], str]) -> str:
    """An axis' name: its title, else its column's label."""
    return axis.title or (label(column) if column else "")


def _range(axis: Axis, column: str | None, label: Callable[[str], str]) -> str:
    """``mpg from 9 to 46.6``; a category axis' levels; a time axis' dates."""
    name = _title(axis, column, label)
    if not name and axis.kind != "time":
        return ""
    if axis.kind == "band":
        levels = list(axis.levels or [])
        if not levels:
            return ""
        shown = ", ".join(levels[:5]) + (f" and {len(levels) - 5} more" if len(levels) > 5 else "")
        return f"{name}: {shown}"
    lo, hi = axis.lo, axis.hi
    if lo is None or hi is None or not (math.isfinite(lo) and math.isfinite(hi)):
        return ""
    show = axis.format or (_date if axis.kind == "time" else _number)
    span = f"from {show(lo)} to {show(hi)}"
    return f"{name} {span}" if name else f"dates {span}"


def _number(v: float) -> str:
    """A value to three significant digits, from 10,000 whole and with separators (a year
    as it is)."""
    if abs(v) >= 10_000:
        return f"{v:,.0f}"
    if v == int(v) or abs(v) >= 1000:
        return str(round(v))
    return f"{v:.3g}"


def _date(ms: float) -> str:
    """A time (ms since 1970, UTC) as its date, and its time when not midnight."""
    t = dt.datetime(1970, 1, 1, tzinfo=dt.UTC) + dt.timedelta(milliseconds=ms)
    return t.strftime("%Y-%m-%d" if (t.hour, t.minute, t.second) == (0, 0, 0) else "%Y-%m-%d %H:%M")


def _joined(words: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]
