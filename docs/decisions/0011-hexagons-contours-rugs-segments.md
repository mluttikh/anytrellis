# 0011: Hexagons and contours from binned counts; rugs pinned to the panel's edge

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 1).
- Changes: `stats.py` (`HexGrid`, `HexCells`, `hexbin`, `hexbin_parts`, `Bins2`, `Binned`,
  `contour`, `contour_parts`, `_smoothed`, `_isolines`), `summaries.py` (`_Ask.hexbin`,
  `_Ask.contour`, the `HexCells` test), `layers.py` (`segment_geometry`, `pinned`),
  `query.py` (`panel_extents` of several columns or none), `plot.py` (`segments`,
  `hexbin`, `contour`, `rug`, `_rug`, the pinned axis in the spec, extents and selection),
  `figure.py` (the pinned axis), `js/src/core/scene.ts` (`layerMap`), `view.ts`,
  `selection.ts`, `types.ts` (`pin`); `tests/test_more_marks.py`, the paged tests,
  `js/test/marks.mjs`; `docs/user/how-to/distributions.md`, `more-marks.md`.

## Context

Too many points to read is the common case with a database behind the plot (0004).
Seaborn, ggplot2 and Vega-Lite answer it with hexagonal bins and density contours, and
show a summary's raw values with a rug. A change from one value to another (before and
after, a link) wants a segment per row. Each has to work with `load="pages"`, the same as
in memory, and be drawn by the three renderers and by `figure.py` alike (0002, 0003).

## Decision

- **Hexagons are a summary of counts**, like a histogram: rows go to the nearest centre
  of two offset lattices (as matplotlib's `hexbin`), each hexagon is a row of the summary's
  table (its centre, its count or percent), and its colour is that number on the plot's
  colour scale, with a colour bar. The lattice is the same in every panel. A hexagon is
  as tall as wide on screen for the plot's number `aspect` (else a panel 0.62 as high as
  wide).
- **A hexagon is drawn as two trapezoids** of the band kind, so no renderer needs a new
  shape. They are 2% larger than the cell, so no seam shows between them.
- **A brush selects whole hexagons**: a hexagon's rows are those whose code (the cell
  number of the nearest centre) is the hexagon's, so `selected()` and linked plots ask
  for those codes, in numpy or as a query. The code is computed as a float in queries:
  an engine may evaluate a cast to an integer on rows a filter leaves out.
- **Contours are of binned counts**: the rows are counted on a `gridsize` grid (padded
  20% beyond their range), smoothed with a Gaussian of Scott's bandwidth (times
  `bw_adjust`) from the binned moments, and traced by marching squares (a saddle split by
  the cell's centre value). In a database the counting is one `group_by` of the bin
  indices, so it reads no rows, and what it draws is what memory draws. The levels are
  shared by every panel. The lines stand for no rows: a brush over them selects none.
- **A rug is a plain mark with a pinned axis.** Each row is a tick at its value on one
  axis; on the other, the tick runs from the panel's edge `length` pixels in. The spec
  marks that axis (`pin`), and every place that maps a layer to the screen (the renderers'
  draw, `figure.py`) maps it in pixels from the panel's bottom (or left) edge, so the rug
  stays at the edge, as long, however the panel zooms. The pinned axis is left out of the
  extents, hovering, the compare tooltip and the brush (a brush tests the rug's values
  alone). Without a colour, a rug takes the colour of the layer before it.
- **A rug is not a rule** of the plot's data: a rule's values would be read whole, while
  a plain mark reads only the rows of the page shown (`load="pages"`).
- **A segment is a row's line from (x, y) to (x2, y2)**, drawn as the line kind's
  capsules. An end not given is the start's. A brush selects a segment with either end
  inside it; the extents are of both ends.

## Known limits

- A segments plot's y title names `y`, not `y2`.
- Contours have no fill (bands between the levels).
- Hexagons colour only by their count or percent, not by another column's mean.
