"""Images drawn in Python (``save_svg``, ``save_png``): the plot as shown, without a browser.

The ticks, layout and selection are ports of the browser's; these tests check what the
image holds. (Their agreement with the TypeScript, case by case, was checked when they were
ported: same ticks for random ranges of every axis kind, same layouts, same selections.)
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

import anytrellis as at
from anytrellis import Trellis
from anytrellis.figure import (
    DAY,
    FADED,
    THEMES,
    figure_svg,
    fit,
    format_number,
    text_width,
    ticks,
)
from anytrellis.synthetic import sales, sensors

NS = "{http://www.w3.org/2000/svg}"


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def texts(svg: str) -> list[str]:
    return [e.text or "" for e in parse(svg).iter(f"{NS}text")]


def size(svg: str) -> tuple[float, float]:
    root = parse(svg)
    return float(root.get("width", 0)), float(root.get("height", 0))


def opacities(svg: str) -> set[str]:
    return set(re.findall(r'(?:stroke|fill)-opacity="([\d.]+)"', svg))


@pytest.fixture
def temps() -> Trellis:
    return Trellis(sensors(stations=4, hours=24 * 7), wrap="station", title="Temperatures"
                   ).line(x="time", y="temp", color="sensor")  # fmt: skip


def test_an_svg_of_the_plot(temps: Trellis, tmp_path: Path) -> None:
    path = temps.save_svg(tmp_path / "temps.svg")
    svg = path.read_text(encoding="utf-8")
    words = texts(svg)
    assert "Temperatures" in words  # the title
    assert {f"station {i}" for i in range(1, 5)} <= set(words)  # the strips
    assert {"sensor", "s1", "s2", "s3"} <= set(words)  # the legend
    assert {"time", "temp"} <= set(words)  # the axis titles
    assert any(re.fullmatch(r"Mar \d+", w) for w in words)  # time ticks
    assert len(parse(svg).findall(f".//{NS}path")) > 4 * 3  # marks, gridlines, axes
    # colours every SVG reader takes: #rrggbb and an opacity, no rgba()
    assert "rgba(" not in svg
    assert not re.search(r'"#[0-9a-f]{8}"', svg)


def test_the_size_is_the_shown_width_else_800(temps: Trellis) -> None:
    assert size(figure_svg(temps))[0] == 800
    assert size(figure_svg(temps, width=1200))[0] == 1200
    width, height = size(figure_svg(temps, width=600, height=500))
    assert (width, height) == (600, 500)
    # wider: the panels, and so the plot, grow
    assert size(figure_svg(temps, width=1200))[1] > size(figure_svg(temps, width=600))[1]


def test_the_view_the_browser_reports_is_drawn(temps: Trellis) -> None:
    w = temps.widget
    spec = temps._scene()[0]
    x0 = spec["panels"][0]["x"][0]
    # zoomed into one day (x is in ms relative to the origin), 700 px wide
    view = {"type": "view", "width": 700, "x": [[0, [x0 + 2 * DAY, x0 + 3 * DAY]]],
            "y": [[0, [5.0, 6.0]]]}  # fmt: skip
    w._on_msg(w, view, [])
    svg = figure_svg(temps)
    assert size(svg)[0] == 700
    words = texts(svg)
    assert any(re.fullmatch(r"\d\d:00", s) for s in words)  # hours: zoomed in
    assert "5.0" in words  # and y too


def test_a_selection_fades_the_other_marks(temps: Trellis) -> None:
    plain = figure_svg(temps)
    temps.select(color="s2")
    chosen = figure_svg(temps)
    assert str(FADED) in opacities(chosen)
    assert str(FADED) not in opacities(plain)
    # a brush is drawn
    temps.select(x=("2026-03-02", "2026-03-03"))
    assert 'stroke-opacity="0.8"' in figure_svg(temps)


def test_a_linked_plot_shows_what_the_other_selects() -> None:
    data = sensors(stations=2, hours=48)
    lines = Trellis(data, wrap="station").line(x="time", y="temp", color="sensor")
    counts = Trellis(data).hist(x="temp")
    at.link(lines, counts)
    lines.select(color="s1")
    assert str(FADED) in opacities(figure_svg(counts))


def test_an_opened_panel_alone(temps: Trellis) -> None:
    temps.open("station 2")
    words = texts(figure_svg(temps))
    assert "station 2" in words
    assert "station 1" not in words
    temps.close()
    assert "station 1" in texts(figure_svg(temps))


def test_themes(temps: Trellis) -> None:
    for name, theme in THEMES.items():
        background = parse(figure_svg(temps, theme=name)).find(f"{NS}rect")
        assert background is not None
        assert background.get("fill") == theme["bg"]
    with pytest.raises(ValueError, match="theme"):
        figure_svg(temps, theme="blue")


def test_too_small_an_image_is_refused(temps: Trellis) -> None:
    with pytest.raises(ValueError, match="width"):
        figure_svg(temps, width=50)
    with pytest.raises(ValueError, match="height"):
        figure_svg(temps, height=40)


def test_categories_logs_bars_and_labels() -> None:
    data = sales()
    bars = Trellis(data, wrap="store").bars(x="month", y="units", color="product")
    words = texts(figure_svg(bars, width=1000))
    assert {"Jan", "Jun", "Amsterdam", "Oslo"} <= set(words)
    pts = {"x": np.array([1.0, 10, 100, 1e4]), "y": np.array([1.0, 2, 3, 4]),
           "name": np.array(["a", "b", "c", "d"])}  # fmt: skip
    logged = Trellis(pts, x_scale="log").points(x="x", y="y").text(x="x", y="y", text="name")
    words = texts(figure_svg(logged))
    assert {"1", "100", "10000"} <= set(words)
    assert {"a", "b", "c", "d"} <= set(words)


def test_x_labels_of_neighbouring_panels_do_not_run_together() -> None:
    # a month of hours: ticks at Mar 1 and Apr 1, each at a panel's edge
    data = sensors(stations=3, hours=24 * 31)
    t = Trellis(data, wrap="station", cols=3).line(x="time", y="temp")
    words = texts(figure_svg(t, width=700))
    # the first two panels leave out the label at their right edge (the next panel's
    # first is there); the last keeps it
    assert words.count("Apr") == 1
    assert words.count("Mar") == 3


def test_ticks_as_the_browser_writes_them() -> None:
    assert [t[1] for t in ticks("number", -2, 2, 0, 4)] == ["−2", "−1", "0", "1", "2"]
    assert [t[1] for t in ticks("number", 0, 2e6, 0, 4)] == ["0", "500k", "1.0M", "1.5M", "2.0M"]
    assert format_number(0.30000000000000004, 0.1, 1) == "0.3"
    assert format_number(2.5, 1, 0) == "3"  # halves away from zero, as toFixed
    # weeks start on Mondays; months by name, years by number
    week = [t[1] for t in ticks("time", 0, 30 * DAY, 0, 5)]
    assert week[0] == "Jan 5"  # 1970-01-05 was a Monday
    months = [t[1] for t in ticks("time", 0, 400 * DAY, 0, 6)]
    assert months == ["1970", "Apr", "Jul", "Oct", "1971"]  # quarters
    assert [t[1] for t in ticks("log", 0, 4, 0, 5)] == ["1", "10", "100", "1000", "10000"]
    assert [t[1] for t in ticks("band", -0.5, 2.5, 0, 10, ["a", "b", "c"])] == ["a", "b", "c"]


def test_text_is_measured_and_fitted() -> None:
    assert text_width("iii") < text_width("mmm")
    assert text_width("ab", 24) == 2 * text_width("ab", 12)
    assert fit("short", 100) == "short"
    cut = fit("a rather long panel name", 60)
    assert cut.endswith("…")
    assert text_width(cut) <= 60


def test_a_png(temps: Trellis, tmp_path: Path) -> None:
    pytest.importorskip("resvg_py")
    path = temps.save_png(tmp_path / "temps.png", width=600, scale=2)
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    svg_w, svg_h = size(figure_svg(temps, width=600))
    assert (width, height) == (round(svg_w * 2), round(svg_h * 2))
    with pytest.raises(ValueError, match="scale"):
        temps.save_png(tmp_path / "x.png", scale=0)


def test_a_png_without_resvg_says_how_to_get_it(
    temps: Trellis, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "resvg_py", None)
    with pytest.raises(ImportError, match=r"anytrellis\[png\]"):
        temps.save_png(tmp_path / "temps.png")
