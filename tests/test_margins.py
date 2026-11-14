"""Margins: a grid's (all) row and column, each panel the rows of several panels."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.layers import Geometry

DATA = pl.DataFrame(
    {
        "r": ["a", "a", "a", "b", "b", "b", "b"],
        "c": ["x", "y", "y", "x", "x", "y", "z"],
        "p": ["one", "one", "two", "one", "two", "two", "two"],
        "t": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        "v": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
    }
)


def geometry(t: Trellis, layer: int = 0) -> Geometry:
    """A drawn layer's marks (built by ``_scene``)."""
    geom = t._geometry[layer][2]
    assert geom is not None
    return geom


def counts(t: Trellis, layer: int = 0) -> dict[str, int]:
    """How many marks each panel draws, by its name."""
    spec, _ = t._scene()
    names = t.panels()
    geom = geometry(t, layer)
    found = np.bincount(geom.panel, minlength=len(spec["panels"]))
    return dict(zip(names, found.tolist(), strict=True))


def test_both_margins_and_a_corner() -> None:
    t = Trellis(DATA, row="r", col="c", margins=True).points(x="t", y="v")
    spec, _ = t._scene()
    assert spec["grid"]["row_labels"] == ["a", "b", "(all)"]
    assert spec["grid"]["col_labels"] == ["x", "y", "z", "(all)"]
    n = counts(t)
    assert n["a · (all)"] == 3
    assert n["b · (all)"] == 4
    assert [n[f"(all) · {c}"] for c in "xyz"] == [3, 3, 1]  # each column's
    assert n["(all) · (all)"] == 7
    assert n["a · x"] == 1  # the panels keep their own rows


@pytest.mark.parametrize(("margins", "rows", "cols"), [("row", 3, 3), ("col", 2, 4)])
def test_one_margin(margins: str, rows: int, cols: int) -> None:
    spec, _ = Trellis(DATA, row="r", col="c", margins=margins).points(x="t", y="v")._scene()
    assert (spec["grid"]["rows"], spec["grid"]["cols"]) == (rows, cols)


def test_true_adds_the_margins_the_grid_has() -> None:
    t = Trellis(DATA, col="c", margins=True).points(x="t", y="v")
    assert t.panels() == ["x", "y", "z", "(all)"]
    assert counts(t)["(all)"] == 7


def test_summaries_of_a_margin_are_of_its_rows() -> None:
    t = Trellis(DATA, row="r", col="c", margins=True).hist(x="v", bins=3)
    spec, _ = t._scene()
    geom = geometry(t)
    heights = np.bincount(geom.panel, weights=geom.y1 - geom.y0, minlength=len(spec["panels"]))
    total = dict(zip(t.panels(), heights.tolist(), strict=True))
    assert total["(all) · (all)"] == 7
    assert total["b · (all)"] == 4
    assert total["(all) · y"] == 3


def test_a_layer_without_facet_columns_is_in_the_margins_too() -> None:
    ref = pl.DataFrame({"t": [0.0, 6.0], "v": [0.0, 0.0]})
    t = Trellis(DATA, row="r", col="c", margins=True).points(x="t", y="v")
    t.points(x="t", y="v", data=ref)
    assert set(counts(t, 1).values()) == {2}


def test_context_of_a_margin() -> None:
    t = Trellis(DATA, row="r", col="c", margins=True)
    t.points(x="t", y="v", facet="exclude").points(x="t", y="v")
    n = counts(t)
    assert n["(all) · (all)"] == 0  # every row is in the corner: no context
    assert n["a · (all)"] == 4  # b's rows
    assert n["a · x"] == 6


def test_blank_cells_keep_the_margins() -> None:
    t = Trellis(DATA, row="r", col="c", margins=True, empty="blank").points(x="t", y="v")
    n = counts(t)
    assert "a · z" not in n  # no data: left out
    assert n["(all) · z"] == 1
    assert n["(all) · (all)"] == 7


def test_margins_on_every_page() -> None:
    t = Trellis(DATA, row="r", col="c", page="p", margins=True).points(x="t", y="v")
    n = counts(t)
    assert n["one · (all) · (all)"] == 3
    assert n["two · (all) · (all)"] == 4
    assert n["two · b · (all)"] == 3


def test_selecting_in_a_margin_selects_rows_once() -> None:
    t = Trellis(DATA, row="r", col="c", margins=True).points(x="t", y="v")
    t.select(x=(1.5, 4.5), panel=("(all)", "(all)"))
    selected: Any = t.selected()
    assert sorted(selected["t"].to_list()) == [2.0, 3.0, 4.0]


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        ({"wrap": "c", "margins": True}, "grid"),
        ({"col": "c", "margins": "row"}, "row="),
        ({"row": "r", "margins": "both"}, "margins must be"),
    ],
)
def test_what_margins_need(kw: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Trellis(DATA, **kw).points(x="t", y="v")._scene()


def test_not_with_pages_read_from_a_database() -> None:
    t = Trellis(DATA.lazy(), row="r", col="c", page="p", margins=True, load="pages")
    with pytest.raises(ValueError, match="margins"):
        t.points(x="t", y="v")._scene()
