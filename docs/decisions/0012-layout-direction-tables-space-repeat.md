# 0012: Layout: fill direction, layout tables, panels sized by range, repeated columns

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 2).
- Changes: `facets.py` (`DIRECTIONS`, `direction_of`, `wrap_shape`, `place`,
  `layout_places`, `Grid.direction`, `Grid.placed`, `build_grid(direction=, places=)`),
  `data.py` (`repeated`, `MEASURE`, `VALUE`), `plot.py` (`direction=`, `layout=`,
  `space=`, `repeat=`, the `direction` and `space` properties, the settings, `code()`,
  `_pages`, `_level_pages`, `_space_spec`), `figure.py` (`place` on a paged wrap, the
  columns' widths and rows' heights, `_span`, `_shares`), `js/src/core/layout.ts`
  (`place`, the same widths and heights), `types.ts` (`GridSpec.dir`,
  `TrellisSpec.space`); `tests/test_layout.py`, `js/test/layout.mjs`;
  `docs/user/how-to/layout.md`.

## Context

A wrap filled row by row from the top left fits most plots, but not all: neighbouring
levels read better one under another, lattice starts at the bottom left, a right-to-left
language starts at the right, and some panels have a shape of their own (a map, a plate's
wells). Free scales let each panel show its own range, but squeeze a panel of three
categories into the width of one of eight. Measurements kept side by side in columns are
read best stacked on one time axis. ggplot2 (`dir=`, `space=`), geofacet (`grid=`) and
Vega-Lite (`repeat`) answer these; each answer here has to work with a database behind
the plot (0004) and be laid out the same by the browser and by `figure.py` (0003).

## Decision

- **A direction is two letters**, the side a run starts from and the side the next run
  goes to (`"lt"`, rows from the left, top first; `"tl"`, columns from the top, left
  first), with `"h"` and `"v"` for the common two. One function, `place(k, rows, cols,
  dir)`, puts the k-th panel in its cell; Python, `layout.ts` and `figure.py` each have
  it and use it for a wrap and for each page of a paged wrap. Filled by columns, a wrap
  keeps its `cols=` and has as few rows as hold every panel.
- **A layout table places a wrap's panels by their levels**, named as the panels name
  them (a number level as its label), at rows and columns counted from 1, as geofacet's
  grids are. The grid is as large as the table's places; the cells without a panel are
  empty, and their neighbours draw the axes, as a grid's empty cells do. A table may hold
  places the data has no panel for; a panel without a place is an error, not a panel put
  somewhere. The table places every panel, so it doesn't go with `cols=`, `direction=`
  or a paged wrap's `rows=`; with `page=`, it is a grid's page, every cell in its place.
- **Space shares the panels' width by their x ranges** (their height by their y ranges):
  a column is as wide as the widest range of its panels, its share of the width that
  range over all of them; a band axis's range is its levels from the first to the last a
  panel has. The panel size computed as before is the mean, so the plot's width and
  height, and an `aspect`, keep their meaning. Since the ranges are the panels' own,
  `space=` needs scales free along those lines (`share_x="col"` or `False` for x), and in
  a wrap one row (or column) of panels, whose columns (rows) each hold one panel. The
  settings panel offers only the shares that go with it. Category labels are laid flat,
  wrapped or angled by one band's width, the same in every panel.
- **Repeat melts the data**, a row per row and column, into `measure` (the rows' facet,
  in the order the columns were given) and `value` (the layers' `y`), with narwhals'
  `unpivot`, so a database's melt is part of its query and `load="pages"` reads a page's
  rows. Each row has its own y scale by default, its strip names the column by its label,
  and the y title is left to the strips. `selected()` returns the melted rows. The
  description counts the data's rows, not the melted ones.

## Known limits

- The browser measures text and `figure.py` estimates it, so the gutters beside a strip or
  an axis's labels can differ by a few pixels; the panels' order, rows and sizes are the
  same (`layout.mjs` checks them).
- A layout table places a wrap's panels, not a grid's.
- Repeating columns as columns of panels (Vega-Lite's `repeat: {column: ...}`), or both
  ways, is not offered: `col=` with a melted table does it by hand.
