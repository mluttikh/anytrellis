"""Accessibility: a description made from what the plot shows (``description``, ``alt=``),
in the spec, the browser's label and saved images; and ``redundant=``, the colour column
also as points' shapes and lines' dashes."""

from __future__ import annotations

from collections.abc import Callable

import duckdb
import numpy as np
import polars as pl
import pytest

import anytrellis as at
from anytrellis import Theme, Trellis
from anytrellis.datasets import load
from anytrellis.figure import figure_svg


def test_a_scatter_described() -> None:
    t = Trellis(load("cars"), wrap="origin").points(x="weight", y="mpg", color="cylinders")
    assert t.description == (
        "Scatter of mpg against weight, one panel per origin (3), coloured by cylinders. "
        "406 rows. mpg from 9 to 46.6; weight from 1613 to 5140."
    )
    assert t._scene()[0]["description"] == t.description


@pytest.mark.parametrize(
    ("make", "says"),
    [
        (lambda: Trellis(load("barley"), wrap="site").bars(x="yield", y="variety"),
         ["Bars of yield by variety", "variety: Glabron, Manchuria", "and 5 more"]),
        (lambda: Trellis(load("penguins"), row="sex", col="island").hist(x="body_mass_g"),
         ["Histogram of body_mass_g", "panels by sex (3 rows) and island (3 columns)"]),
        (lambda: Trellis(load("seattle_weather"), wrap="weather").line(x="date", y="temp_max"),
         ["Lines of temp_max against date", "date from 2012-01-01 to 2015-12-31"]),
        (lambda: Trellis(load("gapminder"), wrap="country", rows=2, cols=4)
         .line(x="year", y="life_expect").points(x="year", y="life_expect"),
         ["Lines and points of", "(63), 8 a page", "year from 1955 to 2005"]),
        (lambda: Trellis(load("cars"), labels={"mpg": "fuel use"}).points(x="weight", y="mpg",
                                                                          size="horsepower"),
         ["Scatter of fuel use against weight, sized by horsepower.", "fuel use from 9"]),
        (lambda: Trellis(load("cars")).points(x="weight", y="mpg").scale(y="log"),
         ["mpg from 9 to 46.6"]),  # the scale undone
        (lambda: Trellis(load("cars")).box(x="origin", y="mpg"),
         ["Box plots of mpg by origin.", "origin: Europe, Japan, USA"]),
    ],
)  # fmt: skip
def test_descriptions_of_other_plots(make: Callable[[], Trellis], says: list[str]) -> None:
    text = make().description
    for part in says:
        assert part in text, text


def test_alt_replaces_it_and_saved_images_carry_it() -> None:
    t = Trellis(load("cars"), wrap="origin", title="Fuel use",
                alt="Heavier cars use more fuel.").points(x="weight", y="mpg")  # fmt: skip
    assert t.description == "Heavier cars use more fuel."
    svg = figure_svg(t, width=600)
    assert 'role="img"><title>Fuel use</title><desc>Heavier cars use more fuel.</desc>' in svg
    plain = figure_svg(Trellis(load("cars")).points(x="weight", y="mpg"), width=400)
    assert "<title>Scatter of mpg against weight. 406 rows." in plain
    assert "<desc>" not in plain  # no title: the description is it
    assert '"description": "Heavier cars use more fuel."' in t._embed_html()


def test_from_a_database_counted_not_read() -> None:
    frame = pl.DataFrame({"g": np.repeat(["a", "b", "c", "d"], 50), "x": np.arange(200.0),  # noqa: F841
                          "y": np.arange(200.0) % 7})  # fmt: skip
    t = Trellis(duckdb.sql("select * from frame"), wrap="g", rows=1, cols=2,
                load="pages").points(x="x", y="y")  # fmt: skip
    text = t.description
    assert "one panel per g (4), 2 a page. 200 rows." in text
    assert t._data is not None
    assert t._data._n is None  # counted in the database


def test_redundant_shapes_points_and_dashes_lines_by_their_colour() -> None:
    t = Trellis(load("penguins"), wrap="island", redundant=True)
    t.points(x="bill_length_mm", y="bill_depth_mm", color="species")
    t.line(x="bill_length_mm", y="bill_depth_mm", color="sex")
    spec, _ = t._scene()
    points, line = spec["layers"][0], spec["layers"][1]
    assert points["marker"]["shapes"] is not None
    assert line["dash"]["codes"] is not None
    legend = next(lg for lg in spec["legends"] if lg["name"] == "species")
    assert legend["shapes"] == [0, 1, 2]  # one legend shows both
    assert "coloured and shaped by species" in t.description
    assert "coloured and dashed by sex" in t.description
    assert figure_svg(t, width=700).count("<path") > 0


def test_redundant_leaves_what_it_cannot_or_was_given() -> None:
    t = Trellis(load("cars"), redundant=True)
    t.points(x="weight", y="mpg", color="horsepower")  # numbers: the colormap alone
    t.points(x="weight", y="mpg", color="origin", shape="square")  # given: kept
    t.line(x="weight", y="mpg", color="origin", dash=(4, 3))  # one dash given: kept
    t.points(x="weight", y="mpg", color="#888888")  # one colour
    spec, _ = t._scene()
    assert spec["layers"][0]["marker"] is None
    assert spec["layers"][1]["marker"]["shape"] == 1  # square, for every point
    assert spec["layers"][1]["marker"]["shapes"] is None
    assert spec["layers"][2]["dash"]["codes"] is None
    assert spec["layers"][3]["marker"] is None
    plain = Trellis(load("cars")).points(x="weight", y="mpg", color="origin")
    assert plain._scene()[0]["layers"][0]["marker"] is None  # off unless asked


def test_redundant_from_the_theme() -> None:
    try:
        at.set_theme(redundant=True)
        t = Trellis(load("cars")).points(x="weight", y="mpg", color="origin")
        assert t.redundant
        assert t._scene()[0]["layers"][0]["marker"]["shapes"] is not None
        assert not Trellis(load("cars"), redundant=False).redundant
    finally:
        at.set_theme()
    assert Theme().redundant is False
    assert "redundant" not in Theme(redundant=True).spec()  # drawn in Python
    with pytest.raises(ValueError, match="redundant must be True or False"):
        Theme(redundant="yes")  # ty: ignore[invalid-argument-type]
