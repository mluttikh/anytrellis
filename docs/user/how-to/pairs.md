# Plot every pair of columns

`pairs()` draws a scatterplot matrix: every pair of a table's number columns against each
other, one variable on x in each column of panels and one on y in each row. A variable's
scale is shared along its column and its row, so a point sits at the same height across
its row and at the same place across its column. The diagonal shows each variable on its
own.

```python exec="on" source="above" session="pairs" html="true"
from anytrellis import pairs
from anytrellis.datasets import load

penguins = load("penguins")
plot = pairs(
    penguins,
    ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"],
    color="species",
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

The column strips on top and the row strips on the right name the variables; a panel's
name is its row's variable, then its column's (`"bill_depth_mm · bill_length_mm"`), as
`panels()` and `open()` use it.

## Brush one panel, see the rows everywhere

Press **s** and drag a box in any panel: the rows inside it light up in every panel, so a
cluster found in one pair of variables shows where it lies in all the others. Hovering a
point shows its whole row.

`selected()` gives the brushed rows of your table, once each, as the same kind of table:

```python
plot.selected()                 # a Polars DataFrame here: the brushed penguins
```

From Python, select in one panel, named by its row's and its column's variable: here the
long, deep bills of bill depth (y) against bill length (x), mostly Chinstrap penguins:

```python exec="on" source="above" session="pairs" result="text"
plot.select(x=(45, 60), y=(17, 22), panel=("bill_depth_mm", "bill_length_mm"))
print(plot.selected()["species"].value_counts().sort("species"))
```

## The diagonal

`diag="auto"` (the default) draws a density curve per colour when there is a colour column,
and a histogram otherwise. Each is drawn over its variable's range, so the row's scale
still reads for it: a curve or bar reaching the top is the most common value, not a count.
Hover a curve or a bar for its density or count.

| Argument | Draws |
| --- | --- |
| `diag="density"` | a density curve per colour, each weighted by its share of the rows |
| `diag="hist"` | a histogram, stacked by colour; `bins=20` sets its bins |
| `diag=None` | nothing |

## Each pair once

`corner=True` keeps the panels below the diagonal (and the diagonal), since those above it
show the same pairs mirrored:

```python exec="on" source="above" session="pairs" html="true"
plot = pairs(
    penguins,
    ["bill_length_mm", "bill_depth_mm", "flipper_length_mm"],
    color="species",
    diag="hist",
    corner=True,
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Options

| Argument | Sets |
| --- | --- |
| `columns=[...]` | the number columns, in order (default: all of them but `color`) |
| `color="species"` | a colour column (numbers: a colormap, the diagonal in grey) or one colour |
| `palette=[...]` | colours for a category colour column |
| `size=3`, `opacity=0.6` | the points' diameter in pixels, and their opacity |
| `tooltip=["island"]` | more columns shown on hover |
| `title="Penguins"` | a title over the plot |
| `panel_height=150`, `height=600` | the panels' or the plot's height (default: square panels) |
| `legend="bottom"` | the legend under the plot |
| `renderer="webgl2"` | as for `Trellis` |

A `pairs()` plot is a `Trellis`: it zooms (a panel's zoom moves its row and column), saves
(`save_html`, `save_png`) and opens panels like any other. It draws its own layers, so it
takes no more.

## Large tables

Every row is drawn once in each panel off the diagonal: five columns of a million rows are
20 million points. Panels of more than 100,000 points are drawn as cells, as in
[Plot large data](large.md), and brushing still selects the rows themselves.
