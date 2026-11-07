# Why small multiples

A trellis plot draws the same plot once for each group of a table, side by side, on the
same scales. Edward Tufte called them *small multiples*; ggplot2 and seaborn call them
*facets*; Becker, Cleveland and Shyu called them *trellis displays* (1996), after the
lattice of panels.

## Comparing at a glance

Comparing groups in one plot means telling them apart by colour, and overlapping marks
hide each other. Separate plots with their own scales put each group in view, but every
comparison then needs reading the axes. Small multiples keep both: each group in its own
panel, and the same scales everywhere, so the eye compares positions directly. "Is this
panel higher than that one?" is answered by looking, not reading.

This works because the panels are the same plot: once you have read one, you have read
them all, and what differs between them is the data.

## Instead of an animation

An animation of fifty years shows one year at a time, and asks you to remember the
others. Fifty panels show every year at once:

```python exec="on" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

plot = Trellis(load("gapminder"), wrap="year", cols=6, panel_height=100)
plot.points(x="fertility", y="life_expect", color="region", size=4, tooltip=["country"])
print(plot._embed_html())
```

What the animation keeps is which dot is which country through time. Linked brushing
gives that back: with `link="country"`, a brush in one year follows the same countries in
every other ([Select data](../tutorials/select.md)).

## Cleveland's rules

Trellis displays came with rules that anytrellis follows by default:

- **Shared scales**, so panels compare; free ones only when the values differ too much.
- **Axes only on the outer panels**: inner axes would repeat the same ticks.
- **Labels in strips** over each panel, so the panel says what it is.
- **Panels ordered by what they show**, not alphabetically: by a median, for example.
  Ordered panels make the exception stand out, as in Cleveland's barley data, where one
  site's two years look swapped ([Altair and lattice](../how-to/from-altair-lattice.md)).

## Why interactive

A static trellis of fifty panels is small; zooming into one detail means a new plot.
anytrellis zooms all the panels that share a scale together, so a detail found in one
panel is compared in all of them at once, and a brushed range or a picked colour selects
the same thing in every panel.
