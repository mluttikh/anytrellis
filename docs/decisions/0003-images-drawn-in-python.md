# 0003: Images drawn in Python, as the browser draws them

- Status: **implemented**, 7 November 2026 (`save_png`, `save_svg`), and kept in step by
  every change since.
- Changes: `figure.py` (layout, ticks, strips, marks, legend, selection, as SVG),
  `formats.py` (d3-format and time formats), `channels.py` (shape paths, dashes),
  `transforms.py`; `tests/test_figure.py`, `js/test/d3-formats.json` (shared by both
  languages' tests).
- Written after the fact, from the code and the pull requests.

## Context

A figure for a report or a CI job must be made without a browser, and must be the plot the
reader explored, not a look-alike.

## Decision

- **`save_svg` writes the plot as SVG in Python**, mirroring `js/src/core` piece by piece:
  layout, ticks, number and time formats, strips, axes, the Canvas 2D marks, shapes and
  dashes, the legend, the selection, pins, the compared panel's grey marks, direct labels
  and notes. `save_png` converts that SVG with the optional `resvg-py`.
- **It shows the plot as shown**: the zoom the browser last reported (`view` messages), the
  selection, a linked plot's highlight, the opened panel, the page and its order. A plot
  never shown is drawn whole at `DEFAULT_WIDTH`.
- **A change to how the browser draws changes `figure.py` in the same pull request**, and
  the other way round. Python functions name the TypeScript function they mirror
  (`ticks.ts: scaleTicks`), and functions that must agree say "in step with". Number
  formats are tested against the same fixture in both languages.
- **Text is measured with Helvetica's widths**, near the system font the browser uses, so
  labels thin out and fit as they do on screen.
- **The browser's own export** (the Export menu) paints with the plot's code instead
  (0002); both carry the same title and description for screen readers.

## Known limits

- Text widths are estimated, so a label near its limit can thin out differently.
- The browser's SVG export writes haloed text twice (a stroke, then a fill).
