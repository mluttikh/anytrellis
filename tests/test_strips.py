"""Nested strips: with several facet columns, a strip per column, the first outermost, each
spanning the panels (rows, columns) next to each other that share its level; ``"joined"``:
one strip naming the levels together. The browser and ``save_svg`` lay them out alike."""

from __future__ import annotations

from typing import Any

import pytest

from anytrellis import Trellis
from anytrellis.figure import figure_svg, layout, nest


def sales() -> dict[str, list[Any]]:
    rows: dict[str, list[Any]] = {"region": [], "store": [], "kind": [], "size": [],
                                  "month": [], "units": []}  # fmt: skip
    for region, stores in (("north", ("n1", "n2")), ("south", ("s1",))):
        for store in stores:
            for kind, size in (("food", "big"), ("food", "small"), ("toys", "big")):
                for month in range(1, 4):
                    row = {"region": region, "store": store, "kind": kind, "size": size,
                           "month": month, "units": month * 2}  # fmt: skip
                    for name, v in row.items():
                        rows[name].append(v)
    return rows


def spans(strips: list[Any], vertical: bool) -> list[tuple[str, float, float]]:
    return [(s.label, *((s.rect.y, s.rect.y + s.rect.h) if vertical else
                        (s.rect.x, s.rect.x + s.rect.w)))
            for s in strips if s.vertical == vertical]  # fmt: skip


def test_nest_finds_the_runs_of_each_level() -> None:
    keys = [["A", "x"], ["A", "y"], ["B", "x"], ["A", "x"]]
    assert nest(keys, 2) == [(0, 0, 1), (0, 2, 2), (0, 3, 3),
                             (1, 0, 0), (1, 1, 1), (1, 2, 2), (1, 3, 3)]  # fmt: skip


def test_a_grid_nests_its_column_and_row_strips() -> None:
    t = Trellis(sales(), col=["region", "store"], row=["kind", "size"]).line(x="month", y="units")
    spec, _ = t._scene()
    assert spec["grid"]["col_keys"] == [["north", "n1"], ["north", "n2"], ["south", "s1"]]
    assert spec["grid"]["row_keys"] == [["food", "big"], ["food", "small"], ["toys", "big"]]
    out = layout(spec, 900)
    top_row = sorted({b.rect.x for b in out.panels})
    left_col = sorted({b.rect.y for b in out.panels})
    pw, ph = out.panels[0].rect.w, out.panels[0].rect.h
    top = spans(out.strips, vertical=False)
    assert [s[0] for s in top] == ["north", "south", "n1", "n2", "s1"]
    assert top[0][1:] == (top_row[0], top_row[1] + pw)  # north over its two stores
    assert top[1][1:] == (top_row[2], top_row[2] + pw)
    right = spans(out.strips, vertical=True)
    assert [s[0] for s in right] == ["food", "toys", "big", "small", "big"]
    assert right[0][1:] == (left_col[0], left_col[1] + ph)  # food over its two sizes
    outer = next(s.rect.x for s in out.strips if s.vertical and s.label == "food")
    inner = next(s.rect.x for s in out.strips if s.vertical and s.label == "small")
    assert outer > inner  # the first row column outermost, on the right
    assert out.strips[0].rect.y + out.strips[0].rect.h < out.strips[2].rect.y  # above


def test_joined_strips_name_the_levels_together() -> None:
    nested = Trellis(sales(), col=["region", "store"]).line(x="month", y="units")
    joined = Trellis(sales(), col=["region", "store"], strips="joined").line(x="month", y="units")
    a, b = layout(nested._scene()[0], 900), layout(joined._scene()[0], 900)
    assert [s.label for s in b.strips] == ["north · n1", "north · n2", "south · s1"]
    assert a.panels[0].rect.y > b.panels[0].rect.y  # two strips high
    with pytest.raises(ValueError, match="strips must be one of"):
        Trellis(sales(), strips="stacked")


def test_a_wrap_nests_its_strips_over_the_panels_side_by_side() -> None:
    t = Trellis(sales(), wrap=["region", "store"], cols=2).line(x="month", y="units")
    out = layout(t._scene()[0], 900)
    assert [b.label for b in out.panels] == ["n1", "n2", "s1"]
    assert [(s.label, s.rect.x, s.rect.w) for s in out.strips] == [
        ("north", out.panels[0].rect.x, out.panels[1].rect.x + out.panels[1].rect.w
         - out.panels[0].rect.x),
        ("south", out.panels[2].rect.x, out.panels[2].rect.w),
    ]  # fmt: skip
    first = out.panels[0]
    assert first.strip is not None
    assert out.strips[0].rect.y + out.strips[0].rect.h + 1 == first.strip.y
    joined = Trellis(sales(), wrap=["region", "store"], cols=2, strips="joined")
    out = layout(joined.line(x="month", y="units")._scene()[0], 900)
    assert [b.label for b in out.panels] == ["north · n1", "north · n2", "south · s1"]
    assert out.strips == []


def test_a_page_column_is_not_a_strip() -> None:
    """With page=, a wrap's strips name its own levels; the page's are in the pager."""
    t = Trellis(sales(), page="region", wrap=["kind", "size"], cols=3).line(x="month", y="units")
    spec, _ = t._scene()
    assert spec["grid"]["strip_from"] == 1
    out = layout(spec, 900)
    assert [b.label for b in out.panels] == ["big", "small", "big"]
    assert [s.label for s in out.strips] == ["food", "toys"]


def test_an_svg_draws_the_nested_strips() -> None:
    t = Trellis(sales(), col=["region", "store"]).line(x="month", y="units")
    svg = figure_svg(t)
    for label in ("north", "south", "n1", "n2", "s1"):
        assert f">{label}<" in svg
