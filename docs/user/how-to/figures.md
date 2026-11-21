# Put different plots in one figure

A trellis plot repeats one plot for each group. Sometimes you want different plots
together: a scatterplot beside a histogram of one of its columns, or a map of panels over
a summary. `|` puts plots side by side and `/` puts one under another; the result shows
in a notebook, saves as one page and as one image.

## Side by side and one under another

```python exec="on" source="above" session="figures" html="true"
from anytrellis import Trellis, concat
from anytrellis.datasets import load

cars = load("cars")
scatter = Trellis(cars, wrap="origin", cols=2, title="Weight and mpg").points(
    x="weight", y="mpg", color="cylinders")
counts = Trellis(cars, title="Horsepower").hist(x="horsepower")
boxes = Trellis(cars, title="mpg by origin", height=260).box(x="origin", y="mpg")

figure = (scatter | counts) / boxes
figure
print(figure._embed_html())  # markdown-exec: hide
```

`a | b | c` is one row of three, and `a / b / c` one column; `(a | b) / c` puts a row over
a plot. Each plot keeps its own scales, legend, toolbar and zoom: it is the same plot as
on its own, given a share of the width. Each row is as high as its highest plot, and each
plot sits at the top of its row.

## A grid, widths and a title

`concat()` makes the same figures, and more: a grid of `cols=` columns filled row by row,
each column's share of the width (`widths=`), and a title over the whole.

```python exec="on" source="above" session="figures" html="true"
figure = concat(scatter, counts, boxes, cols=2, widths=[2, 1], title="Cars")
figure
print(figure._embed_html())  # markdown-exec: hide
```

Without `cols=`, the plots go in one row. A titled figure is kept whole when you put it
beside or under another plot; otherwise `(a | b) | c` is one row of three.

## Linked plots in a figure

Plots linked with [`link()`](link.md) stay linked in a figure, in a notebook and in its
saved page: a brush in the scatterplot lights up the same cars in the histogram.

```python
from anytrellis import link

link(scatter, counts)
(scatter | counts).save_html("cars.html")
```

## Save the figure

```python
figure.save_html("cars.html")              # one page, no Python needed to open it
figure.save_svg("cars.svg")                # one image, drawn in Python
figure.save_png("cars.png", width=1200)    # needs anytrellis[png]
figure.save_pdf("cars.pdf", width="180mm") # a vector PDF for print; anytrellis[pdf]
figure.plots                               # its plots, row by row
```

The image puts each plot where the page does: the same columns, the same 24 px between
plots. Its width is the figure's as last shown, or 400 px a column (at least 800). Each
plot is drawn as its own `save_svg` draws it, with the zoom, selection and opened panel it
shows.

## In marimo

In marimo a figure shows as stacks of its plots (`mo.hstack` rows in a `mo.vstack`),
the same columns and widths.

## When plots are narrow

A plot too narrow for its title and toolbar side by side puts its toolbar on a line under
the title. Give a figure fewer columns, or a wider column with `widths=`, when its plots
have many panels.
