"""Summary marks of a lazy table computed by its database (``load="pages"``): a histogram's
counts, a box's quartiles and whiskers (and the values beyond them), an error bar's means
and spreads, a line's sums of squares, and the values of a density, a violin or a loess
fit counted in fine bins, whose curves come from the bins. Every panel's at once, in a
query or two, so the axes are those of every panel's summary and the pages turn without
asking again; only the summaries are read, not the rows. They are drawn as ``stats`` draws
those of rows read.

``parts`` returns None for what it doesn't compute: a violin's points, error bars of given
ends, or a query the backend can't run (an Ibis table's times as numbers); the caller then
summarises the rows, read.

``selected`` turns the summaries a brush selects into a query of the rows they stand for.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from anytrellis.data import Column, Table
from anytrellis.facets import Grid
from anytrellis.layers import Layer
from anytrellis.query import _finite, always, among_labels, within
from anytrellis.stats import (
    Fit,
    Keys,
    Labels,
    Part,
    Range,
    Where,
    _codes,
    _color_codes,
    _kde_binned,
    bin_edges,
    box_parts,
    density_grids,
    density_parts,
    errorbar_parts,
    hist_parts,
    linear_fit,
    loess_binned,
    no_members,
    smooth_parts,
    violin_parts,
)

VALUE = "__anytrellis_v"
X = "__anytrellis_x"
Y = "__anytrellis_y"
BIN = "__anytrellis_bin"
N = "__anytrellis_n"
LO = "__anytrellis_lo"
HI = "__anytrellis_hi"
SD = "__anytrellis_sd"
MEAN = "__anytrellis_mean"
Q1 = "__anytrellis_q1"
MED = "__anytrellis_med"
Q3 = "__anytrellis_q3"
INSIDE = "__anytrellis_in"
SXX = "__anytrellis_sxx"
SXY = "__anytrellis_sxy"
SYY = "__anytrellis_syy"
DX = "__anytrellis_dx"
DY = "__anytrellis_dy"
XBAR = "__anytrellis_xbar"
YBAR = "__anytrellis_ybar"
XLO = "__anytrellis_xlo"
XHI = "__anytrellis_xhi"

FINE = 8
"""A density's bins: this many to a bandwidth (from 64 to 8192 over a group's values, as
``stats._kde`` bins many values)."""

LOESS_BINS = 1024
"""A loess fit's bins of x, over each group's range."""


class _Unable(Exception):
    """The backend can't run a query (an operation it lacks)."""


def parts(layer: Layer, whole: Table, grid: Grid, logs: Sequence[str]) -> list[Part] | None:
    """A summary layer's parts, of every panel, from the database (None: not computed
    there; the caller summarises the rows)."""
    ask = _Ask(layer, whole, grid, logs)
    mark, args = layer.mark, layer.stat_args
    try:
        if mark == "hist":
            return ask.hist()
        if mark == "box":
            return ask.box()
        if mark == "violin" and args["inner"] != "points":
            return ask.violin()
        if mark == "density":
            return ask.density()
        if mark == "smooth":
            return ask.smooth()
        if mark == "errorbar" and args.get("lo") is None:
            return ask.errorbar()
    except _Unable:
        return None
    return None


@dataclass
class _Ask:
    """A summary layer's queries of the plot's lazy table."""

    layer: Layer
    whole: Table
    grid: Grid
    logs: Sequence[str]

    # ---- the marks ---------------------------------------------------------------------

    def hist(self) -> list[Part]:
        layer, whole = self.layer, self.whole
        assert layer.x is not None
        x, args = layer.x, layer.stat_args
        color = self._color()
        groups = self._by(color)
        kind = whole.kind(x)
        log = "x" in self.logs
        edges: np.ndarray | None = None
        if kind == "category":
            col = Column(x, "category", np.zeros(0, dtype=object), whole.levels(x))
            by = list(dict.fromkeys([*groups, x]))
            found = self._read(lambda q: q.group_by(*by).agg(_len()))
            nbins = len(col.levels)
            b = found.column(x).level_codes()
        else:
            col = Column(x, kind, self._span(x, log), log=log)
            edges = bin_edges(col, args["bins"], args["binwidth"])
            nbins = len(edges) - 1
            v = self._value(x, log)
            bins = args["bins"]
            if isinstance(bins, Sequence | np.ndarray) and not isinstance(bins, str):
                import narwhals as nw  # given edges: the number of them at or below a value

                bin_of = sum(((v >= float(e)).cast(nw.Int64) for e in edges[1:-1]), v * 0)
            else:  # equal bins: from the first edge, a width at a time
                width = float(edges[1] - edges[0])
                bin_of = ((v - float(edges[0])) / width).floor().clip(0, nbins - 1)
            ok = self._ok(x, log) & (v >= float(edges[0])) & (v <= float(edges[-1]))
            found = self._read(lambda q: q.filter(ok).with_columns(bin_of.alias(BIN))
                               .group_by(*groups, BIN).agg(_len()))  # fmt: skip
            b = np.nan_to_num(found.column(BIN).values, nan=-1).astype(np.int64)
        p = self._panels(found)
        c = self._color_codes(color, found)
        keep = (p >= 0) & (b >= 0) & (b < nbins)
        nc = max(len(color.levels), 1) if color is not None else 1
        key = ((p * nc + c) * nbins + b)[keep]
        uniq, inverse = np.unique(key, return_inverse=True)
        counts = np.bincount(inverse.ravel(), weights=found.column(N).values[keep],
                             minlength=len(uniq)).astype(np.int64)  # fmt: skip
        return hist_parts(layer, col, color, edges, uniq, counts, len(self.grid.panels),
                          no_members(len(uniq)))  # fmt: skip

    def box(self) -> list[Part]:
        import narwhals as nw

        c = nw.col
        args = self.layer.stat_args
        g, groups, ok, v = self._positions()
        whis = float(args["whis"])

        def quartile(f: float) -> Any:
            return c(VALUE).quantile(f, interpolation="linear").over(*groups)

        iqr = c(Q3) - c(Q1)
        inside = (c(VALUE) >= c(Q1) - whis * iqr) & (c(VALUE) <= c(Q3) + whis * iqr)

        def marked(q: Any) -> Any:
            return (q.filter(ok).select(*groups, v.alias(VALUE))
                    .with_columns(quartile(0.25).alias(Q1), quartile(0.75).alias(Q3))
                    .with_columns(inside.alias(INSIDE)))  # fmt: skip

        found = self._read(lambda q: marked(q).group_by(*groups).agg(
            _len(), c(Q1).min().alias(Q1), c(Q3).min().alias(Q3),
            c(VALUE).quantile(0.5, interpolation="linear").alias(MED),
            nw.when(c(INSIDE)).then(c(VALUE)).min().alias(LO),
            nw.when(c(INSIDE)).then(c(VALUE)).max().alias(HI)))  # fmt: skip
        keys, at = self._keys(g, found)
        q1, med, q3, lo, hi = (found.column(k).values[at] for k in (Q1, MED, Q3, LO, HI))
        tips = list(dict.fromkeys(n for n in self.layer.tooltip if n not in groups))
        og, ov = np.zeros(0, dtype=np.int64), np.zeros(0)
        user: dict[str, np.ndarray] = {n: np.zeros(0) for n in self.layer.tooltip}
        if args["outliers"]:
            beyond = self._read(lambda q: q.filter(ok).select(*groups, v.alias(VALUE), *tips)
                                .with_columns(quartile(0.25).alias(Q1),
                                              quartile(0.75).alias(Q3))
                                .filter(~inside).select(*groups, VALUE, *tips))  # fmt: skip
            og = self._group_of(keys, g, beyond)
            values = beyond.column(VALUE).values
            shown = np.flatnonzero(og >= 0)
            shown = shown[np.lexsort((values[shown], og[shown]))]  # by group, then value
            og, ov = og[shown], values[shown]
            user = {n: beyond.raw(n)[shown] for n in self.layer.tooltip}
        return box_parts(keys, q1, med, q3, np.nan_to_num(lo, nan=np.inf),
                         np.nan_to_num(hi, nan=-np.inf), (og, ov, user),
                         no_members(len(keys.guniq)), no_members(len(og)))  # fmt: skip

    def violin(self) -> list[Part]:
        import narwhals as nw

        c = nw.col
        args = self.layer.stat_args
        g, groups, ok, v = self._positions()
        found = self._read(lambda q: q.filter(ok).select(*groups, v.alias(VALUE))
                           .group_by(*groups).agg(
            _len(), c(VALUE).std(ddof=1).alias(SD), c(VALUE).min().alias(LO),
            c(VALUE).max().alias(HI),
            *(c(VALUE).quantile(f, interpolation="linear").alias(name)
              for f, name in ((0.25, Q1), (0.5, MED), (0.75, Q3)))))  # fmt: skip
        keys, at = self._keys(g, found)
        q1, med, q3 = (found.column(k).values[at] for k in (Q1, MED, Q3))
        n, sd, lo, hi = (found.column(k).values[at] for k in (N, SD, LO, HI))
        adjust, cut, gridsize = (float(args["bw_adjust"]), float(args["cut"]),
                                 int(args["gridsize"]))  # fmt: skip
        bws = _bandwidths(n, sd, lo, hi, adjust)
        bins = self._fine_bins(groups, ok, v, adjust)
        of = _Slices(self._group_of(keys, g, bins), len(keys.guniq))
        curves = []
        for k in np.flatnonzero(bws > 0):
            grid = np.linspace(lo[k] - cut * bws[k], hi[k] + cut * bws[k], gridsize)
            mine = of[int(k)]
            centres, weights = bins.column(MEAN).values[mine], bins.column(N).values[mine]
            curves.append((int(k), grid, _kde_binned(centres, weights, grid, bws[k], n[k])))
        return violin_parts(keys, q1, med, q3, curves, no_members(len(keys.guniq)))

    def density(self) -> list[Part]:
        layer, whole = self.layer, self.whole
        assert layer.x is not None
        x, args = layer.x, layer.stat_args
        kind = whole.kind(x)
        if kind == "category":
            raise ValueError(f"density(): x must be numbers or times; {x!r} holds categories")
        log = "x" in self.logs
        color = self._color()
        groups = self._by(color)
        adjust = float(args["bw_adjust"])
        bins = self._fine_bins(groups, self._ok(x, log), self._value(x, log), adjust,
                               totals=True)  # fmt: skip
        p = self._panels(bins)
        cc = self._color_codes(color, bins)
        nc = max(len(color.levels), 1) if color is not None else 1
        gkey = np.where(p >= 0, p * nc + cc, -1)
        guniq, of = _grouped(gkey)
        first = of.first()  # each group's first bin: its totals
        n, sd, lo, hi = (bins.column(k).values[first] for k in (N + "_all", SD, LO, HI))
        bws = _bandwidths(n, sd, lo, hi, adjust)
        curves = []
        at = 0
        for g, xs in density_grids(bws, lo, hi, float(args["cut"]), int(args["gridsize"])):
            mine = of[g]
            centres, weights = bins.column(MEAN).values[mine], bins.column(N).values[mine]
            curves.append((g, xs, _kde_binned(centres, weights, xs, bws[g], n[g])))
            at += len(xs)
        col = Column(x, kind, np.zeros(0), log=log)
        return density_parts(layer, col, color, guniq, curves, no_members(at))

    def smooth(self) -> list[Part]:
        import narwhals as nw

        c = nw.col
        layer, whole = self.layer, self.whole
        assert layer.x is not None
        assert layer.y is not None
        args = layer.stat_args
        for name in (layer.x, layer.y):
            if whole.kind(name) == "category":
                raise ValueError(
                    f"smooth(): x and y must be numbers or times; {name!r} holds categories"
                )
        xlog, ylog = "x" in self.logs, "y" in self.logs
        color = self._color()
        groups = self._by(color)
        ok = self._ok(layer.x, xlog) & self._ok(layer.y, ylog)
        xc = Column(layer.x, whole.kind(layer.x), np.zeros(0), log=xlog)
        yc = Column(layer.y, "number", np.zeros(0), log=ylog)
        if args["method"] == "loess":
            return self._loess(xc, yc, color, groups, ok)
        dx, dy = c(X) - c(X).mean().over(*groups), c(Y) - c(Y).mean().over(*groups)
        xv, yv = self._value(layer.x, xlog), self._value(layer.y, ylog)
        found = self._read(lambda q: q.filter(ok).select(*groups, xv.alias(X), yv.alias(Y))
                           .with_columns(dx.alias(DX), dy.alias(DY)).group_by(*groups).agg(
            _len(), c(X).mean().alias(XBAR), c(Y).mean().alias(YBAR),
            (c(DX) * c(DX)).sum().alias(SXX), (c(DX) * c(DY)).sum().alias(SXY),
            (c(DY) * c(DY)).sum().alias(SYY), c(X).min().alias(XLO),
            c(X).max().alias(XHI)))  # fmt: skip
        p = self._panels(found)
        cc = self._color_codes(color, found)
        nc = max(len(color.levels), 1) if color is not None else 1
        gkey = np.where(p >= 0, p * nc + cc, -1)
        order = np.argsort(gkey, kind="stable")
        order = order[gkey[order] >= 0]
        n, xbar, ybar, sxx, sxy, syy, lo, hi = (
            found.column(k).values[order] for k in (N, XBAR, YBAR, SXX, SXY, SYY, XLO, XHI)
        )
        full = (float(lo.min()), float(hi.max())) if args["fullrange"] and len(lo) else None
        fits = []
        for k in range(len(order)):
            if not hi[k] > lo[k]:  # fewer than two distinct x
                continue
            grid = np.linspace(*(full or (lo[k], hi[k])), int(args["n"]))
            fit, se, df = linear_fit(n[k], xbar[k], ybar[k], sxx[k], sxy[k], syy[k], grid)
            fits.append(Fit(int(gkey[order[k]]), grid, fit, se, df))
        return smooth_parts(layer, xc, yc, color, fits, no_members(len(fits) * int(args["n"])))

    def _loess(self, xc: Column, yc: Column, color: Column | None, groups: list[str],
               ok: Any) -> list[Part]:  # fmt: skip
        """Loess fits from each group's values in fine bins of x (``stats.loess_binned``)."""
        import narwhals as nw

        c = nw.col
        layer = self.layer
        args = layer.stat_args
        xv, yv = self._value(xc.name, xc.log), self._value(yc.name, yc.log)
        bin_of = ((c(X) - c(XLO)) / (c(XHI) - c(XLO)) * LOESS_BINS).floor()
        found = self._read(lambda q: q.filter(ok).select(*groups, xv.alias(X), yv.alias(Y))
                           .with_columns(c(X).min().over(*groups).alias(XLO),
                                         c(X).max().over(*groups).alias(XHI),
                                         c(Y).mean().over(*groups).alias(YBAR))
                           .filter(c(XHI) > c(XLO))
                           .with_columns(bin_of.clip(0, LOESS_BINS - 1).alias(BIN),
                                         (c(Y) - c(YBAR)).alias(DY))
                           .group_by(*groups, BIN).agg(
            _len(), c(X).mean().alias(XBAR), c(DY).sum().alias(SXY),
            (c(DY) * c(DY)).sum().alias(SYY), c(XLO).min().alias(XLO),
            c(XHI).min().alias(XHI), c(YBAR).min().alias(YBAR)))  # fmt: skip
        p = self._panels(found)
        cc = self._color_codes(color, found)
        nc = max(len(color.levels), 1) if color is not None else 1
        gkey = np.where(p >= 0, p * nc + cc, -1)
        guniq, of = _grouped(gkey, found.column(XBAR).values)
        rows = np.flatnonzero(gkey >= 0)
        lo, hi = found.column(XLO).values, found.column(XHI).values
        full = (float(lo[rows].min()), float(hi[rows].max())) \
            if args["fullrange"] and len(rows) else None  # fmt: skip
        fits = []
        for g in range(len(guniq)):
            mine = of[g]  # (by x)
            first = mine[0]
            grid = np.linspace(*(full or (lo[first], hi[first])), int(args["n"]))
            n, xbar, sy, syy = (found.column(k).values[mine] for k in (N, XBAR, SXY, SYY))
            fit, se, df = loess_binned(xbar, n, sy, syy, grid, float(args["span"]))
            fits.append(Fit(int(guniq[g]), grid, fit + found.column(YBAR).values[first], se,
                            df))  # fmt: skip
        return smooth_parts(layer, xc, yc, color, fits, no_members(len(fits) * int(args["n"])))

    def errorbar(self) -> list[Part]:
        import narwhals as nw

        c = nw.col
        g, groups, ok, v = self._positions()
        found = self._read(lambda q: q.filter(ok).select(*groups, v.alias(VALUE))
                           .group_by(*groups).agg(
            _len(), c(VALUE).mean().alias(MEAN), c(VALUE).std(ddof=1).alias(SD),
            c(VALUE).min().alias(LO), c(VALUE).max().alias(HI)))  # fmt: skip
        keys, at = self._keys(g, found)
        mean, sd, lo, hi = (found.column(k).values[at] for k in (MEAN, SD, LO, HI))
        return errorbar_parts(keys, mean, sd, lo, hi, no_members(len(keys.guniq)))

    # ---- groups --------------------------------------------------------------------------

    def _color(self) -> Column | None:
        """The category column the summary is split by (a colour), as ``stats._color``."""
        layer, whole = self.layer, self.whole
        if layer.color is None or layer.color not in whole:
            return None
        if whole.kind(layer.color) != "category":
            raise ValueError(
                f"{layer.mark}(color={layer.color!r}): a summary is split by a category "
                f"column, and this one holds {whole.kind(layer.color)}s"
            )
        return Column(layer.color, "category", np.zeros(0, dtype=object),
                      whole.levels(layer.color))  # fmt: skip

    def _by(self, color: Column | None, *more: str) -> list[str]:
        """The columns a query groups by: the facets', more, and the colour's."""
        extra = [] if color is None else [color.name]
        return list(dict.fromkeys([*self.grid.columns, *more, *extra]))

    def _positions(self) -> tuple[_Shape, list[str], Any, Any]:
        """A box's, a violin's or an error bar's positions and values: their shape, the
        columns grouped by, the rows summarised and their values (axis units)."""
        layer, whole = self.layer, self.whole
        assert layer.x is not None
        assert layer.y is not None
        horizontal = whole.kind(layer.y) == "category" and whole.kind(layer.x) != "category"
        pos, val = (layer.y, layer.x) if horizontal else (layer.x, layer.y)
        pos_log = ("y" if horizontal else "x") in self.logs
        val_log = ("x" if horizontal else "y") in self.logs
        if whole.kind(val) != "number":
            raise ValueError(
                f"{layer.mark}(): the values must be numbers; {val!r} holds "
                f"{whole.kind(val)}s (one of x and y gives the positions, the other the "
                "numbers)"
            )
        color = self._color()
        kind = whole.kind(pos)
        levels = whole.levels(pos) if kind == "category" else ()
        shape = _Shape(horizontal, Column(pos, kind, np.zeros(0), levels, log=pos_log),
                       Column(val, "number", np.zeros(0), log=val_log), color)  # fmt: skip
        ok = self._ok(val, val_log)
        if kind != "category":
            ok = ok & self._ok(pos, pos_log)
        return shape, self._by(color, pos), ok, self._value(val, val_log)

    def _keys(self, shape: _Shape, found: Table) -> tuple[Keys, np.ndarray]:
        """The groups of a query's rows (one each), and the rows in the groups' order."""
        gkey, puniq = self._group_keys(shape, found)
        order = np.argsort(gkey, kind="stable")
        order = order[gkey[order] >= 0]
        labels, _ = _color_codes(shape.color, np.zeros(0, dtype=np.int64))
        counts = found.column(N).values[order].astype(np.int64)
        keys = Keys(self.layer, shape.horizontal, shape.pos, shape.val, shape.color, puniq,
                    labels, gkey[order], counts)  # fmt: skip
        shape.puniq = puniq
        return keys, order

    def _group_of(self, keys: Keys, shape: _Shape, found: Table) -> np.ndarray:
        """The group (an index in ``keys``) of each of a query's rows (−1: none)."""
        gkey, _ = self._group_keys(shape, found)
        at = np.clip(np.searchsorted(keys.guniq, gkey), 0, max(len(keys.guniq) - 1, 0))
        if not len(keys.guniq):
            return np.full(len(gkey), -1)
        return np.where((gkey >= 0) & (keys.guniq[at] == gkey), at, -1)

    def _group_keys(self, shape: _Shape, found: Table) -> tuple[np.ndarray, np.ndarray]:
        """Each row's ``(panel * positions + position) * colours + colour`` (−1: none),
        and the positions."""
        p = self._panels(found)
        pos = shape.pos
        if pos.kind == "category":
            puniq = np.array(pos.levels, dtype=object)
            pi = found.column(pos.name).level_codes()
        else:
            values = found.column(pos.name).values
            if pos.log:
                with np.errstate(divide="ignore", invalid="ignore"):
                    values = np.log10(values)
            if shape.puniq is not None:  # the groups' positions: a row's among them
                puniq = shape.puniq
                pi = np.full(len(values), -1, dtype=np.int64)
                if len(puniq):
                    at = np.clip(np.searchsorted(puniq, values), 0, len(puniq) - 1)
                    pi = np.where(puniq[at] == values, at, -1)
            else:
                puniq, pi = _codes(values)
        cc = self._color_codes(shape.color, found)
        npos = max(len(puniq), 1)
        nc = max(len(shape.color.levels), 1) if shape.color is not None else 1
        gkey = (p * npos + pi) * nc + cc
        return np.where((p >= 0) & (pi >= 0), gkey, -1), puniq

    def _panels(self, found: Table) -> np.ndarray:
        at = self.grid.assign(found)
        assert at is not None  # (the queries group by the facet columns)
        return at

    def _color_codes(self, color: Column | None, found: Table) -> np.ndarray:
        if color is None or not color.levels:
            return np.zeros(found.n, dtype=np.int64)
        return np.maximum(found.column(color.name).level_codes(), 0)

    # ---- queries -------------------------------------------------------------------------

    def _read(self, query: Callable[[Any], Any]) -> Table:
        """A query of the lazy table, read (a table in memory, its categories with the
        whole table's levels)."""
        import narwhals as nw

        try:
            frame = query(self.whole.lazy).collect()
        except Exception as e:  # the backend lacks an operation: from the rows instead
            raise _Unable from e
        out = Table(nw.to_native(frame))
        out.whole = self.whole
        return out

    def _span(self, name: str, log: bool) -> np.ndarray:
        """The finite range of a column (on a log axis: of its values above 0, in log10
        units), or none."""
        from anytrellis.query import span

        whole = self.whole
        found = whole.memo(("span", name, log), lambda: span(whole, name, positive=log))
        if found is None:
            return np.zeros(0)
        return np.log10(np.array(found)) if log else np.array(found)

    def _value(self, name: str, log: bool) -> Any:
        """A number or time column as numbers on its axis: log10 units on a log axis,
        times in milliseconds of wall-clock time."""
        import narwhals as nw

        c = nw.col(name)
        if self.whole.kind(name) == "time":
            dtype = self.whole.dtype(name)
            if isinstance(dtype, nw.Date):
                c = c.cast(nw.Datetime("us"))
            elif getattr(dtype, "time_zone", None) is not None:
                c = c.dt.replace_time_zone(None)
            epoch = dt.datetime(1970, 1, 1)  # noqa: DTZ001 - wall-clock time
            return (c - nw.lit(epoch)).dt.total_milliseconds().cast(nw.Float64)
        if self.whole.kind(name) != "number":
            raise ValueError(f"{self.layer.mark}(): {name!r} holds categories")
        value = c.cast(nw.Float64)
        return value.log(10) if log else value

    def _ok(self, name: str, log: bool) -> Any:
        """Rows with a value drawn: finite, and above 0 on a log axis."""
        import narwhals as nw

        if self.whole.kind(name) == "category":
            return always(name)
        if log and self.whole.kind(name) != "number":
            raise ValueError(f"a log scale needs numbers; {name!r} holds "
                             f"{self.whole.kind(name)}s")  # fmt: skip
        ok = _finite(self.whole, name)
        return ok & (nw.col(name) > 0) if log else ok

    def _fine_bins(self, groups: list[str], ok: Any, v: Any, adjust: float,
                   totals: bool = False) -> Table:  # fmt: skip
        """Each group's values in fine bins, a ``1 / FINE`` of its bandwidth wide: their
        count and mean (``totals``: and each group's count, sd, lowest and highest)."""
        import narwhals as nw

        c = nw.col
        span = c(HI) - c(LO)
        bw = adjust * c(SD) * c(N) ** -0.2
        width = nw.max_horizontal(nw.min_horizontal(bw / FINE, span / 64), span / 8192)
        bin_of = ((c(VALUE) - c(LO)) / width).floor()
        extra = [c(N).min().alias(N + "_all"), c(SD).min().alias(SD), c(LO).min().alias(LO),
                 c(HI).min().alias(HI)] if totals else []  # fmt: skip
        return self._read(lambda q: q.filter(ok).select(*groups, v.alias(VALUE))
                          .with_columns(c(VALUE).min().over(*groups).alias(LO),
                                        c(VALUE).max().over(*groups).alias(HI),
                                        c(VALUE).std(ddof=1).over(*groups).alias(SD),
                                        c(VALUE).count().over(*groups).alias(N))
                          .filter((c(N) >= 2) & (c(HI) > c(LO)) & (c(SD) > 0))
                          .with_columns(bin_of.alias(BIN))
                          .group_by(*groups, BIN)
                          .agg(c(VALUE).count().alias(N), c(VALUE).mean().alias(MEAN),
                               *extra))  # fmt: skip


@dataclass
class _Shape:
    """A box's, a violin's or an error bar's orientation, positions, values and colour."""

    horizontal: bool
    pos: Column
    val: Column
    color: Column | None
    puniq: np.ndarray | None = None
    """The groups' positions, once known."""


class _Slices:
    """Rows by group: ``of[g]``, group ``g``'s (−1: none), in order (or ``within``'s)."""

    def __init__(self, group: np.ndarray, groups: int, within: np.ndarray | None = None) -> None:
        keys = (group,) if within is None else (within, group)
        order = np.lexsort(keys)
        order = order[group[order] >= 0]
        self.order = order
        self.starts = np.searchsorted(group[order], np.arange(groups + 1))

    def __getitem__(self, g: int) -> np.ndarray:
        return self.order[self.starts[g] : self.starts[g + 1]]

    def first(self) -> np.ndarray:
        return self.order[self.starts[:-1]]


def _grouped(key: np.ndarray, within: np.ndarray | None = None) -> tuple[np.ndarray, _Slices]:
    """The distinct keys (−1: none) and their rows."""
    guniq, inverse = np.unique(key[key >= 0], return_inverse=True)
    group = np.full(len(key), -1, dtype=np.int64)
    group[key >= 0] = inverse.ravel()
    return guniq, _Slices(group, len(guniq), within)


def _len() -> Any:
    import narwhals as nw

    return nw.len().alias(N)


def _bandwidths(n: np.ndarray, sd: np.ndarray, lo: np.ndarray, hi: np.ndarray,
                adjust: float) -> np.ndarray:  # fmt: skip
    """Scott's rule times ``adjust`` (0: fewer than two values, or all the same)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        bw = adjust * sd * np.asarray(n, dtype=np.float64) ** -0.2
    ok = (n >= 2) & (hi > lo) & np.isfinite(bw) & (bw > 0)
    return np.where(ok, bw, 0.0)


# ---- selecting -------------------------------------------------------------------------


def selected(whole: Table, wheres: list[Where], panels: Callable[[list[int]], Any]) -> Any:
    """A condition of the rows that summary rows stand for (``wheres``: those selected),
    each panel's (``panels``: the condition of a panel's rows): the ranges of touching
    bins or curve pieces joined, so a brush over many asks a few tests."""
    from anytrellis.query import never

    terms: dict[tuple[Any, ...], list[tuple[float, float, bool]]] = {}
    for w in wheres:
        tests = list(w.tests)
        end = tests[-1] if tests else None
        last = end if isinstance(end, Range) else None  # its ranges joined, where they touch
        if last is not None:
            tests.pop()
        for r in range(len(w.panel)):
            color = None if w.color is None else (w.color.name, w.color.labels[r])
            head = (int(w.panel[r]), w.finite, color, *(_test_key(t, r) for t in tests))
            if last is None:
                terms.setdefault(head, [])
                continue
            head = (*head, ("range", last.name, last.kind, last.log))
            is_open = bool(last.open[r]) if last.open is not None else False
            terms.setdefault(head, []).append((float(last.lo[r]), float(last.hi[r]), is_open))
    by_panel: dict[int, list[Any]] = {}  # a panel's tests (None: all its rows)
    for head, ranges in terms.items():
        panel, finite, color, *keys = head
        cond = None
        for name, log in finite:
            cond = _and(cond, _drawn(whole, name, log))
        if color is not None:
            cond = _and(cond, among_labels(whole, color[0], [color[1]]))
        joined = keys.pop() if keys and keys[-1][0] == "range" else None
        for key in keys:
            cond = _and(cond, _test(whole, key))
        if joined is not None:
            _, name, kind, log = joined
            either = None
            for lo, hi, is_open in _joined(ranges):
                either = _or(either, _range(whole, name, kind, log, lo, hi, is_open))
            cond = _and(cond, either)
        by_panel.setdefault(panel, []).append(cond)
    out = None
    for panel, conds in sorted(by_panel.items()):
        either = None
        if all(cond is not None for cond in conds):
            for cond in conds:
                either = _or(either, cond)
        out = _or(out, _and(panels([panel]), either))
    return never(whole.names[0]) if out is None else out


def _test_key(test: Range | Labels, r: int) -> tuple[Any, ...]:
    if isinstance(test, Labels):
        return ("labels", test.name, test.labels[r])
    is_open = bool(test.open[r]) if test.open is not None else False
    return ("value", test.name, test.kind, test.log, float(test.lo[r]), float(test.hi[r]),
            is_open)  # fmt: skip


def _test(whole: Table, key: tuple[Any, ...]) -> Any:
    if key[0] == "labels":
        return among_labels(whole, key[1], [key[2]])
    _, name, kind, log, lo, hi, is_open = key
    return _range(whole, name, kind, log, lo, hi, is_open)


def _range(whole: Table, name: str, kind: str, log: bool, lo: float, hi: float,
           is_open: bool) -> Any:  # fmt: skip
    """Values from ``lo`` to ``hi`` (axis units); ``lo == hi``: that value (as read: within
    a hair of it)."""
    if lo == hi:
        hair = 1e-3 if kind == "time" else 1e-10 if log else 1e-12 * max(abs(lo), 1e-300)
        lo, hi, is_open = lo - hair, hi + hair, False
    return within(whole, name, lo, hi, "log" if log else kind, open_hi=is_open)


def _drawn(whole: Table, name: str, log: bool) -> Any:
    import narwhals as nw

    ok = _finite(whole, name)
    return ok & (nw.col(name) > 0) if log else ok


def _joined(ranges: list[tuple[float, float, bool]]) -> list[tuple[float, float, bool]]:
    """Ranges that touch or overlap, joined."""
    out: list[tuple[float, float, bool]] = []
    for lo, hi, is_open in sorted(ranges):
        if out and lo <= out[-1][1]:
            a, b, was_open = out[-1]
            if hi > b or (hi == b and not is_open):
                out[-1] = (a, hi, is_open)
            else:
                out[-1] = (a, b, was_open)
            continue
        out.append((lo, hi, is_open))
    return out


def _and(a: Any, b: Any) -> Any:
    return b if a is None else a if b is None else a & b


def _or(a: Any, b: Any) -> Any:
    return b if a is None else a if b is None else a | b
