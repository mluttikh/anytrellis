"""Banking to 45 degrees: ``aspect="bank"`` shapes the panels for the lines' slopes."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.plot import BANK_LIMITS, banked_aspect


def aspect(t: Trellis) -> float:
    spec, _ = t._scene()
    return spec["aspect"]


def test_a_rise_across_the_panel_is_square() -> None:
    assert aspect(Trellis({"t": [0.0, 1.0], "v": [0.0, 1.0]}, aspect="bank")
                  .line(x="t", y="v")) == pytest.approx(1.0)  # fmt: skip


def test_steep_segments_make_wide_panels() -> None:
    # each segment rises the whole height (1.08 padded) in a tenth of the width (10.8)
    data = {"t": np.arange(11.0), "v": np.arange(11.0) % 2}
    assert aspect(Trellis(data, aspect="bank").line(x="t", y="v")) == pytest.approx(0.1)


def test_the_median_slope_of_every_panel_and_series() -> None:
    data = pl.DataFrame({
        "g": ["a"] * 3 + ["b"] * 3,
        "s": ["p", "p", "p", "q", "q", "q"],
        "t": [0.0, 1.0, 2.0] * 2,
        "v": [0.0, 1.0, 2.0, 0.0, 0.5, 1.0],
    })  # fmt: skip
    # free y: each panel's line rises its whole height
    t = Trellis(data, wrap="g", share_y=False, aspect="bank").line(x="t", y="v")
    assert aspect(t) == pytest.approx(1.0)
    # shared y: b rises half as much as a, so the median of 1, 1, 0.5, 0.5 is 0.75
    t = Trellis(data, wrap="g", aspect="bank").line(x="t", y="v", color="s")
    assert aspect(t) == pytest.approx(1 / 0.75)


def test_flat_and_vertical_segments_are_left_out() -> None:
    data = {"t": [0.0, 1.0, 1.0, 2.0, 3.0], "v": [0.0, 0.0, 1.0, 1.0, 2.0]}
    # only 2 -> 3 rises and runs: 1 of y's 2.16 (padded) over 1 of x's 3.24
    assert aspect(Trellis(data, aspect="bank").line(x="t", y="v")) == pytest.approx(2.16 / 3.24)


def test_limits() -> None:
    assert banked_aspect(np.array([1000.0])) == BANK_LIMITS[0]
    assert banked_aspect(np.array([0.001])) == BANK_LIMITS[1]
    assert banked_aspect(np.zeros(0)) == pytest.approx(0.62)


def test_a_smooth_is_banked_without_lines() -> None:
    x = np.linspace(0, 10, 200)
    data = pl.DataFrame({"g": np.repeat(["a", "b"], 100), "t": x,
                         "v": np.r_[x[:100], x[100:] * 3]})  # fmt: skip
    t = Trellis(data, wrap="g", share_y=False, share_x=False, aspect="bank")
    t.smooth(x="t", y="v", method="linear", se=False)
    assert aspect(t) == pytest.approx(1.0, rel=0.01)  # each fit rises its whole panel


def test_a_smooth_is_banked_before_the_noisy_line() -> None:
    x = np.linspace(0, 10, 200)
    noisy = {"t": x, "v": x + np.where(np.arange(200) % 2, 1.0, -1.0)}
    alone = aspect(Trellis(noisy, aspect="bank").line(x="t", y="v"))
    t = Trellis(noisy, aspect="bank").line(x="t", y="v")
    t.smooth(x="t", y="v", method="linear", se=False)
    assert alone < 0.05  # the noise's steep segments
    assert aspect(t) > 0.5  # the trend's


def test_a_number_or_bank() -> None:
    with pytest.raises(ValueError, match="aspect"):
        Trellis({"t": [0.0]}, aspect="square")
    with pytest.raises(ValueError, match="aspect"):
        Trellis({"t": [0.0]}, aspect=0)
    with pytest.raises(ValueError, match="line"):
        aspect(Trellis({"t": [0.0, 1.0], "v": [0.0, 1.0]}, aspect="bank").points(x="t", y="v"))


def test_pages_keep_their_shape() -> None:
    from anytrellis.synthetic import sensors

    frame = pl.DataFrame(sensors(stations=120, sensors=1, hours=24))
    t = Trellis(frame.lazy(), wrap="station", load="pages", aspect="bank")
    t.line(x="time", y="temp")
    first = aspect(t)
    t.show_page(3)
    assert aspect(t) == first
