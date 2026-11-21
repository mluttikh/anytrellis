# Change a plot from its settings panel

You explore a plot by trying things: two columns instead of three, each panel's own y
scale, a log axis, another colour column, the panels by their median. Editing the cell and
running it again for each is slow. The settings panel does it in the plot, and gives back
the Python, so nothing done by hand is lost.

## Open it

The toolbar's settings button (or ++comma++) opens it. It offers what the plot has:

| Section | Setting | In Python |
| --- | --- | --- |
| Layout | Columns (a wrap) | `t.cols`, `Trellis(cols=)` |
| | Panel shape: auto, wide, 4:3, square, tall, banked to 45° (lines) | `t.aspect`, `Trellis(aspect=)` |
| Scales | Share x, share y: shared, free, per row or column (a grid), per page (paged), sliced | `t.share_x`, `t.share_y`, `share()` |
| | x scale, y scale (numbers): linear, log, square root, symlog | `t.x_scale`, `t.y_scale`, `scale()` |
| Data | Colour by: a column with a few categories, or numbers; none | `t.color` |
| | Order panels by: the median, mean, smallest or largest value of y (else x), the rows, or as the levels go | `order(..., by=, of=)` |

Each change draws the plot again, from Python. One the plot can't draw (bars on a log
axis) is refused with the reason, and the plot stays as it was.

A plot given `panel_height=` or `height=` has its panels' height set by it, and the panel
shape shows it (*200 px high*). Choosing a shape lets that height go: the shape sets the
panels' height from then on, and the code says `aspect=` instead. Setting `t.panel_height`
or `t.height` again takes over from the shape; the latest of the two decides.

## Read it back in Python

Every setting is the property or method of the same name, both ways: what the panel set,
Python reads, and what Python sets, the panel shows. `t.title`, `t.subtitle`, `t.caption`,
`t.height` and `t.panel_height` redraw a shown plot too, and are in its code.

```python exec="on" source="above" session="settings" result="text"
from anytrellis import Trellis
from anytrellis.datasets import load

cars = load("cars")
t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="cylinders")
t.share_y = "sliced"      # as the panel's "Share y: Sliced"
t.color = "origin"        # "Colour by: origin"
print(t.share_y, t.color)
```

## Copy as Python

The panel's *Copy as Python* puts the plot's code on the clipboard, and shows it.
`t.code()` returns the same: the calls that made the plot, with every change made since
in the panel, the page bar (sort, filters, pins) and on a panel (compare) written in.
A table is written as the name it has in the notebook.

```python exec="on" source="above" session="settings" result="text"
t.order("origin", by="median", of="mpg")
print(t.code())
```

Run, the code makes the same plot. A page saved with `save_html` keeps *Copy as Python*
(the plot as it was saved); its other settings need Python, so it leaves them out.

## Leave it out

`Trellis(..., controls=False)` removes the settings button, for a page to publish.

The panel changes the layout, the scales, the colour column and the order. Adding marks
or changing the data stays in code.
