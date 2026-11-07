# Link plots

`link(a, b, ...)` gives separate plots one selection: brush marks in one, and the others
show the same rows. Points and lines of those rows stay bright while the rest fade, a
histogram's bars fill to the share of their count that is selected, and a box lights up
when any of its rows is. This is often called crossfiltering.

!!! note "Linking needs a running notebook"

    Python passes the selection from plot to plot, so plots are linked while the kernel
    runs: in JupyterLab, VS Code or marimo, not on this page or in a page from
    `save_html`. The plots below are live on their own; the Python results were made when
    the page was built. Run the
    [linked plots notebook](https://github.com/mluttikh/anytrellis/blob/main/examples/jupyter/07_linked_plots.ipynb)
    to try it.

## Plots of one table

Plots of the same table (the same object) select the same rows:

```python exec="on" source="above" session="link" html="true"
from anytrellis import Trellis, link
from anytrellis.datasets import load

cars = load("cars").drop_nulls(["mpg", "horsepower"])
scatter = Trellis(cars, panel_height=240, title="Weight and mileage")
scatter.points(x="weight", y="mpg", color="origin", size=5, tooltip=["name"])
power = Trellis(cars, wrap="origin", cols=3, panel_height=130, title="Horsepower")
power.hist(x="horsepower", binwidth=10)

link(scatter, power)
scatter
print(scatter._embed_html())  # markdown-exec: hide
print(power._embed_html())  # markdown-exec: hide
```

In a notebook, brush the heaviest cars in the scatter (**s**, then drag): the histograms
fill to the share of each bin those cars make up. A selection made in Python reaches the
other plots the same way, and `selected()` on any plot of the link gives the rows the
link's selection picks:

```python exec="on" source="above" result="python" session="link"
scatter.select(x=(4000, 5200))
print(power.selected().select("name", "horsepower", "weight").head())
```

A brush in another plot of the link replaces the first one, and a click or **Esc** in any
of them clears it. The brush updates the others as it moves.

## Plots of different tables: `on=`

A filtered copy, or a table of other things, is not the same table. Link it by a key
column with `on=`: selecting rows then selects every row sharing their key, in all the
linked plots.

```python exec="on" source="above" session="link" html="true"
gapminder = load("gapminder")
years = Trellis(gapminder, wrap="year", cols=6, panel_height=100, link="country",
                title="Fertility and life expectancy")
years.points(x="fertility", y="life_expect", color="region", size=4, tooltip=["country"])
lives = Trellis(gapminder, panel_height=220, title="Life expectancy")
lives.line(x="year", y="life_expect", color="region", group="country", tooltip=["country"])

link(years, lives, on="country")
years
print(years._embed_html())  # markdown-exec: hide
```

```python exec="on" source="above" result="python" session="link"
years.select(x=(7, 9), panel="1955")
print(sorted(lives.selected()["country"].unique()))
```

`link="country"` on `years` follows the brushed countries through its own panels;
`on="country"` shows the same countries in `lives`.

## Unlink

`link()` returns a `Link`. `unlink()` sets the plots apart again (each keeps its own
brush), and `clear()` clears the selection in all of them:

```python
connection = link(scatter, power)
connection.clear()
connection.unlink()
```

A plot is in one link at most. See [link and Link](../reference/link.md).
