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

Bars count nothing themselves: to count rows, use a [histogram](distributions.md), or count
with your table library first (`df.group_by(...).len()`).

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

`rule()` draws reference lines across every panel: `rule(y=0)`, `rule(x=[1960, 1980])`.
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
