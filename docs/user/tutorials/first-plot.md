# Your first trellis plot

In this tutorial you split a table of cars into panels, look around in the plot, colour the
cars by a column, add a fitted line, and save the plot as a page to share. It takes about
ten minutes.

You need a notebook (JupyterLab, VS Code or marimo) with anytrellis and Polars installed:
`pip install "anytrellis[examples]"`. See [how to install anytrellis](../how-to/install.md).
Type each step into a new cell and run it.

## 1. Get a table

anytrellis comes with a few small datasets. `cars` has 406 cars from the 1970s and early
1980s, one row per car:

```python exec="on" source="above" session="first" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

cars = load("cars")
cars.head()
print(cars.head()._repr_html_())  # markdown-exec: hide
```

## 2. A panel per group

A trellis plot splits a table into groups and draws the same plot for each one. Here,
`wrap="origin"` makes a panel per origin, and each panel draws the cars' weight against
their fuel use:

```python exec="on" source="above" session="first" html="true"
plot = Trellis(cars, wrap="origin")
plot.points(x="weight", y="mpg")
plot
print(plot._embed_html())  # markdown-exec: hide
```

The last line, `plot`, shows the plot below the cell. The three panels share their scales:
the same weight is at the same place in each, so you can compare the panels at a glance.
The axes are drawn only once, at the edges.

## 3. Look around

The plot above is live, like the one in your notebook. Try this:

1. **Click the plot**, then **scroll** over a panel to zoom in on x. All three panels zoom
   together, because they share x. (Before a click, scrolling scrolls the page.)
2. **Drag** to pan. **Shift+scroll** zooms y.
3. **Hover** over a point to see its values, and a crosshair in every panel.
4. **Double-click** a panel to see it alone. Press **Page Down** for the next one, and
   **Backspace** to go back to all of them.
5. Press **r** to reset the zoom.

[Mouse and keys](../reference/mouse-and-keys.md) lists everything the plot does.

## 4. Colour by a column

Give `color=` a column. A column of numbers, like `cylinders`, is drawn along a colour
scale; a column of text gets a colour per category. `tooltip=` adds columns to what
hovering shows:

```python exec="on" source="above" session="first" html="true"
plot = Trellis(cars, wrap="origin", title="Fuel use and weight, by origin")
plot.points(x="weight", y="mpg", color="cylinders", tooltip=["name", "year"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

Hover over the lightest cars in the Japan panel: their names are in the tooltip.

## 5. Add a layer

Each method adds a layer, and every panel draws every layer, in the order you added them.
A `smooth()` layer fits a line to each panel's points, with a band for its uncertainty.
The methods return the plot, so you can chain them:

```python exec="on" source="above" session="first" html="true"
plot = (
    Trellis(cars, wrap="origin", title="Fuel use and weight, by origin")
    .points(x="weight", y="mpg", color="cylinders", tooltip=["name"])
    .smooth(x="weight", y="mpg", color="#444444")
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

In every origin, heavier cars use more fuel. At the same weight, European and Japanese cars
went only a little further on a gallon than American ones: most of the difference between
the origins is that the American cars were heavier.

## 6. Share it

`save_html` writes the plot, with its data, into one HTML file. It opens in any browser,
without Python, and zooms and hovers as it does here:

```python
plot.save_html("cars.html")
```

## What you learned

- `Trellis(table, wrap="column")` makes a panel per level of a column.
- Methods like `points()` and `smooth()` add layers that every panel draws.
- Panels share their scales, and zoom together.
- `color=` and `tooltip=` take columns.
- `save_html()` writes a page that opens without Python.

Next: [Facets and scales](facets-and-scales.md) shows grids of panels, and what to do when
the panels' values are too different to share a scale.
