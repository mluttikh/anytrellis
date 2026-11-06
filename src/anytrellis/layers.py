"""Layers: what each mark type draws, as geometry in axis units.

Every mark becomes instances of three primitives the GPU draws: a rectangle between two
corners (bars, rects), a capsule from one point to another (a line segment; a point is a
capsule of zero length), or a trapezoid from a segment down to its base (areas). Text is
drawn as labels at points. ``Geometry`` holds them sorted by panel, with each instance's
source row (for tooltips) and colour.

Axis units: numbers as they are, times in milliseconds since 1970 (wall-clock), and
categories as their index along the axis (a band scale).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from anytrellis.data import Column, Table

Mark = Literal["line", "points", "bars", "area", "rect", "text", "rule", "hist", "box", "density"]
SUMMARIES = ("hist", "box", "density")
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
    # rects: a second corner (else centred on x, y), a tile's height (a fraction of the step)
    x2: str | None = None
    y2: str | None = None
    rect_height: float = 1.0
    # text: the labels' column, alignment and offset (px)
    text: str | None = None
    align: Literal["left", "center", "right"] = "center"
    dx: float = 0.0
    dy: float = 0.0
    # summaries (hist, box, density): their options; on a drawn part, the summary's mark
    stat_args: dict[str, Any] = field(default_factory=dict)
    stat: str | None = None
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
    base0: np.ndarray | None = None
    base1: np.ndarray | None = None
    """An area's base at each end of a segment (its top is y0, y1); None otherwise."""

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
            None if self.base0 is None else self.base0[order],
            None if self.base1 is None else self.base1[order],
        )  # fmt: skip


def axis_values(column: Column, levels: list[str] | None) -> np.ndarray:
    """A column in axis units: numbers and times as they are, categories as band indices
    (NaN for a value not on the axis)."""
    if column.kind != "category":
        return column.values
    lookup = {v: float(i) for i, v in enumerate(levels or [])}
    # the column's own levels to the axis's, then each row by its code
    mapped = np.array([lookup.get(lv, np.nan) for lv in column.levels] + [np.nan])
    return mapped[column.level_codes()]  # a code of -1: the NaN at the end


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


def area_geometry(
    rows: np.ndarray, panel: np.ndarray, x: np.ndarray, y: np.ndarray, series: np.ndarray,
    *, stack: bool,
) -> Geometry:  # fmt: skip
    """Areas from each series' line down to 0, or (``stack``) stacked on the series before
    it at the same x (positives up, negatives down): a trapezoid per segment, split where
    the line crosses its base."""
    xs, ys, ss = x[rows], y[rows], series[rows]
    keep = np.isfinite(xs) & np.isfinite(ys)
    rows, panel, xs, ys, ss = rows[keep], panel[keep], xs[keep], ys[keep], ss[keep]
    base = np.zeros(len(ys))
    top = ys.copy()
    if stack and len(ys):
        order = np.lexsort((ss, xs, panel))
        rows, panel, xs, ys, ss = rows[order], panel[order], xs[order], ys[order], ss[order]
        base, top = _stack(panel, xs, ys)
    # segments between consecutive points of a series, in x
    order = np.lexsort((xs, ss, panel))
    rows, panel, xs, ss, base, top = (a[order] for a in (rows, panel, xs, ss, base, top))
    pair = np.flatnonzero((panel[1:] == panel[:-1]) & (ss[1:] == ss[:-1]))
    a, b = pair, pair + 1
    x0, x1 = xs[a], xs[b]
    t0, t1, b0, b1 = top[a], top[b], base[a], base[b]
    r0, r1, pn = rows[a], rows[b], panel[a]
    # where the line crosses its base, two trapezoids meeting there
    d0, d1 = t0 - b0, t1 - b1
    cross = (d0 * d1) < 0
    if cross.any():
        f = d0[cross] / (d0[cross] - d1[cross])
        xm = x0[cross] + f * (x1[cross] - x0[cross])
        ym = b0[cross] + f * (b1[cross] - b0[cross])
        keep_ = ~cross
        x0 = np.concatenate([x0[keep_], x0[cross], xm])
        x1 = np.concatenate([x1[keep_], xm, x1[cross]])
        t0 = np.concatenate([t0[keep_], t0[cross], ym])
        t1 = np.concatenate([t1[keep_], ym, t1[cross]])
        nb0 = np.concatenate([b0[keep_], b0[cross], ym])
        nb1 = np.concatenate([b1[keep_], ym, b1[cross]])
        b0, b1 = nb0, nb1
        r0 = np.concatenate([r0[keep_], r0[cross], r0[cross]])
        r1 = np.concatenate([r1[keep_], r1[cross], r1[cross]])
        pn = np.concatenate([pn[keep_], pn[cross], pn[cross]])
    geom = Geometry(pn, x0, t0, x1, t1, r0, rows_end=r1, base0=b0, base1=b1)
    return geom.take(np.lexsort((geom.x0, pn)))


def rect_geometry(
    rows: np.ndarray, panel: np.ndarray, x: np.ndarray, y: np.ndarray,
    x2: np.ndarray | None, y2: np.ndarray | None,
    *, x_step: float, y_step: float, width: float, height: float,
) -> Geometry:  # fmt: skip
    """Tiles: from (x, y) to (x2, y2) where given, else centred on x (y), ``width``
    (``height``) of the step between values wide (high): a heatmap's cells."""
    xs, ys = x[rows], y[rows]
    xe = x2[rows] if x2 is not None else None
    ye = y2[rows] if y2 is not None else None
    keep = np.isfinite(xs) & np.isfinite(ys)
    if xe is not None:
        keep &= np.isfinite(xe)
    if ye is not None:
        keep &= np.isfinite(ye)
    rows, panel, xs, ys = rows[keep], panel[keep], xs[keep], ys[keep]
    if xe is not None:
        x0, x1 = xs, xe[keep]
    else:
        x0, x1 = xs - width * x_step / 2, xs + width * x_step / 2
    if ye is not None:
        y0, y1 = ys, ye[keep]
    else:
        y0, y1 = ys - height * y_step / 2, ys + height * y_step / 2
    geom = Geometry(panel, x0, y0, x1, y1, rows)
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
