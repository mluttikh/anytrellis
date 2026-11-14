"""Horizon charts: a series' distance from an origin, in bands laid over each other."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.layers import Geometry
from anytrellis.stats import band_labels, nice_step, ramp


def parts(t: Trellis) -> list[tuple[str, Geometry]]:
    """Each drawn part's band (its label) and marks."""
    t._scene()
    out = []
    for layer, table, geom in t._geometry:
        assert geom is not None
        assert layer.color is not None
        out.append((str(table.column(layer.color).values[0]), geom))
    return out


def area(g: Geometry) -> float:
    """The area of the trapezoids from each segment down to 0."""
    return float(np.sum((g.x1 - g.x0) * (g.y0 + g.y1) / 2))


def test_bands_are_slices_of_the_distance() -> None:
    data = {"t": np.linspace(0.0, 10.0, 3), "v": np.linspace(0.0, 10.0, 3)}  # v = t
    t = Trellis(data).horizon(x="t", y="v", bands=2, step=5)
    found = dict(parts(t))
    assert set(found) == {"≥ 5", "0 to 5"}  # nothing below the origin: no reds
    assert area(found["0 to 5"]) == pytest.approx(12.5 + 25)  # v up to 5, then 5
    assert area(found["≥ 5"]) == pytest.approx(12.5)  # v - 5 from 5 on
    assert found["≥ 5"].y1.max() <= 5


def test_a_point_where_the_series_crosses_a_band_edge() -> None:
    data = {"t": [0.0, 1.0], "v": [-7.0, 7.0]}
    t = Trellis(data).horizon(x="t", y="v", bands=2, step=5)
    t._scene()
    table = t._geometry[0][1]
    assert table.column("v").values.tolist() == [-7.0, -5.0, 0.0, 5.0, 7.0]
    assert table.column("t").values == pytest.approx([0.0, 1 / 7, 0.5, 6 / 7, 1.0])


def test_below_the_origin_is_folded_up_in_reds() -> None:
    data = {"t": [0.0, 1.0, 2.0], "v": [10.0, 4.0, 10.0]}
    t = Trellis(data).horizon(x="t", y="v", origin=10, bands=1, step=10)
    ((label, geom),) = parts(t)
    assert label == "≤ 10"
    assert geom.y0.max() == pytest.approx(6.0)  # 10 - 4, upwards
    spec, _ = t._scene()
    (legend,) = spec["legends"]
    assert legend["title"] == "v band"
    assert legend["labels"] == ["≥ 10", "≤ 10"]
    assert legend["colors"][1] == ramp("#fcbba1", "#67000d", 1)[0]


def test_the_step_is_round_and_shared_by_every_panel() -> None:
    data = pl.DataFrame({"g": ["a"] * 3 + ["b"] * 3, "t": [0.0, 1.0, 2.0] * 2,
                         "v": [0.0, 2.0, 1.0, 0.0, 8.0, 1.0]})  # fmt: skip
    spec, _ = Trellis(data, wrap="g").horizon(x="t", y="v", bands=3)._scene()
    assert [p["y"] for p in spec["panels"]] == [[0.0, 5.0], [0.0, 5.0]]  # 8 / 3 -> 5
    assert spec["legends"][0]["labels"][:3] == ["≥ 10", "5 to 10", "0 to 5"]


def test_helpers() -> None:
    assert [nice_step(v) for v in (0.0, 0.7, 2.6, 8.3, 30.0)] == [1.0, 1.0, 5.0, 10.0, 50.0]
    assert band_labels(2, 0, 2.5) == ["≥ 2.5", "0 to 2.5", "-2.5 to 0", "≤ -2.5"]
    assert band_labels(1, 7.73997919385, 10)[0] == "≥ 7.7"
    assert ramp("#000000", "#ffffff", 3) == ["#000000", "#808080", "#ffffff"]


def test_not_in_margins() -> None:
    data = pl.DataFrame({"r": ["a", "a", "b", "b"], "c": ["x", "x", "x", "x"],
                         "t": [0.0, 1.0, 0.0, 1.0], "v": [1.0, 2.0, 3.0, 4.0]})  # fmt: skip
    t = Trellis(data, row="r", col="c", margins="row").horizon(x="t", y="v")
    panels = {int(p) for _, g in parts(t) for p in g.panel}
    assert panels == {0, 1}  # the (all) row's panel (2) is left empty


@pytest.mark.parametrize(
    ("kw", "match"),
    [({"bands": 0}, "bands"), ({"bands": 7}, "bands"), ({"step": 0}, "step")],
)
def test_options_checked(kw: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Trellis({"t": [0.0], "v": [1.0]}).horizon(x="t", y="v", **kw)


def test_needs_numbers_on_a_linear_y() -> None:
    with pytest.raises(ValueError, match="categories"):
        Trellis({"t": [0.0, 1.0], "v": ["a", "b"]}).horizon(x="t", y="v")._scene()
    with pytest.raises(ValueError, match="log"):
        Trellis({"t": [0.0, 1.0], "v": [1.0, 2.0]}, y_scale="log").horizon(x="t", y="v")._scene()


def test_pages_read_from_a_database_share_the_step() -> None:
    from anytrellis.synthetic import sensors

    frame = pl.DataFrame(sensors(stations=120, sensors=1, hours=24))
    paged = Trellis(frame.lazy(), wrap="station", load="pages").horizon(x="time", y="temp")
    eager = Trellis(frame, wrap="station").horizon(x="time", y="temp")
    spec_p, _ = paged._scene()
    spec_e, _ = eager._scene()
    assert spec_p["legends"] == spec_e["legends"]
    assert spec_p["panels"][0]["y"] == spec_e["panels"][0]["y"]
