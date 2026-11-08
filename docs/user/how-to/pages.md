# Page through many panels

A wrap of more than 100 panels shows them a page at a time: 6 columns by 4 rows, with a
bar over them to turn the pages, sort the panels and filter them. The pages share the
plot's scales, so a panel on one page compares with a panel on any other.

```python exec="on" source="above" session="pages" html="true"
from anytrellis import Trellis
from anytrellis.synthetic import sensors

readings = sensors(stations=150, sensors=1, hours=24 * 7)
plot = Trellis(readings, wrap="station", title="150 stations")
plot.line(x="time", y="temp", width=1)
plot
print(plot._embed_html())  # markdown-exec: hide
```

## Turn the pages

Click ‹ and ›, or press ++page-up++ and ++page-down++. Every page is as tall as a full
one, so the plot stays put as you turn them.

Double-click a panel (or press ++enter++ over it) to open it alone. ++page-up++ and
++page-down++ then step through the panels in the order the pages show, sorted and
filtered; going back shows the page with the panel you were on.

## Sort and filter

**Sort** orders the panels by a statistic of each, computed in Python from the values the
plot draws (the first layer's y; a histogram's x):

| Statistic | Of each panel |
| --- | --- |
| `rows` | its number of rows |
| `mean`, `median`, `min`, `max` | its values |
| `sd` | its values' standard deviation |
| `trend` | how far its least-squares line rises (or falls) over the panel's x, in y's units |

Each statistic is named after the column, such as `trend temp`. The arrow next to the menu
switches between ascending and descending. While the panels are sorted, each strip shows
the panel's value at its right end. Panels without a value go last.

**Filter by name** keeps the panels whose name has every word you type: `north 3` keeps
`north 3` and `north 13`. The **filter** button next to it sets a range for any
statistic, a low end, a high end or both, and counts the filters set. The bar says how many
panels are kept, out of how many.

## Your own statistics

Anything you can compute per panel can sort and filter it: give a table with the facet
column(s) and one row per panel to `panel_stats()`. Number columns get ranges; other
columns get a text filter (keep the panels whose value has the text you type).

```python exec="on" source="above" session="pages" html="true"
import polars as pl

frame = pl.DataFrame(readings)
info = frame.group_by("station").agg(
    pl.col("temp").quantile(0.9).alias("p90 temp"),
    (pl.col("temp").max() - pl.col("temp").min()).alias("range temp"),
)
plot.panel_stats(info).sort_panels("range temp", descending=True)
plot
print(plot._embed_html())  # markdown-exec: hide
```

A column with the name of a statistic the plot computes (`rows`, say) replaces it.

## From Python

The page, the sort and the filters can be set from Python, and they follow the browser's:

```python
plot.sort_panels("trend temp", descending=True)   # None: as given
plot.filter_panels("north", **{"mean temp": (10, None)})
plot.filter_panels()                               # all again
plot.show_page(2)                                  # from 1
plot.shown_panels()   # the names on the page shown
plot.page, plot.pages # the page shown, and how many there are
plot.stats()          # {"panel": [...], "rows": [...], "mean temp": [...], ...}
plot.paging           # the page, sort and filters, as the browser shows them
```

A statistic's name with a space goes in a dict, as above; one without can be a keyword:
`filter_panels(rows=(100, None))`.

`save_png` and `save_svg` draw the page shown, sorted and filtered as it is, and a page
from `save_html` opens on it.

## Only the pages near you are sent

In a notebook, the browser gets the data of the page shown and of the pages either side of
it, not of every panel: a thousand panels of a week's readings start with about 2 MB
instead of 46 MB. The next or previous page draws at once, and Python then sends the pages
around it. A page further away (a jump, a sort, a filter) says *Loading the panels…* until
its data comes, a moment later. Opening a panel of another page brings its data too.

A page from `save_html` (or `to_html`) has no Python to ask, so it holds every panel's
data: all its pages turn, sort and filter as in the notebook.

Two things count only the panels whose data the browser has: `fit_y=True` with a shared
y fits the panels sent, and the count of selected marks in the corner is of the marks
sent. `selected()` in Python uses every row.

## The page's size

`cols=` sets the columns and `rows=` the rows of a page. `rows=` also pages a wrap of fewer
panels, for the sort and filters. `rows="all"` never pages.

```python
Trellis(readings, wrap="station", cols=8, rows=3)   # 24 a page
Trellis(readings, wrap="station", rows="all")       # every panel at once
```

A grid (`row=`, `col=`) shows all its cells; page it by a column (below). To order a
wrap's panels for good, rather than in the browser, use `order()`:
`plot.order("station", by="max", of="temp", descending=True)`.

## A page per level of a column

`page=` makes each level of a column a page of its own: a region's stations, a site's grid
of sensors by metric. The bar names the page shown and lists the others to pick from.

```python exec="on" source="above" session="pages" html="true"
regions = Trellis(sensors(stations=40, sensors=1, hours=48), wrap="station", page="region",
                  title="Stations by region")
regions.line(x="time", y="temp", width=1)
regions
print(regions._embed_html())  # markdown-exec: hide
```

- **A wrap** shows a level's panels, as many rows as its largest level needs. With `rows=`,
  a level of more panels goes on several pages ("north (2 of 3)"). Sorting and filtering
  order each level's panels; a level with none left has no page.
- **A grid** (`row=`, `col=`) shows each level's every cell, in the same place on every
  page, so turning the pages compares them cell by cell. Its pages aren't sorted or
  filtered.
- **The scales** are shared by every page, unless `share_x="page"` or `share_y="page"`
  gives each page its own.
- **The levels** are in the column's order; `order("region", ...)` orders them, by name or
  by a summary.

```python
Trellis(df, row="sensor", col="metric", page="site", share_y="page")
plot.show_page("north")       # a level's first page
plot.page_names               # ["coast", "north", "south"]
```

With `load="pages"` (a table in a database), turning to a level reads that level's rows.
