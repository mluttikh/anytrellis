# 0001: Python computes, the browser draws, and bulk data travels as buffers

- Status: **implemented**, 6 November 2026 (0.1), with the window of panels added on 7
  November and the start of a view fixed in #51 (21 November 2026).
- Changes: `plot.py` (`_scene`, `_buffer_ids`, `_send_detail`, `_send_shown`), `codec.py`
  (`Buffers`), `widget.py` (the protocol, in its docstring), `js/src/widget.ts`,
  `js/src/standalone.ts`, `js/src/core/transport.ts` (`BufferStore`), `js/src/core/scene.ts`
  (`bufferIds`).
- Written after the fact, from the code and the pull requests.

## Context

A trellis of a million rows in a hundred panels must zoom at the frame rate, in a notebook
whose kernel may be slow, remote or gone, and must also work as a saved page with no
kernel at all.

## Decision

- **Python does the work that needs the data**: it reads only the columns the layers use,
  assigns rows to panels, computes summaries (bins, boxes, densities, fits), scales,
  domains, colours and the level of detail, and writes a **spec**: small JSON describing
  the plot, whose layers refer to **binary buffers** by content id, dtype and count.
- **The browser does everything that changes while a reader looks**: zoom, pan, brushing,
  hover, the legend, paging, sorting and filtering, all without a round trip. Python is
  asked only for what it alone has: tooltip columns, more detail after a zoom settles, the
  panels of a page further away.
- **Bulk data never goes into a synced trait.** `_spec` and the small state (`open_panel`,
  `compare_panel`, `selection`, `paging`) are traits; buffers go by message. The browser
  asks for the ids it lacks (`need`), and Python answers in chunks (`put`). So a notebook
  does not store the data, and only views that ask receive it.
- **Buffers are content-addressed**: an id is a hash of the bytes, so a buffer sent once is
  never sent again, across spec changes and views.
- **Every buffer a spec names is listed twice**: `bufferIds` in `scene.ts` and
  `_buffer_ids` in `plot.py`. A buffer missing from either still works in tests and saved
  pages, and fails only in a live notebook. A new spec field holding a buffer is added to
  both in the same change, and checked in JupyterLab.
- **`detail` messages replace a spec layer** for the view shown, matched by the id of the
  base layer's coords (`of`), so a detail meant for an earlier spec is recognised and
  dropped.
- **A view that starts asks Python** (`ready`) for the layers it shows differently from the
  starting spec, so state set in Python before the plot was displayed (a page, an opened or
  compared panel) reaches it.
- **`save_html` writes the same spec and buffers** into one page, so it draws as the
  notebook did, without Python. What only Python can give (more detail after a zoom) is
  not there: the page shows the plot at the detail it starts with.
- **Three runtime dependencies**: numpy, anywidget and narwhals (for any table: pandas,
  Polars, PyArrow, DuckDB, Ibis). Anything else is optional (`resvg-py` for PNGs).

## Known limits

- The spec is rebuilt as a whole when the plot changes in Python; only the buffers are
  reused.
- A page from `save_html` holds every panel's data, so a very large plot makes a large
  page.
