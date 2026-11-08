"""``as_category``: a number column read as categories, its distinct values the levels in
order, labelled as numbers; in memory, and from a database a page at a time."""

from __future__ import annotations

from typing import Any

import duckdb
import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis


def data(n: int = 120) -> pl.DataFrame:
    i = np.arange(n)
    return pl.DataFrame({
        "station": [f"s{k}" for k in i % 3],
        "t": i.astype(float),
        "v": np.sin(i / 7.0) * 10,
        "level": np.array([-10, -2, 3, 10])[i % 4],           # integers, negatives too
        "dose": np.array([0.5, 1.0, 2.5, 0.1 + 0.2])[i % 4],  # floats, 0.30000000000000004
    })  # fmt: skip


def legend(t: Trellis) -> list[tuple[str, Any]]:
    return [(g["kind"], g.get("labels")) for g in t._scene()[0]["legends"]]


def test_a_number_column_colours_as_categories() -> None:
    plain = Trellis(data()).points(x="t", y="v", color="level")
    assert legend(plain) == [("number", None)]
    t = Trellis(data()).as_category("level").points(x="t", y="v", color="level")
    assert legend(t) == [("category", ["-10", "-2", "3", "10"])]  # by value, not as text
    doses = Trellis(data()).as_category("dose").points(x="t", y="v", color="dose")
    assert legend(doses) == [("category", ["0.3", "0.5", "1", "2.5"])]  # 1, not 1.0
    missing = data().with_columns(dose=pl.when(pl.col("dose") > 2).then(None)
                                  .otherwise(pl.col("dose")))  # fmt: skip
    t = Trellis(missing).as_category("dose").points(x="t", y="v", color="dose")
    assert legend(t) == [("category", ["0.3", "0.5", "1", "(missing)"])]


def test_the_levels_order_as_given_and_as_an_axis() -> None:
    t = Trellis(data()).as_category("level", "dose").order("level", [10, 3])
    t.order("dose", [1.0, 2.5])
    t.points(x="t", y="v", color="level").points(x="t", y="v", color="dose")
    assert legend(t) == [("category", ["10", "3", "-10", "-2"]),
                         ("category", ["1", "2.5", "0.3", "0.5"])]  # fmt: skip
    bars = Trellis(data()).as_category("level").bars(x="level", y="v")
    axis = bars._scene()[0]["x"]
    assert (axis["kind"], axis["levels"]) == ("band", ["-10", "-2", "3", "10"])
    lines = Trellis(data()).as_category("level").line(x="t", y="v", color="level")
    assert legend(lines) == [("category", ["-10", "-2", "3", "10"])]  # a series each
    wrap = Trellis(data(), wrap="level").as_category("level").points(x="t", y="v")
    assert wrap.panels() == ["-10", "-2", "3", "10"]  # as a number facet column's


def test_selecting_colours_selects_their_rows() -> None:
    t = Trellis(data()).as_category("level").points(x="t", y="v", color="level")
    t.select(color=["-2", "10"])
    assert sorted(set(t.selected()["level"].to_list())) == [-2, 10]


def test_as_category_after_the_plot_is_drawn() -> None:
    t = Trellis(data()).points(x="t", y="v", color="level")
    assert legend(t)[0][0] == "number"
    t.as_category("level")
    assert legend(t) == [("category", ["-10", "-2", "3", "10"])]


def test_as_category_needs_a_number_column_in_the_data() -> None:
    with pytest.raises(ValueError, match="no data has this column"):
        legend(Trellis(data()).as_category("nope").points(x="t", y="v"))
    timed = data().with_columns(when=pl.datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="a time column"):
        legend(Trellis(timed).as_category("when").points(x="t", y="v"))
    text = Trellis(data()).as_category("station").points(x="t", y="v", color="station")
    assert legend(text) == [("category", ["s0", "s1", "s2"])]  # a category already


def pages(df: pl.DataFrame, **kw: Any) -> tuple[Trellis, Trellis]:
    """The same plot from a database a page at a time, and with every row in memory."""
    rel = duckdb.from_arrow(df.to_arrow())
    paged = Trellis(rel, wrap="station", load="pages", rows=1, cols=1, **kw)
    whole = Trellis(df, wrap="station", rows=1, cols=1, **kw)
    return paged.as_category("level", "dose"), whole.as_category("level", "dose")


def test_a_database_reads_the_levels_and_selects_by_them() -> None:
    paged, whole = pages(data())
    for t in (paged, whole):
        t.points(x="t", y="v", color="dose")
        t.show_page(2)
    assert legend(paged) == legend(whole) == [("category", ["0.3", "0.5", "1", "2.5"])]
    for t in (paged, whole):
        t.select(color=["0.3", "2.5"])  # 0.3: the rows of 0.1 + 0.2
    rows = paged.selected().pl()
    assert sorted(set(rows["dose"].round(6).to_list())) == [0.3, 2.5]
    assert len(rows) == len(whole.selected()) == 60


def test_a_database_counts_a_histogram_by_the_levels() -> None:
    paged, whole = pages(data())
    for t in (paged, whole):
        t.hist(x="v", color="level", bins=5)
        t.show_page(2)
    assert legend(paged) == legend(whole) == [("category", ["-10", "-2", "3", "10"])]

    def bars(t: Trellis) -> list[tuple[float, ...]]:
        geom = next(g for _, _, g in t._geometry if g is not None and g.count)
        shown = geom.panel == 1
        rows = np.column_stack([geom.x0, geom.y0, geom.y1, *np.asarray(geom.rgba).T])
        return sorted(map(tuple, np.round(rows[shown], 6).tolist()))

    assert bars(paged) == bars(whole)
