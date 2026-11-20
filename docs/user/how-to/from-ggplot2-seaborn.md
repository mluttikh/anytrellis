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
| `geom_bar()`, `stat_summary(geom = "bar")` | `.bars(x=..., stat="count")`, `.bars(stat="mean")` |
| `stat_ecdf()` | `.ecdf()` |
| `geom_area()`, `geom_ribbon()`, `geom_tile()`, `geom_text()` | `.area()`, `.band()`, `.rect()`, `.text()` |
| `geom_hline()`, `geom_vline()` | `.rule(y=...)`, `.rule(x=...)` |
| `ggrepel::geom_text_repel()` | `.text(..., repel=True)` |
| `directlabels::geom_dl(method = "last.points")`, `ggrepel` at the lines' ends | `.line(..., label="end")` |
| `annotate("text", x =, y =, label =)` | `.annotate("label", x=, y=)` (a panel, or every one) |
| `geom_histogram()`, `geom_boxplot()`, `geom_violin()`, `geom_density()` | `.hist()`, `.box()`, `.violin()`, `.density()` |
| `geom_errorbar()`, `geom_pointrange()`, `stat_summary()` | `.errorbar()` |
| `geom_step()` | `.line(step="post")` |
| `geom_smooth()`, `geom_smooth(method = "lm")` | `.smooth()`, `.smooth(method="linear")` |
| `aes(colour = g)`, `aes(group = g)` | `color="g"`, `group="g"` |
| `aes(shape = g)`, `aes(size = n)`, `aes(linetype = g)` | `.points(shape="g", size="n")`, `.line(dash="g")` |
| `aes(colour = factor(cyl))` | `.as_category("cyl")`, then `color="cyl"` |
| `scale_y_log10()` | `Trellis(..., y_scale="log")` |
| `position = "dodge"` | `.bars(position="dodge")` |
| `position = "fill"` | `.bars(position="fill")`, also `.area()`, `.hist()` |
| `geom_col()` with a discrete y, `coord_flip()` | `.bars(x="value", y="category")` |
| `geom_jitter()`, `sns.stripplot()` | `.points(x="category", y="value", jitter=0.4)` |
| `geom_hline(data = targets, aes(yintercept = target))` | `.rule(targets, y="target")` |
| `gghighlight()` | a layer with `facet="exclude"` |
| `fct_reorder(f, x, median)` | `.order("f", by="median", of="x")` |
| `labs(title =, subtitle =, caption =, x =, y =)` | `Trellis(..., title=, subtitle=, caption=, x_title=, y_title=)` |
| `labs(dictionary =)` (4.0) | `Trellis(..., labels={"mpg": "Fuel use (mpg)"})` |
| `scale_y_continuous(limits = c(0, NA))`, `coord_cartesian()` | `.limits(y=(0, None))` |
| `scale_x_continuous(labels = scales::label_comma())`, `scale_x_date(date_labels =)` | `.format(x=",.0f")`, `.format(x="%b %Y")` |
| `theme(legend.position = "right")`, `guides(colour = "none")` | `.legend("right")`, `.legend("none")` |
| `scale_colour_viridis_c(option = "cividis")`, `scale_colour_distiller(palette = "Blues")` | `.colormap("cividis")`, `.colormap("Blues")` |
| `scale_colour_gradient2(midpoint = 0)` | `.colormap(scale="diverging", midpoint=0)` |
| `scale_colour_binned()`, `scale_colour_viridis_b()` | `.colormap(scale="binned")` |
| `scale_colour_manual(values = c(USA = "red"))` | `Trellis(..., palette={"USA": "red"})` |

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

- **Columns by name**, not `aes()`: each mark takes `x=`, `y=` and `color=` (and
  `shape=`, `size=` or `dash=`) as column names.
- **Stats by name.** `bars()` draws the heights you give it, as `geom_col()`; with
  `stat="count"`, `"sum"`, `"mean"` or `"median"` it summarises the rows itself, as
  `geom_bar()` and `stat_summary()`. `hist()` counts in bins.
- **Two looks, no theme objects.** `theme="minimal"` (the default, close to
  `theme_minimal()`) or `theme="classic"` (close to `theme_grey()`); colours come from
  `palette=` and `color=`; the plot follows the notebook's light or dark theme.
- **Interactive**: every plot zooms, pans, brushes and hands its selection to Python.

## seaborn

seaborn's `relplot`, `displot`, `catplot`, `lmplot` and `FacetGrid` take `col=`, `row=`,
`col_wrap=` and `hue=`:

| seaborn | anytrellis |
| --- | --- |
| `col="a"`, `row="b"` | `col="a"`, `row="b"` |
| `col="a", col_wrap=3` | `wrap="a", cols=3` |
| `hue="g"` | `color="g"` |
| `style="g"`, `size="n"` | `.points(shape="g", size="n")`, `.line(dash="g")` |
| `facet_kws={"sharey": False}` | `share_y=False` |
| `relplot(kind="scatter")`, `relplot(kind="line")` | `.points()`, `.line()` |
| `displot(kind="hist")`, `displot(kind="kde")` | `.hist()`, `.density()` |
| `catplot(kind="box")`, `catplot(kind="bar")` | `.box()`, `.bars(stat="mean")` |
| `countplot()` | `.bars(x=..., stat="count")` |
| `ecdfplot()`, `displot(kind="ecdf")` | `.ecdf()` |
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

`catplot(kind="bar")` draws means with confidence intervals; with anytrellis, that is
two layers: `bars(x=..., y=..., stat="mean")` and `errorbar(x=..., y=...)` over them.
