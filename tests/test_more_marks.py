"""Segments, hexagonal bins, density contours and rugs: what they draw, what a brush over
them selects, and the same from a database (``load="pages"``)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import polars as pl
import pytest
from test_page_summaries import ids, readings

from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.stats import HexGrid


def layer_spec(t: Trellis, name: str) -> dict[str, Any]:
    spec, _ = t._scene()
    return next(lr for lr in spec["layers"] if lr["name"] == name)


def geometry(t: Trellis, name: str) -> Any:
    t._scene()
    return next(g for lr, _, g in t._geometry if lr.name == name)


# ---- segments --------------------------------------------------------------------------------


def test_a_segment_a_row_from_its_start_to_its_end() -> None:
    df = pl.DataFrame({"x": [0.0, 1.0, np.nan, 3.0], "y": [0.0, 1.0, 2.0, 3.0],
                       "x2": [1.0, 2.0, 3.0, 4.0], "y2": [5.0, 6.0, 7.0, np.inf]})  # fmt: skip
    t = Trellis(df).segments(x="x", y="y", x2="x2", y2="y2")
    g = geometry(t, "segment")
    assert g.rows.tolist() == [0, 1]  # (an end not finite: not drawn)
    assert g.rows_end.tolist() == [0, 1]
    assert g.x1.tolist() == [1.0, 2.0]
    assert g.y1.tolist() == [5.0, 6.0]
    assert layer_spec(t, "segment")["type"] == "line"
    assert t._scene()[0]["panels"][0]["y"][1] >= 6.0  # its ends' range too


def test_a_segment_needs_an_end_and_keeps_the_axis_not_given() -> None:
    df = pl.DataFrame({"x": [0.0, 1.0], "y": [0.0, 1.0], "y2": [2.0, 3.0]})
    with pytest.raises(ValueError, match="x2"):
        Trellis(df).segments(x="x", y="y")
    g = geometry(Trellis(df).segments(x="x", y="y", y2="y2"), "segment")
    assert g.x1.tolist() == [0.0, 1.0]  # vertical: x2 is x


def test_a_brush_selects_the_segments_with_an_end_inside() -> None:
    df = pl.DataFrame({"id": [0, 1, 2], "x": [0.0, 5.0, 8.0], "y": [0.0, 0.0, 0.0],
                       "x2": [1.0, 9.0, 9.0], "y2": [1.0, 1.0, 1.0]})  # fmt: skip
    t = Trellis(df).segments(x="x", y="y", x2="x2", y2="y2")
    t.select(x=(0.5, 1.5), y=(0.5, 1.5))
    assert t.selected()["id"].to_list() == [0]
    t.select(x=(8.5, 9.5))
    assert t.selected()["id"].to_list() == [1, 2]


# ---- hexagonal bins --------------------------------------------------------------------------


def test_hexagons_count_every_row_once() -> None:
    p = load("penguins")
    t = Trellis(p, wrap="species").hexbin(x="bill_length_mm", y="bill_depth_mm", bins=10)
    t._scene()
    part = next(d.part for d in t._drawn if d.part is not None)
    counts = part.table.column("count").values
    finite = p.drop_nulls(["bill_length_mm", "bill_depth_mm"])
    assert counts.sum() == finite.height
    spec = layer_spec(t, "hexbin")
    assert spec["type"] == "band"
    assert spec["count"] == 2 * len(counts)  # two halves each
    assert [lg["kind"] for lg in t._scene()[0]["legends"]] == ["number"]


def test_a_hexagon_of_percents_sums_to_a_hundred_a_panel() -> None:
    p = load("penguins")
    t = Trellis(p, wrap="island").hexbin(x="bill_length_mm", y="bill_depth_mm", stat="percent")
    t._scene()
    part = next(d.part for d in t._drawn if d.part is not None)
    from anytrellis.stats import PANEL

    pct = part.table.column("percent").values
    panel = part.table.column(PANEL).values.astype(int)
    assert np.allclose(np.bincount(panel, weights=pct), 100)


def test_each_point_falls_in_the_nearest_hexagon() -> None:
    rng = np.random.default_rng(1)
    x, y = rng.normal(0, 1, 2000), rng.normal(0, 3, 2000)
    grid = HexGrid.over(x, y, (12, 8), 0.62)
    codes = grid.cells(x, y)
    cx, cy = grid.centres(codes)
    # the hexagon's centre is the nearest of all centres, in the grid's own units
    every = np.unique(codes)
    ax, ay = grid.centres(every)
    d = ((x[:, None] - ax) / grid.sx) ** 2 + ((y[:, None] - ay) / grid.sy) ** 2 * 3
    assert np.allclose(((x - cx) / grid.sx) ** 2 + ((y - cy) / grid.sy) ** 2 * 3, d.min(axis=1))


def test_a_brush_over_hexagons_selects_their_rows() -> None:
    df = pl.DataFrame({"id": range(400), "x": np.linspace(0, 10, 400),
                       "y": np.sin(np.linspace(0, 10, 400))})  # fmt: skip
    t = Trellis(df).hexbin(x="x", y="y", bins=10)
    t.select(x=(4.0, 6.0))
    chosen = t.selected()["x"].to_numpy()
    assert chosen.min() < 4.5  # whole hexagons
    assert chosen.max() > 5.5


def test_bins_and_stat_are_checked() -> None:
    df = pl.DataFrame({"x": [0.0], "y": [0.0]})
    with pytest.raises(ValueError, match="stat"):
        Trellis(df).hexbin(x="x", y="y", stat="mean")  # type: ignore[arg-type]


# ---- density contours ------------------------------------------------------------------------


def test_contours_at_levels_shared_by_the_panels() -> None:
    p = load("penguins")
    t = Trellis(p, wrap="island").contour(x="bill_length_mm", y="bill_depth_mm", levels=3)
    t._scene()
    part = next(d.part for d in t._drawn if d.part is not None)
    levels = np.unique(part.table.column("level").values)
    assert 2 <= len(levels) <= 3
    assert np.allclose(levels / levels.max(), np.arange(4 - len(levels), 4) / 3)
    spec = layer_spec(t, "contour")
    assert spec["type"] == "line"
    assert spec["count"] > 20


def test_a_contour_line_is_closed_round_a_lone_bump() -> None:
    rng = np.random.default_rng(2)
    df = pl.DataFrame({"x": rng.normal(0, 1, 3000), "y": rng.normal(0, 1, 3000)})
    g = geometry(Trellis(df).contour(x="x", y="y", levels=1), "contour")
    ends = np.round(np.concatenate([np.c_[g.x0, g.y0], np.c_[g.x1, g.y1]]), 9)
    _, n = np.unique(ends, axis=0, return_counts=True)
    assert (n == 2).all()  # every end meets another: one closed line


def test_contours_select_nothing_and_are_checked() -> None:
    df = pl.DataFrame({"x": [0.0, 1.0, 2.0], "y": [0.0, 1.0, 0.5]})
    t = Trellis(df).contour(x="x", y="y")
    t.select(x=(-1, 3))
    assert t.selected().height == 0
    with pytest.raises(ValueError, match="levels"):
        Trellis(df).contour(x="x", y="y", levels=0)
    with pytest.raises(ValueError, match="gridsize"):
        Trellis(df).contour(x="x", y="y", gridsize=2)


# ---- rugs ------------------------------------------------------------------------------------


def test_a_rug_is_pinned_to_the_panels_edge_and_keeps_the_axis() -> None:
    p = load("penguins")
    alone = Trellis(p).points(x="bill_length_mm", y="bill_depth_mm")
    t = Trellis(p).points(x="bill_length_mm", y="bill_depth_mm").rug(
        x="bill_length_mm", y="bill_depth_mm", length=6)  # fmt: skip
    spec, _ = t._scene()
    assert spec["panels"][0]["y"] == alone._scene()[0]["panels"][0]["y"]  # pixels: no range
    assert spec["panels"][0]["x"] == alone._scene()[0]["panels"][0]["x"]
    x, y = layer_spec(t, "rug"), layer_spec(t, "rug_y")
    assert (x["type"], x["pin"], y["pin"]) == ("line", "y", "x")
    g = geometry(t, "rug")
    assert (g.y0 == 0).all()
    assert (g.y1 == 6).all()
    assert (g.x0 == g.x1).all()
    assert x["color"]["solid"] == layer_spec(t, "points")["color"]["solid"]  # its marks' colour


def test_a_brush_selects_a_rug_by_its_values_alone() -> None:
    df = pl.DataFrame({"id": range(5), "x": [1.0, 2.0, 3.0, 4.0, 5.0],
                       "y": [10.0, 20.0, 30.0, 40.0, 50.0]})  # fmt: skip
    t = Trellis(df).rug(x="x")
    t.select(x=(1.5, 3.5), y=(1e6, 2e6))  # (no row's y there: a rug's ticks, not its y)
    assert t.selected()["id"].to_list() == [1, 2]


def test_a_rug_needs_a_column() -> None:
    with pytest.raises(ValueError, match="x=, y="):
        Trellis(pl.DataFrame({"x": [1.0]})).rug()


def test_a_rug_draws_at_the_bottom_edge_in_svg(tmp_path: Path) -> None:
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [5.0, 6.0, 7.0]})
    Trellis(df).rug(x="x", length=10, color="#ff0000").save_svg(tmp_path / "rug.svg")
    svg = (tmp_path / "rug.svg").read_text()
    ticks = re.findall(r'<path d="([^"]*)"[^>]*stroke="#ff0000"', svg)
    assert ticks, svg[:500]
    ys = [float(v) for v in re.findall(r"[ML]\s*[-\d.]+[ ,]([-\d.]+)", ticks[0])]
    assert max(ys) - min(ys) == pytest.approx(10, abs=0.01)


# ---- from a database -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mark", "kw", "brush"),
    [
        ("rug", {"x": "t"}, {"x": (2.0, 4.0), "y": (100.0, 200.0)}),
        ("rug", {"y": "v"}, {"y": (-1.0, 1.0)}),
        ("segments", {"x": "t", "y": "v", "x2": "w"}, {"x": (2.0, 4.0), "y": (-1.0, 1.0)}),
    ],
)
def test_a_database_selects_as_memory_does(mark: str, kw: dict[str, Any],
                                           brush: dict[str, Any]) -> None:  # fmt: skip
    df = readings(3000, stations=12).filter(pl.col("station").is_not_null())
    rel = duckdb.from_arrow(df.to_arrow())
    paged = getattr(Trellis(rel, wrap="station", rows=2, cols=2, load="pages"), mark)(**kw)
    memory = getattr(Trellis(df, wrap="station", rows=2, cols=2), mark)(**kw)
    for t in (paged, memory):
        t._scene()
        t.select(**brush)
    got = ids(paged.selected())
    assert got
    assert got == ids(memory.selected())
