# Changelog

All notable changes to anytrellis. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) (before 1.0, minor versions may change the API).

## [Unreleased]

### Added

- `pairs()`: a scatterplot matrix of a table's number columns, x by column and y by row,
  each variable's scale shared along its column and its row. The diagonal shows each
  variable alone (a density curve per colour, or a stacked histogram) over its own range.
  Brushing a panel lights up its rows in every panel; `selected()` gives them as rows of
  the table, and hovering a point shows its row. `corner=True` keeps each pair once.
- `Trellis(aspect=)`: each panel's height as a multiple of its width (`1`: square).
- Lazy tables and databases: a Polars `LazyFrame`, a DuckDB relation or an Ibis table (on
  any database Ibis queries) is read in one query, with only the columns the plot uses,
  when the plot is first drawn. The database computes the panels' summaries: the pages'
  statistics (rows, mean, median, min, max, sd) and `order()`'s summaries; the trend comes
  from the rows without sorting them. Ten million rows in 1,000 panels build in 3.3 s
  rather than 5.3 s from Ibis on DuckDB (3.2 s rather than 6.6 s from a `LazyFrame`).
- `Trellis(load="pages")`: a paged wrap of a lazy table (DuckDB, Ibis, a `LazyFrame`) reads
  only the rows of the panels of the page shown and the pages either side of it, and the
  next ones as the pages turn. The panels, their statistics (with the trend), each panel's
  range of x and y, the category levels and the colour ranges come from the database, so
  every page looks as with every row read. Ten million rows in 1,000 panels from DuckDB
  are drawn in 1.0 s from 480,000 rows read (3.9 s reading all of them); a page turns in
  0.3 s. Lines, points and text; `selected()` is a query of the selected rows; a saved
  page reads every row. Not with `link`.
- Paged wraps send only the panels near the page shown: in a notebook, the browser gets
  the data of the page shown and the pages either side of it, and more as the pages turn,
  are sorted or filtered, or a panel of another page opens; a page further away says it
  is loading until its data comes. A thousand panels of a week's readings start with
  2.2 MB instead of 46 MB. A page from `save_html` or `to_html` still holds every panel.

- Level of detail: what goes to the browser grows with the pixels shown, not the rows. A
  panel of more than 20,000 points of a line sends each series thinned (M4: per column,
  its first, last, lowest and highest point), and a panel of more than 100,000 points is
  drawn as cells, each in its points' colours mixed in proportion and more opaque the more
  it holds; hovering one tells its points, of each colour. Zoomed in, in a notebook, Python
  sends the panels shown in more detail: a line at two columns a pixel, finer cells, or
  the points again. Four million points send about 1 MB instead of 128 MB, and their
  `save_html` page shrinks from 171 MB to 1.4 MB. Selections still use every row;
  `save_png` and `save_svg` draw the detail shown; a saved page shows the plot as it
  starts.

### Changed

- Faster selections over linked rows (`link=`): number and category link columns are
  keyed from their values and codes, not their text; and dense points' cells are counted
  and grouped without sorting their points.
- Faster plots of many rows in panels: rows find their panel by their column's codes, not
  their text, and numbers as panels are labelled once per value, not once per row. Four
  million rows of a line in four panels build in 1.2 s instead of 2.2 s (by a column of
  numbers: 1 s instead of 4.2 s), and in 1,000 panels ordered by a median, with statistics
  to sort pages by, in 3.5 s instead of 93 s.
- Text columns are encoded by PyArrow when it is installed, not labelled row by row in
  Python: ten million rows of text facets read in 0.15 s instead of 4 s. A Polars
  `DataFrame` of ten million rows in 1,000 panels builds in 4.2 s instead of 6.1 s.
- Rects edge to edge (heatmap tiles, cells) show no seams between them in Canvas 2D, the
  browser's image export, `save_png` and `save_svg`: their edges fall on whole pixels.

## [0.2.0] - 2026-11-07

### Added

- Export images of a plot (toolbar button, or `e`): copy a PNG, or an SVG with a PNG beside
  it, to the clipboard; download a PNG (twice the screen's size) or an SVG; or, in a
  notebook, save either next to the notebook without overwriting. The image is the plot as
  shown (zoom, selection, opened panel, theme), without the toolbar. It works in pages
  saved with `save_html` too.
- `Trellis.save_png` and `Trellis.save_svg`: the same image drawn in Python, without a
  browser (scripts, reports, CI): the zoom last shown in the notebook, the selection, a
  linked plot's highlight and an opened panel, in the light or dark theme, at any size.
  PNGs need the new `png` extra (`pip install "anytrellis[png]"`, with resvg-py).
- Pages of panels: a wrap of more than 100 panels shows them a page at a time (6 by 4;
  `Trellis(rows=, cols=)` sets the page, `rows="all"` turns paging off), with a bar to turn
  the pages (also Page Up and Page Down), sort the panels by a statistic of each and filter
  them by name and by statistics' ranges. The statistics are computed in Python: rows, and
  the mean, median, min, max, sd and trend of the values drawn, plus any columns given with
  `panel_stats()`. From Python: `sort_panels()`, `filter_panels()`, `show_page()`,
  `shown_panels()`, `stats()`, `page`, `pages` and `paging`. An opened panel steps through
  the panels as sorted and filtered; images and saved pages show the page shown.
- `violin()`: each group's values as a violin (a kernel density mirrored around its
  position), with its median and quartiles, or its values as points (`inner=`). Scaled to
  the same area, by count or to the same width (`scale=`); side by side with a colour,
  sideways when y is the category. Brushing selects whole violins.
- `errorbar()`: each group's mean with its confidence interval (`extent="ci"`, at
  `level=`), standard error, standard deviation or range, with caps and a point at the
  mean; or intervals you computed, from `ymin=`/`ymax=` (or `xmin=`/`xmax=`, sideways).
- `line(step=...)`: step lines, `"post"`, `"pre"` or `"mid"`. Hovering a step shows the
  row it starts from.
- Documentation at [mluttikh.github.io/anytrellis](https://mluttikh.github.io/anytrellis/):
  tutorials, how-to guides, a gallery, the API reference and explanations, with live plots.

### Changed

- A wrap of more than 100 panels now shows them a page at a time (it drew them all, small);
  `Trellis(..., rows="all")` draws them all as before. See
  [Upgrading](https://mluttikh.github.io/anytrellis/reference/upgrading.html).
- A page of many plots (`standalone.js`) starts each plot as it scrolls near, so a long
  page stays within the browser's limit of GPU contexts.

### Fixed

- Tooltips on documentation sites (Material, Zensical) are as compact as in a notebook:
  the site's table styles no longer reach them, nor its letter spacing the plot.
- A linked plot's highlight of part of a histogram's bars draws the faded bars whole, with
  the selected share solid from their base (the faded part was missing).
- x labels of neighbouring panels no longer run together at their edges ("AprMar"): a
  label that would reach the next panel's first is left out.
- Box plots failed in WebAssembly (marimo's in-browser notebooks, Pyodide), where indices
  are 32-bit.
- A plot now redraws when the page switches between light and dark by
  `data-md-color-scheme` (Material and Zensical sites).

## [0.1.0] - 2026-11-07

The first release.

### Added

- `Trellis`: one panel per level of the facet columns: a wrap (`wrap=`, `cols=`) or a
  grid (`row=`, `col=`) that keeps empty cells, with shared, per-row, per-column or free
  scales (`share_x=`, `share_y=`), linear or log (`x_scale=`, `y_scale=`).
- Marks: `line`, `points`, `bars` (stacked or dodged), `area`, `band`, `rect`, `text`,
  `rule`, and summaries computed per panel in Python: `hist`, `box`, `density` and `smooth`
  (loess or linear, with a confidence band).
- Data from Polars, pandas, PyArrow or DuckDB (through narwhals), or a dict of arrays;
  numbers, times and categories, with category colours and legends.
- Drawing with WebGPU, WebGL2 or Canvas 2D, whichever the browser has; the data goes to the
  browser once, as binary buffers, so millions of marks stay interactive.
- Zooming and panning (scroll, drag, one axis, box zoom), panels that share a scale
  zooming together, `fit_y` to fit y to the data in view, undo and reset; one panel at a
  time (`open`, `close`) and full screen.
- Selecting: a brush (`s`) in every panel or, with `link=`, in one panel and followed by
  key; `select()`, `selection` and `selected()` from Python. Clicking legend entries
  selects their colours.
- Linked plots: `link(a, b, ..., on=)` shares one selection between plots, histograms
  filling to their selected share (crossfiltering).
- Tooltips with Python's values; `save_html` writes a page that opens without Python.
- Works in JupyterLab and marimo, and other anywidget hosts (Jupyter Notebook, VS Code).
- `anytrellis.datasets.load`: six small example datasets, with their sources and licences
  in `datasets/SOURCES.md`; example notebooks for Jupyter and marimo.

[Unreleased]: https://github.com/mluttikh/anytrellis/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mluttikh/anytrellis/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mluttikh/anytrellis/releases/tag/v0.1.0
