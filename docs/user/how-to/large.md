# Plot large data

anytrellis draws marks as instances on the GPU, every panel a viewport of one canvas, so
zooming and panning change a few numbers per panel and stay smooth with millions of marks
and hundreds of panels. The data goes to the browser once, as binary arrays.

The plots on this page use fewer rows than you would in a notebook, to keep the page
light: each plot's data is part of the page. The code for the full size is under each one.

## Many points

```python exec="on" source="above" session="large" html="true"
from anytrellis import Trellis
from anytrellis.synthetic import scatter

points = scatter(n=40_000, groups=16)
plot = Trellis(points, wrap="group", cols=4, panel_height=120, title="40,000 points")
plot.points(x="x", y="y", color="cluster", size=1.5, opacity=0.4)
plot
print(plot._embed_html())  # markdown-exec: hide
```

In a notebook, a million points draw as smoothly:

```python
million = scatter(n=1_000_000, groups=16)
Trellis(million, wrap="group", cols=4).points(x="x", y="y", color="cluster", size=1.5, opacity=0.3)
```

Small, partly transparent points (`size=1.5`, `opacity=0.3`) show where points crowd.

## Long series

```python exec="on" source="above" session="large" html="true"
from anytrellis.synthetic import sensors

readings = sensors(stations=8, sensors=2, hours=24 * 60)
plot = Trellis(readings, wrap="station", cols=4, panel_height=100, fit_y=True,
               title="Hourly temperatures, two months")
plot.line(x="time", y="temp", color="sensor", width=0.8, opacity=0.7)
plot
print(plot._embed_html())  # markdown-exec: hide
```

Zoomed out, the daily cycle fills a band; zoom in on a week and the days and the sensors
come apart. `fit_y=True` keeps y fitted to the data in view as you zoom x. A year of 24
stations is about 840,000 line segments:

```python
readings = sensors(stations=24, sensors=4, hours=24 * 365)
```

## Many panels

Up to 100 panels show at once; small ones stay readable with `panel_height=`:

```python exec="on" source="above" session="large" html="true"
week = sensors(stations=60, sensors=1, hours=24 * 7)
plot = Trellis(week, wrap="station", cols=10, panel_height=55, title="60 stations")
plot.line(x="time", y="temp", width=1)
plot
print(plot._embed_html())  # markdown-exec: hide
```

A wrap of more panels shows them a page at a time, which the reader sorts and filters by
each panel's statistics: see [Page through many panels](pages.md).

## Which renderer draws

The plot picks the fastest one the browser has; hover over it, and its bottom-right corner
says which:

| Renderer | Where | Good for |
| --- | --- | --- |
| WebGPU | Recent Chrome, Edge, Safari; Firefox on some systems | millions of marks |
| WebGL2 | Every current browser with a GPU | millions of marks |
| Canvas 2D | Everywhere, also without a GPU (remote desktops, some virtual machines) | thousands of marks; slow for millions |

`Trellis(..., renderer="webgl2")` picks one. [How the plot is drawn](../explanation/drawing.md)
explains the differences.

## What takes time

- **In Python**: reading the columns once, and the summaries (`hist`, `box`, `density`,
  `smooth`) per panel. A plot with only marks is quick at a million rows.
- **Sending**: the columns go to the browser once, as binary arrays.
- **Saving**: a page from `save_html` holds the data, so a million points make a page of
  about 50 MB. Sample before saving a page to share.
