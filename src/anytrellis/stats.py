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


# ---- box plots ----------------------------------------------------------------------------


def box(layer: Layer, table: Table, panel_of: np.ndarray | None, npanels: int) -> list[Part]:
    """A box per (panel, position, colour): the quartiles, a line at the median, whiskers
    to the furthest values within ``whis`` IQRs of the box, and the values beyond as
    points. Vertical, or horizontal when y is the category and x the numbers."""
    assert layer.x is not None
    assert layer.y is not None
    args = layer.stat_args
    xc, yc = table.column(layer.x), table.column(layer.y)
    horizontal = yc.kind == "category" and xc.kind != "category"
    pos, val = (yc, xc) if horizontal else (xc, yc)
    if val.kind != "number":
        raise ValueError(
            f"box(): the values must be numbers; {val.name!r} holds {val.kind}s (one of x and "
            "y gives the positions, the other the numbers)"
        )
    color = _color(layer, table)
    rows, panel = expand(panel_of, table.n, npanels, layer.facet)
    v = val.values[rows]
    keep = np.isfinite(v)
    if pos.kind != "category":
        keep &= np.isfinite(pos.values[rows])
    rows, panel, v = rows[keep], panel[keep], v[keep]
    if pos.kind == "category":  # by code: a million strings don't sort fast
        puniq, pi_ = np.array(pos.levels, dtype=object), pos.level_codes()[rows]
    else:
        puniq, pi_ = _codes(pos.values[rows])
    labels, c = _color_codes(color, rows)
    npos, nc = max(len(puniq), 1), len(labels)
    guniq, ginv = _codes((panel * npos + pi_) * nc + c)
    order = np.lexsort((v, ginv))
    sv, sg, srows = v[order], ginv[order], rows[order]
    counts = np.bincount(sg, minlength=len(guniq))
    # intp: reduceat takes only the platform's index type (int32 in WebAssembly)
    starts = np.r_[0, np.cumsum(counts)].astype(np.intp)
    first = starts[:-1]

    def quantile(f: float) -> np.ndarray:
        h = (counts - 1) * f
        lo = np.floor(h).astype(np.int64)
        hi = np.ceil(h).astype(np.int64)
        return sv[first + lo] + (h - lo) * (sv[first + hi] - sv[first + lo])

    q1, med, q3 = quantile(0.25), quantile(0.5), quantile(0.75)
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
    gp = guniq // (npos * nc)
    gpos = (guniq // nc) % npos
    gc = guniq % nc

    def position_column(index: np.ndarray) -> Column:
        values = puniq[index]
        if pos.kind == "category":
            return Column(pos.name, "category", values.astype(object), pos.levels)
        return Column(pos.name, pos.kind, values.astype(np.float64))

    def raw_position(index: np.ndarray) -> np.ndarray:
        values = puniq[index]
        if pos.log:
            return 10.0 ** values.astype(np.float64)
        return _times(values) if pos.kind == "time" else values

    boxes_cols = [Column(PANEL, "number", gp.astype(np.float64)), position_column(gpos),
                  Column(val.name, "number", med)]  # fmt: skip
    if color is not None:
        boxes_cols.append(Column(color.name, "category", labels[gc], color.levels))
    shown_med, shown_q1, shown_q3, shown_lo, shown_hi = _shown(val, med, q1, q3, wlo, whi)
    stats_text = {
        pos.name: raw_position(gpos),
        "n": counts,
        "median": shown_med,
        "q1": shown_q1,
        "q3": shown_q3,
        "whiskers": _ranges(shown_lo, shown_hi, "number"),
    }
    boxes = _table(boxes_cols, stats_text)
    out_mask = ~inside
    orows, og, ov = srows[out_mask], sg[out_mask], sv[out_mask]
    if not args["outliers"]:
        orows, og, ov = orows[:0], og[:0], ov[:0]
    outlier_cols = [Column(PANEL, "number", gp[og].astype(np.float64)), position_column(gpos[og]),
                    Column(val.name, "number", ov)]  # fmt: skip
    if color is not None:
        outlier_cols.append(Column(color.name, "category", labels[gc[og]], color.levels))
    user_tips = {name: table.raw(name)[orows] for name in layer.tooltip}
    outliers = _table(outlier_cols, {pos.name: raw_position(gpos[og]), **user_tips})
    step = 1.0 if pos.kind == "category" else step_of([puniq.astype(np.float64)])
    span = float(args["width"]) * step
    dodge = color is not None and color.name != pos.name and layer.position == "dodge"

    def centres(tbl: Table, x_levels: Levels, y_levels: Levels,
                color_levels: ColorLevels) -> tuple[np.ndarray, float]:  # fmt: skip
        centre = axis_values(tbl.column(pos.name), y_levels if horizontal else x_levels)
        if not dodge or color is None:
            return centre, span / 2
        k = max(len(color_levels[color.name]), 1)
        code = axis_values(tbl.column(color.name), color_levels[color.name])
        slot = span / k
        return centre - span / 2 + (code + 0.5) * slot, slot * 0.9 / 2

    def oriented(panel_: np.ndarray, a0: np.ndarray, v0: np.ndarray, a1: np.ndarray,
                 v1: np.ndarray, rows_: np.ndarray, line: bool = False) -> Geometry:  # fmt: skip
        g = Geometry(panel_, v0, a0, v1, a1, rows_) if horizontal else Geometry(
            panel_, a0, v0, a1, v1, rows_)  # fmt: skip
        if line:
            g.rows_end = rows_.copy()
        return _sorted(g)

    def build_body(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, h = centres(boxes, xl, yl, cl)
        return oriented(gp, c_ - h, q1, c_ + h, q3, np.arange(len(gp)))

    def build_lines(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, h = centres(boxes, xl, yl, cl)
        left, right = c_ - h, c_ + h
        segments = [  # the outline, the median, the whiskers
            (left, q1, right, q1), (right, q1, right, q3), (right, q3, left, q3),
            (left, q3, left, q1), (left, med, right, med), (c_, q1, c_, wlo), (c_, q3, c_, whi),
        ]  # fmt: skip
        a0, v0, a1, v1 = (np.concatenate([s[i] for s in segments]) for i in range(4))
        n = len(gp)
        return oriented(np.tile(gp, 7), a0, v0, a1, v1, np.tile(np.arange(n), 7), line=True)

    def build_points(xl: Levels, yl: Levels, cl: ColorLevels) -> Geometry:
        c_, _ = centres(outliers, xl, yl, cl)
        return oriented(gp[og], c_, ov, c_.copy(), ov.copy(), np.arange(len(og)))

    tips = [pos.name, "n", "median", "q1", "q3", "whiskers"]
    group_members = Members(starts, srows)
    body = replace(layer, mark="rect", opacity=layer.opacity * FILL, tooltip=tips)
    lines = replace(layer, mark="line", tooltip=tips)
    points = replace(layer, mark="points", tooltip=list(layer.tooltip))
    return [
        Part(body, boxes, build_body, group_members, hide=("x", "y"), family=True),
        Part(lines, boxes, build_lines, group_members, hide=("x", "y"), family=True),
        Part(points, outliers, build_points, Members.each(orows)),
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
