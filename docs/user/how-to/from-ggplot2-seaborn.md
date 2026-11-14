# Coming from ggplot2 or seaborn

anytrellis builds a plot as ggplot2 does, a layer at a time, and names its facets as
seaborn's figure-level functions do. The notebooks
[`03_ggplot2_style`](https://github.com/mluttikh/anytrellis/blob/main/examples/jupyter/03_ggplot2_style.ipynb)
and
[`04_seaborn_style`](https://github.com/mluttikh/anytrellis/blob/main/examples/jupyter/04_seaborn_style.ipynb)
redo well-known figures of both.

## ggplot2

| ggplot2 | anytrellis |
| --- | --- |
| `facet_wrap(~ a, ncol = 3)` | `Trellis(df, wrap="a", cols=3)` |
| `facet_grid(a ~ b)` | `Trellis(df, row="a", col="b")` |
| `facet_grid(a ~ b, margins = TRUE)` | `Trellis(df, row="a", col="b", margins=True)` |
| `scales = "free_y"` / `"free"` | `share_y=False` / `share_x=False, share_y=False` |
| `geom_point()`, `geom_line()`, `geom_col()` | `.points()`, `.line()`, `.bars()` |
| `geom_area()`, `geom_ribbon()`, `geom_tile()`, `geom_text()` | `.area()`, `.band()`, `.rect()`, `.text()` |
| `geom_hline()`, `geom_vline()` | `.rule(y=...)`, `.rule(x=...)` |
| `geom_histogram()`, `geom_boxplot()`, `geom_violin()`, `geom_density()` | `.hist()`, `.box()`, `.violin()`, `.density()` |
| `geom_errorbar()`, `geom_pointrange()`, `stat_summary()` | `.errorbar()` |
| `geom_step()` | `.line(step="post")` |
| `geom_smooth()`, `geom_smooth(method = "lm")` | `.smooth()`, `.smooth(method="linear")` |
| `aes(colour = g)`, `aes(group = g)` | `color="g"`, `group="g"` |
| `aes(colour = factor(cyl))` | `.as_category("cyl")`, then `color="cyl"` |
| `scale_y_log10()` | `Trellis(..., y_scale="log")` |
| `position = "dodge"` | `.bars(position="dodge")` |
| `gghighlight()` | a layer with `facet="exclude"` |
| `fct_reorder(f, x, median)` | `.order("f", by="median", of="x")` |
| `labs(title =, x =, y =)` | `Trellis(..., title=, x_title=, y_title=)` |

```r
ggplot(penguins, aes(flipper_length_mm, body_mass_g, colour = sex)) +
  geom_point() + facet_wrap(~ species)
```

```python exec="on" source="above" session="gg" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

penguins = load("penguins")
plot = Trellis(penguins, wrap="species", panel_height=170)
plot.points(x="flipper_length_mm", y="body_mass_g", color="sex")
plot
print(plot._embed_html())  # markdown-exec: hide
```

What differs:

- **Columns by name**, not `aes()`: each mark takes `x=`, `y=` and `color=` as column
  names.
- **No stats on plain marks.** `bars()` draws the heights you give it; `hist()` counts.
  Summarise with your table library first, as for `geom_col()`.
- **No themes or scales objects.** Colours come from `palette=` and `color=`; the plot
  follows the notebook's light or dark theme.
- **Interactive**: every plot zooms, pans, brushes and hands its selection to Python.

## seaborn

seaborn's `relplot`, `displot`, `catplot`, `lmplot` and `FacetGrid` take `col=`, `row=`,
`col_wrap=` and `hue=`:

| seaborn | anytrellis |
| --- | --- |
| `col="a"`, `row="b"` | `col="a"`, `row="b"` |
| `col="a", col_wrap=3` | `wrap="a", cols=3` |
| `hue="g"` | `color="g"` |
| `facet_kws={"sharey": False}` | `share_y=False` |
| `relplot(kind="scatter")`, `relplot(kind="line")` | `.points()`, `.line()` |
| `displot(kind="hist")`, `displot(kind="kde")` | `.hist()`, `.density()` |
| `catplot(kind="box")`, `catplot(kind="bar")` | `.box()`, `.bars()` (of means you compute) |
| `catplot(kind="violin")` | `.violin()` |
| `catplot(kind="point")`, `pointplot(errorbar="ci")` | `.errorbar()`, `.errorbar(extent="ci")` |
| `lineplot(drawstyle="steps-post")` | `.line(step="post")` |
| `pairplot(df, hue="g")`, `pairplot(corner=True)` | `pairs(df, color="g")`, `pairs(df, corner=True)` |
| `lmplot` | `.points()` and `.smooth(method="linear")` |
| `bw_adjust=` | `bw_adjust=` |

```python
sns.lmplot(data=penguins, x="flipper_length_mm", y="body_mass_g", hue="sex", col="species")
```

```python exec="on" source="above" session="gg" html="true"
known = penguins.drop_nulls("sex")
plot = (
    Trellis(known, col="species", panel_height=220)
    .points(x="flipper_length_mm", y="body_mass_g", color="sex", size=5)
    .smooth(x="flipper_length_mm", y="body_mass_g", color="sex", method="linear")
)
plot
print(plot._embed_html())  # markdown-exec: hide
```

`catplot(kind="bar")` computes means and confidence intervals itself; with anytrellis,
compute the means with Polars or pandas and draw them with `bars()`.
