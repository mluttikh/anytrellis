# 0007: A minimal look by default, set as a theme of named settings

- Status: **implemented**, 17 November 2026 (0.6: minimal, framed, classic) and 20 November
  2026 (#44: text size and contexts).
- Changes: `theme.py` (`Theme`, `PRESETS`, `set_theme`), `styling.py` (palettes, colormaps),
  `js/src/core/look.ts`, `figure.py`; `docs/user/reference/theme.md`.
- Written after the fact, from the code and the pull requests.

## Decision

- **Minimal by default**: nothing behind the data but a faint grid, strips as titles at the
  left, the y title level over the plot ("↑ temp"), no fill or frame. Before, 72 grey
  rectangles sat on a 6 by 4 page before any data, and the y title and row labels were
  turned on their side.
- **The old look is kept** as `theme="classic"`, and `"framed"` (after Observable Plot)
  separates panels with a thin frame.
- **A theme is named settings** (`Theme(base, panel_fill, frame, grid, ...)`): a preset with
  any of them changed, per plot (`theme=`) or per session (`set_theme`). The browser and
  the images drawn in Python read the same settings.
- **One size control**: `context=` ("paper", "notebook", "talk", "poster") scales text,
  line widths and point sizes together; `font_size="auto"` steps with the panels' width.
- **Colour**: Petroff's colour-vision-tested ten colours by default (minimal),
  observable10 (framed), tab10 (classic). A dict palette keeps categories their colours
  across plots. Number colours use perceptual colormaps.
- **The look follows the host's light or dark theme**, in notebooks, VS Code and docs
  sites.

## Known limits

- The theme is read when the plot is made: `set_theme` changes the plots made after it.
