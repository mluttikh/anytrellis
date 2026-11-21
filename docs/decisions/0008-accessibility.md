# 0008: Accessibility: a description from Python, keys for everything, colour not alone

- Status: **partly implemented**, 21 November 2026 (#51 keys between panels, #52 touch, #53
  the description and second encodings).
- Changes: `describe.py`, `plot.py` (`description`, `alt=`, `redundant=`), `theme.py`
  (`redundant`), `channels.py`, `figure.py` and `js/src/core/export.ts` (`<title>`,
  `<desc>`), `js/src/core/view.ts` (`role="figure"`, keys); `docs/user/how-to/
  accessibility.md`.
- Written after the fact, from the code and the design review of November 2026.

## Context

The plot is three canvases: a screen reader finds nothing in them. Its colours may be the
only thing telling series apart. Chartability (Elavsky, Bennett and Moritz, 2022) gives
testable criteria.

## Decision

- **A description made in Python** from what it knows: marks and what they plot, panels,
  colour, shape, dash and size columns, rows, and the axes' ranges. The plot's root is
  `role="figure"` labelled with it; saved SVGs carry it as `<title>`/`<desc>`.
  `alt=` replaces it. With `load="pages"`, rows are counted in the database.
- **A second encoding is one switch away**: `redundant=True` (or `set_theme(redundant=True)`)
  gives a colour column's categories a shape on points and a dash on lines, in one legend.
  It is off by default to keep the default look minimal. A layer's own `shape=`/`dash=`
  wins; a number colour keeps its colormap alone.
- **Keys for everything the mouse does**: Tab reaches the plot, arrows move a ring between
  panels and announce the panel, Enter opens it; the toolbar and legend are buttons with
  names.
- **The default palette is tested for colour-vision deficiency** (0007).

## To do

- Arrows stepping through the marks inside a panel, announcing the tooltip through a live
  region; a table view of the panels and rows (design review, phase 3).
- `prefers-reduced-motion`, `prefers-contrast` and `forced-colors`, once animation lands.
- An audit with Chartability, published in the docs.
