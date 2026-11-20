"""Bars that summarise the rows at each position (``bars(stat=...)``: a count, a sum, a
mean or a median) and the empirical cumulative distribution (``ecdf``)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.stats import ECDF_STEPS

DATA = pl.DataFrame({
    "g": ["a", "a", "a", "b", "b", "b", "b", "c"],
    "k": ["p", "q", "p", "p", "q", "q", "q", "p"],
    "n": [3, 4, 4, 6, 6, 6, 8, 4],
    "v": [1.0, 2.0, 6.0, 3.0, 5.0, 7.0, 9.0, 4.0],
})  # fmt: skip


def bars(t: Trellis) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The first layer's bars: each one's panel, centre across, low and high end along."""
    t._scene()
    _, _, geom = t._geometry[0]
    assert geom is not None
    return geom.panel, (geom.x0 + geom.x1) / 2, geom.y0, geom.y1


def part(t: Trellis) -> pl.DataFrame:
    """The first layer's summary table, as drawn."""
    t._scene()
    _, table, _ = t._geometry[0]
    return pl.DataFrame({name: table.raw(name) for name in table.names})


def test_count_the_rows_at_each_x() -> None:
    t = Trellis(DATA, wrap="g").bars(x="n", stat="count")
    spec, _ = t._scene()
    assert spec["layers"][0]["type"] == "bars"
    assert spec["y"]["title"] == "count"
    panel, x, y0, y1 = bars(t)
    got = sorted(zip(panel.tolist(), x.tolist(), y1.tolist(), strict=True))
    assert got == [(0, 3.0, 1.0), (0, 4.0, 2.0), (1, 6.0, 3.0), (1, 8.0, 1.0), (2, 4.0, 1.0)]
    assert not y0.any()


def test_sum_mean_and_median_of_the_values() -> None:
    for stat, want in [("sum", {"a": 9.0, "b": 24.0, "c": 4.0}),
                       ("mean", {"a": 3.0, "b": 6.0, "c": 4.0}),
                       ("median", {"a": 2.0, "b": 6.0, "c": 4.0})]:  # fmt: skip
        t = Trellis(DATA).bars(x="g", y="v", stat=stat)
        got = part(t)
        assert dict(zip(got["g"].to_list(), got[stat].to_list(), strict=True)) == want, stat
        assert got["n"].to_list() == [3, 4, 1]
        _, _, _, y1 = bars(t)
        assert sorted(y1.tolist()) == sorted(want.values())
        assert t._scene()[0]["y"]["title"] == "v"  # the values' axis, named as the column


def test_horizontal_bars_along_a_category_y() -> None:
    t = Trellis(DATA).bars(y="g", stat="count")
    t._scene()
    _, _, geom = t._geometry[0]
    assert geom is not None
    assert sorted(geom.x1.tolist()) == [1.0, 3.0, 4.0]  # along x
    assert not geom.x0.any()
    spec, _ = t._scene()
    assert spec["y"]["kind"] == "band"
    assert spec["x"]["title"] == "count"
    m = Trellis(DATA).bars(x="v", y="g", stat="mean")
    m._scene()
    mg = m._geometry[0][2]
    assert mg is not None
    assert sorted(mg.x1.tolist()) == [3.0, 4.0, 6.0]


def test_colours_stack_counts_and_dodge_means() -> None:
    t = Trellis(DATA).bars(x="g", stat="count", color="k")
    _, x, y0, y1 = bars(t)
    tops = {}
    for c, top in zip(np.round(x, 6).tolist(), y1.tolist(), strict=True):
        tops[c] = max(tops.get(c, 0.0), top)
    assert sorted(tops.values()) == [1.0, 3.0, 4.0]  # each stack as tall as its rows
    assert y0.any()  # the second colour on the first
    filled = Trellis(DATA).bars(x="g", stat="count", color="k", position="fill")
    assert np.isclose(bars(filled)[3].max(), 1.0)
    m = Trellis(DATA).bars(x="g", y="v", stat="mean", color="k")  # dodged by default
    _, mx, my0, _ = bars(m)
    assert len(np.unique(np.round(mx, 6))) == len(mx)  # side by side
    assert not my0.any()


def test_a_selection_is_of_the_rows_summarised() -> None:
    t = Trellis(DATA).bars(x="g", y="v", stat="mean")
    t.select(x=["b"])
    assert sorted(t.selected()["v"].to_list()) == [3.0, 5.0, 7.0, 9.0]
    c = Trellis(DATA, wrap="g").bars(x="n", stat="count")
    c.select(x=(5, 7))
    assert c.selected()["n"].to_list() == [6, 6, 6]


def test_values_on_a_sqrt_axis_once_summed() -> None:
    t = Trellis(DATA).bars(x="g", y="v", stat="sum").scale(y="sqrt")
    _, _, _, y1 = bars(t)
    assert np.allclose(sorted(y1.tolist()), np.sqrt([4.0, 9.0, 24.0]))
    with pytest.raises(ValueError, match="log y axis"):
        Trellis(DATA).bars(x="g", stat="count").scale(y="log")._scene()


def test_bar_stat_errors() -> None:
    t = Trellis(DATA)
    with pytest.raises(ValueError, match="stat must be one of"):
        t.bars(x="g", y="v", stat="max")
    with pytest.raises(ValueError, match="needs x and y"):
        t.bars(x="g")
    with pytest.raises(ValueError, match="not both"):
        t.bars(x="g", y="v", stat="count")
    with pytest.raises(ValueError, match="positions and the values"):
        t.bars(x="g", stat="mean")
    with pytest.raises(ValueError, match="don't add up"):
        t.bars(x="g", y="v", stat="mean", position="stack")
    with pytest.raises(ValueError, match="tooltip= is for bars of rows"):
        t.bars(x="g", y="v", stat="sum", tooltip=["n"])
    with pytest.raises(ValueError, match="must be numbers"):
        Trellis(DATA).bars(x="v", y="g", stat="sum").bars(x="g", y="k", stat="sum",
                                                           name="b")._scene()  # fmt: skip
    with pytest.raises(ValueError, match=r"bars\(stat='count'\) with color='n'"):
        Trellis(DATA).bars(x="g", stat="count", color="n")._scene()


# ---- ECDF ---------------------------------------------------------------------------------


def steps(t: Trellis) -> pl.DataFrame:
    got = part(t)
    return got.rename({"__panel__": "panel"})


def test_ecdf_rises_to_one_at_each_value() -> None:
    t = Trellis(DATA, wrap="g").ecdf(x="v")
    spec, _ = t._scene()
    assert spec["layers"][0]["type"] == "line"
    assert spec["y"]["title"] == "proportion"
    s = steps(t)
    a = s.filter(pl.col("panel") == 0)
    assert a["v"].to_list() == [1.0, 2.0, 6.0]
    assert np.allclose(a["proportion"].to_list(), [1 / 3, 2 / 3, 1.0])
    # a riser at each value, then along to the next: 3 risers and 2 runs in panel a
    geom = t._geometry[0][2]
    assert geom is not None
    mine = geom.panel == 0
    assert mine.sum() == 5
    risers = mine & (geom.x0 == geom.x1)
    assert np.allclose(sorted(geom.y0[risers].tolist()), [0.0, 1 / 3, 2 / 3])


def test_ecdf_stats_colours_and_ties() -> None:
    t = Trellis(DATA).ecdf(x="n", color="k", stat="count")
    s = steps(t).filter(pl.col("k") == "q")
    assert s["n"].to_list() == [4.0, 6.0, 8.0]  # a tie (6, 6): one step, two rows
    assert s["count"].to_list() == [1.0, 3.0, 4.0]
    survival = steps(Trellis(DATA).ecdf(x="v", complementary=True, stat="percent"))
    assert survival["percent"].to_list()[-1] == 0.0
    assert np.isclose(survival["percent"].to_list()[0], 100 * 7 / 8)


def test_ecdf_of_many_values_steps_at_most_so_often() -> None:
    rng = np.random.default_rng(1)
    big = pl.DataFrame({"x": rng.normal(size=20_000)})
    s = steps(Trellis(big).ecdf(x="x"))
    assert len(s) == ECDF_STEPS
    assert s["proportion"].to_list()[-1] == 1.0
    exact = np.searchsorted(np.sort(big["x"].to_numpy()), s["x"].to_numpy(), side="right")
    assert np.allclose(s["proportion"].to_numpy(), exact / len(big))  # each step exact


def test_ecdf_selection_and_errors() -> None:
    t = Trellis(DATA, wrap="g").ecdf(x="v")
    t.select(x=(8, 10), y=(0.9, 1.1), panel="b")  # the last step, up to 1: 9's
    assert t.selected()["v"].to_list() == [9.0]
    with pytest.raises(ValueError, match="numbers or times"):
        Trellis(DATA).ecdf(x="g")._scene()
    with pytest.raises(ValueError, match="stat must be"):
        Trellis(DATA).ecdf(x="v", stat="density")
    with pytest.raises(ValueError, match="log y axis"):
        Trellis(DATA).ecdf(x="v").scale(y="log")._scene()


def test_saved_images_draw_them(tmp_path: Path) -> None:
    for t in (Trellis(DATA, wrap="g").bars(x="k", y="v", stat="mean"),
              Trellis(DATA, wrap="g").ecdf(x="v", color="k")):  # fmt: skip
        svg = t.save_svg(tmp_path / "s.svg").read_text(encoding="utf-8")
        assert "<path" in svg or "<rect" in svg
