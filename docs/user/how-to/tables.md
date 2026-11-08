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

### Reading a page at a time

With `load="pages"`, a paged wrap reads only the rows of the panels of the page shown and
the pages either side of it: Python never holds the whole table. Turning the page reads the
rows of the next panels (a query of the facet columns' values), and the browser draws them
as it draws any paged plot's.

```python
import duckdb

con = duckdb.connect("readings.duckdb")
plot = Trellis(con.table("readings"), wrap="station", load="pages")
plot.line(x="time", y="temp", color="humidity")
```

What a page needs of the other rows comes from the database, so every page looks as it
would with every row read: the panels (the facet columns' combinations), their statistics
(and their trend, as a window query), each panel's range of x and y, the levels of the
category columns and the range of the number colours.

Ten million readings of 1,000 stations, from DuckDB, are drawn in 1.0 s rather than 3.9 s,
from 480,000 rows read rather than all of them. Turning a page keeps the rows of the pages
still around it and reads those of the page that came near (240,000) in 0.25 s. With
`page=`, a level is read by its value (`WHERE site IN (...)`), not panel by panel.

- **Lines, points and text** are drawn from the plot's data a page at a time.
- **Summaries** (`hist`, `box`, `violin`, `density`, `smooth`, `errorbar`) are computed by
  the database, every panel's at once, and no row is read: see below.
- **`selected()`** is a query of the selected rows, in every panel, not yet read: a DuckDB
  relation, an Ibis table or a `LazyFrame`. Read the rows when you need them
  (`selected().pl()`, `.to_pandas()`, `.collect()`), or count them first. A brush over a
  summary selects the rows it stands for: a histogram's bins, a box's group, a stretch of a
  curve.
- **`save_html`** and `to_html` read every row of the lines, points and text, as
  `load="all"` does: the page holds every panel. A plot of summaries only reads none.
- Not yet: `link=` and `anytrellis.link`. A wrap of 100 panels or fewer, which doesn't
  page, reads every row; give `rows=` to page it. With `page=`, a page is a level: turning
  to it reads that level's rows (a grid's too).
- A database that can't compute the panels' statistics (a median, a standard deviation)
  gives an error: use `load="all"`. Without the trend's window query (Ibis, over a time x),
  the statistics have no trend.

#### Summaries from the database

A summary of the plot's data is a query or two, grouped by the facet columns (and the
colour, and a box's positions), whose answer is a few rows per panel:

| Mark | What the database computes |
| --- | --- |
| `hist` | the count in each bin; the bins from the range of every row (`min`, `max`) |
| `box` | the quartiles (`quantile_cont`), the whiskers' ends, and the values beyond them |
| `errorbar` | each group's count, mean, standard deviation, lowest and highest value |
| `smooth(method="linear")` | each group's sums of squares and products about its means |
| `smooth()` (loess) | each group's values in 1,024 bins of x: their count and mean x, and the sum of y and of its squares; the local fits are made on the bins |
| `density`, `violin` | each group's values in fine bins, an eighth of its bandwidth wide (64 to 8,192 to a group); the curve is made from the bins |

They are made once, for every panel: the axes are those of every panel's summary from the
start, and turning a page sends the next panels' without asking again. They are as they
are from the rows read, except the curves made from bins: a density's or a violin's
differs by about 0.03% of its peak, and a loess fit by a few thousandths of the scatter
about it.

Ten million readings of 1,000 stations, from DuckDB:

| Mark | `load="pages"` | `load="all"` |
| --- | --- | --- |
| `hist(x="temp", color="sensor")` | 0.8 s | 3.2 s |
| `box(x="sensor", y="temp")` | 0.9 s | 4.6 s |
| `violin(x="sensor", y="temp")` | 1.8 s | 8.4 s |
| `density(x="temp", color="sensor")` | 1.5 s | 5.2 s |
| `smooth(x="time", y="temp", method="linear")` | 0.7 s | 2.9 s |
| `smooth(x="time", y="temp")` (loess) | 3.6 s | 22 s |
| `errorbar(x="sensor", y="temp")` | 0.4 s | 4.4 s |

What the database doesn't summarise comes from the rows, read once (the columns the mark
draws, every panel's): a violin's points (`inner="points"`), error bars of given ends
(`ymin=`, `ymax=`), and, from Ibis, summaries of a time column (it has no times as
numbers).

## Large tables

anytrellis reads only the columns a plot uses, once, and sends them to the browser as
binary arrays. Text columns are encoded by PyArrow when it is installed: tens of times
faster than labelling millions of rows one by one. See [Plot large data](large.md).
