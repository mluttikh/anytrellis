"""The table view (the toolbar's Table, ``t``): each panel's statistics, as ``stats()``
gives them for any plot, and the rows when they are few, every value as text; from a
database (``load="pages"``) the statistics alone, the same as in memory."""

from __future__ import annotations

import json
import re

import duckdb
import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.plot import TABLE_ROWS


@pytest.fixture
def cars() -> pl.DataFrame:
    return load("cars")


def test_each_panels_statistics_as_stats_gives_them(cars: pl.DataFrame) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
    stats = t.stats()  # a plot that does not page has them too
    assert set(stats["panel"]) == {"Europe", "Japan", "USA"}
    view = t._table_view()
    columns = view["panels"]["columns"]
    assert columns[:3] == ["panel", "rows", "mean mpg"]
    for i, row in enumerate(view["panels"]["rows"]):
        assert row[0] == stats["panel"][i]
        assert float(row[1]) == stats["rows"][i]
        assert abs(float(row[2]) - stats["mean mpg"][i]) < 0.01 * abs(stats["mean mpg"][i])


def test_the_rows_when_few_with_what_the_plot_shows(cars: pl.DataFrame) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="cylinders",
                                            tooltip=["name"])  # fmt: skip
    rows = t._table_view()["rows"]
    assert rows is not None
    assert rows["columns"] == ["origin", "weight", "mpg", "cylinders", "name"]
    assert len(rows["rows"]) == cars.height
    missing = cars.with_row_index().filter(pl.col("mpg").is_null() | pl.col("mpg").is_nan())
    missing = missing["index"][0]
    assert rows["rows"][missing][2] == ""  # a missing number: blank
    big = Trellis(pl.DataFrame({"x": np.arange(TABLE_ROWS + 1.0)})).points(x="x", y="x")
    view = big._table_view()
    assert view["rows"] is None
    assert "too many" in view["note"]


def test_a_database_plot_lists_its_statistics_as_memory_does() -> None:
    gapminder = load("gapminder")
    rel = duckdb.from_arrow(gapminder.to_arrow())
    memory = Trellis(gapminder, wrap="country", rows=2, cols=3).line(x="year", y="pop")
    paged = Trellis(rel, wrap="country", rows=2, cols=3, load="pages").line(x="year", y="pop")
    a, b = memory._table_view(), paged._table_view()
    assert a["panels"]["columns"] == b["panels"]["columns"]
    assert sorted(a["panels"]["rows"]) == sorted(b["panels"]["rows"])
    assert b["rows"] is None
    assert "database" in b["note"]


def test_the_widget_answers_and_a_saved_page_keeps_it(cars: pl.DataFrame) -> None:
    t = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
    sent: list[dict] = []
    widget = t.widget
    widget.send = lambda msg, *_, **__: sent.append(msg)
    widget._on_msg(widget, {"type": "table", "request": 7}, [])
    assert sent[-1]["request"] == 7
    assert sent[-1]["table"]["panels"]["rows"] == t._table_view()["panels"]["rows"]
    page = t.to_html()
    payload = json.loads(re.findall(r"<script type='application/json'>(.*?)</script>", page)[0])
    assert payload["table"]["rows"]["caption"] == f"Rows ({cars.height:,})"
