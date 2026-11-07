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

```python
Trellis(cars, wrap=["origin", "cylinders"])
```

The panel's strip shows both levels, joined by ` · `, which is also its name in
`panels()` and `open()`.

## Size

| Argument | Sets |
| --- | --- |
| `panel_height=160` | Each panel's height in pixels |
| `height=600` | The whole plot's height; the panels share it |
| neither | Each panel is about 0.6 times as high as it is wide, from 90 to 300 pixels |

The width is the notebook's or the page's. A plot keeps the width it is given and fits
its panels in it.

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
