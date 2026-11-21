# 0018: Different plots in one figure

- Status: **implemented**, 21 November 2026 (design review, Phase 3: concatenation).
- Changes: `src/anytrellis/compose.py` (`Concat`, `concat`, `beside`, `under`, `GAP`),
  `plot.py` (`Trellis.__or__`, `__truediv__`), `figure.py` (`figure_svg(ids=)`: ids
  unique among a figure's plots), `__init__.py`; `widget.css` (a narrow header wraps);
  `js/scripts/shots.mjs`, `scripts/docs_gallery.py` (a figure's card);
  `tests/test_compose.py`, `js/test/concat.mjs`; `docs/user/how-to/figures.md`,
  `reference/concat.md`.

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
- **Narrow plots**: a plot's header wraps, the toolbar on a line under the title when the
  title would get less than 8em, and its buttons on two lines when wider than the plot.
  The state chips take only the room left beside the title (`flex-basis: 0`): a chip
  appearing never wraps the header, which would move the plot under a brush being drawn.

## Known limits

- Panels of plots side by side are not aligned to each other (patchwork aligns their
  axes): each plot lays out on its own, so different y-label widths shift their panels.
- No legend collected for the figure; each plot keeps its own.
- No shared scales across plots in a figure; `share_y` works within a plot only.
- In a page, a plot's header height can differ from the image (the toolbar is not drawn
  in images), so rows can differ in height by a toolbar line.
- `Link.save_html(cols=)` stays as it was: `(a | b).save_html()` is the same page of a
  link's plots.
