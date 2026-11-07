"""Paged wraps: when a wrap pages, its panels' statistics, and the page, sort and filters."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.figure import figure_svg
from anytrellis.pages import Stat, order


def stations(n: int, hours: int = 24) -> pl.DataFrame:
    """``n`` stations: station k's temperature rises by k/10 a day, from k."""
    k = np.repeat(np.arange(n), hours)
    t = np.tile(np.arange(hours, dtype=np.float64), n)
    return pl.DataFrame({
        "station": [f"s{i:03d}" for i in k],
        "t": t,
        "temp": k + k / 10 * t / 24,
        "zone": np.where(k % 2 == 0, "even", "odd"),
    })  # fmt: skip


def paged(n: int, **kwargs: Any) -> Trellis:
    return Trellis(stations(n), wrap="station", **kwargs).line(x="t", y="temp")


# ---- when a wrap pages ----------------------------------------------------------------------


def test_a_wrap_of_many_panels_pages_by_itself():
    assert paged(100)._scene()[0]["pages"] is None  # 100: all at once
    spec, _ = paged(101)._scene()
    assert (spec["pages"]["rows"], spec["pages"]["cols"]) == (4, 6)
    assert (spec["grid"]["rows"], spec["grid"]["cols"]) == (4, 6)
    # the panels placed in turn on a page: panel 24 starts the second page
    assert [(p["row"], p["col"]) for p in spec["panels"][22:26]] == [(3, 4), (3, 5), (0, 0), (0, 1)]


def test_rows_pages_any_wrap_and_all_never():
    spec, _ = paged(10, rows=1, cols=4)._scene()
    assert (spec["pages"]["rows"], spec["pages"]["cols"]) == (1, 4)
    t = paged(10, rows=1, cols=4)
    assert t.pages == 3
    assert t.shown_panels() == ["s000", "s001", "s002", "s003"]
    small = paged(10, rows=5, cols=4)._scene()[0]["pages"]
    assert small["rows"] == 3  # no more rows than the panels fill
    assert paged(300, rows="all")._scene()[0]["pages"] is None
    assert paged(300, rows="all").pages == 1
    with pytest.raises(ValueError, match="pages a wrap"):
        Trellis(stations(4), row="station", rows=2)
    with pytest.raises(ValueError, match="rows must be"):
        Trellis(stations(4), wrap="station", rows=0)


# ---- statistics ----------------------------------------------------------------------------


def test_builtin_stats_per_panel():
    t = paged(101)
    stats = t.stats()
    assert list(stats) == ["panel", "rows", "mean temp", "median temp", "min temp", "max temp",
                           "sd temp", "trend temp"]  # fmt: skip
    df = stations(101)
    for k in (0, 7, 100):
        v = df.filter(pl.col("station") == f"s{k:03d}")["temp"].to_numpy()
        assert stats["rows"][k] == 24
        assert np.isclose(stats["mean temp"][k], v.mean())
        assert np.isclose(stats["median temp"][k], np.median(v))
        assert np.isclose(stats["max temp"][k], v.max())
        assert np.isclose(stats["sd temp"][k], v.std(ddof=1)) or k == 0
        # the least-squares line's rise over the panel's x: k/10 a day, over 23 hours
        assert np.isclose(stats["trend temp"][k], k / 10 * 23 / 24)
    spec, _ = t._scene()
    trend = spec["pages"]["stats"][-1]
    assert trend["text"][7] == "0.6708"  # 4 significant digits
    assert spec["pages"]["stats"][0]["text"][0] == "24"


def test_stats_of_x_when_y_is_not_numbers_and_missing_values():
    df = stations(101).with_columns(pl.when(pl.col("station") == "s003").then(None)
                                    .otherwise(pl.col("temp")).alias("temp"))  # fmt: skip
    t = Trellis(df, wrap="station").line(x="t", y="temp")
    stats = t.stats()
    assert math.isnan(stats["mean temp"][3])
    assert stats["rows"][3] == 24
    spec, _ = t._scene()
    assert spec["pages"]["stats"][1]["values"][3] is None  # JSON: null
    h = Trellis(stations(101), wrap="station").hist(x="temp")
    assert "mean temp" in h.stats()
    assert "trend temp" not in h.stats()  # no x to trend over


def test_panel_stats_join_by_the_facet_columns():
    df = stations(101)
    info = df.group_by("station", maintain_order=True).agg(
        pl.col("zone").first(), pl.col("temp").max().alias("peak"), (pl.len() * 2).alias("rows")
    )
    info = info.filter(pl.col("station") != "s005")
    t = paged(101).panel_stats(info)
    stats = t.stats()
    assert stats["zone"][:4] == ["even", "odd", "even", "odd"]
    assert stats["zone"][5] == ""  # not in the table
    assert math.isnan(stats["peak"][5])
    assert stats["rows"][0] == 48  # the table's replaces the plot's
    assert list(stats).count("rows") == 1
    with pytest.raises(ValueError, match="one row per panel"):
        paged(101).panel_stats(pl.concat([info, info])).stats()
    with pytest.raises(ValueError, match="facet columns"):
        paged(101).panel_stats(info.drop("station"))
    with pytest.raises(ValueError, match="for a wrap"):
        Trellis(df, row="station").panel_stats(info)


# ---- order, pages ---------------------------------------------------------------------------

NAMES = ["north a", "north b", "south a", "south b", "east"]
STATS = [
    Stat("v", "number", [3.0, 1.0, math.nan, 1.0, 2.0], []),
    Stat("zone", "text", ["cold", "cold", "warm", "", "warm"], []),
]


@pytest.mark.parametrize(
    ("paging", "expected"),
    [
        ({}, [0, 1, 2, 3, 4]),
        ({"name": "North"}, [0, 1]),
        ({"name": "a north"}, [0]),  # every word
        ({"sort": "v"}, [1, 3, 4, 0, 2]),  # ties as given, missing last
        ({"sort": "v", "descending": True}, [0, 4, 1, 3, 2]),
        ({"sort": "zone"}, [0, 1, 2, 4, 3]),
        ({"sort": "zone", "descending": True}, [2, 4, 0, 1, 3]),
        ({"where": {"v": [1.5, None]}}, [0, 4]),
        ({"where": {"v": [None, 2]}}, [1, 3, 4]),
        ({"where": {"zone": "WAR"}}, [2, 4]),
        ({"where": {"zone": "", "v": [None, None]}}, [0, 1, 2, 3, 4]),  # open: no filter
        ({"where": {"nothing": [1, 2]}}, [0, 1, 2, 3, 4]),
        ({"name": "south", "sort": "v", "descending": True}, [3, 2]),
    ],
)  # fmt: skip
def test_order_filters_then_sorts(paging: Any, expected: list[int]):
    # js/test/core.test.ts checks panelOrder with the same cases
    assert order(STATS, NAMES, paging) == expected


def test_sort_filter_and_turn_pages_from_python():
    t = paged(150)
    assert (t.pages, t.page) == (7, 1)
    t.sort_panels("trend temp", descending=True)
    assert t.shown_panels()[:3] == ["s149", "s148", "s147"]
    t.show_page(7)
    assert t.page == 7
    assert t.shown_panels() == [f"s{k:03d}" for k in range(5, -1, -1)]
    t.filter_panels("s1")  # turns back to the first page
    assert t.page == 1
    assert t.pages == 3  # s100 to s149 and s010 to s019: 60 panels
    t.filter_panels(**{"mean temp": (150, None)})  # k + k/10 * 11.5/24 >= 150: s144 on
    assert t.shown_panels() == ["s149", "s148", "s147", "s146", "s145", "s144"]
    assert t.paging["where"] == {"mean temp": [150, None]}
    t.filter_panels()
    assert t.pages == 7
    t.sort_panels()
    assert t.shown_panels()[0] == "s000"
    with pytest.raises(ValueError, match="no statistic"):
        t.sort_panels("height")
    with pytest.raises(ValueError, match="no statistic"):
        t.filter_panels(height=(1, 2))
    with pytest.raises(ValueError, match="page must be from 1 to 7"):
        t.show_page(8)
    with pytest.raises(ValueError, match="does not page"):
        paged(10).show_page(1)
    assert paged(10).shown_panels() == [f"s{k:03d}" for k in range(10)]


def test_paging_goes_to_the_browser_and_back():
    t = paged(150)
    w = t.widget
    assert w.paging == {}
    t.sort_panels("max temp").show_page(2)
    assert w.paging == {"sort": "max temp", "descending": False, "page": 1}
    w.paging = {"page": 3, "name": "s0"}  # the reader, in the browser
    assert t.paging == {"page": 3, "name": "s0"}
    assert t._paging == {"page": 3, "name": "s0"}  # kept for save_html
    assert t.page == 4  # s000 to s099: 5 pages
    assert '"paging": {"page": 3, "name": "s0"}' in t._embed_html()


def test_images_draw_the_page_shown():
    t = paged(150).sort_panels("trend temp", descending=True).show_page(2)
    svg = figure_svg(t, width=900)
    assert ">s125<" in svg  # the 25th: first on page 2
    assert ">11.98<" in svg  # its trend, on its strip
    assert ">s149" not in svg
    t.filter_panels("nothing")
    assert "No panel matches the filters" in figure_svg(t, width=900)


def test_a_short_last_page_keeps_the_height():
    from anytrellis.figure import layout

    spec, _ = paged(101)._scene()
    assert layout(spec, 900, page=[100]).height == layout(spec, 900).height
    assert layout(spec, 900, page=[]).height == layout(spec, 900).height


# ---- the panels sent: around the page shown -------------------------------------------------


class Sent:
    """A widget's messages to the browser."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def __call__(self, content: dict[str, Any], buffers: Any = None) -> None:
        self.messages.append(content)

    def details(self) -> list[dict[str, Any]]:
        return [m for m in self.messages if m["type"] == "detail"]


def has(layer: dict[str, Any]) -> list[int]:
    """The panels a spec layer has data of."""
    return layer["panels"]


def test_a_paged_plot_sends_the_pages_around_the_one_shown():
    t = paged(300)
    spec, _ = t._scene()
    line = spec["layers"][0]
    assert has(line) == list(range(48))  # pages 1 and 2: 24 panels each
    assert line["count"] == 48 * 23  # 23 segments a station
    full, _ = t._full_scene()  # a saved page's: every panel's, as it starts
    assert full["layers"][0]["count"] == 300 * 23
    assert "panels" not in full["layers"][0]
    few = paged(30)  # it does not page: every panel's data, saved or shown
    assert few._full_scene()[0] is few._scene()[0]
    assert "panels" not in few._scene()[0]["layers"][0]


def test_turning_pages_sends_their_panels_once():
    t = paged(300)
    sent = Sent()
    t.widget.send = sent
    t.show_page(5)  # pages 4 to 6
    [message] = sent.details()
    [layer] = message["layers"]
    assert layer["index"] == 0
    assert layer["of"] == t._scene()[0]["layers"][0]["coords"]["id"]
    assert has(layer["layer"]) == list(range(72, 144))
    assert layer["layer"]["count"] == 72 * 23
    t.show_page(5)
    assert len(sent.details()) == 1  # the same page: nothing new
    t.widget.paging = {"page": 11}  # the reader, in the browser: page 12 of 13
    assert has(sent.details()[-1]["layers"][0]["layer"]) == list(range(240, 300))
    t.sort_panels("trend temp", descending=True)  # back to page 1: the steepest first
    assert has(sent.details()[-1]["layers"][0]["layer"]) == list(range(252, 300))
    # the buffers sent are there to ask for
    coords = sent.details()[-1]["layers"][0]["layer"]["coords"]["id"]
    t.widget._on_msg(t.widget, {"type": "need", "ids": [coords]}, [])
    assert sent.messages[-1]["type"] == "put"


def test_an_opened_panel_of_another_page_comes_with_its_data():
    t = paged(300)
    sent = Sent()
    t.widget.send = sent
    t.open("s250")
    assert 250 in has(sent.details()[-1]["layers"][0]["layer"])
    t.widget.open_panel = "s260"  # opened in the browser
    assert 260 in has(sent.details()[-1]["layers"][0]["layer"])


def test_labels_come_with_their_panels():
    data = stations(150)
    first = data.group_by("station", maintain_order=True).first()
    t = Trellis(data, wrap="station").line(x="t", y="temp").text(first, x="t", y="temp",
                                                                 text="station")  # fmt: skip
    spec, _ = t._scene()
    assert spec["layers"][1]["type"] == "text"
    assert has(spec["layers"][1]) == list(range(48))
    assert spec["layers"][1]["count"] == 48
    sent = Sent()
    t.widget.send = sent
    t.show_page(6)
    assert [lr["index"] for lr in sent.details()[-1]["layers"]] == [0, 1]
    assert sent.details()[-1]["layers"][1]["layer"]["count"] == 150 - 96


def test_tooltips_and_images_of_a_page_far_away():
    t = paged(300).show_page(10)  # no widget: the images draw it all the same
    assert ">s216<" in figure_svg(t, width=900)
    shown = t._shown_layers[0]
    assert shown["count"] == 72 * 23
    sent = Sent()
    t.widget.send = sent
    t.widget._on_msg(t.widget, {"type": "tooltip", "request": 1, "layer": 0, "index": 0,
                                "of": shown["coords"]["id"]}, [])  # fmt: skip
    assert sent.messages[-1]["rows"] == []  # no tooltip columns: the browser shows x and y
    geom = t._sent[0][2]
    assert geom is not None
    assert geom.panel[0] == 192  # the first instance: page 9's first panel


def test_a_saved_page_has_every_panel_and_the_page_shown():
    import json
    import re

    t = paged(300).show_page(10)
    found = re.search(r"<script type='application/json'>(.*?)</script>", t._embed_html())
    assert found is not None
    payload = json.loads(found.group(1).replace("<\\/", "</"))
    assert payload["spec"]["layers"][0]["count"] == 300 * 23
    assert payload["paging"] == {"page": 9}
    first = payload["spec"]["layers"][0]
    ids = {first["coords"]["id"], first["starts"]["id"]}
    assert ids <= set(payload["buffers"])


def test_long_lines_in_pages_are_thinned_and_sent_by_page():
    from anytrellis.detail import THIN

    n = THIN + 5_000
    rng = np.random.default_rng(0)
    data = {"s": np.repeat([f"s{i}" for i in range(6)], n),
            "t": np.tile(np.arange(n, dtype=np.float64), 6),
            "v": np.cumsum(rng.normal(size=6 * n))}  # fmt: skip
    t = Trellis(data, wrap="s", rows=1, cols=2).line(x="t", y="v")
    spec, _ = t._scene()
    assert has(spec["layers"][0]) == [0, 1, 2, 3]  # pages 1 and 2
    thin = spec["layers"][0]["count"]
    assert thin < 4 * n / 2  # thinned (M4)
    sent = Sent()
    t.widget.send = sent
    ox = spec["x"]["origin"]
    report = {"width": 800, "x": [[0, [1000 - ox, 2000 - ox]]], "y": [],
              "panels": [[0, 400, 300], [1, 400, 300]]}  # fmt: skip
    t.widget._on_msg(t.widget, {"type": "view", **report}, [])
    zoomed = sent.details()[-1]["layers"][0]["layer"]
    assert has(zoomed) == [0, 1, 2, 3]

    def in_view(entry: Any) -> int:  # panel 0's segments between t = 1000 and 2000
        g = entry[2]
        return int(((g.panel == 0) & (g.x0 >= 1000) & (g.x0 <= 2000)).sum())

    assert in_view(t._sent[0]) > 2 * in_view(t._start[0])  # in detail where zoomed in
    t.show_page(3)  # panels 4 and 5: the window moves, the detail stays
    moved = sent.details()[-1]["layers"][0]["layer"]
    assert has(moved) == [2, 3, 4, 5]
    full, _ = t._full_scene()
    start = t._start[0][2]
    assert start is not None
    assert full["layers"][0]["count"] == start.count  # every panel, thinned as it starts
    assert set(start.panel.tolist()) == set(range(6))
