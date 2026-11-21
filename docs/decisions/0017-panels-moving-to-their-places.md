# 0017: Panels moving to their places

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 1).
- Changes: `js/src/core/motion.ts` (`motionFrom`, `tween`, `placeBy`, `ease`,
  `reducedMotion`, `MOTION_MS`), `view.ts` (`motion`, `moveNext`: set by `setPaging` and
  `setFocus`, started in `relayout`, drawn in `draw`); `js/test/motion.mjs`, vitest;
  `docs/user/how-to/pages.md`, `reference/mouse-and-keys.md`, `how-to/accessibility.md`.

## Context

A sort, a filter or a panel opened put every panel in a new place at once: a reader
watching one panel lost it. Heer and Robertson (2007) found animated transitions improve
object tracking over a hard cut, with simple staging preferred. The review asked for each
panel to slide to its new place in about 250 ms when sorted or filtered, an opened panel to
grow from where it was, and none of it when the browser asks for reduced motion.

## Decision

- **Only the panels' places move.** Each frame draws the plot as it always does, with each
  panel's rect between where it was and where it goes (`tween`); its marks, gridlines, axes
  and tick labels are drawn in that rect, so they move and scale with it. A strip or axis
  past an edge of the panel keeps its size and its gap to that edge, and stretches along it
  (`placeBy`). A grid's row and column strips belong to no one panel: they show at the end.
- **What moves**: the panels shown before and after; a panel new to the plot grows from 60%
  of its size about its middle. Panels that leave are gone at once. With no panel in both
  (a page of all-new panels, Page Down between opened panels) or none moved, it is a cut.
- **When**: a change of the paged wrap's state (sort, filter, page, pins: `setPaging`) or of
  the opened panel (`setFocus`), from Python or the reader. A resize, a zoom or a new spec
  from Python never animates.
- **250 ms, slow at both ends** (cubic). Keys and the pointer work meanwhile; hit testing
  uses the rects drawn. A step among the marks (0016) puts the panels in place at once. What is shown is reported to Python (`view`) once the panels stop.
- **Reduced motion**: `prefers-reduced-motion: reduce` turns it off; the browser's setting,
  not the plot's, so it holds in every notebook and page.
- `figure.py` draws images, which have nothing to animate (0003 unchanged).

## Known limits

- Moving panels are drawn over the still ones without a background: for a quarter second,
  a panel's lines cross another's.
- No staging (first the leaving panels, then the moves): one step, as the review's 250 ms
  asks.
- There is no option to turn it off for one plot; the system's reduced motion does it for
  all.
