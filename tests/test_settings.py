"""The settings panel and ``code()``: each setting is the property or method of the same
name, the panel's changes come from the browser as one message, and ``code()`` writes the
Python that makes the plot as it is now (run, it makes the same spec)."""

from __future__ import annotations

import json
import sys
from typing import Any

import duckdb
import numpy as np
import polars as pl
import pytest

import anytrellis as at
from anytrellis import Theme, Trellis
from anytrellis.datasets import load


class Sent:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def __call__(self, content: dict[str, Any], buffers: Any = None) -> None:
        self.messages.append(content)


def same(a: Trellis, b: Trellis) -> bool:
    def text(t: Trellis) -> str:
        spec = dict(t._scene()[0])
        return json.dumps(spec, sort_keys=True, default=str)

    return text(a) == text(b)


def rerun(t: Trellis, **names: Any) -> Trellis:
    """``t.code()`` run, with the tables by the names it gives them."""
    return eval(t.code(), {"Trellis": Trellis, "Theme": Theme, "pairs": at.pairs, **names})


CARS = load("cars")


def test_code_writes_the_calls_as_made() -> None:
    t = (Trellis(CARS, wrap="origin", title="Fuel", theme=Theme("framed", panel_gap=12))
         .as_category("cylinders")
         .points(x="weight", y="mpg", color="cylinders", tooltip=["name"])
         .smooth(x="weight", y="mpg")
         .limits(y=(0, None)).format(y=".0f")
         .annotate("Heavy", x=4500, y=40, panel="USA"))  # fmt: skip
    code = t.code()
    assert code.startswith('(\n    Trellis(data, wrap="origin", title="Fuel", '
                           'theme=Theme("framed", panel_gap=12))\n')  # fmt: skip
    assert '    .as_category("cylinders")\n' in code
    assert '    .points(x="weight", y="mpg", color="cylinders", tooltip=["name"])\n' in code
    assert '    .annotate("Heavy", x=4500, y=40, panel="USA")\n)' in code
    assert same(t, rerun(t, data=CARS))


def test_code_names_a_table_as_the_notebook_does() -> None:
    main = vars(sys.modules["__main__"])
    main["my_cars"] = CARS
    try:
        assert (
            Trellis(CARS).points(x="weight", y="mpg").code().startswith("(\n    Trellis(my_cars)")
        )
    finally:
        del main["my_cars"]


def test_properties_read_back_and_redraw() -> None:
    t = Trellis(CARS, wrap="origin").points(x="weight", y="mpg", color="cylinders")
    sent = Sent()
    t.widget.send = sent
    t.share_y = "sliced"
    assert t.share_y == "sliced"
    assert t.widget._spec["y"]["share"] == "sliced"
    t.y_scale = ("log", "reverse")
    assert t.y_scale == ("log", "reverse")
    t.x_scale = "sqrt"
    t.cols = 1
    t.aspect = 0.5
    t.color = "origin"
    assert (t.cols, t.aspect, t.color, t.share_x, t.x_scale) == (1, 0.5, "origin", True, "sqrt")
    assert t.widget._spec["grid"]["cols"] == 1
    assert 'cols=1, aspect=0.5, share_y="sliced", x_scale="sqrt", y_scale=("log", "reverse")' \
        in t.widget._code  # fmt: skip
    assert '.points(x="weight", y="mpg", color="origin")' in t.widget._code
    t.color = None
    assert t.color is None
    assert '.points(x="weight", y="mpg")' in t.code()
    with pytest.raises(ValueError, match="not a column"):
        t.color = "wheels"
    with pytest.raises(ValueError, match="cols must be at least 1"):
        t.cols = 0
    with pytest.raises(ValueError, match="aspect must be positive"):
        t.aspect = -1


def test_the_panel_describes_its_settings() -> None:
    t = Trellis(CARS, wrap="origin").as_category("cylinders").line(x="year", y="mpg",
                                                                   color="cylinders")  # fmt: skip
    sections = t._scene()[0]["settings"]
    by = {s["name"]: s for sec in sections for s in sec["settings"]}
    assert [sec["title"] for sec in sections] == ["Layout", "Scales", "Data"]
    assert by["cols"]["kind"] == "stepper"
    assert by["cols"]["shown"] == 2
    assert ["bank", "Banked to 45°"] in by["aspect"]["options"]
    assert [o[0] for o in by["share_y"]["options"]] == [True, False, "sliced"]
    assert by["color"]["value"] == "cylinders"
    names = [o[0] for o in by["color"]["options"]]
    assert names[0] is None
    assert "origin" in names
    assert "name" not in names  # 300 categories: no colour for each
    assert by["order"]["of"] == "mpg"
    grid = Trellis(CARS, row="origin", col="cylinders").points(x="weight", y="mpg")
    by = {s["name"]: s for sec in grid._scene()[0]["settings"] for s in sec["settings"]}
    assert "cols" not in by  # a grid's columns are its levels
    assert ["row", "Per row"] in by["share_y"]["options"]
    single = Trellis(CARS).bars(x="origin", y="mpg", stat="mean")
    by = {s["name"]: s for sec in single._scene()[0]["settings"] for s in sec["settings"]}
    assert "share_y" not in by  # one panel
    assert "x_scale" not in by  # categories


def test_changes_from_the_browser_all_or_none() -> None:
    t = Trellis(CARS, wrap="origin").bars(x="origin", y="mpg", stat="mean")
    sent = Sent()
    t.widget.send = sent
    t.widget._on_msg(t.widget, {"type": "settings", "request": 3,
                                "changes": {"share_y": False, "order": "median"}}, [])  # fmt: skip
    assert sent.messages[-1] == {"type": "answer", "request": 3}
    assert t.share_y is False
    assert t.widget._spec["panels"][0]["label"] == "USA"  # the lowest median mpg
    # bars from zero on a log y: refused, and the plot as it was
    t.widget._on_msg(t.widget, {"type": "settings", "request": 4,
                                "changes": {"cols": 1, "y_scale": "log"}}, [])  # fmt: skip
    assert "log" in sent.messages[-1]["error"]
    assert (t.cols, t.y_scale) == (None, "linear")
    assert t.widget._spec["y"]["share"] == "none"
    t.widget._on_msg(t.widget, {"type": "settings", "request": 5,
                                "changes": {"order": "levels"}}, [])  # fmt: skip
    assert t.widget._spec["panels"][0]["label"] == "Europe"
    assert ".order(" not in t.code()


def test_code_follows_the_page_bar_and_the_panels() -> None:
    t = Trellis(CARS, wrap="name", rows=2, cols=3).points(x="weight", y="mpg")
    t.widget.paging = {"page": 2, "sort": "mean mpg", "descending": True, "name": "ford",
                       "where": {"rows": [2, None]}, "pinned": ["amc ambassador dpl"]}  # fmt: skip
    t.widget.compare_panel = "ford pinto"
    code = t.widget._code
    assert '.sort_panels("mean mpg", descending=True)' in code
    assert '.filter_panels("ford", rows=[2, None])' in code
    assert '.pin("amc ambassador dpl")' in code
    assert '.compare("ford pinto")' in code
    assert "show_page" not in code  # the page shown is not the plot's
    t.filter_panels(**{"mean mpg": (20, None)})
    assert 'filter_panels(**{"mean mpg": [20, None]})' in t.code()


def test_controls_false_and_pairs_have_no_panel() -> None:
    t = Trellis(CARS, wrap="origin", controls=False).points(x="weight", y="mpg")
    assert t._scene()[0]["settings"] is None
    assert '"code": null' in t._embed_html()
    assert '"code": "(\\n    Trellis(' in Trellis(CARS).points(x="weight", y="mpg")._embed_html()
    p = at.pairs(CARS, ["mpg", "weight"], color="origin", corner=True)
    assert p._scene()[0]["settings"] is None
    assert p.code() == 'pairs(data, ["mpg", "weight"], color="origin", corner=True)'
    assert same(p, rerun(p, data=CARS))


def test_redundant_shapes_follow_the_colour() -> None:
    t = Trellis(CARS, redundant=True).points(x="weight", y="mpg", color="origin")
    t.color = "cylinders"  # numbers: the colormap alone
    assert t._layers[0].shape == "cylinders"
    assert t._scene()[0]["layers"][0]["marker"] is None
    t.as_category("cylinders")
    assert t._scene()[0]["layers"][0]["marker"]["shapes"] is not None
    t.color = None
    assert t._layers[0].shape is None
    assert '.points(x="weight", y="mpg")' in t.code()


def test_from_a_database() -> None:
    frame = pl.DataFrame({"g": np.repeat(["a", "b", "c", "d"], 50), "x": np.arange(200.0),  # noqa: F841
                          "y": np.arange(200.0) % 7, "k": np.tile(["p", "q"], 100)})  # fmt: skip
    t = Trellis(duckdb.sql("select * from frame"), wrap="g", rows=1, cols=2,
                load="pages").points(x="x", y="y")  # fmt: skip
    by = {s["name"]: s for sec in t._scene()[0]["settings"] for s in sec["settings"]}
    assert ["k", "k"] in by["color"]["options"]
    assert by["cols"]["max"] == 12
    sent = Sent()
    t.widget.send = sent
    t.widget._on_msg(t.widget, {"type": "settings", "request": 1,
                                "changes": {"color": "k", "order": "max"}}, [])  # fmt: skip
    assert sent.messages[-1] == {"type": "answer", "request": 1}
    assert t.widget._spec["legends"][0]["name"] == "k"
    assert '.order("g", by="max", of="y")' in t.code()


def test_texts_and_heights_redraw_and_are_in_the_code() -> None:
    t = Trellis(CARS, wrap="origin").points(x="weight", y="mpg")
    t.widget.send = Sent()
    t.title = "Fuel"
    t.subtitle = "by weight"
    t.caption = "Source: cars"
    t.panel_height = 200
    spec = t.widget._spec
    assert (spec["title"], spec["subtitle"], spec["caption"]) == ("Fuel", "by weight",
                                                                  "Source: cars")  # fmt: skip
    assert spec["panel_height"] == 200
    code = t.widget._code
    assert ('Trellis(data, wrap="origin", panel_height=200, title="Fuel", '
            'subtitle="by weight", caption="Source: cars")') in code  # fmt: skip
    assert same(t, rerun(t, data=CARS))
    t.height = 500
    assert t.widget._spec["height"] == 500
    with pytest.raises(ValueError, match="positive number of pixels"):
        t.panel_height = 0


def test_a_panel_shape_replaces_a_height() -> None:
    t = Trellis(CARS, wrap="origin", panel_height=200).points(x="weight", y="mpg")
    sent = Sent()
    t.widget.send = sent
    by = {s["name"]: s for sec in t._scene()[0]["settings"] for s in sec["settings"]}
    assert by["aspect"]["value"] == "fixed"
    assert by["aspect"]["options"][0] == ["fixed", "200 px high"]
    # chosen again: kept
    t.widget._on_msg(t.widget, {"type": "settings", "request": 1,
                                "changes": {"aspect": "fixed"}}, [])  # fmt: skip
    assert (t.panel_height, t.aspect) == (200, None)
    # a shape: it sets the panels' height now
    t.widget._on_msg(t.widget, {"type": "settings", "request": 2,
                                "changes": {"aspect": 1}}, [])  # fmt: skip
    assert sent.messages[-1] == {"type": "answer", "request": 2}
    assert (t.panel_height, t.aspect) == (None, 1)
    assert t.widget._spec["panel_height"] is None
    assert "panel_height" not in t.code()
    assert 'Trellis(data, wrap="origin", aspect=1)' in t.code()
    by = {s["name"]: s for sec in t.widget._spec["settings"] for s in sec["settings"]}
    assert by["aspect"]["value"] == 1
    assert "fixed" not in [o[0] for o in by["aspect"]["options"]]
    # and a height set after it takes over again
    t.panel_height = 150
    assert (t.panel_height, t.aspect) == (150, None)
    # the plot's height alike
    h = Trellis(CARS, wrap="origin", height=480).points(x="weight", y="mpg")
    h.aspect = 0.5
    assert (h.height, h.aspect) == (None, 0.5)


def test_pairs_code_has_its_texts_as_they_are() -> None:
    p = at.pairs(CARS, ["mpg", "weight"])
    p.title = "Pairs"
    assert p.code() == 'pairs(data, ["mpg", "weight"], title="Pairs")'
