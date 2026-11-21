"""Layout: the way a wrap fills its cells (``direction=``), panels placed by a layout table
(``layout=``), panels sized by their range (``space=``) and columns repeated as rows
(``repeat=``), in memory, in a database and as ``figure.py`` draws them."""

from __future__ import annotations

from typing import Any

import duckdb
import narwhals as nw
import numpy as np
import polars as pl
import pytest
from test_page_summaries import readings

from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.facets import DIRECTIONS, place, wrap_shape
from anytrellis.figure import figure_svg, layout


def cells(t: Trellis) -> list[str]:
    """The panels' first letters, row by row, a space for an empty cell."""
    spec, _ = t._scene()
    grid = spec["grid"]
    out = [[" "] * grid["cols"] for _ in range(grid["rows"])]
    for p in spec["panels"]:
        out[p["row"]][p["col"]] = p["label"][0]
    return ["".join(r) for r in out]


def letters(n: int) -> pl.DataFrame:
    return pl.DataFrame({"k": [chr(97 + i) for i in range(n)], "x": [1.0] * n, "y": [1.0] * n})


# ---- direction -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("direction", "want"),
    [
        ("h", ["abc", "def", "g  "]),
        ("v", ["adg", "be ", "cf "]),
        ("rt", ["cba", "fed", "  g"]),
        ("lb", ["g  ", "def", "abc"]),
        ("tr", ["gda", " eb", " fc"]),
        ("br", [" fc", " eb", "gda"]),
    ],
)
def test_a_wrap_fills_its_cells_in_the_direction_given(direction: str, want: list[str]) -> None:
    t = Trellis(letters(7), wrap="k", cols=3, direction=direction).points(x="x", y="y")
    assert cells(t) == want


def test_every_direction_places_each_panel_in_its_own_cell() -> None:
    for direction in DIRECTIONS:
        for n in range(1, 14):
            for cols in range(1, n + 1):
                rows, c = wrap_shape(n, cols, direction)
                at = {place(k, rows, c, direction) for k in range(n)}
                assert len(at) == n
                assert all(0 <= r < rows and 0 <= q < c for r, q in at)


def test_a_paged_wrap_fills_each_page_in_its_direction() -> None:
    t = Trellis(letters(10), wrap="k", rows=2, cols=2, direction="v").points(x="x", y="y")
    spec, _ = t._scene()
    assert spec["grid"]["dir"] == "tl"
    box = layout(spec, 600)
    first = sorted(box.panels, key=lambda b: (b.rect.x, b.rect.y))
    assert [b.label for b in first] == ["a", "b", "c", "d"]  # down the columns
    assert box.panels[1].rect.x == box.panels[0].rect.x  # b below a


def test_direction_is_checked_set_and_written() -> None:
    with pytest.raises(ValueError, match="direction"):
        Trellis(letters(3), wrap="k", direction="up")
    with pytest.raises(ValueError, match="grid"):
        Trellis(letters(3), col="k", direction="v")
    t = Trellis(letters(7), wrap="k", cols=3).points(x="x", y="y")
    t.direction = "v"
    assert cells(t)[0] == "adg"
    assert 'direction="v"' in t.code()
    names = [s["name"] for sec in t._scene()[0]["settings"] for s in sec["settings"]]
    assert "direction" in names


# ---- layout tables ---------------------------------------------------------------------------


GRID = pl.DataFrame({"k": ["a", "b", "c"], "row": [1, 2, 2], "col": [2, 1, 3]})


def test_a_layout_table_places_each_panel_and_leaves_the_rest_empty() -> None:
    t = Trellis(letters(3), wrap="k", layout=GRID).points(x="x", y="y")
    assert cells(t) == [" a ", "b c"]
    mapping = Trellis(letters(3), wrap="k", layout={"a": (1, 2), "b": (2, 1), "c": (2, 3)})
    assert cells(mapping.points(x="x", y="y")) == [" a ", "b c"]


def test_a_layout_table_of_two_wrap_columns_and_number_levels() -> None:
    df = pl.DataFrame({"g": ["p", "p", "q"], "n": [1, 2, 1], "x": [0.0] * 3, "y": [0.0] * 3})
    table = pl.DataFrame({"g": ["p", "p", "q"], "n": [1, 2, 1], "row": [1, 1, 2], "col": [1, 2, 1]})
    spec, _ = Trellis(df, wrap=["g", "n"], layout=table).points(x="x", y="y")._scene()
    at = {p["label"]: (p["row"], p["col"]) for p in spec["panels"]}
    assert at == {"p · 1": (0, 0), "p · 2": (0, 1), "q · 1": (1, 0)}


def test_a_layout_table_is_checked() -> None:
    def plot(table: Any, **kw: Any) -> None:
        Trellis(letters(3), wrap="k", layout=table, **kw).points(x="x", y="y")._scene()

    with pytest.raises(ValueError, match=r"no place for \['c'\]"):
        plot(GRID.head(2))
    with pytest.raises(ValueError, match="both at row 1, col 2"):
        plot(pl.concat([GRID, pl.DataFrame({"k": ["d"], "row": [1], "col": [2]})]))
    with pytest.raises(ValueError, match="counted from 1"):
        plot({"a": (0, 1)})
    with pytest.raises(ValueError, match="needs the columns"):
        plot(GRID.drop("col"))
    with pytest.raises(ValueError, match="cols= or direction="):
        plot(GRID, cols=2)
    with pytest.raises(ValueError, match="rows="):
        plot(GRID, rows=2)
    with pytest.raises(ValueError, match="wrap="):
        Trellis(letters(3), layout=GRID)


def test_a_layout_table_keeps_its_places_on_every_page() -> None:
    df = pl.concat([letters(3).with_columns(half=pl.lit(h)) for h in ("one", "two")])
    t = Trellis(df.filter((pl.col("half") == "one") | (pl.col("k") != "a")), wrap="k",
                layout=GRID, page="half").points(x="x", y="y")  # fmt: skip
    spec, _ = t._scene()
    assert spec["pages"]["grid"]
    assert cells(t) == [" a ", "b c"]
    second = layout(spec, 600, page=[i for i, g in enumerate(spec["pages"]["groups"]) if g == 1])
    assert {b.label for b in second.panels} == {"b", "c"}
    assert [b.rect.x for b in second.panels] == [b.rect.x for b in layout(spec, 600).panels[1:]]


def test_a_layout_table_with_a_database_and_written_as_code() -> None:
    gapminder = load("gapminder")
    rel = duckdb.from_arrow(gapminder.to_arrow())
    europe = pl.DataFrame({"country": ["Spain", "France", "Germany"], "row": [2, 1, 1],
                           "col": [1, 1, 2]})  # fmt: skip
    t = Trellis(rel.filter("country in ('Spain', 'France', 'Germany')"), wrap="country",
                layout=duckdb.from_arrow(europe.to_arrow())).line(x="year", y="pop")  # fmt: skip
    spec, _ = t._scene()
    assert {p["label"]: (p["row"], p["col"]) for p in spec["panels"]} == {
        "France": (0, 0), "Germany": (0, 1), "Spain": (1, 0)}  # fmt: skip
    names = [s["name"] for sec in spec["settings"] for s in sec["settings"]]
    assert "cols" not in names
    assert "direction" not in names
    assert "layout=" in t.code()


# ---- space -----------------------------------------------------------------------------------


def test_free_x_space_makes_each_category_as_wide() -> None:
    df = pl.DataFrame({"g": ["a"] * 2 + ["b"] * 4, "k": ["p", "q", "p", "q", "r", "s"],
                       "v": [1.0] * 6})  # fmt: skip
    t = Trellis(df, col="g", share_x="col", space="free_x").bars(x="k", y="v")
    spec, _ = t._scene()
    assert spec["space"] == {"x": True, "y": False}
    a, b = layout(spec, 900).panels
    assert b.rect.w / a.rect.w == pytest.approx(2, rel=0.02)
    assert a.rect.h == b.rect.h
    fixed = Trellis(df, col="g", share_x="col").bars(x="k", y="v")._scene()[0]
    assert fixed["space"] is None
    p, q = layout(fixed, 900).panels
    assert p.rect.w == q.rect.w


def test_free_y_space_sizes_each_row_by_its_range() -> None:
    df = pl.DataFrame({"g": ["a"] * 2 + ["b"] * 2, "x": [0.0, 1.0] * 2,
                       "y": [0.0, 10.0, 0.0, 30.0]})  # fmt: skip
    t = Trellis(df, row="g", share_y="row", space="free_y", height=600).points(x="x", y="y")
    a, b = layout(t._scene()[0], 600).panels
    assert b.rect.h / a.rect.h == pytest.approx(3, rel=0.05)
    assert b.rect.y > a.rect.y + a.rect.h  # in order, apart
    assert figure_svg(t, width=600).startswith("<svg")


def test_space_is_checked_against_the_sharing_and_the_wrap() -> None:
    cars = load("cars")
    with pytest.raises(ValueError, match="share_x='col'"):
        Trellis(cars, col="origin", space="free_x").points(x="weight", y="mpg")._scene()
    with pytest.raises(ValueError, match="one row"):
        Trellis(cars, wrap="origin", cols=2, share_x=False,
                space="free_x").points(x="weight", y="mpg")._scene()  # fmt: skip
    with pytest.raises(ValueError, match="space must be"):
        Trellis(cars, space="wide")
    t = Trellis(cars, col="origin", share_x="col", space="free_x").points(x="weight", y="mpg")
    shares = next(s for sec in t._scene()[0]["settings"] for s in sec["settings"]
                  if s["name"] == "share_x")  # fmt: skip
    assert [o[0] for o in shares["options"]] == [False, "col"]
    assert 'space="free_x"' in t.code()


# ---- repeat ----------------------------------------------------------------------------------


def test_repeat_stacks_a_row_of_panels_per_column() -> None:
    weather = load("seattle_weather")
    t = Trellis(weather, repeat=["wind", "temp_max"],
                labels={"temp_max": "High (°C)"}).line(x="date", y="value")  # fmt: skip
    spec, _ = t._scene()
    assert spec["grid"]["rows"] == 2
    assert spec["grid"]["row_labels"] == ["wind", "High (°C)"]  # as given, by their labels
    assert t.share_y == "row"
    assert spec["y"]["title"] == ""
    wind, high = spec["panels"]
    assert wind["y"][1] < high["y"][1]  # each its own scale
    assert t.description.startswith("Lines of value against date, a row of panels per column")
    assert f"{weather.height:,} rows" in t.description
    assert 'repeat=["wind", "temp_max"], labels={"temp_max": "High (°C)"})' in t.code()
    assert "share_y" not in t.code()


def test_repeat_with_a_shared_scale_and_columns() -> None:
    weather = load("seattle_weather").with_columns(year=pl.col("date").dt.year())
    t = Trellis(weather, repeat=["temp_min", "temp_max"], col="year",
                share_y=True).line(x="date", y="value")  # fmt: skip
    spec, _ = t._scene()
    assert (spec["grid"]["rows"], spec["grid"]["cols"]) == (2, 4)
    assert len({tuple(p["y"]) for p in spec["panels"]}) == 1


def test_repeat_is_checked() -> None:
    weather = load("seattle_weather")
    with pytest.raises(ValueError, match="not columns"):
        Trellis(weather, repeat=["wind", "gust"])
    with pytest.raises(ValueError, match="number columns"):
        Trellis(weather, repeat=["wind", "weather"])
    with pytest.raises(ValueError, match="row= or wrap="):
        Trellis(weather, repeat=["wind"], row="weather")
    with pytest.raises(ValueError, match="rename"):
        Trellis(weather.with_columns(value=pl.lit(1.0)), repeat=["wind", "temp_max"])


def test_repeat_of_a_dict_of_arrays() -> None:
    data = {"t": np.arange(4.0), "a": np.arange(4.0), "b": np.arange(4.0) * 10}
    spec, _ = Trellis(data, repeat=["a", "b"]).line(x="t", y="value")._scene()
    assert [p["y"][1] >= 3 for p in spec["panels"]] == [True, True]
    assert spec["panels"][1]["y"][1] >= 30


def test_repeat_from_a_database_selects_as_memory_does() -> None:
    df = readings(3000, stations=6).filter(pl.col("station").is_not_null())
    rel = duckdb.from_arrow(df.to_arrow())
    paged = Trellis(rel, repeat=["v", "w"], page="station", load="pages").points(x="t", y="value")
    memory = Trellis(df, repeat=["v", "w"], page="station").points(x="t", y="value")

    def chosen(t: Trellis) -> set[tuple[int, str]]:
        t._scene()
        t.select(x=(2.0, 4.0), y=(0.5, 1.5))
        got = nw.from_native(t.selected())
        if isinstance(got, nw.LazyFrame):
            got = got.collect()
        return set(zip(got["id"].to_list(), got["measure"].to_list(), strict=True))

    got = chosen(paged)
    assert got
    assert {m for _, m in got} == {"v", "w"}
    assert got == chosen(memory)
