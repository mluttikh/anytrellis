"""The look (``Trellis(theme=)``): minimal by default, classic as before 0.6; the same in the
browser (drawing.ts, layout.ts) and in images drawn in Python (figure.py)."""

from __future__ import annotations

import re

import pytest

import anytrellis as at
from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.figure import GRID_ALPHA, THEMES, figure_svg, grid_axes, layout
from anytrellis.styling import PETROFF10, TAB10
from anytrellis.synthetic import sensors

LIGHT = THEMES["light"]


@pytest.fixture(scope="module")
def cars():
    return load("cars")


def lines(theme: str = "minimal", **kw) -> Trellis:
    return Trellis(sensors(stations=3, hours=48), wrap="station", theme=theme, **kw).line(
        x="time", y="temp", color="sensor"
    )


def test_minimal_is_the_default() -> None:
    plot = Trellis(sensors(stations=2, hours=24), wrap="station").line(x="time", y="temp")
    assert plot.theme == "minimal"
    spec, _ = plot._shown_scene()
    assert spec["theme"] == "minimal"


def test_an_unknown_theme_or_palette_is_refused() -> None:
    with pytest.raises(ValueError, match="theme must be one of"):
        Trellis(theme="dark")
    with pytest.raises(ValueError, match="unknown palette"):
        Trellis(palette="rainbow")
    with pytest.raises(ValueError, match="unknown colour"):
        Trellis(palette=["#123456", "not a colour"])


def test_each_look_has_its_palette() -> None:
    legend = lambda plot: plot._shown_scene()[0]["legends"][0]["colors"]  # noqa: E731
    assert legend(lines()) == PETROFF10[:3]
    assert legend(lines("classic")) == TAB10[:3]
    assert legend(lines(palette="tab10")) == TAB10[:3]
    assert legend(lines("classic", palette="petroff10")) == PETROFF10[:3]
    assert legend(lines(palette=["#000000", "#ffffff"])) == ["#000000", "#ffffff", "#000000"]


def test_minimal_panels_have_no_fill_and_a_faint_grid() -> None:
    svg = figure_svg(lines())
    assert f'fill="{LIGHT["panel"]}"' not in svg
    assert f'fill="{LIGHT["strip"]}"' not in svg
    assert f'stroke="{LIGHT["text"]}" stroke-opacity="{GRID_ALPHA}"' in svg
    classic = figure_svg(lines("classic"))
    assert f'fill="{LIGHT["panel"]}"' in classic
    assert f'fill="{LIGHT["strip"]}"' in classic


def test_the_grid_runs_across_y_and_across_x_for_points(cars) -> None:
    def axes(plot: Trellis) -> tuple[bool, bool]:
        return grid_axes(plot._shown_scene()[0])

    assert axes(lines()) == (False, True)
    assert axes(Trellis(cars, wrap="origin").points(x="weight", y="mpg")) == (True, True)
    assert axes(Trellis(cars, wrap="year").box(x="mpg", y="origin")) == (True, False)
    assert axes(lines("classic")) == (True, True)
    # only horizontal grid lines in the image: "H" paths, no "V"
    grid = re.findall(r'<path d="([^"]*)" fill="none" stroke="#1b2430" stroke-opacity',
                      figure_svg(lines()))  # fmt: skip
    assert grid
    assert all("V" not in d for d in grid)


def test_the_y_title_sits_over_the_plot() -> None:
    spec, _ = lines(y_title="Temperature (°C)")._shown_scene()
    lay = layout(spec, 800)
    assert lay.y_title is not None
    x, y = lay.y_title
    assert y < min(b.strip.y for b in lay.panels if b.strip is not None)
    assert x < min(b.rect.x for b in lay.panels)
    assert "↑ Temperature (°C)" in figure_svg(lines(y_title="Temperature (°C)"))
    classic, _ = lines("classic")._shown_scene()
    _, cy = layout(classic, 800).y_title or (0, 0)
    assert cy > 40  # on its side, halfway down


def test_times_have_no_x_title_unless_given() -> None:
    assert lines()._shown_scene()[0]["x"]["title"] == ""
    assert lines(x_title="hour")._shown_scene()[0]["x"]["title"] == "hour"
    assert lines("classic")._shown_scene()[0]["x"]["title"] == "time"


def test_a_grids_row_labels_are_level_and_fit(cars) -> None:
    for theme, vertical in (("minimal", False), ("classic", True)):
        plot = Trellis(cars, row="origin", col="cylinders", theme=theme)
        plot.points(x="weight", y="mpg")
        spec, _ = plot._shown_scene()
        rows = [s for s in layout(spec, 900).strips if s.side == "right"]
        assert [s.label for s in rows] == ["Europe", "Japan", "USA"]
        assert all(s.vertical == vertical for s in rows)
        assert "Europe" in figure_svg(plot)  # whole, not cut


def test_nested_strips_spanning_panels_are_marked() -> None:
    barley = load("barley")
    plot = Trellis(barley, row=["year", "site"], col="variety").points(x="yield", y="variety")
    spec, _ = plot._shown_scene()
    rows = [s for s in layout(spec, 1200).strips if s.side == "right"]
    assert {s.label for s in rows if s.span} == {"1931", "1932"}
    assert not any(s.span for s in rows if s.label not in ("1931", "1932"))


def test_pairs_take_a_theme() -> None:
    penguins = load("penguins")
    p = at.pairs(penguins, ["bill_length_mm", "bill_depth_mm"], theme="classic")
    assert p._shown_scene()[0]["theme"] == "classic"
    assert at.pairs(penguins, ["bill_length_mm", "bill_depth_mm"]).theme == "minimal"
