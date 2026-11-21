"""Panels to compare with: pinned first on every page (``pin``), and one panel's marks drawn
faintly in every other (``compare``), from Python and from the browser."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.figure import figure_svg
from anytrellis.pages import page_labels, page_list, pins_of


def stations(n: int, hours: int = 12) -> pl.DataFrame:
    k = np.repeat(np.arange(n), hours)
    return pl.DataFrame({
        "station": [f"s{i:03d}" for i in k],
        "t": np.tile(np.arange(hours, dtype=np.float64), n),
        "temp": k + np.tile(np.arange(hours, dtype=np.float64), n) / 10,
        "zone": np.where(k % 2 == 0, "even", "odd"),
    })  # fmt: skip


def paged(n: int, **kwargs: Any) -> Trellis:
    return Trellis(stations(n), wrap="station", rows=2, cols=3, **kwargs).line(x="t", y="temp")


class Sent:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def __call__(self, content: dict[str, Any], buffers: Any = None) -> None:
        self.messages.append(content)

    def last_panels(self) -> list[int]:
        details = [m for m in self.messages if m["type"] == "detail"]
        return details[-1]["layers"][0]["layer"]["panels"]


def test_pinned_panels_lead_every_page() -> None:
    assert page_list(range(10), 4, None, [7, 2]) == [[7, 2, 0, 1], [7, 2, 3, 4], [7, 2, 5, 6],
                                                    [7, 2, 8, 9]]  # fmt: skip
    assert page_list([], 4, None, [3]) == [[3]]  # the filters keep none: the pinned still
    assert pins_of([1, 2, 3, 4, 1], 4) == [1, 2, 3]  # a place left for another
    groups = [0, 0, 0, 1, 1, 1]
    listed = page_list(range(6), 3, groups, [4])
    assert listed == [[4, 0, 1], [4, 2], [4, 3, 5]]
    assert page_labels(listed, groups, ["a", "b"]) == ["a (1 of 2)", "a (2 of 2)", "b"]


def test_pin_from_python_whatever_the_sort_and_filters() -> None:
    t = paged(20).pin("s015", "s009")
    assert t.pinned == ["s015", "s009"]
    assert t.shown_panels() == ["s015", "s009", "s000", "s001", "s002", "s003"]
    assert t.pages == 5  # 18 others, 4 a page
    t.show_page(2)
    assert t.shown_panels()[:3] == ["s015", "s009", "s004"]
    t.filter_panels("s01")  # s010 to s019: the pinned stay
    assert t.shown_panels()[:2] == ["s015", "s009"]
    assert "s010" in t.shown_panels()
    t.sort_panels("max temp", descending=True)
    assert t.shown_panels()[:3] == ["s015", "s009", "s019"]
    t.unpin("s015")
    assert t.pinned == ["s009"]
    t.unpin()
    assert t.pinned == []
    with pytest.raises(ValueError, match="no panel 's999'"):
        t.pin("s999")
    with pytest.raises(ValueError, match="does not page"):
        Trellis(stations(3), wrap="station").line(x="t", y="temp").pin("s001")
    data = stations(4).with_columns(site=pl.lit("a"))
    grid = Trellis(data, row="zone", col="station", page="site").line(x="t", y="temp")
    with pytest.raises(ValueError, match="in place"):
        grid.pin(grid.panels()[0])


def test_pins_go_to_the_browser_and_back_with_their_data() -> None:
    t = paged(60)
    sent = Sent()
    t.widget.send = sent
    t.pin("s050")
    assert t.widget.paging["pinned"] == ["s050"]
    assert 50 in sent.last_panels()  # on every page: its data sent
    t.widget.paging = {"page": 4, "pinned": ["s040"]}  # the reader, in the browser
    assert t.pinned == ["s040"]
    assert t.shown_panels()[0] == "s040"
    assert 40 in sent.last_panels()
    assert '"pinned": ["s040"]' in t._embed_html()


def test_saved_images_mark_the_pinned() -> None:
    t = paged(20).pin("s012")
    svg = figure_svg(t, width=700)
    assert svg.index(">s012<") < svg.index(">s000<")
    assert svg.count('r="3" fill="#1f77b4"') == 1  # its pin


def test_compare_draws_one_panels_marks_in_the_others() -> None:
    t = Trellis(stations(4), wrap="station").line(x="t", y="temp")
    plain = figure_svg(t, width=700)
    t.compare("s002")
    assert t.compared == "s002"
    svg = figure_svg(t, width=700)
    assert plain.count("#b8bec6") == 0
    assert svg.count('stroke="#b8bec6"') == 3  # in each of the three others
    assert '"compare": "s002"' in t._embed_html()
    t.compare()
    assert t.compared is None
    with pytest.raises(ValueError, match="no panel"):
        t.compare("s9")


def test_a_compared_panel_of_another_page_comes_with_its_data() -> None:
    t = paged(60)
    sent = Sent()
    t.widget.send = sent
    t.compare("s055")
    assert t.widget.compare_panel == "s055"
    assert 55 in sent.last_panels()
    t.widget.compare_panel = "s045"  # chosen in the browser
    assert t.compared == "s045"
    assert 45 in sent.last_panels()


def test_from_the_database_the_pinned_and_compared_come_with_each_page() -> None:
    import duckdb

    frame = stations(60)  # noqa: F841  (duckdb reads it by name)
    t = Trellis(duckdb.sql("select * from frame"), wrap="station", rows=2, cols=3,
                load="pages").line(x="t", y="temp")  # fmt: skip
    t.pin("s050").compare("s030").show_page(4)
    spec, _ = t._shown_scene()
    panels = spec["layers"][0]["panels"]
    assert 50 in panels
    assert 30 in panels
    svg = figure_svg(t, width=700)
    assert ">s050<" in svg
    assert svg.count('stroke="#b8bec6"') == 6  # s030 (on another page): in all six


def test_a_view_started_after_a_page_turn_gets_the_panels_shown() -> None:
    t = paged(60).show_page(5).compare("s055")  # before the plot is first shown
    sent = Sent()
    t.widget.send = sent
    assert 55 not in t.widget._spec["layers"][0]["panels"]  # the spec: as the plot started
    t.widget._on_msg(t.widget, {"type": "ready"}, [])
    panels = sent.last_panels()
    assert 55 in panels
    assert t.shown_panels()[0] in [t.panels()[i] for i in panels]
