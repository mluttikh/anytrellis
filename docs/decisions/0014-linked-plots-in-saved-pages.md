# 0014: Linked plots in a saved page, by keys on each mark

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 4).
- Changes: `linking.py` (`Link.save_html`, `to_html`, `_embed_html`, `saved_links`),
  `plot.py` (`_embed_html(link)`, `_saved_entries`, `page_html`), `js/src/core/savedlink.ts`
  (`readLink`, `chosenKeys`, `linkHighlight`, `LinkGroup`), `standalone.ts` (a link's
  plots grouped and started together), `view.ts` (`ownSelection`);
  `tests/test_saved_links.py`, `js/test/savedlink.mjs`; `docs/user/how-to/link.md`,
  `how-to/share.md`, `explanation/selection.md`.

## Context

`link()` gives plots one selection, but Python relays it: it works out the rows a brush
selects and sends each other plot which of its marks they are. A page from `save_html` has
no Python, so linked plots came apart there, and the documentation's own linking guide
could not show what it describes. Mosaic keeps crossfiltering in a saved page by running
DuckDB in the browser; that is a large dependency for what a link needs.

## Decision

- **Python writes each mark's keys; the page does the rest.** Without `on=`, a key is a
  row's place in its table (tables that are the same object share them); with `on=`, the
  code `link_keys` gives its values, the same across tables. A plain mark carries its row's
  key (a line's piece also its end's); a summary's mark (a histogram's bar, a box) carries
  the keys of every row it stands for.
- **The browser repeats Python's arithmetic.** A selection chooses the keys of its
  selected marks' rows; another plot lights a mark when any of its keys is chosen, and
  fills a histogram's bar to the share of its keys chosen: what `highlight_message` sends.
  `test_saved_links.py` emulates the browser's code on the saved keys and compares with
  what Python's link sends, in memory and from DuckDB.
- **Selections stay shapes of the brush.** The page links whatever selects marks in the
  source plot: a brush, a lasso, clicks, a legend entry. One plot leads: a selection in
  another takes over and the first one's goes, as in a notebook. While a brush moves, the
  others follow once a frame.
- **One page, one call.** `Link.save_html(path, cols=1)` writes every plot of the link, in
  a grid of `cols` columns, with the bundle once; the selection made in Python is saved and
  shown in the others when the page opens. A link's plots start together (not each as it
  nears the screen), so the highlight is there to see.
- **`load="pages"` plots are saved with every row**, as their own `save_html` does
  (decision 0004), so their keys are real rows and `on=` links them as in memory.

## Known limits

- The page holds a key per row per plot (four bytes), and a summary's bars the keys of all
  their rows: a link of plots of millions of rows makes a large page.
- `figure.py` draws one plot at a time; a saved link's images are each plot's own
  `save_svg`, with the highlight Python's link last sent it.
- A plot can be in one link; a page links the plots of one `Link` (several links on one
  page each work on their own).
