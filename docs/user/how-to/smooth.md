# Fit a smooth line

`smooth()` fits a line through each panel's points (and each colour's), with a band for
the uncertainty of its mean. It is computed in Python, per panel, when the plot is drawn.

```python exec="on" source="above" session="smooth" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

cars = load("cars")
plot = (
    Trellis(cars, wrap="origin", cols=3, panel_height=170, title="Fuel use and power")
    .points(x="horsepower", y="mpg", size=4, opacity=0.5, tooltip=["name"])
    .smooth(x="horsepower", y="mpg")
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Loess or a straight line

| `method=` | Fits | Tuned by |
| --- | --- | --- |
| `"loess"` (default) | local lines, each weighted to the nearby points (tricube weights) | `span=0.75`: the share of the points each local fit uses; smaller follows the data more closely |
| `"linear"` | one least-squares line | |

```python exec="on" source="above" session="smooth" html="true"
quartet = load("anscombe")
plot = (
    Trellis(quartet, wrap="dataset", panel_height=150, title="Anscombe's quartet")
    .points(x="x", y="y", size=7)
    .smooth(x="x", y="y", method="linear", fullrange=True, color="#d62728")
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

Anscombe's four datasets have the same least-squares line, and very different points:
fit, then look.

## The band

The band is the `level=0.95` confidence interval for the line (the mean of y at each x),
not for single points. `se=False` leaves it out. Hover the line for the interval at a
point.

## Other arguments

- `color=` with a category column fits a line per category.
- `fullrange=True` draws each line across the whole x axis, not only its own points' range.
- `n=80` sets how many points each line is drawn through.

Brush the line and `selected()` gives the rows under it.
