"""Formats, limits and the legend's place: ``format()`` writes axis values, tooltips and a
colour legend's ends by d3-format and strftime strings (formats.py, as format.ts and as d3
itself), ``limits()`` sets an axis's range, either end from the data, and ``legend()`` puts
the legend right of the plot, under it, or nowhere."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.figure import RIGHT_MOST, _legend_groups, figure_svg, layout, legend_width
from anytrellis.formats import number_format, time_format
from anytrellis.synthetic import sensors

D3 = json.loads((Path(__file__).parents[1] / "js" / "test" / "d3-formats.json").read_text())


@pytest.fixture(scope="module")
def cars():
    return load("cars")


def texts(svg: str) -> list[str]:
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


# ---- formats ----------------------------------------------------------------------------------


def test_numbers_are_written_as_d3_writes_them() -> None:
    wrong = [(spec, value, want, number_format(spec)(-0.0 if value == "-0" else value))
             for spec, value, want in D3["numbers"]]  # fmt: skip
    wrong = [w for w in wrong if w[2] != w[3]]
    assert not wrong, wrong[:5]
    assert len(D3["numbers"]) > 1000


def test_times_are_written_as_d3_utc_format_writes_them() -> None:
    wrong = [(s, t, want, time_format(s)(t)) for s, t, want in D3["times"]]
    assert not [w for w in wrong if w[2] != w[3]]


def test_halves_round_away_from_zero_as_in_javascript() -> None:
    assert number_format(".0f")(2.5) == "3"  # Python's format: "2"
    assert number_format(".0f")(-2.5) == "−3"
    assert number_format(",.2f")(-1234.5) == "−1,234.50"
    assert number_format(".2s")(1234) == "1.2k"
    assert number_format(".1%")(0.1234) == "12.3%"


def test_a_format_that_cannot_be_read_is_refused(cars) -> None:
    with pytest.raises(ValueError, match="invalid number format"):
        number_format(".2q")
    with pytest.raises(ValueError, match="invalid time format"):
        time_format("%Q")
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
    with pytest.raises(ValueError, match="neither a d3-format string"):
        t.format(x="%Q")
    with pytest.raises(ValueError, match="a colour legend's ends are numbers"):
        t.format(color="%b")


def test_axes_are_labelled_by_their_formats(cars) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg").format(x="$,.0f", y=".1f")
    spec, _ = t._shown_scene()
    assert (spec["x"]["format"], spec["y"]["format"]) == ("$,.0f", ".1f")
    words = texts(figure_svg(t))
    assert "$3,000" in words
    assert "20.0" in words
    t.format(x="")  # the automatic labels again
    assert t._shown_scene()[0]["x"]["format"] is None


def test_a_time_axis_takes_a_strftime_format() -> None:
    t = Trellis(sensors(stations=2, hours=24 * 60), wrap="station").line(x="time", y="temp")
    t.format(x="%-d %b")
    words = texts(figure_svg(t, width=900))
    assert any(re.fullmatch(r"\d{1,2} (Mar|Apr)", w) for w in words)
    with pytest.raises(ValueError, match="holds times"):
        t.format(x=",.0f")._shown_scene()


def test_a_format_must_fit_its_axis(cars) -> None:
    with pytest.raises(ValueError, match="holds numbers"):
        Trellis(cars).points(x="weight", y="mpg").format(y="%Y")._shown_scene()
    with pytest.raises(ValueError, match="holds categories"):
        Trellis(cars).box(x="origin", y="mpg").format(x=".1f")._shown_scene()


def test_a_colour_legends_ends_take_the_colour_format(cars) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="horsepower")
    t.format(color=".0f")
    spec, _ = t._shown_scene()
    assert spec["legends"][0]["format"] == ".0f"
    assert "230" in texts(figure_svg(t))


# ---- limits -----------------------------------------------------------------------------------


def test_limits_set_either_end_of_a_range(cars) -> None:
    t = Trellis(cars, wrap="origin", share_y=False).points(x="weight", y="mpg")
    t.limits(y=(0, None), x=(1000, 6000))
    spec, _ = t._shown_scene()
    for p in spec["panels"]:
        assert p["y"][0] == 0
        assert p["y"][1] > 30  # each panel's own top, from its data
        assert p["x"] == [1000, 6000]
    tops = {p["y"][1] for p in spec["panels"]}
    assert len(tops) > 1
    t.limits(y=(None, None))  # the data's range again
    assert t._shown_scene()[0]["panels"][0]["y"][0] > 0


def test_limits_of_times_and_logs() -> None:
    t = Trellis(sensors(stations=2, hours=48), wrap="station").line(x="time", y="temp")
    t.limits(x=("2026-03-01", "2026-03-04"))
    spec, _ = t._shown_scene()
    lo, hi = (v + spec["x"]["origin"] for v in spec["panels"][0]["x"])
    assert hi - lo == 3 * 86_400_000
    cars = load("cars")
    log = Trellis(cars, x_scale="log").points(x="weight", y="mpg").limits(x=(1000, 10000))
    assert log._shown_scene()[0]["panels"][0]["x"] == [3.0, 4.0]


def test_limits_that_cannot_be_are_refused(cars) -> None:
    t = Trellis(cars).points(x="weight", y="mpg")
    with pytest.raises(ValueError, match="low must be under high"):
        t.limits(y=(10, 5))
    with pytest.raises(ValueError, match=r"is \(low, high\)"):
        t.limits(y=5)  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="holds categories"):
        Trellis(cars).box(x="origin", y="mpg").limits(x=(0, 1))._shown_scene()


# ---- the legend -------------------------------------------------------------------------------


def test_a_legend_right_of_the_plot(cars) -> None:
    t = Trellis(cars, wrap="origin", cols=3).points(x="weight", y="mpg", color="cylinders")
    full = layout(t._shown_scene()[0], 900)
    t.legend("right", title="Cylinders")
    spec, _ = t._shown_scene()
    assert spec["legend_position"] == "right"
    assert spec["legends"][0]["title"] == "Cylinders"
    svg = figure_svg(t, width=900)
    title = re.search(r'<text x="([\d.]+)"[^>]*>Cylinders</text>', svg)
    assert title is not None
    lw = legend_width(_legend_groups(spec, None), 900 * RIGHT_MOST)
    narrowed = layout(spec, 900 - lw)
    edge = max(b.rect.x + b.rect.w for b in narrowed.panels)
    assert edge < max(b.rect.x + b.rect.w for b in full.panels)  # narrowed to make room
    assert float(title.group(1)) > edge  # the legend right of the panels


def test_no_legend(cars) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="cylinders")
    with_legend = figure_svg(t)
    t.legend("none")
    assert "cylinders" in texts(with_legend)
    assert "cylinders" not in texts(figure_svg(t))
    with pytest.raises(ValueError, match="legend must be one of"):
        t.legend("left")


def test_legend_titles_by_column(cars) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="origin")
    t.legend(title={"origin": "Made in"})
    assert t._shown_scene()[0]["legends"][0]["title"] == "Made in"
    # code still names the column
    t.select(color="Japan")
    assert t._legend_out(t._current_selection() or {}) == ("origin", ["Japan"])
