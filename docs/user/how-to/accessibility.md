# Make a plot readable by everyone

A plot is drawn on canvases, which a screen reader can't read, and its colours may be
the only thing telling its series apart. anytrellis does five things about that.

## A description, made for you

Every plot gets a sentence saying what it shows, made from what Python knows: its marks
and what they plot, its panels, what its colours stand for, its rows and the ranges of
its axes.

```python exec="on" source="above" session="a11y" result="text"
from anytrellis import Trellis
from anytrellis.datasets import load

cars = load("cars")
plot = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="cylinders")
print(plot.description)
```

In a notebook or a saved page the plot is a figure (`role="figure"`) with this sentence as
its label, so a screen reader says it when the plot gets the keys. An image saved with
`save_svg` has it as its `<title>` (as its `<desc>`, under the plot's title, when the
plot has one), as has one saved from the plot's menu.

What you want readers to take away is yours to say. `alt=` replaces the sentence:

```python
Trellis(cars, wrap="origin", alt="Heavier cars go fewer miles on a gallon, in every "
        "region; American cars are the heaviest.")
```

## The marks, one at a time, by the keys

Click the plot (or reach it with ++tab++), and the arrow keys move a ring between its
panels; ++enter++ opens one. In a panel opened, or in a plot of one panel, the arrow keys
step through its marks:

| Key | Goes to |
| --- | --- |
| ++left++ ++right++ | the previous or next mark along x (a line's every point) |
| ++up++ ++down++ | the nearest mark above or below: at the same x, the other series |
| ++home++ ++end++ | the first or last mark |
| ++esc++ | lets go of the mark (again: back to all panels) |

Each mark shows its tooltip, and a screen reader says it, with where the mark is among the
panel's ("Europe, weight 1825, mpg: 29.5. 1 of 70."). Lines coloured by a category say
every line's value at that x, as hovering shows them. A mark off the zoomed view brings the
view to it.

## The plot as a table

The toolbar's table button (or ++t++) shows the plot as HTML tables a screen reader can
move through: a row for each panel with its statistics (the rows, and the mean, median,
min, max, sd and trend of the values drawn: `stats()`), and the rows themselves, with the
columns the plot shows, when there are 500 or fewer. A panel's name opens it.

```python exec="on" source="above" session="a11y" result="python"
plot = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
print({name: values[:3] for name, values in plot.stats().items() if name in ("panel", "rows", "mean mpg")})
```

A plot reading a database a page at a time (`load="pages"`) lists the statistics the
database computes, and not its rows. A page from `save_html` has the table too.

## A second encoding: shapes and dashes

`redundant=True` gives a colour column's categories a shape each (points) and a dash each
(lines), so colour doesn't carry them alone: for readers who don't tell the colours apart,
and for a page printed in grey. One legend shows both.

```python exec="on" source="above" session="a11y" html="true"
penguins = load("penguins")
plot = Trellis(penguins, wrap="island", cols=3, panel_height=180, redundant=True)
plot.points(x="bill_length_mm", y="bill_depth_mm", color="species")
plot
print(plot._embed_html())  # markdown-exec: hide
```

A layer's own `shape=` or `dash=` wins, and a number colour keeps its colormap alone. To
have it in every plot of a session:

```python
import anytrellis as at

at.set_theme(redundant=True)
```

## Colours and keys

- The default palette (Petroff's ten colours, in the minimal theme) was chosen for readers
  with colour-vision deficiencies; `palette="okabe-ito"` is another such set.
- Everything the mouse does, the keys do too: the arrow keys move between panels and
  marks, Enter opens a panel, and `?` lists the rest ([mouse and
  keys](../reference/mouse-and-keys.md)). The toolbar and legend are buttons with names.
- Panels slide to their new places when sorted, filtered or opened; with the system's
  *reduced motion* setting they go there at once.
- `label="end"` names lines at their ends, in their colour, so the legend's colours
  needn't be matched ([marks](marks.md)).
