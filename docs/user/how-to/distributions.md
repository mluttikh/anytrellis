# Show distributions

`hist()`, `box()` and `density()` summarise each panel's rows in Python, and draw the
result as bars, boxes and lines. Their bins and x values are the same in every panel, so
the panels compare. Brushing selects whole bins and boxes, and `selected()` gives the rows
they stand for.

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

## Which one?

| You want to see | Use |
| --- | --- |
| How many rows, and where | `hist()` |
| Medians and spread, many groups side by side | `box()` |
| The shape of a few groups, overlaid | `density()` |
