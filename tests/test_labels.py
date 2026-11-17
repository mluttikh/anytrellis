"""Labelling a plot: ``subtitle=`` and ``caption=`` round the plot (in the page and its
images), and ``labels=`` naming columns wherever a column's name is shown, while code goes
on naming them as they are."""

from __future__ import annotations

import re

import pytest

import anytrellis as at
from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.figure import figure_svg, wrap_text
from anytrellis.synthetic import sensors

LABELS = {"mpg": "Fuel use (mpg)", "weight": "Weight (lb)", "origin": "Region"}


@pytest.fixture(scope="module")
def cars():
    return load("cars")


def texts(svg: str) -> list[str]:
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


def test_labels_name_the_axes_and_the_legend(cars) -> None:
    t = Trellis(cars, wrap="cylinders", labels=LABELS).points(x="weight", y="mpg", color="origin")
    spec, _ = t._shown_scene()
    assert spec["x"]["title"] == "Weight (lb)"
    assert spec["y"]["title"] == "Fuel use (mpg)"
    legend = spec["legends"][0]
    assert (legend["title"], legend["name"]) == ("Region", "origin")
    svg = texts(figure_svg(t))
    assert {"Weight (lb)", "↑ Fuel use (mpg)", "Region"} <= set(svg)
    # code names columns as they are
    t.select(color="Europe")
    assert t._legend_out(t._current_selection() or {}) == ("origin", ["Europe"])


def test_a_title_given_wins_over_a_label(cars) -> None:
    t = Trellis(cars, labels=LABELS, x_title="Mass").points(x="weight", y="mpg")
    spec, _ = t._shown_scene()
    assert (spec["x"]["title"], spec["y"]["title"]) == ("Mass", "Fuel use (mpg)")


def test_tooltips_show_labels(cars) -> None:
    t = Trellis(cars, labels={"name": "Model", "horsepower": "Power (hp)"})
    t.points(x="weight", y="mpg", tooltip=["name", "horsepower"])
    t._shown_scene()
    assert [n for n, _ in t._tooltip(0, 0)] == ["Model", "Power (hp)"]
    box = Trellis(cars, labels={"mpg": "Fuel use (mpg)"}).box(x="origin", y="mpg")
    spec, _ = box._shown_scene()
    names = [n for lr in spec["layers"] if lr.get("tips") for n in lr["tips"]["names"]]
    assert names
    assert "mpg" not in names


def test_the_sort_menu_shows_labels_and_sorting_takes_names() -> None:
    t = Trellis(sensors(stations=12, hours=48), wrap="station", rows=1, cols=4,
                labels={"temp": "Temperature (°C)"}).line(x="time", y="temp")  # fmt: skip
    spec, _ = t._shown_scene()
    stats = {s["name"]: s["label"] for s in spec["pages"]["stats"]}
    assert stats["rows"] == "rows"
    assert stats["mean temp"] == "mean Temperature (°C)"
    t.sort_panels("mean temp")
    assert list(t.stats())[2] == "mean temp"


def test_a_page_columns_title_is_its_label() -> None:
    df = sensors(stations=4, hours=24)
    t = Trellis(df, wrap="sensor", page="station", labels={"station": "Station"})
    t.line(x="time", y="temp")
    assert t._shown_scene()[0]["pages"]["title"] == "Station"


def test_labels_must_be_strings() -> None:
    with pytest.raises(TypeError, match="labels must be a dict"):
        Trellis(labels=["mpg"])  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="labels: column names and labels are strings"):
        Trellis(labels={"mpg": 3})  # ty: ignore[invalid-argument-type]


def test_subtitle_and_caption_are_in_the_spec_and_the_image(cars) -> None:
    plain = Trellis(cars, wrap="origin", title="Cars").points(x="weight", y="mpg")
    t = Trellis(cars, wrap="origin", title="Cars", subtitle="Miles per gallon by weight",
                caption="Source: UCI").points(x="weight", y="mpg")  # fmt: skip
    spec, _ = t._shown_scene()
    assert (spec["subtitle"], spec["caption"]) == ("Miles per gallon by weight", "Source: UCI")
    svg = figure_svg(t, width=800)
    assert {"Cars", "Miles per gallon by weight", "Source: UCI"} <= set(texts(svg))

    def height(s: str) -> float:
        m = re.search(r'height="([\d.]+)"', s)
        assert m is not None
        return float(m.group(1))

    assert height(svg) > height(figure_svg(plain, width=800)) + 30
    # under the plot: the caption is the lowest text
    ys = [float(y) for y in re.findall(r'<text x="[\d.]+" y="([\d.]+)"', svg)]
    caption = re.search(r'y="([\d.]+)"[^>]*>Source: UCI<', svg)
    assert caption is not None
    assert float(caption.group(1)) == max(ys)
    # a given height: the subtitle and the caption take their room from the plot
    assert height(figure_svg(t, width=800, height=500)) == 500


def test_a_long_subtitle_wraps() -> None:
    lines = wrap_text("one two three four five six seven eight nine ten", 80)
    assert len(lines) > 1
    assert " ".join(lines) == "one two three four five six seven eight nine ten"
    assert wrap_text("first\nsecond", 500) == ["first", "second"]


def test_pairs_label_their_strips_not_their_panels() -> None:
    penguins = load("penguins")
    names = {"bill_length_mm": "Bill length (mm)", "bill_depth_mm": "Bill depth (mm)"}
    p = at.pairs(penguins, list(names), labels=names, caption="Palmer penguins")
    spec, _ = p._shown_scene()
    assert spec["grid"]["col_labels"] == list(names.values())
    assert spec["caption"] == "Palmer penguins"
    assert "bill_depth_mm · bill_length_mm" in p.panels()
    assert "Bill length (mm)" in texts(figure_svg(p))
