# Make a plot readable by everyone

A plot is drawn on canvases, which a screen reader can't read, and its colours may be
the only thing telling its series apart. anytrellis does three things about that.

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
- Everything the mouse does, the keys do too: the arrow keys move between panels, Enter
  opens one, and `?` lists the rest ([mouse and keys](../reference/mouse-and-keys.md)). The
  toolbar and legend are buttons with names.
- `label="end"` names lines at their ends, in their colour, so the legend's colours
  needn't be matched ([marks](marks.md)).
