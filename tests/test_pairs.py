"""``pairs``: a scatterplot matrix of a table's number columns."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest

from anytrellis import Pairs, pairs
from anytrellis.data import Table, group_order
from anytrellis.selection import link_keys

COLS = ["a", "b", "c"]


def data(n: int = 60) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    a = rng.normal(size=n)
    return pl.DataFrame({
        "a": a, "b": 2 * a + rng.normal(size=n), "c": rng.uniform(10, 20, n),
        "g": rng.choice(["x", "y"], n), "id": np.arange(n),
    })  # fmt: skip


def layer(spec: dict[str, Any], name: str) -> dict[str, Any]:
    return next(lr for lr in spec["layers"] if lr.get("name") == name)


def test_a_panel_per_pair_x_by_column_and_y_by_row() -> None:
    p = pairs(data(), COLS, color="g")
    spec, _ = p._scene()
    assert isinstance(p, Pairs)
    assert (spec["grid"]["rows"], spec["grid"]["cols"]) == (3, 3)
    assert spec["grid"]["col_labels"] == COLS
    assert spec["grid"]["row_labels"] == COLS
    assert p.panels()[1] == "a · b"  # row a (y), column b (x)
    assert [q["xg"] for q in spec["panels"]] == [0, 1, 2] * 3
    assert [q["yg"] for q in spec["panels"]] == [0] * 3 + [1] * 3 + [2] * 3
    assert spec["aspect"] == 1.0
    assert spec["x"]["title"] == ""
    assert spec["y"]["title"] == ""
    # a column's x domain and a row's y domain are the same variable's
    df = data()
    for i, name in enumerate(COLS):
        lo, hi = spec["panels"][i * 3 + i]["x"]
        assert lo <= df[name].min()
        assert hi >= df[name].max()
        assert spec["panels"][i * 3]["y"] == spec["panels"][i * 3 + 2]["y"]


def test_default_columns_are_the_number_columns_but_the_colour() -> None:
    p = pairs(data(), color="g")
    p._scene()
    assert p._columns == ["a", "b", "c", "id"]


def test_corner_keeps_the_panels_below_the_diagonal() -> None:
    p = pairs(data(), COLS, corner=True)
    spec, _ = p._scene()
    assert p.panels() == ["a · a", "b · a", "b · b", "c · a", "c · b", "c · c"]
    assert [(q["row"], q["col"]) for q in spec["panels"]] == [
        (0, 0), (1, 0), (1, 1), (2, 0), (2, 1), (2, 2)]  # fmt: skip
    p = pairs(data(), COLS, corner=True, diag=None)
    p._scene()
    assert p.panels() == ["b · a", "c · a", "c · b"]


def test_the_diagonal_fills_each_variable_range() -> None:
    df = data()
    p = pairs(df, COLS, color="g")
    p._scene()
    band = next(t for lr, t, g in p._geometry if lr.name == "density")
    for name in COLS:
        on = band.column("_x_var").values == name
        top, values = band.column("_y").values[on], df[name].to_numpy()
        assert np.isclose(top.max(), values.max())
        assert top.min() >= values.min() - 1e-9
    h = pairs(df, COLS, diag="hist", color="g", bins=8)
    h._scene()
    bars = next(t for lr, t, g in h._geometry if lr.name == "hist")
    for name in COLS:
        on = bars.column("_x_var").values == name
        assert bars.column("count").values[on].sum() == len(df)
        assert np.isclose(bars.column("_y").values[on].max(), df[name].to_numpy().max())


def test_auto_diagonal_is_a_density_with_a_colour_else_a_histogram() -> None:
    names = [lr.name for lr in pairs(data(), COLS, color="g")._layers]
    assert names == ["points", "density", "density line"]
    assert [lr.name for lr in pairs(data(), COLS)._layers] == ["points", "hist"]
    assert [lr.name for lr in pairs(data(), COLS, diag=None)._layers] == ["points"]


def test_a_brush_selects_rows_of_the_data_in_every_panel() -> None:
    df = data()
    p = pairs(df, COLS)
    p.select(x=(0, 9), y=(-9, 9), panel=("b", "a"))
    rows = p.selected()
    assert isinstance(rows, pl.DataFrame)
    assert rows["id"].to_list() == df.filter(pl.col("a") >= 0)["id"].to_list()
    # the link grows it to every panel's copy of those rows
    spec, _ = p._scene()
    points = p._layers[0]
    mask = p._source_mask(points)
    table = p._table(points)
    assert len(np.unique(table.column("_row").values[mask])) == len(rows)
    assert mask.sum() == len(rows) * 6  # 6 panels off the diagonal
    assert "link" in layer(spec, "points")


def test_tooltips_tell_the_row_of_the_data() -> None:
    df = data()
    p = pairs(df, COLS, color="g", tooltip=["id"])
    spec, _ = p._scene()
    index = spec["layers"].index(layer(spec, "points"))
    _, table, geom, _ = p._sent[index]
    row = int(table.column("_row").values[geom.rows[0]])
    tip = dict(p._tooltip(index, 0))
    assert list(tip) == ["a", "b", "c", "g", "id"]
    assert tip["id"] == str(df["id"][row])
    assert tip["g"] == df["g"][row]
    curve = dict(p._tooltip(spec["layers"].index(layer(spec, "density line")), 0))
    assert set(curve) == {"a", "density", "g"}


def test_mistakes_are_explained() -> None:
    with pytest.raises(ValueError, match="number columns"):
        pairs(data(), ["a", "g"])
    with pytest.raises(ValueError, match="at least two"):
        pairs(data(), ["a"])
    with pytest.raises(ValueError, match="diag"):
        pairs(data(), COLS, diag="box")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="neither a column nor a colour"):
        pairs(data(), COLS, color="nope")
    with pytest.raises(TypeError, match="draws its own layers"):
        pairs(data(), COLS).line(x="a", y="b")
    with pytest.raises(ValueError, match="give no layer"):
        pairs(data(), COLS).selected("points")


def test_one_colour_and_a_number_colour() -> None:
    spec, _ = pairs(data(), COLS, color="#d62728")._scene()
    assert layer(spec, "points")["color"] == layer(spec, "hist")["color"]
    spec, _ = pairs(data(), COLS, color="c")._scene()  # a colormap; the diagonal in grey
    assert [lr["name"] for lr in spec["layers"]] == ["points", "hist"]


def test_group_order_sorts_many_groups_by_radix() -> None:
    rng = np.random.default_rng(1)
    for n in (5, 70_000, 300_000):
        codes = rng.integers(0, n, 50_000)
        assert np.array_equal(group_order(codes, n), np.argsort(codes, kind="stable"))
        v = rng.normal(size=codes.size)
        order = group_order(codes, n, within=v)
        assert np.array_equal(order, np.lexsort((v, codes)))


def test_link_keys_from_numbers_and_categories() -> None:
    a = Table({"k": np.array([3.0, 1.0, 3.0]), "s": np.array(["u", "v", "u"])})
    b = Table({"k": np.array([1.0, 2.5]), "s": np.array(["v", "w"])})
    ka, kb = link_keys([a, b], ["k"])
    assert ka is not None
    assert kb is not None
    assert ka[0] == ka[2] != ka[1]
    assert ka[1] == kb[0] != kb[1]
    ka, kb = link_keys([a, b], ["k", "s"])
    assert ka is not None
    assert kb is not None
    assert ka[0] == ka[2]
    assert ka[1] == kb[0]
    assert len({*ka, *kb}) == 3
    whole = Table({"k": np.array([7.0, 0.0, 7.0])})
    (kw,) = link_keys([whole], ["k"])
    assert kw is not None
    assert kw[0] == kw[2] != kw[1]
