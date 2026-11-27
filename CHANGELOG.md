# Changelog

All notable changes to anytrellis. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) (before 1.0, minor versions may change the API).

## [Unreleased]

### Added

- **One range for a figure's plots**: `concat(..., share_x=, share_y=)`, or
  `(a | b).share(y=True)`, gives the plots one range on an axis, as Altair's
  `resolve_scale(y="shared")`: `True` every plot, `"row"` the plots in each row, `"col"`
  those in each column. The range holds each plot's own over all its panels (`limits()`
  included), every panel takes it, and a plot changed while shown gives the others the new
  range; in the notebook (Jupyter and marimo), the saved page and the image alike.

- **One legend for a figure**: `concat(..., legend="collect")` shows its plots' legends
  once, under the figure, as patchwork's `guides="collect"`; each plot leaves its own out.
  A click on an entry selects its marks in every plot that has that legend (Shift adds
  one), hovering shows them, a double-click shows them alone; in the notebook (Jupyter and
  marimo), the saved page and the image.

- **A paged plot's pages in one PDF**: `save_pdf(path, pages="all")`, or a list of page
  numbers or names (`pages=[1, "north"]`). Each page is the grid of that page, in the
  order shown (sorted, filtered), says under the title which page it is, and is a bookmark
  of the PDF. The plot shown stays on its page; with `load="pages"` the rows are read a few
  pages at a time. The `pdf` extra now also installs `pypdf`.

### Changed

- **A figure's plots line up** (`a | b`, `a / b`, `concat()`), as in patchwork: their
  panels' left and right edges in a column, their tops in a row, and in a row the plots
  whose height is free as high as the highest of them, so their x axes line up too. A plot
  with `height=`, `panel_height=` or `aspect=` keeps its height. In the notebook (Jupyter
  and marimo), the saved page and the image alike; `concat(..., align=False)` shows each
  plot as it is alone, as before.
- `save_html` of a `load="pages"` plot reads the rows a few panels at a time (about two
  million rows), keeping of each what the page draws: saving a table larger than memory
  works, and takes less time. With 30 million rows it needs 1 GB more than the plot
  (was 5.6 GB), and 100 million 3.3 GB (was 9.4 GB). The page is the same.

## [0.8.0] - 2026-11-26

### Added

- **A plot in one call**: `at.line(df, x=, y=, wrap=)` and `at.points`, `at.bars`,
  `at.area`, `at.hist`, `at.density`, `at.box`, `at.violin`, `at.ecdf`, `at.hexbin`: each
  argument goes to `Trellis()` or to the mark by its name, an unknown one an error that
  says what was meant.
- **pandas' `df.plot`**: `pd.options.plotting.backend = "anytrellis"`. No x: the index; no
  y or several: one series a column; `by=` facets; `logy=`, `xlabel=`, `figsize=` and
  others as in pandas. `anytrellis.shortcuts.plot(df, kind=...)` does the same for any
  table.
- **`df.trellis`** on pandas and Polars tables, the shortcuts as methods, after `import
  anytrellis.pandas` or `import anytrellis.polars`.

- **Sizes for print and PDF**: `save_svg`, `save_png` and the new `save_pdf` take `width=`
  and `height=` as lengths (`"180mm"`, `"18cm"`, `"7in"`, `"500pt"`) as well as CSS pixels;
  `save_png` takes `dpi=` (instead of `scale=`) and records it in the PNG, and the SVG says
  its printed size. `save_pdf` writes a vector PDF, its text kept as text, at the plot's
  size (`pip install "anytrellis[pdf]"`). Figures (`concat`) have them too.

- **Different plots in one figure**: `a | b` side by side, `a / b` one under another, and
  `concat(*plots, cols=, widths=, title=)` a grid, nested as deep as you like. A figure
  shows in Jupyter (an ipywidgets grid of the plots) and marimo, saves as one page
  (`save_html`, linked plots still linked) and one image (`save_svg`, `save_png`), each
  plot in the same place.
- A plot too narrow for its title and toolbar puts the toolbar on a line under the title,
  its buttons on two lines when they don't fit on one.

- **Panels move to their places**: a sort, a filter or a panel opened (and back) slides
  each panel from where it was to where it goes in 250 ms, the panels new to the plot
  growing in about their middles. At once when the system asks for reduced motion, and for
  a page of all-new panels.

- `hexbin(x, y, bins=30, stat="count"|"percent")`: the rows counted in hexagons, coloured
  by their counts, the same hexagons in every panel. Hover one for its count; a brush
  selects its rows.
- `contour(x, y, color, levels=6, bw_adjust=1, gridsize=100)`: the lines of a
  two-dimensional density, per panel and colour, at levels shared by the panels.
- `rug(x=, y=, length=8)`: a tick at the panel's edge for each row's value, that stays
  at the edge as the panel zooms. A brush selects by its values alone.
- `segments(x, y, x2=, y2=)`: a line from (x, y) to (x2, y2) for each row.
- All four work with `load="pages"`: the database counts the hexagons and the contours'
  grid, and a page's rows draw the rugs and segments.
- `direction=`: the way a wrap fills its cells, `"h"` (rows, the default), `"v"`
  (columns) or two letters for any start corner and direction (`"lb"`: rows from the
  bottom left). Paged wraps fill each page the same way. A Fill setting and
  `t.direction`.
- `layout=`: a wrap's panels placed by a table of the wrap column(s), `row` and `col`
  (or a dict `{level: (row, col)}`), as R's geofacet: a map's or a plate's shape, the cells
  without a panel empty.
- `space="free_x"|"free_y"|"free"`: panels sized by their range, so a category or a day is
  as wide (or a unit as high) in every panel, as ggplot2's `space=`. With free scales
  along those lines; `t.space`.
- `repeat=[...]`: columns stacked as rows of panels, each on its own y scale: the data
  melted into `measure` and `value` (in the query, for a database).
- **Lasso selection**: `l` (or the toolbar's lasso) draws round the marks to select;
  dragged from inside, it moves. From Python, `select(lasso=[(x, y), ...])`;
  `selection["lasso"]` has its corners.
- **Click selection**: with select or the lasso on, a click selects the mark under it
  (with `link=`, its key in every panel), Shift+click adds or removes one, a click on no
  mark clears. From Python, `select(at=[(x, y)], panel=...)`; `selection["at"]`.
- Both work with `load="pages"`: the lasso is a condition of the query (a point inside the
  polygon by the even-odd rule), the same rows memory selects, and with `save_svg` /
  `save_png`, which draw the lasso's outline.
- **Linked plots in a saved page**: `Link.save_html(path, cols=1)` (and `to_html`) writes
  the plots of a link to one page that stays linked without a kernel. A brush, lasso or
  click in one highlights the same rows in the others, a histogram's bars filled to the
  share selected, as in a notebook; the selection made in Python is saved with it. Plots
  reading DuckDB (`load="pages"`) are saved with every row and link `on=` their keys.
- **Views**: `save_view(name)` keeps what a plot shows (sort, filters, pins, page, the
  panel opened or compared, the zoom), `show_view(name)` shows it again, `drop_view` and
  `views`. The page bar's Views menu lists them, shows one and keeps the one shown; a saved
  page keeps them, and a link to it ending `#view=<name>` opens on one.
- **Filter histograms**: in the page bar's filters, each number statistic shows its values
  over the panels as a small histogram (the panels the other filters keep on top). Drag
  across it to filter by that range; a click clears it.
- **The marks by the keys**: in a panel opened (or a plot of one panel), the arrow keys step
  through its marks, ← → along x and ↑ ↓ to the mark above or below (Home, End: the ends).
  Each shows its tooltip, said to a screen reader through a live region; the view follows a
  mark off it.
- **A table view**: the toolbar's table button (or `t`) shows each panel's statistics and,
  when 500 or fewer, the rows the plot draws as HTML tables; a panel's name opens it. A
  saved page has it too.

### Changed

- `stats()` gives the panels' statistics of any plot, not only a paged wrap's.
- With select on, a click on a mark selects it; a click on no mark still clears the
  selection.

### Fixed

- Full screen fits a paged wrap on the screen: the pager's bar was left out of the height,
  so the plot ran past the bottom and its x axis needed a scroll.

## [0.7.0] - 2026-11-21

### Added

- **A settings panel** in the toolbar (or `,`): the columns, the panels' shape, how the
  scales are shared, log, square-root and symlog scales, the colour column and the
  panels' order (by the median, mean, extremes or rows), each the property or method of
  the same name in Python (`t.cols`, `t.aspect`, `t.share_x`, `t.share_y`, `t.x_scale`,
  `t.y_scale`, `t.color`, `order()`), synced both ways. A change the plot can't draw is
  refused with the reason. `controls=False` leaves it out.
- `t.title`, `t.subtitle`, `t.caption`, `t.height` and `t.panel_height` redraw a shown
  plot when set, and are in its code. Of a height and a panel shape (`aspect`), the one set
  last sets the panels' height, in Python and in the settings panel.
- The settings panel keeps a choice the plot had that its lists don't offer (a shape like
  `aspect=0.8`, `share_y="row"` on a wrap, a colour column of many categories, an order
  of given levels or descending) after another is chosen, to go back to. Panel shapes
  read width:height: Wide (2:1), 4:3, Square, Tall (2:3).
- **`t.code()` and "Copy as Python"**: the Python that makes the plot as it is now, the
  calls that made it with every change made by hand written in (the settings panel, the
  page bar's sort, filters and pins, the compared panel), tables by their notebook names.
  Run, it makes the same plot. Saved pages keep "Copy as Python".
- **A description for screen readers**: every plot gets a sentence made from what it
  shows ("Scatter of mpg against weight, one panel per origin (3), coloured by cylinders.
  406 rows. mpg from 9 to 46.6; weight from 1613 to 5140."), `t.description`. The plot is
  a figure (`role="figure"`) labelled with it; saved SVGs (Python's and the browser's) have
  it as their `<title>`/`<desc>`. `Trellis(alt=...)` says it in your words. With
  `load="pages"` the rows are counted in the database.
- **A second encoding**: `Trellis(redundant=True)` (or `set_theme(redundant=True)`)
  gives a colour column's categories a shape each on points and a dash each on lines, in
  one legend, so colour doesn't carry them alone. A layer's own `shape=`/`dash=` wins.
- **Touch**: pinch to zoom a panel about the fingers (side by side: x alone; one above
  the other: y alone), two fingers to pan, a long press for the values there (pinned; a
  tap lets them go). One finger scrolls the page past the plot, unless box zoom or select
  is on or the plot fills the screen, when it draws as a mouse drag does.
- **A cheat sheet** in the documentation: all of anytrellis on one page, as code that runs
  (the tests run it).
- **The documentation for AI assistants** ([llms.txt](https://llmstxt.org)):
  `llms.txt` maps the pages with what each holds, `llms-full.txt` has them all in one file,
  and every page is also Markdown at its address with `.md` for `.html`, the API reference
  written out from the docstrings.
- **Text size and contexts** in `Theme`: `font_size=` sets the text's size in pixels, and
  `context="paper"`, `"notebook"`, `"talk"` or `"poster"` scales the text, line widths
  and point sizes together (0.8, 1, 1.5, 2), for a figure in a paper or a plot on slides:
  `set_theme(context="talk")`. The header, legend and caption follow the size, and images
  saved from Python draw it the same.
- **Square-root and symlog scales, and reversed axes**: `x_scale=`/`y_scale=` (and
  `scale()`) take `"sqrt"` (counts and sizes, 0 kept at the bottom) and `"symlog"` (a log
  scale either side of 0, linear near it, for changes), with ticks at round values or at
  symlog's decades. `"reverse"` runs an axis from high to low, alone or with a scale:
  `y_scale=("log", "reverse")`. Bars, areas, histograms and densities go on a sqrt or
  symlog y (stacked or counted first, then drawn on the scale). Summaries, selections,
  limits, rules, `load="pages"` queries and saved images all follow the scale.
- **Tooltips that compare**: over lines coloured by a category, the tooltip lists every
  series at the x nearest the pointer, top to bottom, with a ring on each. A click pins a
  tooltip, so you can compare it with the next one and copy from it (Esc or its ×
  unpins it). The crosshair's x and y are written on the axes.
- **A legend to explore with**: hovering an entry makes its marks stand out in every
  panel, and a double-click shows that colour alone (again, or Esc: all of them). Dragging
  on a number colour's gradient selects the marks of the values in that range, and a
  binned scale's entries each select their range; from Python, `select(color=(low,
  high))`, and `selection["color"]` gives the range back. `selected()` follows, in a
  `load="pages"` query too.
- **Long legends** show their first 20 entries, how many more there are, and a search box
  for the rest.
- **`legend("top")`** puts the legend over the panels, under the title.
- **Bars that count or summarise**: `bars(x="origin", stat="count")` counts the rows at
  each position (y alone: bars along y), and `stat="sum"`, `"mean"` or `"median"`
  summarises y's values at each x (and colour). Counts and sums stack; means and medians
  go side by side. Hovering a bar shows its value and how many rows it stands for, and
  brushing it selects them.
- **`ecdf()`**: the empirical cumulative distribution per panel and colour, as steps
  (`stat="proportion"`, `"percent"` or `"count"`; `complementary=True` for survival).
- Both come from the database with `load="pages"`: the bars as a grouped query, the ECDF
  counted in 1,024 bins.
- **Compare every panel with one**: *Compare with this* on a panel (its button, or `c`)
  draws that panel's marks in grey in every other, a reference chosen as you go;
  `t.compare("Japan")` from Python, `t.compare()` to stop. A chip says which panel, and
  saved images draw it too.
- **Pinned panels**: in a paged wrap, a pinned panel (its pin button, or `p`) stays first
  on every page, whatever the sort and the filters, with a pin in its strip;
  `t.pin(...)`, `t.unpin(...)` and `t.pinned` from Python. Pins travel with the paging to
  Python, saved images and `save_html` pages, and with `load="pages"` their data comes
  with every page.
- **Moving between panels with the keys**: the arrow keys move a ring from panel to panel
  (its name is said to screen readers), Enter opens it, `p` pins it, `c` compares with it,
  Esc lets it go. Pointing at a panel shows its buttons: open, pin, compare
  (`Trellis(..., panel_buttons=False)` leaves them out; the keys still work).
- **Names at the ends of lines**: `line(color="country", label="end")` writes each
  series' name at the end of its line, in its colour, in place of the legend: once in the
  plot, in the panel where the line ends rightmost, moved apart where lines end close
  together (a name too far from its line is left out until you zoom in), at the last
  point in view as you zoom. Hovering a name shows its line in every panel; a click
  selects it, as its legend entry would. The x axis leaves room for the names.
- **Text labels that keep apart**: `text(..., repel=True)` places each label at the first
  spot around its point (right, left, above, below, the corners, then farther out with a
  line back) where it covers no other label nor a point, inside the panel; one with no
  room is left out until zooming in makes room.
- **`annotate()`**: a note at a data position (a number, a time, a category), in one
  panel, several or every one: `t.annotate("Heat wave", x="2015-06-27", y=32,
  panel="sun", dx=30, dy=-20)`, with a line back to the position when moved. With x
  alone it sits at the panel's top, with y alone at its left. Notes and names have a
  halo of the panel's colour, and saved images draw them alike.
- **Shape, size and dash from columns**: `points(shape="species")` gives each category a
  shape (circle, square, triangle, diamond, plus, cross, triangle down), `points(size="pop")`
  sizes points by a number column, by area (`size_range=(2, 14)`, the largest drawn
  first), and `line(dash="scenario")` dashes each category's line its own way (or
  `dash=(4, 3)`, every line). The same column as `color=`: one legend shows both, a
  second encoding for readers who can't tell the colours apart; another column gets a
  legend of its own. The saved images (`save_svg`, `save_png`, Export) draw them alike.

### Changed

- **Text steps with the panels' size** in the minimal and framed themes
  (`font_size="auto"`): ticks, strips and axis titles are 11 px in panels under 160 px
  wide and 13 px in an opened panel, 12 px otherwise. classic keeps 12 px. Category labels
  thin out by the text's size, so they fit as the text grows or shrinks.
- **Tooltips have a title line** (the panel and the x value), then a row a value: the
  mark's, with a swatch of its colour, its colour column and the `tooltip=` columns.
  Values lose the zeros that only pad them (1975, not 1975.00).

## [0.6.0] - 2026-11-17

### Changed

- **A new default look**, `theme="minimal"`: panels without a fill, the grid as the text
  colour at 10% opacity and only across y (across x too for points, or when y is a band),
  an x baseline and no y axis line, strips as left-aligned semibold titles with nothing
  behind them, the y title level over the plot (`↑ temp`), a grid's row labels level at the
  right as wide as they need, no x title on a time axis unless given, and Petroff's
  colour-vision-tested palette (`petroff10`) in place of tab10. A paged wrap's strip keeps
  the panel's name whole and shows the sorted value in lighter type. `theme="classic"`
  keeps the look before ([Upgrading](docs/user/reference/upgrading.md)); images saved from
  Python (`save_svg`, `save_png`) draw both looks the same as the browser.
- **The toolbar explains itself.** What a drag does is one control of three, pan, box zoom
  and select, with the one on filled; they were two toggles that left pan implied. The
  icons are in the muted colour at full opacity (over 3:1 on the background), the text
  colour on hover and focus, where they were faded to 45% and looked disabled. Chips beside
  the toolbar say what differs from the start, "Zoomed in x", "267 of 693 marks selected",
  "2 filters: 12 of 40 panels", each with its Reset or Clear (the count of a brush released
  is no longer a passing notice). `?` or the new **?** button shows the keys and mouse,
  the renderer and the anytrellis version; the renderer's name no longer appears in the
  plot's corner on hover.
- **Time axes take the nearest calendar step**, as d3 does, not the next larger one, and
  never fewer than two ticks: a week of data in a narrow panel is labelled every two days,
  where it showed a single date; a year at six ticks is labelled every two months.
- **Category labels too long to sit side by side wrap onto two lines, or failing that are
  set at 45 degrees** (cut at 90 px), instead of being thinned out: every variety of the
  barley data now shows under its bar, where two of ten did. The x axis grows to hold them,
  in the browser and in `save_svg` / `save_png`.
- Panels with an `aspect` (banked or a number) keep their shape in full screen, in an
  opened panel and in an image of a given `height`: as large as fits, narrower and centred
  when the height is too low for the whole width. An opened panel is then at most 85% of
  the window high (720 px in an image), and at least 320 px. Before, the height given
  overrode the shape. Plots without an `aspect` are unchanged.

### Added

- **Bars along y**: `bars(x="units", y="product")`, with a category y and x not, draws
  the bars from zero along x, stacked or dodged as upright ones are.
- **`position="fill"`** on `bars()`, `area()` and `hist()`: each stack as shares of its
  total, up to 1, on an axis written in percent.
- **`points(jitter=)`**: points spread across their category's band, up to that fraction
  of its width, each row in the same place every time it is drawn.
- **Rules from data**: `rule(targets, y="target")` draws a line per row of a table, in the
  panel of its facet columns' values (or every panel, without them).
- **`colormap()`** for number colour columns: `"viridis"` (the default), `"cividis"`,
  `"magma"`, `"Blues"`, `"RdBu"` and `"PuOr"`, each reversed with `"_r"`, or a list of
  colours; and how the values take it, `scale=`: `"linear"`, `"diverging"` (as deep on
  both sides of `midpoint=`, RdBu with red high by default), `"binned"` (about `bins=`
  steps of round width) or `"quantile"` (`bins=` steps of as many values each). A stepped
  scale's legend lists its ranges (`"10–20"`), written by `format(color=)` when given.
- **`palette="okabe-ito"`** (Okabe and Ito's eight colours), and `palette=` as a dict,
  `{"USA": "#d62728"}`: those categories keep their colours in every plot, the others take
  the palette's colours that are left.
- **`limits(x=, y=)`**: an axis's range, either end `None` for the data's own
  (`limits(y=(0, None))`); times as dates, log axes in their values. Zooming starts there
  and Reset returns there.
- **`format(x=, y=, color=)`**: d3-format strings for numbers (`",.0f"`, `".1%"`, `".2s"`,
  `"$,.2f"`) and strftime strings for times (`"%b %Y"`), for tick labels, tooltips and a
  colour legend's ends, in the page and in `save_svg` / `save_png` alike. Both sides are
  checked against d3's own output.
- **`legend(position, title=)`**: `"right"` (a column right of the plot) and `"none"`
  join `"auto"` and `"bottom"`, also as `Trellis(legend=)`; `title=` renames the legend.
- **`subtitle=` and `caption=`** on `Trellis` and `pairs`: a line or two under the title,
  and a note under the plot (a source, a footnote). Both wrap, and both are in exported
  images, from the page and from `save_svg` / `save_png`.
- **`labels=`**, one dictionary naming columns for readers (`{"mpg": "Fuel use (mpg)"}`):
  used for axis titles, the legend's title, tooltips, a page column's title, the sort and
  filter menus, and a pairs plot's strips. Code still names columns as they are.
- `Trellis(theme=)`: `"minimal"`, `"framed"` or `"classic"`, also on `pairs()`. `framed`,
  after Observable Plot, draws a thin frame around each panel, 10 px between them, strips
  centred, the x title at its axis' end (`weight →`) and d3's observable10 palette.
- `anytrellis.Theme("minimal", frame=True, panel_gap=12, ...)`: a named theme with any of
  its settings changed (panel fill, frame, grid direction and opacity, axis lines, strip
  fill, alignment and weight, where the axis titles go, row labels level or on their side,
  the gap between panels, the palette). `anytrellis.set_theme()` sets the session's
  default; `get_theme()` reads it.
- `palette=` takes a name: `"petroff10"`, `"petroff8"`, `"petroff6"`, `"observable10"` or
  `"tab10"`.
- `Trellis(aspect="bank")`: the panels' shape that shows the median slope of the lines'
  segments at 45 degrees, each measured in its own panel's ranges (Cleveland's banking):
  the `smooth()` fits' (a trend, not the noise around it), or without them the `line()`
  layers'. Between 0.02 and 5 times as
  high as wide; with `load="pages"`, kept from the panels read first.
- `horizon(x, y, bands=3, origin=0, step=None)`: a horizon chart in each panel. A series'
  distance from `origin` is cut into bands of one height, laid over each other and darker
  the farther, blues above the origin and reds below it, so a series shows its highs and
  lows in a panel 24 px high. Every panel shares the band height (by default a round
  number reaching the farthest value of any panel); the legend names each band's range,
  and clicking it selects the times a series reaches it. Works with `load="pages"`;
  margins are left empty.
- `Trellis(margins=)`: a grid's "(all)" panels, as ggplot2's `facet_grid(margins = TRUE)`.
  `True` adds an (all) row under the rows (each panel the rows of its column) and an (all)
  column right of the columns (each panel the rows of its row), with a corner of every
  row; `"row"` or `"col"` adds one. Every layer draws them, summaries computed from their
  rows; a row selected in a margin is selected once. With `empty="blank"` and `page=`;
  not with `load="pages"` or a wrap.
- `share_x="sliced"` / `share_y="sliced"` (also in `share()`): each panel its own range,
  about its own data, every one as wide as the widest, so a change of 5 looks the same size
  in every panel (lattice's `relation="sliced"`). Zooming one panel zooms all to its width,
  each about its own centre; panning moves one; fitting y keeps them as wide. Bars keep
  their base at 0. With `load="pages"`, the widths come from every panel's range in the
  database. Not on an axis of categories.

### Fixed

- Lines, areas and bands drawn in other panels than their own (a margin's, or with
  `facet="all"` or `"exclude"`) no longer join the rows of several panels into one line
  zigzagging between them: each panel's rows stay a line of their own.

## [0.5.0] - 2026-11-09

### Added

- `Trellis.as_category("column")`: a number column read as categories. Its distinct values
  are the levels, in order (`-10, -2, 3`), labelled as numbers (`4`, not `4.0`), rows
  without one last as `(missing)`: a colour per value from the palette with a legend, a
  band per value on an axis, a series per value with `group=`, and `order()` with numbers.
  With `load="pages"`, the database finds the values and selects by them.

### Fixed

- Panel backgrounds, gridlines, strips and axes no longer vanish when the window is
  resized. A resized plot is drawn again at once instead of a frame later, and a plot
  whose height brings a page scrollbar at one width and not 17 px narrower (Windows) no
  longer flips between the two widths every frame, blank each time: it keeps the narrower.

## [0.4.0] - 2026-11-08

### Added

- `Trellis(strips=)`: `"nested"` (the default) or `"joined"`. With several facet columns,
  nested strips give each column a strip, the first outermost, spanning the panels next
  to each other that share its level (as ggh4x's in R): stacked on top of a grid's columns
  and a wrap's panels, side by side on the right of a grid's rows. Saved images draw them
  too.
- `Trellis(empty="blank")`: a grid's cells without data are left out, and the other
  panels keep their rows and columns, with axes drawn into the blank cells beside them.
  The default, `"draw"`, keeps the empty panels. With `page=`, a cell is left out when
  it has no data on any page, so every page has the same cells.
- `Trellis(strip_label=)`: a column whose value names each panel (one value per panel),
  in a strip of the panel's own, in a grid too, in place of the row, column and nested
  strips. A panel without a value is named by its levels; panel names in `panels()` and
  `open()` stay the levels. With `load="pages"`, the database gives the labels with the
  panels.

### Changed

- A plot faceted by several columns (`wrap=["a", "b"]`, `col=[...]`, `row=[...]`) now
  shows nested strips, not one strip per panel naming the levels together (`"a · b"`);
  `strips="joined"` shows those. Panel names in `panels()` and `open()` are unchanged. See
  [Upgrading](https://mluttikh.github.io/anytrellis/reference/upgrading.html).

### Fixed

- A panel's last x label no longer runs into the y labels or the strip of the panel below
  and right of it, when both draw into the empty cell between them ("10" over "4").

## [0.3.0] - 2026-11-08

### Added

- `Trellis(page=)`: a page per level of a column (or columns). A grid (`row=`, `col=`)
  shows each level's every cell, in the same place on every page; a wrap shows the level's
  panels, sorted and filtered within it, on several pages with `rows=` when there are more
  than fit. The pager names the page shown and lists the levels to pick from;
  `show_page("north")` and `page_names` do the same from Python. `share_x="page"` and
  `share_y="page"` give each page its own scale. With `load="pages"`, a level's rows are
  read as its page is turned to.
- `pairs()`: a scatterplot matrix of a table's number columns, x by column and y by row,
  each variable's scale shared along its column and its row. The diagonal shows each
  variable alone (a density curve per colour, or a stacked histogram) over its own range.
  Brushing a panel lights up its rows in every panel; `selected()` gives them as rows of
  the table, and hovering a point shows its row. `corner=True` keeps each pair once.
- `Trellis(aspect=)`: each panel's height as a multiple of its width (`1`: square).
- Lazy tables and databases: a Polars `LazyFrame`, a DuckDB relation or an Ibis table (on
  any database Ibis queries) is read in one query, with only the columns the plot uses,
  when the plot is first drawn. The database computes the panels' summaries: the pages'
  statistics (rows, mean, median, min, max, sd) and `order()`'s summaries; the trend comes
  from the rows without sorting them. Ten million rows in 1,000 panels build in 3.3 s
  rather than 5.3 s from Ibis on DuckDB (3.2 s rather than 6.6 s from a `LazyFrame`).
- `Trellis(load="pages")`: a paged wrap of a lazy table (DuckDB, Ibis, a `LazyFrame`) reads
  only the rows of the panels of the page shown and the pages either side of it, and the
  next ones as the pages turn. The panels, their statistics (with the trend), each panel's
  range of x and y, the category levels and the colour ranges come from the database, so
  every page looks as with every row read. Ten million rows in 1,000 panels from DuckDB
  are drawn in 1.0 s from 480,000 rows read (3.9 s reading all of them); a page turned
  reads only the page that came near and makes only its panels' lines and points, keeping
  the others', in 0.2 s. `selected()` is a query of the selected
  rows; a saved page reads every row of the lines, points and text.
- Summaries with `load="pages"`: `hist`, `box`, `violin`, `density`, `smooth` and
  `errorbar` of the plot's data are computed by the database, every panel's at once, and
  no row is read: bin counts, quartiles and whiskers, means and spreads, sums of squares,
  and values in fine bins for densities, violins and loess fits (drawn from the bins, to
  within about 0.03%). The axes are every panel's from the start, and pages turn without
  asking again. A brush over a summary selects the rows it stands for, as a query. Ten
  million rows in 1,000 panels: a histogram in 0.8 s (3.2 s reading every row), a loess
  fit in 3.6 s (22 s).
- Linking with `load="pages"`: `link=` selects the rows sharing the brushed rows' keys in
  every panel, as a query. `anytrellis.link(..., on=)` links a plot reading pages to any
  other: its selection is read as the keys chosen, and a selection elsewhere lights up the
  rows of the pages read and fills its summaries to the share of the keys chosen, which
  the database counts in a query per summary (0.2 s for 4,000 of 5,000 keys over ten
  million rows). A link of a plot reading pages needs `on=`.
- Paged wraps send only the panels near the page shown: in a notebook, the browser gets
  the data of the page shown and the pages either side of it, and more as the pages turn,
  are sorted or filtered, or a panel of another page opens; a page further away says it
  is loading until its data comes. A thousand panels of a week's readings start with
  2.2 MB instead of 46 MB. A page from `save_html` or `to_html` still holds every panel.
- Level of detail: what goes to the browser grows with the pixels shown, not the rows. A
  panel of more than 20,000 points of a line sends each series thinned (M4: per column,
  its first, last, lowest and highest point), and a panel of more than 100,000 points is
  drawn as cells, each in its points' colours mixed in proportion and more opaque the more
  it holds; hovering one tells its points, of each colour. Zoomed in, in a notebook, Python
  sends the panels shown in more detail: a line at two columns a pixel, finer cells, or
  the points again. Four million points send about 1 MB instead of 128 MB, and their
  `save_html` page shrinks from 171 MB to 1.4 MB. Selections still use every row;
  `save_png` and `save_svg` draw the detail shown; a saved page shows the plot as it
  starts.

### Changed

- A lazy table (a Polars `LazyFrame`, a DuckDB relation, an Ibis table) is read when the
  plot is first drawn, with only the columns it uses, not collected whole when the plot
  is made. A panel of more than 20,000 points of a line or 100,000 points shows them at
  the level of detail its pixels need (see Added); zoom in for more. No code changes. See
  [Upgrading](https://mluttikh.github.io/anytrellis/reference/upgrading.html).
- Faster selections over linked rows (`link=`): number and category link columns are
  keyed from their values and codes, not their text; and dense points' cells are counted
  and grouped without sorting their points.
- Faster plots of many rows in panels: rows find their panel by their column's codes, not
  their text, and numbers as panels are labelled once per value, not once per row. Four
  million rows of a line in four panels build in 1.2 s instead of 2.2 s (by a column of
  numbers: 1 s instead of 4.2 s), and in 1,000 panels ordered by a median, with statistics
  to sort pages by, in 3.5 s instead of 93 s.
- Text columns are encoded by PyArrow when it is installed, not labelled row by row in
  Python: ten million rows of text facets read in 0.15 s instead of 4 s. A Polars
  `DataFrame` of ten million rows in 1,000 panels builds in 4.2 s instead of 6.1 s.
- Rects edge to edge (heatmap tiles, cells) show no seams between them in Canvas 2D, the
  browser's image export, `save_png` and `save_svg`: their edges fall on whole pixels.

## [0.2.0] - 2026-11-07

### Added

- Export images of a plot (toolbar button, or `e`): copy a PNG, or an SVG with a PNG beside
  it, to the clipboard; download a PNG (twice the screen's size) or an SVG; or, in a
  notebook, save either next to the notebook without overwriting. The image is the plot as
  shown (zoom, selection, opened panel, theme), without the toolbar. It works in pages
  saved with `save_html` too.
- `Trellis.save_png` and `Trellis.save_svg`: the same image drawn in Python, without a
  browser (scripts, reports, CI): the zoom last shown in the notebook, the selection, a
  linked plot's highlight and an opened panel, in the light or dark theme, at any size.
  PNGs need the new `png` extra (`pip install "anytrellis[png]"`, with resvg-py).
- Pages of panels: a wrap of more than 100 panels shows them a page at a time (6 by 4;
  `Trellis(rows=, cols=)` sets the page, `rows="all"` turns paging off), with a bar to turn
  the pages (also Page Up and Page Down), sort the panels by a statistic of each and filter
  them by name and by statistics' ranges. The statistics are computed in Python: rows, and
  the mean, median, min, max, sd and trend of the values drawn, plus any columns given with
  `panel_stats()`. From Python: `sort_panels()`, `filter_panels()`, `show_page()`,
  `shown_panels()`, `stats()`, `page`, `pages` and `paging`. An opened panel steps through
  the panels as sorted and filtered; images and saved pages show the page shown.
- `violin()`: each group's values as a violin (a kernel density mirrored around its
  position), with its median and quartiles, or its values as points (`inner=`). Scaled to
  the same area, by count or to the same width (`scale=`); side by side with a colour,
  sideways when y is the category. Brushing selects whole violins.
- `errorbar()`: each group's mean with its confidence interval (`extent="ci"`, at
  `level=`), standard error, standard deviation or range, with caps and a point at the
  mean; or intervals you computed, from `ymin=`/`ymax=` (or `xmin=`/`xmax=`, sideways).
- `line(step=...)`: step lines, `"post"`, `"pre"` or `"mid"`. Hovering a step shows the
  row it starts from.
- Documentation at [mluttikh.github.io/anytrellis](https://mluttikh.github.io/anytrellis/):
  tutorials, how-to guides, a gallery, the API reference and explanations, with live plots.

### Changed

- A wrap of more than 100 panels now shows them a page at a time (it drew them all, small);
  `Trellis(..., rows="all")` draws them all as before. See
  [Upgrading](https://mluttikh.github.io/anytrellis/reference/upgrading.html).
- A page of many plots (`standalone.js`) starts each plot as it scrolls near, so a long
  page stays within the browser's limit of GPU contexts.

### Fixed

- Tooltips on documentation sites (Material, Zensical) are as compact as in a notebook:
  the site's table styles no longer reach them, nor its letter spacing the plot.
- A linked plot's highlight of part of a histogram's bars draws the faded bars whole, with
  the selected share solid from their base (the faded part was missing).
- x labels of neighbouring panels no longer run together at their edges ("AprMar"): a
  label that would reach the next panel's first is left out.
- Box plots failed in WebAssembly (marimo's in-browser notebooks, Pyodide), where indices
  are 32-bit.
- A plot now redraws when the page switches between light and dark by
  `data-md-color-scheme` (Material and Zensical sites).

## [0.1.0] - 2026-11-07

The first release.

### Added

- `Trellis`: one panel per level of the facet columns: a wrap (`wrap=`, `cols=`) or a
  grid (`row=`, `col=`) that keeps empty cells, with shared, per-row, per-column or free
  scales (`share_x=`, `share_y=`), linear or log (`x_scale=`, `y_scale=`).
- Marks: `line`, `points`, `bars` (stacked or dodged), `area`, `band`, `rect`, `text`,
  `rule`, and summaries computed per panel in Python: `hist`, `box`, `density` and `smooth`
  (loess or linear, with a confidence band).
- Data from Polars, pandas, PyArrow or DuckDB (through narwhals), or a dict of arrays;
  numbers, times and categories, with category colours and legends.
- Drawing with WebGPU, WebGL2 or Canvas 2D, whichever the browser has; the data goes to the
  browser once, as binary buffers, so millions of marks stay interactive.
- Zooming and panning (scroll, drag, one axis, box zoom), panels that share a scale
  zooming together, `fit_y` to fit y to the data in view, undo and reset; one panel at a
  time (`open`, `close`) and full screen.
- Selecting: a brush (`s`) in every panel or, with `link=`, in one panel and followed by
  key; `select()`, `selection` and `selected()` from Python. Clicking legend entries
  selects their colours.
- Linked plots: `link(a, b, ..., on=)` shares one selection between plots, histograms
  filling to their selected share (crossfiltering).
- Tooltips with Python's values; `save_html` writes a page that opens without Python.
- Works in JupyterLab and marimo, and other anywidget hosts (Jupyter Notebook, VS Code).
- `anytrellis.datasets.load`: six small example datasets, with their sources and licences
  in `datasets/SOURCES.md`; example notebooks for Jupyter and marimo.

[Unreleased]: https://github.com/mluttikh/anytrellis/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/mluttikh/anytrellis/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mluttikh/anytrellis/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mluttikh/anytrellis/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/mluttikh/anytrellis/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/mluttikh/anytrellis/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mluttikh/anytrellis/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mluttikh/anytrellis/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mluttikh/anytrellis/releases/tag/v0.1.0
