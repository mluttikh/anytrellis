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
    # Getting started

    A trellis (small multiples, facets) draws the same plot once per group of a table, on
    scales that are the same everywhere, so the panels can be compared at a glance. With
    anytrellis you say which columns split the table into panels (`wrap=`, or `row=` and
    `col=`) and which layers each panel draws (`line`, `points`, `bars`, `hist`, `box`, ...).
    Every panel is drawn on the GPU in one canvas, so millions of marks stay smooth.

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
    from anytrellis import Trellis
    from anytrellis.datasets import load

    return Trellis, load


@app.cell
def _(load):
    cars = load("cars")
    cars.head()
    return (cars,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## One panel per group: `wrap=`

    `wrap=` makes a panel per level of a column and wraps them into rows (`cols=` sets how
    many columns). A colour column with numbers is drawn along a colormap.
    """)
    return


@app.cell
def _(Trellis, cars):
    by_origin = Trellis(cars, wrap="origin", title="Fuel use and weight, by origin")
    by_origin.points(x="weight", y="mpg", color="cylinders", tooltip=["name", "year"])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Rows and columns: `row=` and `col=`

    A grid crosses two columns: a row per level of one and a column per level of the other.
    Every cell is kept, also those without data (there were no 3- or 5-cylinder cars from the
    USA), so the rows and columns stay aligned.
    """)
    return


@app.cell
def _(Trellis, cars):
    grid = Trellis(cars, row="origin", col="cylinders", panel_height=130)
    grid.points(x="horsepower", y="mpg", size=4, tooltip=["name"])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Free scales

    Shared scales make panels comparable; free scales show each panel's own detail.
    `share_y=False` gives each panel its own y scale (`"row"` or `"col"`: one per row or
    column of a grid). Zooming x still moves every panel: x is shared. Here: countries whose
    populations differ a thousandfold, each growing in its own way.
    """)
    return


@app.cell
def _(Trellis, load):
    gapminder = load("gapminder")
    six = gapminder.filter(gapminder["country"].is_in(
        ["China", "India", "United States", "Nigeria", "Japan", "Iceland"]))
    free = Trellis(six, row="country", share_y=False, panel_height=90, title="Population")
    free.line(x="year", y="pop")
    return (six,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Layers, context and reference lines

    Each layer is drawn in every panel. `facet="exclude"` draws the *other* panels' rows in
    grey behind each panel, so each country is seen against the rest; `rule` draws a line at
    fixed positions (here a life expectancy of 70 years).
    """)
    return


@app.cell
def _(Trellis, six):
    layered = (
        Trellis(six, wrap="country", cols=3, title="Each country against the others")
        .line(x="year", y="life_expect", group="country", facet="exclude", width=1, name="others")
        .line(x="year", y="life_expect", color="#1f77b4", width=2, name="life expectancy")
        .rule(y=70, dash=[4, 3], color="#888888")
    )
    layered
    return (layered,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Order

    Panels, bands and colours are in alphabetical order unless told otherwise: `order()`
    takes the levels in order, or ranks them by a summary of a column (`by="median"`,
    `"mean"`, `"min"`, `"max"`, `"sum"` or `"count"`).
    """)
    return


@app.cell
def _(Trellis, cars):
    ranked = (
        Trellis(cars, wrap="origin", cols=3, title="Origins by median fuel use")
        .order("origin", by="median", of="mpg", descending=True)
        .points(x="weight", y="mpg", size=4)
    )
    ranked
    return (ranked,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## One panel at a time

    Double-click a panel to see it alone on the whole plot, and step through the others with
    Page Up and Page Down at the same zoom. From Python, `open()` does the same (by the
    panel's name, see `panels()`), `close()` goes back, and `focused` says which panel the
    plot shows, also when it was opened in the browser.
    """)
    return


@app.cell
def _(ranked):
    ranked.panels()
    return


@app.cell
def _(ranked):
    ranked.open("Japan")
    ranked.focused
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Sharing a plot

    `save_html` writes a page with the data and the code inside it: it opens in any browser,
    without Python, and keeps zooming and hovering.
    """)
    return


@app.cell
def _(layered):
    layered.save_html("life_expectancy.html")
    return


if __name__ == "__main__":
    app.run()
