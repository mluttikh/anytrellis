# Use anytrellis in marimo

A plot is shown in marimo as in Jupyter: make it the last expression of a cell.

```python
import marimo as mo

from anytrellis import Trellis
from anytrellis.datasets import load

cars = load("cars")
plot = Trellis(cars, wrap="origin").points(x="weight", y="mpg", tooltip=["name"])
plot
```

Every example notebook is also a marimo notebook, in
[`examples/marimo`](https://github.com/mluttikh/anytrellis/tree/main/examples/marimo):

```bash
marimo edit examples/marimo/01_getting_started.py
```

## React to a selection

marimo runs a cell again when a UI element it uses changes. Wrap the plot's widget in
`mo.ui.anywidget` to make its selection such an element:

```python
brush = mo.ui.anywidget(plot.widget)
brush
```

```python
brush.value["selection"]       # this cell runs again after each brush
plot.selected()                # the brushed rows
```

Show `brush` instead of `plot`: it is the same plot. A brush reaches Python when you let
go of it.

## Things to know

- **One cell, one plot.** marimo does not allow two cells to define the same name, so
  give each plot its own name.
- **Linked plots** ([`link()`](link.md)) work in marimo as in Jupyter.
