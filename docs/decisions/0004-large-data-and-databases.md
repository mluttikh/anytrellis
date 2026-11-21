# 0004: Large data: a database is the main source, and what is sent follows the pixels

- Status: **implemented**, 7 and 8 November 2026 (0.2 and 0.3): level of detail, lazy
  tables, a window of panels, `load="pages"`, summaries and links computed by the database.
- Changes: `data.py` (`Table`), `detail.py`, `query.py`, `summaries.py`, `plot.py`
  (`_rows_of`, `_wanted_of`, `_window`, `_page_summary`), `linking.py`; `tests/test_detail.py`,
  `tests/test_page_*.py`, `js/test/live-*.mjs`.
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
- **Rows find their panel by codes**, not by comparing values, so assigning a million rows
  to a thousand panels stays fast.

## Known limits

- `save_html` reads every row (a saved page has no database to ask).
- A page saved without Python shows the plot at its starting level of detail.
