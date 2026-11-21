# 0010: A settings panel whose changes are Python's, and the plot's code from its calls

- Status: **implemented**, 21 November 2026 (design review, item 1).
- Changes: `code.py` (`recorded`, `recorded_init`, `literal`, `source_name`), `plot.py`
  (the properties `cols`, `aspect`, `share_x`, `share_y`, `x_scale`, `y_scale`, `color`,
  `title`, `subtitle`, `caption`, `height`, `panel_height`;
  `code`, `_settings`, `_apply_settings`), `widget.py` (the `settings` message, `_code`),
  `js/src/core/view.ts` (the panel), `js/src/standalone.ts`; `tests/test_settings.py`,
  `js/test/settings.mjs`; `docs/user/how-to/settings.md`.

## Context

A notebook user explores by editing a cell and running it again. hvPlot's Explorer,
marimo's chart builder and PyGWalker show that a panel in the plot makes that loop quick,
and that the result has to come back as code. 0006 asks that every control have the same
name in Python.

## Decision

- **A panel, not a builder.** It changes the layout (columns, panel shape), the scales
  (sharing; linear, log, sqrt, symlog), the colour column and the panels' order. Adding
  marks or changing the data stays in code. It is closed by default, behind a toolbar
  button and `,`; `controls=False` removes it.
- **Python decides what the panel offers and applies it.** The spec carries the panel's
  sections (`settings`): each setting's name, label, value and choices, made from what the
  plot has (a wrap's columns, a grid's row and column sharing, scales only for numbers,
  colour columns with at most 30 categories, or numbers). The browser draws them and sends
  a change as one `settings` message. Python applies it through the property or method of
  the same name and sends the new spec. The browser holds no rules of its own.
- **What the plot had stays a choice.** A value of the plot's own that a menu doesn't
  offer (`aspect=0.8`, `share_y="row"` on a wrap, a colour column of many categories, an
  order of given levels or descending) is listed under its name while it is the plot's,
  and kept in the list after another is chosen, so going back is one choice: an order is
  kept whole (its levels, summary, column and direction) and restored as it was.
- **All or none.** A change the plot can't draw (bars on a log axis) is undone in Python,
  and the browser shows the reason.
- **Names are Python's**: `t.cols`, `t.aspect`, `t.share_x`, `t.share_y`, `t.x_scale`,
  `t.y_scale` and `t.color` read back what the panel shows, take the constructor's values,
  and redraw a shown plot when set. The order is `order(column, by=, of=)`. The plot's
  other settable values (`t.title`, `t.subtitle`, `t.caption`, `t.height`,
  `t.panel_height`) are properties that redraw too: an attribute set without a redraw would
  leave the plot, the panel and `code()` disagreeing.
- **Every control does what it says.** A height given (`panel_height=`, `height=`) sets
  the panels' height over a shape, so the panel shows it as the shape (*200 px high*), and
  choosing a shape lets the height go; the height stays a choice, to go back to. In
  Python alike: of `aspect` and a height, the one
  set last decides.
- **`code()` writes the calls that made the plot**, recorded as they were made (the
  constructor's arguments that differ from its defaults, then each method), with what was
  changed since written in from the plot's state:
  - the settings (as constructor arguments; `share()` and `scale()` calls folded in);
  - a layer's colour;
  - `as_category` and `order`;
  - the page bar's sort, filters and pins;
  - the compared panel.

  The page shown, the opened panel and the selection are views of the plot, not part of
  it, and are left out. A table is written as the name the notebook gives it, else `data`.
  Run, the code makes the same spec, as the tests check.
- **"Copy as Python" copies in the click**: the widget keeps `code()` current in a synced
  trait (`_code`), because a clipboard write must happen during the click, not after a
  round trip. A saved page carries the code it was saved with, and its panel offers that
  copy only.

## Known limits

- A plot changed by assigning to its state directly (not through a method or property) is
  not in `code()`.
- `pairs()` is written as its one call, and has no settings panel.
- Layers with their own data are written with their tables' notebook names; a table not
  bound to a name in the notebook is written as `data`.
