# Make a plot in one call

`Trellis(df, wrap="origin").points(x="weight", y="mpg")` builds a plot in two steps: the
panels, then the marks in them. For a quick look, or if you come from Plotly Express or
pandas' `df.plot`, a shortcut does both in one call.

## at.line, at.points and the others

```python exec="on" source="above" session="one-call" html="true"
import anytrellis as at
from anytrellis.datasets import load

cars = load("cars")
plot = at.points(cars, x="weight", y="mpg", color="cylinders", wrap="origin", cols=3)
plot
print(plot._embed_html())  # markdown-exec: hide
```

Each argument goes to `Trellis()` or to the mark by its name: `wrap=`, `cols=`, `title=`
and `share_y=` to the plot, `x=`, `y=`, `color=` and `size=` to the points. A name
neither takes is an error that says what you may have meant. The result is the same
`Trellis`, so you can go on from it:

```python
at.line(gapminder, x="year", y="life_expect", group="country", wrap="region") \
    .smooth(x="year", y="life_expect", color="region")
```

There is a shortcut for each common mark: `at.line`, `at.points`, `at.bars`, `at.area`,
`at.hist`, `at.density`, `at.box`, `at.violin`, `at.ecdf` and `at.hexbin`. They take any
table `Trellis` takes, a DuckDB table read a page at a time too:

```python
at.line(duckdb.sql("select * from readings"), x="time", y="temp", wrap="station",
        load="pages")
```

## df.plot with pandas

Set anytrellis as pandas' plotting backend, and `df.plot` draws with it:

```python
import pandas as pd

pd.options.plotting.backend = "anytrellis"

df.plot.scatter(x="weight", y="mpg", by="origin")   # by=: a panel for each origin
df[["temp_min", "temp_max"]].plot()                  # x: the index; a line a column
df.plot.hist(y=["mpg", "acceleration"], bins=20)     # one histogram a column
df.groupby("origin")["mpg"].mean().plot.barh()
```

pandas' kinds map to marks: `line`, `scatter` (points), `bar` and `barh` (bars), `area`,
`hist`, `kde` and `density`, `box` and `hexbin`; `pie` is not drawn. As in pandas, no `x`
uses the index, and no `y`, or a list of them, draws every number column, one coloured
series each (their names in a column called `column`, their values in `value`). pandas'
`by=` facets the plot (`wrap=`), and `logx=`, `logy=`, `loglog=`, `xlabel=`, `ylabel=`,
`legend=False`, `stacked=` and `figsize=` (its height) do what they do there. Any
`Trellis` or mark argument works too: `df.plot(x="date", y="temp", wrap="station",
share_y=False)`.

## df.trellis on pandas and Polars tables

Polars' `df.plot` draws with Altair, and pandas' may stay on matplotlib. Import
`anytrellis.polars` or `anytrellis.pandas`, and every table gets a `trellis` with the
shortcuts as methods:

```python
import anytrellis.polars  # Polars DataFrames and LazyFrames; anytrellis.pandas for pandas

cars.trellis.points(x="weight", y="mpg", wrap="origin")
cars.trellis.hist(x="mpg", color="origin")
cars.trellis(kind="scatter", x="weight", y="mpg")   # by a kind's name, as df.plot
```

Neither is imported with `anytrellis`, so importing it stays quick when you use neither.

## When to write the plot out

A shortcut makes one mark. For several layers, a reference line or settings on the plot
after its marks, `Trellis(...)` and its methods say each step, and `t.code()` writes the
long form of any plot, a shortcut's included.
