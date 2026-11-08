"""Summaries computed where a lazy table's rows are: grouped queries through narwhals' lazy
API (a Polars ``LazyFrame``, a DuckDB relation, an Ibis table), so the database, not
Python, sorts the rows for each group's median. Each answer is a small table, a row per
group, read like any other.

Each returns None for a table in memory, or when the backend can't run the query (an
operation it lacks): the caller then computes the summary from the rows, as for any table.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from anytrellis.data import Table

SUMMARIES = ("mean", "median", "min", "max", "sd")
"""The statistics of a panel's values the database computes (``rows`` too, and the trend
comes from the rows: it needs each value's x)."""


def panel_summaries(table: Table, keys: Sequence[str], value: str,
                    x: str | None) -> tuple[Table, Table] | None:  # fmt: skip
    """Per combination of the facet columns ``keys``: its rows (a table of ``keys`` and
    ``rows``), and the mean, median, min, max and sd of its finite values of ``value``,
    leaving out rows without a finite ``x`` when given (``keys`` and ``SUMMARIES``)."""
    lazy = table.lazy
    if lazy is None or not _numeric(table, value):
        return None
    import narwhals as nw

    c = nw.col
    ok = _finite(table, value)
    if x is not None:
        ok = ok & _finite(table, x)
    try:
        rows = lazy.group_by(*keys).agg(nw.len().alias("rows")).collect()
        stats = (
            lazy.filter(ok)
            .group_by(*keys)
            .agg(
                c(value).mean().alias("mean"),
                c(value).median().alias("median"),
                c(value).min().alias("min"),
                c(value).max().alias("max"),
                c(value).std(ddof=1).alias("sd"),
            )
            .collect()
        )
    except Exception:  # the backend lacks an operation: from the rows instead
        return None
    return Table(nw.to_native(rows)), Table(nw.to_native(stats))


def level_summary(table: Table, name: str, by: str, of: str | None) -> Table | None:
    """Per level of column ``name``: ``by`` (median, mean, min, max, sum or count) of
    column ``of``'s values, leaving out those missing (a table of ``name`` and ``v``)."""
    lazy = table.lazy
    if lazy is None:
        return None
    import narwhals as nw

    c = nw.col
    try:
        if by == "count":
            found = lazy.group_by(name).agg(nw.len().alias("v"))
        else:
            assert of is not None
            agg = {"median": c(of).median(), "mean": c(of).mean(), "min": c(of).min(),
                   "max": c(of).max(), "sum": c(of).sum()}[by]  # fmt: skip
            found = lazy.filter(_present(table, of)).group_by(name).agg(agg.alias("v"))
        return Table(nw.to_native(found.collect()))
    except Exception:  # the backend lacks an operation: from the rows instead
        return None


def _numeric(table: Table, name: str) -> bool:
    import narwhals as nw

    dtype = table.dtype(name)
    return bool(dtype.is_numeric()) and dtype != nw.Boolean


def _present(table: Table, name: str) -> Any:
    """Rows with a value of ``name``: not missing, nor NaN (for floats)."""
    import narwhals as nw

    present = ~nw.col(name).is_null()
    if table.dtype(name).is_float():
        present = present & ~nw.col(name).is_nan()
    return present


def _finite(table: Table, name: str) -> Any:
    """Rows with a finite value of ``name``: not missing, NaN or infinite (for floats)."""
    import narwhals as nw

    if table.dtype(name).is_float():
        return nw.col(name).is_finite()
    return ~nw.col(name).is_null()


# ---- reading a page at a time (load="pages") ----------------------------------------------


def distinct(table: Table, names: Sequence[str]) -> Table:
    """The distinct combinations of a lazy table's columns ``names`` (a table in memory)."""
    import narwhals as nw

    return Table(nw.to_native(table.lazy.select(*names).unique().collect()))


def span(table: Table, name: str, positive: bool = False) -> tuple[float, float] | None:
    """The range of a lazy table's finite values of a number or time column (times in
    milliseconds, as read; ``positive``: of those above 0), or None: it has none."""
    import narwhals as nw

    if table.kind(name) == "category":
        return None
    c = nw.col(name)
    ok = _finite(table, name)
    if positive:
        ok = ok & (c > 0)
    found = Table(nw.to_native(table.lazy.filter(ok)
                               .select(c.min().alias("lo"), c.max().alias("hi"))
                               .collect()))  # fmt: skip
    lo, hi = found.column("lo").values, found.column("hi").values
    if not len(lo) or not (np.isfinite(lo[0]) and np.isfinite(hi[0])):
        return None
    return float(lo[0]), float(hi[0])


def panel_extents(table: Table, keys: Sequence[str], x: str, y: str,
                  logs: Sequence[str]) -> Table:  # fmt: skip
    """Per combination of the facet columns ``keys``: the low and high x and y of the rows
    drawn (``x_lo``, ``x_hi``, ``y_lo``, ``y_hi``: those with both; on a log axis, above
    0), of number and time columns (a category axis's are left out)."""
    import narwhals as nw

    drawn = always(x)
    aggs = []
    for axis, name in (("x", x), ("y", y)):
        if table.kind(name) == "category":  # every row has a category (or "(missing)")
            continue
        drawn = drawn & _finite(table, name)
        if axis in logs:
            drawn = drawn & (nw.col(name) > 0)
        aggs += [nw.col(name).min().alias(f"{axis}_lo"), nw.col(name).max().alias(f"{axis}_hi")]
    if not aggs:
        return Table({})
    found = table.lazy.filter(drawn).group_by(*keys).agg(*aggs).collect()
    return Table(nw.to_native(found))


TREND_X = "__anytrellis_x"
TREND_DX = "__anytrellis_dx"
TREND_DY = "__anytrellis_dy"


def panel_trends(table: Table, keys: Sequence[str], value: str, x: str) -> Table | None:
    """Per combination of the facet columns ``keys``: the trend of ``value`` over ``x``
    (as ``pages.trends``: the change of its least-squares line over the span of x, of the
    rows with both finite), or None: the backend can't (a time x in milliseconds)."""
    import narwhals as nw

    c = nw.col
    ok = _finite(table, value) & _finite(table, x)
    shifted = c(x) - c(x).min().over(*keys)  # from each panel's first x: small numbers
    if table.kind(x) == "time":
        shifted = shifted.dt.total_milliseconds()
    try:
        found = (
            table.lazy.filter(ok)
            .select(
                *keys,
                shifted.cast(nw.Float64).alias(TREND_X),
                c(value).cast(nw.Float64).alias(value),
            )
            .with_columns(
                (c(TREND_X) - c(TREND_X).mean().over(*keys)).alias(TREND_DX),
                (c(value) - c(value).mean().over(*keys)).alias(TREND_DY),
            )
            .group_by(*keys)
            .agg(
                (c(TREND_DX) * c(TREND_DY)).sum().alias("sxy"),
                (c(TREND_DX) * c(TREND_DX)).sum().alias("sxx"),
                c(TREND_X).max().alias("span"),
            )
            .collect()
        )
    except Exception:  # the backend lacks an operation: no trend
        return None
    out = Table(nw.to_native(found))
    sxy, sxx, width = (out.column(k).values for k in ("sxy", "sxx", "span"))
    with np.errstate(invalid="ignore", divide="ignore"):
        trend = np.where(width > 0, sxy / sxx * width, np.nan)
    return Table({**{k: np.array(out.values(k), dtype=object) for k in keys}, "trend": trend})


def among(table: Table, name: str, values: Sequence[Any]) -> Any:
    """Rows whose value of ``name`` is one of ``values`` (Python values, as read; None or
    NaN: rows without one)."""
    import narwhals as nw

    c = nw.col(name)
    plain = [v for v in values if not _missing(v)]
    out = c.is_in(plain) if plain else never(name)
    if any(v is None for v in values):
        out = out | c.is_null()
    if table.dtype(name).is_float() and any(isinstance(v, float) and v != v for v in values):
        out = out | c.is_nan()
    return out


def among_labels(table: Table, name: str, labels: Sequence[str]) -> Any:
    """Rows of a category column whose label is one of ``labels`` (``MISSING_LABEL``:
    rows without a value)."""
    import narwhals as nw

    from anytrellis.data import MISSING_LABEL

    c = nw.col(name).cast(nw.String)
    plain = [lv for lv in labels if lv != MISSING_LABEL]
    out = c.is_in(plain) if plain else never(name)
    if MISSING_LABEL in labels:
        out = out | nw.col(name).is_null()
    return out


def combos(table: Table, names: Sequence[str], rows: Sequence[Sequence[Any]]) -> Any:
    """Rows having one of these combinations of values of the columns ``names``."""

    if not rows:
        return never(names[0])
    if len(names) == 1:
        return among(table, names[0], [r[0] for r in rows])
    out = None
    for row in rows:
        term = None
        for name, v in zip(names, row, strict=True):
            one = among(table, name, [v])
            term = one if term is None else term & one
        out = term if out is None else out | term
    return out


def within(table: Table, name: str, lo: float, hi: float, kind: str,
           open_hi: bool = False) -> Any:  # fmt: skip
    """Rows whose value of number or time column ``name`` is in ``[lo, hi]`` (``open_hi``:
    ``[lo, hi)``; an infinite end: no end; a time: milliseconds of wall-clock time in its
    zone; ``kind`` "log": log10 units)."""
    import narwhals as nw

    c = nw.col(name)
    if kind == "time":
        dtype = table.dtype(name)
        if isinstance(dtype, nw.Date):
            c = c.cast(nw.Datetime("us"))
        zone = getattr(dtype, "time_zone", None)
        value: Callable[[float], Any] = lambda ms: _datetime(ms, zone)  # noqa: E731
    elif kind == "log":
        value = lambda v: 10.0**v  # noqa: E731
    else:
        value = float
    out = None if lo == -np.inf else c >= value(lo)
    if hi != np.inf:
        high = c < value(hi) if open_hi else c <= value(hi)
        out = high if out is None else out & high
    return always(name) if out is None else out


def _datetime(ms: float, zone: str | None) -> Any:
    """Milliseconds of wall-clock time as a datetime (in ``zone``); past the years a
    datetime has: its ends."""
    import datetime as dt

    epoch = dt.datetime(1970, 1, 1)  # noqa: DTZ001 - wall-clock time
    micro = dt.timedelta(microseconds=1)
    first = (dt.datetime.min - epoch) // micro  # noqa: DTZ901 - wall-clock time
    last = (dt.datetime.max - epoch) // micro  # noqa: DTZ901 - wall-clock time
    us = min(max(ms * 1000, first), last)
    when = epoch + dt.timedelta(microseconds=round(us))
    if zone is None:
        return when
    from zoneinfo import ZoneInfo

    return when.replace(tzinfo=ZoneInfo(zone))


def linked(table: Table, chosen: Any, names: Sequence[str]) -> Any:
    """The rows of a lazy table sharing their values of the columns ``names`` with the rows
    of ``chosen`` (a query of it): a semi join, rows without a value matching each other."""
    import narwhals as nw

    def keys() -> list[Any]:
        out = []
        for i, name in enumerate(names):
            c = nw.col(name)
            dtype = table.dtype(name)
            if dtype == nw.String:
                value = c.fill_null("")
            elif dtype.is_numeric():
                value = c.fill_null(0)
            else:  # (categories, times, ...: by their text)
                value = c.cast(nw.String).fill_null("")
            out += [value.alias(f"{LINK_KEY}{i}"), c.is_null().alias(f"{LINK_MISSING}{i}")]
        return out

    on = [f"{p}{i}" for i in range(len(names)) for p in (LINK_KEY, LINK_MISSING)]
    picked = chosen.select(*keys()).unique()
    return table.lazy.with_columns(*keys()).join(picked, on=on, how="semi").drop(*on)


LINK_KEY = "__anytrellis_key"
LINK_MISSING = "__anytrellis_missing"


def drawn(table: Table, name: str) -> Any:
    """Rows a point is drawn for, along column ``name``: a finite number or a time (any
    category, or none)."""

    if table.kind(name) == "category":
        return always(name)
    return _finite(table, name)


def always(name: str) -> Any:
    """A condition every row meets (row by row, as a filter needs: not a literal)."""
    import narwhals as nw

    return nw.col(name).is_null() | ~nw.col(name).is_null()


def never(name: str) -> Any:
    """A condition no row meets (row by row, as a filter needs: not a literal)."""
    import narwhals as nw

    return nw.col(name).is_null() & ~nw.col(name).is_null()


def _missing(v: Any) -> bool:
    return v is None or (isinstance(v, float) and v != v)
