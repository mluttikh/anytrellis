# 0013: Lasso and click selection, as shapes of the brush

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 3).
- Changes: `selection.py` (`in_polygon`, `boxes_meet_polygon`, `row_mask(lasso=, at=,
  near=)`, `value_out`), `query.py` (`in_polygon_expr`), `plot.py` (`select(lasso=,
  at=)`, `selection`, `_shapes`, `_lasso_expr`, the paged query), `figure.py` (`select`
  by regions, the lasso's outline), `js/src/core/selection.ts` (`Brush.lasso`, `at`,
  `near`, `inPolygon`, `boxMeetsPolygon`, `simplify`), `view.ts` (the lasso mode, `l`,
  `clickSelect`), `drawing.ts` (`lassos`); `tests/test_lasso.py`, `js/test/lasso.mjs`;
  `docs/user/tutorials/select.md`, `reference/mouse-and-keys.md`.

## Context

A brush is a box, and many groups of marks don't fit in one: a curved band of points, a
cluster beside another. Plotly and Bokeh offer a lasso and a click for these. Each
selection here has to reach Python (`selection`, `selected()`), select the same rows from a
database as in memory (0004), be drawn by `figure.py` as the browser draws it (0003), and
follow `link=` keys as a brush does.

## Decision

- **Both are shapes of the one brush**, not new kinds of selection: a lasso adds its
  corners (`lasso`) and keeps `x` and `y` as their bounding box; marks clicked are points
  (`at`, each `[x, y, panel]`) with `near`, how far from each a mark may be. Everything that
  reads a brush (the legend filter, link keys, a summary's parts, the chip's count, linked
  plots, Python's `selected()`) works with them unchanged. The bounding box still filters
  first, so a lasso's polygon is tested only on the marks in it.
- **A lasso selects as a brush does**: a point inside it by the even-odd rule, a line with
  either end inside, a bar, rect or band piece it overlaps (a corner of either inside the
  other, or an edge of each crossing). A rug is selected by the lasso's extent on its axis.
  The rule is written once per language (`inPolygon`, `in_polygon`, `in_polygon_expr`) with
  the same arithmetic, so a point exactly on an edge falls the same way in each.
- **A lasso has at most 64 corners**: the path drawn is simplified (Ramer-Douglas-Peucker,
  its tolerance raised until it fits). A database tests each corner's edge in the query,
  and the brush goes to Python on every change.
- **In a database, a lasso is a condition of the query**: a sum of the edges a ray crosses,
  odd inside. A category axis takes each category's position (only those in the lasso's
  extent), and two category axes each cell's.
- **A click selects the mark under it**, the one the tooltip would show: a point or a
  line's point there, or a bar, tile or band where it was clicked; `near` is half a pixel
  each way, so the mark and any drawn on it. A click is in its panel only, unlike a brush:
  with `link=`, its key follows into the others. Shift, Cmd or Ctrl add a mark or take one
  away; a click on no mark clears, as before. A rug is never clicked (it is never hovered).
- **Lasso is a fourth drag mode** (`l`), beside pan, box zoom and select. A click selects
  in either select mode, so the brush's mode keeps its clicks.

## Known limits

- A lasso is one polygon: Shift doesn't add a second.
- A point given to `select(at=...)` from Python selects marks within a hundred-thousandth
  of the axis of it, not half a pixel: Python doesn't know the panel's size.
- A click on a category axis's jittered point selects that point in memory, but in a
  database (which has no jitter) every point of its category at that value.
