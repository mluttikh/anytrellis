"""Summaries computed where a lazy table's rows are: grouped queries through narwhals' lazy
API (a Polars ``LazyFrame``, a DuckDB relation, an Ibis table), so the database, not
Python, sorts the rows for each group's median. Each answer is a small table, a row per
group, read like any other.

Each returns None for a table in memory, or when the backend can't run the query (an
operation it lacks): the caller then computes the summary from the rows, as for any table.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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
