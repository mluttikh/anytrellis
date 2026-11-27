"""Linked plots in a saved page (``Link.save_html``): the keys written for each plot's marks
highlight, in the browser's arithmetic (``savedlink.ts``, emulated here), what Python's link
would send each plot, in memory and from a database (``load="pages"``)."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import duckdb
import numpy as np
import polars as pl
import pytest

import anytrellis as at
from anytrellis.datasets import load
from anytrellis.linking import highlight_message, saved_links


def u32(b64: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype="<u4").astype(np.int64)


def chosen_keys(layers: list[Any], masks: list[np.ndarray | None], size: int) -> np.ndarray:
    """``chosenKeys``: the keys of the rows of the marks selected."""
    chosen = np.zeros(size, dtype=bool)
    for layer, mask in zip(layers, masks, strict=True):
        if layer is None or mask is None:
            continue
        if "keys" in layer:
            chosen[u32(layer["keys"])[mask]] = True
            if layer["ends"]:
                chosen[u32(layer["ends"])[mask]] = True
        else:
            starts, members = u32(layer["starts"]), u32(layer["members"])
            for i in np.flatnonzero(mask):
                chosen[members[starts[i] : starts[i + 1]]] = True
    return chosen


def link_highlight(layers: list[Any], chosen: np.ndarray) -> list[Any]:
    """``linkHighlight``: per layer, a mask of marks, a bar's share, or None."""
    out: list[Any] = []
    for layer in layers:
        if layer is None:
            out.append(None)
        elif "keys" in layer:
            hit = chosen[u32(layer["keys"])]
            if layer["ends"]:
                hit = hit | chosen[u32(layer["ends"])]
            out.append(("mask", hit))
        else:
            starts, members = u32(layer["starts"]), u32(layer["members"])
            inside = np.r_[0, np.cumsum(chosen[members])]
            count, size = inside[starts[1:]] - inside[starts[:-1]], np.diff(starts)
            share = np.divide(count, size, out=np.zeros(len(size)), where=size > 0)
            out.append(("fraction", share.astype(np.float32)) if layer["share"]
                       else ("mask", count > 0))  # fmt: skip
    return out


def sent(plot: at.Trellis) -> list[Any]:
    """What Python's link sends ``plot`` (``highlight_message``), read as the browser does."""
    message, buffers = highlight_message(plot._highlight_entries(), plot._highlight)
    out: list[Any] = []
    for entry in message["layers"] or []:
        if entry is None:
            out.append(None)
        elif "mask" in entry:
            bits = np.unpackbits(np.frombuffer(buffers[entry["mask"]], dtype=np.uint8),
                                 bitorder="little")  # fmt: skip
            out.append(("mask", bits[: entry["count"]].astype(bool)))
        else:
            out.append(("fraction", np.frombuffer(buffers[entry["fraction"]], dtype=np.float32)))
    return out


def marks_selected(plot: at.Trellis) -> list[np.ndarray | None]:
    """The source's marks its brush selects, per spec layer (its points: their rows')."""
    (_, rows), *_ = plot._selected_masks()
    return [None if e.geom is None else rows[e.geom.rows] for e in plot._saved_entries()]


def brushed(plot: at.Trellis, on: tuple[str, ...], panel: str, x: str, xr: tuple[float, float],
            y: str, yr: tuple[float, float]) -> list[np.ndarray | None]:  # fmt: skip
    """The marks of the saved page a brush in ``panel`` selects (``xr``, ``yr`` of the
    columns ``x``, ``y``), per spec layer, from the rows they are of."""
    index = [p.label for p in plot._grid.panels].index(panel)
    out: list[np.ndarray | None] = []
    for e in plot._saved_entries(on):
        if e.geom is None or e.table is None or e.part is not None:
            out.append(None)
            continue
        xs = np.asarray(e.table.values(x), dtype=float)[e.geom.rows]
        ys = np.asarray(e.table.values(y), dtype=float)[e.geom.rows]
        out.append((e.geom.panel == index) & (xs >= xr[0]) & (xs <= xr[1])
                   & (ys >= yr[0]) & (ys <= yr[1]))  # fmt: skip
    return out


def layer_sizes(page: str) -> list[list[tuple[int, int]]]:
    """Per plot of a saved page, per linked layer: its marks, and the marks its keys are
    for (a plain mark's keys, a summary's starts)."""
    out = []
    for m in re.findall(r"<script type='application/json'>(.*?)</script>", page):
        payload = json.loads(m.replace("<\\/", "</"))
        sizes = []
        for layer, keys in zip(payload["spec"]["layers"], payload["link"]["layers"], strict=True):
            if keys is not None:
                n = len(u32(keys["keys"])) if "keys" in keys else len(u32(keys["starts"])) - 1
                sizes.append((layer["count"], n))
        out.append(sizes)
    return out


def same(a: list[Any], b: list[Any]) -> None:
    assert len(a) == len(b)
    for x, y in zip(a, b, strict=True):
        assert (x is None) == (y is None)
        if x is not None:
            assert x[0] == y[0]
            np.testing.assert_allclose(x[1].astype(float), y[1].astype(float), atol=1e-6)


@pytest.fixture
def cars() -> pl.DataFrame:
    return load("cars")


def test_the_same_table_highlights_as_python_does(cars: pl.DataFrame) -> None:
    scatter = at.Trellis(cars).points(x="weight", y="mpg")
    counts = at.Trellis(cars, wrap="origin").hist(x="horsepower")
    lines = at.Trellis(cars).line(x="year", y="mpg", color="name")
    link = at.link(scatter, counts, lines)
    scatter.select(x=(2000, 3000), y=(20, 40))
    payloads = saved_links(link)
    assert len({p["group"] for p in payloads}) == 1
    chosen = chosen_keys(payloads[0]["layers"], marks_selected(scatter), payloads[0]["size"])
    assert chosen.sum() == len(scatter.selected())
    for plot, payload in zip((counts, lines), payloads[1:], strict=True):
        same(link_highlight(payload["layers"], chosen), sent(plot))
    hist = link_highlight(payloads[1]["layers"], chosen)
    assert hist[0][0] == "fraction"
    assert 0 < hist[0][1].max() <= 1


def test_on_keys_link_any_tables(cars: pl.DataFrame) -> None:
    by_origin = cars.group_by("origin").agg(pl.col("mpg").mean())
    scatter = at.Trellis(cars).points(x="weight", y="mpg")
    bars = at.Trellis(by_origin).bars(x="origin", y="mpg")
    link = at.link(scatter, bars, on="origin")
    scatter.select(x=(4000, 6000))  # heavy cars: all American
    payloads = saved_links(link)
    chosen = chosen_keys(payloads[0]["layers"], marks_selected(scatter), payloads[0]["size"])
    got = link_highlight(payloads[1]["layers"], chosen)
    same(got, sent(bars))
    assert got[0][1].sum() == 1


def test_a_database_link_saves_what_memory_does() -> None:
    df = load("gapminder")
    rel = duckdb.from_arrow(df.to_arrow())
    out = []
    for data, load_ in ((df, "all"), (rel, "pages")):
        a = at.Trellis(data, wrap="year", rows=1, cols=3, load=load_)
        a.points(x="fertility", y="life_expect")
        b = at.Trellis(data, wrap="region", rows=1, cols=2, load=load_).points(x="year", y="pop")
        b.hist(x="life_expect")  # a summary: from the database with load="pages"
        link = at.link(a, b, on="country")
        a._scene()
        a.select(x=(6, 9), y=(20, 40), panel="1955")
        payloads = saved_links(link)
        source = brushed(a, ("country",), "1955", "fertility", (6, 9), "life_expect", (20, 40))
        chosen = chosen_keys(payloads[0]["layers"], source, payloads[0]["size"])
        assert chosen.any()
        # the layers that draw something (load="pages" adds dense points' cells: none here)
        out.append([h for h in link_highlight(payloads[1]["layers"], chosen)
                    if h is not None and len(h[1])])  # fmt: skip
        # the keys are for the marks the page draws: as many, every panel's (paged plots)
        sizes = layer_sizes(link.to_html())
        assert all(drawn == keyed for plot in sizes for drawn, keyed in plot), sizes
        assert sizes[0][0][0] == df.height  # every panel's points, not the page's
    same(out[1], out[0])
    assert 0 < out[0][0][1].sum() < len(out[0][0][1])
    assert out[0][1][0] == "fraction"
    assert 0 < out[0][1][1].max() <= 1


def test_the_page_holds_every_plot_and_the_selection(cars: pl.DataFrame) -> None:
    scatter = at.Trellis(cars, title="Weight").points(x="weight", y="mpg")
    counts = at.Trellis(cars).hist(x="horsepower")
    link = at.link(scatter, counts)
    scatter.select(x=(2000, 3000))
    page = link.to_html(cols=2)
    assert page.count("class='anytrellis-embed'") == 2
    assert "<title>Weight</title>" in page
    assert "repeat(2," in page
    payloads = [json.loads(m.replace("<\\/", "</")) for m in
                re.findall(r"<script type='application/json'>(.*?)</script>", page)]  # fmt: skip
    assert payloads[0]["selection"] is not None
    assert payloads[1]["selection"] is None
    assert payloads[0]["link"]["group"] == payloads[1]["link"]["group"]
    with pytest.raises(ValueError, match="cols"):
        link.to_html(cols=0)


def test_a_saved_link_of_database_plots_reads_a_chunk_of_panels_at_a_time(monkeypatch) -> None:
    from test_query import frame

    import anytrellis.plot as plot
    from anytrellis import Trellis
    from anytrellis.data import Table

    monkeypatch.setattr(plot, "CHUNK_ROWS", 400)  # chunks of 4 panels
    df = frame(12_000, stations=120)
    rel = duckdb.from_arrow(df.to_arrow())
    a = Trellis(rel, wrap="station", load="pages").points(x="t", y="temp")
    b = Trellis(rel, wrap="station", load="pages").points(x="t", y="rain").hist(x="rain")
    link = at.link(a, b, on="t")
    a.show_page(2)
    a._scene()
    b._scene()
    reads: list[int] = []
    loads: list[int] = []
    query, load_all = Trellis._query_rows, Table._load

    def counted(self: Trellis, *args: Any) -> Table:
        rows = query(self, *args)
        reads.append(rows.n)
        return rows

    def loaded(self: Table) -> None:
        loads.append(1)
        load_all(self)

    monkeypatch.setattr(Trellis, "_query_rows", counted)
    monkeypatch.setattr(Table, "_load", loaded)
    page = link.to_html()
    assert loads == []  # no table read whole
    assert max(reads) <= 4 * 12_000 // 120  # a chunk's panels' rows
    assert sum(reads) == 2 * len(df)  # each plot's rows, once
    sizes = layer_sizes(page)
    assert all(drawn == keyed for plot_ in sizes for drawn, keyed in plot_), sizes
    assert sizes[0][0][0] == df.filter(pl.col("temp").is_finite()).height  # every panel's
    drawn = [n for n, _ in sizes[1] if n]  # (dense points' cells: none here)
    assert drawn[0] == len(df)
    assert len(drawn) == 2  # the points, and the histogram's bars with their members
