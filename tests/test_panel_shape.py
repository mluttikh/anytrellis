"""Panels with a shape (``aspect=``, banked or a number) keep it in full screen and opened."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pytest

from anytrellis import Trellis
from anytrellis.figure import FOCUS_MAX, Rect, figure_svg, layout


def plot(aspect: float | Literal["bank"] | None, panel_height: int | None = None) -> Trellis:
    x = np.linspace(0.0, 10.0, 50)
    data = {"g": np.repeat(list("abcd"), 50), "t": np.tile(x, 4), "v": np.tile(np.sin(x), 4)}
    t = Trellis(data, wrap="g", cols=2, aspect=aspect, panel_height=panel_height)
    return t.line(x="t", y="v")


def ratio(r: Rect) -> float:
    return r.h / r.w


def test_full_screen_narrows_and_centres_the_grid() -> None:
    spec, _ = plot(1.0)._scene()
    low = layout(spec, 800, 400)
    a, b = low.panels[0].rect, low.panels[1].rect
    assert ratio(a) == pytest.approx(1, abs=0.05)
    assert low.height <= 402
    left, right = low.panels[0].y_axis_x or 0, 800 - (b.x + b.w)
    assert right > 150
    assert abs(left - right) < 16


def test_full_screen_does_not_stretch_flat_panels() -> None:
    spec, _ = plot(0.2)._scene()
    assert layout(spec, 800, 1000).panels[0].rect == layout(spec, 800).panels[0].rect


def test_an_opened_panel_keeps_the_shape() -> None:
    spec, _ = plot(0.2)._scene()
    box = layout(spec, 800, 600, focused=0).panels[0]
    assert box.rect.w > 700
    assert ratio(box.rect) == pytest.approx(0.2, abs=0.01)
    spec, _ = plot(2.0)._scene()
    box = layout(spec, 800, FOCUS_MAX, focused=0).panels[0]
    assert ratio(box.rect) == pytest.approx(2, abs=0.05)
    assert box.rect.x > 200  # narrowed, centred


def test_the_image_of_an_opened_panel_keeps_the_banked_shape() -> None:
    t = plot("bank")
    spec, _ = t._scene()
    shaped = layout(spec, 800, FOCUS_MAX, focused=0)
    assert ratio(shaped.panels[0].rect) == pytest.approx(spec["aspect"], abs=0.01)
    t.open("a")
    svg = figure_svg(t, width=800)
    assert float(svg.split('height="', 1)[1].split('"', 1)[0]) == shaped.height


def test_not_kept_when_a_height_is_set() -> None:
    spec, _ = plot(1.0, panel_height=100)._scene()
    assert layout(spec, 800, 1000).panels[0].rect.h > 300


def test_without_a_shape_full_screen_fills_the_height() -> None:
    spec, _ = plot(None)._scene()
    assert abs(layout(spec, 800, 900).height - 900) < 4
