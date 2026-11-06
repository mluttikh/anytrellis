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
    # Trellis displays: lattice and Cleveland

    Trellis displays come from Becker, Cleveland and Shyu (*The visual design and control of
    trellis display*, 1996), built into S-PLUS and later R's **lattice**. Their rules are
    anytrellis' defaults: shared scales, axes only on the outer panels, labels in strips over
    the panels, and panels ordered by what they show rather than alphabetically.

    **Using a plot:** click it, then scroll to zoom along x (Shift+scroll: y; over an axis:
    that axis), drag to pan, Shift+drag to zoom to a box, `u` to undo and `r` to reset. Panels
    that share a scale zoom and pan together. `y` keeps y fitted to the data in view, and `s`
    makes drag a brush that selects (Esc clears). Hover a mark for its values. Double-click a
    panel to see it alone (Page Up and Page Down: the next ones; Backspace: all again), and
    press `f` (or the toolbar's button) for full screen.
    """)
    return


@app.cell
def _():
    import polars as pl

    from anytrellis import Trellis
    from anytrellis.datasets import load

    return Trellis, load, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
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
    """)
    return


@app.cell
def _(Trellis, load, pl):
    barley = load("barley").with_columns(pl.col("year").cast(pl.String))  # years as categories

    dots = (
        Trellis(barley, wrap="site", cols=2, panel_height=160, title="Barley yields at six sites",
                x_title="yield (bushels per acre)", y_title="")
        .order("site", by="median", of="yield", descending=True)
        .order("variety", by="median", of="yield")
        .points(x="yield", y="variety", color="year", size=7)
    )
    dots
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Anscombe's quartet

    Four datasets with the same means, variances, correlation and least-squares line (1973),
    and four very different pictures. Each panel draws its points and the line fitted to
    them: a second table with the `dataset` column lands in its own panels.
    """)
    return


@app.cell
def _(Trellis, load, pl):
    quartet = load("anscombe")
    fitted = (
        quartet.group_by("dataset")
        .agg(
            slope=pl.cov("x", "y") / pl.col("x").var(),
            mx=pl.col("x").mean(),
            my=pl.col("y").mean(),
        )
        .join(pl.DataFrame({"x": [3.0, 20.0]}), how="cross")
        .with_columns(y=pl.col("my") + pl.col("slope") * (pl.col("x") - pl.col("mx")))
    )

    anscombe = (
        Trellis(quartet, wrap="dataset", title="Anscombe's quartet")
        .points(x="x", y="y", size=8)
        .line(fitted, x="x", y="y", color="#d62728", name="least squares")
    )
    anscombe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Conditioning on two variables

    lattice's `xyplot(mpg ~ horsepower | cylinders * origin, groups = year)`: a grid
    conditions on two columns. `share_x="col"` gives each column of the grid its own x scale.
    """)
    return


@app.cell
def _(Trellis, load, pl):
    cars = load("cars").filter(pl.col("cylinders").is_in([4, 6, 8]))

    conditioned = (
        Trellis(cars, row="origin", col="cylinders", panel_height=120,
                title="Fuel use and power, by cylinders and origin")
        .share(x="col")
        .points(x="horsepower", y="mpg", color="year", size=5, tooltip=["name"])
    )
    conditioned
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Small multiples instead of an animation

    Hans Rosling's famous animation of fertility against life expectancy, as one panel per
    year: every year is on screen at once, on the same scales.
    """)
    return


@app.cell
def _(Trellis, load):
    gapminder = load("gapminder")

    years = (
        Trellis(gapminder, wrap="year", cols=4, panel_height=150,
                title="Fertility and life expectancy, 1955-2005")
        .points(x="fertility", y="life_expect", color="region", size=6, tooltip=["country", "pop"])
    )
    years
    return (gapminder,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Following countries: brushing with `link`

    Small multiples lose what the animation had: which dot is which country over time. Linked
    brushing brings it back. With `link="country"`, a brush selects in the panel you draw it
    in and then every row of the same countries, in all panels; the rest fade. Press `s` (or
    the toolbar's select button) and drag a brush in 1955: the countries that had fewer than
    three children per woman then, followed through fifty years. Drag the brush to move it, a
    click or Esc clears it.

    From Python, `select()` does the same, and `selected()` gives the rows, also of a brush
    drawn in the browser.
    """)
    return


@app.cell
def _(Trellis, gapminder):
    followed = (
        Trellis(gapminder, wrap="year", cols=4, panel_height=150, link="country",
                title="Fewer than three children per woman in 1955: where they went")
        .points(x="fertility", y="life_expect", color="region", size=6, tooltip=["country"])
        .select(x=(0, 3), panel="1955")
    )
    followed
    return (followed,)


@app.cell
def _(followed):
    followed.selected()["country"].unique().sort().to_list()
    return


if __name__ == "__main__":
    app.run()
