"""Shape, size and dash as data: ``points(shape=, size=)`` and ``line(dash=)``, their
legends, and how the browser and the saved images draw them."""

from __future__ import annotations

import re

import duckdb
import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.channels import (
    DASHES,
    SHAPES,
    dash_pieces,
    shape_paths,
    size_breaks,
    size_factors,
)
from anytrellis.codec import DTYPES
from anytrellis.figure import figure_svg
from anytrellis.plot import _buffer_ids

DATA = pl.DataFrame({
    "x": [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0],
    "y": [1.0, 2.0, 3.0, 4.0, 2.0, 3.0, 4.0, 5.0],
    "k": ["a", "a", "a", "a", "b", "b", "b", "b"],
    "j": ["p", "q", "p", "q", "p", "q", "p", "q"],
    "v": [0.0, 25.0, 50.0, 100.0, 10.0, 20.0, 30.0, np.nan],
})  # fmt: skip


def layer(t: Trellis, i: int = 0) -> tuple[dict, dict[str, bytes]]:
    spec, buffers = t._scene()
    return spec["layers"][i], buffers.data


def array(ref: dict, data: dict[str, bytes]) -> np.ndarray:
    return np.frombuffer(data[ref["id"]], dtype=DTYPES[ref["dtype"]])[: ref["count"]]


def test_a_shape_a_level_and_one_legend_with_the_colour() -> None:
    t = Trellis(DATA).points(x="x", y="y", color="k", shape="k")
    lr, data = layer(t)
    assert lr["marker"]["shape"] == 0
    codes = array(lr["marker"]["shapes"], data)
    t._scene()
    geom = t._geometry[0][2]
    assert geom is not None
    rows = geom.rows
    assert codes.tolist() == [0 if DATA["k"][int(r)] == "a" else 1 for r in rows]
    [lg] = t._scene()[0]["legends"]
    assert lg["kind"] == "category"
    assert lg["shapes"] == [0, 1]  # in the colour legend: no second legend
    assert lr["marker"]["shapes"]["id"] in _buffer_ids(lr)  # a notebook asks for it


def test_another_column_gets_its_own_legend_in_the_marks_colour() -> None:
    t = Trellis(DATA).points(x="x", y="y", color="k", shape="j")
    colour, shape = t._scene()[0]["legends"]
    assert "shapes" not in colour
    assert shape["kind"] == "shape"
    assert shape["labels"] == ["p", "q"]
    assert shape["shapes"] == [0, 1]
    assert shape["colors"] == ["#4a5260"] * 2  # coloured by a column: grey
    plain = Trellis(DATA).points(x="x", y="y", shape="j", color="#c33")
    assert plain._scene()[0]["legends"][0]["colors"] == ["#c33", "#c33"]
    with pytest.raises(ValueError, match="no colour legend has all of"):
        t.select(color=["p"])  # a shape legend isn't a colour's


def test_one_shape_for_all_and_more_levels_than_shapes_cycle() -> None:
    lr, _ = layer(Trellis(DATA).points(x="x", y="y", shape="diamond"))
    assert lr["marker"] == {"shape": SHAPES.index("diamond"), "shapes": None, "sizes": None}
    assert layer(Trellis(DATA).points(x="x", y="y", shape="circle"))[0]["marker"] is None
    many = pl.DataFrame({"x": range(9), "y": range(9), "s": list("abcdefghi")})
    [lg] = Trellis(many).points(x="x", y="y", shape="s")._scene()[0]["legends"]
    assert lg["shapes"] == [0, 1, 2, 3, 4, 5, 6, 0, 1]
    with pytest.raises(ValueError, match="shape must be a column or one of"):
        Trellis(DATA).points(x="x", y="y", shape="star")._scene()
    with pytest.raises(ValueError, match=r"shape='v' draws a shape a category"):
        Trellis(DATA).points(x="x", y="y", shape="v")._scene()


def test_sizes_by_area_largest_first_and_a_legend() -> None:
    t = Trellis(DATA, wrap="k").points(x="x", y="y", size="v", size_range=(2, 12))
    lr, data = layer(t)
    assert lr["size"] == 12
    factors = array(lr["marker"]["sizes"], data)
    t._scene()
    geom = t._geometry[0][2]
    assert geom is not None
    values = DATA["v"].to_numpy()[geom.rows]
    want = (2 + 10 * np.sqrt(values / 100)) / 12
    assert np.allclose(factors, want, equal_nan=True)
    a = geom.panel == 0
    assert values[a].tolist() == [100.0, 50.0, 25.0, 0.0]  # the largest first
    assert np.isnan(factors[~a][-1])  # no value: not drawn
    size = t._scene()[0]["legends"][0]
    assert size["kind"] == "size"
    assert size["labels"] == ["0", "25", "50", "75", "100"]
    assert size["sizes"][0] == pytest.approx(2)
    assert size["sizes"][-1] == pytest.approx(12)
    assert [row[0] for row in t._tooltip(0, 0)][-1] == "v"  # the size, in the tooltip
    with pytest.raises(ValueError, match="size_range"):
        Trellis(DATA).points(x="x", y="y", size="v", size_range=(5, 2))
    with pytest.raises(ValueError, match="sizes points by a number column"):
        Trellis(DATA).points(x="x", y="y", size="k")._scene()


def test_a_dash_a_level_each_its_own_series() -> None:
    t = Trellis(DATA).line(x="x", y="y", dash="k", color="k")
    lr, data = layer(t)
    assert lr["dash"]["patterns"] == [list(p) for p in DASHES.values()]
    codes = array(lr["dash"]["codes"], data)
    assert sorted(set(codes.tolist())) == [0, 1]
    assert lr["count"] == 6  # two lines of three segments: not joined
    [lg] = t._scene()[0]["legends"]
    assert lg["dashes"] == [[], [4, 4]]
    assert lg["line_width"] == 1.5
    other = Trellis(DATA).line(x="x", y="y", dash="j")
    assert other._scene()[0]["legends"][0]["kind"] == "dash"
    assert layer(other)[0]["count"] == 6  # split by p and q: 3 segments each, not 7
    assert lr["dash"]["codes"]["id"] in _buffer_ids(lr)


def test_one_dash_in_px_as_a_rules() -> None:
    lr, _ = layer(Trellis(DATA).line(x="x", y="y", dash=(6, 3), width=2))
    assert lr["dash"] == {"patterns": [[3.0, 1.5]], "codes": None}
    assert layer(Trellis(DATA).line(x="x", y="y"))[0]["dash"] is None
    with pytest.raises(ValueError, match="pairs of dash and gap"):
        Trellis(DATA).line(x="x", y="y", dash=(4,))


def test_dashes_cut_by_length_and_carried_on_across_segments() -> None:
    # 0..10 then 10..20 px, dashes of 4 and gaps of 4 at width 1: caps take 1 from each dash
    ax, ay = np.array([0.0, 10.0]), np.zeros(2)
    bx, by = np.array([10.0, 20.0]), np.zeros(2)
    pieces, src = dash_pieces(ax, ay, bx, by, None, [[4, 4]], 1.0)
    assert pieces[:, 0].tolist() == [0.0, 8.0, 10.0, 16.0]
    assert pieces[:, 2].tolist() == [3.0, 10.0, 11.0, 19.0]
    assert src.tolist() == [0, 0, 1, 1]
    # a gap of a dot pattern: zero-length dashes, each a round dot
    dots, _ = dash_pieces(np.array([0.0]), np.zeros(1), np.array([9.0]), np.zeros(1), None,
                          [[1, 3]], 1.0)  # fmt: skip
    assert dots[:, 0].tolist() == dots[:, 2].tolist() == [0.0, 4.0, 8.0]
    solid, _ = dash_pieces(ax, ay, bx, by, np.array([0, 0], np.uint8), [[]], 1.0)
    assert len(solid) == 2


@pytest.mark.parametrize("mark", ["points", "line"])
def test_the_database_gives_the_same(mark: str) -> None:
    frame = DATA  # noqa: F841  (duckdb reads it by name)
    out = []
    for data, load in ((DATA, "all"), (duckdb.sql("select * from frame"), "pages")):
        t = Trellis(data, wrap="k", load=load)
        if mark == "points":
            t.points(x="x", y="y", size="v", shape="j")
        else:
            t.line(x="x", y="y", dash="j")
        spec, buffers = t._scene()
        lr = spec["layers"][0]
        refs = [lr["marker"]["shapes"], lr["marker"]["sizes"]] if mark == "points" \
            else [lr["dash"]["codes"]]  # fmt: skip
        out.append((spec["legends"], [array(r, buffers.data).tolist() for r in refs]))
    (eager, eager_codes), (paged, paged_codes) = out
    assert paged == eager  # every row's range and levels
    assert np.allclose(np.array(paged_codes[0], float), np.array(eager_codes[0], float),
                       equal_nan=True)  # fmt: skip


def test_saved_images_draw_shapes_sizes_and_dashes() -> None:
    t = Trellis(DATA).points(x="x", y="y", shape="k", size="v", color="k")
    svg = figure_svg(t, width=500)
    triangle = shape_paths(np.array([2]), np.zeros(1), np.zeros(1), np.ones(1))[0]
    assert triangle.count("L") == 2
    assert svg.count(" 0 1 0 ") >= 2  # circles: two arcs each
    assert re.search(r'<path d="M[^"]*L[^"]*L[^"]*z" fill="#', svg)  # a square of points
    line = Trellis(DATA).line(x="x", y="y", dash="k", color="k")
    svg = figure_svg(line, width=500)
    assert 'stroke-dasharray="' in svg  # the legend's dashed swatch
    solid = figure_svg(Trellis(DATA).line(x="x", y="y", color="k"), width=500)
    assert svg.count("M") > solid.count("M") + 5  # the dashes, each a piece


def test_size_breaks_and_factors() -> None:
    assert size_breaks(5e4, 1.3e9) == [2.5e8, 5e8, 7.5e8, 1e9, 1.25e9]
    assert size_breaks(2.3, 7.9) == [3, 4, 5, 6, 7]
    assert size_breaks(3, 3) == [3]
    f = size_factors(np.array([0.0, 100.0, np.nan]), 0, 100, 2, 10)
    assert f[0] == pytest.approx(0.2)
    assert f[1] == 1
    assert np.isnan(f[2])


def test_zoomed_in_points_keep_their_shapes() -> None:
    rng = np.random.default_rng(0)
    n = 300_000
    cloud = pl.DataFrame({"x": rng.normal(size=n), "y": rng.normal(size=n),
                          "k": rng.choice(["a", "b"], n)})  # fmt: skip
    t = Trellis(cloud).points(x="x", y="y", shape="k")
    spec, _ = t._scene()
    ox, oy = spec["x"]["origin"], spec["y"]["origin"]
    report = {"width": 800, "panels": [[0, 600, 400]], "x": [[0, [-ox, 0.02 - ox]]],
              "y": [[0, [-oy, 0.02 - oy]]]}  # fmt: skip
    message = t._detail(report)
    assert message is not None
    points = message["layers"][0]["layer"]
    assert 0 < points["count"] < n
    assert points["marker"]["shapes"]["count"] == points["count"]
