# Link plots

`link(a, b, ...)` gives separate plots one selection: brush marks in one, and the others
show the same rows. Points and lines of those rows stay bright while the rest fade, a
histogram's bars fill to the share of their count that is selected, and a box lights up
when any of its rows is. This is often called crossfiltering.

The plots on this page are linked: brush in one (**s**, then drag) and watch the others.
In a notebook Python passes the selection from plot to plot; on a page saved with
[`save_html`](#save-linked-plots-to-one-page), the page does. The Python results below were
made when the page was built.

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

both = link(scatter, power)
scatter
print(both._embed_html())  # markdown-exec: hide
```

Brush the heaviest cars in the scatter (**s**, then drag): the histograms
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

by_country = link(years, lives, on="country")
years
print(by_country._embed_html())  # markdown-exec: hide
```

```python exec="on" source="above" result="python" session="link"
years.select(x=(7, 9), panel="1955")
print(sorted(lives.selected()["country"].unique()))
```

`link="country"` on `years` follows the brushed countries through its own panels;
`on="country"` shows the same countries in `lives`.

A plot reading a database a page at a time (`load="pages"`, see
[tables](tables.md#reading-a-page-at-a-time)) links with `on=` only: its rows are in the
database. Its selection is read as the keys chosen, and a selection elsewhere lights up
the rows of its pages read; its histograms fill to the share of the keys chosen, counted
by the database.

## Save linked plots to one page

`save_html` on the link writes its plots to one page, linked without Python: send it, put
it on a site, open it years later. Each mark carries the keys of its rows, and the page
highlights the marks whose keys a selection chooses, as Python would. `cols=2` puts the
plots side by side; a selection made in Python (`select()`) is saved with it.

```python
both = link(scatter, power)
scatter.select(x=(4000, 5200))
both.save_html("cars.html", cols=2)
html = both.to_html(title="Cars")  # the page as a string
```

Plots reading a database a page at a time are saved with every row, as `save_html` on one
of them does, so the page links them by their `on=` keys too. The page holds the keys of
every row once per plot: a few bytes a row beside the data it already has.

## Unlink

`link()` returns a `Link`. `unlink()` sets the plots apart again (each keeps its own
brush), and `clear()` clears the selection in all of them:

```python
connection = link(scatter, power)
connection.clear()
connection.unlink()
```

A plot is in one link at most. See [link and Link](../reference/link.md).
