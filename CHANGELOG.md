# Changelog

All notable changes to anytrellis. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) (before 1.0, minor versions may change the API).

## [Unreleased]

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

[Unreleased]: https://github.com/mluttikh/anytrellis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mluttikh/anytrellis/releases/tag/v0.1.0
