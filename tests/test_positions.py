"""Bars along y (a category y), stacks filled to 1 (``position="fill"``), points jittered
across a category's band, and rules from a table, a line per panel."""

from __future__ import annotations

import re

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.figure import figure_svg
from anytrellis.layers import Geometry, _stack, jittered


@pytest.fixture(scope="module")
def barley():
    return load("barley")


@pytest.fixture(scope="module")
def penguins():
    return load("penguins").drop_nulls()


def built(t: Trellis) -> tuple[dict, list[Geometry]]:
    spec, _ = t._shown_scene()
    return spec, [g for _, _, g in t._geometry if g is not None]


# ---- bars along y -----------------------------------------------------------------------------


def test_a_category_y_turns_the_bars(barley) -> None:
    morris = barley.filter(pl.col("site") == "Morris", pl.col("year") == 1931)
    spec, (geom,) = built(Trellis(morris).bars(x="yield", y="variety"))
    assert spec["y"]["kind"] == "band"
    assert spec["x"]["kind"] == "number"
    # from 0 to the value along x, a band's 0.8 across y
    assert np.all(geom.x0 == 0)
    assert np.allclose(np.sort(geom.x1), np.sort(morris["yield"].to_numpy()))
    assert np.allclose(geom.y1 - geom.y0, 0.8)
    # x starts at 0, unpadded, as y does for upright bars
    assert spec["panels"][0]["x"][0] == 0.0


def test_bars_along_y_stack_and_dodge(barley) -> None:
    morris = barley.filter(pl.col("site") == "Morris")
    t = Trellis(morris).as_category("year").bars(x="yield", y="variety", color="year")
    _, (geom,) = built(t)
    totals = morris.group_by("variety").agg(pl.col("yield").sum())
    assert np.isclose(geom.x1.max(), totals["yield"].max())
    dodged = Trellis(morris).as_category("year")
    _, (geom,) = built(dodged.bars(x="yield", y="variety", color="year", position="dodge"))
    assert np.all(geom.x0 == 0)
    assert np.allclose(geom.y1 - geom.y0, 0.4)


def test_bars_along_y_have_no_log_x(barley) -> None:
    t = Trellis(barley, x_scale="log").bars(x="yield", y="variety")
    with pytest.raises(ValueError, match="log x axis"):
        t._shown_scene()


def test_upright_bars_are_as_before(barley) -> None:
    _, (geom,) = built(Trellis(barley).bars(x="variety", y="yield"))
    assert np.all(geom.y0 == 0)
    assert np.allclose(geom.x1 - geom.x0, 0.8)


# ---- fill -------------------------------------------------------------------------------------


def test_stacks_fill_to_one() -> None:
    panel = np.zeros(5, dtype=np.int64)
    x = np.array([1.0, 1.0, 1.0, 2.0, 2.0])
    y = np.array([1.0, 1.0, 2.0, 3.0, -1.0])
    y0, y1 = _stack(panel, x, y, fill=True)
    assert y1.tolist() == [0.25, 0.5, 1.0, 1.0, -1.0]
    assert y0.tolist() == [0.0, 0.25, 0.5, 0.0, 0.0]


def test_filled_bars_are_shares_on_a_percent_axis(barley) -> None:
    t = Trellis(barley, wrap="site").as_category("year")
    spec, (geom,) = built(t.bars(x="variety", y="yield", color="year", position="fill"))
    assert np.isclose(geom.y1.max(), 1.0)
    assert np.all(geom.y0 >= 0)
    assert spec["y"]["format"] == ".0%"
    assert spec["panels"][0]["y"] == [0.0, pytest.approx(1.0, abs=0.06)]
    assert "100%" in re.findall(r"<text[^>]*>([^<]*)</text>", figure_svg(t))
    # a format given wins
    spec, _ = built(t.format(y=".1%"))
    assert spec["y"]["format"] == ".1%"


def test_a_filled_area_and_histogram(penguins) -> None:
    gap = load("gapminder").group_by("year", "region").agg(pl.col("pop").sum())
    spec, (geom,) = built(Trellis(gap).area(x="year", y="pop", color="region",
                                           position="fill"))  # fmt: skip
    assert np.isclose(max(geom.y0.max(), geom.y1.max()), 1.0)
    assert spec["y"]["format"] == ".0%"
    spec, geoms = built(Trellis(penguins, wrap="island").hist(
        x="body_mass_g", color="sex", position="fill", binwidth=250))  # fmt: skip
    assert np.isclose(max(g.y1.max() for g in geoms), 1.0)
    assert spec["y"]["format"] == ".0%"


def test_a_plot_with_other_marks_keeps_its_numbers(barley) -> None:
    t = Trellis(barley).as_category("year")
    t.bars(x="variety", y="yield", color="year", position="fill").rule(y=0.5)
    assert built(t)[0]["y"]["format"] == ".0%"  # a rule is not a mark
    t.points(x="variety", y="yield")
    assert built(t)[0]["y"]["format"] is None


def test_positions_are_checked(barley) -> None:
    with pytest.raises(ValueError, match="'stack', 'fill', 'dodge' or 'identity'"):
        Trellis(barley).bars(x="variety", y="yield", position="swarm")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="'stack', 'fill' or 'identity'"):
        Trellis(barley).area(x="year", y="yield", position="dodge")


# ---- jitter -----------------------------------------------------------------------------------


def test_jitter_spreads_points_within_their_band(penguins) -> None:
    t = Trellis(penguins).points(x="species", y="body_mass_g", jitter=0.4)
    spec, (geom,) = built(t)
    levels = spec["x"]["levels"]
    centre = np.array([levels.index(s) for s in penguins["species"]], dtype=np.float64)
    offset = geom.x0 - centre[geom.rows]
    assert np.abs(offset).max() <= 0.2
    assert offset.std() > 0.08  # spread, not stacked on the centre
    assert np.allclose(geom.y0, penguins["body_mass_g"].to_numpy()[geom.rows])
    # the same each time
    _, (again,) = built(Trellis(penguins).points(x="species", y="body_mass_g", jitter=0.4))
    assert np.array_equal(again.x0, geom.x0)


def test_jitter_along_a_category_y(penguins) -> None:
    _, (geom,) = built(Trellis(penguins).points(x="body_mass_g", y="species", jitter=0.5))
    assert np.allclose(geom.x0, penguins["body_mass_g"].to_numpy()[geom.rows])
    assert (geom.y0 % 1 != 0).any()


def test_jitter_needs_a_category_axis(penguins) -> None:
    t = Trellis(penguins).points(x="flipper_length_mm", y="body_mass_g", jitter=0.3)
    with pytest.raises(ValueError, match="neither axis holds categories"):
        t._shown_scene()
    with pytest.raises(ValueError, match="0 to 1"):
        Trellis(penguins).points(x="species", y="body_mass_g", jitter=2)


def test_jittered_offsets_are_even() -> None:
    u = jittered(np.zeros(100_000), np.arange(100_000), 1.0, 1)
    assert u.min() >= -0.5
    assert u.max() < 0.5
    assert abs(u.mean()) < 0.01
    assert np.histogram(u, bins=10)[0].min() > 9000


# ---- rules from data --------------------------------------------------------------------------


def targets(barley: pl.DataFrame) -> pl.DataFrame:
    sites = barley["site"].unique().sort()
    return pl.DataFrame({"site": sites, "target": [30.0 + 5 * i for i in range(len(sites))]})


def test_a_rule_per_panel_from_a_table(barley) -> None:
    t = Trellis(barley, wrap="site").points(x="yield", y="variety")
    t.rule(targets(barley), x="target", dash=(4, 3))
    spec, _ = built(t)
    rule = next(lr for lr in spec["layers"] if lr["type"] == "rule")
    names = [p["label"] for p in spec["panels"]]
    by_panel = dict(zip(rule["panels"], rule["values"], strict=True))
    sites = targets(barley)["site"].to_list()
    assert {names[p]: v for p, v in by_panel.items()} == dict(
        zip(sites, targets(barley)["target"].to_list(), strict=True)
    )
    # in an image: one dashed line in each panel
    svg = figure_svg(t)
    assert len(re.findall(r'<path d="M[^"]*V[^"]*"[^>]*stroke-dasharray', svg)) == len(sites)


def test_a_rule_table_without_facet_columns_is_in_every_panel(barley) -> None:
    t = Trellis(barley, wrap="site").points(x="yield", y="variety")
    t.rule(pl.DataFrame({"limit": [25.0, 50.0]}), x="limit")
    spec, _ = built(t)
    rule = next(lr for lr in spec["layers"] if lr["type"] == "rule")
    assert rule["panels"] == [-1, -1]
    assert rule["values"] == [25.0, 50.0]


def test_a_rule_from_data_widens_its_panel_only(barley) -> None:
    far = pl.DataFrame({"site": ["Morris"], "target": [200.0]})
    t = Trellis(barley, wrap="site").share(x=False).points(x="yield", y="variety")
    spec, _ = built(t.rule(far, x="target"))
    ranges = {p["label"]: p["x"] for p in spec["panels"]}
    assert ranges["Morris"][1] >= 200
    assert ranges["Duluth"][1] < 100


def test_a_rule_from_data_is_checked(barley) -> None:
    t = Trellis(barley, wrap="site").points(x="yield", y="variety")
    with pytest.raises(ValueError, match="name the data's column"):
        t.rule(targets(barley), x=30)
    with pytest.raises(ValueError, match="the y axis holds categories"):
        Trellis(barley, wrap="site").points(x="yield", y="variety").rule(
            targets(barley), y="target")._shown_scene()  # fmt: skip
    # categories on a category axis
    picks = pl.DataFrame({"pick": ["Trebi"]})
    spec, _ = built(Trellis(barley).points(x="yield", y="variety").rule(picks, y="pick"))
    rule = next(lr for lr in spec["layers"] if lr["type"] == "rule")
    assert rule["values"] == [float(spec["y"]["levels"].index("Trebi"))]
