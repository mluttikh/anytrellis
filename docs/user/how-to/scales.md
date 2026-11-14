# Share or free the scales

Panels share both scales by default: the same value is at the same place in every panel,
so you compare them at a glance, and zooming one zooms all. Free a scale when the panels'
values differ so much that a shared scale flattens some of them.

| `share_x=` / `share_y=` | Each scale is shared by |
| --- | --- |
| `True` (default) | all panels |
| `"row"` | the panels of a row (a grid, or a wrap's row) |
| `"col"` | the panels of a column |
| `False` | nothing: each panel has its own |
| `"sliced"` | nothing, but every panel's range is as wide as the widest |

Set them when you make the plot, or later with `share()`:

```python
Trellis(df, wrap="station", share_y=False)
Trellis(df, row="origin", col="cylinders").share(x="col")
```

## Free y, shared x

The common case: series of very different sizes over the same time. Each panel draws its
own y axis, so the values stay readable:

```python exec="on" source="above" session="scales" html="true"
import polars as pl

from anytrellis import Trellis
from anytrellis.datasets import load

gapminder = load("gapminder")
regions = (
    gapminder.group_by("region", "year").agg(pl.col("pop").sum())
)
plot = Trellis(regions, wrap="region", cols=3, panel_height=120, share_y=False,
               title="Population by region")
plot.line(x="year", y="pop")
plot
print(plot._embed_html())  # markdown-exec: hide
```

x is still shared: zoom in on x in one panel and all of them follow.

## The same width in every panel: sliced scales

Free scales stretch each panel's data over the whole panel, so a small change looks as
big as a large one. `share_y="sliced"` gives each panel its own range, about its own data,
but makes every range as wide as the widest: a change of 10 years is as tall in every panel,
whatever its level. This is lattice's `relation="sliced"`.

```python exec="on" source="above" session="scales" html="true"
life = gapminder.group_by("region", "year").agg(pl.col("life_expect").median())
plot = Trellis(life, wrap="region", cols=3, panel_height=120, share_y="sliced",
               title="Median life expectancy by region")
plot.line(x="year", y="life_expect")
plot
print(plot._embed_html())  # markdown-exec: hide
```

Europe's rise is half as tall as South Asia's, as it is in years. Zooming y in one panel
zooms every panel to the same width, each about its own centre; panning moves one panel
alone. Bars keep their base at 0 and grow upwards. An axis of categories has no width to
share, so it can't be sliced.

## A scale per row or per column of a grid

In a grid, `share_x="col"` gives each column its own x, and the rows still compare:

```python exec="on" source="above" session="scales" html="true"
cars = load("cars").filter(pl.col("cylinders").is_in([4, 6, 8]))
plot = (
    Trellis(cars, row="origin", col="cylinders", panel_height=110)
    .share(x="col")
    .points(x="horsepower", y="mpg", size=4, tooltip=["name"])
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Where axes are drawn

A panel draws an axis only where its scale differs from its neighbour's: with shared
scales, only the outer panels have axes; with free ones, every panel does. Zooming over an
axis zooms that axis alone, and with it every panel that shares it.

## Zoom stays linked

Panels that share a scale zoom and pan together, whatever you share. Fit y to the data in
view with **y** (or `Trellis(..., fit_y=True)`): a shared y fits all its panels together,
so they stay comparable.

## Shared, free, or log?

When the panels' values differ by orders of magnitude, a [log scale](log.md) is often
better than free scales: the panels stay comparable, and each one's change still shows.
[How scales are shared](../explanation/scales.md) explains the trade-off.
