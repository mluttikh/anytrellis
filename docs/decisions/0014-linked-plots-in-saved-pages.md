# 0014: Linked plots in a saved page, by keys on each mark

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 4); amended 27
  November 2026: `load="pages"` plots saved a chunk of panels at a time.
- Changes: `linking.py` (`Link.save_html`, `to_html`, `_embed_html`, `saved_links`),
  `plot.py` (`_embed_html(link)`, `_saved_entries`, `page_html`), `js/src/core/savedlink.ts`
  (`readLink`, `chosenKeys`, `linkHighlight`, `LinkGroup`), `standalone.ts` (a link's
  plots grouped and started together), `view.ts` (`ownSelection`);
  `tests/test_saved_links.py`, `js/test/savedlink.mjs`; `docs/user/how-to/link.md`,
  `how-to/share.md`, `explanation/selection.md`.
- A chunk at a time: `plot.py` (`Saved`, `_saved_entries(on)`, `_saved_members`,
  `_chunked_scene` keeps its entries in `_full_entries`, `_alone` keeps `_reads_on`; the
  every-row copy `_every_row` removed), `summaries.py` (`saved_members`, `_hits` out of
  `_counted`), `linking.py` (`saved_links` from `_saved_entries`).

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
- **The keys are those of the marks the page draws** (`Trellis._saved_entries`: each
  spec layer's user layer, part, geometry, the table its rows are of, and a summary's
  members), so a page's marks and its keys can't part: the same entries build both.
- **`load="pages"` plots are saved a chunk of panels at a time**, as a plot's own
  `save_html` is (decision 0004), never every row at once. Each chunk's reading has the
  link's `on` columns (`_alone` keeps them as `_reads_on`, `_page_names` reads them), and
  the chunks' entries, joined, are the ones the page draws (`_full_entries`): a plain
  mark's key is its row's `on` values. A summary from the database has no rows in Python:
  the database groups the rows by what its marks test (panel, colour, labels, values), by
  their value in the range each covers (a histogram's bin; else the value) and by `on`
  (`summaries.saved_members`), and each group finds its mark as `linked_counts`' do
  (`_hits`). A histogram's bar has each key as often as its rows, so it fills to the share
  of its rows chosen as in memory; other summaries' marks have each key once (they light
  up or not). A backend that can't run the query leaves that layer unlinked, with a
  warning. `on=` is required for `load="pages"` plots, so keys never need row positions.

## Known limits

- The page holds a key per row per plot (four bytes), and a summary's bars the keys of all
  their rows: a link of plots of millions of rows makes a large page.
- A database summary's keys come in one query a layer, not a chunk at a time: a group per
  mark and key (a histogram's), or per value and key (a box's, a curve's: the value finds
  its mark), so a summary of many distinct values reads as many narrow groups, the link's
  columns and a count each.
- `figure.py` draws one plot at a time; a saved link's images are each plot's own
  `save_svg`, with the highlight Python's link last sent it.
- A plot can be in one link; a page links the plots of one `Link` (several links on one
  page each work on their own).
