"""Linking with ``load="pages"``: rows sharing a key with those selected (``link=``), in
every panel, as a query; and plots linked by key (``anytrellis.link(..., on=)``) whether
they read pages or not, a plot reading pages highlighting the rows of its pages read and
its summaries from the database."""

from __future__ import annotations

from typing import Any

import duckdb
import numpy as np
import polars as pl
import pytest
from test_page_summaries import ids, readings
from test_query import LAZY

import anytrellis as at
from anytrellis import Trellis
from anytrellis.linking import highlight_message


def batched(n: int = 6000) -> pl.DataFrame:
    """Readings with a batch (some missing) and a run: keys shared across stations."""
    df = readings(n)
    rng = np.random.default_rng(0)
    batch = rng.integers(0, 300, len(df)).astype(str).astype(object)
    batch[::17] = None
    return df.with_columns(pl.Series("batch", batch.tolist()),
                           pl.Series("run", rng.integers(0, 50, len(df))))  # fmt: skip


def batches(df: pl.DataFrame) -> pl.DataFrame:
    """A row per batch: its mean reading and size."""
    known = df.filter(pl.col("batch").is_not_null())
    sizes = known.group_by("batch").agg(pl.col("t").mean().alias("mean_t"), pl.len().alias("size"))
    return sizes.sort("batch")


def paged(data: Any, **kw: Any) -> Trellis:
    return Trellis(data, wrap="station", rows=2, cols=3, **kw)


@pytest.mark.parametrize("kind", list(LAZY))
@pytest.mark.parametrize("link", ["batch", ["batch", "sensor"], "run"])
def test_link_selects_the_rows_sharing_a_key_in_every_panel(kind: str, link: Any) -> None:
    df = batched()
    a = paged(LAZY[kind](df), load="pages", link=link).points(x="t", y="v")
    b = paged(df, link=link).points(x="t", y="v")
    for brush in ({"x": (2, 3), "panel": "s03"}, {"x": (2, 3), "y": (0, 1), "panel": "s05"},
                  {"x": (2, 3)}):  # fmt: skip
        a.select(**brush)
        b.select(**brush)
        chosen = ids(a.selected())
        assert chosen == ids(b.selected())
        assert chosen


def test_the_brushed_panel_stays_while_the_pages_turn() -> None:
    df = batched()
    p = paged(duckdb.from_arrow(df.to_arrow()), load="pages", link="batch").points(x="t", y="v")
    spec, _ = p._scene()
    assert spec["layers"][0]["link"] is not None  # the browser grows a brush by the keys
    p.select(x=(2, 3), panel="s01")
    brushed = p.panels().index("s01")
    p._paging = {"page": 3}
    p._detail(None)
    assert p._window is not None
    assert brushed in p._window  # its marks' keys select those of the page shown
    read = p._table(p._layers[0])
    assert {"batch"} <= set(read.names)


def shown(p: Trellis) -> list[dict[int, list[float]] | None]:
    """What a plot's highlight shows: per spec layer drawing something, per panel, its
    instances' masks or shares, sorted (a plot reading pages has a layer for the cells of
    dense points too, empty here)."""
    entries = p._highlight_entries()
    message, buffers = highlight_message(entries, p._highlight)
    out: list[dict[int, list[float]] | None] = []
    for entry, (_, _, geom) in zip(message["layers"] or [None] * len(entries), entries,
                                   strict=True):  # fmt: skip
        if geom is not None and len(geom.rows) == 0:
            continue
        if entry is None:
            out.append(None)
            continue
        if "mask" in entry:
            bits = np.frombuffer(buffers[entry["mask"]], dtype=np.uint8)
            value = np.unpackbits(bits, bitorder="little")[: entry["count"]].astype(float)
        else:
            value = np.frombuffer(buffers[entry["fraction"]], dtype=np.float32).astype(float)
        out.append({int(k): sorted(np.round(value[geom.panel == k], 5).tolist())
                    for k in np.unique(geom.panel)})  # fmt: skip
    return out


def readings_plot(data: Any, **kw: Any) -> Trellis:
    p = paged(data, **kw)
    return p.points(x="t", y="v").hist(x="v", color="sensor", bins=12).box(x="t", y="v")


@pytest.mark.parametrize("kind", list(LAZY))
def test_a_selection_elsewhere_highlights_the_pages_read(kind: str) -> None:
    df = batched()
    by_batch = batches(df)
    scatter = Trellis(by_batch).points(x="mean_t", y="size")
    page = readings_plot(LAZY[kind](df), load="pages")
    every = readings_plot(df)
    scatter2 = Trellis(by_batch).points(x="mean_t", y="size")
    at.link(scatter, page, on="batch")
    at.link(scatter2, every, on="batch")
    for brush in ({"x": (4, 6)}, {"x": (0, 10), "y": (25, 100)}):
        scatter.select(**brush)
        scatter2.select(**brush)
        got, want = shown(page), shown(every)
        assert got == want
        assert any(v for layer in got if layer for vs in layer.values() for v in vs)
        assert ids(page.selected()) == ids(every.selected())  # the rows of the keys chosen
    # the page turned: the highlight of the rows read now
    page._paging = every._paging = {"page": 2}
    page._send_detail()
    every._send_detail()
    assert shown(page) == shown(every)
    scatter.select()
    assert page._highlight is None


@pytest.mark.parametrize("kind", list(LAZY))
def test_a_plot_reading_pages_selects_for_the_others(kind: str) -> None:
    df = batched()
    by_batch = batches(df)
    page = paged(LAZY[kind](df), load="pages").points(x="t", y="v")
    every = paged(df).points(x="t", y="v")
    a = Trellis(by_batch).points(x="mean_t", y="size")
    b = Trellis(by_batch).points(x="mean_t", y="size")
    at.link(page, a, on="batch")
    at.link(every, b, on="batch")
    page.select(x=(2, 2.5), panel="s07")
    every.select(x=(2, 2.5), panel="s07")
    assert shown(a) == shown(b)
    assert a._highlight is not None
    picked = a._highlight[id(a._layers[0])]
    assert isinstance(picked, np.ndarray)
    assert picked.any()
    assert a.selected()["batch"].to_list() == b.selected()["batch"].to_list()


def test_two_plots_reading_pages() -> None:
    df = batched()
    rel = duckdb.from_arrow(df.to_arrow())
    one = paged(rel, load="pages").points(x="t", y="v")
    two = readings_plot(rel, load="pages")
    every = readings_plot(df)
    other = paged(df).points(x="t", y="v")
    at.link(one, two, on="run")
    at.link(other, every, on="run")
    one.select(y=(2.5, 4))
    other.select(y=(2.5, 4))
    assert shown(two) == shown(every)
    assert ids(two.selected()) == ids(every.selected())


def test_a_plot_reading_pages_links_by_key() -> None:
    df = batched(600)
    rel = duckdb.from_arrow(df.to_arrow())
    with pytest.raises(ValueError, match="give on="):
        at.link(paged(rel, load="pages").points(x="t", y="v"), Trellis(df).points(x="t", y="v"))
