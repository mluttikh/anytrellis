# 0018: Different plots in one figure

- Status: **implemented**, 21 November 2026 (design review, Phase 3: concatenation);
  amended 26 November 2026: the plots' panels lined up (`align`).
- Changes: `src/anytrellis/compose.py` (`Concat`, `concat`, `beside`, `under`, `GAP`),
  `plot.py` (`Trellis.__or__`, `__truediv__`), `figure.py` (`figure_svg(ids=)`: ids
  unique among a figure's plots), `__init__.py`; `widget.css` (a narrow header wraps);
  `js/scripts/shots.mjs`, `scripts/docs_gallery.py` (a figure's card);
  `tests/test_compose.py`, `js/test/concat.mjs`; `docs/user/how-to/figures.md`,
  `reference/concat.md`.
- Lined up: `compose.py` (`Concat(align=)`, `_cell`, `_aligned`), `figure.py` (`Frame`,
  `panels_box`, `figure_box`, `layout(frame=)`, `figure_svg(frame=)`), `widget.py`
  (`_figure`), `plot.py` (`_embed_html(figure=)`); `js/src/core/align.ts`, `layout.ts`
  (`Frame`, `panelsBox`, `LayoutOptions.frame`), `view.ts` (`lineUp`, `setFigure`),
  `widget.ts`, `standalone.ts` (a figure's plots start together).

## Context

A trellis repeats one plot per group. Readers also want different plots together (a
scatterplot beside a histogram, a summary under a grid of panels), as patchwork, plotnine
and Altair's `|` and `&` give. `link()` already saved linked plots to one page in columns
(`Link.save_html(cols=)`), but there was no figure: nothing to show in a notebook, nor
one image, nor a grid of unlinked plots.

## Decision

- **Operators and a function**: `a | b` is a row, `a / b` a column (patchwork's and
  plotnine's operators; `/` reads as "over"). A plain row or column is added to, so
  `a | b | c` is one row of three; a titled figure, or one with its own widths, is kept
  whole. `concat(*plots, cols=, widths=, title=)` makes any of them and a grid of `cols`
  columns filled row by row. Items may be figures: nested as deep as needed.
- **One layout, three places**: columns as wide as `widths` say, shares of the width
  less `GAP` (24 px, as `Link`'s page) between them; each row as high as its highest
  plot, each plot at its top; a title over the whole, as a plot's title.
  - Jupyter: an ipywidgets `GridBox` of the plots' own widgets (`grid-template-columns`
    of `minmax(0, wfr)`), in a `VBox` under an `HTML` title. ipywidgets comes with
    anywidget: no new dependency.
  - marimo: `mo.hstack` rows (`widths=`, the gap in rem) in a `mo.vstack`; a short last
    row padded.
  - A page: a CSS grid of the plots' embeds. A plot in a link carries its link payload
    (`saved_links`, made once per link), and a figure with linked plots is an
    `anytrellis-link`, so its plots start together.
  - An image: each plot's `figure_svg` at its column's width, as an `<svg x y>` in one
    SVG, its ids prefixed so clip paths and gradients don't collide. Its default width is
    the figure's as last shown (from each plot's reported width), else 400 px a column,
    at least 800.
- **Each plot stays itself**: its own scales, legend, toolbar, zoom, selection and views;
  the figure only places them. Python's `plots` lists them, row by row.
- **Panels lined up** (`align=True`, the default; patchwork's alignment): in a column the
  panels' left and right edges, in a row their tops (the first row of panels, not the
  strips over them: a plot of one panel beside a wrap starts level with the wrap's
  panels), and in a row the plots whose height is free (no `height`, `panel_height` or
  `aspect`, no panel opened) as high as the highest of them, so their x axes line up. A
  plot whose height is set keeps it (its panels a little lower when its top moves down);
  one with a shape keeps it. `align=False` lays each plot out alone, as before.
  - The layout takes a frame (`Frame`: the panels' least left edge and top, and the room
    right of them): the margins grow to it, the y title moving with the panels, and the
    pixels the panels' widths round off go to the first columns so the right edges meet
    to the pixel. Rows and columns elsewhere are unchanged.
  - Each plot is laid out three times, each from the step before alone, so there is
    nothing to go round: as it is (where its panels would be), framed (each column's
    furthest-in edges and each row's lowest top), and stretched (a free plot given the
    height that makes its panels as high as its row's highest free plot's, and once more
    for what rounding lost). Python does it for an image (`Concat._aligned`); in the
    browser each plot is its own view, so they meet in a registry on the page's global
    object, by the figure's id (`align.ts`): a view says where its panels are, and the
    others lay out again when that changes (at most 12 times in a row).
  - Each medium measures its own text: in a page the header with its toolbar, in an
    image the header without it, so the plots line up in each though the page's rows can
    be a toolbar line lower than the image's.
  - A plot's widget is told its place (`_figure`: the figure's id, row and column), a
    saved embed carries it (`figure`). A view lines up only with those beside it on the
    page: in a row those whose cells start at its height, in a column those whose cells
    start as far left and are as wide. A plot shown alone and then in a figure has one
    widget, so both its views are told the place: the one alone is beside nothing and
    stays as it is.
- **Narrow plots**: a plot's header wraps, the toolbar on a line under the title when the
  title would get less than 8em, and its buttons on two lines when wider than the plot.
  The state chips take only the room left beside the title (`flex-basis: 0`): a chip
  appearing never wraps the header, which would move the plot under a brush being drawn.

## Known limits

- A figure inside a figure lines up its own plots, not with the plots around it.
- Full screen and an opened panel leave the figure: the other plots line up without
  that plot until it is back.
- Only the panels' outer edges line up: the panels of two grids with different columns
  don't meet inside them.
- No legend collected for the figure; each plot keeps its own.
- No shared scales across plots in a figure; `share_y` works within a plot only.
- In a page, a plot's header height can differ from the image (the toolbar is not drawn
  in images), so rows can differ in height by a toolbar line.
- `Link.save_html(cols=)` stays as it was: `(a | b).save_html()` is the same page of a
  link's plots.
