# anytrellis

Trellis plots for Jupyter and marimo notebooks, drawn on the GPU. A trellis (also called
small multiples, or facets) draws the same plot once for each group of a table, on the same
scales, so you compare the groups at a glance. anytrellis draws every panel in one canvas,
so a grid of hundreds of panels and millions of marks stays smooth to zoom.

The plots on these pages are live: hover over a point, click a plot and scroll to zoom,
and drag to pan. Panels that share a scale zoom together.

```python exec="on" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

gapminder = load("gapminder")
plot = Trellis(
    gapminder,
    wrap="year",
    cols=4,
    panel_height=140,
    title="Fertility and life expectancy, 1955 to 2005",
)
plot.points(
    x="fertility",
    y="life_expect",
    color="region",
    size=5,
    tooltip=["country", "pop"],
)
print(plot._embed_html())
```

```python
from anytrellis import Trellis
from anytrellis.datasets import load

gapminder = load("gapminder")
plot = Trellis(gapminder, wrap="year", cols=4, title="Fertility and life expectancy")
plot.points(x="fertility", y="life_expect", color="region", tooltip=["country", "pop"])
plot
```

## What it does

- **Panels from your columns**: a wrap of one column's levels (`wrap=`), or a grid that
  crosses two (`row=`, `col=`) and keeps empty cells so rows and columns line up
  ([tutorial](tutorials/first-plot.md), [how to](how-to/layout.md)).
- **Scales you can compare**: shared by every panel by default, or per row, per column or
  free; linear or log ([tutorial](tutorials/facets-and-scales.md),
  [how to](how-to/scales.md)).
- **Layers**: lines, points, bars, areas, bands, rects, text and reference rules, and
  summaries computed per panel: histograms, box plots, densities and smooth fits
  ([how to](how-to/marks.md), [distributions](how-to/distributions.md)).
- **Interaction**: zoom and pan linked across panels, box zoom, fit y to the data in view,
  one panel at a time, full screen ([mouse and keys](reference/mouse-and-keys.md)).
- **Selection that reaches Python**: brush marks or click a legend entry, and
  `plot.selected()` gives the rows; plots linked with `link()` share one selection
  ([tutorial](tutorials/select.md), [how to](how-to/link.md)).
- **Any table**: Polars, pandas, PyArrow or a dict of columns
  ([how to](how-to/tables.md)).
- **Pages that open anywhere**: `save_html` writes the plot with its data into one HTML
  file that opens without Python ([how to](how-to/share.md)).

## Where to start

<div class="grid cards" markdown>

- **New to anytrellis?** Start with [Your first trellis plot](tutorials/first-plot.md):
  ten minutes, in a notebook.
- **Looking for a kind of plot?** The [gallery](gallery.md) shows each one, linked to the
  guide that makes it.
- **Know ggplot2, seaborn or Altair?** See how their facets translate:
  [ggplot2 and seaborn](how-to/from-ggplot2-seaborn.md),
  [Altair and lattice](how-to/from-altair-lattice.md).
- **Looking up an argument?** The [reference](reference/index.md) lists every method.

</div>

## Install

```bash
pip install anytrellis
```

anytrellis needs Python 3.12 or newer, and runs in JupyterLab, Jupyter Notebook, VS Code
and marimo. See [Install anytrellis](how-to/install.md).

The bundled datasets are credited in [anytrellis.datasets](reference/datasets.md); the
gapminder data is based on free material from [GAPMINDER.ORG](https://www.gapminder.org/),
CC-BY LICENSE.
