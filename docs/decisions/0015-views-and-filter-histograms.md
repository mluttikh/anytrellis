# 0015: Views of a paged plot, and its filters as histograms

- Status: **implemented**, 21 November 2026 (design review, Phase 3 item 5).
- Changes: `plot.py` (`save_view`, `show_view`, `drop_view`, `views`, `VIEW_KEYS`,
  `code()`, the saved page's `views` and `zoom`), `widget.py` (`views`, the `zoom`
  message), `js/src/core/pager.ts` (the Views menu, `histogram`), `view.ts` (`showView`,
  `setViews`, `setZoom`, `viewShown`), `types.ts` (`SavedView`, `Zoom`), `widget.ts`,
  `standalone.ts` (`#view=`); `tests/test_views.py`, `js/test/views.mjs`;
  `docs/user/how-to/pages.md`.

## Context

Trelliscope's two ideas for many panels were missing: filters shown as histograms you
brush, and named views that restore a sort, filter and layout. A paged plot's state was
already the paging (page, sort, filters, pins) plus the opened and compared panels and the
zoom; nothing kept it under a name, and the filters were typed ranges with no picture of
where the panels lie.

## Decision

- **A view is the plot's state, flat**: the paging's keys, `open`, `compare` and `zoom`
  (each scale group's range in the spec's units; None: as the plot starts). It is plain
  JSON, the same in Python (`views`), the widget (`views`, synced both ways) and a saved
  page, so `code()` writes each as `save_view(name, {...})` with what differs from the
  start.
- **`save_view(name)` keeps what is shown now**; `save_view(name, view)` keeps one given.
  `show_view` sets the paging, panels and zoom: the zoom reaches the images (`_view`, so
  `save_png` draws it, 0003) and the browser (a `zoom` message, sent again when a view
  starts until the browser reports one), and a saved page opens on it.
- **The Views menu lives in the page bar**, beside the filters it restores: the views to
  show and delete, and a name to keep the one shown. The bar names the view the plot shows
  (its state, page aside, equal to the view's, the zoom to six digits), so a reader sees
  when they've left it.
- **A link names a view**: `#view=<name>` on a saved page shows it on each plot that has
  it, at once and when the link changes. Views kept in a saved page last until it closes:
  the page has nowhere to write them that its other readers would see.
- **A number statistic's filter is a histogram to brush**: twenty bins over its range, every
  panel's in grey and those the other filters keep on top, its own range a band. A drag sets
  the range (rounded to a hundredth of the range's decade; past an end: open there), a
  click clears it, and the number boxes stay for exact values and the keyboard. Showing
  the other filters' panels makes the histograms crossfilter each other, as Trelliscope's
  do. They are drawn from the statistics in the spec, so a plot reading a database
  (`load="pages"`) gets them as well (0004).

## Known limits

- The Views menu shows on a paged plot only; another plot's views are shown from Python or
  by a `#view=` link.
- A view's zoom is in the plot's scale groups: changing `share_x` or the data moves what it
  shows.
- A text statistic keeps its typed filter: no histogram.
