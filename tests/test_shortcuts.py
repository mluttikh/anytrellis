"""A plot in one call (``shortcuts.py``): ``at.line(df, ...)`` and the other shortcuts,
``plot(df, kind=...)`` as the pandas plotting backend, and ``df.trellis`` on pandas and
Polars tables."""

from __future__ import annotations

import inspect

import duckdb
import pandas as pd
import polars as pl
import pytest

import anytrellis as at
from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.shortcuts import SHORTCUTS, plot


@pytest.fixture
def cars() -> pl.DataFrame:
    return load("cars")


@pytest.fixture
def backend() -> object:
    before = pd.options.plotting.backend
    pd.options.plotting.backend = "anytrellis"  # the entry point (pyproject.toml)
    yield
    pd.options.plotting.backend = before


def test_a_shortcut_is_the_plot_and_its_mark_in_one_call(cars: pl.DataFrame) -> None:
    short = at.points(cars, x="weight", y="mpg", color="origin", wrap="cylinders",
                      title="Cars", size=3)  # fmt: skip
    long = Trellis(cars, wrap="cylinders", title="Cars").points(x="weight", y="mpg",
                                                                color="origin", size=3)  # fmt: skip
    assert short.code() == long.code()
    assert set(SHORTCUTS) <= set(at.__all__)
    for name in SHORTCUTS:
        made = getattr(at, name)(cars, x="mpg", **({} if name in ("hist", "density", "ecdf")
                                                    else {"y": "weight"}))  # fmt: skip
        assert made._layers[0].mark.startswith(name.rstrip("s")[:3])
        made._scene()


def test_its_arguments_listed_and_an_unknown_one_named(cars: pl.DataFrame) -> None:
    params = inspect.signature(at.line).parameters
    assert next(iter(params.values())).kind is inspect.Parameter.POSITIONAL_ONLY
    assert {"x", "y", "color", "wrap", "share_y", "title"} <= set(params)
    assert getattr(at.line, "__name__", None) == "line"
    assert "Trellis(data, ...).line(...)" in (inspect.getdoc(at.line) or "")
    with pytest.raises(TypeError, match="did you mean 'wrap'"):
        at.line(cars, x="year", y="mpg", wrapp="origin")


def test_by_a_kinds_name_pandas_names_too(cars: pl.DataFrame) -> None:
    assert plot(cars, kind="scatter", x="weight", y="mpg", by="origin").code() == (
        at.points(cars, x="weight", y="mpg", wrap="origin").code())  # fmt: skip
    t = plot(cars, kind="kde", x="mpg", logx=True, xlabel="Miles", legend=False)
    assert t._layers[0].mark == "density"
    assert (t.x_scale, t.x_title) == ("log", "Miles")
    assert 'legend="none"' in t.code()
    bars = plot(cars, kind="barh", x="origin", y="mpg", stat="mean")
    assert (bars._layers[0].x, bars._layers[0].y) == ("mpg", "origin")  # categories up the side
    with pytest.raises(ValueError, match="kind must be one of"):
        plot(cars, kind="pie", y="mpg")


def test_several_columns_one_series_each(cars: pl.DataFrame) -> None:
    lines = plot(cars, x="weight", y=["mpg", "acceleration"])
    layer = lines._layers[0]
    assert (layer.y, layer.color) == ("value", "column")
    hist = plot(cars, kind="hist", y=["mpg", "acceleration"], bins=10)
    assert (hist._layers[0].x, hist._layers[0].color) == ("value", "column")
    boxes = plot(cars, kind="box", y=["mpg", "acceleration"])
    assert (boxes._layers[0].x, boxes._layers[0].y) == ("column", "value")
    every = plot(cars.select("weight", "mpg", "horsepower", "origin"), x="weight")
    assert every._layers[0].color == "column"  # every number column but x
    for t in (lines, hist, boxes, every):
        t._scene()


def test_pandas_df_plot_draws_with_anytrellis(cars: pl.DataFrame, backend: object) -> None:
    df = cars.to_pandas()
    t = df.plot.scatter(x="weight", y="mpg", by="origin")  # s=None, c=None from pandas
    assert isinstance(t, Trellis)
    assert 'wrap="origin"' in t.code()
    weather = load("seattle_weather").to_pandas().set_index("date")
    lines = weather[["temp_min", "temp_max"]].plot()  # x: the index
    assert (lines._layers[0].x, lines._layers[0].color) == ("date", "column")
    series = df["mpg"].plot.kde()  # bw_method=None, ind=None from pandas
    assert series._layers[0].x == "mpg"
    area = df.plot.area(x="weight", y="mpg", figsize=(6, 3))  # stacked=True from pandas
    assert area.height == 288
    assert area._layers[0].position == "stack"
    means = df.groupby("origin")["mpg"].mean().plot.barh()
    assert (means._layers[0].x, means._layers[0].y) == ("mpg", "origin")
    for made in (t, lines, series, area, means):
        made._scene()


def test_df_trellis_on_pandas_and_polars(cars: pl.DataFrame) -> None:
    import anytrellis.pandas
    import anytrellis.polars  # noqa: F401

    expected = at.points(cars, x="weight", y="mpg", wrap="origin").code()
    # (registered when imported: unknown to a type checker, as pandas' accessors are)
    points = cars.trellis.points(x="weight", y="mpg", wrap="origin")  # ty: ignore[unresolved-attribute]
    assert points.code() == expected
    lazy = cars.lazy().trellis.hist(x="mpg")  # ty: ignore[unresolved-attribute]
    assert lazy._layers[0].mark == "hist"
    df = cars.to_pandas()
    assert df.trellis(kind="scatter", x="weight", y="mpg")._layers[0].mark == "points"
    assert df["mpg"].trellis.hist()._layers[0].x == "mpg"  # (plot: y's column, along x)
    assert "line" in dir(df.trellis)
    with pytest.raises(AttributeError, match="shortcuts"):
        df.trellis.pie  # noqa: B018


def test_a_database_table_as_any_other(cars: pl.DataFrame) -> None:
    rel = duckdb.from_arrow(cars.to_arrow())
    t = at.line(rel, x="weight", y="mpg", wrap="origin", load="pages")
    t._scene()
    every = plot(duckdb.from_arrow(cars.select("weight", "mpg", "horsepower").to_arrow()),
                 kind="scatter", x="weight")  # fmt: skip
    assert every._layers[0].color == "column"
    every._scene()
