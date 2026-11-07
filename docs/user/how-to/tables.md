# Plot your own tables

Give `Trellis` any table: a Polars, pandas or PyArrow table, a DuckDB relation, or a dict
of columns (lists or NumPy arrays). Name its columns in the facets and the layers.

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

## Large tables

anytrellis reads only the columns a plot uses, once, and sends them to the browser as
binary arrays. See [Plot large data](large.md).
