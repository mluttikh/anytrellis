# Plot large data

anytrellis draws marks as instances on the GPU, every panel a viewport of one canvas, so
zooming and panning change a few numbers per panel and stay smooth with millions of marks
and hundreds of panels. The data goes to the browser once, as binary arrays, and no more
of it than the pixels show: a long line goes thinned, and dense points as cells (see
[Level of detail](#level-of-detail)).

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

Small, partly transparent points (`size=1.5`, `opacity=0.4`) show where points crowd.

A panel of more than 100,000 points is drawn as cells instead, each in the colours of its
points (mixed in proportion) and more opaque the more it holds. A million points, a
quarter in each panel, make a page of half a megabyte:

```python exec="on" source="above" session="large" html="true"
million = scatter(n=1_000_000, groups=4)
plot = Trellis(million, wrap="group", cols=2, panel_height=180, title="A million points")
plot.points(x="x", y="y", color="cluster", size=1.5)
plot
print(plot._embed_html())  # markdown-exec: hide
```

Hover over a cell for its points, of each colour. In a notebook, zoom in and the cells get
finer, then turn back into points once a panel shows at most 100,000 of them.

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
stations is about 840,000 points:

```python
readings = sensors(stations=24, sensors=4, hours=24 * 365)
```

A series of millions of points (a sensor read every second) goes thinned, and in detail
where you zoom in: see the next section.

## Level of detail

What the browser gets grows with the pixels it shows, not with the rows:

- **Long lines.** In a panel of more than 20,000 points, each series keeps, in each of
  2,000 columns across the panel, its first, last, lowest and highest point (the M4
  method). The thinned line covers the same pixels as all of its points, peaks and dips
  included, at a fraction of the size: four million points send about 30,000 segments.
- **Dense points.** A panel of more than 100,000 points is drawn as cells of about 3
  pixels (for the plot 800 pixels wide), over the panel's scales, so the cells of panels
  sharing a scale line up.
- **Zoomed in.** In a notebook, the plot tells Python what it shows, and Python sends the
  panels shown in more detail: a line at two columns a pixel over the range in view (and
  some either side, for panning), cells of about 3 pixels, or the points themselves.
  Zoomed out again, the plot goes back to how it started.

The detail is only in what is drawn. `select()`, `selected()` and a linked plot's
selection use every row, and a brush over cells selects the rows under it. `save_png` and
`save_svg` draw the detail last shown. A page from `save_html` has no Python to ask, so it
shows the plot as it starts, at any zoom.

Points on a category axis are never drawn as cells.

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
  `smooth`) per panel. A plot with only marks takes about half a second a million rows.
- **Sending**: the marks go to the browser once, as binary arrays, at the level of detail
  shown: a megabyte or two for millions of rows, and more as you zoom in.
- **Saving**: a page from `save_html` holds the marks as the plot starts. A long line or
  dense points stay small; marks below the thresholds (bars, areas, a million points
  spread over many panels) are all in the page, about 40 bytes each.
