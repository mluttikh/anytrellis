# Use a log scale

`y_scale="log"` (or `x_scale="log"`) draws a base-10 log scale, with ticks at the decades,
and at 2 and 5 between them when they fit. On it, equal distances are equal ratios: a
doubling looks the same for a thousand people and for a billion.

```python exec="on" source="above" session="log" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

gapminder = load("gapminder")
plot = Trellis(gapminder, wrap="region", cols=3, panel_height=130, y_scale="log",
               title="Population (log scale)")
plot.line(x="year", y="pop", group="country", width=1, tooltip=["country"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

Set it later with `scale()`: `plot.scale(y="log")`, and back with `plot.scale(y="linear")`.

## What a log scale leaves out

- **Values of 0 or less** have no place on a log scale: they are left out.
- **Marks drawn from zero** (bars, areas, histograms and densities) don't go on a log y;
  the plot raises an error that says so. Points, lines, bands, rects, text, box plots and
  smooth lines do.

## Summaries on a log scale

A summary is computed on the scale it is drawn on, as in ggplot2: on a log x, a
histogram's bins are equally wide on the log scale, a density is estimated there, and a
smooth line is fitted there.

```python exec="on" source="above" session="log" html="true"
plot = Trellis(gapminder, wrap="year", cols=4, panel_height=110, x_scale="log")
plot.hist(x="pop", bins=20)
plot
print(plot._embed_html())  # markdown-exec: hide
```
