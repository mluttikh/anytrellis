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
    return [None if geom is None else rows[geom.rows] for _, _, geom in plot._saved_entries()[1]]


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
        link = at.link(a, b, on="country")
        a._scene()
        a.select(x=(6, 9), y=(20, 40), panel="1955")
        payloads = saved_links(link)
        source = marks_selected(a._every_row() if load_ == "pages" else a)
        chosen = chosen_keys(payloads[0]["layers"], source, payloads[0]["size"])
        out.append(link_highlight(payloads[1]["layers"], chosen))
    same(out[1], out[0])
    assert 0 < out[0][0][1].sum() < len(out[0][0][1])


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
