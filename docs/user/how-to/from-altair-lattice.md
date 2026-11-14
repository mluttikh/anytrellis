# Coming from Altair or lattice

The notebooks
[`05_vega_lite_style`](https://github.com/mluttikh/anytrellis/blob/main/examples/jupyter/05_vega_lite_style.ipynb)
and
[`02_lattice_and_cleveland`](https://github.com/mluttikh/anytrellis/blob/main/examples/jupyter/02_lattice_and_cleveland.ipynb)
redo well-known figures of both.

## Altair and Vega-Lite

Vega-Lite facets with the `row`, `column` and `facet` channels, and makes scales
independent with `resolve_scale`:

| Altair | anytrellis |
| --- | --- |
| `.facet(row="country")` | `Trellis(df, row="country")` |
| `.facet(column="island")` | `Trellis(df, col="island")` |
| `.facet(facet="year", columns=3)` | `Trellis(df, wrap="year", cols=3)` |
| `.resolve_scale(y="independent")` | `share_y=False` |
| `mark_point()`, `mark_line()`, `mark_bar()` | `.points()`, `.line()`, `.bars()` |
| `mark_area()`, `mark_rect()`, `mark_text()`, `mark_rule()` | `.area()`, `.rect()`, `.text()`, `.rule()` |
| `alt.Color("region")` | `color="region"` |
| `alt.Color("cylinders:N")`, `"cylinders:O"` | `.as_category("cylinders")`, then `color="cylinders"` |
| `alt.Tooltip(["country"])` | `tooltip=["country"]` |
| `alt.Scale(type="log")` | `y_scale="log"` |
| `alt.selection_interval()` | a brush: built in (**s**, then drag) |
| `alt.selection_point(fields=["region"], bind="legend")` | a legend click: built in |
| `.repeat(row=[...], column=[...])` of a scatter plot | `pairs(df, [...])` |

```python
alt.Chart(three).mark_point().encode(x="fertility", y="life_expect", color="region") \
    .facet(column="year")
```

```python exec="on" source="above" session="alt" html="true"
import polars as pl

from anytrellis import Trellis
from anytrellis.datasets import load

three = load("gapminder").filter(pl.col("year").is_in([1955, 1980, 2005]))
plot = Trellis(three, col="year", panel_height=240)
plot.points(x="fertility", y="life_expect", color="region", size=6, tooltip=["country"])
plot
print(plot._embed_html())  # markdown-exec: hide
```

What differs: Altair writes a chart's specification for Vega-Lite to draw; anytrellis
draws on the GPU in one canvas, so it stays smooth at millions of marks (Altair's default
limit is 5,000 rows), and its selection comes back to Python as rows (`selected()`).
Altair has many more kinds of chart and transforms.

## Cleveland and lattice

Trellis displays come from Becker, Cleveland and Shyu (1996), built into S-PLUS and later
R's lattice. Their rules are anytrellis's defaults: shared scales, axes only on the outer
panels, labels in strips over the panels, and panels ordered by what they show.

| lattice | anytrellis |
| --- | --- |
| `xyplot(y ~ x \| a)` | `Trellis(df, wrap="a").points(x="x", y="y")` |
| `xyplot(y ~ x \| a * b)` | `Trellis(df, row="a", col="b")` |
| `xyplot(y ~ x \| a * b * c)` (a page per level of `c`) | `Trellis(df, row="a", col="b", page="c")` |
| `groups = g` | `color="g"` |
| `layout = c(2, 3)` | `cols=2` |
| `type = c("p", "r")` | `.points()` and `.smooth(method="linear")` |
| `dotplot`, `bwplot`, `histogram`, `densityplot` | `.points()`, `.box()`, `.hist()`, `.density()` |
| `splom(~ df[1:4], groups = g)` | `pairs(df, ["a", "b", "c", "d"], color="g")` |
| `scales = list(y = "free")` | `share_y=False` |
| `scales = list(y = "sliced")` | `share_y="sliced"` |
| `index.cond`, `reorder()` | `.order(...)` |

Cleveland's barley data, as a dot plot with sites and varieties ordered by their median
yield:

```r
dotplot(variety ~ yield | site, data = barley, groups = year, layout = c(2, 3))
```

```python exec="on" source="above" session="alt" html="true"
barley = load("barley").with_columns(pl.col("year").cast(pl.String))
dots = (
    Trellis(barley, wrap="site", cols=2, panel_height=150, title="Barley yields at six sites",
            x_title="yield (bushels per acre)", y_title="")
    .order("site", by="median", of="yield", descending=True)
    .order("variety", by="median", of="yield")
    .points(x="yield", y="variety", color="year", size=7)
)
dots
print(dots._embed_html())  # markdown-exec: hide
```

Look at Morris: at every other site 1931 yielded more than 1932 for all but at most one
variety, and at Morris 1932 yielded more for all ten. Cleveland suspected that the two years had been swapped by mistake. Ordered
panels make it stand out.
