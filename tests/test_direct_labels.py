"""Text by the data: names at the ends of lines (``line(label="end")``), text labels that
keep out of each other's way (``text(repel=True)``) and notes (``annotate()``)."""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import duckdb
import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.codec import DTYPES
from anytrellis.figure import Rect, figure_svg, repel, spread
from anytrellis.plot import _buffer_ids

DATA = pl.DataFrame({
    "x": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
    "y": [1.0, 2.0, 3.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
    "k": ["a", "a", "a", "b", "b", "b", "c", "c", "c"],
    "p": ["u", "u", "u", "u", "u", "u", "v", "v", "v"],
})  # fmt: skip


def array(ref: dict, data: dict[str, bytes]) -> np.ndarray:
    return np.frombuffer(data[ref["id"]], dtype=DTYPES[ref["dtype"]])[: ref["count"]]


def test_names_of_the_colours_levels_in_place_of_their_legend() -> None:
    t = Trellis(DATA).line(x="x", y="y", color="k", label="end")
    spec, buffers = t._scene()
    lr = spec["layers"][0]
    ends = lr["end_labels"]
    assert ends["names"] == ["a", "b", "c"]
    assert ends["legend"] == 0
    series = array(ends["series"], buffers.data)
    assert len(series) == lr["count"]
    assert sorted(set(series.tolist())) == [0, 1, 2]
    assert ends["series"]["id"] in _buffer_ids(lr)  # a notebook asks for it
    [lg] = spec["legends"]
    assert lg["direct"] is True  # kept: select(color=) and the labels' clicks use it
    t.select(color=["b"])
    svg = figure_svg(t, width=600)
    assert ">b</text>" in svg
    assert 'paint-order="stroke"' in svg  # a halo
    assert ">k</text>" not in svg  # no legend


def test_another_mark_of_the_colour_keeps_the_legend() -> None:
    t = Trellis(DATA).line(x="x", y="y", color="k", label="end").points(x="x", y="y", color="k")
    assert "direct" not in t._scene()[0]["legends"][0]


def test_groups_name_the_series_without_a_colour() -> None:
    t = Trellis(DATA).line(x="x", y="y", group=["p", "k"], label="end")
    spec, _buffers = t._scene()
    ends = spec["layers"][0]["end_labels"]
    assert ends["names"] == ["u · a", "u · b", "v · c"]
    assert ends["legend"] is None
    one = Trellis(DATA.filter(pl.col("k") == "a")).line(x="x", y="y", label="end")
    assert one._scene()[0]["layers"][0]["end_labels"]["names"] == ["y"]


def test_room_on_the_right_for_the_names() -> None:
    plain = Trellis(DATA).line(x="x", y="y", color="k")._scene()[0]
    named = Trellis(DATA).line(x="x", y="y", color="k", label="end")._scene()[0]
    lo, hi = plain["panels"][0]["x"]
    lo2, hi2 = named["panels"][0]["x"]
    assert lo2 == lo
    assert hi2 > hi
    limited = Trellis(DATA).line(x="x", y="y", color="k", label="end").limits(x=(0, 3))
    assert limited._scene()[0]["panels"][0]["x"][1] - limited._scene()[0]["x"]["origin"] == 3
    with pytest.raises(ValueError, match='label must be "end"'):
        Trellis(DATA).line(x="x", y="y", label="start")


def test_the_database_gives_the_same_names() -> None:
    frame = DATA  # noqa: F841  (duckdb reads it by name)
    out = []
    for data, load in ((DATA, "all"), (duckdb.sql("select * from frame"), "pages")):
        t = Trellis(data, wrap="p", load=load).line(x="x", y="y", color="k", label="end")
        spec, buffers = t._scene()
        ends = spec["layers"][0]["end_labels"]
        out.append((ends["names"], sorted(array(ends["series"], buffers.data).tolist())))
    assert out[0] == out[1]


def test_saved_images_name_each_series_once_in_the_rightmost_panel() -> None:
    wide = pl.concat([DATA.with_columns(f=pl.lit("one")), DATA.with_columns(f=pl.lit("two"))])
    svg = figure_svg(Trellis(wide, wrap="f").line(x="x", y="y", color="k", label="end"),
                     width=800)  # fmt: skip
    assert svg.count(">a</text>") == 1


def test_spread_moves_labels_apart_and_leaves_out_those_too_far() -> None:
    ls = [SimpleNamespace(y=y) for y in (50.0, 51.0, 52.0, 200.0)]
    kept = spread(ls, 0, 300, 10, 15)
    ys = sorted(ls[i].y for i in kept)
    assert kept == [0, 1, 3]  # the third would move 20 px
    assert all(b - a >= 10 for a, b in itertools.pairwise(ys))
    crowd = [SimpleNamespace(y=95.0) for _ in range(3)]
    kept = spread(crowd, 0, 100, 10, 30)
    assert max(crowd[i].y for i in kept) <= 100  # pushed back up inside


def test_repel_places_labels_apart_inside_the_panel() -> None:
    r = Rect(0, 0, 200, 100)
    points = [(i, 100.0, 50.0, 40.0) for i in range(4)]
    placed = repel(points, 10, r, 4)
    boxes = [(x, y - 5, 40, 10) for _, x, y, _ in placed]
    for i, a in enumerate(boxes):
        assert r.x <= a[0]
        assert a[0] + a[2] <= r.x + r.w
        for b in boxes[i + 1 :]:
            assert not (a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and
                        a[1] < b[1] + b[3] and b[1] < a[1] + a[3])  # fmt: skip
    assert placed[0][1] == 104  # right of the point first
    assert placed[0][3] is None
    crowded = repel([(i, 100.0, 50.0, 40.0) for i in range(30)], 10, r, 4)
    assert 4 < len(crowded) < 30  # those with no room left out
    assert any(p[3] is not None for p in crowded)  # farther out: a line back


def test_text_repel_in_the_spec_and_the_image() -> None:
    labels = DATA.with_columns(name=pl.col("k") + pl.col("x").cast(pl.String))
    t = Trellis(labels).text(x="x", y="y", text="name", repel=True)
    assert t._scene()[0]["layers"][0]["repel"] is True
    svg = figure_svg(t, width=600)
    assert svg.count("<text") >= 9


def test_annotate_in_axis_units_and_panels() -> None:
    days = pl.DataFrame({"t": pl.datetime_range(pl.datetime(2024, 1, 1), pl.datetime(2024, 1, 10),
                                                "1d", eager=True), "v": range(10),
                         "s": ["a"] * 5 + ["b"] * 5})  # fmt: skip
    t = Trellis(days, wrap="s").line(x="t", y="v")
    t.annotate("peak", x="2024-01-09", y=8, panel="b", dx=-10, dy=5)
    t.annotate("all", x="2024-01-02")
    spec, _ = t._scene()
    peak, everywhere = spec["notes"]
    ms = np.datetime64("2024-01-09", "ms").astype(np.int64)
    assert peak["x"] == pytest.approx(ms - spec["x"]["origin"])
    assert peak["y"] == pytest.approx(8 - spec["y"]["origin"])
    assert peak["panels"] == [1]
    assert peak["align"] == "right"  # away from the point
    assert everywhere["panels"] is None
    assert everywhere["y"] is None
    assert everywhere["align"] == "center"
    svg = figure_svg(t, width=600)
    assert svg.count(">all</text>") == 2
    assert svg.count(">peak</text>") == 1
    with pytest.raises(ValueError, match="annotate\\(panel='c'\\): no such panel"):
        Trellis(days, wrap="s").line(x="t", y="v").annotate("x", x=1, panel="c")._scene()


def test_annotate_a_category_and_a_colour() -> None:
    t = Trellis(DATA).bars(x="k", y="y").annotate("best", x="c", y=7, color="#c33", size=14)
    note = t._scene()[0]["notes"][0]
    assert note["x"] == 2 - t._scene()[0]["x"]["origin"]
    assert note["color"] == [204, 51, 51, 255]
    with pytest.raises(ValueError, match="not a place on the x axis"):
        Trellis(DATA).bars(x="k", y="y").annotate("?", x="z")._scene()
    with pytest.raises(ValueError, match="align must be"):
        Trellis(DATA).annotate("?", align="middle")
