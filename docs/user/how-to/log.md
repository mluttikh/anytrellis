# Use a log, sqrt or symlog scale, or reverse one

`x_scale=` and `y_scale=` (or `scale()` later) choose how an axis spaces its values:

| Scale | Equal distances are | For | Values |
|---|---|---|---|
| `"linear"` | equal differences | most things (the default) | any |
| `"log"` | equal ratios | growth, sizes over many orders of magnitude | above 0 |
| `"sqrt"` | equal differences of square roots | counts and sizes, keeping 0 at the bottom | 0 and above |
| `"symlog"` | equal ratios away from 0, differences near it | changes either side of 0 | any |

Add `"reverse"` to run an axis from high to low: `y_scale="reverse"`, or with a scale,
`y_scale=("log", "reverse")`.

## A log scale

`y_scale="log"` draws a base-10 log scale, with ticks at the decades, and at 2 and 5
between them when they fit. On it, equal distances are equal ratios: a doubling looks the
same for a thousand people and for a billion.

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

### What a log scale leaves out

- **Values of 0 or less** have no place on a log scale: they are left out.
- **Marks drawn from zero** (bars, areas, histograms and densities) don't go on a log y;
  the plot raises an error that says so. Points, lines, bands, rects, text, box plots and
  smooth lines do. A sqrt or symlog y takes them all.

## A square-root scale

A sqrt scale spreads out the small values less than a log scale does, and keeps 0: the
big countries no longer flatten the rest, and bars, areas and histograms still start at
the bottom. Values below 0 are left out.

```python exec="on" source="above" session="log" html="true"
plot = Trellis(gapminder, wrap="region", cols=3, panel_height=130, y_scale="sqrt",
               title="Population (square-root scale)")
plot.line(x="year", y="pop", group="country", width=1, tooltip=["country"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

Stacked bars and areas are stacked first, then drawn on the scale: the top of a stack is
at its total, and each part's height is what it adds to the total there.

## A symlog scale

A symmetric log scale is a log scale on both sides of 0, with a linear piece between: it
is `sign(v) · log10(1 + |v|)`. Use it for changes, profits and losses, anything that runs
over orders of magnitude in both directions.

```python exec="on" source="above" session="log" html="true"
import polars as pl

change = gapminder.sort("country", "year").with_columns(
    change=pl.col("pop").diff().over("country")
)
plot = Trellis(change, wrap="region", cols=3, panel_height=130, y_scale="symlog",
               title="Population change over five years (symlog scale)")
plot.line(x="year", y="change", group="country", width=1, tooltip=["country"])
plot.rule(y=0)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## A reversed axis

`"reverse"` runs an axis from high to low: x from right to left, y from top to bottom.
Ranks read best that way, first at the top:

```python exec="on" source="above" session="log" html="true"
countries = ["Japan", "Chile", "Brazil", "India", "Kenya", "Iceland", "Turkey"]
ranked = gapminder.with_columns(
    rank=pl.col("life_expect").rank(descending=True).over("year")
).filter(pl.col("country").is_in(countries))
plot = Trellis(ranked, y_scale="reverse", title="Life expectancy rank, of 63 countries")
plot.line(x="year", y="rank", color="country").points(x="year", y="rank", color="country")
plot
print(plot._embed_html())  # markdown-exec: hide
```

Zooming, panning, brushing and saving images all follow the reversed direction; limits,
rules and selections stay in the data's values: `plot.limits(y=(1, 20))` is the top 20.

## Summaries on a transformed scale

A summary is computed on the scale it is drawn on, as in ggplot2: on a log (sqrt, symlog)
x, a histogram's bins are equally wide on that scale, a density is estimated there, and a
smooth line is fitted there. On a sqrt or symlog y, a histogram counts first and then
draws its counts on the scale.

```python exec="on" source="above" session="log" html="true"
plot = Trellis(gapminder, wrap="year", cols=4, panel_height=110, x_scale="log")
plot.hist(x="pop", bins=20)
plot
print(plot._embed_html())  # markdown-exec: hide
```

With `load="pages"` the database computes the same summaries on the same scales.
