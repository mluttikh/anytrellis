"""Level of detail: long lines thinned and dense points drawn as cells, so what goes to the
browser grows with the pixels it shows, not with the rows.

Lines. In a panel with more than ``THIN`` points, each series keeps, in each column of the
panel's x range, its first, last, lowest and highest point (M4: Jugel et al., "M4: A
Visualization-Oriented Time Series Data Aggregation", VLDB 2014). Drawn no wider than its
columns, the thinned line covers the pixels all its points would. A plot starts with
``COLUMNS`` columns across each panel's data.

Points. A panel with more than ``DENSE`` points is drawn as cells: a grid over its scales'
domain (so the cells of panels sharing them line up), each cell in the colour of its points
(a category column's colours mixed in proportion, as datashader does; a number column's
mean), more opaque the more points it holds. A plot starts with cells of about ``CELL_PX``
pixels for the panels' size at the default width, ``START_WIDTH``.

Zoomed in. The browser reports what it shows (each scale group's range, each panel's size
in pixels), and a panel shown in more detail than it was sent gets its range in view, and
some more either side: a line at ``COLUMNS_PX`` columns a pixel; points as cells of
about ``CELL_PX`` pixels, or as points again when at most ``DENSE`` are in view. Images drawn
in Python show the same. A page from ``save_html`` has no Python to ask: it shows the
plot as it starts.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from anytrellis.data import Table, group_order
from anytrellis.layers import Geometry, polyline

COLUMNS = 2000
"""Columns across a panel's data a thinned line starts with."""
THIN = 20_000
"""A line layer's panel with more points than this is thinned."""
DENSE = 100_000
"""A points layer's panel with more points than this is drawn as cells."""
START_WIDTH = 800
"""The plot's width (px) the cells it starts with are sized for (a saved page's, before
the browser tells)."""
COLUMNS_PX = 2.0
"""A line's columns a pixel, zoomed in (screens of two device pixels a CSS pixel)."""
CELL_PX = 3.0
"""A cell's size in pixels."""
MARGIN = 0.5
"""What a panel zoomed in is sent: its range in view and this much of it again either side,
so a pan does not need more at once."""
CELL_MARGIN = 0.25
"""Cells': on both axes, so less."""
MAX_COLUMNS = 20_000
MAX_CELLS = 1000
"""At most so many columns (cells across or up) for a panel."""
TIP_LEVELS = 12
"""A cell's tooltip tells its points of each colour level, of at most so many levels."""


@dataclass(frozen=True)
class Window:
    """What a panel was sent for, zoomed in: an x range (points: and y) at ``nx`` columns
    (cells: ``nx`` by ``ny``), or (``raw``) the points in it."""

    x0: float
    x1: float
    y0: float = -math.inf
    y1: float = math.inf
    nx: int = 0
    ny: int = 0
    raw: bool = False


@dataclass(frozen=True)
class Shown:
    """A panel as the browser shows it: its ranges (axis units) and size (CSS px)."""

    x0: float
    x1: float
    y0: float
    y1: float
    w: float
    h: float


def m4(seg: np.ndarray, x: np.ndarray, y: np.ndarray, lo: np.ndarray, hi: np.ndarray,
       columns: np.ndarray, panel: np.ndarray) -> np.ndarray:  # fmt: skip
    """The points M4 keeps (their indices, sorted) of points sorted by series (``seg``, a
    number unique across panels) and x: in each series, per column of ``[lo, hi]`` (split
    in ``columns``; all three per panel), its first, last, lowest and highest point."""
    n = len(x)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    span = (hi - lo)[panel]
    f = np.where(span > 0, (x - lo[panel]) / np.where(span > 0, span, 1.0), 0.0)
    cols = columns[panel]
    col = np.clip(np.floor(f * cols), 0, cols - 1).astype(np.int64)
    new = np.ones(n, dtype=bool)
    new[1:] = (seg[1:] != seg[:-1]) | (col[1:] != col[:-1])
    starts = np.flatnonzero(new)
    ends = np.r_[starts[1:], n] - 1
    run = np.cumsum(new) - 1
    lowest = _first(y == np.minimum.reduceat(y, starts)[run], run)
    highest = _first(y == np.maximum.reduceat(y, starts)[run], run)
    return np.unique(np.concatenate([starts, ends, lowest, highest]))


def _first(hit: np.ndarray, run: np.ndarray) -> np.ndarray:
    """The first index of each run where ``hit`` holds."""
    idx = np.flatnonzero(hit)
    return idx[np.r_[True, run[idx[1:]] != run[idx[:-1]]]] if len(idx) else idx


def _extents(panel: np.ndarray, v: np.ndarray, npanels: int) -> tuple[np.ndarray, np.ndarray]:
    """Each panel's lowest and highest of ``v`` (sorted by panel); NaN: none. A panel of one
    value gets a range of 1 around it."""
    lo = np.full(npanels, np.nan)
    hi = np.full(npanels, np.nan)
    if len(v):
        starts = np.flatnonzero(np.r_[True, panel[1:] != panel[:-1]])
        p = panel[starts]
        lo[p] = np.minimum.reduceat(v, starts)
        hi[p] = np.maximum.reduceat(v, starts)
    flat = lo == hi
    lo[flat] -= 0.5
    hi[flat] += 0.5
    return lo, hi


def _within(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return (v >= lo) & (v <= hi)


class LineDetail:
    """A line layer thinned: its points, sorted by panel, series and x, split in series
    where a point is missing (``seg``), and the window each panel was sent for."""

    def __init__(self, rows: np.ndarray, panel: np.ndarray, xs: np.ndarray, ys: np.ndarray,
                 ss: np.ndarray, npanels: int, step: str | None,
                 paint: Callable[[Geometry], None]) -> None:  # fmt: skip
        valid = np.isfinite(xs) & np.isfinite(ys)
        new = np.ones(len(xs), dtype=bool)
        new[1:] = (panel[1:] != panel[:-1]) | (ss[1:] != ss[:-1]) | ~valid[:-1]
        seg = np.cumsum(new)
        self.rows, self.panel, self.x, self.y, self.seg = (
            a[valid] for a in (rows, panel, xs, ys, seg)
        )
        self.step = step
        self.paint = paint
        self.thin = np.bincount(self.panel, minlength=npanels) > THIN
        self.lo, self.hi = _extents(self.panel, self.x, npanels)
        self.windows: dict[int, Window] = {}

    @property
    def points(self) -> Geometry:
        """Every point, as Python selects them (a line's rows: those of its points)."""
        return Geometry(self.panel, self.x, self.y, self.x, self.y, self.rows)

    def geometry(self) -> Geometry:
        """The line as sent: thinned panels by M4, at each one's window or from the start."""
        npanels = len(self.thin)
        lo, hi = self.lo.copy(), self.hi.copy()
        columns = np.full(npanels, COLUMNS, dtype=np.int64)
        clipped = np.zeros(npanels, dtype=bool)
        for p, w in self.windows.items():
            lo[p], hi[p], columns[p], clipped[p] = w.x0, w.x1, w.nx, True
        pt = self.panel
        thin = self.thin[pt]
        inside = ~clipped[pt] | ((self.x >= lo[pt]) & (self.x <= hi[pt]))
        # and a point either side of a window, so the line runs on out of view
        same = self.seg[1:] == self.seg[:-1]
        near = inside.copy()
        near[:-1] |= inside[1:] & same
        near[1:] |= inside[:-1] & same
        pick = np.flatnonzero(thin & near)
        kept = pick[m4(self.seg[pick], self.x[pick], self.y[pick], lo, hi, columns, pt[pick])]
        keep = np.union1d(np.flatnonzero(~thin), kept)
        geom = polyline(self.rows[keep], pt[keep], self.x[keep], self.y[keep], self.seg[keep],
                        self.step)  # fmt: skip
        self.paint(geom)
        return geom

    def update(self, shown: dict[int, Shown]) -> bool:
        """Windows for the panels shown; True: some changed."""
        changed = False
        for p, v in shown.items():
            if p >= len(self.thin) or not self.thin[p]:
                continue
            cur = self.windows.get(p)
            new = self._want(p, v, cur)
            if new != cur:
                changed = True
                if new is None:
                    del self.windows[p]
                else:
                    self.windows[p] = new
        return changed

    def _want(self, p: int, v: Shown, cur: Window | None) -> Window | None:
        lo, hi = float(self.lo[p]), float(self.hi[p])
        span = v.x1 - v.x0
        if not (span > 0 and hi > lo and v.w > 0):
            return cur
        need = COLUMNS_PX * v.w / span  # columns per unit of x
        if COLUMNS / (hi - lo) * 1.5 >= need:
            return None  # as it started is detailed enough
        a, b = max(v.x0, lo), min(v.x1, hi)
        if a > b:
            return cur  # no data in view
        if cur is not None and cur.x0 <= a and cur.x1 >= b:
            have = cur.nx / (cur.x1 - cur.x0)
            if need / 1.5 <= have <= need * 2 or (cur.nx >= MAX_COLUMNS and have <= need * 2):
                return cur
        x0 = max(lo, v.x0 - span * MARGIN)
        x1 = min(hi, v.x1 + span * MARGIN)
        nx = int(min(MAX_COLUMNS, max(1, math.ceil(need * (x1 - x0)))))
        return Window(x0, x1, nx=nx)


class PointDetail:
    """A points layer with dense panels: its points (painted, sorted by panel), each one's
    colour level (``codes``) or number (``values``), and the window each dense panel was sent
    for. ``cell_colors``: RGBA of ``n`` cells from their points of each colour level (a
    category: the levels' colours mixed in proportion) or their mean number."""

    def __init__(self, geom: Geometry, npanels: int, values: np.ndarray | None,
                 cell_colors: Callable[[int, np.ndarray | None, np.ndarray | None], np.ndarray],
                 color_name: str | None, levels: list[str] | None) -> None:  # fmt: skip
        self.geom = geom
        self.values = values
        self.cell_colors = cell_colors
        self.color_name = color_name
        self.levels = levels
        self.starts = geom.starts(npanels)
        self.dense = np.diff(self.starts) > DENSE
        self.xlo, self.xhi = _extents(geom.panel, geom.x0, npanels)
        self.ylo, self.yhi = _extents(geom.panel, geom.y0, npanels)
        self.windows: dict[int, Window] = {}
        self.start: dict[int, Window] = {}
        """Each dense panel's cells as the plot starts (``start_at``)."""
        self.ref: float | None = None
        """The most points in a unit of area of a cell, as the plot starts: as opaque as a
        cell gets (cells of other sizes in proportion)."""

    def start_at(self, domains: list[tuple[float, float, float, float]],
                 sizes: list[tuple[float, float]]) -> None:  # fmt: skip
        """The cells to start with: over each panel's domain (x0, x1, y0, y1), about
        ``CELL_PX`` pixels for its size (w, h)."""
        for p in np.flatnonzero(self.dense):
            x0, x1, y0, y1 = domains[p]
            w, h = sizes[p]
            nx = int(min(MAX_CELLS, max(8, round(w / CELL_PX))))
            ny = int(min(MAX_CELLS, max(8, round(h / CELL_PX))))
            self.start[int(p)] = Window(x0, x1, y0, y1, nx, ny)

    def points(self) -> Geometry:
        """The points sent: those of panels not dense, and those in a raw window."""
        g = self.geom
        keep = ~self.dense[g.panel]
        for p, w in self.windows.items():
            if w.raw:
                s, e = self.starts[p], self.starts[p + 1]
                keep[s:e] = _within(g.x0[s:e], w.x0, w.x1) & _within(g.y0[s:e], w.y0, w.y1)
        return g.take(np.flatnonzero(keep))

    def cells(self) -> tuple[Table, Geometry, np.ndarray, np.ndarray]:
        """The cells sent: their table (points, of each colour), geometry (rows: the table's;
        codes: the colour level most of its points have), and the source rows of each
        (``rows[starts[i]:starts[i + 1]]``)."""
        npanels = len(self.dense)
        use = self.dense.copy()
        x0, x1, y0, y1 = self.xlo.copy(), self.xhi.copy(), self.ylo.copy(), self.yhi.copy()
        nx = np.full(npanels, 100, dtype=np.int64)  # (no start given: tests)
        ny = np.full(npanels, 100, dtype=np.int64)
        for p, w in {**self.start, **self.windows}.items():
            if w.raw:
                use[p] = False
            else:
                x0[p], x1[p], y0[p], y1[p], nx[p], ny[p] = w.x0, w.x1, w.y0, w.y1, w.nx, w.ny
        g = self.geom
        pt = g.panel
        with np.errstate(invalid="ignore"):
            fx = (g.x0 - x0[pt]) / (x1 - x0)[pt]
            fy = (g.y0 - y0[pt]) / (y1 - y0)[pt]
        idx = np.flatnonzero(use[pt] & (fx >= 0) & (fx <= 1) & (fy >= 0) & (fy <= 1))
        p = pt[idx]
        ix = np.minimum(np.floor(fx[idx] * nx[p]).astype(np.int64), nx[p] - 1)
        iy = np.minimum(np.floor(fy[idx] * ny[p]).astype(np.int64), ny[p] - 1)
        wide, high = int(nx.max()), int(ny.max())
        key = (p * high + iy) * wide + ix
        space = npanels * high * wide
        if space <= max(4 * len(key), 1 << 20):  # few possible cells: count them in place
            every = np.bincount(key, minlength=space)
            uniq = np.flatnonzero(every)
            counts = every[uniq]
            number = np.zeros(space, dtype=np.int64)
            number[uniq] = np.arange(len(uniq))
            inverse = number[key]
        else:
            uniq, inverse, counts = np.unique(key, return_inverse=True, return_counts=True)
            inverse = inverse.ravel()
        cx, rest = uniq % wide, uniq // wide
        cy, cp = rest % high, rest // high
        n = len(uniq)
        # a category colour: the points of each level in each cell; the most, its level
        mix = cc = None
        if g.codes is not None and self.levels:
            ncodes = len(self.levels)
            code = g.codes[idx].astype(np.int64)
            mix = np.bincount(inverse * ncodes + code, minlength=n * ncodes).reshape(n, ncodes)
            cc = mix.argmax(axis=1)
        cw = (x1 - x0) / nx
        ch = (y1 - y0) / ny
        left = x0[cp] + cx * cw[cp]
        bottom = y0[cp] + cy * ch[cp]
        geom = Geometry(cp, left, bottom, left + cw[cp], bottom + ch[cp], np.arange(n), codes=cc)
        means = None
        if self.values is not None:
            v = self.values[idx]
            ok = np.isfinite(v)
            total = np.bincount(inverse, weights=np.where(ok, v, 0.0), minlength=n)
            seen = np.bincount(inverse, weights=ok.astype(np.float64), minlength=n)
            means = np.divide(total, seen, out=np.full(n, np.nan), where=seen > 0)
        area = (cw * ch)[cp]
        if self.ref is None:
            self.ref = float((counts / area).max()) if n else 1.0
        full = np.maximum(self.ref * area, 2.0)  # the points of a cell as opaque as it gets
        alpha = np.clip(0.2 + 0.8 * np.log1p(counts) / np.log1p(full), 0.2, 1.0)
        rgba = self.cell_colors(n, mix, means).copy()
        rgba[:, 3] = np.round(rgba[:, 3] * alpha).astype(np.uint8)
        geom.rgba = rgba
        # the points of each level (the most's: the browser tells it, from the legend)
        columns: dict[str, np.ndarray] = {"points": counts}
        if mix is not None and self.levels and len(self.levels) <= TIP_LEVELS:
            for k, level in enumerate(self.levels):
                columns[f"{self.color_name} {level}"] = mix[:, k]
        if self.color_name is not None and means is not None:
            columns[f"mean {self.color_name}"] = means
        order = group_order(inverse, n)
        member_starts = np.r_[0, np.cumsum(counts)]
        return Table(columns), geom, member_starts, g.rows[idx][order]

    def update(self, shown: dict[int, Shown]) -> bool:
        changed = False
        for p, v in shown.items():
            if p >= len(self.dense) or not self.dense[p]:
                continue
            cur = self.windows.get(p)
            new = self._want(p, v, cur)
            if new != cur:
                changed = True
                if new is None:
                    del self.windows[p]
                else:
                    self.windows[p] = new
        return changed

    def _count(self, p: int, x0: float, x1: float, y0: float, y1: float) -> int:
        s, e = self.starts[p], self.starts[p + 1]
        g = self.geom
        return int(np.count_nonzero(_within(g.x0[s:e], x0, x1) & _within(g.y0[s:e], y0, y1)))

    def _want(self, p: int, v: Shown, cur: Window | None) -> Window | None:
        xlo, xhi = float(self.xlo[p]), float(self.xhi[p])
        ylo, yhi = float(self.ylo[p]), float(self.yhi[p])
        sx, sy = v.x1 - v.x0, v.y1 - v.y0
        if not (sx > 0 and sy > 0 and v.w > 0 and v.h > 0):
            return cur
        a, b, c, d = max(v.x0, xlo), min(v.x1, xhi), max(v.y0, ylo), min(v.y1, yhi)
        if a > b or c > d:
            return cur  # no data in view

        def covers(w: Window) -> bool:
            return w.x0 <= a and w.x1 >= b and w.y0 <= c and w.y1 >= d

        m = CELL_MARGIN
        wide = (max(xlo, v.x0 - sx * m), min(xhi, v.x1 + sx * m),
                max(ylo, v.y0 - sy * m), min(yhi, v.y1 + sy * m))  # fmt: skip
        if self._count(p, v.x0, v.x1, v.y0, v.y1) <= DENSE:
            if cur is not None and cur.raw and covers(cur):
                return cur
            if self._count(p, *wide) > 2 * DENSE:
                return Window(a, b, c, d, raw=True)
            return Window(*wide, raw=True)
        px, py = v.w / sx, v.h / sy  # px per unit

        def fits(cw: float, ch: float) -> bool:
            return CELL_PX / 2 <= cw * px <= CELL_PX * 2 and CELL_PX / 2 <= ch * py <= CELL_PX * 2

        start = self.start.get(p)
        if start is not None and fits((start.x1 - start.x0) / start.nx,
                                      (start.y1 - start.y0) / start.ny):  # fmt: skip
            return None  # as it started does
        if (cur is not None and not cur.raw and covers(cur)
                and fits((cur.x1 - cur.x0) / cur.nx, (cur.y1 - cur.y0) / cur.ny)):  # fmt: skip
            return cur
        x0, x1, y0, y1 = wide
        nx = int(min(MAX_CELLS, max(1, math.ceil((x1 - x0) * px / CELL_PX))))
        ny = int(min(MAX_CELLS, max(1, math.ceil((y1 - y0) * py / CELL_PX))))
        return Window(x0, x1, y0, y1, nx, ny)


Detail = LineDetail | PointDetail
