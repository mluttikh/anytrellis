"""Write the example notebooks: examples/jupyter/*.ipynb and examples/marimo/*.py.

The notebooks are written here once (markdown and code cells) and then converted to
marimo with ``marimo convert``, so both sets say the same. Each plot is built in one cell,
and no two cells define the same name: marimo needs both.

    uv run python scripts/build_examples.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUPYTER = ROOT / "examples" / "jupyter"
MARIMO = ROOT / "examples" / "marimo"

IMPORTS = """\
import polars as pl

from anytrellis import Trellis
from anytrellis.datasets import load"""

HOW_TO_USE = """\
**Using a plot:** click it, then scroll to zoom along x (Shift+scroll: y; over an axis:
that axis), drag to pan, Shift+drag to zoom to a box, `u` to undo and `r` to reset. Panels
that share a scale zoom and pan together. `y` keeps y fitted to the data in view. Hover a
mark for its values. Double-click a panel to see it alone (Page Up and Page Down: the next
ones; Backspace: all again), and press `f` (or the toolbar's button) for full screen."""

NOTEBOOKS: dict[str, list[tuple[str, str]]] = {}


def notebook(name: str, *cells: tuple[str, str]) -> None:
    NOTEBOOKS[name] = list(cells)


def md(text: str) -> tuple[str, str]:
    return ("markdown", text.strip("\n"))


def py(text: str) -> tuple[str, str]:
    return ("code", text.strip("\n"))


# ---- 01 -----------------------------------------------------------------------------------

notebook(
    "01_getting_started",
    md(
        """
# Getting started

A trellis (small multiples, facets) draws the same plot once per group of a table, on
scales that are the same everywhere, so the panels can be compared at a glance. With
anytrellis you say which columns split the table into panels (`wrap=`, or `row=` and
`col=`) and which layers each panel draws (`line`, `points`, `bars`, `rule`). Every panel
is drawn on the GPU in one canvas, so millions of marks stay smooth.

"""
        + HOW_TO_USE
    ),
    py(IMPORTS),
    py("""
cars = load("cars")
cars.head()
"""),
    md("""
## One panel per group: `wrap=`

`wrap=` makes a panel per level of a column and wraps them into rows (`cols=` sets how
many columns). A colour column with numbers is drawn along a colormap.
"""),
    py("""
by_origin = Trellis(cars, wrap="origin", title="Fuel use and weight, by origin")
by_origin.points(x="weight", y="mpg", color="cylinders", tooltip=["name", "year"])
"""),
    md("""
## Rows and columns: `row=` and `col=`

A grid crosses two columns: a row per level of one and a column per level of the other.
Every cell is kept, also those without data (there were no 3- or 5-cylinder cars from the
USA), so the rows and columns stay aligned.
"""),
    py("""
grid = Trellis(cars, row="origin", col="cylinders", panel_height=130)
grid.points(x="horsepower", y="mpg", size=4, tooltip=["name"])
"""),
    md("""
## Free scales

Shared scales make panels comparable; free scales show each panel's own detail.
`share_y=False` gives each panel its own y scale (`"row"` or `"col"`: one per row or
column of a grid). Zooming x still moves every panel: x is shared.
"""),
    py("""
stocks = load("stocks")
free = Trellis(stocks, row="symbol", share_y=False, panel_height=90, title="Monthly prices")
free.line(x="date", y="price")
"""),
    md("""
## Layers, context and reference lines

Each layer is drawn in every panel. `facet="exclude"` draws the *other* panels' rows in
grey behind each panel, so each stock is seen against the rest; `rule` draws a line at
fixed positions (here the day Lehman Brothers fell).
"""),
    py("""
layered = (
    Trellis(stocks, wrap="symbol", cols=3, title="Each stock against the others")
    .line(x="date", y="price", group="symbol", facet="exclude", width=1, name="others")
    .line(x="date", y="price", color="#1f77b4", width=2, name="price")
    .rule(x="2008-09-15", dash=[4, 3], color="#888888")
)
layered
"""),
    md("""
## Order

Panels, bands and colours are in alphabetical order unless told otherwise: `order()`
takes the levels in order, or ranks them by a summary of a column (`by="median"`,
`"mean"`, `"min"`, `"max"`, `"sum"` or `"count"`).
"""),
    py("""
ranked = (
    Trellis(cars, wrap="origin", cols=3, title="Origins by median fuel use")
    .order("origin", by="median", of="mpg", descending=True)
    .points(x="weight", y="mpg", size=4)
)
ranked
"""),
    md("""
## One panel at a time

Double-click a panel to see it alone on the whole plot, and step through the others with
Page Up and Page Down at the same zoom. From Python, `open()` does the same (by the
panel's name, see `panels()`), `close()` goes back, and `focused` says which panel the
plot shows, also when it was opened in the browser.
"""),
    py("""
ranked.panels()
"""),
    py("""
ranked.open("Japan")
ranked.focused
"""),
    md("""
## Sharing a plot

`save_html` writes a page with the data and the code inside it: it opens in any browser,
without Python, and keeps zooming and hovering.
"""),
    py("""
layered.save_html("stocks.html")
"""),
)

# ---- 02 -----------------------------------------------------------------------------------

notebook(
    "02_lattice_and_cleveland",
    md(
        """
# Trellis displays: lattice and Cleveland

Trellis displays come from Becker, Cleveland and Shyu (*The visual design and control of
trellis display*, 1996), built into S-PLUS and later R's **lattice**. Their rules are
anytrellis' defaults: shared scales, axes only on the outer panels, labels in strips over
the panels, and panels ordered by what they show rather than alphabetically.

"""
        + HOW_TO_USE
    ),
    py(IMPORTS),
    md("""
## Barley: a dot plot ordered by the median

The classic trellis display, from Cleveland's *Visualizing Data* (1993): barley yields of
ten varieties at six sites in Minnesota, in 1931 and 1932. In lattice:

```r
dotplot(variety ~ yield | site, data = barley, groups = year, layout = c(2, 3))
```

Sites and varieties are ordered by their median yield. Look at Morris: there, and only
there, 1932 beat 1931 for nearly every variety. Cleveland suggested the two years at Morris
had been swapped by mistake (later work found it may be real); either way, ordered panels
make it jump out.
"""),
    py("""
barley = load("barley").with_columns(pl.col("year").cast(pl.String))  # years as categories

dots = (
    Trellis(barley, wrap="site", cols=2, panel_height=160, title="Barley yields at six sites",
            x_title="yield (bushels per acre)", y_title="")
    .order("site", by="median", of="yield", descending=True)
    .order("variety", by="median", of="yield")
    .points(x="yield", y="variety", color="year", size=7)
)
dots
"""),
    md("""
## Anscombe's quartet

Four datasets with the same means, variances, correlation and least-squares line (1973),
and four very different pictures. Each panel draws its points and the line fitted to
them: a second table with the `dataset` column lands in its own panels.
"""),
    py("""
quartet = load("anscombe")
fitted = (
    quartet.group_by("dataset")
    .agg(slope=pl.cov("x", "y") / pl.col("x").var(), mx=pl.col("x").mean(), my=pl.col("y").mean())
    .join(pl.DataFrame({"x": [3.0, 20.0]}), how="cross")
    .with_columns(y=pl.col("my") + pl.col("slope") * (pl.col("x") - pl.col("mx")))
)

anscombe = (
    Trellis(quartet, wrap="dataset", title="Anscombe's quartet")
    .points(x="x", y="y", size=8)
    .line(fitted, x="x", y="y", color="#d62728", name="least squares")
)
anscombe
"""),
    md("""
## Conditioning on two variables

lattice's `xyplot(mpg ~ horsepower | cylinders * origin, groups = year)`: a grid
conditions on two columns. `share_x="col"` gives each column of the grid its own x scale.
"""),
    py("""
cars = load("cars").filter(pl.col("cylinders").is_in([4, 6, 8]))

conditioned = (
    Trellis(cars, row="origin", col="cylinders", panel_height=120,
            title="Fuel use and power, by cylinders and origin")
    .share(x="col")
    .points(x="horsepower", y="mpg", color="year", size=5, tooltip=["name"])
)
conditioned
"""),
    md("""
## Small multiples instead of an animation

Hans Rosling's famous animation of fertility against life expectancy, as one panel per
year: every year is on screen at once, on the same scales.
"""),
    py("""
gapminder = load("gapminder")

years = (
    Trellis(gapminder, wrap="year", cols=4, panel_height=150,
            title="Fertility and life expectancy, 1955-2005")
    .points(x="fertility", y="life_expect", color="region", size=6, tooltip=["country", "pop"])
)
years
"""),
)

# ---- 03 -----------------------------------------------------------------------------------

notebook(
    "03_ggplot2_style",
    md(
        """
# ggplot2 style

For those who know ggplot2's faceting:

| ggplot2                                  | anytrellis                                  |
|------------------------------------------|---------------------------------------------|
| `facet_wrap(~ a, ncol = 3)`              | `Trellis(df, wrap="a", cols=3)`             |
| `facet_grid(a ~ b)`                      | `Trellis(df, row="a", col="b")`             |
| `scales = "free_y"` / `"free"`           | `share_y=False` / `share_x=False, share_y=False` |
| `geom_point()`, `geom_line()`, `geom_col()` | `.points()`, `.line()`, `.bars()`        |
| `geom_hline()`, `geom_vline()`           | `.rule(y=...)`, `.rule(x=...)`              |
| `position = "dodge"`                     | `.bars(position="dodge")`                   |
| `gghighlight()`                          | a layer with `facet="exclude"`              |
| `fct_reorder(f, x, median)`              | `.order("f", by="median", of="x")`          |

"""
        + HOW_TO_USE
    ),
    py(IMPORTS),
    md("""
## `facet_wrap`

```r
ggplot(penguins, aes(flipper_length_mm, body_mass_g, colour = sex)) +
  geom_point() + facet_wrap(~ species)
```

Rows without a sex get a `(missing)` colour of their own.
"""),
    py("""
penguins = load("penguins")

wrapped = (
    Trellis(penguins, wrap="species", title="Palmer penguins")
    .points(x="flipper_length_mm", y="body_mass_g", color="sex", size=5, tooltip=["island"])
)
wrapped
"""),
    md("""
## `facet_grid`

```r
ggplot(drop_na(penguins, sex), aes(bill_length_mm, bill_depth_mm)) +
  geom_point() + facet_grid(sex ~ species)
```
"""),
    py("""
known = penguins.drop_nulls("sex")

crossed = (
    Trellis(known, row="sex", col="species", panel_height=160)
    .points(x="bill_length_mm", y="bill_depth_mm", color="island", size=5)
)
crossed
"""),
    md("""
## `gghighlight`: each group against the rest

```r
ggplot(gapminder, aes(year, life_expect, group = country, colour = region)) +
  geom_line() + gghighlight() + facet_wrap(~ region)
```

The grey layer (`facet="exclude"`) draws every other region's countries behind each
panel.
"""),
    py("""
gapminder = load("gapminder")

highlighted = (
    Trellis(gapminder, wrap="region", cols=3, title="Life expectancy, by region")
    .line(x="year", y="life_expect", group="country", facet="exclude", width=1, name="others")
    .line(x="year", y="life_expect", group="country", color="region", tooltip=["country"])
)
highlighted
"""),
    md("""
## `scales = "free_y"`

Population differs by orders of magnitude between regions: free y scales show each
region's trend (and the tick labels say how far apart they are).
"""),
    py("""
population = (
    Trellis(gapminder, wrap="region", cols=3, share_y=False, title="Population")
    .line(x="year", y="pop", group="country", width=1, tooltip=["country"])
)
population
"""),
    md("""
## `geom_col` with stacked categories

Days of each kind of weather in Seattle per month, a panel per year. The months and the
kinds of weather are put in order with `order()`, and `palette=` gives the kinds their
colours (in that order).
"""),
    py("""
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
kinds = ["sun", "fog", "drizzle", "rain", "snow"]

monthly = (
    load("seattle_weather")
    .group_by("weather", year=pl.col("date").dt.year(), month=pl.col("date").dt.strftime("%b"))
    .agg(days=pl.len())
)

stacked = (
    Trellis(monthly, wrap="year", cols=2, title="Seattle weather",
            palette=["#e7ba52", "#c7c7c7", "#aec7e8", "#1f77b4", "#9467bd"])
    .order("month", months)
    .order("weather", kinds)
    .bars(x="month", y="days", color="weather")
)
stacked
"""),
    md("""
## `position = "dodge"`

```r
penguins |> group_by(island, species, sex) |> summarise(mass = mean(body_mass_g)) |>
  ggplot(aes(species, mass, fill = sex)) + geom_col(position = "dodge") + facet_grid(~ island)
```
"""),
    py("""
mass = known.group_by("island", "species", "sex").agg(mass=pl.col("body_mass_g").mean())

dodged = (
    Trellis(mass, col="island", panel_height=220, title="Mean body mass", y_title="grams")
    .bars(x="species", y="mass", color="sex", position="dodge")
)
dodged
"""),
)

# ---- 04 -----------------------------------------------------------------------------------

notebook(
    "04_seaborn_style",
    md(
        """
# seaborn style

seaborn's figure-level functions (`relplot`, `displot`, `catplot`) and `FacetGrid` take
`col=`, `row=`, `col_wrap=` and `hue=`; in anytrellis they are `col=`, `row=`,
`wrap=` with `cols=`, and `color=`. `facet_kws={"sharey": False}` is `share_y=False`.

"""
        + HOW_TO_USE
    ),
    py(IMPORTS),
    md("""
## `relplot`: scatter plots

```python
sns.relplot(data=penguins, x="bill_length_mm", y="bill_depth_mm", hue="species", col="island")
```
"""),
    py("""
penguins = load("penguins")

scatter = (
    Trellis(penguins, col="island", panel_height=240)
    .points(x="bill_length_mm", y="bill_depth_mm", color="species", size=6, tooltip=["sex"])
)
scatter
"""),
    md("""
## `relplot(kind="line")` with `col_wrap`

```python
sns.relplot(data=weather, x="date", y="temp_max", col="year", col_wrap=2, kind="line",
            facet_kws={"sharex": False})
```

Two layers here: the day's high and low. `share_x=False` gives each year its own dates.
"""),
    py("""
weather = load("seattle_weather").with_columns(year=pl.col("date").dt.year())

temperatures = (
    Trellis(weather, wrap="year", cols=2, share_x=False, title="Seattle temperatures",
            y_title="°C")
    .line(x="date", y="temp_max", color="#d62728", width=1, name="high")
    .line(x="date", y="temp_min", color="#1f77b4", width=1, name="low")
    .rule(y=0, color="#888888")
)
temperatures
"""),
    md("""
## `FacetGrid` with histograms

```python
g = sns.FacetGrid(penguins, row="sex", col="species")
g.map(sns.histplot, "flipper_length_mm", binwidth=5)
```

Bin the values (here with Polars), then draw the counts as bars a whole bin wide.
"""),
    py("""
binned = (
    penguins.drop_nulls("sex")
    .with_columns(bin=(pl.col("flipper_length_mm") // 5) * 5 + 2.5)
    .group_by("sex", "species", "bin")
    .agg(count=pl.len())
)

histograms = (
    Trellis(binned, row="sex", col="species", panel_height=140, x_title="flipper length (mm)")
    .bars(x="bin", y="count", width=1.0)
)
histograms
"""),
    md("""
## `catplot(kind="bar")`

```python
sns.catplot(data=penguins, x="species", y="body_mass_g", hue="sex", col="island", kind="bar")
```

seaborn computes the means (and confidence intervals) itself; here Polars computes the
means, and `order()` puts the species in the same order in every panel.
"""),
    py("""
means = penguins.drop_nulls("sex").group_by("island", "species", "sex").agg(
    body_mass_g=pl.col("body_mass_g").mean()
)

bars = (
    Trellis(means, col="island", panel_height=220)
    .order("species", ["Adelie", "Chinstrap", "Gentoo"])
    .bars(x="species", y="body_mass_g", color="sex", position="dodge")
)
bars
"""),
)

# ---- 05 -----------------------------------------------------------------------------------

notebook(
    "05_vega_lite_style",
    md(
        """
# Vega-Lite and Altair style

Vega-Lite facets with `row`, `column` and `facet` (with `columns`) channels, and makes
scales independent with `resolve_scale`:

| Altair                                          | anytrellis                     |
|-------------------------------------------------|--------------------------------|
| `.facet(row="symbol")`                          | `row="symbol"`                 |
| `.facet(column="island")`                       | `col="island"`                 |
| `.facet(facet="year", columns=3)`               | `wrap="year", cols=3`          |
| `.resolve_scale(y="independent")`               | `share_y=False`                |
| `alt.Color("sex")`                              | `color="sex"`                  |

"""
        + HOW_TO_USE
    ),
    py(IMPORTS),
    md("""
## Rows with independent y scales

```python
alt.Chart(stocks).mark_line().encode(x="date:T", y="price:Q").facet(row="symbol") \\
    .resolve_scale(y="independent")
```
"""),
    py("""
stocks = load("stocks")

rows = (
    Trellis(stocks, row="symbol", share_y=False, panel_height=80)
    .line(x="date", y="price", color="symbol", tooltip=["symbol"])
)
rows
"""),
    md("""
## A trellis of grouped bars

The US population by age and sex, a panel per census (Vega-Lite's population example,
faceted).
"""),
    py("""
census = load("population").filter(pl.col("year").is_in([1900, 1930, 1960, 1990, 2000]))

pyramids = (
    Trellis(census, wrap="year", cols=2, panel_height=150, title="US population by age",
            palette=["#e377c2", "#1f77b4"])
    .order("sex", ["female", "male"])
    .bars(x="age", y="people", color="sex", position="dodge")
)
pyramids
"""),
    md("""
## Columns

```python
alt.Chart(gapminder).mark_point().encode(x="fertility", y="life_expect", color="region") \\
    .transform_filter(alt.FieldOneOfPredicate("year", [1955, 1980, 2005])).facet(column="year")
```
"""),
    py("""
three = load("gapminder").filter(pl.col("year").is_in([1955, 1980, 2005]))

columns = (
    Trellis(three, col="year", panel_height=260)
    .points(x="fertility", y="life_expect", color="region", size=7, tooltip=["country"])
)
columns
"""),
)

# ---- 06 -----------------------------------------------------------------------------------

notebook(
    "06_large_data",
    md(
        """
# Large data

Marks are instances on the GPU: every panel is a viewport of one canvas, and zooming only
changes a few numbers per panel. The data goes to the browser once, as binary buffers.
WebGPU draws when the browser has it, else WebGL2, else Canvas 2D (fine for thousands of
marks, slow for millions). `Trellis(..., renderer="webgl2")` picks one; the plot's
bottom-right corner says which one draws.

"""
        + HOW_TO_USE
    ),
    py("""
from anytrellis import Trellis
from anytrellis.synthetic import scatter, sensors
"""),
    md("""
## A million points in 16 panels
"""),
    py("""
million = scatter(n=1_000_000, groups=16)

clusters = (
    Trellis(million, wrap="group", cols=4, panel_height=170, title="1,000,000 points")
    .points(x="x", y="y", color="cluster", size=1.5, opacity=0.3)
)
clusters
"""),
    md("""
## A year of hourly readings

24 stations with 4 sensors each, hourly for a year: about 840,000 line segments. Zoomed
out, the daily cycle fills a band and the seasons show; scroll in on a week (or Shift+drag
across it) and the days and the sensors come apart, still sharp. `fit_y=True` keeps y
fitted to the week in view, the same for all panels, so they stay comparable.
"""),
    py("""
readings = sensors(stations=24, sensors=4, hours=24 * 365)

year = (
    Trellis(readings, wrap="station", cols=4, panel_height=110, fit_y=True,
            title="Hourly temperatures")
    .line(x="time", y="temp", color="sensor", width=0.8, opacity=0.7)
)
year
"""),
    md("""
## Many panels

A hundred small panels: a trellis scales to as many panels as fit on the screen.
"""),
    py("""
month = sensors(stations=100, sensors=2, hours=24 * 30)

hundred = (
    Trellis(month, wrap="station", cols=10, panel_height=60, title="100 stations")
    .line(x="time", y="temp", color="sensor", width=1)
)
hundred
"""),
)


# ---- writing ------------------------------------------------------------------------------


def ipynb(name: str, cells: list[tuple[str, str]]) -> dict:
    out = []
    for i, (kind, text) in enumerate(cells):
        lines = text.splitlines(keepends=True)
        cell: dict = {
            "cell_type": kind,
            "id": f"{name[:2]}-{i:02d}",
            "metadata": {},
            "source": lines,
        }
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        out.append(cell)
    return {
        "cells": out,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    JUPYTER.mkdir(parents=True, exist_ok=True)
    MARIMO.mkdir(parents=True, exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        nb = JUPYTER / f"{name}.ipynb"
        nb.write_text(json.dumps(ipynb(name, cells), indent=1, ensure_ascii=False) + "\n")
        mo = MARIMO / f"{name}.py"
        subprocess.run([sys.executable, "-m", "marimo", "convert", str(nb), "-o", str(mo)],
                       check=True, capture_output=True)  # fmt: skip
        print(f"{nb.relative_to(ROOT)}  {mo.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
