# Draw areas, bands, rects and text

## Areas

`area()` fills under a line, down to zero. With a category `color=`, areas stack, so the
top edge is the total; `position="identity"` overlaps them instead:

```python exec="on" source="above" session="more" html="true"
import polars as pl

from anytrellis import Trellis
from anytrellis.datasets import load

gapminder = load("gapminder")
by_region = gapminder.group_by("region", "year").agg(pl.col("pop").sum())
plot = Trellis(by_region, panel_height=240, title="Population by region")
plot.area(x="year", y="pop", color="region", tooltip=["region"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

A plot without a facet column is one panel: a trellis of one.

## Bands

`band()` fills between two columns: a range, an interval, an envelope.

```python exec="on" source="above" session="more" html="true"
weather = load("seattle_weather").with_columns(year=pl.col("date").dt.year())
plot = Trellis(weather, wrap="year", cols=2, share_x=False, panel_height=130,
               title="Seattle: each day's low to high", y_title="°C")
plot.band(x="date", ymin="temp_min", ymax="temp_max", color="#d62728", opacity=0.35)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Rects and heatmaps

`rect()` draws a tile per row, centred on x and y and one step of the data wide and high.
With a number `color=`, that is a heatmap:

```python exec="on" source="above" session="more" html="true"
daily = weather.with_columns(month=pl.col("date").dt.month(), day=pl.col("date").dt.day())
plot = Trellis(daily, wrap="year", cols=2, panel_height=130, title="Seattle: daily high (°C)")
plot.rect(x="day", y="month", color="temp_max", tooltip=["date"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

`width=` and `height=` shrink the tiles (as a share of the step). With `x2=` and `y2=`, a
rect goes from (x, y) to (x2, y2) instead: periods, ranges, regions.

## Text

`text()` writes a column's values at (x, y). `dx=` and `dy=` move the labels by pixels, so
they keep their distance from their points while you zoom; a label that would run past
the panel's edge moves to the other side of its point.

```python exec="on" source="above" session="more" html="true"
eight = gapminder.filter(
    pl.col("year").is_in([1955, 2005])
    & pl.col("country").is_in(["China", "India", "Japan", "Netherlands", "Brazil",
                               "Nigeria", "United States", "Egypt"])
)
plot = (
    Trellis(eight, wrap="year", panel_height=220, title="Eight countries, 1955 and 2005")
    .points(x="fertility", y="life_expect", color="region", size=7)
    .text(x="fertility", y="life_expect", text="country", align="left", dx=6)
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Reference lines

`rule(x=...)` draws vertical lines and `rule(y=...)` horizontal ones, at a value or a list
of values, across every panel:

```python
plot.rule(y=70, color="#888888", dash=(4, 3))
plot.rule(x=[1960, 1980, 2000])
```

Rules are not selected, and neither are text labels.
