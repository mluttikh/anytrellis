# 0019: Sizes for print, and PDF

- Status: **implemented**, 21 November 2026 (design review, Phase 3: print sizing in mm and
  dpi; PDF).
- Changes: `figure.py` (`length`, `UNITS`, `CSS_DPI`, `print_size`, `png_scale`,
  `png_dpi`, `svg_to_pdf`; `svg_to_png` records its dpi), `plot.py` (`_image_svg`,
  `save_svg`, `save_png(dpi=)`, `save_pdf`), `compose.py` (the same for figures),
  `pyproject.toml` (the `pdf` extra); `tests/test_print.py`; `docs/user/how-to/share.md`,
  `install.md`.

## Context

`save_svg` and `save_png` took sizes in CSS pixels and a PNG `scale`. A journal asks for
a figure 180 mm wide at 300 dpi, or a vector PDF (ggsave's `width=, units="mm", dpi=`;
matplotlib's `savefig(dpi=)` and PDF backend). The review asked for `width="180mm"`,
`dpi=300` and PDF.

## Decision

- **A length is CSS pixels or a string with a unit**: `"180mm"`, `"18cm"`, `"7in"`,
  `"500pt"`, `"680px"`. A CSS pixel is 1/96 inch, as in browsers: the plot lays out at
  the length in pixels, so 180 mm is 680 px and 12 px text prints at 9 pt, about what
  journals ask for. Text is not scaled to the size: a poster sets `context="poster"` or
  the theme's `font_size`, as on screen.
- **The SVG says its printed size**: given a length, its `width` and `height` are in that
  unit, its `viewBox` in CSS pixels, so Inkscape, a word processor or LaTeX places it at
  its size. Given pixels, it is as before.
- **A PNG's `dpi`**: pixels per inch, `dpi / 96` per CSS pixel; given with `scale` it is an
  error (one says the other). Every PNG records its dpi (a `pHYs` chunk, `96 * scale`), so
  a document places it at its size: 180 mm at 300 dpi is 2125 px and prints 180 mm wide.
- **PDF through vl-convert-python** (`svg_to_pdf`, the `pdf` extra): a vector PDF of the
  same SVG, its text kept as text (searchable, copyable), its fonts embedded, one page the
  plot's size. It is one wheel with no system libraries on every platform, as resvg-py is
  for PNGs; cairosvg needs Cairo installed, and svglib draws clip paths and text less
  faithfully. vl-convert reads SVG units as points, so the SVG goes in with its width and
  height times 0.75 (a CSS pixel is 0.75 pt) and its viewBox unchanged: the page is the
  plot's size exactly.
- **Figures** (`concat`, 0018) take the same `width`, `dpi` and `save_pdf`.
- The browser's Export menu is unchanged (an image of the plot as on screen, twice its
  size): print sizes are for Python, where a figure for a paper is made.

## Known limits

- vl-convert-python is about 30 MB, for PDFs alone.
- One page per PDF; no multi-page PDF of a paged wrap's pages.
- Fonts are the system's (`system-ui` and its fallbacks, as for PNGs): a PDF made on
  another machine may use another sans-serif.
