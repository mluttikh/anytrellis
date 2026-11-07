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


def test_fit_y():
    t = Trellis(SMALL, wrap="g").points(x="t", y="v")
    assert t._scene()[0]["fit_y"] is False
    f = Trellis(SMALL, wrap="g", fit_y=True).points(x="t", y="v")
    assert f._scene()[0]["fit_y"] is True
    assert '"fit_y": true' in f.to_html()


# ---- selecting ----------------------------------------------------------------------------


def test_select_points_in_every_panel():
    t = Trellis(SMALL, wrap="g").points(x="t", y="v")
    assert t.selection is None
    assert len(t.selected()["v"]) == 0
    t.select(x=(0.5, 1.5))
    assert list(t.selected()["v"]) == [2.0, 20.0, 200.0]  # the brush holds in all panels
    t.select(x=(0.5, 1.5), y=(0, 50))
    assert list(t.selected()["v"]) == [2.0, 20.0]
    assert t.selection == {"x": (0.5, 1.5), "y": (0.0, 50.0), "color": None, "panel": None}
    t.select()
    assert t.selection is None


def test_select_line_segments_by_either_end():
    t = Trellis(SMALL, wrap="g").line(x="t", y="v")
    t.select(y=(15, 25))  # only the end of panel b's segment
    assert list(t.selected()["v"]) == [20.0]


def test_select_bars_that_overlap():
    t = Trellis(SMALL).bars(x="h", y="v", position="dodge")
    t.select(x="y")
    assert t.selection == {"x": ["y"], "y": None, "color": None, "panel": None}
    assert sorted(t.selected()["v"]) == [2.0, 20.0]


def test_select_times_as_datetimes():
    data = {"t": np.array(["2026-03-01", "2026-03-02", "2026-03-03"], dtype="datetime64[ms]"),
            "v": [1.0, 2.0, 3.0]}  # fmt: skip
    t = Trellis(data).points(x="t", y="v")
    t.select(x=("2026-03-01T12:00", "2026-03-03"))
    assert list(t.selected()["v"]) == [2.0, 3.0]
    assert t.selection is not None
    lo, hi = t.selection["x"]
    assert lo == np.datetime64("2026-03-01T12:00", "ms")
    assert hi == np.datetime64("2026-03-03", "ms")


def test_link_grows_the_selection_across_panels():
    data = {"year": [1, 1, 2, 2], "country": ["NL", "BE", "NL", "BE"],
            "x": [1.0, 5.0, 9.0, 2.0], "y": [1.0, 1.0, 1.0, 1.0]}  # fmt: skip
    t = Trellis(data, wrap="year", link="country").points(x="x", y="y")
    t.select(x=(0, 3))  # NL in year 1, BE in year 2
    assert sorted(t.selected()["country"]) == ["BE", "BE", "NL", "NL"]
    t.select(x=(0, 3), panel="1")  # NL in year 1 only, followed into year 2
    assert sorted(t.selected()["country"]) == ["NL", "NL"]
    assert t.selection is not None
    assert t.selection["panel"] == "1"
    with pytest.raises(ValueError, match="no panel '3'"):
        t.select(x=(0, 3), panel=3)
    spec, _ = scene(t)
    keys = array(t, spec["layers"][0]["link"])
    assert keys.dtype == np.uint32
    assert len(set(keys.tolist())) == 2
    plain = Trellis(data, wrap="year").points(x="x", y="y").select(x=(0, 3))
    assert sorted(plain.selected()["country"]) == ["BE", "NL"]
    with pytest.raises(ValueError, match="no layer's data has these columns"):
        scene(Trellis(data, link="city").points(x="x", y="y"))


def test_selected_keeps_the_table_kind_and_picks_layers():
    t = Trellis(pl.DataFrame(SMALL), wrap="g").points(x="t", y="v").line(x="t", y="v")
    t.select(x=(0.5, 1.5))
    out = t.selected("line")
    assert isinstance(out, pl.DataFrame)
    assert out["v"].to_list() == [2.0, 20.0, 200.0]
    assert t.selected(1).height == 3
    with pytest.raises(ValueError, match="no layer 'bars'"):
        t.selected("bars")


def test_selection_syncs_with_the_widget_and_html():
    t = Trellis(SMALL, wrap="g").points(x="t", y="v").select(x=(0.5, 1.5))
    w = t.widget
    assert w.selection == {"x": [0.5, 1.5], "y": None, "panel": None}
    w.selection = {"x": None, "y": [0.0, 5.0]}  # drawn in the browser
    assert list(t.selected()["v"]) == [1.0, 2.0]
    assert '"selection": {"x": null, "y": [0.0, 5.0]}' in t.to_html()
    t.select()
    assert w.selection is None


# ---- area, rect, text ---------------------------------------------------------------------


def base_of(t: Trellis, layer: int = 0) -> np.ndarray:
    spec, _ = scene(t)
    return array(t, spec["layers"][layer]["base"])


def test_area_stacks_series_at_equal_x():
    data = {"t": [0.0, 1.0, 0.0, 1.0], "v": [1.0, 2.0, 10.0, 20.0], "s": ["a", "a", "b", "b"]}
    t = Trellis(data).area(x="t", y="v", color="s")
    tops = coords(t)[:, [1, 3]]
    bases = base_of(t)
    # a from 0 to (1, 2); b on top of it: from (1, 2) to (11, 22)
    assert sorted(map(tuple, tops.tolist())) == [(1.0, 2.0), (11.0, 22.0)]
    assert sorted(map(tuple, bases.tolist())) == [(0.0, 0.0), (1.0, 2.0)]
    spec, _ = scene(t)
    assert spec["panels"][0]["y"][0] == 0.0  # the base at 0, unpadded


def test_area_splits_where_it_crosses_its_base():
    data = {"t": [0.0, 2.0], "v": [1.0, -1.0]}
    t = Trellis(data).area(x="t", y="v", position="identity")
    c = coords(t)
    assert len(c) == 2  # two trapezoids meeting at x = 1
    assert sorted(c[:, 2].tolist()) == [1.0, 2.0]
    assert np.allclose(base_of(t), 0.0)


def test_rect_tiles_a_step_wide_or_to_x2():
    data = {"x": [0.0, 2.0, 4.0], "y": [0.0, 0.0, 0.0], "v": [1.0, 2.0, 3.0]}
    c = coords(Trellis(data).rect(x="x", y="y", color="v"))
    assert c[0].tolist() == [-1.0, -0.5, 1.0, 0.5]  # x step 2, y step 1 (one value)
    band = {"a": ["p", "q"], "b": ["r", "r"], "v": [1.0, 2.0]}
    c = coords(Trellis(band).rect(x="a", y="b", color="v", width=0.9))
    assert np.allclose(c[0], [-0.45, -0.5, 0.45, 0.5])
    spans = {"x": [0.0], "x2": [3.0], "y": [1.0], "y2": [5.0]}
    assert coords(Trellis(spans).rect(x="x", y="y", x2="x2", y2="y2"))[0].tolist() == [0, 1, 3, 5]


def test_rect_tooltip_shows_a_number_colour():
    data = {"x": ["a", "b"], "y": ["c", "c"], "v": [1.5, 2.5]}
    t = Trellis(data).rect(x="x", y="y", color="v")
    spec, _ = scene(t)
    assert spec["layers"][0]["tooltip"] is True
    assert t._tooltip(0, 1) == [["v", "2.5"]]


def test_brush_selects_rects_it_overlaps_and_area_segments_with_an_end_inside():
    cells = {"x": [0.0, 2.0, 4.0], "y": [0.0, 0.0, 0.0], "v": [1.0, 2.0, 3.0]}
    t = Trellis(cells).rect(x="x", y="y", color="v")
    t.select(x=(0.5, 0.9))  # inside the first cell (it spans -1..1), not at its centre
    assert t.selected()["x"].tolist() == [0.0]
    series = {"x": [0.0, 1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0, 4.0]}
    a = Trellis(series).area(x="x", y="y")
    a.select(x=(0.9, 1.1))  # x = 1: the ends of two segments, one row
    assert a.selected()["x"].tolist() == [1.0]


def test_text_sends_labels_as_utf8():
    data = {"x": [1.0, 2.0], "y": [1.0, 2.0], "name": ["Zürich", "Oslo"]}
    t = Trellis(data).text(x="x", y="y", text="name", align="left", dx=4)
    spec, buffers = scene(t)
    layer = spec["layers"][0]
    assert layer["type"] == "text"
    assert layer["align"] == "left"
    raw = buffers.data[layer["labels"]["id"]]
    offsets = np.frombuffer(buffers.data[layer["offsets"]["id"]], dtype=np.uint32)
    labels = [raw[offsets[i] : offsets[i + 1]].decode("utf-8") for i in range(2)]
    assert labels == ["Zürich", "Oslo"]
    with pytest.raises(ValueError, match="align must be"):
        Trellis(data).text(x="x", y="y", text="name", align="middle")


# ---- summaries: hist, box, density -----------------------------------------------------------

RNG = np.random.default_rng(7)
DIST = {
    "g": ["a"] * 200 + ["b"] * 100,
    "c": (["p", "q"] * 150),
    "v": np.r_[RNG.normal(10, 2, 200), RNG.normal(14, 1, 100)],
}


def test_hist_shares_round_bins_across_panels():
    t = Trellis(DIST, wrap="g").hist(x="v", bins=10)
    c = coords(t)
    widths = np.round(c[:, 2] - c[:, 0], 9)
    assert len(set(widths)) == 1  # one width everywhere
    w = widths[0]
    assert w / 10 ** np.floor(np.log10(w)) in (1, 2, 2.5, 5)
    assert np.allclose(np.round(c[:, 0] / w), c[:, 0] / w)  # edges at multiples of it
    spec, _ = scene(t)
    assert spec["layers"][0]["type"] == "bars"
    assert spec["y"]["title"] == "count"
    counts = c[:, 3] - c[:, 1]
    st = starts(t)
    assert counts[st[0] : st[1]].sum() == 200
    assert counts[st[1] : st[2]].sum() == 100


def test_hist_stacks_colours_and_normalises_per_panel():
    t = Trellis(DIST, wrap="g").hist(x="v", color="c", bins=8, stat="percent")
    c = coords(t)
    st = starts(t)
    heights = c[:, 3] - c[:, 1]
    assert np.isclose(heights[st[0] : st[1]].sum(), 100)
    assert np.isclose(heights[st[1] : st[2]].sum(), 100)
    # stacked: at each bin, the second colour starts where the first ends
    first = c[st[0] : st[1]]
    for x0 in np.unique(first[:, 0]):
        here = first[first[:, 0] == x0]
        if len(here) == 2:
            assert np.isclose(here[:, 1].max(), here[:, 3].min())
    d = Trellis(DIST, wrap="g").hist(x="v", bins=8, stat="density")
    dc = coords(d)
    area = ((dc[:, 2] - dc[:, 0]) * (dc[:, 3] - dc[:, 1]))[: starts(d)[1]].sum()
    assert np.isclose(area, 1)


def test_hist_binwidth_edges_and_categories():
    data = {"v": [0.0, 0.1, 0.9, 1.0, 2.5]}
    c = coords(Trellis(data).hist(x="v", binwidth=1))
    assert c[:, 0].tolist() == [0.0, 1.0, 2.0]  # the 1.0 counts in [1, 2)
    assert (c[:, 3] - c[:, 1]).tolist() == [3.0, 1.0, 1.0]
    c = coords(Trellis(data).hist(x="v", bins=[0, 1, 3]))
    assert (c[:, 3] - c[:, 1]).tolist() == [3.0, 2.0]  # the last edge is in the last bin
    cats = {"k": ["x", "y", "y", "z", "z", "z"]}
    t = Trellis(cats).hist(x="k")
    spec, _ = scene(t)
    assert spec["x"]["kind"] == "band"
    c = coords(t)
    assert (c[:, 3] - c[:, 1]).tolist() == [1.0, 2.0, 3.0]
    assert np.allclose(c[:, 2] - c[:, 0], 0.8)
    with pytest.raises(ValueError, match="category column"):
        Trellis(DIST).hist(x="v", color="v")._scene()


def test_hist_context_counts_the_other_panels():
    t = Trellis(DIST, wrap="g").hist(x="v", facet="exclude", bins=10).hist(x="v", bins=10)
    spec, _ = scene(t)
    assert spec["layers"][0]["context"] is True
    c = coords(t, 0)
    st = starts(t, 0)
    assert (c[st[0] : st[1], 3] - c[st[0] : st[1], 1]).sum() == 100  # in a: b's rows


def test_hist_tooltip_and_selection_are_of_bins_and_their_rows():
    data = {"v": [0.0, 0.5, 1.5, 2.5, 2.6], "name": list("abcde")}
    t = Trellis(data).hist(x="v", binwidth=1)
    spec, _ = scene(t)
    layer = spec["layers"][0]
    assert layer["hide"] == ["x", "y"]
    assert layer["tips"]["names"] == ["bin", "count"]
    assert layer["tips"]["values"][0] == ["0 – 1", "2"]
    t.select(x=(2.2, 2.4))  # meets the bin [2, 3)
    assert list(t.selected()["name"]) == ["d", "e"]


def test_box_quartiles_whiskers_and_outliers():
    values = np.r_[np.arange(1.0, 12.0), 40.0]  # 40: beyond the whiskers
    data = {"k": ["a"] * len(values), "v": values, "id": [f"r{i}" for i in range(len(values))]}
    t = Trellis(data).box(x="k", y="v", tooltip=["id"])
    spec, _ = scene(t)
    assert [lr["type"] for lr in spec["layers"]] == ["rect", "line", "points"]
    q1, med, q3 = np.percentile(values, [25, 50, 75])
    body = coords(t, 0)[0]
    assert np.allclose([body[1], body[3]], [q1, q3])
    assert np.allclose(body[2] - body[0], 0.8)
    segments = coords(t, 1)
    assert len(segments) == 7
    assert np.isclose(segments[:, [1, 3]].max(), 11.0)  # the upper whisker: the furthest inside
    assert any(np.allclose(s[[1, 3]], [med, med]) for s in segments)  # the median
    points = coords(t, 2)
    assert points[:, 1].tolist() == [40.0]
    assert t._tooltip(2, 0) == [["id", "r11"]]
    tips = spec["layers"][0]["tips"]
    assert tips["names"] == ["k", "n", "median", "q1", "q3", "whiskers"]
    assert tips["values"][0][:3] == ["a", "12", "6.5"]


def test_box_dodges_colours_and_goes_horizontal():
    t = Trellis(DIST).box(x="g", y="v", color="c")
    body = coords(t, 0)
    assert len(body) == 4  # 2 positions x 2 colours
    centres = np.sort((body[:, 0] + body[:, 2]) / 2)
    assert np.allclose(centres, [-0.2, 0.2, 0.8, 1.2])
    h = Trellis(DIST).box(x="v", y="g")
    spec, _ = scene(h)
    assert spec["y"]["kind"] == "band"
    assert spec["x"]["kind"] == "number"
    hb = coords(h, 0)
    assert np.allclose(hb[:, 3] - hb[:, 1], 0.8)  # the width is along y
    with pytest.raises(ValueError, match="must be numbers"):
        Trellis(DIST).box(x="g", y="c")._scene()


def test_box_selects_whole_boxes_and_their_rows():
    t = Trellis(DIST).box(x="g", y="v")
    spec, _ = scene(t)
    assert spec["layers"][0]["family"] == spec["layers"][1]["family"] == 0
    assert spec["layers"][2]["family"] is None
    t.select(x=["b"])
    rows = t.selected()
    assert set(rows["g"]) == {"b"}
    assert len(rows["g"]) == 100  # the box's rows, not one per box


def test_density_integrates_to_one_on_a_shared_grid():
    t = Trellis(DIST, wrap="g").density(x="v", fill=True)
    spec, _ = scene(t)
    assert [lr["type"] for lr in spec["layers"]] == ["area", "line"]
    assert spec["y"]["title"] == "density"
    assert spec["panels"][0]["y"][0] == 0.0  # from zero
    c = coords(t, 1)
    st = starts(t, 1)
    for p in range(2):
        seg = c[st[p] : st[p + 1]]
        area = ((seg[:, 2] - seg[:, 0]) * (seg[:, 1] + seg[:, 3]) / 2).sum()
        assert abs(area - 1) < 0.01
    step_a = np.diff(np.unique(c[st[0] : st[1], 0]))[0]
    step_b = np.diff(np.unique(c[st[1] : st[2], 0]))[0]
    assert np.isclose(step_a, step_b)  # one grid
    assert np.allclose(base_of(t, 0), 0)
    t.select(x=(9.0, 9.5), panel="a")
    rows = t.selected()
    assert set(rows["g"]) == {"a"}
    assert np.min(rows["v"]) >= 8.9
    assert np.max(rows["v"]) <= 9.7


def test_density_bandwidth_and_errors():
    narrow = coords(Trellis(DIST).density(x="v", bw_adjust=0.3))[:, 1].max()
    wide = coords(Trellis(DIST).density(x="v", bw_adjust=3))[:, 1].max()
    assert narrow > wide
    with pytest.raises(ValueError, match="numbers or times"):
        Trellis(DIST).density(x="g")._scene()


# ---- log scales -----------------------------------------------------------------------------


def test_log_axis_sends_log10_values_and_leaves_out_non_positive():
    data = {"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 100.0, 0.0, -5.0], "name": list("abcd")}
    t = Trellis(data, y_scale="log").points(x="x", y="y", tooltip=["name"])
    spec, _ = scene(t)
    assert spec["y"]["kind"] == "log"
    assert spec["x"]["kind"] == "number"
    c = coords(t)
    assert c[:, 1].tolist() == [0.0, 2.0]  # 0 and -5 left out
    assert t._tooltip(0, 1) == [["name", "b"]]
    t.select(y=(50, 200))  # values, not logs
    assert list(t.selected()["name"]) == ["b"]
    lo, hi = t.selection["y"]  # ty: ignore[not-subscriptable]
    assert np.isclose(lo, 50)
    assert np.isclose(hi, 200)


def test_log_scale_method_rules_and_errors():
    data = {"x": [1.0, 10.0, 1000.0], "y": [1.0, 2.0, 3.0]}
    t = Trellis(data).line(x="x", y="y").rule(x=100).scale(x="log")
    spec, _ = scene(t)
    assert spec["x"]["kind"] == "log"
    assert spec["layers"][1]["values"] == [2.0]
    assert spec["panels"][0]["x"][0] < 0 < 3 < spec["panels"][0]["x"][1]
    with pytest.raises(ValueError, match="draws from zero"):
        Trellis(data, y_scale="log").bars(x="x", y="y")._scene()
    with pytest.raises(ValueError, match="needs numbers"):
        Trellis({"x": ["a", "b"], "y": [1.0, 2.0]}, x_scale="log").points(x="x", y="y")._scene()
    with pytest.raises(ValueError, match="scale is one of"):
        Trellis(data, x_scale="sqrt")
    with pytest.raises(ValueError, match="not on a log axis"):
        Trellis(data, x_scale="log").points(x="x", y="y").rule(x=0)._scene()


def test_summaries_on_a_log_axis_are_computed_on_it():
    data = {"g": ["a"] * 4, "v": [1.0, 10.0, 100.0, 1000.0]}
    t = Trellis(data, x_scale="log").hist(x="v", binwidth=1)  # a decade per bin
    c = coords(t)
    assert c[:, 0].tolist() == [0.0, 1.0, 2.0]
    assert (c[:, 3] - c[:, 1]).tolist() == [1.0, 1.0, 2.0]
    spec, _ = scene(t)
    assert spec["layers"][0]["tips"]["values"][0][0] == "1 – 10"
    b = Trellis(data, y_scale="log").box(x="g", y="v")
    body = coords(b, 0)[0]
    assert np.allclose([body[1], body[3]], [0.75, 2.25])  # quartiles of the logs
    tips = scene(b)[0]["layers"][0]["tips"]["values"][0]
    assert tips[2] == f"{10**1.5:.6g}"  # the median as a value


# ---- bands and smooth fits -------------------------------------------------------------------


def test_band_draws_between_two_lines_and_splits_where_they_cross():
    data = {"x": [0.0, 1.0, 2.0], "lo": [0.0, 1.0, 3.0], "hi": [2.0, 3.0, 1.0], "k": list("abc")}
    t = Trellis(data).band(x="x", ymin="lo", ymax="hi", tooltip=["k"])
    spec, _ = scene(t)
    layer = spec["layers"][0]
    assert layer["type"] == "band"
    assert layer["hide"] == ["y"]
    c = coords(t)
    base = base_of(t)
    assert len(c) == 3  # the second segment crosses at x = 1.5
    assert c[0].tolist() == [0.0, 2.0, 1.0, 3.0]
    assert base[0].tolist() == [0.0, 1.0]
    assert np.isclose(c[1, 2], 1.5)
    assert t._tooltip(0, 0) == [["lo", "0"], ["hi", "2"], ["k", "a"]]
    assert spec["panels"][0]["y"][0] < 0  # padded, not from zero
    t.select(x=(0.2, 0.4), y=(1.5, 1.6))  # inside the band, away from both lines
    assert list(t.selected()["k"]) == ["a", "b"]


def test_smooth_linear_matches_least_squares_with_a_t_band():
    rng = np.random.default_rng(3)
    x = np.linspace(0, 10, 40)
    y = 2 + 0.5 * x + rng.normal(0, 1, 40)
    t = Trellis({"x": x, "y": y}).smooth(x="x", y="y", method="linear", n=11)
    spec, _ = scene(t)
    assert [lr["type"] for lr in spec["layers"]] == ["band", "line"]
    line = coords(t, 1)
    slope, intercept = np.polyfit(x, y, 1)
    assert np.allclose(line[:, 1], intercept + slope * line[:, 0])
    band, base = coords(t, 0), base_of(t, 0)
    resid = y - (intercept + slope * x)
    sigma = np.sqrt((resid**2).sum() / 38)
    se = sigma * np.sqrt(1 / 40 + (0 - x.mean()) ** 2 / ((x - x.mean()) ** 2).sum())
    assert np.isclose(band[0, 1] - line[0, 1], 2.0244 * se, rtol=1e-3)  # t(0.975, 38)
    assert np.isclose(line[0, 1] - base[0, 0], 2.0244 * se, rtol=1e-3)
    assert spec["layers"][1]["tips"]["names"] == ["95% interval"]


def test_smooth_loess_follows_a_curve_and_selects_its_rows():
    x = np.linspace(0, 2 * np.pi, 200)
    data = {"g": ["a"] * 200, "x": x, "y": np.sin(x)}
    t = Trellis(data, wrap="g").smooth(x="x", y="y", span=0.2, se=False)
    spec, _ = scene(t)
    assert [lr["type"] for lr in spec["layers"]] == ["line"]
    c = coords(t)
    assert np.abs(c[:, 1] - np.sin(c[:, 0])).max() < 0.04  # a local line flattens the crests
    t.select(x=(1.0, 1.2))
    rows = t.selected()
    assert rows["x"].min() >= 0.9
    assert rows["x"].max() <= 1.4
    with pytest.raises(ValueError, match="numbers or times"):
        Trellis({"x": ["a", "b"], "y": [1.0, 2.0]}).smooth(x="x", y="y")._scene()


def test_smooth_per_colour_fullrange_and_on_a_log_axis():
    data = {"x": [1.0, 2, 3, 1, 2, 3, 10], "y": [1.0, 2, 3, 3, 2, 1, 0.5], "c": list("aaabbbb")}
    t = Trellis(data).smooth(x="x", y="y", color="c", method="linear", fullrange=True, n=5)
    line = coords(t, 1)
    assert len(line) == 8  # two lines of 4 segments
    assert line[:, 0].min() == 1.0
    assert line[:, 2].max() == 10.0  # the colour a's line too
    lg = Trellis({"x": [1.0, 10, 100, 1000], "y": [1.0, 2, 3, 4]}, x_scale="log")
    lg.smooth(x="x", y="y", method="linear", se=False)
    c = coords(lg)
    assert np.allclose(np.diff(c[:, 3]) / np.diff(c[:, 2]), 1.0)  # a line in log10(x)


# ---- legend selection ---------------------------------------------------------------------


def test_select_color_picks_the_marks_of_those_colours() -> None:
    t = Trellis(SMALL).points(x="t", y="v", color="h")
    t.select(color="y")
    assert t.selected()["v"].tolist() == [2.0, 20.0]
    assert t.selection == {"x": None, "y": None, "color": ["y"], "panel": None}
    t.select(x=(0.5, 1.5), color=["x"])  # both: in the range and of the colour
    assert t.selected()["v"].tolist() == [200.0]
    legends = t._scene()[0]["legends"]
    level = legends[0]["labels"].index("x")
    brush = t._current_selection()
    assert brush is not None
    assert brush["legend"] == {"index": 0, "levels": [level]}


def test_legend_selection_from_the_browser_and_other_layers() -> None:
    t = (Trellis(SMALL, wrap="g").points(x="t", y="v", color="h")
         .line(x="t", y="v", name="plain"))  # fmt: skip
    legend = {"index": 0, "levels": [1]}  # the second of h's levels: "y"
    t.widget.selection = {"x": None, "y": None, "panel": None, "legend": legend}
    assert t.selected()["h"].tolist() == ["y", "y"]
    assert t.selected("plain")["v"].tolist() == []  # not coloured by h: none of its marks


def test_legend_selects_a_stacked_histograms_rows() -> None:
    data = {"v": [1.0, 1.2, 2.5, 2.7, 3.1], "k": ["p", "q", "p", "q", "q"]}
    t = Trellis(data).hist(x="v", color="k", binwidth=1)
    t.select(color="q")
    assert sorted(t.selected()["v"].tolist()) == [1.2, 2.7, 3.1]


def test_select_color_errors() -> None:
    with pytest.raises(ValueError, match="no colour legend"):
        Trellis(SMALL).points(x="t", y="v", color="h").select(color="nope")
    with pytest.raises(ValueError, match="needs a category colour"):
        Trellis(SMALL).points(x="t", y="v").select(color="x")
