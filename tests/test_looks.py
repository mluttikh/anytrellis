"""The look (``Trellis(theme=)``, ``anytrellis.Theme``): minimal by default, framed, classic
as before 0.6, or any of their settings changed; the same in the browser (look.ts,
drawing.ts, layout.ts) and in images drawn in Python (figure.py)."""

from __future__ import annotations

import re
from typing import Any

import pytest

import anytrellis as at
from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.figure import THEMES, figure_svg, grid_axes, layout
from anytrellis.styling import PALETTES, PETROFF10, TAB10
from anytrellis.synthetic import sensors
from anytrellis.theme import Theme, get_theme, set_theme

LIGHT = THEMES["light"]


@pytest.fixture(scope="module")
def cars():
    return load("cars")


def lines(theme: str | Theme = "minimal", **kw) -> Trellis:
    return Trellis(sensors(stations=3, hours=48), wrap="station", theme=theme, **kw).line(
        x="time", y="temp", color="sensor"
    )


def test_minimal_is_the_default() -> None:
    plot = Trellis(sensors(stations=2, hours=24), wrap="station").line(x="time", y="temp")
    assert plot.theme == Theme("minimal")
    spec, _ = plot._shown_scene()
    assert spec["theme"]["base"] == "minimal"
    assert spec["theme"]["panel_gap"] == 6


def test_an_unknown_theme_or_palette_is_refused() -> None:
    with pytest.raises(ValueError, match="theme must be one of"):
        Trellis(theme="dark")
    with pytest.raises(ValueError, match="grid must be one of"):
        Theme(grid="diagonal")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="panel_gap"):
        Theme(panel_gap=-1)
    with pytest.raises(ValueError, match="grid_opacity"):
        Theme(grid_opacity=2)
    with pytest.raises(ValueError, match="frame must be True or False"):
        Theme(frame="yes")  # ty: ignore[invalid-argument-type]
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
    assert f'stroke="{LIGHT["text"]}" stroke-opacity="0.1"' in svg
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
    assert p._shown_scene()[0]["theme"]["base"] == "classic"
    assert at.pairs(penguins, ["bill_length_mm", "bill_depth_mm"]).theme.base == "minimal"


def test_a_theme_is_a_preset_with_settings_changed() -> None:
    t = Theme("minimal", frame=True, panel_gap=12)
    assert t.frame
    assert t.panel_gap == 12
    assert t.strip_align == "left"  # the rest: minimal's
    framed = Theme("framed")
    assert framed.frame
    assert framed.strip_align == "center"
    assert framed.colors() == PALETTES["observable10"]
    assert framed.replace(palette="tab10").colors() == TAB10
    assert Theme("classic", palette=[]).palette == "tab10"  # empty: the preset's


def test_framed_draws_a_frame_and_no_axis_lines() -> None:
    svg = figure_svg(lines("framed", x_title="hour"))
    frames = re.findall(r'<path d="([^"]*Z)" fill="none" stroke="#a3abb5"', svg)
    assert len(frames) == 1
    assert frames[0].count("Z") == 3  # a panel each
    assert "hour →" in svg  # the x title at its axis' end
    spec, _ = lines("framed")._shown_scene()
    tight, roomy = (layout(sp, 800) for sp in (lines()._shown_scene()[0], spec))
    gap = lambda lay: lay.panels[1].rect.x - lay.panels[0].rect.x - lay.panels[0].rect.w  # noqa: E731
    assert (gap(tight), gap(roomy)) == (6, 10)


def test_settings_change_what_is_drawn() -> None:
    plain = Theme("minimal", grid="none", axis_lines="none", strip_bold=False)
    svg = figure_svg(lines(plain))
    assert 'stroke-opacity="0.1"' not in svg  # no grid
    strip = re.search(r"<text [^>]*>station 1</text>", svg)
    assert strip is not None
    assert "font-weight" not in strip.group(0)  # strips not bold
    filled = figure_svg(lines(Theme("minimal", panel_fill=True, strip_fill=True)))
    assert f'fill="{LIGHT["panel"]}"' in filled
    assert f'fill="{LIGHT["strip"]}"' in filled
    side = lines(Theme("minimal", y_title="side"))._shown_scene()[0]
    assert layout(side, 800).y_title[1] > 60  # ty: ignore[not-subscriptable]


def test_set_theme_is_the_default_of_plots_made_after() -> None:
    try:
        set_theme("framed", panel_gap=14)
        assert get_theme() == Theme("framed", panel_gap=14)
        plot = Trellis(sensors(stations=2, hours=24), wrap="station")
        assert plot.theme.base == "framed"
        assert plot.theme.panel_gap == 14
        assert Trellis(theme="classic").theme.base == "classic"  # given: as given
    finally:
        set_theme()
    assert Trellis().theme == Theme()


def test_palette_overrides_the_themes() -> None:
    legend = lines(Theme("framed", palette="tab10"), palette="petroff6")
    assert legend._shown_scene()[0]["legends"][0]["colors"] == PALETTES["petroff6"][:3]


def test_font_size_and_context_resolve_to_pixels() -> None:
    default = Theme().spec()
    assert (default["font_size"], default["font_step"], default["mark_scale"]) == (12, True, 1)
    assert Theme("classic").spec()["font_step"] is False  # classic: 12 px, as before
    talk = Theme(context="talk").spec()
    assert (talk["font_size"], talk["font_step"], talk["mark_scale"]) == (18.0, True, 1.5)
    fixed = Theme(font_size=14, context="poster").spec()
    assert (fixed["font_size"], fixed["font_step"]) == (28.0, False)
    refused: list[tuple[str, Any]] = [("font_size", 3), ("font_size", "big"),
                                      ("font_size", True), ("context", "slides")]  # fmt: skip
    for name, value in refused:
        with pytest.raises(ValueError, match=name):
            Theme(**{name: value})


def test_auto_text_steps_with_the_panels_width() -> None:
    gap = load("gapminder")
    narrow = Trellis(gap, wrap="country", cols=8).line(x="year", y="life_expect", color="region")
    spec = narrow._shown_scene()[0]
    assert layout(spec, 900).font_size == 11  # panels under 160 px
    assert layout(spec, 1600).font_size == 12
    assert layout(spec, 900, focused=0).font_size == 13  # an opened panel
    classic = Trellis(gap, wrap="country", cols=8, theme="classic").line(x="year", y="life_expect")
    spec = classic._shown_scene()[0]
    assert {layout(spec, 900).font_size, layout(spec, 900, focused=0).font_size} == {12}
    svg = figure_svg(narrow, width=900)
    assert 'font-size="11"' in svg.split(">", 1)[0]  # the panels' text
    assert re.search(r'font-size="12"[^>]*>region<', svg)  # the legend: the page's text


def test_a_context_scales_text_lines_and_points(cars) -> None:
    def plot(theme: Theme) -> Trellis:
        return (Trellis(cars, wrap="origin", theme=theme, title="Fuel", caption="UCI")
                .points(x="weight", y="mpg").line(x="weight", y="mpg").rule(y=20)
                .text(x="weight", y="mpg", text="cylinders"))  # fmt: skip

    def sizes(t: Trellis) -> list[float]:
        return [lr.get("size") or lr.get("width") for lr in t._shown_scene()[0]["layers"]]

    assert sizes(plot(Theme(context="talk"))) == [k * 1.5 for k in sizes(plot(Theme()))]
    talk = plot(Theme(context="talk"))
    svg = figure_svg(talk, width=800)
    assert 'font-size="18"' in svg.split(">", 1)[0]  # wide panels: no step
    assert re.search(r'font-size="20.7"[^>]*>Fuel<', svg)  # the title, 1.15 times
    assert re.search(r'font-size="16.5"[^>]*>UCI<', svg)  # the caption, 11/12
    assert (
        layout(talk._shown_scene()[0], 800).height
        > layout(plot(Theme())._shown_scene()[0], 800).height
    )
    try:
        set_theme(context="paper")
        assert Trellis(cars).theme.spec()["font_size"] == pytest.approx(9.6)
    finally:
        set_theme()
