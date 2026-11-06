"""The spec a Trellis sends to the browser: panels, scales, geometry and the protocol."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
import pytest

from anytrellis import Trellis
from anytrellis.synthetic import sales, sensors
from anytrellis.widget import CHUNK_BYTES

DTYPES = {"float64": np.float64, "float32": np.float32, "uint32": np.uint32, "int32": np.int32,
          "uint16": np.uint16, "uint8": np.uint8}  # fmt: skip


def scene(t: Trellis) -> tuple[dict[str, Any], Any]:
    return t._scene()


def array(t: Trellis, ref: dict[str, Any]) -> np.ndarray:
    _, buffers = scene(t)
    a = np.frombuffer(buffers.data[ref["id"]], dtype=DTYPES[ref["dtype"]])
    return a.reshape(-1, ref["components"]) if ref["components"] > 1 else a


def coords(t: Trellis, layer: int = 0) -> np.ndarray:
    spec, _ = scene(t)
    return array(t, spec["layers"][layer]["coords"])


def starts(t: Trellis, layer: int = 0) -> np.ndarray:
    spec, _ = scene(t)
    return array(t, spec["layers"][layer]["starts"])


SMALL = {
    "g": ["a", "a", "b", "b", "c", "c"],
    "h": ["x", "y", "x", "y", "x", "x"],
    "t": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    "v": [1.0, 2.0, 10.0, 20.0, 100.0, 200.0],
}


# ---- facets -------------------------------------------------------------------------------


def test_single_panel_without_facets() -> None:
    spec, _ = scene(Trellis(SMALL).line(x="t", y="v"))
    assert spec["grid"]["kind"] == "single"
    assert len(spec["panels"]) == 1


def test_grid_keeps_every_cell_and_labels() -> None:
    spec, _ = scene(Trellis(SMALL, row="g", col="h").points(x="t", y="v"))
    g = spec["grid"]
    assert (g["kind"], g["rows"], g["cols"]) == ("grid", 3, 2)
    assert g["row_labels"] == ["a", "b", "c"]
    assert g["col_labels"] == ["x", "y"]
    assert len(spec["panels"]) == 6  # c/y has no data but keeps its cell


def test_wrap_uses_present_levels_and_square_layout() -> None:
    spec, _ = scene(Trellis(sensors(stations=5), wrap="station").line(x="time", y="temp"))
    assert spec["grid"]["kind"] == "wrap"
    assert spec["grid"]["cols"] == 3
    assert [p["label"] for p in spec["panels"]] == [f"station {i}" for i in range(1, 6)]
    assert [(p["row"], p["col"]) for p in spec["panels"]][3:] == [(1, 0), (1, 1)]


def test_wrap_cols_and_multiple_columns() -> None:
    spec, _ = scene(Trellis(SMALL, wrap=["g", "h"], cols=5).points(x="t", y="v"))
    assert spec["grid"]["cols"] == 5
    assert spec["panels"][0]["label"] == "a · x"
    assert spec["panels"][0]["keys"] == ["a", "x"]
    assert len(spec["panels"]) == 5  # c/y is absent


def test_order_by_given_levels_and_by_summary() -> None:
    t = Trellis(SMALL, wrap="g").points(x="t", y="v").order("g", ["c"])
    assert [p["label"] for p in scene(t)[0]["panels"]] == ["c", "a", "b"]
    t = (
        Trellis(SMALL, wrap="g")
        .points(x="t", y="v")
        .order("g", by="median", of="v", descending=True)
    )
    assert [p["label"] for p in scene(t)[0]["panels"]] == ["c", "b", "a"]


def test_order_applies_to_band_axes_and_colours() -> None:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    t = Trellis(sales(), wrap="store").bars(x="month", y="units", color="product")
    assert scene(t)[0]["x"]["levels"][:3] == ["Apr", "Aug", "Dec"]  # alphabetical by default
    t.order("month", months).order("product", ["tea"])
    spec, _ = scene(t)
    assert spec["x"]["levels"] == months
    assert spec["legends"][0]["labels"] == ["tea", "cocoa", "coffee"]
    t.order("month", by="sum", of="units", descending=True)
    ranked = scene(t)[0]["x"]["levels"]
    totals = {m: sum(u for mm, u in zip(sales()["month"], sales()["units"], strict=True) if mm == m)
              for m in months}  # fmt: skip
    assert ranked == sorted(months, key=lambda m: -totals[m])


def test_panels_hold_their_rows() -> None:
    t = Trellis(SMALL, wrap="g").points(x="t", y="v")
    s = starts(t)
    c = coords(t)
    assert list(s) == [0, 2, 4, 6]
    assert sorted(c[s[2] : s[3], 1]) == [100.0, 200.0]


def test_partial_facet_columns_is_an_error() -> None:
    t = Trellis(SMALL, row="g", col="h").points({"g": ["a"], "t": [0.0], "v": [1.0]}, x="t", y="v")
    with pytest.raises(ValueError, match="some facet columns"):
        scene(t)


def test_layer_without_facet_columns_is_in_every_panel() -> None:
    t = (
        Trellis(SMALL, wrap="g")
        .points(x="t", y="v")
        .line({"t": [0.0, 1.0], "v": [5.0, 5.0]}, x="t", y="v")
    )
    assert list(starts(t, 1)) == [0, 1, 2, 3]  # one segment per panel


def test_exclude_draws_the_other_panels_rows_as_context() -> None:
    t = (
        Trellis(SMALL, wrap="g")
        .points(x="t", y="v", facet="exclude", name="ctx")
        .points(x="t", y="v")
    )
    spec, _ = scene(t)
    assert spec["layers"][0]["context"] is True
    assert spec["layers"][1]["context"] is False
    s, c = starts(t, 0), coords(t, 0)
    assert list(np.diff(s)) == [4, 4, 4]
    assert 1.0 not in c[s[0] : s[1], 1]  # panel a shows b and c only


# ---- scales -------------------------------------------------------------------------------


def test_shared_scales_have_one_group_and_one_domain() -> None:
    spec, _ = scene(Trellis(SMALL, wrap="g").points(x="t", y="v"))
    assert {p["yg"] for p in spec["panels"]} == {0}
    assert len({tuple(p["y"]) for p in spec["panels"]}) == 1


def test_free_y_gives_each_panel_its_domain() -> None:
    spec, _ = scene(Trellis(SMALL, wrap="g", share_y=False).points(x="t", y="v"))
    assert [p["yg"] for p in spec["panels"]] == [0, 1, 2]
    lo, hi = spec["panels"][2]["y"]
    assert lo < 100 < 200 < hi
    assert hi - lo < 200  # not the shared range


def test_share_by_row() -> None:
    spec, _ = scene(Trellis(SMALL, row="g", col="h").points(x="t", y="v").share(y="row"))
    assert [p["yg"] for p in spec["panels"]] == [0, 0, 1, 1, 2, 2]


def test_bars_domain_starts_at_zero() -> None:
    spec, _ = scene(Trellis(sales()).bars(x="month", y="units"))
    assert spec["panels"][0]["y"][0] == 0.0
    assert spec["x"]["kind"] == "band"
    assert spec["panels"][0]["x"] == [-0.5, 11.5]


def test_time_axis_is_relative_to_its_origin() -> None:
    spec, _ = scene(Trellis(sensors(stations=1, sensors=1, hours=48)).line(x="time", y="temp"))
    x = spec["x"]
    assert x["kind"] == "time"
    start = float(np.datetime64("2026-03-01T00:00", "ms").astype(np.int64))
    assert start - 86_400_000 < x["origin"] <= start  # the padded domain's low end
    lo, hi = spec["panels"][0]["x"]
    assert abs(lo) < 1e8
    assert abs(hi) < 1e9


def test_mixed_axis_kinds_are_an_error() -> None:
    t = Trellis(SMALL).points(x="t", y="v").points(x="g", y="v")
    with pytest.raises(ValueError, match="different kinds"):
        scene(t)


# ---- geometry -----------------------------------------------------------------------------


def test_line_breaks_at_missing_values_and_sorts_by_x() -> None:
    data = {"x": [3.0, 0.0, 1.0, 2.0, 4.0], "y": [3.0, 0.0, 1.0, np.nan, 4.0]}
    c = coords(Trellis(data).line(x="x", y="y"))
    segments = {(a, b) for a, _, b, _ in c}
    assert (0.0, 1.0) in segments
    assert (3.0, 4.0) in segments
    assert not any(np.isnan(c).any(axis=1))
    assert len(c) == 2


def test_isolated_point_of_a_line_is_a_dot() -> None:
    data = {"x": [0.0, 1.0, 2.0], "y": [1.0, np.nan, 3.0]}
    c = coords(Trellis(data).line(x="x", y="y"))
    assert len(c) == 2
    assert all(row[0] == row[2] and row[1] == row[3] for row in c)


def test_lines_per_colour_and_group() -> None:
    df = sensors(stations=2, sensors=2, hours=10)
    one = coords(Trellis(df).line(x="time", y="temp"))
    by_group = coords(Trellis(df).line(x="time", y="temp", group=["station", "sensor"]))
    assert len(by_group) == 4 * 9
    assert len(one) == 39  # a single series through all 40 rows


def test_stacked_bars_go_up_and_down() -> None:
    data = {"x": ["a", "a", "a"], "y": [2.0, 3.0, -1.0], "c": ["p", "q", "r"]}
    c = coords(Trellis(data).bars(x="x", y="y", color="c"))
    spans = sorted((float(r[1]), float(r[3])) for r in c)
    assert spans == [(0.0, -1.0), (0.0, 2.0), (2.0, 5.0)]


def test_dodged_bars_sit_side_by_side() -> None:
    data = {"x": ["a", "a"], "y": [2.0, 3.0], "c": ["p", "q"]}
    c = coords(Trellis(data).bars(x="x", y="y", color="c", position="dodge"))
    assert c[0][2] <= c[1][0] + 1e-9
    assert all(r[1] == 0 for r in c)


def test_category_colour_sends_codes_and_a_legend() -> None:
    t = Trellis(SMALL).points(x="t", y="v", color="h")
    spec, _ = scene(t)
    layer = spec["layers"][0]
    assert layer["color"]["legend"] == 0
    assert spec["legends"][0]["labels"] == ["x", "y"]
    assert set(array(t, layer["color"]["codes"])) == {0, 1}


def test_numeric_colour_has_a_gradient_legend() -> None:
    spec, _ = scene(Trellis(SMALL).points(x="t", y="v", color="v"))
    lg = spec["legends"][0]
    assert lg["kind"] == "number"
    assert (lg["lo"], lg["hi"]) == (1.0, 200.0)


def test_rules_on_numbers_times_and_bands() -> None:
    t = (Trellis(sales()).bars(x="month", y="units")
         .rule(x="Mar").rule(y=100, dash=[4, 2]))  # fmt: skip
    spec, _ = scene(t)
    rx, ry = spec["layers"][1], spec["layers"][2]
    assert rx["axis"] == "x"
    assert rx["values"] == [spec["x"]["levels"].index("Mar")]
    assert ry["values"] == [100.0]
    assert ry["dash"] == [4, 2]
    scene(t)  # building again keeps working (rules are not changed in place)
    with pytest.raises(ValueError, match="not a category"):
        scene(Trellis(sales()).bars(x="month", y="units").rule(x="Smarch"))


# ---- input tables -------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["dict", "pandas", "polars", "pyarrow"])
def test_tables_of_every_kind_give_the_same_spec(kind: str) -> None:
    df = sensors(stations=2, sensors=2, hours=24)
    data: Any = {
        "dict": df,
        "pandas": pd.DataFrame(df),
        "polars": pl.DataFrame(df),
        "pyarrow": pa.table(df),
    }[kind]
    t = Trellis(data, wrap="station").line(x="time", y="temp", color="sensor")
    reference = Trellis(df, wrap="station").line(x="time", y="temp", color="sensor")
    assert np.array_equal(coords(t), coords(reference))
    assert scene(t)[0]["panels"] == scene(reference)[0]["panels"]


def test_time_zones_show_wall_clock_time() -> None:
    times = pd.date_range("2026-01-01", periods=3, freq="h", tz="Europe/Amsterdam")
    naive = pd.date_range("2026-01-01", periods=3, freq="h")
    a = Trellis(pd.DataFrame({"t": times, "v": [1.0, 2.0, 3.0]})).line(x="t", y="v")
    b = Trellis(pd.DataFrame({"t": naive, "v": [1.0, 2.0, 3.0]})).line(x="t", y="v")
    assert scene(a)[0]["x"]["origin"] == scene(b)[0]["x"]["origin"]


def test_declared_categories_keep_their_order() -> None:
    df = pl.DataFrame({"g": ["lo", "hi", "mid"], "v": [1.0, 2.0, 3.0], "t": [0.0, 0.0, 0.0]})
    df = df.with_columns(pl.col("g").cast(pl.Enum(["lo", "mid", "hi"])))
    spec, _ = scene(Trellis(df, wrap="g").points(x="t", y="v"))
    assert [p["label"] for p in spec["panels"]] == ["lo", "mid", "hi"]


def test_missing_categories_get_a_panel() -> None:
    spec, _ = scene(
        Trellis({"g": ["a", None], "t": [0.0, 1.0], "v": [1.0, 2.0]}, wrap="g").points(x="t", y="v")
    )
    assert [p["label"] for p in spec["panels"]] == ["a", "(missing)"]


def test_unknown_column_is_an_error() -> None:
    with pytest.raises(KeyError):
        Trellis(SMALL).line(x="t", y="nope")


# ---- widget and export --------------------------------------------------------------------


class Sent:
    def __init__(self) -> None:
        self.messages: list[tuple[dict[str, Any], list[bytes]]] = []

    def __call__(self, content: dict[str, Any], buffers: Any = None) -> None:
        self.messages.append((content, list(buffers or [])))


def test_widget_answers_need_with_chunks_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    t = Trellis(SMALL).points(x="t", y="v", tooltip=["g"])
    w = t.widget
    sent = Sent()
    monkeypatch.setattr(w, "send", sent)
    ref = w._spec["layers"][0]["coords"]
    w._on_msg(w, {"type": "need", "ids": [ref["id"], "nope"]}, [])
    (put, chunks), (missing, _) = sent.messages
    assert put["type"] == "put"
    assert put["chunks"] == 1
    assert put["byteLength"] == ref["byteLength"]
    assert len(chunks[0]) == ref["byteLength"]
    assert missing == {"type": "missing", "id": "nope"}
    w._on_msg(w, {"type": "tooltip", "request": 7, "layer": 0, "index": 0}, [])
    answer = sent.messages[-1][0]
    assert answer["request"] == 7
    assert answer["rows"][0][0] == "g"


def test_large_buffers_go_in_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    n = CHUNK_BYTES // 32 + 10  # 32 bytes per instance: just over one chunk
    t = Trellis({"x": np.arange(n, dtype=float), "y": np.zeros(n)}).points(x="x", y="y")
    w = t.widget
    sent = Sent()
    monkeypatch.setattr(w, "send", sent)
    w._on_msg(w, {"type": "need", "ids": [w._spec["layers"][0]["coords"]["id"]]}, [])
    assert [m["chunk"] for m, _ in sent.messages] == [0, 1]
    assert sum(len(b[0]) for _, b in sent.messages) == n * 32


def test_widget_follows_changes() -> None:
    t = Trellis(SMALL).points(x="t", y="v")
    w = t.widget
    t.line(x="t", y="v")
    assert [layer["type"] for layer in w._spec["layers"]] == ["points", "line"]


def test_spec_is_json_and_html_is_self_contained(tmp_path: Any) -> None:
    t = Trellis(SMALL, wrap="g", title="</script><b>x").points(x="t", y="v")
    spec, buffers = scene(t)
    json.dumps(spec)
    page = t.to_html()
    assert page.count("</script>") == 2  # the data's and the code's; the title is escaped
    assert all(ref in page for ref in buffers.data)
    path = t.save_html(tmp_path / "plot.html")
    assert path.read_text(encoding="utf-8") == page


def test_layer_names_are_unique() -> None:
    t = Trellis(SMALL).points(x="t", y="v")
    t.points(x="t", y="v")
    assert [layer["name"] for layer in scene(t)[0]["layers"]] == ["points", "points2"]
    with pytest.raises(ValueError, match="already named"):
        t.points(x="t", y="v", name="points")


# ---- opening a panel ----------------------------------------------------------------------


def test_panel_names_match_the_browser() -> None:
    assert Trellis(SMALL, wrap="g").points(x="t", y="v").panels() == ["a", "b", "c"]
    grid = Trellis(SMALL, row="g", col="h").points(x="t", y="v")
    assert grid.panels()[:3] == ["a · x", "a · y", "b · x"]


def test_open_and_close() -> None:
    t = Trellis(SMALL, row="g", col="h").points(x="t", y="v")
    assert t.focused is None
    assert t.open("b", "y").focused == "b · y"
    assert t.open("c · x").focused == "c · x"
    assert t.close().focused is None
    with pytest.raises(ValueError, match="no panel 'z'"):
        t.open("z")
    with pytest.raises(ValueError, match="one panel"):
        Trellis(SMALL).points(x="t", y="v").open("a")


def test_open_syncs_with_the_widget_both_ways() -> None:
    t = Trellis(SMALL, wrap="g").points(x="t", y="v").open("b")
    w = t.widget
    assert w.open_panel == "b"  # opened before the widget was made
    t.open("c")
    assert w.open_panel == "c"
    w.open_panel = "a"  # the browser opened one
    assert t.focused == "a"
    w.open_panel = None
    assert t.focused is None


def test_html_keeps_the_opened_panel() -> None:
    t = Trellis(SMALL, wrap="g").points(x="t", y="v").open("b")
    assert '"focus": "b"' in t.to_html()


def test_legend_position():
    t = Trellis(SMALL, wrap="g").points(x="t", y="v", color="h")
    assert t._scene()[0]["legend_position"] == "auto"
    b = Trellis(SMALL, wrap="g", legend="bottom").points(x="t", y="v", color="h")
    assert b._scene()[0]["legend_position"] == "bottom"
    assert '"legend_position": "bottom"' in b.to_html()
    with pytest.raises(ValueError, match="legend must be one of"):
        Trellis(SMALL, legend="left")
