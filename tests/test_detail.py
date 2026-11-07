"""Level of detail: long lines thinned (M4), dense points drawn as cells, and either in more
detail for the view the browser reports."""

from __future__ import annotations

import base64
import json
from typing import Any

import numpy as np
import pytest

from anytrellis import Trellis, link
from anytrellis.detail import COLUMNS, DENSE, THIN, m4
from anytrellis.figure import figure_svg

N = 3 * THIN  # points per panel of a long line


def walk(panels: int = 2, n: int = N, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "t": np.tile(np.arange(n, dtype=np.float64), panels),
        "v": np.cumsum(rng.normal(size=panels * n)),
        "s": np.repeat([f"s{i}" for i in range(panels)], n),
    }


def cloud(n: int = 2 * DENSE, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "x": rng.normal(size=n),
        "y": rng.normal(size=n),
        "c": rng.choice(["a", "b", "c"], n, p=[0.6, 0.3, 0.1]),
        "k": rng.uniform(size=n),
    }


Range = tuple[float, float]


def view(plot: Trellis, x: Range | None = None, y: Range | None = None, w: float = 400,
         h: float = 300) -> dict[str, Any]:  # fmt: skip
    """What the browser reports: every panel shown, ranges in axis units (absolute)."""
    spec, _ = plot._scene()
    ox, oy = spec["x"]["origin"], spec["y"]["origin"]
    groups = {p["xg"] for p in spec["panels"]}
    out: dict[str, Any] = {"width": 800, "x": [], "y": [],
                           "panels": [[i, w, h] for i in range(len(spec["panels"]))]}  # fmt: skip
    if x is not None:
        out["x"] = [[g, [x[0] - ox, x[1] - ox]] for g in groups]
    if y is not None:
        out["y"] = [[g, [y[0] - oy, y[1] - oy]] for g in {p["yg"] for p in spec["panels"]}]
    return out


def coords(plot: Trellis, index: int, shown: bool = True) -> np.ndarray:
    spec, buffers = plot._shown_scene() if shown else plot._scene()
    ref = spec["layers"][index]["coords"]
    data = buffers.data[ref["id"]]
    return np.frombuffer(data, dtype="<f8").reshape(-1, 4)


# ---- M4 -------------------------------------------------------------------------------------


def test_m4_keeps_each_columns_first_last_lowest_and_highest():
    x = np.arange(12, dtype=np.float64)
    y = np.array([5, 1, 9, 4, 3, 3, 7, 7, 2, 8, 0, 6], dtype=np.float64)
    seg = np.zeros(12, dtype=np.int64)
    one = np.zeros(1, dtype=np.int64)
    kept = m4(seg, x, y, np.array([0.0]), np.array([12.0]), np.array([2]), one)
    # columns [0, 6) and [6, 12): first, lowest, highest, last of each
    assert kept.tolist() == [0, 1, 2, 5, 6, 9, 10, 11]
    # a column a point: all of them
    all_kept = m4(seg, x, y, np.array([0.0]), np.array([12.0]), np.array([12]), one)
    assert all_kept.tolist() == list(range(12))
    # series apart: each its own first and last
    seg2 = np.repeat([0, 1], 6)
    assert set(m4(seg2, x, y, np.array([0.0]), np.array([12.0]), np.array([1]), one)) >= {5, 6}


# ---- lines -------------------------------------------------------------------------------


def test_a_long_line_is_sent_thinned_with_its_extremes():
    data = walk()
    plot = Trellis(data, wrap="s").line(x="t", y="v")
    spec, _ = plot._scene()
    layer = spec["layers"][0]
    assert layer["count"] <= 2 * 4 * COLUMNS  # two panels, four points a column
    c = coords(plot, 0)
    oy = spec["y"]["origin"]
    # each panel's lowest and highest point is drawn
    for i in range(2):
        v = data["v"][i * N : (i + 1) * N]
        starts = np.frombuffer(plot._scene()[1].data[layer["starts"]["id"]], dtype="<u4")
        ys = c[starts[i] : starts[i + 1], [1, 3]] + oy
        assert np.isclose(ys.min(), v.min())
        assert np.isclose(ys.max(), v.max())
    # Python selects among all the points, not those sent
    plot.select(x=(100, 199))
    assert len(plot.selected()["t"]) == 2 * 100


def test_a_short_line_is_sent_whole():
    data = walk(n=THIN // 2)
    plot = Trellis(data, wrap="s").line(x="t", y="v")
    assert plot._scene()[0]["layers"][0]["count"] == 2 * (THIN // 2 - 1)
    assert plot._details == []
    assert plot._detail(view(plot, (0, 10))) is None


def test_a_gap_in_a_thinned_line_stays_a_gap():
    data = walk(panels=1)
    data["v"][N // 2] = np.nan
    plot = Trellis(data).line(x="t", y="v")
    c = coords(plot, 0)
    gap = N // 2
    # no segment crosses the missing point
    assert not np.any((c[:, 0] < gap) & (c[:, 2] > gap))


def test_zoomed_in_the_line_comes_in_detail():
    plot = Trellis(walk(), wrap="s").line(x="t", y="v")
    spec, _ = plot._scene()
    base = spec["layers"][0]["coords"]["id"]
    message = plot._detail(view(plot, (1000, 2000), w=400))
    assert message is not None
    [entry] = message["layers"]
    assert entry["index"] == 0
    assert entry["of"] == base
    c = coords(plot, 0)
    inside = c[(c[:, 0] >= 1000) & (c[:, 2] <= 2000)]
    # 1000 points over 400 px at two columns a pixel: every point
    assert len(inside) >= 2 * 999
    # a little pan stays in what was sent
    assert plot._detail(view(plot, (1100, 2100), w=400)) is None
    # zoomed out again: as it started
    out = plot._detail(view(plot, (0, N), w=400))
    assert out is not None
    assert out["layers"][0]["layer"]["coords"]["id"] == base
    assert plot._detail_buffers.data.keys() <= set(_ids(out["layers"][0]["layer"]))


def _ids(spec_layer: dict[str, Any]) -> set[str]:
    from anytrellis.plot import _buffer_ids

    return set(_buffer_ids(spec_layer))


def test_tooltips_find_the_layer_as_the_browser_showed_it():
    data = walk()
    data["note"] = np.array([f"row {i}" for i in range(len(data["t"]))])
    plot = Trellis(data, wrap="s").line(x="t", y="v", tooltip=["note"])
    spec, _ = plot._scene()
    base = spec["layers"][0]["coords"]["id"]
    first = plot._tooltip(0, 0, base)
    plot._detail(view(plot, (1000, 2000)))
    detail = plot._shown_layers[0]["coords"]["id"]
    assert plot._tooltip(0, 0, base) == first  # asked for as it was shown
    assert plot._tooltip(0, 0, detail) != first  # in detail: another first instance
    assert plot._tooltip(0, 0, detail) == plot._tooltip(0, 0)


def test_images_draw_the_detail_shown():
    plot = Trellis(walk(panels=1)).line(x="t", y="v")
    before = figure_svg(plot, width=600)
    plot._view = view(plot, (1000, 1100))
    plot._detail(plot._view)
    after = figure_svg(plot, width=600)
    assert after != before
    assert len(after) < 2 * len(before)


# ---- points ------------------------------------------------------------------------------


def test_dense_points_are_sent_as_cells():
    data = cloud()
    plot = Trellis(data).points(x="x", y="y")
    spec, _ = plot._scene()
    points, cells = spec["layers"]
    assert points["type"] == "points"
    assert points["count"] == 0
    assert cells["type"] == "rect"
    assert cells["name"] == points["name"]
    assert cells["count"] > 0
    _, table, _, part = plot._sent[1]
    assert part is not None
    assert table.column("points").values.sum() == len(data["x"])
    assert part.members.starts[-1] == len(data["x"])
    # Python selects among the points, exactly
    plot.select(x=(0, 1), y=(0, 1))
    inside = (data["x"] >= 0) & (data["x"] <= 1) & (data["y"] >= 0) & (data["y"] <= 1)
    assert len(plot.selected()["x"]) == inside.sum()


def test_cells_mix_a_category_colour_and_tell_each_levels_points():
    plot = Trellis(cloud()).points(x="x", y="y", color="c")
    plot._scene()
    _, table, geom, _ = plot._sent[1]
    assert geom is not None
    assert {"c a", "c b", "c c"} <= set(table.names)
    counts = [table.column(f"c {lv}").values for lv in "abc"]
    assert np.array_equal(sum(counts), table.column("points").values)
    assert geom.codes is not None
    assert np.array_equal(geom.codes, np.argmax(np.stack(counts, axis=1), axis=1))
    rows = plot._tooltip(1, 0)
    assert [name for name, _ in rows] == ["points", "c a", "c b", "c c"]
    # a number colour: its mean
    k = Trellis(cloud()).points(x="x", y="y", color="k")
    k._scene()
    assert "mean k" in k._sent[1][1].names


def test_zoomed_in_dense_points_come_as_finer_cells_then_points():
    plot = Trellis(cloud()).points(x="x", y="y")
    spec, _ = plot._scene()
    # a little: finer cells
    message = plot._detail(view(plot, (-2, 2), (-2, 2), w=600, h=400))
    assert message is not None
    assert [e["index"] for e in message["layers"]] == [0, 1]
    assert message["layers"][0]["layer"]["count"] == 0
    assert message["layers"][1]["layer"]["count"] > spec["layers"][1]["count"]
    assert all(e["of"] == spec["layers"][e["index"]]["coords"]["id"] for e in message["layers"])
    # a lot: few points in view, so points again
    message = plot._detail(view(plot, (0, 0.05), (0, 0.05), w=600, h=400))
    assert message is not None
    points, cells = (e["layer"] for e in message["layers"])
    assert cells["count"] == 0
    assert 0 < points["count"] < DENSE
    c = coords(plot, 0)
    assert c[:, 0].min() >= -0.05
    assert c[:, 0].max() <= 0.1


def test_points_on_a_category_axis_or_few_stay_points():
    data = cloud()
    data["g"] = np.where(data["x"] > 0, "right", "left")
    spec, _ = Trellis(data).points(x="g", y="y")._scene()
    assert [lr["type"] for lr in spec["layers"]] == ["points"]
    spec, _ = Trellis(cloud(n=DENSE)).points(x="x", y="y")._scene()
    assert [lr["count"] for lr in spec["layers"]] == [DENSE]


def test_highlights_say_which_data_they_are_for():
    data = cloud()
    a = Trellis(data).points(x="x", y="y")
    b = Trellis(data).points(x="x", y="y")
    link(a, b)
    a.select(x=(0, 1))
    entries = b._highlight_entries()
    from anytrellis.linking import highlight_message

    message, buffers = highlight_message(entries, b._highlight)
    cells = message["layers"][1]
    bits = np.unpackbits(np.frombuffer(buffers[cells["mask"]], dtype=np.uint8), bitorder="little")
    assert 0 < bits[: cells["count"]].sum() < cells["count"]  # cells with a point selected

    class Sent:
        def __init__(self) -> None:
            self.messages: list[Any] = []

        def __call__(self, content: Any, buffers: Any = None) -> None:
            self.messages.append(content)

    w = b.widget
    sent = Sent()
    w.send = sent
    b._send_highlight()
    ofs = [lr and lr.get("of") for lr in sent.messages[-1]["layers"]]
    assert ofs == [lr["coords"]["id"] for lr in b._shown_layers]


# ---- the widget and saved pages ------------------------------------------------------------


def test_the_widget_sends_detail_for_the_view_and_its_buffers():
    plot = Trellis(walk(), wrap="s").line(x="t", y="v")
    w = plot.widget
    sent: list[tuple[dict[str, Any], Any]] = []
    w.send = lambda content, buffers=None: sent.append((content, buffers))
    report = view(plot, (1000, 2000))
    w._on_msg(w, {"type": "view", **report}, [])
    assert plot._view is not None
    assert plot._view["panels"] == report["panels"]
    [(message, _)] = sent
    assert message["type"] == "detail"
    layer = message["layers"][0]["layer"]
    w._on_msg(w, {"type": "need", "ids": [layer["coords"]["id"]]}, [])
    put, _data = sent[-1]
    assert put["type"] == "put"
    assert put["byteLength"] == layer["count"] * 32
    # the same view again: nothing to send
    w._on_msg(w, {"type": "view", **report}, [])
    assert len(sent) == 2
    w._on_msg(w, {"type": "tooltip", "request": 1, "layer": 0, "index": 0,
                  "of": layer["coords"]["id"]}, [])  # fmt: skip
    assert sent[-1][0] == {"type": "answer", "request": 1, "rows": []}


def test_saved_pages_embed_what_the_plot_starts_with():
    plot = Trellis(walk(), wrap="s").line(x="t", y="v")
    plot._detail(view(plot, (1000, 2000)))
    html = plot._embed_html()
    payload = json.loads(html.split("<script type='application/json'>")[1].split("</script>")[0])
    spec, buffers = plot._scene()
    assert set(payload["buffers"]) == set(buffers.data)
    assert payload["spec"]["layers"][0]["count"] == spec["layers"][0]["count"]
    size = sum(len(base64.b64decode(b)) for b in payload["buffers"].values())
    assert size < 2 * 4 * COLUMNS * 40


@pytest.mark.parametrize("mark", ["line", "points"])
def test_a_plot_rebuilt_starts_over(mark: str):
    if mark == "line":
        plot = Trellis(walk(), wrap="s").line(x="t", y="v")
        plot._detail(view(plot, (1000, 2000)))
    else:
        plot = Trellis(cloud()).points(x="x", y="y")
        plot._detail(view(plot, (0, 0.05), (0, 0.05)))
    assert plot._detail_buffers.data
    plot.title = "again"
    plot._changed()
    spec, _ = plot._scene()
    assert plot._detail_buffers.data == {}
    assert plot._shown_layers == spec["layers"]
