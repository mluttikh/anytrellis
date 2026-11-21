"""Views (``save_view``, ``show_view``): what a view keeps and shows again, the zoom it
gives the images and the browser, what ``code()`` and a saved page keep, the reader's views
from the browser, and a plot reading a database (``load="pages"``)."""

from __future__ import annotations

import json
import re
from typing import Any

import duckdb
import polars as pl
import pytest

from anytrellis import Trellis, figure
from anytrellis.synthetic import sensors


@pytest.fixture
def readings() -> pl.DataFrame:
    return pl.DataFrame(sensors(stations=30, sensors=1, hours=24))


def paged(data: Any, **kw: Any) -> Trellis:
    return Trellis(data, wrap="station", rows=2, cols=3, **kw).line(x="time", y="temp")


def test_a_view_keeps_and_shows_the_sort_filters_pins_and_panels(readings: pl.DataFrame) -> None:
    t = paged(readings)
    t.sort_panels("mean temp", descending=True).filter_panels(**{"mean temp": (5, None)})
    t.pin(t.shown_panels()[2]).show_page(2)
    t.compare(t.shown_panels()[1])
    t.save_view("warm")
    shown, compared, pinned = t.shown_panels(), t.compared, t.pinned
    t.sort_panels(None).filter_panels().unpin().compare()
    assert t.shown_panels() != shown
    t.show_view("warm")
    assert (t.shown_panels(), t.compared, t.pinned, t.page) == (shown, compared, pinned, 2)
    view = t.views["warm"]
    assert view["where"] == {"mean temp": [5, None]}
    assert view["zoom"] is None
    t.views["warm"]["sort"] = "nothing"  # a copy
    assert t.views["warm"]["sort"] == "mean temp"


def test_views_are_named_dropped_and_checked(readings: pl.DataFrame) -> None:
    t = paged(readings).save_view("a").save_view("b")
    assert list(t.views) == ["a", "b"]
    t.drop_view("a")
    assert list(t.views) == ["b"]
    with pytest.raises(ValueError, match="no view 'a'"):
        t.show_view("a")
    with pytest.raises(ValueError, match="name"):
        t.save_view("  ")
    with pytest.raises(ValueError, match="not"):
        t.save_view("c", {"color": "red"})


def test_a_views_zoom_reaches_the_images_and_the_browser(readings: pl.DataFrame) -> None:
    t = paged(readings)
    spec, _ = t._scene()
    lo, hi = spec["panels"][0]["x"]
    zoom = {"x": [[0, [lo, (lo + hi) / 2]]], "y": []}
    t.save_view("first half", {"zoom": zoom})
    t.show_view("first half")
    assert figure._shown(t)["x"] == {0: (lo, (lo + hi) / 2)}
    sent: list[dict[str, Any]] = []
    widget = t.widget
    widget.send = lambda msg, *_, **__: sent.append(msg)
    widget._on_msg(widget, {"type": "ready"}, [])  # a view starting: the zoom, until shown
    assert sent[0] == {"type": "zoom", "zoom": zoom}
    shown = {"type": "view", "width": 800, "x": zoom["x"], "y": [], "panels": []}
    widget._on_msg(widget, shown, [])
    sent.clear()
    widget._on_msg(widget, {"type": "ready"}, [])
    assert not [m for m in sent if m.get("type") == "zoom"]
    t.save_view("again")
    assert t.views["again"]["zoom"] == {"x": zoom["x"], "y": []}


def test_code_and_a_saved_page_keep_the_views(readings: pl.DataFrame) -> None:
    t = paged(readings).sort_panels("max temp").save_view("hot").sort_panels(None)
    code = t.code()
    assert '.save_view("hot", {"sort": "max temp"})' in code
    again = eval(code, {"Trellis": Trellis, "readings": readings, "data": readings})
    again.show_view("hot")
    t.show_view("hot")
    assert again.shown_panels() == t.shown_panels()
    page = t.to_html()
    payload = json.loads(re.findall(r"<script type='application/json'>(.*?)</script>", page)[0])
    assert payload["views"]["hot"]["sort"] == "max temp"


def test_views_kept_in_the_browser_reach_python(readings: pl.DataFrame) -> None:
    t = paged(readings)
    widget = t.widget
    widget.views = {"mine": {"sort": "min temp", "descending": True, "open": None}}
    assert t.views == {"mine": {"sort": "min temp", "descending": True, "open": None}}
    assert "save_view" in widget._code
    t.save_view("python")
    assert set(widget.views) == {"mine", "python"}


def test_a_database_plot_shows_a_view_as_memory_does(readings: pl.DataFrame) -> None:
    rel = duckdb.from_arrow(readings.to_arrow())
    shown = []
    for t in (paged(readings), paged(rel, load="pages")):
        t._scene()
        t.save_view("trend", {"sort": "trend temp", "descending": True, "page": 1,
                              "where": {"rows": [1, None]}})  # fmt: skip
        t.show_view("trend")
        t._scene()
        shown.append(t.shown_panels())
    assert shown[0] == shown[1]
    assert len(shown[0]) == 6
