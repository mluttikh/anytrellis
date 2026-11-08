"""Pages of a page column (``page=``): a page per level, a grid's every cell on each or a
wrap of the level's panels; named by their level, sorted and filtered within a level."""

from __future__ import annotations

import duckdb
import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.data import Table
from anytrellis.pages import page_labels, page_list


def readings(n: int = 6000) -> pl.DataFrame:
    """Sites (whose readings rise with their letter), stations of each, sensors by metric."""
    rng = np.random.default_rng(1)
    site = rng.choice(["A", "B", "C"], n)
    station = [f"{s}{k}" for s, k in zip(site, rng.integers(0, 12, n), strict=True)]
    base = {"A": 0.0, "B": 10.0, "C": 20.0}
    return pl.DataFrame(
        {
            "site": site,
            "station": station,
            "sensor": rng.choice(["a", "b"], n),
            "metric": rng.choice(["temp", "rain", "wind"], n),
            "t": rng.uniform(0, 10, n),
            "v": np.array([base[s] for s in site]) + rng.normal(0, 1, n),
        }
    )


def test_pages_of_levels_as_the_browser_makes_them() -> None:
    groups = [0, 0, 0, 1, 1, 1, 1, 1, 2]  # as in js/test/core.test.ts
    every = list(range(9))
    assert page_list(every, 3, groups) == [[0, 1, 2], [3, 4, 5], [6, 7], [8]]
    assert page_labels(page_list(every, 3, groups), groups, ["a", "b", "c"]) == [
        "a", "b (1 of 2)", "b (2 of 2)", "c"]  # fmt: skip
    assert page_list([7, 1, 0, 5], 3, groups) == [[1, 0], [7, 5]]  # sorted, filtered
    assert page_list([], 3, groups) == [[]]
    assert page_list(every, 4, None) == [[0, 1, 2, 3], [4, 5, 6, 7], [8]]


def test_a_wrap_a_page_per_level() -> None:
    df = readings()
    p = Trellis(df, wrap="station", page="site").points(x="t", y="v")
    assert p.pages == 3
    assert p.page_names == ["A", "B", "C"]
    assert all(name.startswith("A · ") for name in p.shown_panels())
    assert len(p.shown_panels()) == 12
    spec, _ = p._scene()
    assert spec["pages"]["title"] == "site"
    assert spec["pages"]["levels"] == ["A", "B", "C"]
    labels = [q["label"] for q in spec["panels"]]
    assert labels[0] == "A0"  # the strip: the station (the page names the site)
    p.show_page("C")
    assert p.page == 3
    assert all(name.startswith("C · ") for name in p.shown_panels())
    p.show_page(2)
    assert p.shown_panels()[0] == "B · B0"
    with pytest.raises(ValueError, match="no page 'D'"):
        p.show_page("D")


def test_a_level_of_more_panels_than_a_page_holds_goes_on_several() -> None:
    p = Trellis(readings(), wrap="station", page="site", rows=2, cols=4).points(x="t", y="v")
    assert p.page_names == [f"{s} ({k} of 2)" for s in "ABC" for k in (1, 2)]
    assert len(p.shown_panels()) == 8
    p.show_page("B")  # its first page
    assert p.page == 3
    p.show_page("B (2 of 2)")
    assert p.shown_panels()[0] == "B · B8"


def test_sorted_and_filtered_within_each_level() -> None:
    df = readings()
    p = Trellis(df, wrap="station", page="site").points(x="t", y="v")
    p.sort_panels("mean v", descending=True)
    means = dict(zip(p.panels(), p.stats()["mean v"], strict=True))
    shown = p.shown_panels()
    assert all(name.startswith("A") for name in shown)
    assert [means[n] for n in shown] == sorted((means[n] for n in shown), reverse=True)
    p.filter_panels("C")  # only site C's stations: one page
    assert p.page_names == ["C"]


def test_a_grid_per_level() -> None:
    df = readings()
    p = Trellis(df, row="sensor", col="metric", page="site", share_y="page")
    p.points(x="t", y="v")
    spec, _ = p._scene()
    assert spec["grid"]["rows"] == 2
    assert spec["grid"]["cols"] == 3
    assert len(spec["panels"]) == 18
    assert spec["pages"]["grid"] is True
    assert spec["pages"]["stats"] == []
    assert p.shown_panels() == [f"A · {s} · {m}" for s in "ab" for m in ("rain", "temp", "wind")]
    # each panel has its rows
    geom = p._geometry[0][2]
    assert geom is not None
    counts = np.bincount(geom.panel, minlength=18)
    for i, name in enumerate(p.panels()):
        site, sensor, metric = name.split(" · ")
        want = df.filter((pl.col("site") == site) & (pl.col("sensor") == sensor)
                         & (pl.col("metric") == metric))  # fmt: skip
        assert counts[i] == len(want), name
    # a y scale per site
    y = [tuple(q["y"]) for q in spec["panels"]]
    assert len(set(y[:6])) == 1
    assert y[0][1] < y[12][0]  # site A's below site C's
    with pytest.raises(ValueError, match="not sorted or filtered"):
        p.sort_panels("rows")


def test_a_page_column_alone_a_panel_a_page() -> None:
    p = Trellis(readings(), page="site").points(x="t", y="v")
    assert p.pages == 3
    assert p.shown_panels() == ["A"]


def test_the_levels_in_order() -> None:
    p = Trellis(readings(), wrap="station", page="site").points(x="t", y="v")
    p.order("site", ["C", "A", "B"])
    assert p.page_names == ["C", "A", "B"]
    p.order("site", by="mean", of="v", descending=True)
    assert p.page_names == ["C", "B", "A"]


def test_statistics_given_for_a_wrap_of_pages() -> None:
    df = readings()
    p = Trellis(df, wrap="station", page="site").points(x="t", y="v")
    info = df.group_by("site", "station").agg(pl.col("v").max().alias("top"))
    p.panel_stats(info)
    assert "top" in p.stats()
    with pytest.raises(ValueError, match="facet columns"):
        p.panel_stats(info.drop("site"))


def test_the_image_draws_the_page_shown(tmp_path) -> None:
    from anytrellis.figure import _page

    p = Trellis(readings(), row="sensor", col="metric", page="site").points(x="t", y="v")
    p.show_page("B")
    spec, _ = p._shown_scene()
    assert _page(p, spec) == list(range(6, 12))
    svg = p.save_svg(tmp_path / "b.svg").read_text()
    assert ">a<" in svg  # the grid's row strips
    assert "A0" not in svg


def test_pages_read_from_the_database_a_level_at_a_time(monkeypatch) -> None:
    loads: list[list[str]] = []
    original = Table._load

    def counted(self: Table) -> None:
        loads.append(list(self._wanted))
        original(self)

    monkeypatch.setattr(Table, "_load", counted)
    df = readings()
    rel = duckdb.from_arrow(df.to_arrow())
    p = Trellis(rel, row="sensor", col="metric", page="site", load="pages").points(x="t", y="v")
    eager = Trellis(df, row="sensor", col="metric", page="site").points(x="t", y="v")
    spec, _ = p._scene()
    assert loads == []
    assert p.panels() == eager.panels()
    for a, b in zip(spec["panels"], eager._scene()[0]["panels"], strict=True):
        assert np.allclose(a["y"], b["y"])
    read = p._table(p._layers[0])
    assert read.n == len(df.filter(pl.col("site").is_in(["A", "B"])))  # the page, the next
    p._paging = {"page": 2}
    assert p._detail(None) is not None
    assert p._table(p._layers[0]).n == len(df.filter(pl.col("site").is_in(["B", "C"])))
    wrap = Trellis(rel, wrap="station", page="site", load="pages").points(x="t", y="v")
    assert wrap.page_names == ["A", "B", "C"]


def test_what_page_columns_do_not_do() -> None:
    df = readings(600)
    with pytest.raises(ValueError, match="can't be a row"):
        Trellis(df, wrap="site", page="site")
    with pytest.raises(ValueError, match="rows='all'"):
        Trellis(df, wrap="station", page="site", rows="all")
    with pytest.raises(ValueError, match="rows= pages a wrap"):
        Trellis(df, row="sensor", page="site", rows=2)
    with pytest.raises(ValueError, match="give page="):
        Trellis(df, wrap="station", share_y="page").points(x="t", y="v")._scene()
