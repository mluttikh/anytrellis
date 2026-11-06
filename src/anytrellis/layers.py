"""Layers: what each mark type draws, as geometry in axis units.

Every mark becomes instances of two primitives the GPU draws: a rectangle between two
corners (bars), or a capsule from one point to another (a line segment; a point is a
capsule of zero length). ``Geometry`` holds them sorted by panel, with each instance's
source row (for tooltips) and colour.

Axis units: numbers as they are, times in milliseconds since 1970 (wall-clock), and
categories as their index along the axis (a band scale).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from anytrellis.data import Column, Table

Mark = Literal["line", "points", "bars", "rule"]
FacetMode = Literal["auto", "include", "all", "exclude"]
Position = Literal["stack", "dodge", "identity"]

FACET_MODES = ("auto", "include", "all", "exclude")


@dataclass
class Layer:
    """A layer as the user gave it (``Trellis.line`` and the others)."""

    mark: Mark
    name: str
    data: Any = None
    x: str | None = None
    y: str | None = None
    color: str | None = None
    group: tuple[str, ...] = ()
    facet: FacetMode = "auto"
    width: float = 1.5
    size: float = 5.0
    opacity: float = 1.0
    position: Position = "stack"
    bar_width: float = 0.8
    tooltip: list[str] = field(default_factory=list)
    # rules: constant positions
    values: list[Any] = field(default_factory=list)
    axis: Literal["x", "y"] = "y"
    dash: list[float] = field(default_factory=list)


@dataclass
class Geometry:
    """A layer's instances, sorted by panel."""

    panel: np.ndarray
    x0: np.ndarray
    y0: np.ndarray
    x1: np.ndarray
    y1: np.ndarray
    rows: np.ndarray
    """The source row of each instance in the layer's table."""
    rgba: np.ndarray | None = None
    """Per instance RGBA bytes (a colour column), or None (one colour)."""
    codes: np.ndarray | None = None
    """Per instance level of a category colour column (for tooltips)."""
    rows_end: np.ndarray | None = None
    """A line segment's end row (``rows`` is its start); None for points and bars."""

    @property
    def count(self) -> int:
        return len(self.panel)

    def starts(self, panels: int) -> np.ndarray:
        """Offsets: panel p holds instances ``starts[p]:starts[p + 1]``."""
        return np.searchsorted(self.panel, np.arange(panels + 1)).astype(np.uint32)

    def take(self, order: np.ndarray) -> Geometry:
        return Geometry(
            self.panel[order], self.x0[order], self.y0[order], self.x1[order], self.y1[order],
            self.rows[order],
            None if self.rgba is None else self.rgba[order],
            None if self.codes is None else self.codes[order],
            None if self.rows_end is None else self.rows_end[order],
        )  # fmt: skip


def axis_values(column: Column, levels: list[str] | None) -> np.ndarray:
    """A column in axis units: numbers and times as they are, categories as band indices
    (NaN for a value not on the axis)."""
    if column.kind != "category":
        return column.values
    lookup = {v: float(i) for i, v in enumerate(levels or [])}
    uniq, inverse = np.unique(column.values.astype(str), return_inverse=True)
    mapped = np.array([lookup.get(u, np.nan) for u in uniq], dtype=np.float64)
    return mapped[inverse.ravel()]


def expand(
    panel_of: np.ndarray | None, n: int, panels: int, mode: FacetMode
) -> tuple[np.ndarray, np.ndarray]:
    """The rows each panel draws, as (rows, panel) pairs.

    ``auto`` and ``include``: each row in its own panel (``auto``: in every panel when the
    data has no facet columns); ``all``: every row in every panel; ``exclude``: in every
    panel, the rows of the other panels (context).
    """
    rows = np.arange(n, dtype=np.int64)
    if mode == "all" or (panel_of is None and mode == "auto"):
        return np.tile(rows, panels), np.repeat(np.arange(panels, dtype=np.int64), n)
    if panel_of is None:
        raise ValueError(
            f"facet={mode!r} needs the facet columns in the layer's data; it has none of them"
        )
    if mode == "exclude":
        keep = panel_of >= 0
        picked, owner = rows[keep], panel_of[keep]
        out_rows = [picked[owner != p] for p in range(panels)]
        out_panel = [np.full(len(r), p, dtype=np.int64) for p, r in enumerate(out_rows)]
        return np.concatenate(out_rows), np.concatenate(out_panel)
    keep = panel_of >= 0
    return rows[keep], panel_of[keep]


def line_geometry(
    rows: np.ndarray, panel: np.ndarray, x: np.ndarray, y: np.ndarray, series: np.ndarray
) -> Geometry:
    """Segments between consecutive points of each series (sorted by x), in each panel; a
    point with no neighbour is a dot (a segment of zero length)."""
    xs, ys, ss = x[rows], y[rows], series[rows]
    order = np.lexsort((xs, ss, panel))
    rows, panel, xs, ys, ss = rows[order], panel[order], xs[order], ys[order], ss[order]
    valid = np.isfinite(xs) & np.isfinite(ys)
    same = (panel[1:] == panel[:-1]) & (ss[1:] == ss[:-1]) & valid[1:] & valid[:-1]
    pairs = np.flatnonzero(same)
    touched = np.zeros(len(rows), dtype=bool)
    touched[pairs] = True
    touched[pairs + 1] = True
    dots = np.flatnonzero(valid & ~touched)
    first = np.concatenate([pairs, dots])
    second = np.concatenate([pairs + 1, dots])
    geom = Geometry(panel[first], xs[first], ys[first], xs[second], ys[second], rows[first],
                    rows_end=rows[second])  # fmt: skip
    return geom.take(np.argsort(geom.panel, kind="stable"))


def point_geometry(rows: np.ndarray, panel: np.ndarray, x: np.ndarray, y: np.ndarray) -> Geometry:
    xs, ys = x[rows], y[rows]
    keep = np.isfinite(xs) & np.isfinite(ys)
    rows, panel, xs, ys = rows[keep], panel[keep], xs[keep], ys[keep]
    order = np.argsort(panel, kind="stable")
    rows, panel, xs, ys = rows[order], panel[order], xs[order], ys[order]
    return Geometry(panel, xs, ys, xs.copy(), ys.copy(), rows)


def bar_geometry(
    rows: np.ndarray,
    panel: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    *,
    step: float,
    width: float,
    codes: np.ndarray | None,
    ncodes: int,
    position: Position,
) -> Geometry:
    """Bars from 0 to y at x, ``width`` of the step between x values wide; with a category
    colour, stacked (positive up, negative down) or dodged side by side."""
    xs, ys = x[rows], y[rows]
    keep = np.isfinite(xs) & np.isfinite(ys)
    rows, panel, xs, ys = rows[keep], panel[keep], xs[keep], ys[keep]
    code = codes[rows] if codes is not None else np.zeros(len(rows), dtype=np.int64)
    w = width * step
    x0, x1 = xs - w / 2, xs + w / 2
    y0, y1 = np.zeros_like(ys), ys.copy()
    if codes is not None and position == "dodge" and ncodes > 1:
        slot = w / ncodes
        x0 = xs - w / 2 + code * slot
        x1 = x0 + slot
    elif codes is not None and position == "stack":
        order = np.lexsort((code, xs, panel))
        rows, panel, xs, ys, code = rows[order], panel[order], xs[order], ys[order], code[order]
        x0, x1 = xs - w / 2, xs + w / 2
        y0, y1 = _stack(panel, xs, ys)
    geom = Geometry(panel, x0, y0, x1, y1, rows)
    return geom.take(np.argsort(geom.panel, kind="stable"))


def _stack(panel: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Cumulative bases within each (panel, x), sorted by both: positives up, negatives
    down."""
    n = len(ys)
    y0, y1 = np.zeros(n), np.zeros(n)
    if not n:
        return y0, y1
    start = np.flatnonzero(np.r_[True, (panel[1:] != panel[:-1]) | (xs[1:] != xs[:-1])])
    group = np.repeat(np.arange(len(start)), np.diff(np.r_[start, n]))
    for sign in (1.0, -1.0):
        part = np.where(np.sign(ys) == sign, ys, 0.0)
        cum = np.cumsum(part)
        base = np.r_[0.0, cum][start][group]
        top = cum - base
        pick = np.sign(ys) == sign
        y1[pick] = top[pick]
        y0[pick] = (top - part)[pick]
    return y0, y1


def step_of(values: list[np.ndarray]) -> float:
    """The smallest positive step between distinct x values (bar width unit)."""
    uniq = np.unique(np.concatenate([v[np.isfinite(v)] for v in values]) if values else [])
    if len(uniq) < 2:
        return 1.0
    steps = np.diff(uniq)
    steps = steps[steps > 0]
    return float(steps.min()) if len(steps) else 1.0


def series_codes(table: Table, names: list[str]) -> np.ndarray:
    """One integer per row for the combination of ``names`` (line series)."""
    if not names:
        return np.zeros(table.n, dtype=np.int64)
    out = np.zeros(table.n, dtype=np.int64)
    for name in names:
        col = table.column(name)
        values = col.values.astype(str) if col.kind == "category" else col.values
        _, inverse = np.unique(values, return_inverse=True)
        out = out * (int(inverse.max(initial=0)) + 1) + inverse.ravel()
    return out
