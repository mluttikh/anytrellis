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

### The direction a wrap fills

A wrap fills its cells row by row from the top left, as text runs. `direction="v"` fills
them column by column instead, as ggplot2's `facet_wrap(dir = "v")` does, which keeps
neighbouring levels one under another:

```python exec="on" source="above" session="layout" html="true"
gapminder = load("gapminder")
plot = Trellis(gapminder, wrap="year", cols=4, direction="v", panel_height=110)
plot.points(x="fertility", y="life_expect", color="region", size=4)
plot
print(plot._embed_html())  # markdown-exec: hide
```

Two letters name any start and direction: the first where a run starts (`l`eft, `r`ight,
`t`op, `b`ottom), the second where the next run goes. `"lt"` is `"h"`, the default;
`"tl"` is `"v"`; `"lb"` fills rows from the bottom up, so the first level is at the bottom
left, as lattice draws them; `"rt"` fills rows from the right, for a language read right
to left. Filled by columns, a wrap keeps its `cols=` and has as few rows as hold every
panel. A paged wrap fills each page the same way. The settings panel's Fill choice changes
it, and so does `plot.direction = "v"`.

## Panels placed by hand: a layout table

Some panels belong in a shape: the countries of a map, the wells of a plate, the floors and
rooms of a building. `layout=` places each panel at a row and column, as R's geofacet
does. Give a table with the wrap column and `row` and `col`, counted from 1, or a dict
`{level: (row, col)}`. The cells without a panel stay empty:

```python exec="on" source="above" session="layout" html="true"
import polars as pl

europe = pl.DataFrame(
    [("Iceland", 1, 1), ("Norway", 1, 4), ("Finland", 1, 5),
     ("Ireland", 2, 1), ("United Kingdom", 2, 2), ("Netherlands", 2, 3),
     ("Germany", 2, 4), ("Poland", 2, 5),
     ("France", 3, 2), ("Belgium", 3, 3), ("Switzerland", 3, 4), ("Austria", 3, 5),
     ("Portugal", 4, 1), ("Spain", 4, 2), ("Italy", 4, 4), ("Croatia", 4, 5),
     ("Georgia", 4, 7), ("Greece", 5, 5), ("Turkey", 5, 6)],
    schema=["country", "row", "col"], orient="row",
)
in_europe = gapminder.filter(pl.col("region") == "Europe & Central Asia")
plot = Trellis(in_europe, wrap="country", layout=europe, panel_height=70)
plot.area(x="year", y="fertility")
plot
print(plot._embed_html())  # markdown-exec: hide
```

The table can be a DataFrame, a DuckDB query or any table the plot takes, and can hold
more places than the data has panels (a map of every country, used for a few): those cells
stay empty. A panel without a place is an error, and so are two panels in one cell. With
several wrap columns, the table has each of them (and a dict's keys are tuples). A layout
table places every panel, so it doesn't go with `cols=`, `direction=` or `rows=`; with
`page=`, every page has the same cells.

## Columns repeated as rows

Measurements side by side in columns (a temperature, a rainfall, a wind speed) are often
best read stacked, on one time axis, each on its own scale. `repeat=` makes a row of
panels per column:

```python exec="on" source="above" session="layout" html="true"
weather = load("seattle_weather")
plot = Trellis(weather, repeat=["temp_max", "precipitation", "wind"],
               labels={"temp_max": "High (°C)", "precipitation": "Rain (mm)",
                       "wind": "Wind (m/s)"}, panel_height=90)
plot.line(x="date", y="value", width=0.8)
plot
print(plot._embed_html())  # markdown-exec: hide
```

The data is melted: a row per row and column, the column's name in `measure` and its value
in `value`, which the layers draw as `y`. The rows keep the order given, each strip names
its column by its label, and each row has its own y scale (`share_y="row"`; give
`share_y=True` for one scale). `col=` and `page=` still facet, so
`Trellis(weather, repeat=[...], col="year")` is a grid of measurements by years.
`selected()` returns the melted rows, with `measure` and `value`. From a database, the
melt is part of the query, so `load="pages"` reads a page's rows only. The columns must
all be numbers (or all times); `repeat=` doesn't go with `row=` or `wrap=`, and a data
that has a `measure` or `value` column already has to rename it.

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

### Panels sized by their range: `space=`

With free scales, one panel may show three categories and the next eight, each squeezed
into the same width. `space="free_x"` makes each column of panels as wide as its x range
takes of them all, so a category (or a year) is as wide in every panel, as ggplot2's
`facet_grid(space = "free_x")` does:

```python exec="on" source="above" session="layout" html="true"
cars = load("cars").with_columns(cyl=pl.col("cylinders").cast(pl.String))
plot = Trellis(cars, col="origin", share_x="col", space="free_x", panel_height=180)
plot.bars(x="cyl", stat="count", color="cyl")
plot
print(plot._embed_html())  # markdown-exec: hide
```

`space="free_y"` sizes each row by its y range in the same way, and `space="free"` both.
The ranges are the panels' own, so `space=` goes with free scales along its lines:
`"free_x"` with `share_x="col"` or `False`, `"free_y"` with `share_y="row"` or `False`.
A wrap's columns hold panels of different ranges, so in a wrap `"free_x"` needs one row
of panels and `"free_y"` one column. `plot.space = "fixed"` sizes every panel the same
again.

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

## Titles, a subtitle and a caption

```python
plot = Trellis(
    cars, wrap="origin",
    title="Fuel use falls with weight in every region",
    subtitle="Miles per gallon by weight, 1970 to 1982 models",
    caption="Source: UCI Machine Learning Repository",
    labels={"mpg": "Fuel use (mpg)", "weight": "Weight (lb)", "cylinders": "Cylinders"},
)
plot.points(x="weight", y="mpg", color="cylinders")
```

A title can say what the plot shows; the subtitle under it, what is plotted, in what units,
over what period; the caption under the plot, where the data come from. Readers remember
annotated charts better, and the text is part of every image you export, from the page or
with `save_svg` / `save_png`. A long subtitle or caption wraps.

`labels=` names columns for readers, once for the plot: the axis titles, the legend's title,
the tooltips, a page column's title and the sort and filter menus show the label in place of
the name. Code goes on naming columns as they are: `select(color="Europe")`,
`sort_panels("mean mpg")`. A pairs plot shows the labels on its strips too.

`x_title=` and `y_title=` set an axis title outright, over its label:

```python
Trellis(cars, wrap="origin", x_title="weight (lb)", y_title="miles per gallon")
```

A time axis has no title (dates say what they are) unless you give one; `x_title=""` hides
any. The y title sits level over the plot's top left, `↑ miles per gallon`, where it reads
without tilting your head.

## The look

Three themes come with anytrellis:

| `theme=` | What it draws |
| --- | --- |
| `"minimal"` (the default) | Nothing behind the data but a faint grid (across y, and across x for points); strips as semibold titles at each panel's left; the y title level over the plot; Petroff's colour-vision-tested palette |
| `"framed"` | After Observable Plot: a thin frame around each panel and more room between them, so each facet reads as one; strips centred over the panels; the x title at the end of its axis (`weight →`); d3's observable10 palette |
| `"classic"` | anytrellis before 0.6: grey panels and strips, a full grid, titles on their side, tab10 |

```python
Trellis(cars, row="origin", col="cylinders", theme="framed")
```

### Change the look

A theme is a dozen settings, and `anytrellis.Theme` starts from a named one and changes
any of them:

```python
import anytrellis as at

roomy = at.Theme("minimal", frame=True, panel_gap=14, strip_align="center")
Trellis(cars, wrap="origin", theme=roomy)
```

| Setting | Values |
| --- | --- |
| `panel_fill` | `True`: each panel filled light grey |
| `frame` | `True`: a thin line around each panel |
| `grid` | `"auto"` (across y, and across x for points), `"x"`, `"y"`, `"both"`, `"none"` |
| `grid_opacity` | the grid's opacity, 0 to 1 (it is the text colour, so it suits light and dark) |
| `axis_lines` | which axes draw a line along the panels' edge: `"x"`, `"y"`, `"both"`, `"none"` |
| `strip_fill` | `True`: strips filled grey; `False`: the label alone, as a title |
| `strip_align` | `"left"` or `"center"` |
| `strip_bold` | semibold strip labels |
| `y_title` | `"top"`: level over the plot (`↑ mpg`); `"side"`: on its side at the left |
| `x_title` | `"center"` under the plot, or `"end"` of the axis (`weight →`) |
| `row_labels` | a grid's row labels `"level"` at the right, or on their `"side"` |
| `panel_gap` | pixels between panels |
| `palette` | category colours: a name (`"petroff10"`, `"observable10"`, `"tab10"`, ...) or a list |
| `font_size` | the text's size in pixels, or `"auto"` (see below) |
| `context` | `"paper"`, `"notebook"`, `"talk"` or `"poster"` (see below) |

### Text size, and plots for slides

Text is 12 px. In minimal and framed (`font_size="auto"`), panels under 160 px wide set
their ticks, strips and axis titles at 11 px, so a wrap of many small panels stays
legible, and an opened panel sets them at 13 px. `font_size=14` sets a size that doesn't
step; the title is 1.15 times as big, the caption 11/12.

`context=` scales the text, the lines and the points together, for where the plot is
shown, as seaborn's contexts do:

| `context=` | Scale | For |
| --- | --- | --- |
| `"paper"` | 0.8 | a figure in a document |
| `"notebook"` (the default) | 1 | a notebook |
| `"talk"` | 1.5 | slides |
| `"poster"` | 2 | a poster |

```python exec="on" source="above" session="layout" html="true"
import anytrellis as at

plot = Trellis(cars, wrap="origin", theme=at.Theme(context="talk"),
               title="Heavier cars use more fuel")
plot.points(x="weight", y="mpg", color="cylinders")
plot
print(plot._embed_html())  # markdown-exec: hide
```

Line widths and point sizes you give are scaled too, so `width=2` draws 3 px lines in
talk. Images saved from Python (`save_png`, `save_svg`) are drawn the same way.

`set_theme` makes a theme the default of every plot made after it in the session, so a
notebook sets it once at the top:

```python
at.set_theme("framed", palette="tab10")
at.set_theme(context="talk")              # minimal, for slides
at.set_theme()                            # back to minimal
```

A plot's `theme=` and `palette=` still win over the session's. The theme is drawn the same
in the notebook, in a saved page and in `save_svg` / `save_png`.

## The legend's place

```python
plot.legend("right", title="Cylinders")
```

`"auto"` (the default) puts it in a wrap's empty cells when it fits, and under the plot
otherwise; `"top"` puts it over the panels, under the title; `"bottom"` always puts it
under the plot; `"right"` in a column right of the
plot, the panels narrowed to make room (under the plot when it is too tall for that);
`"none"` leaves it out. `Trellis(legend=...)` takes the same. `title=` names it, by
default the colour column's label; with several colour columns, give a dict by column.

## One panel at a time

Double-click a panel to see it alone, or use the button that shows at its top right when
you point at it; Page Up and Page Down step through the others at the same zoom, and
Backspace goes back. The arrow keys move a ring from panel to panel, and Enter opens the
one it is on (or the one under the pointer). `Trellis(..., panel_buttons=False)` leaves
the buttons out (for a page to publish, say); the double-click and the keys still work.
From Python:

```python exec="on" source="above" result="python" session="layout"
plot = Trellis(penguins, wrap="island").points(x="flipper_length_mm", y="body_mass_g")
print(plot.panels())
```

```python
plot.open("Biscoe")   # a grid's panel: plot.open("female", "Gentoo")
plot.focused          # "Biscoe", also when opened in the browser
plot.close()
```

## Compare every panel with one

*Compare with this*, the last of a panel's buttons (or ++c++ with the pointer or the ring
on it), draws that panel's marks in grey in every other: each panel against a reference
you choose as you go, without writing a layer for it. A chip in the header says which, and
Clear, ++esc++ or the button again stops it.

```python exec="on" source="above" session="layout" html="true"
gapminder = load("gapminder")
plot = Trellis(gapminder, wrap="region", cols=3, panel_height=130)
plot.line(x="year", y="life_expect", group="country", width=1)
plot.compare("Europe & Central Asia")
plot
print(plot._embed_html())  # markdown-exec: hide
```

`plot.compare()` stops comparing, and `plot.compared` is the panel compared with. Images
saved from Python draw it too. To draw all the other panels' rows behind each panel instead
(each against the rest), give the layer `facet="exclude"`.
