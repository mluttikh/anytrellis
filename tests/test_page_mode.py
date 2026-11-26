"""``load="pages"``: a lazy table read a page at a time. The rows of the panels around the
page shown are read; the panels, their statistics, the axes' ranges and the colours come
from the database, so the plot looks as it does with every row read."""

from __future__ import annotations

import json
from typing import Any

import narwhals as nw
import numpy as np
import polars as pl
import pytest
from test_query import LAZY, frame

import anytrellis as at
from anytrellis import Trellis
from anytrellis.data import Table


def rows_of(native: Any) -> int:
    return len(nw.from_native(native).lazy().collect())


def no_full_read(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Every read of a whole lazy table (``Table._load``), to assert there are none."""
    loads: list[list[str]] = []
    original = Table._load

    def counted(self: Table) -> None:
        loads.append(list(self._wanted))
        original(self)

    monkeypatch.setattr(Table, "_load", counted)
    return loads


def plots(kind: str, mark: str = "line", n: int = 30_000, **kw: Any) -> tuple[Trellis, Trellis]:
    """A plot reading pages, and the same plot of the rows in memory."""
    df = frame(n)
    args = {"x": "time", "y": "temp", "color": "rain", **kw}
    paged = getattr(Trellis(LAZY[kind](df), wrap="station", load="pages"), mark)(**args)
    eager = getattr(Trellis(df, wrap="station"), mark)(**args)
    return paged, eager


@pytest.mark.parametrize("kind", list(LAZY))
def test_a_page_reads_its_rows_and_looks_as_with_every_row(kind: str, monkeypatch) -> None:
    loads = no_full_read(monkeypatch)
    paged, eager = plots(kind)
    sp, se = paged._scene()[0], eager._scene()[0]
    assert loads == []  # never every row
    assert paged.panels() == eager.panels()
    for a, b in zip(sp["panels"], se["panels"], strict=True):
        assert np.allclose(a["x"], b["x"])
        assert np.allclose(a["y"], b["y"])
    assert sp["x"] == se["x"]
    assert sp["y"] == se["y"]
    assert sp["legends"] == se["legends"]  # the colours of every row's range
    names = [s.name for s in eager._stats]
    if kind == "ibis":  # no trend over a time x on Ibis
        names.remove("trend temp")
    assert [s.name for s in paged._stats] == names
    for s in paged._stats:
        other = next(e for e in eager._stats if e.name == s.name)
        assert np.allclose(np.array(s.values, float), np.array(other.values, float),
                           rtol=1e-9, equal_nan=True), s.name  # fmt: skip
    read = paged._table(paged._layers[0])
    assert read.n < len(frame(30_000)) / 2  # three pages of seven
    assert paged._window is not None
    panel_of = paged._grid.assign(read)
    assert panel_of is not None
    assert set(np.unique(panel_of).tolist()) == set(paged._window)


@pytest.mark.parametrize("kind", ["duckdb", "polars"])
def test_turning_the_page_reads_its_rows_and_sends_every_layer(kind: str) -> None:
    paged, eager = plots(kind)
    spec, _ = paged._scene()
    ids = [lr["coords"]["id"] for lr in spec["layers"]]
    paged._paging = {"page": 4}  # as the browser turns it
    message = paged._detail(None)
    assert message is not None
    assert [d["index"] for d in message["layers"]] == list(range(len(spec["layers"])))
    assert [d["of"] for d in message["layers"]] == ids  # the layers the browser has
    assert paged._scene()[0] is spec  # the spec stays: only its layers change
    assert paged._window is not None
    assert 4 * 24 in paged._window
    assert 0 not in paged._window
    for d in message["layers"]:
        assert d["layer"]["panels"] == sorted(paged._window)
        for buffer_id in [v for k, v in d["layer"].items() if k in ("x0", "y0")]:
            assert buffer_id in paged._detail_buffers.data  # the widget sends them
    # the panels around page 5 drawn as with every row read
    eager._paging = {"page": 4}
    eager._detail(None)
    got, want = paged._sent[0][2], eager._sent[0][2]
    assert got is not None
    assert want is not None
    assert got.count == want.count
    assert paged._detail(None) is None  # the same page: nothing to send


@pytest.mark.parametrize("kind", ["duckdb", "polars"])
def test_turning_a_page_reads_only_the_panels_not_read(kind: str, monkeypatch) -> None:
    paged, _ = plots(kind)
    queried: list[frozenset[int] | None] = []
    original = Trellis._query_rows

    def spy(self: Trellis, grid: Any, panels: Any, names: Any) -> Table:
        queried.append(panels)
        return original(self, grid, panels, names)

    monkeypatch.setattr(Trellis, "_query_rows", spy)
    paged._scene()
    assert queried == [frozenset(range(48))]  # the first two pages
    for page, new in ((1, range(48, 72)), (2, range(72, 96)), (1, range(24))):
        queried.clear()
        paged._paging = {"page": page}
        paged._detail(None)
        assert queried == [frozenset(new)], page  # the page that came into the window
        rows = paged._table(paged._layers[0])
        fresh = Trellis._query_rows(paged, paged._grid, paged._window, tuple(rows.names))
        assert rows.n == fresh.n  # the same rows as read at once
        for name in ("temp", "rain", "time"):  # (NaNs sorted last)
            a, b = np.sort(rows.column(name).values), np.sort(fresh.column(name).values)
            assert np.array_equal(a, b, equal_nan=True), (page, name)
    queried.clear()
    paged._detail(None)  # the same window: nothing read
    assert queried == []


@pytest.mark.parametrize("kind", list(LAZY))
def test_points_keep_their_cells_layer_from_page_to_page(kind: str) -> None:
    paged, eager = plots(kind, "points", x="t")
    layers = paged._scene()[0]["layers"]
    assert len(layers) == 2  # the points, and their (here empty) cells
    assert len(eager._scene()[0]["layers"]) == 1
    paged._paging = {"page": 5}
    message = paged._detail(None)
    assert message is not None
    assert len(message["layers"]) == 2


@pytest.mark.parametrize("kind", list(LAZY))
def test_selected_rows_are_a_query_of_every_panel(kind: str) -> None:
    paged, eager = plots(kind, "points", x="t")
    for p in (paged, eager):
        p.select(x=(10, 40), y=(5, 12))
    query = paged.selected()
    assert not isinstance(query, pl.DataFrame)  # not read yet
    assert rows_of(query) == len(eager.selected())
    names = paged.panels()
    for p in (paged, eager):
        p.select(x=(10, 40), panel=names[100])  # a panel far from the page shown
    assert rows_of(paged.selected()) == len(eager.selected()) > 0
    for p in (paged, eager):
        p.select()
    assert rows_of(paged.selected()) == 0


@pytest.mark.parametrize("kind", list(LAZY))
def test_selected_by_a_range_of_a_number_colour(kind: str) -> None:
    paged, eager = plots(kind, "points", x="t")
    for p in (paged, eager):
        p.select(color=(1.0, 3.0))  # rain: as a drag on the gradient
    assert rows_of(paged.selected()) == len(eager.selected()) > 0
    assert paged.selection == eager.selection


def test_selected_by_a_time_range_and_a_category_axis() -> None:
    paged, eager = plots("duckdb", "points", x="time")
    for p in (paged, eager):
        p.select(x=("2024-01-01 05:00", "2024-01-03 09:00"))
    assert rows_of(paged.selected()) == len(eager.selected()) > 0
    df = frame(3000).with_columns(pl.col("station").alias("site"))
    import duckdb

    paged = Trellis(duckdb.from_arrow(df.to_arrow()), wrap="station", load="pages")
    paged.points(x="site", y="temp")
    eager = Trellis(df, wrap="station").points(x="site", y="temp")
    for p in (paged, eager):
        p.select(x=["site 3", "site 30"])
    assert rows_of(paged.selected()) == len(eager.selected()) > 0
    assert paged._scene()[0]["x"]["levels"] == eager._scene()[0]["x"]["levels"]


@pytest.mark.parametrize("kind", list(LAZY))
def test_sliced_ranges_are_those_of_every_row(kind: str) -> None:
    df = frame(30_000)
    paged = Trellis(LAZY[kind](df), wrap="station", load="pages", share_y="sliced")
    eager = Trellis(df, wrap="station", share_y="sliced")
    spec_p, _ = paged.line(x="time", y="temp")._scene()
    spec_e, _ = eager.line(x="time", y="temp")._scene()
    widths = {round(p["y"][1] - p["y"][0], 9) for p in spec_p["panels"]}
    assert len(widths) == 1  # also the panels of pages not read

    def ranges(spec: dict[str, Any]) -> list[float]:
        return [y + spec["y"]["origin"] for p in spec["panels"] for y in p["y"]]

    assert ranges(spec_p) == pytest.approx(ranges(spec_e))


def test_order_by_a_summary_from_the_database() -> None:
    paged, eager = plots("duckdb")
    for p in (paged, eager):
        p.order("station", by="median", of="rain", descending=True)
    assert paged.panels() == eager.panels()


def same_scene(a: tuple[dict[str, Any], Any], b: tuple[dict[str, Any], Any]) -> None:
    """Two scenes draw the same: their layers and buffers alike, their panels' statistics
    as close as a database's sums and Python's are."""
    (sa, ba), (sb, bb) = a, b
    drawn = [lr for lr in sa["layers"] if lr.get("count") != 0]  # (no cells: an empty layer)
    other = [lr for lr in sb["layers"] if lr.get("count") != 0]
    assert json.dumps(drawn, sort_keys=True) == json.dumps(other, sort_keys=True)
    assert {k: v for k, v in ba.data.items() if v} == {k: v for k, v in bb.data.items() if v}
    rest = {k: v for k, v in sa.items() if k not in ("layers", "pages")}
    assert json.dumps(rest, sort_keys=True) == \
        json.dumps({k: v for k, v in sb.items() if k in rest}, sort_keys=True)  # fmt: skip
    if sa["pages"] is None:
        assert sb["pages"] is None
        return
    for s, t in zip(sa["pages"]["stats"], sb["pages"]["stats"], strict=True):
        assert {k: v for k, v in s.items() if k != "values"} == \
            {k: v for k, v in t.items() if k != "values"}  # fmt: skip
        if s["kind"] == "number":
            assert np.allclose(np.array(s["values"], float), np.array(t["values"], float),
                               rtol=1e-9, equal_nan=True), s["name"]  # fmt: skip
        else:
            assert s["values"] == t["values"]


def test_a_saved_page_has_every_row(monkeypatch) -> None:
    paged, _ = plots("duckdb")
    paged.show_page(2)
    assert paged._data is not None
    every = Trellis(paged._data.native, wrap="station").line(x="time", y="temp",
                                                             color="rain").show_page(2)  # fmt: skip
    loads = no_full_read(monkeypatch)
    a = paged._full_scene()
    assert loads == []  # never every row at once: a chunk of panels at a time
    same_scene(a, every._full_scene())
    assert paged._window is not None  # the plot itself still reads pages
    assert paged._full_scene() is a  # read once


def test_a_wrap_that_does_not_page_reads_every_row(monkeypatch) -> None:
    loads = no_full_read(monkeypatch)
    df = frame(3000, stations=12)
    import duckdb

    paged = Trellis(duckdb.from_arrow(df.to_arrow()), wrap="station", load="pages")
    paged.line(x="t", y="temp")
    spec, _ = paged._scene()
    assert spec["pages"] is None
    assert loads == []  # in one query of the rows, all of them
    assert paged._table(paged._layers[0]).n == len(df)


def test_what_page_mode_does_not_do() -> None:
    df = frame(600)
    import duckdb

    rel = duckdb.from_arrow(df.to_arrow())
    with pytest.raises(ValueError, match="load must be"):
        Trellis(rel, wrap="station", load="some")
    with pytest.raises(ValueError, match="give wrap="):
        Trellis(rel, row="station", load="pages")
    with pytest.raises(ValueError, match="rows='all'"):
        Trellis(rel, wrap="station", rows="all", load="pages")
    with pytest.raises(ValueError, match="lazy table"):
        Trellis(df, wrap="station", load="pages").line(x="t", y="temp")._scene()
    with pytest.raises(ValueError, match="area"):
        Trellis(rel, wrap="station", load="pages").area(x="t", y="temp")._scene()
    with pytest.raises(ValueError, match="facet="):
        Trellis(rel, wrap="station", load="pages").hist(x="temp", facet="exclude")._scene()
    with pytest.raises(ValueError, match="facet="):
        Trellis(rel, wrap="station", load="pages").line(x="t", y="temp",
                                                       facet="exclude")._scene()  # fmt: skip
    a = Trellis(rel, wrap="station", load="pages").line(x="t", y="temp")
    b = Trellis(df, wrap="station").line(x="t", y="temp")
    with pytest.raises(ValueError, match="give on="):
        at.link(a, b)


def test_a_layer_with_its_own_data_is_read_whole() -> None:
    df = frame(30_000)
    import duckdb

    stations = df.group_by("station").agg(pl.col("temp").mean().alias("mean"))
    paged = Trellis(duckdb.from_arrow(df.to_arrow()), wrap="station", load="pages")
    paged.line(x="t", y="temp").points(x="t", y="mean", data=stations.with_columns(t=0.0))
    spec, _ = paged._scene()
    assert len(spec["layers"]) == 2  # the line and the points (no cells: not a page's)
    assert paged._table(paged._layers[1]).n == len(stations)


SAVED: dict[str, tuple[dict[str, Any], Any]] = {  # Trellis(...)'s options, and its layers
    "colours": ({}, lambda t: t.line(x="t", y="temp", color="rain")),
    "end labels": ({}, lambda t: t.line(x="t", y="temp", group="note", label="end")),
    "log y": ({"y_scale": "log"}, lambda t: t.points(x="t", y="rain", color="temp")),
    "text": ({}, lambda t: t.text(x="t", y="temp", text="note")),
    "link": ({"link": "note"}, lambda t: t.points(x="t", y="temp")),
    "hist": ({}, lambda t: t.line(x="t", y="temp").hist(x="rain")),
    "thinned": ({}, lambda t: t.line(x="t", y="temp")),
    "cells": ({}, lambda t: t.points(x="t", y="temp", color="rain")),
}


@pytest.mark.parametrize("case", list(SAVED))
def test_a_saved_page_reads_a_chunk_of_panels_at_a_time(case: str, monkeypatch) -> None:
    import duckdb

    import anytrellis.detail as detail
    import anytrellis.plot as plot

    monkeypatch.setattr(plot, "CHUNK_ROWS", 400)  # chunks of 4 panels
    for module in (detail, plot):  # lines thinned, points as cells: in so few rows
        monkeypatch.setattr(module, "THIN", 50)
        monkeypatch.setattr(module, "DENSE", 50)
    df = frame(12_000, stations=120)
    options, layers = SAVED[case]
    paged = layers(Trellis(duckdb.from_arrow(df.to_arrow()), wrap="station", load="pages",
                           **options))  # fmt: skip
    paged.show_page(3)
    paged._scene()
    reads: list[int] = []
    query = Trellis._query_rows

    def counted(self: Trellis, *args: Any) -> Table:
        rows = query(self, *args)
        reads.append(rows.n)
        return rows

    monkeypatch.setattr(Trellis, "_query_rows", counted)
    saved = paged._full_scene()
    assert len(reads) == -(-len(saved[0]["panels"]) // 4)  # (121: one of no station)
    assert max(reads) <= 4 * 12_000 // 120  # a chunk's panels' rows
    assert sum(reads) == len(df)  # every row, once
    same_scene(saved, paged._every_row()._full_scene())
    spec = saved[0]
    if case == "thinned":  # (the rows with a temperature: some 98 a panel, 4 columns' kept)
        assert spec["layers"][0]["count"] < len(df) * 0.9
    if case == "cells":
        assert spec["layers"][1]["type"] == "rect"
        assert spec["layers"][1]["count"] > 0
