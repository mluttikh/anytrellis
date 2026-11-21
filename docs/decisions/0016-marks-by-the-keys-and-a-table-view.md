# 0016: The marks by the keys, and the plot as a table

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 6).
- Changes: `js/src/core/stops.ts` (`markStops`, `nextStop`), `view.ts` (`stepMark`, the
  live region `atr-sr`, `toggleTable`, `dataTable`, the keys ← → ↑ ↓ Home End t), `types.ts`
  (`TableView`), `widget.ts`, `standalone.ts`; `plot.py` (`_table_view`, `_all_stats`,
  `stats()` for every plot, `TABLE_ROWS`), `widget.py` (the `table` request);
  `tests/test_table_view.py`, `js/test/keys.mjs`; `docs/user/how-to/accessibility.md`,
  `reference/mouse-and-keys.md`.

## Context

The plot is drawn on canvases. Its description (0008) says what it shows, and the arrow
keys reached panels, but a screen reader could reach no mark and no value. The review asked
for the arrow keys to step through a panel's marks, announcing each one's tooltip, and for
a table view of the panel summaries and, for small data, the rows (Olli's tree, Highcharts'
data table).

## Decision

- **The arrow keys step through marks inside a panel**: the one opened, or a plot's only
  panel, so a grid keeps its arrow keys for moving between panels and Enter goes a level
  down, as a tree would (plot, panel, mark). ← → follow x (a point, a bar's top, a tile's
  centre; a line's, area's or band's every point, its last too), ↑ ↓ go to the nearest mark
  above or below on screen (straight up counting four times aside: at the same x, the other
  series), Home and End to the ends. Grey context and rugs are left out, as hover leaves
  them; so are marks a legend hides.
- **A step is a hover there**: the mark's tooltip and ring are the pointer's, so what a
  screen reader hears is what a sighted reader sees, lines by colour saying every series at
  that x. It is said through a polite live region once the keys rest (250 ms, after
  Python's tooltip columns come), with "k of n"; an end says "The last mark" at once and
  cancels a mark's waiting. A mark off the zoomed view brings x to it, the zoom kept.
- **The table view is Python's**: each panel's statistics (`stats()`, now for every plot:
  the same numbers that sort a paged wrap) and the rows of the first layer, with the
  columns the plot shows (facets, x, y, colour, groups, tooltip), as text, when there are
  `TABLE_ROWS` (500) or fewer. The browser asks for it when it opens (a notebook doesn't
  keep it in the widget's state); a saved page holds it. A plot reading a database lists
  the statistics the database computes, never its rows (0004).
- **Real HTML tables**: a caption, a header row of `th scope="col"`, each panel's name a
  `th scope="row"` and a button that opens it; number columns right-aligned. The dialog
  takes the focus and Esc closes it.

## Known limits

- Within a panel, a mark under another is reached in x order, but the tooltip shows the
  topmost mark there, as hovering does.
- The rows table lists the first layer's data only.
- Python's `figure.py` draws no table: the images are of the plot.
