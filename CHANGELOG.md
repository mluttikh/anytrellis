# Changelog

All notable changes to anytrellis. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) (before 1.0, minor versions may change the API).

## [Unreleased]

### Added

- `Trellis(aspect="bank")`: the panels' shape that shows the median slope of the lines'
  segments at 45 degrees, each measured in its own panel's ranges (Cleveland's banking):
  the `smooth()` fits' (a trend, not the noise around it), or without them the `line()`
  layers'. Between 0.02 and 5 times as
  high as wide; with `load="pages"`, kept from the panels read first.

### Fixed

- Lines, areas and bands drawn in other panels than their own (a margin's, or with
  `facet="all"` or `"exclude"`) no longer join the rows of several panels into one line
  zigzagging between them: each panel's rows stay a line of their own.

### Added

- `horizon(x, y, bands=3, origin=0, step=None)`: a horizon chart in each panel. A series'
  distance from `origin` is cut into bands of one height, laid over each other and darker
  the farther, blues above the origin and reds below it, so a series shows its highs and
  lows in a panel 24 px high. Every panel shares the band height (by default a round
  number reaching the farthest value of any panel); the legend names each band's range,
  and clicking it selects the times a series reaches it. Works with `load="pages"`;
  margins are left empty.

### Added

- `Trellis(margins=)`: a grid's "(all)" panels, as ggplot2's `facet_grid(margins = TRUE)`.
  `True` adds an (all) row under the rows (each panel the rows of its column) and an (all)
  column right of the columns (each panel the rows of its row), with a corner of every
  row; `"row"` or `"col"` adds one. Every layer draws them, summaries computed from their
  rows; a row selected in a margin is selected once. With `empty="blank"` and `page=`;
  not with `load="pages"` or a wrap.

### Added

- `share_x="sliced"` / `share_y="sliced"` (also in `share()`): each panel its own range,
  about its own data, every one as wide as the widest, so a change of 5 looks the same size
  in every panel (lattice's `relation="sliced"`). Zooming one panel zooms all to its width,
  each about its own centre; panning moves one; fitting y keeps them as wide. Bars keep
  their base at 0. With `load="pages"`, the widths come from every panel's range in the
  database. Not on an axis of categories.

## [0.5.0] - 2026-11-09

### Added

- `Trellis.as_category("column")`: a number column read as categories. Its distinct values
  are the levels, in order (`-10, -2, 3`), labelled as numbers (`4`, not `4.0`), rows
  without one last as `(missing)`: a colour per value from the palette with a legend, a
  band per value on an axis, a series per value with `group=`, and `order()` with numbers.
  With `load="pages"`, the database finds the values and selects by them.

### Fixed

- Panel backgrounds, gridlines, strips and axes no longer vanish when the window is
  resized. A resized plot is drawn again at once instead of a frame later, and a plot
  whose height brings a page scrollbar at one width and not 17 px narrower (Windows) no
  longer flips between the two widths every frame, blank each time: it keeps the narrower.

## [0.4.0] - 2026-11-08

### Added

- `Trellis(strips=)`: `"nested"` (the default) or `"joined"`. With several facet columns,
  nested strips give each column a strip, the first outermost, spanning the panels next
  to each other that share its level (as ggh4x's in R): stacked on top of a grid's columns
  and a wrap's panels, side by side on the right of a grid's rows. Saved images draw them
  too.
- `Trellis(empty="blank")`: a grid's cells without data are left out, and the other
  panels keep their rows and columns, with axes drawn into the blank cells beside them.
  The default, `"draw"`, keeps the empty panels. With `page=`, a cell is left out when
  it has no data on any page, so every page has the same cells.
- `Trellis(strip_label=)`: a column whose value names each panel (one value per panel),
  in a strip of the panel's own, in a grid too, in place of the row, column and nested
  strips. A panel without a value is named by its levels; panel names in `panels()` and
  `open()` stay the levels. With `load="pages"`, the database gives the labels with the
  panels.

### Changed

- A plot faceted by several columns (`wrap=["a", "b"]`, `col=[...]`, `row=[...]`) now
  shows nested strips, not one strip per panel naming the levels together (`"a · b"`);
  `strips="joined"` shows those. Panel names in `panels()` and `open()` are unchanged. See
  [Upgrading](https://mluttikh.github.io/anytrellis/reference/upgrading.html).

### Fixed

- A panel's last x label no longer runs into the y labels or the strip of the panel below
  and right of it, when both draw into the empty cell between them ("10" over "4").

## [0.3.0] - 2026-11-08

### Added

- `Trellis(page=)`: a page per level of a column (or columns). A grid (`row=`, `col=`)
  shows each level's every cell, in the same place on every page; a wrap shows the level's
  panels, sorted and filtered within it, on several pages with `rows=` when there are more
  than fit. The pager names the page shown and lists the levels to pick from;
  `show_page("north")` and `page_names` do the same from Python. `share_x="page"` and
  `share_y="page"` give each page its own scale. With `load="pages"`, a level's rows are
  read as its page is turned to.
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
  are drawn in 1.0 s from 480,000 rows read (3.9 s reading all of them); a page turned
  reads only the page that came near and makes only its panels' lines and points, keeping
  the others', in 0.2 s. `selected()` is a query of the selected
  rows; a saved page reads every row of the lines, points and text.
- Summaries with `load="pages"`: `hist`, `box`, `violin`, `density`, `smooth` and
  `errorbar` of the plot's data are computed by the database, every panel's at once, and
  no row is read: bin counts, quartiles and whiskers, means and spreads, sums of squares,
  and values in fine bins for densities, violins and loess fits (drawn from the bins, to
  within about 0.03%). The axes are every panel's from the start, and pages turn without
  asking again. A brush over a summary selects the rows it stands for, as a query. Ten
  million rows in 1,000 panels: a histogram in 0.8 s (3.2 s reading every row), a loess
  fit in 3.6 s (22 s).
- Linking with `load="pages"`: `link=` selects the rows sharing the brushed rows' keys in
  every panel, as a query. `anytrellis.link(..., on=)` links a plot reading pages to any
  other: its selection is read as the keys chosen, and a selection elsewhere lights up the
  rows of the pages read and fills its summaries to the share of the keys chosen, which
  the database counts in a query per summary (0.2 s for 4,000 of 5,000 keys over ten
  million rows). A link of a plot reading pages needs `on=`.
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

- A lazy table (a Polars `LazyFrame`, a DuckDB relation, an Ibis table) is read when the
  plot is first drawn, with only the columns it uses, not collected whole when the plot
  is made. A panel of more than 20,000 points of a line or 100,000 points shows them at
  the level of detail its pixels need (see Added); zoom in for more. No code changes. See
  [Upgrading](https://mluttikh.github.io/anytrellis/reference/upgrading.html).
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

[Unreleased]: https://github.com/mluttikh/anytrellis/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/mluttikh/anytrellis/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/mluttikh/anytrellis/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mluttikh/anytrellis/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mluttikh/anytrellis/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mluttikh/anytrellis/releases/tag/v0.1.0
