# 0006: Every control stays out of sight until asked for, and has the same name in Python

- Status: **partly implemented**, 17 to 21 November 2026 (#42, #46, #47, #50, #51, #52). The
  settings panel and `t.code()` are to do.
- Changes: `js/src/core/view.ts` (toolbar, chips, help, panel buttons, keys, touch),
  `widget.py` (the synced state), `plot.py` (the methods); `docs/user/reference/
  mouse-and-keys.md` lists every control.
- Written after the fact, from the code and the design review of November 2026.

## Context

The plot should stay minimal, with nothing in front of the data, while more and more can be
changed in it. A change made by hand in the plot should not be lost when the notebook runs
again.

## Decision

- **Controls appear when they are needed**: the toolbar on hover or focus, a panel's
  buttons when the pointer is on it (off with `panel_buttons=False`), chips for state that
  is not the default (a selection, a filter, pins, a comparison) with a button to undo it,
  and the `?` overlay for the rest.
- **Every control has the same name in Python**, and state set on either side reaches the
  other: `open`/`focused`, `compare`/`compared`, `pin`/`pinned`, `select`/`selection`,
  `show_page`, `sort_panels`, `filter_panels`, `legend`, `limits`. A new control lands with
  its method, its synced state and its documentation in the same change.
- **Everything the mouse does, the keys do**, and touch does too (pinch, two fingers, a long
  press), with one finger left to scroll the page.
- **The plot says what state it is in**: drag mode, fitted y, selections and filters show
  as chips; notices use `role="status"`.
- **The docs build fails** on a public method or parameter that no guide uses or the cheat
  sheet lacks.

## To do

- A settings panel for the look and layout, and `t.code()`, which writes the Python of what
  was changed by hand (design review, item 1).
- Setting the zoom from Python (it is reported to Python for images, and `limits()` sets
  where it starts).
