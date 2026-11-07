# anytrellis

[![PyPI](https://img.shields.io/pypi/v/anytrellis)](https://pypi.org/project/anytrellis/)
[![CI](https://github.com/mluttikh/anytrellis/actions/workflows/ci.yml/badge.svg)](https://github.com/mluttikh/anytrellis/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mluttikh.github.io%2Fanytrellis-blue)](https://mluttikh.github.io/anytrellis/)

Trellis, facet and small-multiple plots for Jupyter and marimo notebooks, drawn on the GPU
(WebGPU, WebGL2, or Canvas 2D on machines without a usable GPU).

**Documentation: [mluttikh.github.io/anytrellis](https://mluttikh.github.io/anytrellis/)**:
tutorials, guides, a gallery and the API reference, with live plots.

```bash
pip install anytrellis
pip install "anytrellis[examples]"   # with Polars, for the example notebooks and datasets
pip install "anytrellis[png]"        # with resvg-py, for save_png
```

Status: early development (0.1). One panel per level of the facet columns, every panel
drawn with the same layers (lines, points, bars, areas, rects, text, histograms, box plots,
violins, densities, error bars, reference rules), on shared scales unless told otherwise.
Every panel goes into one canvas, so a grid of hundreds of panels and millions of marks
stays interactive.

```python
from anytrellis import Trellis
from anytrellis.synthetic import sensors

df = sensors()  # a dict of columns; any Polars, pandas or PyArrow table works too
t = Trellis(df, wrap="station")
t.line(x="time", y="temp", color="sensor")
t.rule(y=0)
t  # click it, then scroll to zoom; panels that share a scale zoom together
```

A grid crosses two facet columns, and keeps empty cells so rows and columns stay aligned:

```python
from anytrellis.synthetic import sales

Trellis(sales(), row="store", col="product").bars(x="month", y="units")
```

## Marks

Each mark is a method that adds a layer; layers draw in the order they were added.

| method | draws |
|---|---|
| `line(x, y, color, group, step=None\|"post"\|"pre"\|"mid")` | a line per group (and colour), or steps |
| `points(x, y, color, size)` | a point per row |
| `bars(x, y, color, position="stack"\|"dodge"\|"identity")` | a bar per row, from zero |
| `area(x, y, color, group, position="stack"\|"identity")` | the area under a line, stacked like bars |
| `band(x, ymin, ymax, color, group)` | a band between two lines (a range, an interval) |
| `rect(x, y, color, width=1, height=1)` / `rect(x, y, x2=, y2=)` | a cell per row (a heatmap), or a box between two corners |
| `text(x, y, text, color, size, align, dx, dy)` | a label per row |
| `rule(x=..., y=...)` | reference lines across every panel |
| `hist(x, color, bins=30 \| binwidth=, stat="count"\|"percent"\|"density")` | a histogram per panel, stacked by colour |
| `box(x, y, color, whis=1.5)` | box plots per position (and colour, side by side); sideways when y is the category |
| `violin(x, y, color, scale="area"\|"count"\|"width", inner="quartiles")` | violins per position, placed like boxes |
| `density(x, color, fill=False, bw_adjust=1)` | a kernel density curve per panel and colour |
| `errorbar(x, y, color, extent="ci"\|"se"\|"sd"\|"range")` / `errorbar(x, ymin=, ymax=)` | a mean and its interval per position, or intervals you computed |
| `smooth(x, y, color, method="loess"\|"linear", se=True)` | a fitted line per panel and colour, with a confidence band |

A number column as `color` gets a continuous scale (and a gradient legend); text gets a
palette. On a category axis a rect is one band wide by default. A text label's `dx`/`dy`
are pixels, so labels keep their distance while zooming, and a label that would run past
the panel's edge goes to the other side of its point. `tooltip=[...]` adds columns to
what hovering shows (a box: to its outliers'); every mark but `text` and `rule` can be
selected.

`hist`, `box`, `violin`, `density`, `errorbar` and `smooth` summarise each panel's rows in
Python, and are drawn as bars, boxes, violins, lines, bands and points. A histogram's bins are the same in every panel (round widths
by default), and so are a density's x values, so the panels compare. `stat="percent"`
and `"density"` scale each panel's counts. With `facet="exclude"` a summary covers the
other panels' rows, in grey: each panel against the rest. Hovering a box shows its
quartiles, its count and its whiskers' reach; a smooth line, its confidence interval.
`smooth` fits loess (local lines with tricube weights over a `span` share of the points)
or least squares, and its band is the `level` (95%) interval for the mean. Brushing selects whole bins, boxes and violins, and
`t.selected("hist")` gives the rows they stand for.

## Facets and scales

- `Trellis(df, row=..., col=...)`: a grid; `Trellis(df, wrap=..., cols=4)`: a wrap. Each
  takes one column or several (their combinations are the levels).
- `share_x=` / `share_y=` (or `t.share(x=..., y=...)`): `True` (all panels, the default),
  `"row"`, `"col"` or `False` (each panel its own). Axes are drawn only where a panel's
  scale differs from its neighbour's.
- `x_scale="log"` / `y_scale="log"` (or `t.scale(y="log")`): a log10 scale, with ticks at
  decades (and 2 and 5 between when they fit). Values of 0 or less are left out; marks
  drawn from zero (bars, areas, histograms, densities) don't go on a log y. Summaries are
  computed on the log scale, as in ggplot2: a histogram's bins are equally wide on it.
- `t.order("site", by="median", of="yield")`: panels ordered by a summary of each level.
- `t.order("month", ["Jan", "Feb", ...])`: any category column in the given order: panels,
  bands on an axis and colours. Text is sorted otherwise; a pandas Categorical or a
  Polars Enum keeps its declared order.
- `line(..., group=["station", "sensor"])`: one line per combination of the columns.
- A layer whose data lacks the facet columns is drawn in every panel; `facet="exclude"`
  draws, in each panel, the other panels' data (grey context behind it).

A wrap whose last row is not full shows its legend in the empty cells there when it fits,
and under the plot otherwise (also while one panel is open); `Trellis(..., legend="bottom")`
keeps it under the plot.

## Interaction

Click the plot, then: scroll to zoom x (Shift + scroll: y), drag to pan, `r` to reset.
Zoom and pan apply to every panel that shares the scale. Hovering shows the nearest mark's
values and a crosshair across the panels that share x.

**One axis.** Over an axis, scrolling zooms that axis alone and dragging pans it;
double-clicking it resets it. An axis stands for its whole scale: with `share_y="row"` the
left axis of a row zooms that row.

**Box zoom.** Shift+drag draws a box (or switch plain drag to it: `z`, or the toolbar). The
box follows the drag: mostly sideways zooms x alone, mostly up or down y alone, otherwise
both. While you draw it, the panels it will also zoom show where.

**Fit y.** `y` (or the toolbar) fits every y scale to the data in view, and keeps fitting
it as you zoom or pan x; a shared y fits all its panels together, so they stay comparable.
Zooming y by hand stops it. `Trellis(..., fit_y=True)` starts with it on.

`u` (or Cmd/Ctrl+Z) undoes a zoom, one step at a time.

**Selecting.** `s` (or the toolbar) makes drag a brush, shaped like a zoom box: x, y or
both. It selects the marks it meets, in every panel, and the rest fade: the same range
compared across panels. Drag the brush to move it; a click or Esc clears it.

Click a colour's entry in the legend to select its marks (Shift, Cmd or Ctrl+click adds
or removes more; a click on the only one chosen clears). With a brush too, a mark must
meet both: brush a range, then pick a colour in it. Marks coloured by another column, or by
none, fade.

With `Trellis(..., link="country")` the brush selects in the panel you draw it in, and
then every row sharing its link values, in all panels and layers that have the column:
brush countries in 1955 and follow them through the years. From Python:

```python
t.select(x=(2, 4), y=(60, 80))          # a time axis: dates; a category axis: categories
t.select(x=(0, 3), panel="1955")        # in one panel (with link: then followed)
t.select(color=["Asia", "Africa"])      # the legend's entries: these colours' marks
t.selection                             # {"x": (2, 4), "y": (60, 80), "color": None, "panel": None}
t.selected()                            # the selected rows, as the table you gave
t.select()                              # clear
```

A brush drawn in the browser reaches Python when you let go, so `t.selected()` in the next
cell gives its rows. A point is selected inside the brush, a line or area segment with
either end inside, a bar or rect overlapping it, a box when its body or lines are met;
grey context is never selected.

**Linked plots.** `link(a, b, ...)` gives plots one selection (crossfiltering): brush in
one and the others show the same rows, following the brush as it moves. Points and lines of
those rows stay bright and the rest fade, a histogram's bars fill to the share of their
count that is selected, and a box lights up when any of its rows is. A brush in another plot
of the link replaces the first; a click or Esc in any of them clears it.

```python
from anytrellis import link

scatter = Trellis(cars).points(x="weight", y="mpg")
power = Trellis(cars).hist(x="horsepower")
link(scatter, power)                     # the same table: the same rows
link(by_year, lives, on="country")       # any tables: the rows sharing a country
power.selected()                         # the rows the link's selection picks
```

Without `on=`, the plots must draw the same table (the same object): a filtered copy is
another table, so link it `on=` a key column. Python relays the selection, so the plots are
linked while the kernel runs, not in a page from `save_html`. `unlink()` the returned link
to set them apart.

**One panel at a time.** Double-click a panel (or press Enter over it) to see it alone on
the whole plot; Page Up and Page Down (or ‹ ›) step to the previous and next panel at the
same zoom, and Backspace, Esc, a double-click or *All panels* goes back. The zoom stays
linked: back in the grid, the panels that share its scales show what the opened one
showed. From Python: `t.open("station 3")` (a grid's panel: `t.open("north", "s1")`),
`t.close()`, `t.focused`, and `t.panels()` lists the names.

**Images.** The toolbar's Export button (or `e`) copies the plot as shown, its zoom,
selection and theme, to the clipboard as a PNG (or as an SVG with a PNG beside it, where
the browser allows), downloads it as a PNG (at twice the screen's size) or an SVG, or, in
a notebook, saves either next to the notebook. The toolbar and what the pointer points at
are left out. From Python, without a browser (a script, a CI job), `t.save_png("plot.png")`
and `t.save_svg("plot.svg")` draw the same: the zoom last shown, the selection and an
opened panel (`width=`, `height=`, `theme="dark"`; PNGs need the `png` extra).

**Full screen.** The toolbar's button or `f` shows the plot on the whole screen (`f` or Esc
leaves). Browsers allow it only from a click or a key, so not from Python; where a page
forbids it (some notebook frames, iPhone Safari) the button is not shown.

| key | |
|---|---|
| `f` | full screen, and back |
| `e` | the Export menu: copy or download a PNG or SVG |
| `r`, `0` | reset the zoom |
| `u`, Cmd/Ctrl+Z | undo the last zoom |
| `z` | drag draws a zoom box, and back (Shift+drag: the other) |
| `y` | fit y to the data in view, and stop |
| `s` | drag draws a selection brush, and back |
| Esc | clear the selection (else: back to all panels) |
| click a legend entry | select its colour (Shift+click: add or remove one) |
| Enter | open the panel under the pointer |
| Page Up / Page Down | previous / next panel |
| Backspace | back to all panels |

These keys stay in the plot, so JupyterLab's own shortcuts don't also act on them.

## Sharing

`t.save_html("plot.html")` writes a page with the data inside, which opens without Python.

Licence: MIT.

## Examples

Notebooks in [`examples/jupyter`](https://github.com/mluttikh/anytrellis/tree/main/examples/jupyter)
(JupyterLab, VS Code) and the same in
[`examples/marimo`](https://github.com/mluttikh/anytrellis/tree/main/examples/marimo)
(`marimo edit examples/marimo/01_getting_started.py`):

| notebook | what it shows |
|---|---|
| `01_getting_started` | wrap, grid, free scales, layers and context, `rule`, `order`, `save_html` |
| `02_lattice_and_cleveland` | Cleveland's barley dot plot, Anscombe's quartet, conditioning on two variables, small multiples instead of an animation, following countries with linked brushing |
| `03_ggplot2_style` | `facet_wrap`, `facet_grid`, gghighlight, `scales = "free_y"`, stacked and dodged bars |
| `04_seaborn_style` | `relplot` (scatter and line, `col_wrap`), `FacetGrid` histograms, `catplot(kind="bar")` |
| `05_vega_lite_style` | `row` / `column` / `facet` channels, `resolve_scale`, a trellis of grouped bars |
| `06_large_data` | a million points, a year of hourly readings, a hundred panels |
| `07_linked_plots` | crossfiltering a scatter, histograms and boxes; plots linked by a key column |

Their data comes with the package: `from anytrellis.datasets import load; load("barley")`
(anscombe, barley, cars, gapminder, penguins, seattle_weather; from the UCI Machine
Learning Repository and vega-datasets; their sources and licences are in
[`SOURCES.md`](https://github.com/mluttikh/anytrellis/blob/main/src/anytrellis/datasets/SOURCES.md);
the gapminder data is based on free material from [GAPMINDER.ORG](https://www.gapminder.org/),
CC-BY LICENSE).
The notebooks are written once in `scripts/build_examples.py`, which
writes both sets: run `uv run python scripts/build_examples.py` after changing it.

## Development

```sh
uv sync                                    # builds js/ into src/anytrellis/static
uv run pytest                              # Python: spec, geometry, scales, protocol
cd js && npm test && npm run typecheck     # TypeScript: ticks, layout, picking
npm run build                              # after changing js/src
node test/visual.mjs <dir of save_html pages>      # screenshots per backend
node test/interact.mjs <page.html>                 # hover, linked zoom, pan, reset, dark
node test/zoom.mjs <page.html>                     # one axis, box zoom, fit y, undo
node test/select.mjs <page.html> [dir] [renderer]  # brushing, moving, clearing
node test/legend.mjs <page.html> [dir] [renderer]  # clicking legend entries
node test/export.mjs <page.html> [dir] [renderer]  # the Export menu: PNG, SVG, clipboard
node test/details.mjs <dir of pages> [dir] [renderer] # page styles, a partly selected histogram
node test/notebooks.mjs jupyter|marimo <url> <out> # a live notebook: run it, screenshot plots
node test/linked.mjs <url of 07 in JupyterLab>     # linked plots: brushing across plots
```

Pages force a backend with `?renderer=webgpu|webgl2|canvas2d` in their URL;
`uv run python js/test/pages.py <dir>` writes the pages the browser checks run on.

The documentation is in `docs/user/` (Markdown, built by [Zensical](https://zensical.org)
with the settings in `zensical.toml`); its example plots run when it is built, and are live
in the pages:

```sh
uv run python scripts/build_docs.py            # into site/; warnings fail the build
uv run python scripts/build_docs.py serve      # preview at http://localhost:8000
uv run python scripts/docs_gallery.py          # redraw the gallery's pictures (Chromium)
```

Build the JavaScript bundle first (`cd js && npm run build`). The build also fails on a
page over 3 MB gzipped, and on a public method or parameter that no guide uses.

CI (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request: ruff
and ty, the TypeScript checks, pytest on Python 3.12 to 3.15 (Linux; macOS and Windows on
3.15), the select, legend, zoom and export checks in headless Chromium (WebGL2 and Canvas
2D); it builds the documentation (kept as the run's `github-pages` artifact), and builds
the sdist and wheel, checked by `scripts/check_dist.py` (contents, version, a clean install
that draws a plot).

## Releasing

Releases go to PyPI from GitHub Actions by
[trusted publishing](https://docs.pypi.org/trusted-publishers/): no API token is stored.

Once, before the first release:

1. On [pypi.org](https://pypi.org/manage/account/publishing/), add a pending publisher:
   project `anytrellis`, owner `mluttikh`, repository `anytrellis`, workflow
   `release.yml`, environment `pypi`. For dry runs, do the same on
   [test.pypi.org](https://test.pypi.org/manage/account/publishing/) with environment
   `testpypi`.
2. On GitHub (Settings > Environments), the environments `pypi` and `testpypi`; giving
   `pypi` a required reviewer makes every release wait for an approval.
3. For the documentation: Settings > Pages > Source: *GitHub Actions*; then in Settings >
   Environments > `github-pages`, add the tag rule `v*` to the deployment branches and
   tags, so a release may deploy.

Each release:

1. Set the version in `pyproject.toml`, and in `CHANGELOG.md` move *Unreleased* under a
   heading `## [x.y.z] - date` (and update the links at the bottom).
2. Optionally, a dry run: Actions > Release > Run workflow publishes to TestPyPI
   (`pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ anytrellis`).
3. Commit, tag and push: `git tag vx.y.z && git push origin main vx.y.z`. The release
   workflow runs CI on the tag, checks that the tag matches the version, publishes to PyPI
   makes a GitHub release with the changelog's section and the files, and deploys the
   documentation. To fix a page between releases, run Actions > Docs > Run workflow.
