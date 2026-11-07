# Facets and scales

In this tutorial you cross two columns into a grid of panels, give panels their own
scales where their values differ too much to share one, switch to a log scale, and put the
panels in a useful order. It takes about ten minutes, and follows
[Your first trellis plot](first-plot.md).

## 1. A grid of two columns

`wrap=` splits a table by one column. `row=` and `col=` cross two: a row of panels per
level of one, a column per level of the other. Here the Palmer penguins, by sex and
species:

```python exec="on" source="above" session="facets" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

penguins = load("penguins").drop_nulls("sex")
grid = Trellis(penguins, row="sex", col="species", panel_height=160)
grid.points(x="bill_length_mm", y="bill_depth_mm", color="island")
grid
print(grid._embed_html())  # markdown-exec: hide
```

The column labels are on top and the row labels on the right. Every panel shares both
scales, so the Gentoo's longer, shallower bills stand out in both rows.

## 2. Empty cells stay

A grid keeps every combination of its rows and columns, also those without data, so the
rows and columns stay aligned. There were no American cars with 3 or 5 cylinders:

```python exec="on" source="above" session="facets" html="true"
cars = load("cars")
grid = Trellis(cars, row="origin", col="cylinders", panel_height=110)
grid.points(x="horsepower", y="mpg", size=4, tooltip=["name"])
grid
print(grid._embed_html())  # markdown-exec: hide
```

## 3. Scales of their own

Shared scales make panels comparable. But when the groups' values differ a thousandfold,
a shared scale flattens the small ones. Here is the population of six countries, from
Iceland (a few hundred thousand) to China (over a billion):

```python exec="on" source="above" session="facets" html="true"
import polars as pl

gapminder = load("gapminder")
six = gapminder.filter(
    pl.col("country").is_in(["China", "India", "United States", "Nigeria", "Japan", "Iceland"])
)
shared = Trellis(six, wrap="country", cols=3, panel_height=110, title="Population, shared y")
shared.line(x="year", y="pop")
shared
print(shared._embed_html())  # markdown-exec: hide
```

Only China and India show any change. `share_y=False` gives each panel its own y scale:

```python exec="on" source="above" session="facets" html="true"
free = Trellis(six, wrap="country", cols=3, panel_height=110, share_y=False,
               title="Population, free y")
free.line(x="year", y="pop")
free
print(free._embed_html())  # markdown-exec: hide
```

Now each country's growth shows, and each panel draws its own y axis, so you can still
read how far apart they are. x is still shared: zoom in on x and all six panels follow.

In a grid, `share_y="row"` gives each row a scale of its own, and `share_y="col"` each
column. [Share or free the scales](../how-to/scales.md) has more.

## 4. A log scale

A log scale keeps the panels comparable *and* shows each one's change: equal distances
are equal ratios, so a doubling looks the same at any size.

```python exec="on" source="above" session="facets" html="true"
logged = Trellis(six, wrap="country", cols=3, panel_height=110, y_scale="log",
                 title="Population, log y")
logged.line(x="year", y="pop")
logged
print(logged._embed_html())  # markdown-exec: hide
```

Nigeria's line is the steepest: its population grew fastest.

## 5. The order of panels

Panels come in alphabetical order unless you say otherwise. `order()` ranks them by a
summary of a column instead, which is often what makes a pattern visible. Here are the
origins of the cars, by their median fuel use:

```python exec="on" source="above" session="facets" html="true"
ranked = (
    Trellis(cars, wrap="origin", title="Origins by median fuel use")
    .order("origin", by="median", of="mpg", descending=True)
    .points(x="weight", y="mpg", size=4)
)
ranked
print(ranked._embed_html())  # markdown-exec: hide
```

`order()` also takes the levels in the order you want them:
`.order("origin", ["USA", "Europe", "Japan"])`.

## What you learned

- `row=` and `col=` make a grid, which keeps its empty cells.
- `share_x=` and `share_y=` take `True`, `"row"`, `"col"` or `False`.
- `y_scale="log"` keeps panels comparable when their values differ by orders of magnitude.
- `order()` sets the order of panels, by a list or by a summary.

Next: [Select data and use it in Python](select.md).
