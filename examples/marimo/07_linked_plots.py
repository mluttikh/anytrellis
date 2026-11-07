import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Linked plots

    `link(a, b, ...)` gives plots one selection: brush marks in one plot (`s`, then drag) and
    the other plots show the same rows. Points and lines of those rows stay bright while the
    rest fade; a histogram's bars fill to the share of their count that is selected; a box
    lights up when any of its rows is selected. Dragging the brush updates the others as it
    moves (crossfiltering). A brush drawn in another plot of the link replaces the first one,
    and a click or Esc in any of them clears the selection.

    Python relays the selection, so the plots stay linked while the kernel runs. `selected()`
    on any of them gives the rows the selection picks.

    **Using a plot:** click it, then scroll to zoom along x (Shift+scroll: y; over an axis:
    that axis), drag to pan, Shift+drag to zoom to a box, `u` to undo and `r` to reset. Panels
    that share a scale zoom and pan together. `y` keeps y fitted to the data in view, and `s`
    makes drag a brush that selects (Esc clears); a click on a legend entry selects its colour
    (Shift+click: more). Hover a mark for its values. Double-click a panel to see it alone
    (Page Up and Page Down: the next ones; Backspace: all again), and press `f` (or the
    toolbar's button) for full screen.
    """)
    return


@app.cell
def _():
    from anytrellis import Trellis, link
    from anytrellis.datasets import load

    return Trellis, link, load


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Crossfilter: one table, three plots

    Plots of the same table (the same object) select the same rows. Brush the heavy cars in
    the scatter: the histogram shows how much of each horsepower bin they make up, and the
    boxes show which cylinder counts they have.
    """)
    return


@app.cell
def _(Trellis, link, load):
    cars = load("cars").drop_nulls(["mpg", "horsepower"])

    scatter = (
        Trellis(cars, panel_height=260, title="Weight and mileage")
        .points(x="weight", y="mpg", color="origin", size=5, tooltip=["name"])
    )
    power = (
        Trellis(cars, wrap="origin", cols=3, panel_height=140, title="Horsepower by origin")
        .hist(x="horsepower", binwidth=10)
    )
    mileage = (
        Trellis(cars, panel_height=200, title="Mileage by cylinders")
        .box(x="cylinders", y="mpg")
    )

    link(scatter, power, mileage)
    scatter
    return mileage, power, scatter


@app.cell
def _(power):
    power
    return


@app.cell
def _(mileage):
    mileage
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Brush in any of them. In Python, each plot gives the selected rows:
    """)
    return


@app.cell
def _(mileage, scatter):
    scatter.select(x=(4000, 5200))  # the same as a brush over the heaviest cars
    mileage.selected().select("name", "cylinders", "mpg").head()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Linked by a key: `on=`

    With `on="country"`, a selection picks every row sharing a selected row's country, in all
    the linked plots. Brush a few countries with high fertility in 1955: `link="country"`
    follows them through the years of the first plot, and `on="country"` shows their life
    expectancy over fifty years in the second.
    """)
    return


@app.cell
def _(Trellis, link, load):
    gapminder = load("gapminder")

    years = (
        Trellis(gapminder, wrap="year", cols=6, panel_height=110, link="country",
                title="Fertility and life expectancy")
        .points(x="fertility", y="life_expect", color="region", size=4, tooltip=["country"])
    )
    lives = (
        Trellis(gapminder, panel_height=240, title="Life expectancy")
        .line(x="year", y="life_expect", color="region", group="country", tooltip=["country"])
    )

    link(years, lives, on="country")
    years
    return (lives,)


@app.cell
def _(lives):
    lives
    return


if __name__ == "__main__":
    app.run()
