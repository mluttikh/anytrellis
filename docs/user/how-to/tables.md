# Plot your own tables

Give `Trellis` any table: a Polars, pandas or PyArrow table, a Polars `LazyFrame`, a
DuckDB relation, an Ibis table, or a dict of columns (lists or NumPy arrays). Name its
columns in the facets and the layers.

```python exec="on" source="above" session="tables" html="true"
import pandas as pd

from anytrellis import Trellis

df = pd.DataFrame({
    "day": pd.date_range("2026-01-01", periods=90, freq="D").repeat(2),
    "shop": ["north", "south"] * 90,
    "visitors": [120 + (i % 7) * 15 + (i // 2) for i in range(180)],
})
plot = Trellis(df, wrap="shop", panel_height=160).line(x="day", y="visitors")
plot
print(plot._embed_html())  # markdown-exec: hide
```

`selected()` gives the selected rows back as the same kind of table: a pandas table here.

## Columns and their axes

| Column | Axis | Notes |
| --- | --- | --- |
| Numbers | A number axis | Integers and floats; `NaN` and nulls are left out of a layer |
| Dates and datetimes | A time axis | Ticks from years to fractions of a second, as you zoom |
| Text and categories | A category axis | A band per category, in alphabetical order unless [ordered](colours.md#order-categories); nulls become a `(missing)` category |

A pandas `Categorical` and a Polars `Enum` keep their declared order. Booleans count as the
numbers 0 and 1: cast them to text for a category (`pl.col("flag").cast(pl.String)`), and
do the same for numbers you want as categories, such as years in a bar chart. A facet
column can be any of these kinds; its levels are the panels.

## A dict of columns

For data that is not in a table library yet, a dict of equally long columns works:

```python exec="on" source="above" session="tables" html="true"
import numpy as np

rng = np.random.default_rng(1)
columns = {
    "group": np.repeat(["a", "b", "c"], 200),
    "x": rng.normal(size=600),
    "y": rng.normal(size=600),
}
plot = Trellis(columns, wrap="group", panel_height=150).points(x="x", y="y", size=4)
plot
print(plot._embed_html())  # markdown-exec: hide
```

The [synthetic data](../reference/synthetic.md) in these guides are dicts like this.

## A layer with its own table

Each layer can bring its own table as its first argument. A layer whose table has the
facet columns is split into panels like the plot's; one whose table lacks them is drawn in
every panel. Here, a table of targets drawn behind each shop's line:

```python exec="on" source="above" session="tables" html="true"
targets = pd.DataFrame({
    "day": pd.to_datetime(["2026-01-01", "2026-03-31"]),
    "visitors": [150, 250],
})
plot = (
    Trellis(df, wrap="shop", panel_height=160)
    .line(targets, x="day", y="visitors", color="#999999", name="target")
    .line(x="day", y="visitors", name="visitors")
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

`facet="all"` draws every row of a layer in every panel even when it has the facet
columns, and `facet="exclude"` draws the *other* panels' rows: see
[each group against the rest](marks.md#each-group-against-the-rest).

## Lazy tables and databases

A Polars `LazyFrame`, a DuckDB relation or an Ibis table (on DuckDB, Postgres, Snowflake or
any other database Ibis queries) is read when the plot is first drawn: in one query, with
only the columns the plot uses. The summaries of each panel are computed by the database:
the statistics the [pages](pages.md) sort and filter by, and those `order()` ranks levels
by. The medians of millions of rows come from it, not from Python.

```python
import ibis

con = ibis.duckdb.connect("readings.duckdb")
readings = con.table("readings").filter(ibis._.year == 2025)
plot = Trellis(readings, wrap="station").line(x="time", y="temp")
```

Ten million readings of 1,000 stations, from an Ibis table on DuckDB, are drawn in 3.3 s
rather than 5.3 s, and their unused columns are never read.

- **The rows of the columns drawn are read into Python**, as for any table, and the browser
  gets the panels of the pages around the one shown.
- **A column needed later** (a tooltip column of a layer added after the plot was drawn,
  say) reads the table again, with it. The rows must come back in the same order each
  time, as they do from Polars, DuckDB and Ibis on DuckDB. For a database that promises
  no order, sort the table by a unique key first (`readings.order_by("id")`).
- **`selected()`** gives every column of the selected rows, as the table the query
  collects to: a PyArrow table from DuckDB and Ibis, a Polars `DataFrame` from a
  `LazyFrame`.
- A summary the database can't compute (the mean of times, on some backends) is computed
  from the rows instead.

## Large tables

anytrellis reads only the columns a plot uses, once, and sends them to the browser as
binary arrays. Text columns are encoded by PyArrow when it is installed: tens of times
faster than labelling millions of rows one by one. See [Plot large data](large.md).
