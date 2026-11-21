# Draw areas, bands, rects, segments and text

## Areas

`area()` fills under a line, down to zero. With a category `color=`, areas stack, so the
top edge is the total; `position="fill"` stacks them as shares of the total at each x (up
to 100%), and `position="identity"` overlaps them instead:

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

## Segments

`segments()` draws a line from (x, y) to (x2, y2) for each row: a change, a link, a move.
Give `x2=`, `y2=` or both; the one not given stays as it was, so `y2=` alone draws a
vertical line.

```python exec="on" source="above" session="more" html="true"
change = gapminder.filter(pl.col("year").is_in([1955, 2005])).pivot(
    on="year", index=["country", "region"], values=["fertility", "life_expect"])
plot = Trellis(change, wrap="region", cols=3, panel_height=170,
               title="From 1955 to 2005", x_title="Children per woman",
               y_title="Life expectancy")
plot.segments(x="fertility_1955", y="life_expect_1955", x2="fertility_2005",
              y2="life_expect_2005", tooltip=["country"])
plot.points(x="fertility_2005", y="life_expect_2005", size=4)
plot
print(plot._embed_html())  # markdown-exec: hide
```

`width=`, `color=` and `opacity=` work as for `line()`. A brush selects the segments with
an end inside it.

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

With many labels, `repel=True` keeps them apart: each takes the first spot around its
point (right, left, above, below, the corners, then farther out with a line back) where
it covers no other label nor a point. A label with no room is left out, until zooming in
makes room; the table's first rows are placed first, so sort it by importance.

```python exec="on" source="above" session="more" html="true"
y2005 = gapminder.filter(pl.col("year") == 2005)
plot = Trellis(y2005, wrap="region", cols=3, panel_height=170)
plot.points(x="fertility", y="life_expect")
plot.text(x="fertility", y="life_expect", text="country", repel=True, size=10)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Notes

`annotate()` writes a note at a data position, in one panel (`panel=` its name), several
or every one. `dx=` and `dy=` move the text from the position, with a line back to it;
with `x=` alone the note sits at the panel's top, with `y=` alone at its left:

```python exec="on" source="above" session="more" html="true"
weather = load("seattle_weather")
plot = Trellis(weather, wrap="weather", cols=3, panel_height=140)
plot.line(x="date", y="temp_max", width=0.8)
plot.annotate("Heat wave", x="2015-06-27", y=33, panel="sun", dx=-30, dy=18)
plot.rule(x="2014-01-01").annotate("A new sensor", x="2014-01-01", dx=4)
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

A target, a mean or a limit that differs from panel to panel comes from a table: give it
as the rule's data and name its column. Each row's line goes in the panel of its facet
columns' values; a table without them puts its lines in every panel:

```python exec="on" source="above" session="more" html="true"
barley = load("barley")
targets = barley.group_by("site").agg(target=pl.col("yield").mean())
plot = Trellis(barley, wrap="site", cols=3, panel_height=170)
plot.points(x="yield", y="variety", color="year")
plot.rule(targets, x="target", dash=(4, 3))
plot
print(plot._embed_html())  # markdown-exec: hide
```

Rules are not selected, and neither are text labels.
