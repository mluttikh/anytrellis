# How scales are shared

A scale maps data values to positions. Sharing one across panels is what makes them
comparable: the same value is at the same place. anytrellis shares every scale by
default, and lets you free one per row, per column or per panel.

## What each choice compares

| Scales | You compare | You lose |
| --- | --- | --- |
| Shared | Levels across panels, at a glance | Detail in panels with small values |
| Free | Each panel's shape and change | Levels: the axes must be read |
| Sliced | Each panel's change, in the same units: a rise of 5 is as tall everywhere | Levels: the axes must be read |
| Shared per row or column | Levels along a row or a column | Levels across them |
| Log, shared | Ratios and growth rates across panels, at a glance | Differences in absolute terms |

A free scale is honest when each panel draws its own axis, and anytrellis does: wherever a
panel's scale differs from its neighbour's, it draws its own ticks.

## Zooming follows the sharing

A shared scale is one scale: zooming it in one panel zooms it in all the panels that share
it. A panel with a free scale zooms alone. In a grid with `share_y="row"`, zooming y in one
panel zooms its row. A sliced scale keeps every panel as wide: zooming one panel zooms all
of them to its width, each about its own centre, and panning moves one panel alone.

Fitting y to the data in view (**y**) fits each scale to the data of all its panels, so
panels that share y stay comparable while it fits. A sliced y fits each panel to its own
data, every one as wide as the widest.

## Why log scales are often better than free ones

Population, income or counts often differ between groups by orders of magnitude. Free
scales then make every panel look alike: each fills its own panel. A shared log scale
keeps the levels comparable *and* shows each group's change, because on a log scale a
doubling is the same distance at any size.

A log scale has no place for zero or below, so marks drawn from zero (bars, areas,
histograms, densities) don't go on a log y, and values of 0 or less are left out.

## Summaries follow the scale

`hist`, `density` and `smooth` are computed on the scale they are drawn on: on a log x, a
histogram's bins are equally wide on the log scale, as in ggplot2. Their bins and x values
are the same in every panel, so the summaries compare as the marks do.
