"""Linked plots: one selection, shown in every plot of the link."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest

import anytrellis as at
from anytrellis import Trellis

CARS = pl.DataFrame(
    {
        "id": [f"c{i}" for i in range(10)],
        "weight": [1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "mpg": [30.0, 28, 26, 24, 22, 20, 18, 16, 14, 12],
        "hp": [50.0, 55, 60, 95, 100, 105, 150, 155, 160, 165],
        "cyl": ["4", "4", "4", "6", "6", "6", "8", "8", "8", "8"],
    }
)


def mask(layer: dict[str, Any], buffers: list[bytes]) -> list[int]:
    bits = np.frombuffer(buffers[layer["mask"]], dtype=np.uint8)
    return np.unpackbits(bits, bitorder="little")[: layer["count"]].tolist()


class Sent:
    def __init__(self) -> None:
        self.messages: list[tuple[dict[str, Any], list[bytes]]] = []

    def __call__(self, content: dict[str, Any], buffers: Any = None) -> None:
        self.messages.append((content, list(buffers or [])))

    def highlights(self) -> list[tuple[dict[str, Any], list[bytes]]]:
        return [(m, b) for m, b in self.messages if m["type"] == "highlight"]


def ids(frame: pl.DataFrame) -> list[str]:
    return frame["id"].to_list()


def test_same_table_selects_the_same_rows() -> None:
    scatter = Trellis(CARS).points(x="weight", y="mpg")
    counts = Trellis(CARS).hist(x="hp", bins=4)
    at.link(scatter, counts)
    scatter.select(x=(0.5, 3.5))
    assert ids(counts.selected()) == ["c0", "c1", "c2"]
    assert counts.selection is None  # its own brush: none
    scatter.select()
    assert counts.selected().height == 0


def test_brush_in_a_summary_selects_its_rows_in_the_others() -> None:
    scatter = Trellis(CARS).points(x="weight", y="mpg")
    counts = Trellis(CARS).hist(x="hp", binwidth=50)
    at.link(scatter, counts)
    counts.select(x=(155, 170))  # the last bin: 150-200
    assert ids(scatter.selected()) == ["c6", "c7", "c8", "c9"]


def test_one_brush_per_link() -> None:
    a = Trellis(CARS).points(x="weight", y="mpg")
    b = Trellis(CARS).points(x="hp", y="mpg")
    link = at.link(a, b)
    a.select(x=(0.5, 2.5))
    b.select(x=(140, 170))
    assert a.selection is None
    assert b.selection is not None
    assert link.source is b
    assert ids(a.selected()) == ["c6", "c7", "c8", "c9"]


def test_on_links_different_tables_by_key() -> None:
    specs = CARS.select("id", "cyl")
    scatter = Trellis(CARS).points(x="weight", y="mpg")
    bars = Trellis(specs.with_columns(n=pl.lit(1.0))).points(x="cyl", y="n")
    at.link(scatter, bars, on="id")
    scatter.select(x=(3.5, 6.5))
    assert ids(bars.selected()) == ["c3", "c4", "c5"]
    other = Trellis(CARS.clone()).points(x="weight", y="mpg")
    lonely = Trellis(CARS).points(x="weight", y="mpg")
    at.link(other, lonely)  # different objects, no on=: nothing in common
    other.select(x=(0, 20))
    assert lonely.selected().height == 0


def test_hist_bars_get_their_selected_share(monkeypatch: pytest.MonkeyPatch) -> None:
    scatter = Trellis(CARS).points(x="weight", y="mpg")
    counts = Trellis(CARS).hist(x="hp", binwidth=50)  # bins 50-100: 4 cars, 100-150: 2, ...
    sent = Sent()
    monkeypatch.setattr(counts.widget, "send", sent)
    at.link(scatter, counts)
    scatter.select(x=(0.5, 2.5))  # c0, c1: two of the first bin's four
    (message, buffers), = sent.highlights()  # fmt: skip
    (layer,) = message["layers"]
    share = np.frombuffer(buffers[layer["fraction"]], dtype=np.float32)
    assert share.tolist() == [0.5, 0.0, 0.0]
    scatter.select()
    assert sent.highlights()[-1][0] == {"type": "highlight", "layers": None}


def test_points_and_lines_get_a_mask(monkeypatch: pytest.MonkeyPatch) -> None:
    a = Trellis(CARS).points(x="weight", y="mpg")
    b = Trellis(CARS).line(x="weight", y="hp").points(x="weight", y="hp").rule(y=100)
    sent = Sent()
    monkeypatch.setattr(b.widget, "send", sent)
    at.link(a, b)
    a.select(x=(2.5, 3.5))  # c2
    message, buffers = sent.highlights()[-1]
    line, points, rule = message["layers"]
    assert rule is None
    assert mask(line, buffers) == [0, 1, 1, 0, 0, 0, 0, 0, 0]  # the segments touching c2
    assert mask(points, buffers) == [0, 0, 1, 0, 0, 0, 0, 0, 0, 0]


def test_box_lights_up_when_any_of_its_rows_is_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    a = Trellis(CARS).points(x="weight", y="mpg")
    b = Trellis(CARS).box(x="cyl", y="hp")
    sent = Sent()
    monkeypatch.setattr(b.widget, "send", sent)
    at.link(a, b)
    a.select(x=(0.5, 1.5))  # c0: a 4-cylinder car
    message, buffers = sent.highlights()[-1]
    assert mask(message["layers"][0], buffers) == [1, 0, 0]


def test_a_view_asks_for_the_highlight_and_a_click_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    a = Trellis(CARS).points(x="weight", y="mpg")
    b = Trellis(CARS).points(x="hp", y="mpg")
    at.link(a, b)
    a.select(x=(0.5, 2.5))
    w = b.widget  # made after the selection: the browser asks for it
    assert w._live
    sent = Sent()
    monkeypatch.setattr(w, "send", sent)
    w._on_msg(w, {"type": "ready"}, [])
    assert sent.highlights()[-1][0]["selected"] == 2
    w._on_msg(w, {"type": "clear"}, [])
    assert a.selection is None
    assert sent.highlights()[-1][0]["layers"] is None


def test_browser_brush_relays(monkeypatch: pytest.MonkeyPatch) -> None:
    a = Trellis(CARS).points(x="weight", y="mpg")
    b = Trellis(CARS).points(x="hp", y="mpg")
    at.link(a, b)
    sent = Sent()
    monkeypatch.setattr(b.widget, "send", sent)
    origin = a._scene()[0]["x"]["origin"]
    a.widget.selection = {"x": [0.5 - origin, 2.5 - origin], "y": None, "panel": None}
    assert ids(b.selected()) == ["c0", "c1"]
    assert sent.highlights()[-1][0]["selected"] == 2


def test_new_layers_get_the_highlight() -> None:
    a = Trellis(CARS).points(x="weight", y="mpg")
    b = Trellis(CARS).points(x="hp", y="mpg")
    at.link(a, b)
    a.select(x=(0.5, 2.5))
    b.hist(x="hp", name="h")
    assert ids(b.selected("h")) == ["c0", "c1"]


def test_unlink_and_errors() -> None:
    a = Trellis(CARS).points(x="weight", y="mpg")
    b = Trellis(CARS).points(x="hp", y="mpg")
    link = at.link(a, b)
    with pytest.raises(ValueError, match="linked already"):
        at.link(a, Trellis(CARS))
    with pytest.raises(ValueError, match="two plots"):
        at.link(Trellis(CARS))
    a.select(x=(0.5, 2.5))
    link.unlink()
    assert b.selected().height == 0
    assert a.selection is not None
    b.select(x=(0, 1000))
    assert a.selection is not None  # not linked: each its own
    at.link(a, b)  # linked again: a's brush leads
    assert ids(b.selected()) == ["c0", "c1"]
    assert b.selection is None


def test_a_legend_pick_shows_in_the_linked_plots() -> None:
    scatter = Trellis(CARS).points(x="weight", y="mpg", color="cyl")
    counts = Trellis(CARS).hist(x="hp", bins=4)
    at.link(scatter, counts)
    scatter.select(color="6")
    assert ids(counts.selected()) == ["c3", "c4", "c5"]
