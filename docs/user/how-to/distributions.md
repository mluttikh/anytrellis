# Show distributions

`hist()`, `box()`, `violin()`, `density()` and `errorbar()` summarise each panel's rows
in Python, and draw the result as bars, boxes, violins, lines and error bars. Their bins
and x values are the same in every panel, so the panels compare. Brushing selects whole
bins, boxes, violins and error bars, and `selected()` gives the rows they stand for.

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
| `position="stack"` | with a colour: stacked, or `"identity"` (overlapping) |

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

## Which one?

| You want to see | Use |
| --- | --- |
| How many rows, and where | `hist()` |
| Medians and spread, many groups side by side | `box()` |
| The shape of each group, side by side | `violin()` |
| The shape of a few groups, overlaid | `density()` |
| Means and how sure they are | `errorbar()` |
