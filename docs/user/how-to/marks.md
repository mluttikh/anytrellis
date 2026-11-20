# Draw lines, points and bars

Each mark is a method that adds a layer, and every panel draws every layer, in the order
you added them. The methods return the plot, so they chain.

## Points

```python exec="on" source="above" session="marks" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

penguins = load("penguins")
plot = Trellis(penguins, wrap="species", panel_height=170)
plot.points(x="flipper_length_mm", y="body_mass_g", color="sex", size=6, opacity=0.7,
            tooltip=["island"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

`size=` is the diameter in pixels, `opacity=` from 0 to 1, and `tooltip=` adds columns to
what hovering shows.

### Shapes and sizes from columns

`shape=` gives each category of a column a shape: circle, square, triangle, diamond, plus,
cross and a triangle pointing down, then again. Give it the colour's column too, and the
groups differ in two ways at once: one legend shows both, and nobody has to tell the
colours apart. `size=` a number column makes each point's area grow with its value, from
2 to 14 pixels across (`size_range=` sets them), the largest drawn first so none hides a
smaller one:

```python exec="on" source="above" session="marks" html="true"
plot = Trellis(penguins, wrap="island", cols=3, panel_height=170)
plot.points(x="bill_length_mm", y="bill_depth_mm", color="species", shape="species",
            size="body_mass_g", opacity=0.75)
plot
print(plot._embed_html())  # markdown-exec: hide
```

A shape's name (`shape="square"`) draws every point so. Where points are dense enough to
be drawn as cells, they are cells until you zoom in.

## Lines

A line joins the rows of each series, sorted by x. `color=` makes a line per category;
`group=` makes separate lines without colouring them:

```python exec="on" source="above" session="marks" html="true"
gapminder = load("gapminder")
plot = Trellis(gapminder, wrap="region", cols=3, panel_height=120)
plot.line(x="year", y="life_expect", group="country", width=1, tooltip=["country"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

`group=["station", "sensor"]` takes several columns: a line per combination.

### Dashes

`dash=` a category column draws a line per category, each dashed its own way: solid,
dashed, dotted, dot-dash, long dash and two-dash, then again. With the colour's column as
well, a line reads by its dash where colours are hard to tell apart, or printed in grey:

```python exec="on" source="above" session="marks" html="true"
import polars as pl

some = gapminder.filter(pl.col("country").is_in(["Japan", "Brazil", "India", "Nigeria"]))
plot = Trellis(some, panel_height=200)
plot.line(x="year", y="life_expect", color="country", dash="country", width=2)
plot
print(plot._embed_html())  # markdown-exec: hide
```

`dash=(4, 3)` dashes every line alike: dash and gap lengths in pixels, as a rule's.

### Names at the ends of lines

`label="end"` writes each series' name at the end of its line, in its colour, in place of
the legend: the reader's eye stays on the data. It suits up to about seven lines:

```python exec="on" source="above" session="marks" html="true"
plot = Trellis(some, panel_height=200)
plot.line(x="year", y="life_expect", color="country", label="end", width=2)
plot
print(plot._embed_html())  # markdown-exec: hide
```

Each name appears once in the plot, in the panel where its line ends rightmost, at the
last point in view: zoom in and the names follow. Where lines end close together the
names move apart; one that would be too far from its line is left out until you zoom in.
Hovering a name shows its line in every panel, and a click selects it, as its legend
entry would. Without a colour column, the names are the `group=` columns' values.

### Steps

`step=` draws a line as steps: flat between rows, then straight up or down. Use it for a
value that holds until the next row (a price, a setting) or a total over each period, as
each month's rain here, centred on its month:

```python exec="on" source="above" session="marks" html="true"
import polars as pl

weather = load("seattle_weather")
monthly = weather.group_by(
    year=pl.col("date").dt.year().cast(pl.String), month=pl.col("date").dt.month()
).agg(pl.col("precipitation").sum())
plot = Trellis(monthly, wrap="year", cols=2, panel_height=120, y_title="rain (mm)")
plot.line(x="month", y="precipitation", step="mid")
plot
print(plot._embed_html())  # markdown-exec: hide
```

| `step=` | Each row's value |
| --- | --- |
| `"post"` | from its x to the next row's |
| `"pre"` | from the row before's x to its own |
| `"mid"` | from half way to the row before to half way to the next |

Hovering a step shows the row it starts from.

## Bars

Bars go from zero to y at each x. With a category `color=`, they stack by default;
`position="dodge"` puts them side by side, and `"identity"` overlaps them:

```python exec="on" source="above" session="marks" html="true"
import polars as pl

barley = load("barley").with_columns(pl.col("year").cast(pl.String))
plot = Trellis(barley, wrap="site", cols=3, panel_height=140)
plot.bars(x="variety", y="yield", color="year", position="dodge")
plot
print(plot._embed_html())  # markdown-exec: hide
```

The years are cast to text so they are categories (two colours), not numbers (a colour
scale). `width=` sets a bar's width as a share of the step between x values.

### Bars along y

When y is a category column and x is not, the bars lie along y, from zero to x. Long
category names then read across, and ranked bars read from the top:

```python exec="on" source="above" session="marks" html="true"
plot = Trellis(barley, wrap="site", cols=3, panel_height=170)
plot.bars(x="yield", y="variety", color="year")
plot
print(plot._embed_html())  # markdown-exec: hide
```

### Shares: `position="fill"`

`position="fill"` stacks the colours as shares of each stack, so every stack reaches 1
and the composition compares across positions and panels, whatever their totals. The axis
reads in percent (`format(y=...)` changes it):

```python exec="on" source="above" session="marks" html="true"
plot = Trellis(barley, wrap="site", cols=3, panel_height=140)
plot.bars(x="variety", y="yield", color="year", position="fill")
plot
print(plot._embed_html())  # markdown-exec: hide
```

`area()` and `hist()` take `position="fill"` too: each region's share of the population
at each year, each sex's share of each bin.

### Bars that summarise: `stat=`

With `stat=`, bars summarise the rows at each position (and colour) themselves:
`"count"` counts them (give only x, or only y for bars along y), and `"sum"`, `"mean"` and
`"median"` summarise y's values at each x (x's along a category y):

```python exec="on" source="above" session="marks" html="true"
cars = load("cars")
plot = Trellis(cars, wrap="origin", cols=3, panel_height=140)
plot.bars(x="cylinders", stat="count")
plot
print(plot._embed_html())  # markdown-exec: hide
```

```python exec="on" source="above" session="marks" html="true"
plot = Trellis(barley, panel_height=260, title="Mean yield over the six sites")
plot.bars(x="yield", y="variety", stat="mean", color="year")
plot
print(plot._embed_html())  # markdown-exec: hide
```

Counts and sums stack by colour, like other bars; means and medians go side by side
(`position="dodge"`), as they don't add up. Hovering a bar shows its position, its value
and how many rows it stands for, and brushing it selects those rows. With
`load="pages"`, the database counts and averages: no row is read. To count bins of a
number column instead of its values, use a [histogram](distributions.md).

## Several layers

Layers draw in order, so add the background first:

```python exec="on" source="above" session="marks" html="true"
from anytrellis.synthetic import sensors

readings = sensors(stations=4, sensors=2, hours=24 * 7)
plot = (
    Trellis(readings, wrap="station", cols=2, panel_height=130)
    .line(x="time", y="temp", color="sensor", width=1)
    .points(x="time", y="temp", color="sensor", size=2)
    .rule(y=0, color="#888888", dash=(4, 3))
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

`rule()` draws reference lines across every panel, `rule(y=0)`, `rule(x=[1960, 1980])`,
or each panel's own from a table (see [Reference lines](more-marks.md#reference-lines)).
Each layer gets a name (`points`, `line`, ...) for `selected("line")`; `name=` sets your
own.

## Each group against the rest

`facet="exclude"` draws, in each panel, the *other* panels' rows, in grey: each group seen
against all the others.

```python exec="on" source="above" session="marks" html="true"
plot = (
    Trellis(gapminder, wrap="region", cols=3, panel_height=120,
            title="Life expectancy, each region against the rest")
    .line(x="year", y="life_expect", group="country", facet="exclude", width=1, name="others")
    .line(x="year", y="life_expect", group="country", color="region", tooltip=["country"])
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

| `facet=` | Each panel draws |
| --- | --- |
| `"auto"` (default) | its own rows; every row when the layer's table has no facet columns |
| `"include"` | its own rows |
| `"all"` | every row |
| `"exclude"` | the other panels' rows, in grey; never selected |
