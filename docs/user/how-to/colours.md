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

`palette=` also takes a name:

| Name | Colours |
| --- | --- |
| `"petroff10"` (the default), `"petroff8"`, `"petroff6"` | Petroff's, chosen to stay apart for readers with colour-vision deficiency and ranked by a survey of what people prefer; the first are the farthest apart, so a plot with few categories gets the most distinct ones |
| `"okabe-ito"` | Okabe and Ito's eight, made for colour-vision deficiency (black last) |
| `"observable10"` | Observable Plot's, the framed theme's |
| `"tab10"` | Tableau's ten, the default before and the classic theme's |

Rows whose category is missing get a `(missing)` colour of their own.

### Keep a category's colour

The palette's colours go to the categories in order, so a category's colour depends on
which others are in the plot. A dict gives categories their own, the same in every plot
that has them; the other categories take the palette's colours that are left:

```python exec="on" source="above" session="colours" html="true"
plot = Trellis(cars, wrap="cylinders", cols=5, panel_height=150,
               palette={"USA": "#d62728", "Europe": "#1f77b4"})
plot.points(x="weight", y="mpg", color="origin", size=5)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Number colours: `colormap()`

A number colour column runs along viridis, lowest to highest. `colormap()` picks another
colormap and how the values take it:

```python
plot.colormap("cividis")                         # another colormap
plot.colormap(["#ffffff", "#d62728"])            # your own, low to high
plot.colormap(scale="diverging", midpoint=0)     # change from zero
plot.colormap("Blues", scale="binned", bins=6)   # steps of round width
plot.colormap(scale="quantile", bins=4)          # four steps, a quarter of the values each
```

The colormaps are `"viridis"`, `"cividis"` (also for colour-vision deficiency) and
`"magma"`, dark to light; `"Blues"`, one hue; and `"RdBu"` and `"PuOr"`, which diverge from
a light middle. `"_r"` reverses any of them (`"viridis_r"`).

A **diverging** scale puts the colormap's middle at `midpoint=` and goes as deep on both
sides, so equal distances above and below look equally strong; the side with less range
doesn't reach its end. Its default is `"RdBu_r"`, red above the midpoint:

```python exec="on" source="above" session="colours" html="true"
gap = load("gapminder")
change = gap.with_columns(gap=pl.col("life_expect") - pl.col("life_expect").mean())
plot = Trellis(change, wrap="year", cols=4, panel_height=120,
               subtitle="Life expectancy above and below the average of all years")
plot.points(x="fertility", y="life_expect", color="gap", size=5, tooltip=["country"])
plot.colormap(scale="diverging", midpoint=0)
plot
print(plot._embed_html())  # markdown-exec: hide
```

A gradient is hard to read a value back from. A **binned** scale gives about `bins=`
steps of round width (`10–20`, `20–30`, ...), a colour each, and its legend lists them; a
**quantile** scale gives exactly `bins=` steps with as many values in each, for skewed
columns such as population. `format(color=)` writes the ranges:

```python exec="on" source="above" session="colours" html="true"
plot = Trellis(gap, wrap="year", cols=4, panel_height=120)
plot.points(x="fertility", y="life_expect", color="pop", size=5, tooltip=["country"])
plot.colormap("cividis", scale="quantile", bins=4).format(color=".2s")
plot
print(plot._embed_html())  # markdown-exec: hide
```

With a database (`load="pages"`), only a binned scale works: a quantile one needs every
row's value.

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

The legend lists each colour column's categories, or its range. Hovering an entry makes
its marks stand out in every panel. Clicking an entry selects that colour's marks;
Shift+click adds or removes more (see [Select data](../tutorials/select.md)). A
double-click shows that colour alone, the others hidden, until you double-click it again
or press Esc.

A number colour's legend is a gradient: drag on it to select the marks whose values are in
that range, or from Python, `select(color=(low, high))`. A binned scale's entries each
select their range, and Shift+click widens it.

```python
t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="horsepower")
t.select(color=(100, 150))  # as dragging on the gradient from 100 to 150
t.selection["color"]        # (100.0, 150.0)
```

With more than 20 entries, the legend shows the first 20, how many more there are, and a
search box that finds the rest. Images show the first 20.

In a wrap whose last row is not full, the legend goes in the empty cells when it fits;
`legend()` puts it elsewhere or renames it (see [Layout](layout.md#the-legends-place)).

## Light and dark

The plot follows the notebook's theme: JupyterLab's, VS Code's or marimo's light and dark
themes, and these pages' (try the toggle at the top). Marks keep their colours; the
background, grid and text change.
