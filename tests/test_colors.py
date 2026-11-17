"""Colour scales: ``colormap()`` picks a number column's colormap and how its values take
it (linear, diverging around a midpoint, binned in round steps, quantile), and
``palette=`` names a category palette or gives categories their own colours."""

from __future__ import annotations

import re

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.figure import figure_svg
from anytrellis.styling import COLORMAPS, PALETTES, NumberScale, colormap_rgba, hex_of, ramp_rgba


@pytest.fixture(scope="module")
def cars():
    return load("cars")


def legend(t: Trellis, index: int = 0) -> dict:
    spec, _ = t._shown_scene()
    return spec["legends"][index]


# ---- colormaps --------------------------------------------------------------------------------


def test_the_colormaps_named_in_the_design_review_are_built_in() -> None:
    for name in ("viridis", "cividis", "magma", "Blues", "RdBu", "PuOr"):
        assert name in COLORMAPS
        assert f"{name}_r" in COLORMAPS
        assert COLORMAPS[f"{name}_r"] == COLORMAPS[name][::-1]
    assert "okabe-ito" in PALETTES
    assert len(PALETTES["okabe-ito"]) == 8


def test_a_colormap_runs_low_to_high_and_missing_values_are_grey() -> None:
    out = colormap_rgba(np.array([0.0, 1.0, np.nan]), "viridis", 0, 1)
    assert hex_of(out[0]) == COLORMAPS["viridis"][0]
    assert hex_of(out[1]) == COLORMAPS["viridis"][-1]
    assert out[2].tolist() != out[0].tolist()
    # a list of colours is a colormap too
    two = ramp_rgba(np.array([0.0, 0.5, 1.0]), ["#000000", "#ffffff"])
    assert [hex_of(c) for c in two] == ["#000000", "#808080", "#ffffff"]


def test_a_colormap_is_chosen_by_name_or_given_as_colours(cars) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="horsepower")
    assert legend(t)["colors"] == COLORMAPS["viridis"]
    assert legend(t.colormap("cividis"))["colors"] == COLORMAPS["cividis"]
    assert legend(t.colormap(["#ffffff", "#ff0000"]))["colors"] == ["#ffffff", "#ff0000"]
    with pytest.raises(ValueError, match="unknown colormap 'jet'"):
        t.colormap("jet")
    with pytest.raises(ValueError, match="at least two"):
        t.colormap(["#ff0000"])
    with pytest.raises(ValueError, match="a colour scale is one of"):
        t.colormap(scale="log")
    with pytest.raises(ValueError, match="bins must be"):
        t.colormap(bins=1)


def test_settings_given_before_are_kept(cars) -> None:
    t = Trellis(cars).points(x="weight", y="mpg", color="horsepower")
    t.colormap("Blues").colormap(scale="binned").colormap(bins=8)
    assert t._number_scale == NumberScale(colormap="Blues", scale="binned", bins=8)


# ---- diverging --------------------------------------------------------------------------------


def test_a_diverging_scale_is_as_deep_on_both_sides_of_its_midpoint() -> None:
    s = NumberScale(scale="diverging", midpoint=10)
    t = s.positions(np.array([0.0, 10.0, 20.0, 15.0]), 0.0, 15.0, None)
    # the farther side (0, 10 below) reaches the end; 15 is as far above as 5 is below
    assert t.tolist() == [0.0, 0.5, 1.0, 0.75]
    middle = s.rgba(np.array([10.0]), 0.0, 15.0, None)[0]
    assert hex_of(middle) == "#f7f7f7"  # RdBu's light middle
    assert s.colors == COLORMAPS["RdBu_r"]  # red high


def test_a_diverging_legend_shows_the_colours_the_values_take(cars) -> None:
    t = (
        Trellis(cars)
        .points(x="weight", y="mpg", color="mpg")
        .colormap(scale="diverging", midpoint=float(cars["mpg"].min()))
    )
    lg = legend(t)
    # every value is above the midpoint: the legend runs from the middle to the red end
    assert lg["colors"][0] == "#f7f7f7"
    assert lg["colors"][-1] == COLORMAPS["RdBu_r"][-1]


# ---- stepped scales ---------------------------------------------------------------------------


def test_a_binned_scale_steps_in_round_widths(cars) -> None:
    t = Trellis(cars).points(x="weight", y="mpg", color="mpg").colormap(scale="binned", bins=4)
    lg = legend(t)
    assert lg["kind"] == "bins"
    assert lg["labels"] == ["0–10", "10–20", "20–30", "30–40", "40–50"]
    assert len(set(lg["colors"])) == len(lg["colors"])
    # a mark's colour is its bin's
    s = t._number_scale
    breaks = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    a, b = s.rgba(np.array([21.0, 29.0]), 9.0, 46.6, breaks)
    assert a.tolist() == b.tolist()


def test_bins_are_labelled_by_the_colour_format(cars) -> None:
    t = Trellis(cars).points(x="weight", y="mpg", color="weight")
    t.colormap(scale="binned", bins=4).format(color=",.0f")
    assert legend(t)["labels"][0] == "1,000–2,000"
    assert "1,000–2,000" in re.findall(r"<text[^>]*>([^<]*)</text>", figure_svg(t))


def test_negative_bins_are_spaced() -> None:
    s = NumberScale(scale="binned", bins=4)
    lg = s.legend(-10.0, 10.0, s.breaks(-10.0, 10.0, None), None)
    assert lg["labels"][0] == "−10 – −5"
    assert lg["labels"][-1] == "5–10"


def test_a_quantile_scale_puts_as_many_values_in_each_step() -> None:
    values = np.arange(1000, dtype=np.float64) ** 2  # skewed
    s = NumberScale(scale="quantile", bins=4)
    breaks = s.breaks(values.min(), values.max(), values)
    assert breaks is not None
    assert len(breaks) == 5
    t = s.positions(values, values.min(), values.max(), breaks)
    counts = np.unique(t, return_counts=True)[1]
    assert counts.tolist() == [250, 250, 250, 250]


def test_a_quantile_scale_legend(cars) -> None:
    t = Trellis(cars).points(x="weight", y="mpg", color="horsepower")
    lg = legend(t.colormap("cividis", scale="quantile", bins=3))
    assert lg["kind"] == "bins"
    assert len(lg["labels"]) == 3


def test_a_stepped_legend_is_drawn_as_entries_in_images(cars) -> None:
    t = Trellis(cars).points(x="weight", y="mpg", color="mpg").colormap(scale="binned", bins=4)
    words = re.findall(r"<text[^>]*>([^<]*)</text>", figure_svg(t))
    assert "10–20" in words
    assert "40–50" in words


# ---- category palettes ------------------------------------------------------------------------


def test_a_named_palette(cars) -> None:
    t = Trellis(cars, palette="okabe-ito").points(x="weight", y="mpg", color="origin")
    assert legend(t)["colors"] == PALETTES["okabe-ito"][:3]


def test_categories_keep_the_colours_given_them(cars) -> None:
    t = Trellis(cars, palette={"USA": "#d62728"}).points(x="weight", y="mpg", color="origin")
    lg = legend(t)
    colors = dict(zip(lg["labels"], lg["colors"], strict=True))
    assert colors["USA"] == "#d62728"
    # the others take the theme's colours in order
    plain = legend(Trellis(cars).points(x="weight", y="mpg", color="origin"))
    assert [colors["Europe"], colors["Japan"]] == plain["colors"][:2]
    # in another plot without Europe, USA is still red
    us_japan = cars.filter(pl.col("origin") != "Europe")
    other = legend(Trellis(us_japan, palette={"USA": "#d62728"}).points(
        x="weight", y="mpg", color="origin"))  # fmt: skip
    assert dict(zip(other["labels"], other["colors"], strict=True))["USA"] == "#d62728"


def test_a_colour_given_a_category_isnt_used_for_another(cars) -> None:
    first = legend(Trellis(cars).points(x="weight", y="mpg", color="origin"))["colors"][0]
    t = Trellis(cars, palette={"USA": first}).points(x="weight", y="mpg", color="origin")
    lg = legend(t)
    assert lg["colors"].count(first) == 1


def test_a_palette_dict_is_checked(cars) -> None:
    with pytest.raises(ValueError, match="unknown colour 'not a colour'"):
        Trellis(cars, palette={"USA": "not a colour"})
    with pytest.raises(TypeError, match="needs a colour string"):
        Trellis(cars, palette={"USA": 3})  # ty: ignore[invalid-argument-type]
