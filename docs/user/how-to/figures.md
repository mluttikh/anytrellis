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

## Panels lined up

The plots' panels line up, as in patchwork: in a column their left and right edges, in a
row their tops. Above, the box plot's panel starts and ends under the scatterplot's,
however wide their y labels, and the histogram's panel starts level with the
scatterplot's first row, under its title and toolbar.

In a row, the plots whose height is free are as high as the highest of them, so their x
axes line up too: the histogram reaches down to the scatterplot's last row. A plot whose
height you set (`height=`, `panel_height=` or `aspect=`) keeps it; only its top lines up.

Plots line up in the notebook, in the saved page and in the image alike. A figure inside
a figure lines up its own plots, not with the plots around it. To show each plot as it is
on its own, give `align=False`:

```python
concat(scatter, counts, align=False)
```

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

## One legend for the figure

When plots are coloured by the same column, each shows the same legend. `legend="collect"`
shows it once, under the figure, as patchwork's `guides="collect"`: each plot leaves its
own out, and a legend several plots have is shown once.

```python exec="on" source="above" session="figures" html="true"
weights = Trellis(cars, wrap="origin", cols=2, title="Weight and mpg").points(
    x="weight", y="mpg", color="origin")
power = Trellis(cars, title="Horsepower").hist(x="horsepower", color="origin")

figure = concat(weights, power, widths=[3, 2], legend="collect")
figure
print(figure._embed_html())  # markdown-exec: hide
```

The legend works as each plot's would, in every plot that has it: a click on an entry
selects its marks in each (Shift adds one), hovering it shows them, and a double-click
shows them alone. A plot with `legend("none")` adds none of its legends. The image
(`save_svg`, `save_png`, `save_pdf`) draws the legend under the plots too.

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
