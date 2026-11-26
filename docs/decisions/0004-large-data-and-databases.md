# 0004: Large data: a database is the main source, and what is sent follows the pixels

- Status: **implemented**, 7 and 8 November 2026 (0.2 and 0.3): level of detail, lazy
  tables, a window of panels, `load="pages"`, summaries and links computed by the database.
  26 November 2026 (0.9): a saved page read a few panels at a time.
- Changes: `data.py` (`Table`), `detail.py`, `query.py`, `summaries.py`, `plot.py`
  (`_rows_of`, `_wanted_of`, `_window`, `_page_summary`, `_chunked_scene`), `linking.py`;
  `tests/test_detail.py`, `tests/test_page_*.py`, `js/test/live-*.mjs`.
- Written after the fact, from the code and the pull requests.

## Context

The main use is plots of a DuckDB database: thousands of panels, hundreds of millions of
rows. Reading every row into Python, or sending every row to the browser, does not work
there.

## Decision

- **Any table through narwhals**: pandas, Polars (eager or lazy), PyArrow, a DuckDB relation,
  an Ibis table. A lazy table is read when the plot is first drawn, **once, with only the
  columns the plot uses**. A column needed later reads them again, from the same rows.
- **`load="pages"` reads a page at a time.** Python reads the rows of the panels around the
  page shown (that page, the pages either side, the opened panel, the pinned panels and the
  compared one) and asks the database for the rest: each panel's x and y range, the
  levels of category columns, the panels' statistics, and summaries (`hist`, `box`,
  `bars(stat=)`, linked counts) as grouped queries. A summary the backend can't compute is
  computed from rows instead, never refused. Rows are counted in the database, never read
  for that.
- **Every feature works with `load="pages"`**, or says clearly that it doesn't. A new feature
  gets a test with a DuckDB relation and `load="pages"`.
- **Paging is configurable**: `rows=`, `cols=` and `page=` set what a page holds, and the
  window sent around it is the page shown and its neighbours.
- **What is sent grows with the pixels, not the rows** (`detail.py`). A panel's line with
  more than `THIN` (20,000) points is thinned by M4 to the columns of its width; a panel of
  more than `DENSE` (100,000) points is drawn as cells, coloured by their points. When a
  zoom settles, the browser reports what it shows and Python sends those panels in more
  detail, replacing what was drawn.
- **A saved page reads a few panels at a time.** `save_html` of a paged `load="pages"`
  plot builds its layers a chunk of panels at a time (`CHUNK_ROWS`, about two million rows;
  at most `CHUNK_PANELS` panels, whose keys are in the query), as a page turn builds them,
  and keeps of each chunk what its layers send and the rows that refers to. The chunks'
  layers are joined into one, the dense points' cells shaded by the densest cell of them
  all: the page is the one reading every row at once makes, and Python holds a chunk's
  rows, not the table's. A plot that doesn't page has read every row already: its scene is
  the saved page's.
- **Rows find their panel by codes**, not by comparing values, so assigning a million rows
  to a thousand panels stays fast.

## Known limits

- A saved page holds every panel at the detail the plot starts with, so its size grows
  with the panels (258 MB for 1000 panels of 100,000 points), and Python holds about its
  size several times over while writing it.
- `Link.save_html` of `load="pages"` plots reads every row at once (decision 0014).
- A page saved without Python shows the plot at its starting level of detail.
