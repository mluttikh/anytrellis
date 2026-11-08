# Colours, legends and order

## One colour, or a colour per value

`color=` takes a column or one colour:

| `color=` | Draws |
| --- | --- |
| a text or category column | a colour per category, from the palette, with a legend |
| a number column | a colour scale (a colormap), with a gradient legend |
| a hex colour (`"#d62728"`, `"#888"`, or with alpha `"#d6272880"`) | every mark of the layer in it |

```python exec="on" source="above" session="colours" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

cars = load("cars")
plot = Trellis(cars, wrap="origin", cols=3, panel_height=170)
plot.points(x="weight", y="mpg", color="year", size=5, tooltip=["name"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

A number column you mean as categories (years, cylinder counts) gets a colour scale.
`as_category()` reads it as categories: a colour per value, from the palette, with a legend
of the values in order:

```python exec="on" source="above" session="colours" html="true"
plot = Trellis(cars, wrap="origin", cols=3, panel_height=170).as_category("cylinders")
plot.points(x="weight", y="mpg", color="cylinders", size=5, tooltip=["name"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

The values are the levels, in order (`3, 4, 5, 6, 8`; negative numbers first), labelled as
numbers (`4`, not `4.0`), rows without one last as `(missing)`. The column is categories
everywhere in the plot: an axis gets a band per value, `group=` a series per value, and
`order("cylinders", [8, 6, 4])` orders them. With a database (`load="pages"`), the
database finds the values and selects by them.

## A palette

`palette=` gives the category colours, in the order of the categories:

```python exec="on" source="above" session="colours" html="true"
import polars as pl

kinds = ["sun", "fog", "drizzle", "rain", "snow"]
months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
monthly = (
    load("seattle_weather")
    .group_by("weather", year=pl.col("date").dt.year(), month=pl.col("date").dt.strftime("%b"))
    .agg(days=pl.len())
)
plot = (
    Trellis(monthly, wrap="year", cols=2, panel_height=130, title="Seattle weather",
            palette=["#e7ba52", "#c7c7c7", "#aec7e8", "#1f77b4", "#9467bd"])
    .order("month", months)
    .order("weather", kinds)
    .bars(x="month", y="days", color="weather")
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

The default palette is Tableau's ten colours. Rows whose category is missing get a
`(missing)` colour of their own.

## Order categories

Categories (panels, bands on an axis, colours) are in alphabetical order, except a pandas
`Categorical` or a Polars `Enum`, which keep their own. `order()` sets it:

```python
plot.order("month", ["Jan", "Feb", "Mar"])              # these first, the rest after
plot.order("site", by="median", of="yield")             # by a summary of another column
plot.order("site", by="median", of="yield", descending=True)
```

Months are text, so they too would be alphabetical (Apr, Aug, Dec, ...). Listing them puts
them in calendar order, on the axis here:

```python exec="on" source="above" session="order" html="true"
from anytrellis import Trellis
from anytrellis.synthetic import sales

months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
plot = Trellis(sales(), wrap="store", panel_height=150)
plot.line(x="month", y="units", color="product").order("month", months)
plot
print(plot._embed_html())  # markdown-exec: hide
```

`by=` takes `"median"`, `"mean"`, `"min"`, `"max"`, `"sum"` or `"count"`. Ordering panels
by what they show, rather than by name, is what makes many patterns visible: see the
barley example in [Coming from Altair or lattice](from-altair-lattice.md#cleveland-and-lattice).

## The legend

The legend lists each colour column's categories, or its range. Clicking an entry selects
that colour's marks; Shift+click adds or removes more (see
[Select data](../tutorials/select.md)).

In a wrap whose last row is not full, the legend goes in the empty cells when it fits;
`Trellis(..., legend="bottom")` always puts it under the plot.

## Light and dark

The plot follows the notebook's theme: JupyterLab's, VS Code's or marimo's light and dark
themes, and these pages' (try the toggle at the top). Marks keep their colours; the
background, grid and text change.
