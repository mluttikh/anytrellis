# Mouse and keys

Click a plot first: before a click, scrolling scrolls the page and keys go to the
notebook. After it, the keys below go to the plot, and stay there, so JupyterLab's own
shortcuts don't also act on them.

## Mouse and trackpad

| Do | Over | To |
| --- | --- | --- |
| Scroll | a panel | zoom x, at the pointer |
| Shift+scroll | a panel | zoom y |
| Scroll | an axis | zoom that axis alone |
| Drag | a panel | pan |
| Drag | an axis | pan that axis alone |
| Double-click | an axis | reset that axis |
| Shift+drag | a panel | box zoom: sideways zooms x, up or down zooms y, otherwise both |
| Drag | a panel, select on (`s`) | a brush: the marks in it selected, in every panel (with `link=`: in its panel, and their keys in all) |
| Draw round | a panel, lasso on (`l`) | a lasso: the marks inside its outline selected, as a brush selects them |
| Drag | inside the brush or the lasso | move it |
| Click | a mark, select or lasso on | select that mark (and with `link=`, its key in every panel) |
| Shift, Cmd or Ctrl+click | a mark, select or lasso on | add it to the marks clicked, or take it away |
| Click | no mark, select or lasso on | clear the selection |
| Hover | a mark | its values, a crosshair in every panel that shares x, and the pointer's x and y on the axes |
| Hover | lines coloured by category | every series at the nearest x, top to bottom |
| Click | a panel, with a tooltip shown | pin the tooltip: it stays, to compare with the next one and to copy from |
| Double-click | a panel | see it alone |
| Hover | a panel | its buttons at its top right: open it, pin it first on every page (a paged wrap), compare every panel with it (`Trellis(..., panel_buttons=False)` leaves them out) |
| Hover | a legend entry | its marks stand out in every panel, the others fade |
| Click | a legend entry | select that colour's marks |
| Shift, Cmd or Ctrl+click | a legend entry | add or remove a colour |
| Double-click | a legend entry | show that colour alone, the others hidden (again, or ++esc++: all) |
| Drag | a number colour's legend (its gradient) | select the marks of the values in that range (a click clears it) |
| Click | a stepped colour scale's entry | select its range of values (Shift: widen the range) |

Zoom and pan apply to every panel that shares the scale. An axis stands for its whole
scale: with `share_y="row"`, zooming the left axis of a row zooms that row. With
`share_y="sliced"`, zooming one panel zooms every panel to its width; panning moves one.

## Touch

On a phone or a tablet, one finger scrolls the page past the plot, so a plot in a long
page never traps it. The plot takes two fingers.

| Gesture | Does |
|---|---|
| Pinch | zoom the panel under the fingers, about their midpoint: fingers side by side zoom x alone, one above the other y alone, at a slant both |
| Two fingers moved | pan |
| Long press | the values there, pinned (a tap lets them go) |
| Tap | as a click: let pinned values go, pick a line's end label |
| One finger | scroll the page; with box zoom, select or the lasso on (toolbar, `z`, `s`, `l`), or in full screen, a drag as with the mouse |

`u` (or the toolbar's reset) undoes a pinch as it does a zoom. The first time one finger
scrolls the page, the plot says that two fingers pan and zoom.

## Tooltips

Hovering a mark shows a tooltip. Its first line is the panel and the position along the
axis: x, or y for bars along y. Then a row for each value: the mark's value, with a swatch
of its colour, its colour column, and the `tooltip=` columns. Names are as `labels=` gives
them and values as the axis formats them (`format()`).

Over lines coloured by a category column, the tooltip lists every series at the x nearest
the pointer, from top to bottom. The series nearest the pointer is in bold, and each one
gets a ring. Where a colour holds several lines (`group=` within a colour), the tooltip
shows the line you hover instead.

The crosshair's x and y are written on the axes, so you can read them in every panel along
the row and column.

A click pins the tooltip: not the first, which gives the plot the keys, and not with select
or the lasso on, where a click selects the mark under it (or, on none, clears the
selection). It stays
where it is while you hover on, so you can compare two points, and you can select and copy
its text. A click away from the marks, ++esc++ or its
× unpins it, and so does zooming, panning or opening a panel.

## Keys

| Key | Does |
| --- | --- |
| ++r++ or ++0++ | reset the zoom |
| ++u++, ++cmd+z++ or ++ctrl+z++ | undo the last zoom |
| ++z++ | drag draws a zoom box, and back (Shift+drag always does) |
| ++y++ | fit y to the data in view, and keep fitting it as x changes; again to stop |
| ++s++ | drag draws a selection brush, and back |
| ++l++ | drag draws a lasso, and back |
| ++esc++ | unpin the tooltip; with none, show every legend entry again; then let go of the mark the arrow keys reached, or their ring; then stop comparing; then clear the selection; then back to all panels |
| ++left++ ++right++ ++up++ ++down++ | move a ring from panel to panel (its name is said); in a panel opened, or a plot of one panel, step through its marks: ++left++ ++right++ along x, ++up++ ++down++ to the nearest mark above or below. Each shows its tooltip, said to a screen reader |
| ++home++ ++end++ | in a panel opened (or a plot of one): its first or last mark |
| ++t++ | the plot as a table: each panel's statistics, and the rows when 500 or fewer |
| ++enter++ | open the panel the ring is on, or the one under the pointer |
| ++p++ | pin that panel first on every page of a paged wrap, and unpin it |
| ++c++ | compare every panel with that one: its marks in grey in the others; again to stop |
| ++page-up++ / ++page-down++ | the previous / next panel, at the same zoom; with none opened, the previous / next page of a paged wrap |
| ++backspace++ | back to all panels |
| ++e++ | the Export menu: copy, download or save an image |
| ++comma++ | the settings panel: columns, panel shape, scales, colour, order; *Copy as Python* |
| ++f++ | full screen, and back |
| ++question++ | the keys and mouse, the renderer drawing the plot and the anytrellis version |

## The toolbar

The buttons at the top right do the same as keys. The first three choose what a drag
does, one of them always on: pan, box zoom (++z++) or select (++s++); with one focused, the
arrow keys move along them. Then fit y (++y++), reset (++r++), the table (++t++), settings (++comma++), export
(++e++), the keys and mouse (++question++) and full screen (++f++). The settings panel
changes the layout, scales, colour and order, and copies the plot's Python ([Change a plot
from its settings panel](../how-to/settings.md)). With a panel opened, the strip over it
has *All panels* and the previous and next buttons. Over a paged wrap, a bar turns the
pages, sorts the panels and filters them (a drag across a statistic's histogram sets its
range, a click clears it), and shows or keeps views ([Page through many
panels](../how-to/pages.md)).

## Panels moving

Opening a panel grows it from its place in the grid; going back shrinks it to its place
while the others grow in. A sort or a filter slides each panel to its new place. Each move
takes about a quarter of a second, and you can carry on meanwhile. With reduced motion set
in your system's settings, the panels go to their places at once.

## What the plot shows

When the plot no longer shows what it started with, the header says so, beside the
toolbar, each with its way back:

| Chip | Button |
| --- | --- |
| Zoomed in x (y, x and y) | Reset: the zoom the plot started with |
| 267 of 693 marks selected | Clear: no selection |
| Selected in a linked plot | Clear: that plot's selection |
| 2 filters: 12 of 40 panels | Clear: the paged wrap's filters and name search |
| Compared with Japan, in grey | Clear: compare with none |
| 2 pinned | Unpin: the pinned panels back in their places |

A plot scrolled by accident, or a selection made a while ago, then explains itself. y
fitted to the data in view (++y++) is not counted as a zoom: its button shows it.

## Selecting

With ++s++ (or the select button), a drag draws a brush, shaped as a zoom box is: x, y or
both. It selects the marks it meets in every panel, and the rest fade.

| What | Is selected when |
| --- | --- |
| a point | it is inside the brush |
| a line or area segment | either end is inside |
| a bar or rect | it overlaps the brush |
| a box | its body or lines are met |
| a histogram bin | it overlaps the brush |
| grey context (`facet="exclude"`), text, rules | never |

Drag the brush to move it; a click or ++esc++ clears it. With a legend colour (or a range
of a number colour) chosen too, a mark must meet both.

A colour shown alone (a double-click on its legend entry) is a way of looking, not a
selection: Python's `selection` doesn't change, and images saved from Python show every
colour.

## Export

The Export button (++e++) opens a menu. Each item makes an image of the plot as shown,
with its zoom, selection, opened panel and theme. The toolbar, the tooltip and what the
pointer points at are left out.

| Item | Makes |
| --- | --- |
| Copy image | a PNG on the clipboard, to paste into slides or a chat |
| Copy as vector | an SVG on the clipboard, with a PNG beside it for apps that don't read SVG (Chrome, Edge and VS Code) |
| Download PNG | a PNG file, twice the plot's size on screen |
| Download SVG | an SVG file: every mark, axis and label a vector element |
| Save PNG / SVG next to the notebook | the file in the folder Python runs in (in JupyterLab, VS Code and marimo) |

Copying needs a secure page (a notebook, `https://`, or a file opened from disk). A page
that JupyterLab opens in a new browser tab is sandboxed and can't download: open the HTML
file from disk instead. Files are named after the plot's title (and an opened panel), and
saving next to the notebook never overwrites: a second `Sales.png` becomes `Sales-2.png`.

## Full screen

The plot takes the screen's height, or with an `aspect` keeps its panels' shape as large
as fits ([size](../how-to/layout.md#size)). Browsers allow full screen only from a click
or a key, so not from Python. Where a page
forbids it (some notebook frames, Safari on iPhone) the button is not shown.
