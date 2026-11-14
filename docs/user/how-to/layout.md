# Choose a facet layout

A trellis has two layouts: a **wrap** of one column's levels, filled row by row, or a
**grid** that crosses two columns. Pick a wrap when the panels are a list (countries,
stations, years); pick a grid when they are a table of two things (sex by species).

## A wrap: `wrap=` and `cols=`

```python exec="on" source="above" session="layout" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

penguins = load("penguins")
plot = Trellis(penguins, wrap="island", cols=3, panel_height=180)
plot.points(x="flipper_length_mm", y="body_mass_g", color="species")
plot
print(plot._embed_html())  # markdown-exec: hide
```

`cols=` sets how many panels go in a row; without it, a wrap has about the square root
of the number of panels. When the last row is not full, the legend goes in its empty cells if it fits there.

A wrap of more than 100 panels shows them a page at a time; `rows=` sets a page's rows
(see [Page through many panels](pages.md)).

## A grid: `row=` and `col=`

```python exec="on" source="above" session="layout" html="true"
known = penguins.drop_nulls("sex")
plot = Trellis(known, row="sex", col="species", panel_height=150)
plot.points(x="bill_length_mm", y="bill_depth_mm", color="island")
plot
print(plot._embed_html())  # markdown-exec: hide
```

A grid keeps every combination, also those without rows, so its rows and columns stay
aligned. `row=` alone makes a column of panels, and `col=` alone a row of them.

## Several columns as one facet

Each of `wrap=`, `row=` and `col=` takes a list of columns too: a panel per combination of
their levels.

```python exec="on" source="above" session="layout" html="true"
plot = Trellis(penguins, wrap=["species", "island"], cols=3, panel_height=150)
plot.points(x="flipper_length_mm", y="body_mass_g", color="sex")
plot
print(plot._embed_html())  # markdown-exec: hide
```

Each column gets a strip, the first on the outside. A strip spans the panels next to each
other that share its level, as ggh4x's nested strips do in R: here one Adelie strip
over its three islands. A grid nests its strips the same way, the column strips stacked
on top and the row strips side by side on the right, the first column's outermost.

`strips="joined"` shows one strip per panel instead, with the levels joined by ` · `:

```python
Trellis(penguins, wrap=["species", "island"], strips="joined")
```

Either way, a panel's name in `panels()` and `open()` is its levels joined by ` · `
(`"Adelie · Biscoe"`).

## A grid with cells that can't have data

A grid has a cell for every combination of its rows and columns. Some combinations can't
happen: a species that doesn't live on an island, a step that comes before the step it
starts from. Those cells stay empty, and with many of them the grid is mostly empty frames.
`empty="blank"` leaves them out. The other panels keep their rows and columns, and the axes
are drawn into the blank cells next to them:

```python exec="on" source="above" session="layout" html="true"
import polars as pl

counted = penguins.with_columns(
    title=pl.format("{} on {}: {} birds", "species", "island", pl.len().over("species", "island"))
)
plot = Trellis(counted, row="species", col="island", empty="blank", strip_label="title",
               panel_height=140)
plot.points(x="flipper_length_mm", y="body_mass_g", color="sex")
plot
print(plot._embed_html())  # markdown-exec: hide
```

Keep the default, `empty="draw"`, when an empty cell is news: data that should be there
and isn't. With `page=`, a cell is left out when it has no data on any page, so every page
has the same cells and turning the pages moves nothing. A cell with data on some pages
only is drawn, empty, on the others: there, its emptiness is news.

`strip_label="title"` names each panel with the value of a column, in a strip over the
panel. The column must have one value per panel; make it with the data, as above, or in
the database's query. A panel without one is named by its levels. The rows' and columns'
strips go, since each panel names itself. The panel's name in `panels()` and `open()` stays
its levels (`"Adelie · Biscoe"`).

## Margins: the rows and columns together

`margins=True` adds an "(all)" row under a grid's rows and an "(all)" column right of its
columns, as ggplot2's `facet_grid(margins = TRUE)` does. Each panel of the (all) column has
every row of its row, each panel of the (all) row every row of its column, and the corner
has them all. Every layer draws them, and summaries (a smooth, a histogram, a box) are
computed from their rows, so each margin shows what its row or column has in common:

```python exec="on" source="above" session="layout" html="true"
cars = load("cars").filter(pl.col("cylinders").is_in([4, 6, 8]))
plot = Trellis(cars, row="origin", col="cylinders", margins=True, panel_height=110)
plot.points(x="horsepower", y="mpg", size=4).smooth(x="horsepower", y="mpg")
plot
print(plot._embed_html())  # markdown-exec: hide
```

`margins="row"` adds the (all) row alone, `margins="col"` the (all) column. A row selected
in a margin is selected in its own panel too, and `selected()` has it once. Margins work
with `empty="blank"` (a margin is drawn when its row or column has data) and with `page=`
(each page's grid has its own), but not with `load="pages"`, where the database
summarises each panel's rows on its own.

## Size

| Argument | Sets |
| --- | --- |
| `panel_height=160` | Each panel's height in pixels |
| `height=600` | The whole plot's height; the panels share it |
| `aspect=1` | Each panel's height as a multiple of its width: `1` is square |
| `aspect="bank"` | The shape that shows the lines' median slope at 45 degrees |
| none of them | Each panel is about 0.6 times as high as it is wide, from 90 to 300 pixels |

The width is the notebook's or the page's. A plot keeps the width it is given and fits
its panels in it.

Full screen and an opened panel take the room the screen gives. Panels with an `aspect`,
banked or a number, keep their shape there: as large as fits, and narrower and centred
when the screen is too low for the whole width. An image of a given `height`
(`save_png(height=...)`) keeps it in the same way. Without an `aspect`, the panels
stretch to the screen's height.

### Banking to 45 degrees

How steep a line looks depends on the panel's shape, and changes are easiest to compare
when the line's segments slope at about 45 degrees (Cleveland, *Visualizing Data*, 1993).
`aspect="bank"` picks the shape that shows the median slope of every line's segments at
45 degrees, each measured in its own panel's ranges:

```python exec="on" source="above" session="layout" html="true"
weather = load("seattle_weather").with_columns(
    year=pl.col("date").dt.year().cast(pl.String),
    day=pl.col("date").dt.ordinal_day().cast(pl.Float64),
)
plot = Trellis(weather, wrap="year", cols=1, aspect="bank")
plot.smooth(x="day", y="temp_max", span=0.3, se=False)
plot
print(plot._embed_html())  # markdown-exec: hide
```

It banks the `smooth()` fits, or without them the `line()` layers. Day-to-day noise has
steep segments, so a noisy line alone banks to a flat, wide panel: add a smooth to bank
the trend instead, with the line still drawn around it. Segments that neither rise nor
fall don't count, and the shape stays between 0.02 and 5 times as high as wide. `panel_height=` and `height=` take precedence. With
`load="pages"`, the shape comes from the panels read first and stays as the pages turn.

## Titles

```python
Trellis(cars, wrap="origin", title="Fuel use", x_title="weight (lb)", y_title="miles per gallon")
```

The axis titles default to the column names; `x_title=""` hides one.

## The legend's place

`legend="auto"` (the default) puts it in a wrap's empty cells when it fits, and under the
plot otherwise; `legend="bottom"` always puts it under the plot.

## One panel at a time

Double-click a panel to see it alone (or press Enter over it); Page Up and Page Down step
through the others at the same zoom, and Backspace goes back. From Python:

```python exec="on" source="above" result="python" session="layout"
plot = Trellis(penguins, wrap="island").points(x="flipper_length_mm", y="body_mass_g")
print(plot.panels())
```

```python
plot.open("Biscoe")   # a grid's panel: plot.open("female", "Gentoo")
plot.focused          # "Biscoe", also when opened in the browser
plot.close()
```
