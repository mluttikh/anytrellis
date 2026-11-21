# Show distributions

`hist()`, `box()`, `violin()`, `density()`, `ecdf()`, `errorbar()`, `hexbin()` and
`contour()` summarise each panel's rows in Python, and draw the result as bars, boxes,
violins, lines, error bars, hexagons and contour lines. Their bins and x values are the same
in every panel, so the panels compare. Brushing selects whole bins, boxes, violins, error
bars and hexagons, and `selected()` gives the rows they stand for.

## Histograms

```python exec="on" source="above" session="dist" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

penguins = load("penguins")
plot = Trellis(penguins, wrap="species", cols=3, panel_height=170)
plot.hist(x="flipper_length_mm", binwidth=2, color="sex")
plot
print(plot._embed_html())  # markdown-exec: hide
```

| Argument | Sets |
| --- | --- |
| `bins=30` | the number of bins over the values' range, or a list of edges |
| `binwidth=2` | a bin width instead, the edges at its multiples (times: `"7D"`, `"6h"`) |
| `stat="count"` | `"percent"` of each panel's rows, or `"density"` (an area of 1 per panel) |
| `position="stack"` | with a colour: stacked; `"fill"`, as shares of each bin (up to 100%); or `"identity"` (overlapping) |

`stat="percent"` compares the shape of panels with very different numbers of rows. A
category column as `x` counts its categories.

### Against the rest

A histogram with `facet="exclude"` counts the other panels' rows, in grey behind each
panel:

```python exec="on" source="above" session="dist" html="true"
plot = (
    Trellis(penguins, wrap="species", cols=3, panel_height=170, title="Flipper length")
    .hist(x="flipper_length_mm", binwidth=2, facet="exclude", name="others")
    .hist(x="flipper_length_mm", binwidth=2, color="species")
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Box plots

A box goes from the first to the third quartile, with a line at the median, whiskers to
the furthest values within 1.5 box heights (`whis=`), and the values beyond as points.
With a category `color=`, the boxes go side by side. When y is the category column, the
boxes lie sideways:

```python exec="on" source="above" session="dist" html="true"
import polars as pl

cars = load("cars").with_columns(cyl=pl.col("cylinders").cast(pl.String))
plot = Trellis(cars, wrap="origin", cols=3, panel_height=150, title="Fuel use")
plot.box(x="mpg", y="cyl", tooltip=["name"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

Hover a box for its quartiles, its count and its whiskers' reach; hover an outlier for its
row (and its `tooltip=` columns). `outliers=False` leaves the points out.

### The values themselves

A box hides how many values it summarises and how they lie. Points over it show them;
`jitter=` spreads them across their category's band (a fraction of its width) so equal
values don't hide each other. Each point keeps its place from draw to draw:

```python exec="on" source="above" session="dist" html="true"
plot = Trellis(cars, wrap="origin", cols=3, panel_height=150, title="Fuel use")
plot.box(x="cyl", y="mpg", outliers=False)
plot.points(x="cyl", y="mpg", jitter=0.4, size=4, opacity=0.6, tooltip=["name"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Violins

A violin is a box plot with the shape of the values: each side is the values' density,
with the median and the quartiles as lines across it. Like boxes, violins go side by side
with a category `color=` (other than x), and lie sideways when y is the category column:

```python exec="on" source="above" session="dist" html="true"
known = penguins.drop_nulls("sex")
plot = Trellis(known, wrap="species", cols=3, panel_height=170)
plot.violin(x="sex", y="flipper_length_mm", color="sex")
plot
print(plot._embed_html())  # markdown-exec: hide
```

| Argument | Sets |
| --- | --- |
| `scale="area"` | every violin the same area; `"count"`, areas as the rows' counts; `"width"`, every violin as wide |
| `inner="quartiles"` | the median and the quartiles inside; `"points"`, each value; `None`, nothing |
| `width=0.8` | the widest violin, as a share of the step between positions |
| `bw_adjust=1`, `cut=2` | the bandwidth and how far past the values the shape goes, as for densities (below) |
| `gridsize=100` | the number of samples along each violin |

Hover a violin for its count, median and quartiles. With `inner="points"`, the values are
points, and hovering one shows its row and its `tooltip=` columns.

## Densities

A density is a smooth histogram: a Gaussian kernel density estimate, each curve covering
an area of 1.

```python exec="on" source="above" session="dist" html="true"
plot = Trellis(cars, wrap="origin", cols=3, panel_height=150)
plot.density(x="mpg", color="cyl", fill=True)
plot
print(plot._embed_html())  # markdown-exec: hide
```

`bw_adjust=` scales the bandwidth (as in seaborn: 2 is smoother, 0.5 more detailed), and
`cut=` sets how far past the data each curve goes, in bandwidths.

### The values under the curve

`rug()` draws a short tick at the panel's bottom edge for each row's value, so a smooth
curve shows what it was smoothed from. `rug(y=...)` puts the ticks on the left edge, and
giving both draws both. The ticks stay at the edge, as long, however the panel is zoomed,
and a brush selects the rows whose values it covers.

```python exec="on" source="above" session="dist" html="true"
plot = Trellis(penguins, wrap="species", cols=3, panel_height=170)
plot.density(x="body_mass_g", color="sex").rug(x="body_mass_g", color="sex")
plot
print(plot._embed_html())  # markdown-exec: hide
```

| Argument | Sets |
| --- | --- |
| `length=8` | the ticks' length in pixels |
| `width=1` | their width in pixels |
| `opacity=0.5` | lighter where values are few, darker where many overlap |

Without `color=`, a rug takes the colour of the layer before it.

## Cumulative distributions

`ecdf()` draws the empirical cumulative distribution: a step line that rises at each
value, to the share of the rows at or below it. It needs no bins and no bandwidth, so
the panels compare exactly, and the median, the quartiles and the tails read off the y
axis.

```python exec="on" source="above" session="dist" html="true"
plot = Trellis(penguins, wrap="island", cols=3, panel_height=170)
plot.ecdf(x="body_mass_g", color="species")
plot
print(plot._embed_html())  # markdown-exec: hide
```

| Argument | Sets |
| --- | --- |
| `stat="proportion"` | the y axis: from 0 to 1; `"percent"`, or `"count"` of rows |
| `complementary=True` | the share above each value instead: a survival curve |

Hover a line for the share at that x, every colour's at once. A group with more than
1,000 different values steps at 1,000 of them, evenly spaced by rank. With
`load="pages"`, the database counts the rows in 1,024 bins over the values, and the
steps are at the bins' ends.

## Error bars

`errorbar()` draws each group's mean as a point, with a bar for its 95% confidence
interval: how sure the mean is, not how spread the values are.

```python exec="on" source="above" session="dist" html="true"
plot = Trellis(known, wrap="species", cols=3, panel_height=170)
plot.errorbar(x="sex", y="body_mass_g", color="sex")
plot
print(plot._embed_html())  # markdown-exec: hide
```

| Argument | Sets |
| --- | --- |
| `extent="ci"` | the confidence interval for the mean; `"se"`, the mean ± its standard error; `"sd"`, ± the standard deviation; `"range"`, the lowest to the highest value |
| `level=0.95` | the confidence interval's level |
| `cap=0.25` | the caps' width, as a share of the step between positions (`0`: no caps) |
| `points=False` | leaves the means' points out |

Hover a bar for its count, its mean and its ends.

### Ends you computed

To draw intervals you already have (a model's predictions, quantiles), give the ends as
columns: `ymin=` and `ymax=` with x as the positions, or `xmin=` and `xmax=` with y as
the positions for sideways bars. The centre (`y=` or `x=`) is optional; without it, there
are no points.

```python exec="on" source="above" session="dist" html="true"
by_year = cars.group_by("year", "origin").agg(
    mpg=pl.col("mpg").median(),
    low=pl.col("mpg").quantile(0.25),
    high=pl.col("mpg").quantile(0.75),
)
plot = Trellis(by_year, wrap="origin", cols=3, panel_height=150, title="Middle half of mpg")
plot.errorbar(x="year", y="mpg", ymin="low", ymax="high", cap=0)
plot
print(plot._embed_html())  # markdown-exec: hide
```

Each row is one bar, and brushing it selects that row.

## Two columns at once

When points pile up too thickly to read, `hexbin()` counts the rows in hexagons and
colours each by its count:

```python exec="on" source="above" session="dist" html="true"
gapminder = load("gapminder")
plot = Trellis(gapminder, wrap="region", cols=3, panel_height=170)
plot.hexbin(x="fertility", y="life_expect", bins=16)
plot
print(plot._embed_html())  # markdown-exec: hide
```

| Argument | Sets |
| --- | --- |
| `bins=30` | the number of hexagons across x; or `(nx, ny)`, across x and up y |
| `stat="count"` | the colour: the rows in each hexagon; `"percent"`, of each panel's rows |

The hexagons are the same in every panel, and as tall as wide on screen when the plot has
a number `aspect=` (otherwise, for a panel about 0.6 as high as wide). Hover one for its
count; brush to select its rows.

`contour()` draws the lines of a two-dimensional density instead: where the rows are
thickest, as a map draws a hill. Over points, it shows each group's middle and spread
without hiding the points:

```python exec="on" source="above" session="dist" html="true"
plot = Trellis(penguins, wrap="island", cols=3, panel_height=200)
plot.points(x="bill_length_mm", y="bill_depth_mm", color="species", opacity=0.4)
plot.contour(x="bill_length_mm", y="bill_depth_mm", color="species", levels=4)
plot
print(plot._embed_html())  # markdown-exec: hide
```

| Argument | Sets |
| --- | --- |
| `levels=6` | the number of lines, at even heights up to the highest density of any panel |
| `bw_adjust=1` | the bandwidth, as a multiple of Scott's rule: 2 is smoother |
| `gridsize=100` | the grid the density is computed on, along each axis |

The levels are the same in every panel, so a line means the same density everywhere.
Hover a line for its level. The lines stand for no rows, so a brush selects none.

With `load="pages"`, the database counts the rows in each hexagon, and for contours in
each cell of the grid, so neither reads the rows.

## Which one?

| You want to see | Use |
| --- | --- |
| How many rows, and where | `hist()` |
| Medians and spread, many groups side by side | `box()` |
| The shape of each group, side by side | `violin()` |
| The shape of a few groups, overlaid | `density()` |
| Groups compared without choosing bins; medians and tails | `ecdf()` |
| How many rows at each value, or each category | `bars(x=..., stat="count")` |
| Means and how sure they are | `errorbar()` |
| Where many points pile up, in x and y together | `hexbin()` |
| The shape of a few groups in x and y, overlaid | `contour()` |
| Each value under a summary | `rug()` |
