# 0005: Pages of panels, sorted and filtered the same way in both languages

- Status: **implemented**, 7 November 2026 (0.2), with `page=` on 8 November and pins and
  the compared panel in #51 (21 November 2026).
- Changes: `pages.py` (`Paging`, `order`, `page_list`, `pins_of`, `page_labels`),
  `js/src/core/pages.ts` (`panelOrder`, `pageList`, `pinsOf`, `pageLabels`),
  `js/src/core/pager.ts`; `tests/test_pages.py`, `tests/test_page_column.py`,
  `tests/test_pins_compare.py`,
  `js/test/pages.test.ts`, `js/test/paging.mjs`, `js/test/panels.mjs`.
- Written after the fact, from the code and the pull requests.

## Decision

- **A wrap of many panels is shown a page at a time** (`rows=`, `cols=`), or a page per level
  of a column (`page=`). The reader sorts and filters panels by statistics of each panel
  (Tukey's cognostics, as Trelliscope uses them): rows, mean, median, extremes, spread,
  trend, and any given with `panel_stats`.
- **The browser sorts, filters and pages without Python.** Python computes the same order,
  for `shown_panels()`, the images drawn in Python and the panels it sends (0004). The two
  implementations, `pages.py` and `pages.ts`, change together, and each says it is in step
  with the other.
- **The paging state is one synced value** (`paging`: page, sort, descending, name filter,
  ranges, pinned names), set from either side: `show_page`, `sort_panels`, `filter_panels`,
  `pin`, or the page bar.
- **Pinned panels lead every page**, whatever the sort and filters, keeping at least one
  place for the others. A grid's pages keep every cell in place, so they don't pin.
- **The compared panel** (`compare`) is drawn grey in every other panel, and its data is sent
  wherever it is in the order.

## Known limits

- Filtering by a statistic is typed as a range; the design review proposes small histograms
  to brush instead.
