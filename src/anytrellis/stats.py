"""Summary marks: histograms, box plots, densities and smooth fits, computed from a
layer's rows in each panel (and for each colour), and drawn as the plain marks: bars,
rects, line segments, areas, bands and points. So they zoom, hover and brush like any
other layer, and a brush over them selects the rows they summarise (``Trellis.selected``).

Every panel's summary uses the same bins (a histogram) or the same grid of x values (a
density), set from all the rows, so the panels compare at a glance.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from anytrellis.data import Column, Table
from anytrellis.layers import Geometry, Layer, _stack, axis_values, expand, step_of

PANEL = "__panel__"
"""A summary table's panel column: its rows are already in their panels."""

FILL = 0.35
"""A box's body (and a filled density) is drawn at this much of the layer's opacity."""

Levels = list[str] | None
ColorLevels = dict[str, list[str]]
Build = Callable[[Levels, Levels, ColorLevels], Geometry]
"""A part's geometry, once the axes' and colours' categories are known."""


@dataclass
class Members:
    """The source rows each summary row stands for: ``rows[starts[i]:starts[i + 1]]``."""

    starts: np.ndarray
    rows: np.ndarray

    def of(self, mask: np.ndarray) -> np.ndarray:
        """The source rows of the summary rows in ``mask``, sorted, once each."""
        picked = np.repeat(mask, np.diff(self.starts))
        return np.unique(self.rows[picked])

    @staticmethod
    def each(rows: np.ndarray) -> Members:
        """One source row per summary row (outliers)."""
        return Members(np.arange(len(rows) + 1), rows)

    @staticmethod
    def grouped(inverse: np.ndarray, rows: np.ndarray, groups: int) -> Members:
        """Source row ``rows[k]`` stands in summary row ``inverse[k]``."""
        order = np.argsort(inverse, kind="stable")
        counts = np.bincount(inverse, minlength=groups)
        return Members(np.r_[0, np.cumsum(counts)], rows[order])


@dataclass
class Part:
    """One drawn layer of a summary mark."""

    layer: Layer
    """What is drawn: the mark's layer as a plain mark (bars, rect, line, area, points)."""
    table: Table
    """One row per summary: a bin, a box, a density sample, an outlier."""
    build: Build
    members: Members
    hide: tuple[str, ...] = ()
    """Axes the tooltip leaves out (a box's values are in its own rows instead)."""
    family: bool = False
    """Drawn from the same table as the mark's other family parts (a box's body and its
    lines): what selects one of its rows selects the row in all of them."""


def parts(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> list[Part]:
    """A summary layer's drawn parts."""
    if layer.mark == "hist":
        return hist(layer, table, panel_of, npanels)
    if layer.mark == "box":
        return box(layer, table, panel_of, npanels)
    if layer.mark == "density":
        return density(layer, table, panel_of, npanels)
    if layer.mark == "smooth":
        return smooth(layer, table, panel_of, npanels)
    if layer.mark == "violin":
        return violin(layer, table, panel_of, npanels)
    if layer.mark == "errorbar":
        return errorbar(layer, table, panel_of, npanels)
    raise ValueError(f"{layer.mark!r} is not a summary mark")


# ---- histograms ---------------------------------------------------------------------------


def hist(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> list[Part]:
    """Counts in bins shared by every panel, a bar per (panel, colour, bin): stacked by
    colour, or overlapping (``position="identity"``). A category x counts its categories."""
    assert layer.x is not None
    args = layer.stat_args
    col = table.column(layer.x)
    color = _color(layer, table)
    rows, panel = expand(panel_of, table.n, npanels, layer.facet)
    edges: np.ndarray | None = None
    if col.kind == "category":
        levels = list(col.levels)
        bin_of = col.level_codes()
        nbins = len(levels)
    else:
        edges = bin_edges(col, args["bins"], args["binwidth"])
        nbins = len(edges) - 1
        v = col.values
        bin_of = np.searchsorted(edges, v, side="right") - 1
        bin_of[v == edges[-1]] = nbins - 1  # the last bin holds its right edge
        bin_of[~np.isfinite(v) | (v < edges[0]) | (v > edges[-1])] = -1
    b = bin_of[rows]
    keep = b >= 0
    rows, panel, b = rows[keep], panel[keep], b[keep]
    labels, c = _color_codes(color, rows)
    nc = len(labels)
    key = (panel * nc + c) * nbins + b
    uniq, inverse, counts = np.unique(key, return_inverse=True, return_counts=True)
    inverse = inverse.ravel()
    p = uniq // (nc * nbins)
    ci = (uniq // nbins) % nc
    bi = uniq % nbins
    stat = args["stat"]
    total = np.bincount(p, weights=counts, minlength=npanels)[p]
    if stat == "count":
        value = counts.astype(np.float64)
    elif stat == "percent":
        value = 100.0 * counts / total
    else:  # density: each panel's bars cover an area of 1
        widths = np.ones(len(bi)) if edges is None else edges[bi + 1] - edges[bi]
        value = counts / total / widths
    cols = [Column(PANEL, "number", p.astype(np.float64))]
    extra: dict[str, np.ndarray] = {}
    if edges is None:
        names = np.array(levels, dtype=object)[bi]
        cols.append(Column(col.name, "category", names, col.levels))
        extra["bin"] = names
    else:
        lo, hi = edges[bi], edges[bi + 1]
        cols.append(Column(col.name, col.kind, lo))
        if col.kind == "time":
            extra[col.name] = _times(lo)
        shown_lo, shown_hi = _shown(col, lo, hi)
        extra["bin"] = _ranges(shown_lo, shown_hi, col.kind)
    cols.append(Column(stat, "number", value))
    if color is not None:
        cols.append(Column(color.name, "category", labels[ci], color.levels))
    if stat != "count":
        extra["count"] = counts
    out = _table(cols, extra)
    width = args["width"] if args["width"] is not None else (0.8 if edges is None else 1.0)

    def build(x_levels: Levels, _y: Any, color_levels: ColorLevels) -> Geometry:
        if edges is None:
            centre = axis_values(out.column(col.name), x_levels)
            x0, x1 = centre - width / 2, centre + width / 2
        else:
            mid = (edges[bi] + edges[bi + 1]) / 2
            half = (edges[bi + 1] - edges[bi]) * width / 2
            x0, x1 = mid - half, mid + half
        y0, y1 = np.zeros(len(value)), value.copy()
        if color is not None and layer.position == "stack" and len(value):
            code = axis_values(out.column(color.name), color_levels[color.name])
            order = np.lexsort((code, bi, p))
            s0, s1 = _stack(p[order], bi[order].astype(np.float64), value[order])
            y0[order], y1[order] = s0, s1
        return _sorted(Geometry(p, x0, y0, x1, y1, np.arange(len(value))))

    # the bin's range rather than its middle, and a count as a whole number
    tooltip = ["bin", stat] if stat == "count" else ["bin", stat, "count"]
    drawn = replace(layer, mark="bars", y=stat, tooltip=tooltip)
    members = Members.grouped(inverse, rows, len(uniq))
    return [Part(drawn, out, build, members, hide=("x", "y"))]


def bin_edges(col: Column, bins: Any, binwidth: Any) -> np.ndarray:
    """Bin edges over a column's values: ``bins`` edges as given, or ``binwidth`` wide
    (aligned to multiples of it), or ``bins`` equal bins over the values' range."""
    if isinstance(bins, Sequence | np.ndarray) and not isinstance(bins, str):
        edges = np.array([_value(b, col.kind) for b in bins], dtype=np.float64)
        if col.log:  # edges as values: on the axis, their logs
            with np.errstate(divide="ignore", invalid="ignore"):
                edges = np.where(edges > 0, np.log10(edges), np.nan)
            if not np.isfinite(edges).all():
                raise ValueError("bins= edges on a log axis must be above 0")
        if len(edges) < 2 or not np.all(np.diff(edges) > 0):
            raise ValueError("bins= edges must be at least two values, increasing")
        return edges
    v = col.values[np.isfinite(col.values)]
    if not len(v):
        return np.array([0.0, 1.0])
    lo, hi = float(v.min()), float(v.max())
    if binwidth is not None:
        width = _width(binwidth, col.kind)
        if not width > 0:
            raise ValueError(f"binwidth must be positive, got {binwidth!r}")
        start = np.floor(lo / width) * width
        n = max(1, int(np.ceil((hi - start) / width - 1e-9)))  # the last bin holds its edge
        if n > 100_000:
            raise ValueError(f"binwidth={binwidth!r} makes {n} bins; give a wider one")
        return start + width * np.arange(n + 1)
    if isinstance(bins, bool) or not isinstance(bins, int) or bins < 1:
        raise ValueError(f"bins must be a number of bins or a list of edges, got {bins!r}")
    if col.kind == "number" and hi > lo:
        # about that many bins, of a round width (1, 2, 2.5 or 5 times a power of ten) on
        # round edges, so a bin reads "180 – 185"
        width = _round_width((hi - lo) / bins)
        start = np.floor(lo / width) * width
        n = max(1, int(np.ceil((hi - start) / width - 1e-9)))  # the last bin holds its edge
        return start + width * np.arange(n + 1)
    return np.histogram_bin_edges(v, bins=bins)


def _round_width(raw: float) -> float:
    """The round width nearest ``raw`` (on a log scale)."""
    power = 10.0 ** np.floor(np.log10(raw))
    steps = np.array([1.0, 2.0, 2.5, 5.0, 10.0]) * power
    return float(steps[np.argmin(np.abs(np.log(steps / raw)))])


# ---- values by position: box plots, violins, error bars ------------------------------------


@dataclass
class _Groups:
    """A layer's values in groups, one per (panel, position, colour), sorted within each:
    what a box, a violin or an error bar summarises. Vertical, or horizontal when y is
    the category and x the numbers."""

    layer: Layer
    horizontal: bool
    pos: Column
    """The positions (x, or y when horizontal)."""
    val: Column
    """The values (y, or x when horizontal)."""
    color: Column | None
    puniq: np.ndarray
    labels: np.ndarray
    guniq: np.ndarray
    sv: np.ndarray
    """The values, sorted by group and within it."""
    sg: np.ndarray
    srows: np.ndarray
    counts: np.ndarray
    starts: np.ndarray

    @property
    def npos(self) -> int:
        return max(len(self.puniq), 1)

    @property
    def nc(self) -> int:
        return len(self.labels)

    @property
    def gp(self) -> np.ndarray:
        """Each group's panel."""
        return self.guniq // (self.npos * self.nc)

    @property
    def gpos(self) -> np.ndarray:
        """Each group's position (index in ``puniq``)."""
        return (self.guniq // self.nc) % self.npos

    @property
    def gc(self) -> np.ndarray:
        """Each group's colour (index in ``labels``)."""
        return self.guniq % self.nc

    @property
    def first(self) -> np.ndarray:
        return self.starts[:-1]

    def quantile(self, f: float) -> np.ndarray:
        """Each group's ``f`` quantile (linear between values)."""
        h = (self.counts - 1) * f
        lo = np.floor(h).astype(np.int64)
        hi = np.ceil(h).astype(np.int64)
        sv, first = self.sv, self.first
        return sv[first + lo] + (h - lo) * (sv[first + hi] - sv[first + lo])

    def position_column(self, index: np.ndarray) -> Column:
        values = self.puniq[index]
        if self.pos.kind == "category":
            return Column(self.pos.name, "category", values.astype(object), self.pos.levels)
        return Column(self.pos.name, self.pos.kind, values.astype(np.float64))

    def raw_position(self, index: np.ndarray) -> np.ndarray:
        values = self.puniq[index]
        if self.pos.log:
            return 10.0 ** values.astype(np.float64)
        return _times(values) if self.pos.kind == "time" else values

    def columns(self, index: np.ndarray, value: np.ndarray) -> list[Column]:
        """A summary table's columns for groups ``index``: panel, position, ``value`` (on
        the values' axis) and colour."""
        cols = [Column(PANEL, "number", self.gp[index].astype(np.float64)),
                self.position_column(self.gpos[index]),
                Column(self.val.name, "number", value)]  # fmt: skip
        if self.color is not None:
            cols.append(Column(self.color.name, "category", self.labels[self.gc[index]],
                               self.color.levels))  # fmt: skip
        return cols

    def slots(self, width: float) -> _Slots:
        step = 1.0 if self.pos.kind == "category" else step_of([self.puniq.astype(np.float64)])
        color = self.color
        dodge = color is not None and color.name != self.pos.name and \
            self.layer.position == "dodge"  # fmt: skip
        return _Slots(self.pos.name, color.name if dodge and color else None, self.horizontal,
                      width * step)  # fmt: skip


def _grouped(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> _Groups:
    """The layer's values grouped by panel, position (x, or a category y) and colour."""
    assert layer.x is not None
    assert layer.y is not None
    xc, yc = table.column(layer.x), table.column(layer.y)
    horizontal = yc.kind == "category" and xc.kind != "category"
    pos, val = (yc, xc) if horizontal else (xc, yc)
    if val.kind != "number":
        raise ValueError(
            f"{layer.mark}(): the values must be numbers; {val.name!r} holds {val.kind}s (one "
            "of x and y gives the positions, the other the numbers)"
        )
    color = _color(layer, table)
    rows, panel = expand(panel_of, table.n, npanels, layer.facet)
    v = val.values[rows]
    keep = np.isfinite(v)
    if pos.kind != "category":
        keep &= np.isfinite(pos.values[rows])
    else:
        keep &= pos.level_codes()[rows] >= 0
    rows, panel, v = rows[keep], panel[keep], v[keep]
    if pos.kind == "category":  # by code: a million strings don't sort fast
        puniq, pi_ = np.array(pos.levels, dtype=object), pos.level_codes()[rows]
    else:
        puniq, pi_ = _codes(pos.values[rows])
    labels, c = _color_codes(color, rows)
    npos, nc = max(len(puniq), 1), len(labels)
    guniq, ginv = _codes((panel * npos + pi_) * nc + c)
    order = np.lexsort((v, ginv))
    counts = np.bincount(ginv[order], minlength=len(guniq))
    # intp: reduceat takes only the platform's index type (int32 in WebAssembly)
    starts = np.r_[0, np.cumsum(counts)].astype(np.intp)
    return _Groups(layer, horizontal, pos, val, color, puniq, labels, guniq, v[order],
                   ginv[order], rows[order], counts, starts)  # fmt: skip


@dataclass
class _Slots:
    """Where each group sits across its axis: centred on its position, ``span`` wide, or
    (``dodge``: a colour column's name) side by side by colour."""

    pos: str
    dodge: str | None
    horizontal: bool
    span: float

    def centres(self, tbl: Table, x_levels: Levels, y_levels: Levels,
                color_levels: ColorLevels) -> tuple[np.ndarray, float]:  # fmt: skip
        """Each row's centre (on the positions' axis) and its half width."""
        centre = axis_values(tbl.column(self.pos), y_levels if self.horizontal else x_levels)
        if self.dodge is None:
            return centre, self.span / 2
        k = max(len(color_levels[self.dodge]), 1)
        code = axis_values(tbl.column(self.dodge), color_levels[self.dodge])
        slot = self.span / k
        return centre - self.span / 2 + (code + 0.5) * slot, slot * 0.9 / 2

    def oriented(self, panel: np.ndarray, a0: np.ndarray, v0: np.ndarray, a1: np.ndarray,
                 v1: np.ndarray, rows: np.ndarray, line: bool = False) -> Geometry:  # fmt: skip
        """Geometry from (position, value) corners, turned for horizontal groups."""
        if self.horizontal:
            g = Geometry(panel, v0, a0, v1, a1, rows)
        else:
            g = Geometry(panel, a0, v0, a1, v1, rows)
        if line:
            g.rows_end = rows.copy()
        return _sorted(g)


def box(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> list[Part]:
    """A box per (panel, position, colour): the quartiles, a line at the median, whiskers
    to the furthest values within ``whis`` IQRs of the box, and the values beyond as
    points. Vertical, or horizontal when y is the category and x the numbers."""
    args = layer.stat_args
    g = _grouped(layer, table, panel_of, npanels)
    sv, sg, srows, first = g.sv, g.sg, g.srows, g.first
    q1, med, q3 = g.quantile(0.25), g.quantile(0.5), g.quantile(0.75)
    iqr = q3 - q1
    whis = float(args["whis"])
    inside = (sv >= (q1 - whis * iqr)[sg]) & (sv <= (q3 + whis * iqr)[sg])
    if len(sv):
        wlo = np.minimum.reduceat(np.where(inside, sv, np.inf), first)
        whi = np.maximum.reduceat(np.where(inside, sv, -np.inf), first)
    else:
        wlo = whi = np.zeros(0)
    wlo = np.where(np.isfinite(wlo), np.minimum(wlo, q1), q1)
    whi = np.where(np.isfinite(whi), np.maximum(whi, q3), q3)
    groups = np.arange(len(g.guniq))
    shown_med, shown_q1, shown_q3, shown_lo, shown_hi = _shown(g.val, med, q1, q3, wlo, whi)
    stats_text = {
        g.pos.name: g.raw_position(g.gpos),
        "n": g.counts,
        "median": shown_med,
        "q1": shown_q1,
        "q3": shown_q3,
        "whiskers": _ranges(shown_lo, shown_hi, "number"),
    }
    boxes = _table(g.columns(groups, med), stats_text)
    og = sg[~inside]
    orows, ov = srows[~inside], sv[~inside]
    if not args["outliers"]:
        orows, og, ov = orows[:0], og[:0], ov[:0]
    user_tips = {name: table.raw(name)[orows] for name in layer.tooltip}
    outliers = _table(g.columns(og, ov), {g.pos.name: g.raw_position(g.gpos[og]), **user_tips})
    slots = g.slots(float(args["width"]))
    gp = g.gp

    def build_body(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, h = slots.centres(boxes, xl, yl, cl)
        return slots.oriented(gp, c_ - h, q1, c_ + h, q3, groups)

    def build_lines(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, h = slots.centres(boxes, xl, yl, cl)
        left, right = c_ - h, c_ + h
        segments = [  # the outline, the median, the whiskers
            (left, q1, right, q1), (right, q1, right, q3), (right, q3, left, q3),
            (left, q3, left, q1), (left, med, right, med), (c_, q1, c_, wlo), (c_, q3, c_, whi),
        ]  # fmt: skip
        a0, v0, a1, v1 = (np.concatenate([s[i] for s in segments]) for i in range(4))
        return slots.oriented(np.tile(gp, 7), a0, v0, a1, v1, np.tile(groups, 7), line=True)

    def build_points(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, _ = slots.centres(outliers, xl, yl, cl)
        return slots.oriented(gp[og], c_, ov, c_.copy(), ov.copy(), np.arange(len(og)))

    tips = [g.pos.name, "n", "median", "q1", "q3", "whiskers"]
    members = Members(g.starts, srows)
    body = replace(layer, mark="rect", opacity=layer.opacity * FILL, tooltip=tips)
    lines = replace(layer, mark="line", tooltip=tips)
    points = replace(layer, mark="points", tooltip=list(layer.tooltip))
    return [
        Part(body, boxes, build_body, members, hide=("x", "y"), family=True),
        Part(lines, boxes, build_lines, members, hide=("x", "y"), family=True),
        Part(points, outliers, build_points, Members.each(orows)),
    ]


# ---- violins -------------------------------------------------------------------------------

VIOLIN_SCALES = ("area", "count", "width")
VIOLIN_INNER = ("quartiles", "points", None)


def violin(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> list[Part]:
    """A violin per (panel, position, colour): the values' density (a Gaussian kernel
    estimate, ``cut`` bandwidths past them) mirrored around the position, as wide as
    ``scale`` says: ``"area"``, every violin the same area; ``"count"``, areas as the
    counts; ``"width"``, every violin the same width. Inside it: its median and quartiles
    (``inner="quartiles"``), or its values (``"points"``)."""
    args = layer.stat_args
    g = _grouped(layer, table, panel_of, npanels)
    groups = np.arange(len(g.guniq))
    q1, med, q3 = g.quantile(0.25), g.quantile(0.5), g.quantile(0.75)
    cut, gridsize, adjust = float(args["cut"]), int(args["gridsize"]), float(args["bw_adjust"])
    grids: list[np.ndarray] = []
    dens: list[np.ndarray] = []
    owner: list[np.ndarray] = []
    for k in groups:
        s = g.sv[g.starts[k] : g.starts[k + 1]]
        if len(s) < 2 or s[-1] <= s[0]:
            continue
        bw = adjust * float(np.std(s, ddof=1)) * len(s) ** -0.2
        grid = np.linspace(s[0] - cut * bw, s[-1] + cut * bw, gridsize)
        grids.append(grid)
        dens.append(_kde(s, grid, bw))
        owner.append(np.full(gridsize, k))
    ys = np.concatenate(grids) if grids else np.zeros(0)
    d = np.concatenate(dens) if dens else np.zeros(0)
    k_of = np.concatenate(owner) if owner else np.zeros(0, np.int64)
    # each sample's half width, as a share of the slot's half width
    peak = np.zeros(len(groups))
    if len(d):
        np.maximum.at(peak, k_of, d)
    scale = args["scale"]
    if scale == "width":
        w = d / np.where(peak > 0, peak, 1)[k_of]
    elif scale == "count":
        weight = g.counts.astype(np.float64)
        top = float((peak * weight).max()) if len(d) else 1.0
        w = d * weight[k_of] / (top or 1.0)
    else:
        w = d / (float(peak.max()) if len(d) else 1.0)
    # each group's width at its median and quartiles (a group of one value: half)
    at_q = np.full((3, len(groups)), 0.5)
    for i, k in enumerate(np.unique(k_of)):
        sl = slice(i * gridsize, (i + 1) * gridsize)
        at_q[:, k] = np.interp([q1[k], med[k], q3[k]], ys[sl], w[sl])
    pair = np.flatnonzero(k_of[1:] == k_of[:-1]) if len(k_of) else np.zeros(0, np.int64)
    a, b = pair, pair + 1
    kp = k_of[a]
    shown_med, shown_q1, shown_q3 = _shown(g.val, med, q1, q3)
    violins = _table(g.columns(groups, med), {g.pos.name: g.raw_position(g.gpos), "n": g.counts,
                                              "median": shown_med, "q1": shown_q1,
                                              "q3": shown_q3})  # fmt: skip
    slots = g.slots(float(args["width"]))
    gp = g.gp

    def build_fill(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, h = slots.centres(violins, xl, yl, cl)
        c, ya, yb = c_[kp], ys[a], ys[b]
        wa, wb = w[a] * h, w[b] * h
        if slots.horizontal:  # a band along x: its upper edge, its lower as the base
            geom = Geometry(gp[kp], ya, c + wa, yb, c + wb, kp, rows_end=kp.copy(),
                            base0=c - wa, base1=c - wb)  # fmt: skip
            return _sorted(geom)
        # vertical: each slice between two samples as trapezoids with vertical sides: a
        # rectangle as wide as its narrower end, and a triangle on each side
        m, big = np.minimum(wa, wb), np.maximum(wa, wb)
        ym, yb_ = np.where(wa <= wb, ya, yb), np.where(wa <= wb, yb, ya)
        x0 = np.concatenate([c - m, c + m, c - big])
        y0 = np.concatenate([ya, ym, yb_])
        x1 = np.concatenate([c + m, c + big, c - m])
        y1 = np.concatenate([ya, yb_, ym])
        base = np.concatenate([yb, yb_, yb_])
        rows = np.tile(kp, 3)
        geom = Geometry(np.tile(gp[kp], 3), x0, y0, x1, y1, rows, rows_end=rows.copy(),
                        base0=base, base1=base.copy())  # fmt: skip
        return _sorted(geom)

    def build_lines(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, h = slots.centres(violins, xl, yl, cl)
        c, wa, wb = c_[kp], w[a] * h, w[b] * h
        segs = [(c + wa, ys[a], c + wb, ys[b]), (c - wa, ys[a], c - wb, ys[b])]  # its sides
        owners = [kp, kp]
        if args["inner"] == "quartiles":  # the median across it, the quartiles half way
            for q, f, row in ((med, 1.0, 1), (q1, 0.5, 0), (q3, 0.5, 2)):
                half = at_q[row] * h * f
                segs.append((c_ - half, q, c_ + half, q))
                owners.append(groups)
        a0, v0, a1, v1 = (np.concatenate([s[i] for s in segs]) for i in range(4))
        rows = np.concatenate(owners)
        return slots.oriented(gp[rows], a0, v0, a1, v1, rows, line=True)

    tips = [g.pos.name, "n", "median", "q1", "q3"]
    members = Members(g.starts, g.srows)
    fill = replace(layer, mark="band", opacity=layer.opacity * FILL, tooltip=tips)
    lines = replace(layer, mark="line", tooltip=tips)
    out = [
        Part(fill, violins, build_fill, members, hide=("x", "y"), family=True),
        Part(lines, violins, build_lines, members, hide=("x", "y"), family=True),
    ]
    if args["inner"] == "points":
        user_tips = {name: table.raw(name)[g.srows] for name in layer.tooltip}
        values = _table(g.columns(g.sg, g.sv), {g.pos.name: g.raw_position(g.gpos[g.sg]),
                                               **user_tips})  # fmt: skip

        def build_points(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
            c_, _ = slots.centres(values, xl, yl, cl)
            return slots.oriented(gp[g.sg], c_, g.sv, c_.copy(), g.sv.copy(),
                                  np.arange(len(g.sv)))  # fmt: skip

        dots = replace(layer, mark="points", tooltip=list(layer.tooltip))
        out.append(Part(dots, values, build_points, Members.each(g.srows)))
    return out


# ---- error bars ----------------------------------------------------------------------------

EXTENTS = ("ci", "se", "sd", "range")


def errorbar(layer: Layer, table: Table, panel_of: np.ndarray | None,
             npanels: int) -> list[Part]:  # fmt: skip
    """Error bars: from given lows to highs (``ymin`` and ``ymax``, or ``xmin`` and
    ``xmax``), or, from the values, around each group's mean: ``extent="ci"`` (its
    ``level`` confidence interval, Student's t), ``"se"`` (one standard error), ``"sd"``
    (one standard deviation) or ``"range"`` (the lowest value to the highest). Each with
    caps ``cap`` of a position's step wide, and its centre (the mean, or ``y``/``x``) as a
    point."""
    args = layer.stat_args
    if args.get("lo") is None:
        return _errorbar_summary(layer, table, panel_of, npanels)
    return _errorbar_given(layer, table, panel_of, npanels)


def _errorbar_summary(layer: Layer, table: Table, panel_of: np.ndarray | None,
                      npanels: int) -> list[Part]:  # fmt: skip
    args = layer.stat_args
    g = _grouped(layer, table, panel_of, npanels)
    groups = np.arange(len(g.guniq))
    n = g.counts.astype(np.float64)
    first = g.first
    if len(g.sv):
        mean = np.add.reduceat(g.sv, first) / n
        dev = g.sv - mean[g.sg]
        sd = np.sqrt(np.add.reduceat(dev * dev, first) / np.maximum(n - 1, 1))
    else:
        mean = sd = np.zeros(0)
    sd = np.where(n >= 2, sd, np.nan)
    extent = args["extent"]
    if extent == "range":
        lo = np.minimum.reduceat(g.sv, first) if len(g.sv) else np.zeros(0)
        hi = np.maximum.reduceat(g.sv, first) if len(g.sv) else np.zeros(0)
        label = "range"
    else:
        if extent == "ci":
            p_hi = 1 - (1 - float(args["level"])) / 2
            t = np.array([_t_quantile(p_hi, k - 1) if k >= 2 else np.nan for k in n])
            half = t * sd / np.sqrt(n)
            label = f"{float(args['level']):.0%} CI"
        elif extent == "se":
            half = sd / np.sqrt(n)
            label = "mean ± SE"
        else:
            half = sd
            label = "mean ± SD"
        lo, hi = mean - half, mean + half
    shown_mean, shown_lo, shown_hi = _shown(g.val, mean, lo, hi)
    text = _ranges(shown_lo, shown_hi, "number", digits=4)
    text[~np.isfinite(lo)] = ""
    bars = _table(g.columns(groups, mean), {g.pos.name: g.raw_position(g.gpos), "n": g.counts,
                                            "mean": shown_mean, label: text})  # fmt: skip
    tips = [g.pos.name, "n", "mean", label]
    return _errorbar_parts(layer, bars, g.gp, g.slots(float(args["width"])), mean, lo, hi,
                           Members(g.starts, g.srows), tips)  # fmt: skip


def _errorbar_given(layer: Layer, table: Table, panel_of: np.ndarray | None,
                    npanels: int) -> list[Part]:  # fmt: skip
    args = layer.stat_args
    horizontal = bool(args["horizontal"])
    pos_name = layer.y if horizontal else layer.x
    centre_name = layer.x if horizontal else layer.y
    assert pos_name is not None
    pos = table.column(pos_name)
    ends = [table.column(args["lo"]), table.column(args["hi"])]
    values = [*ends, *([table.column(centre_name)] if centre_name else [])]
    for col in values:
        if col.kind == "category":
            raise ValueError(f"errorbar(): {col.name!r} holds categories; the ends (and the "
                             "centre) must be numbers or times")  # fmt: skip
    rows, panel = expand(panel_of, table.n, npanels, layer.facet)
    lo, hi = ends[0].values[rows], ends[1].values[rows]
    keep = np.isfinite(lo) & np.isfinite(hi)
    keep &= (pos.level_codes()[rows] >= 0) if pos.kind == "category" else \
        np.isfinite(pos.values[rows])  # fmt: skip
    rows, panel, lo, hi = rows[keep], panel[keep], lo[keep], hi[keep]
    centre = table.column(centre_name).values[rows] if centre_name else None
    color = _color(layer, table)
    value_name = centre_name or ends[0].name
    cols = [Column(PANEL, "number", panel.astype(np.float64)), _take(pos, rows),
            Column(value_name, values[-1].kind, centre if centre is not None else lo,
                   log=values[-1].log)]  # fmt: skip
    if color is not None:
        cols.append(_take(color, rows))
    names = [pos_name, *([centre_name] if centre_name else []), ends[0].name, ends[1].name]
    raw = {name: table.raw(name)[rows] for name in dict.fromkeys([*names, *layer.tooltip])}
    bars = _table(cols, raw)
    positions = pos.values[rows] if pos.kind != "category" else np.zeros(0)
    step = 1.0 if pos.kind == "category" else step_of([positions])
    dodge = color is not None and color.name != pos_name and layer.position == "dodge"
    slots = _Slots(pos_name, color.name if dodge and color else None, horizontal,
                   float(args["width"]) * step)  # fmt: skip
    tips = list(dict.fromkeys([*names, *layer.tooltip]))
    # the drawn parts' x and y: the table's position and value columns
    axes = {"x": value_name, "y": pos_name} if horizontal else {"x": pos_name, "y": value_name}
    return _errorbar_parts(replace(layer, **axes), bars, panel, slots, centre, lo, hi,
                           Members.each(rows), tips)  # fmt: skip


def _errorbar_parts(layer: Layer, bars: Table, panel: np.ndarray, slots: _Slots,
                    centre: np.ndarray | None, lo: np.ndarray, hi: np.ndarray,
                    members: Members, tips: list[str]) -> list[Part]:  # fmt: skip
    """An error bar per row of ``bars``: a line from ``lo`` to ``hi`` with caps, and its
    centre as a point."""
    args = layer.stat_args
    rows = np.arange(len(lo))
    drawn = np.isfinite(lo) & np.isfinite(hi)
    cap = float(args["cap"])
    width = float(args["width"])

    def build_lines(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, h = slots.centres(bars, xl, yl, cl)
        r = rows[drawn]
        c, a, b = c_[r], lo[r], hi[r]
        segs = [(c, a, c, b)]
        if cap > 0:
            half = h * cap / width  # a share of the step; dodged, of each one's slot
            segs += [(c - half, a, c + half, a), (c - half, b, c + half, b)]
        a0, v0, a1, v1 = (np.concatenate([s[i] for s in segs]) for i in range(4))
        owners = np.tile(r, len(segs))
        return slots.oriented(panel[owners], a0, v0, a1, v1, owners, line=True)

    lines = replace(layer, mark="line", tooltip=tips)
    if centre is None or not args["points"]:
        return [Part(lines, bars, build_lines, members, hide=("x", "y"))]
    mid = np.asarray(centre)
    shown = np.isfinite(mid)

    def build_points(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, _ = slots.centres(bars, xl, yl, cl)
        r = rows[shown]
        return slots.oriented(panel[r], c_[r], mid[r], c_[r].copy(), mid[r].copy(), r)

    points = replace(layer, mark="points", tooltip=tips)
    return [
        Part(lines, bars, build_lines, members, hide=("x", "y"), family=True),
        Part(points, bars, build_points, members, hide=("x", "y"), family=True),
    ]


# ---- densities ----------------------------------------------------------------------------


def density(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> list[Part]:
    """A Gaussian kernel density estimate per (panel, colour), each covering an area of 1,
    on an x grid shared by every panel, ``cut`` bandwidths past the data; the bandwidth
    is Scott's rule times ``bw_adjust``. ``fill``: the area under it too."""
    assert layer.x is not None
    args = layer.stat_args
    col = table.column(layer.x)
    if col.kind == "category":
        raise ValueError(f"density(): x must be numbers or times; {col.name!r} holds categories")
    color = _color(layer, table)
    rows, panel = expand(panel_of, table.n, npanels, layer.facet)
    v = col.values[rows]
    keep = np.isfinite(v)
    rows, panel, v = rows[keep], panel[keep], v[keep]
    labels, c = _color_codes(color, rows)
    nc = len(labels)
    guniq, ginv = _codes(panel * nc + c)
    order = np.lexsort((v, ginv))
    sv, sg, srows = v[order], ginv[order], rows[order]
    counts = np.bincount(sg, minlength=len(guniq))
    starts = np.r_[0, np.cumsum(counts)].astype(np.int64)
    cut, gridsize = float(args["cut"]), int(args["gridsize"])
    bws = np.zeros(len(guniq))
    for g in range(len(guniq)):
        s = sv[starts[g] : starts[g + 1]]
        if len(s) >= 2 and s[-1] > s[0]:
            bws[g] = float(args["bw_adjust"]) * float(np.std(s, ddof=1)) * len(s) ** -0.2
    valid = np.flatnonzero(bws > 0)
    lo = min((sv[starts[g]] - cut * bws[g] for g in valid), default=0.0)
    hi = max((sv[starts[g + 1] - 1] + cut * bws[g] for g in valid), default=1.0)
    grid = np.linspace(lo, hi, gridsize)
    xs_all, ds_all, panel_all, color_all, curve_all = [], [], [], [], []
    sample_of = np.full(len(sv), -1, dtype=np.int64)
    at = 0
    for k, g in enumerate(valid):
        s = sv[starts[g] : starts[g + 1]]
        bw = bws[g]
        xs = grid[(grid >= s[0] - cut * bw) & (grid <= s[-1] + cut * bw)]
        if len(xs) < 2:
            continue
        xs_all.append(xs)
        ds_all.append(_kde(s, xs, bw))
        panel_all.append(np.full(len(xs), guniq[g] // nc))
        color_all.append(np.full(len(xs), guniq[g] % nc))
        curve_all.append(np.full(len(xs), k))
        # each value stands in the sample at or before it (a segment's start)
        idx = np.clip(np.searchsorted(xs, s, side="right") - 1, 0, len(xs) - 1)
        sample_of[starts[g] : starts[g + 1]] = at + idx
        at += len(xs)
    cat = lambda parts, dtype: np.concatenate(parts) if parts else np.zeros(0, dtype)  # noqa: E731
    x, d = cat(xs_all, np.float64), cat(ds_all, np.float64)
    p, ci, curve = cat(panel_all, np.int64), cat(color_all, np.int64), cat(curve_all, np.int64)
    cols = [Column(PANEL, "number", p.astype(np.float64)), Column(col.name, col.kind, x),
            Column("density", "number", d)]  # fmt: skip
    if color is not None:
        cols.append(Column(color.name, "category", labels[ci], color.levels))
    out = _table(cols, {col.name: _times(x)} if col.kind == "time" else {})
    counted = sample_of >= 0
    members = Members.grouped(sample_of[counted], srows[counted], len(x))
    pair = np.flatnonzero(curve[1:] == curve[:-1]) if len(curve) else np.zeros(0, np.int64)

    def build(_x: Any, _y: Any, _c: Any, area: bool = False) -> Geometry:
        a, b = pair, pair + 1
        g = Geometry(p[a], x[a], d[a], x[b], d[b], a, rows_end=b)
        if area:
            g.base0, g.base1 = np.zeros(len(a)), np.zeros(len(a))
        return _sorted(g)

    line = replace(layer, mark="line", y="density", tooltip=[])
    if not args["fill"]:
        return [Part(line, out, build, members)]
    filled = replace(layer, mark="area", y="density", tooltip=[], opacity=layer.opacity * FILL)
    return [
        Part(filled, out, lambda xl, yl, cl: build(xl, yl, cl, area=True), members, family=True),
        Part(line, out, build, members, family=True),
    ]


# ---- smooth fits ---------------------------------------------------------------------------


def smooth(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> list[Part]:
    """A fit of y on x per (panel, colour), at ``n`` points over its x range (or every
    panel's, ``fullrange``), with a confidence band for the mean: least squares, or loess
    (local linear fits with tricube weights over a ``span`` share of the points)."""
    assert layer.x is not None
    assert layer.y is not None
    args = layer.stat_args
    xc, yc = table.column(layer.x), table.column(layer.y)
    for c in (xc, yc):
        if c.kind == "category":
            raise ValueError(
                f"smooth(): x and y must be numbers or times; {c.name!r} holds categories"
            )
    color = _color(layer, table)
    rows, panel = expand(panel_of, table.n, npanels, layer.facet)
    xv, yv = xc.values[rows], yc.values[rows]
    keep = np.isfinite(xv) & np.isfinite(yv)
    rows, panel, xv, yv = rows[keep], panel[keep], xv[keep], yv[keep]
    labels, c = _color_codes(color, rows)
    nc = len(labels)
    guniq, ginv = _codes(panel * nc + c)
    order = np.lexsort((xv, ginv))
    sx, sy, sg, srows = xv[order], yv[order], ginv[order], rows[order]
    starts = np.r_[0, np.cumsum(np.bincount(sg, minlength=len(guniq)))].astype(np.int64)
    full = (float(sx.min()), float(sx.max())) if args["fullrange"] and len(sx) else None
    n = int(args["n"])
    p_hi = 1 - (1 - float(args["level"])) / 2
    pieces: dict[str, list[np.ndarray]] = {k: [] for k in ("x", "fit", "lo", "hi", "p", "c", "k")}
    sample_of = np.full(len(sx), -1, dtype=np.int64)
    at = 0
    for k in range(len(guniq)):
        a, b = starts[k], starts[k + 1]
        gx, gy = sx[a:b], sy[a:b]
        if gx[-1] <= gx[0]:  # fewer than two distinct x
            continue
        lo, hi = full or (float(gx[0]), float(gx[-1]))
        grid = np.linspace(lo, hi, n)
        mid, scale = float(gx.mean()), float(gx.std()) or 1.0
        u, u0 = (gx - mid) / scale, (grid - mid) / scale
        if args["method"] == "linear":
            fit, se, df = _linear(u, gy, u0)
        else:
            fit, se, df = _loess(u, gy, u0, float(args["span"]))
        half = _t_quantile(p_hi, df) * se if args["se"] and df >= 1 else np.full(n, np.nan)
        pieces["x"].append(grid)
        pieces["fit"].append(fit)
        pieces["lo"].append(fit - half)
        pieces["hi"].append(fit + half)
        pieces["p"].append(np.full(n, guniq[k] // nc))
        pieces["c"].append(np.full(n, guniq[k] % nc))
        pieces["k"].append(np.full(n, k))
        idx = np.clip(np.searchsorted(grid, gx, side="right") - 1, 0, n - 1)
        sample_of[a:b] = at + idx
        at += n
    cat = {k: np.concatenate(v) if v else np.zeros(0) for k, v in pieces.items()}
    x, fit, lower, upper = cat["x"], cat["fit"], cat["lo"], cat["hi"]
    p, ci, curve = (cat[k].astype(np.int64) for k in ("p", "c", "k"))
    interval = f"{float(args['level']):.0%} interval"
    shown_lo, shown_hi = _shown(yc, lower, upper)
    text = _ranges(shown_lo, shown_hi, "number", digits=4)
    text[~np.isfinite(lower)] = ""
    cols = [Column(PANEL, "number", p.astype(np.float64)), Column(xc.name, xc.kind, x),
            Column(yc.name, "number", fit)]  # fmt: skip
    if color is not None:
        cols.append(Column(color.name, "category", labels[ci], color.levels))
    extra: dict[str, np.ndarray] = {interval: text}
    if xc.kind == "time":
        extra[xc.name] = _times(x)
    out = _table(cols, extra)
    counted = sample_of >= 0
    members = Members.grouped(sample_of[counted], srows[counted], len(x))
    pair = np.flatnonzero(curve[1:] == curve[:-1]) if len(curve) else np.zeros(0, np.int64)

    def build_line(_x: Any, _y: Any, _c: Any) -> Geometry:
        a, b = pair, pair + 1
        return _sorted(Geometry(p[a], x[a], fit[a], x[b], fit[b], a, rows_end=b))

    def build_band(_x: Any, _y: Any, _c: Any) -> Geometry:
        a = pair[np.isfinite(lower[pair]) & np.isfinite(lower[pair + 1])]
        b = a + 1
        g = Geometry(p[a], x[a], upper[a], x[b], upper[b], a, rows_end=b)
        g.base0, g.base1 = lower[a], lower[b]
        return _sorted(g)

    has_band = bool(args["se"]) and bool(np.isfinite(lower).any())
    line = replace(layer, mark="line", tooltip=[interval] if has_band else [])
    if not has_band:
        return [Part(line, out, build_line, members)]
    band = replace(layer, mark="band", opacity=layer.opacity * 0.25, tooltip=[interval])
    return [
        Part(band, out, build_band, members, hide=("y",), family=True),
        Part(line, out, build_line, members, family=True),
    ]


def _linear(u: np.ndarray, y: np.ndarray, at: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Least squares: the fit at ``at``, its standard error, and the residual degrees of
    freedom."""
    n = len(u)
    ub, yb = u.mean(), y.mean()
    suu = float(((u - ub) ** 2).sum())
    slope = float(((u - ub) * (y - yb)).sum()) / suu
    fit = yb + slope * (at - ub)
    df = n - 2
    if df < 1:
        return fit, np.full(len(at), np.nan), float(df)
    sigma = np.sqrt(float(((y - (yb + slope * (u - ub))) ** 2).sum()) / df)
    return fit, sigma * np.sqrt(1 / n + (at - ub) ** 2 / suu), float(df)


def _loess(u: np.ndarray, y: np.ndarray, at: np.ndarray, span: float
           ) -> tuple[np.ndarray, np.ndarray, float]:  # fmt: skip
    """Loess (degree 1): at each point, a line fitted by weighted least squares to the
    ``span`` share of the points nearest it, weighted by the tricube of their distance.
    The fit is linear in y (``l @ y``), so its standard error is sigma * |l|; sigma from
    the residuals, its degrees of freedom n minus the fit's (the leverages' sum, from the
    leverage of the point nearest each place along the line)."""
    n = len(u)
    q = min(n, max(int(np.ceil(span * n)), 3))
    fit, norm, leverage = np.zeros(len(at)), np.zeros(len(at)), np.zeros(len(at))
    for i, x0 in enumerate(at):
        du = u - x0
        d = np.abs(du)
        reach = np.partition(d, q - 1)[q - 1] * max(span, 1.0)
        reach = max(reach, 1e-12)
        w = np.clip(1 - (d / reach) ** 3, 0, None) ** 3
        s0, s1, s2 = w.sum(), (w * du).sum(), (w * du * du).sum()
        det = s0 * s2 - s1 * s1
        # (the points all at one x: their weighted mean)
        line = det > 1e-12 * max(s0 * s2, 1e-300)
        weights = w * (s2 - s1 * du) / det if line else w / s0
        fit[i] = weights @ y
        norm[i] = np.sqrt((weights * weights).sum())
        leverage[i] = weights[int(np.argmin(d))]
    trace = float(np.clip(leverage.mean() * n, 1.0, n - 1.0)) if n > 2 else float(n)
    df = n - trace
    if df < 1:
        return fit, np.full(len(at), np.nan), df
    resid = y - np.interp(u, at, fit)
    sigma = np.sqrt(float((resid**2).sum()) / df)
    return fit, sigma * norm, df


def _t_quantile(p: float, df: float) -> float:
    """Student's t quantile: exact for 1 and 2 degrees of freedom, else the Cornish-Fisher
    expansion around the normal quantile (within 0.2% from 3 on)."""
    if df <= 1:
        return float(np.tan(np.pi * (p - 0.5)))
    if df <= 2:
        return float((2 * p - 1) / np.sqrt(2 * p * (1 - p)))
    z = _normal_quantile(p)
    g1 = (z**3 + z) / 4
    g2 = (5 * z**5 + 16 * z**3 + 3 * z) / 96
    g3 = (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) / 384
    g4 = (79 * z**9 + 776 * z**7 + 1482 * z**5 - 1920 * z**3 - 945 * z) / 92160
    return float(z + g1 / df + g2 / df**2 + g3 / df**3 + g4 / df**4)


def _normal_quantile(p: float) -> float:
    """The standard normal quantile (Acklam's rational approximation, to about 1e-9)."""
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)  # fmt: skip
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)  # fmt: skip
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)  # fmt: skip
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)  # fmt: skip
    if p < 0.02425 or p > 1 - 0.02425:
        q = np.sqrt(-2 * np.log(min(p, 1 - p)))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
        return float(x if p < 0.5 else -x)
    q = p - 0.5
    r = q * q
    num = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
    return float(num / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1))


def _kde(values: np.ndarray, at: np.ndarray, bw: float) -> np.ndarray:
    """A Gaussian KDE of ``values`` at ``at``: exact, or, for many values, from their
    counts in fine bins (each bin a small fraction of the bandwidth)."""
    norm = 1.0 / (len(values) * bw * np.sqrt(2 * np.pi))
    if len(values) * len(at) <= 500_000:
        z = (at[:, None] - values[None, :]) / bw
        return np.exp(-0.5 * z * z).sum(axis=1) * norm
    nbins = int(min(max(8 * (values[-1] - values[0]) / bw, 64), 8192))
    weights, edges = np.histogram(values, bins=nbins)
    centres = (edges[:-1] + edges[1:]) / 2
    z = (at[:, None] - centres[None, :]) / bw
    return (np.exp(-0.5 * z * z) * weights[None, :]).sum(axis=1) * norm


# ---- helpers ------------------------------------------------------------------------------


def _color(layer: Layer, table: Table) -> Column | None:
    """The category column a summary is split by (a colour), or None."""
    if layer.color is None or layer.color not in table:
        return None
    col = table.column(layer.color)
    if col.kind != "category":
        raise ValueError(
            f"{layer.mark}(color={layer.color!r}): a summary is split by a category column, "
            f"and this one holds {col.kind}s"
        )
    return col


def _codes(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The distinct values, and each value's index among them."""
    uniq, inverse = np.unique(values, return_inverse=True)
    return uniq, inverse.ravel().astype(np.int64)


def _color_codes(color: Column | None, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The colour labels and each row's index among them (one label: no colour)."""
    if color is None or not color.levels:
        return np.array([""], dtype=object), np.zeros(len(rows), dtype=np.int64)
    return np.array(color.levels, dtype=object), color.level_codes()[rows]


def _table(columns: list[Column], extra: dict[str, np.ndarray]) -> Table:
    """A summary table, its columns already read; ``extra``: more columns (or the raw
    values of one, for tooltips)."""
    data: dict[str, np.ndarray] = {c.name: c.values for c in columns}
    data.update(extra)
    out = Table(data)
    out._cache.update({c.name: c for c in columns})
    return out


def _take(col: Column, rows: np.ndarray) -> Column:
    """These rows of a column."""
    codes = col.level_codes()[rows] if col.kind == "category" else None
    return Column(col.name, col.kind, col.values[rows], col.levels, codes, col.log)


def _sorted(g: Geometry) -> Geometry:
    return g.take(np.argsort(g.panel, kind="stable"))


def _times(ms: np.ndarray) -> np.ndarray:
    return np.round(ms).astype(np.int64).astype("datetime64[ms]")


def _shown(col: Column, *values: np.ndarray) -> tuple[np.ndarray, ...]:
    """Values on ``col``'s axis as the data's own (a log axis: 10 to their power)."""
    return tuple(10.0**v if col.log else v for v in values)


def _ranges(lo: np.ndarray, hi: np.ndarray, kind: str, digits: int = 6) -> np.ndarray:
    """``"lo – hi"`` labels."""
    if kind == "time":
        a = np.datetime_as_string(_times(np.r_[lo, hi]), unit="auto")
        return np.array([f"{x} – {y}" for x, y in zip(a[: len(lo)], a[len(lo) :], strict=True)],
                        dtype=object)  # fmt: skip
    return np.array([f"{x:.{digits}g} – {y:.{digits}g}" for x, y in zip(lo, hi, strict=True)],
                    dtype=object)  # fmt: skip


def _value(value: Any, kind: str) -> float:
    if kind == "time" and not isinstance(value, int | float):
        return float(np.datetime64(value, "ms").astype(np.int64))
    return float(value)


def _width(value: Any, kind: str) -> float:
    if isinstance(value, dt.timedelta):
        return value.total_seconds() * 1000.0
    if isinstance(value, np.timedelta64):
        return float(value / np.timedelta64(1, "ms"))
    if kind == "time" and isinstance(value, str):
        return _duration(value)
    return float(value)


def _duration(text: str) -> float:
    """``"7D"``, ``"6h"``, ``"30m"``, ``"10s"`` (or ``W``) in milliseconds."""
    import re

    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([WDhms])\s*", text)
    if not m:
        raise ValueError(f"binwidth {text!r}: give a timedelta or a duration like '7D' or '6h'")
    unit = {"W": 604_800_000, "D": 86_400_000, "h": 3_600_000, "m": 60_000, "s": 1000}
    return float(m.group(1)) * unit[m.group(2)]
