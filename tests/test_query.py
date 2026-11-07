"""Lazy tables (a Polars ``LazyFrame``, a DuckDB relation, an Ibis table): only the columns
drawn are read, in one query, and the panels' summaries come from the database."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

import duckdb
import ibis
import narwhals as nw
import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis, pairs
from anytrellis.data import MISSING_LABEL, Table, _categories, _read
from anytrellis.query import level_summary, panel_summaries


def frame(n: int = 3_000, stations: int = 150) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    i = np.arange(n)
    temp = rng.normal(10, 3, n)
    temp[::17] = np.nan
    temp[::29] = np.inf
    station = np.array([f"site {k}" for k in i % stations], dtype=object)
    station[::41] = None
    start = dt.datetime(2024, 1, 1)  # noqa: DTZ001 - wall-clock times, as sensors log them
    return pl.DataFrame({
        "station": station.tolist(),
        "t": (i // stations).astype(np.float64),
        "time": [start + dt.timedelta(hours=int(h)) for h in i // stations],
        "temp": temp,
        "rain": rng.uniform(0, 5, n),
        "note": ["x" * 20] * n,
    }).with_columns(pl.when(pl.col("temp").is_nan() & (pl.int_range(n) % 2 == 0))
                    .then(None).otherwise(pl.col("temp")).alias("temp"))  # fmt: skip


LAZY: dict[str, Callable[[pl.DataFrame], Any]] = {
    "polars": lambda df: df.lazy(),
    "duckdb": lambda df: duckdb.from_arrow(df.to_arrow()),
    "ibis": ibis.memtable,
}


def stats(p: Trellis) -> dict[str, list[float]]:
    p._scene()
    return {s.name: s.values for s in p._stats}


def assert_same_stats(a: Trellis, b: Trellis) -> None:
    sa, sb = stats(a), stats(b)
    assert list(sa) == list(sb)
    for name in sa:
        x, y = np.array(sa[name], dtype=float), np.array(sb[name], dtype=float)
        assert np.allclose(x, y, rtol=1e-9, atol=1e-9, equal_nan=True), name


@pytest.mark.parametrize("kind", list(LAZY))
def test_a_lazy_table_reads_only_the_columns_drawn_in_one_query(kind: str, monkeypatch) -> None:
    loads = []
    original = Table._load

    def counted(self: Table) -> None:
        loads.append(list(self._wanted))
        original(self)

    monkeypatch.setattr(Table, "_load", counted)
    p = Trellis(LAZY[kind](frame()), wrap="station").line(x="t", y="temp", color="rain")
    p._scene()
    assert p._data is not None
    assert p._data._read_names == {"station", "t", "temp", "rain"}
    assert len(loads) == 1


@pytest.mark.parametrize("kind", list(LAZY))
def test_lazy_tables_draw_as_tables_in_memory(kind: str) -> None:
    df = frame()
    lazy = Trellis(LAZY[kind](df), wrap="station").line(x="t", y="temp")
    eager = Trellis(df, wrap="station").line(x="t", y="temp")
    assert lazy.panels() == eager.panels()
    assert MISSING_LABEL in lazy.panels()
    assert_same_stats(lazy, eager)
    spec, _ = lazy._scene()
    assert spec["pages"] is not None  # 151 panels: paged, with statistics
    counts = [lr["count"] for lr in eager._scene()[0]["layers"]]
    assert [lr["count"] for lr in spec["layers"]] == counts


@pytest.mark.parametrize("kind", list(LAZY))
def test_page_statistics_come_from_the_database(kind: str) -> None:
    table = Table(LAZY[kind](frame()))
    found = panel_summaries(table, ["station"], "temp", "t")
    assert found is not None
    counts, summaries = found
    assert counts.n == 151  # 150 stations and the missing one
    assert summaries.names == ["station", "mean", "median", "min", "max", "sd"]
    assert panel_summaries(Table(frame()), ["station"], "temp", "t") is None  # in memory


@pytest.mark.parametrize("kind", list(LAZY))
def test_a_time_x_trends_as_in_memory(kind: str) -> None:
    df = frame()
    lazy = Trellis(LAZY[kind](df), wrap="station").line(x="time", y="temp")
    eager = Trellis(df, wrap="station").line(x="time", y="temp")
    assert_same_stats(lazy, eager)
    assert "trend temp" in stats(lazy)


@pytest.mark.parametrize("kind", list(LAZY))
def test_order_by_a_summary_from_the_database(kind: str) -> None:
    df = frame(stations=12)
    lazy = Trellis(LAZY[kind](df), wrap="station").points(x="t", y="temp")
    eager = Trellis(df, wrap="station").points(x="t", y="temp")
    for by in ("median", "mean", "max", "count", "sum"):
        for p in (lazy, eager):
            p.order("station", by=by, of=None if by == "count" else "rain", descending=True)
        assert lazy.panels() == eager.panels(), by
    found = level_summary(Table(LAZY[kind](df)), "station", "median", "rain")
    assert found is not None
    assert found.n == 13


def test_a_backend_lacking_an_operation_computes_from_the_rows(monkeypatch) -> None:
    def lacking(*args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("no grouping here")

    monkeypatch.setattr(nw.LazyFrame, "group_by", lacking)
    df = frame()
    lazy = Trellis(df.lazy(), wrap="station").line(x="t", y="temp")
    assert panel_summaries(Table(df.lazy()), ["station"], "temp", "t") is None
    assert_same_stats(lazy, Trellis(df, wrap="station").line(x="t", y="temp"))
    lazy.order("station", by="median", of="rain")
    assert lazy.panels()[0] == Trellis(df, wrap="station").order(
        "station", by="median", of="rain").panels()[0]  # fmt: skip


def test_a_column_needed_later_reads_them_all_again() -> None:
    df = frame()
    p = Trellis(duckdb.from_arrow(df.to_arrow()), wrap="station").points(x="t", y="temp")
    p.select(x=(3, 5))
    rows = p.selected()  # every column of the selected rows
    want = df.filter((pl.col("t") >= 3) & (pl.col("t") <= 5) & pl.col("temp").is_finite())
    assert sorted(nw.from_native(rows).columns) == sorted(df.columns)
    assert len(rows) == len(want)
    assert p._data is not None
    note = p._data.column("note")  # not drawn: read now, with the others, from the same rows
    assert len(note) == len(df)
    assert {"note", "station", "t", "temp"} <= p._data._read_names
    assert np.array_equal(p._data.column("t").values, df["t"].to_numpy())


def test_a_lazy_table_counts_its_rows_without_reading_them() -> None:
    table = Table(duckdb.from_arrow(frame(500).to_arrow()))
    assert table.n == 500
    assert table._frame is None
    assert table.kind("time") == "time"
    assert table.kind("station") == "category"
    assert table._frame is None


def test_text_columns_encoded_by_arrow_as_in_python() -> None:
    values = ["site 10", "site 2", None, MISSING_LABEL, "", "é", "site 2", None, "Site 1"]
    s = nw.from_native(pl.DataFrame({"s": values}))
    fast = _read(s, "s")
    slow = _categories("s", np.array(values, dtype=object), None)
    assert fast.levels == slow.levels
    assert list(fast.values) == list(slow.values)
    assert np.array_equal(fast.level_codes(), slow.level_codes())
    assert fast.levels[-1] == MISSING_LABEL


def test_pairs_of_a_lazy_table() -> None:
    df = frame(600, stations=6).with_columns(pl.col("temp").fill_nan(0.0))
    lazy = pairs(duckdb.from_arrow(df.to_arrow()), ["t", "temp", "rain"])
    eager = pairs(df, ["t", "temp", "rain"])
    assert lazy.panels() == eager.panels()
    assert lazy._scene()[0]["layers"][0]["count"] == eager._scene()[0]["layers"][0]["count"]
    default = pairs(duckdb.from_arrow(df.select("t", "temp", "station").to_arrow()))
    assert default._columns == ["t", "temp"]
