"""Lasso and click selection: what a lasso (a polygon) and marks clicked select, in memory,
from a database (``load="pages"``) and as ``figure.py`` draws it, and how Python reads a
selection made in the browser."""

from __future__ import annotations

from typing import Any

import duckdb
import narwhals as nw
import numpy as np
import polars as pl
import pytest
from test_page_summaries import readings

from anytrellis import Trellis, figure
from anytrellis.datasets import load
from anytrellis.selection import boxes_meet_polygon, in_polygon

TRIANGLE = [(2.0, 50.0), (7.0, 50.0), (4.0, 80.0)]


def ids(native: Any, column: str = "id") -> list[Any]:
    frame = nw.from_native(native)
    if isinstance(frame, nw.LazyFrame):
        frame = frame.collect()
    return sorted(frame[column].to_list())


@pytest.fixture
def gapminder() -> pl.DataFrame:
    return load("gapminder").with_columns(id=pl.int_range(pl.len()))


# ---- the polygon -----------------------------------------------------------------------------


def test_points_inside_by_the_even_odd_rule() -> None:
    rng = np.random.default_rng(4)
    x, y = rng.uniform(-1, 5, 2000), rng.uniform(-1, 5, 2000)
    tri = np.array([[0, 0], [4, 0], [0, 4]], dtype=float)
    assert (in_polygon(x, y, tri) == ((x > 0) & (y >= 0) & (x + y < 4))).mean() > 0.998
    bow = np.array([[0, 0], [2, 2], [4, 0], [4, 4], [2, 2], [0, 4]], dtype=float)
    assert in_polygon(np.array([0.5, 2.0]), np.array([2.0, 0.5]), bow).tolist() == [True, False]


def test_boxes_meet_a_polygon_by_any_overlap() -> None:
    tri = np.array([[0, 0], [4, 0], [0, 4]], dtype=float)
    x0, x1 = np.array([-1.0, 0.5, -1.0, 5.0]), np.array([5.0, 1.0, 10.0, 6.0])
    y0, y1 = np.array([1.0, 0.5, -1.0, 5.0]), np.array([1.2, 1.0, 10.0, 6.0])
    assert boxes_meet_polygon(x0, x1, y0, y1, tri).tolist() == [True, True, True, False]


# ---- a lasso ---------------------------------------------------------------------------------


def test_a_lasso_selects_the_points_inside(gapminder: pl.DataFrame) -> None:
    t = Trellis(gapminder, wrap="year").points(x="fertility", y="life_expect")
    t.select(lasso=TRIANGLE)
    inside = in_polygon(gapminder["fertility"].to_numpy(), gapminder["life_expect"].to_numpy(),
                        np.array(TRIANGLE))  # fmt: skip
    assert ids(t.selected()) == gapminder.filter(pl.Series(inside))["id"].to_list()
    sel = t.selection
    assert sel is not None
    assert sel["lasso"] == TRIANGLE
    assert (sel["x"], sel["y"]) == ((2.0, 7.0), (50.0, 80.0))  # its bounding box


def test_a_lasso_selects_bars_it_meets_and_lines_with_an_end_inside() -> None:
    df = pl.DataFrame({"id": [0, 1, 2], "x": [1.0, 3.0, 5.0], "y": [9.0, 9.0, 9.0]})
    corner = [(0.0, 8.0), (2.0, 8.0), (0.0, 12.0)]  # over the first bar's top, not the second's
    t = Trellis(df).bars(x="x", y="y")
    t.select(lasso=corner)
    assert ids(t.selected()) == [0]
    line = Trellis(df).line(x="x", y="y")
    line.select(lasso=[(2.5, 8.0), (3.5, 8.0), (3.0, 10.0)])  # the middle point
    assert ids(line.selected()) == [1]


def test_a_lasso_on_time_and_log_axes() -> None:
    w = load("seattle_weather").with_columns(id=pl.int_range(pl.len()))
    t = Trellis(w, y_scale="log").points(x="date", y="wind")
    corners = [("2013-01-01", 2.0), ("2014-01-01", 2.0), ("2013-07-01", 8.0)]
    t.select(lasso=corners)
    got = ids(t.selected())
    assert got
    chosen = w.filter(pl.col("id").is_in(got))
    assert str(chosen["date"].min()) >= "2013-01-01"
    assert str(chosen["date"].max()) <= "2014-01-01"
    assert chosen["wind"].min() >= 2.0


def test_lasso_and_at_are_checked() -> None:
    t = Trellis(pl.DataFrame({"x": [1.0], "y": [1.0]})).points(x="x", y="y")
    with pytest.raises(ValueError, match="three corners"):
        t.select(lasso=[(0, 0), (1, 1)])
    with pytest.raises(ValueError, match="not with x="):
        t.select(x=(0, 1), lasso=TRIANGLE)
    with pytest.raises(ValueError, match=r"\(x, y\)"):
        t.select(at=[1.0])


# ---- clicks ----------------------------------------------------------------------------------


def test_at_selects_the_mark_there_in_its_panel(gapminder: pl.DataFrame) -> None:
    t = Trellis(gapminder, wrap="year").points(x="fertility", y="life_expect")
    first = gapminder.row(0, named=True)
    point = (first["fertility"], first["life_expect"])
    t.select(at=[point], panel=str(first["year"]))
    assert ids(t.selected()) == [0]
    sel = t.selection
    assert sel is not None
    assert sel["at"] == [(*point, str(first["year"]))]
    t.select(at=[point])  # in every panel: the same values in another year too, if any
    assert 0 in ids(t.selected())


def test_at_follows_the_link_into_every_panel(gapminder: pl.DataFrame) -> None:
    t = Trellis(gapminder, wrap="year", link="country").points(x="fertility", y="life_expect")
    first = gapminder.row(0, named=True)
    t.select(at=[(first["fertility"], first["life_expect"])], panel=str(first["year"]))
    chosen = gapminder.filter(pl.col("id").is_in(ids(t.selected())))
    assert set(chosen["country"]) == {first["country"]}
    assert chosen.height == gapminder.filter(pl.col("country") == first["country"]).height


def test_a_click_from_the_browser_in_relative_units() -> None:
    """The browser's brush: axis units relative to the origins, and half a pixel's room."""
    w = load("seattle_weather").with_columns(id=pl.int_range(pl.len()))
    t = Trellis(w).points(x="date", y="temp_max")
    spec, _ = t._scene()
    origin = spec["x"]["origin"]
    row = w.row(100, named=True)
    ms = float(np.datetime64(row["date"], "ms").astype(np.int64))
    t._selection = {"x": None, "y": None, "panel": None, "at": [[ms - origin, row["temp_max"], 0]],
                    "near": [43_200_000.0, 0.05]}  # fmt: skip
    assert 100 in ids(t.selected())


def test_a_rug_is_not_clicked_and_a_lasso_takes_its_extent() -> None:
    df = pl.DataFrame({"id": [0, 1, 2], "x": [1.0, 2.0, 3.0], "y": [5.0, 6.0, 7.0]})
    t = Trellis(df).rug(x="x")
    t.select(at=[(2.0, 6.0)])
    assert ids(t.selected()) == []
    t.select(lasso=[(1.5, 100.0), (2.5, 100.0), (2.0, 200.0)])  # far above: its x extent
    assert ids(t.selected()) == [1]


# ---- from a database -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mark", "kw"),
    [
        ("points", {"x": "t", "y": "v"}),
        ("line", {"x": "t", "y": "v", "color": "sensor"}),
        ("segments", {"x": "t", "y": "v", "x2": "w"}),
        ("points", {"x": "when", "y": "v"}),
        ("points", {"x": "sensor", "y": "v"}),
    ],
)
def test_a_database_lasso_selects_as_memory_does(mark: str, kw: dict[str, Any]) -> None:
    df = readings(3000, stations=12).filter(pl.col("station").is_not_null())
    rel = duckdb.from_arrow(df.to_arrow())
    paged = getattr(Trellis(rel, wrap="station", rows=2, cols=2, load="pages"), mark)(**kw)
    memory = getattr(Trellis(df, wrap="station", rows=2, cols=2), mark)(**kw)
    for t in (paged, memory):
        t._scene()
        spec, _ = t._scene()
        x0, x1 = (min(p["x"][0] for p in spec["panels"]), max(p["x"][1] for p in spec["panels"]))
        xo = spec["x"].get("origin", 0.0)
        corners = [(x0 + (x1 - x0) * fx, y) for fx, y in ((0.1, -1.5), (0.9, -1.0), (0.5, 2.0))]
        if spec["x"]["kind"] == "band":
            corners = [(-0.4, -1.5), (1.4, -1.0), (0.5, 2.0)]
        elif spec["x"]["kind"] == "time":
            corners = [(np.datetime64(round(c + xo), "ms"), y) for c, y in corners]
        t.select(lasso=corners)
    got = ids(paged.selected())
    assert got
    assert got == ids(memory.selected())


def test_a_database_click_selects_as_memory_does() -> None:
    df = readings(3000, stations=12).filter(
        pl.col("station").is_not_null() & pl.col("v").is_finite()
    )
    rel = duckdb.from_arrow(df.to_arrow())
    row = df.row(0, named=True)
    for link in (None, "sensor"):
        paged = Trellis(rel, wrap="station", rows=2, cols=2, load="pages", link=link).points(
            x="t", y="v")  # fmt: skip
        memory = Trellis(df, wrap="station", rows=2, cols=2, link=link).points(x="t", y="v")
        for t in (paged, memory):
            t._scene()
            t.select(at=[(row["t"], row["v"])], panel=row["station"])
        got = ids(paged.selected())
        assert row["id"] in got
        assert got == ids(memory.selected())


# ---- figure.py -------------------------------------------------------------------------------


def test_figure_selects_as_python_and_draws_the_lasso(
    gapminder: pl.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    counted: list[int] = []
    real = figure.select

    def spy(marks: Any, brush: Any) -> Any:
        masks = real(marks, brush)
        counted.append(sum(int(m.sum()) for m in masks if m is not None))
        return masks

    monkeypatch.setattr(figure, "select", spy)
    t = Trellis(gapminder, wrap="year").points(x="fertility", y="life_expect")
    t.select(lasso=TRIANGLE)
    svg = figure.figure_svg(t)
    assert counted[-1] == len(ids(t.selected()))
    assert 'fill-opacity="0.07" stroke=' in svg  # the lasso's outline, a path
    first = gapminder.row(0, named=True)
    t.select(at=[(first["fertility"], first["life_expect"])], panel=str(first["year"]))
    figure.figure_svg(t)
    assert counted[-1] == 1
