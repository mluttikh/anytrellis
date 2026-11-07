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
    # Vega-Lite and Altair style

    Vega-Lite facets with `row`, `column` and `facet` (with `columns`) channels, and makes
    scales independent with `resolve_scale`:

    | Altair                                          | anytrellis                     |
    |-------------------------------------------------|--------------------------------|
    | `.facet(row="country")`                         | `row="country"`                |
    | `.facet(column="island")`                       | `col="island"`                 |
    | `.facet(facet="year", columns=3)`               | `wrap="year", cols=3`          |
    | `.resolve_scale(y="independent")`               | `share_y=False`                |
    | `alt.Color("region")`                           | `color="region"`               |

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
    import polars as pl

    from anytrellis import Trellis
    from anytrellis.datasets import load

    return Trellis, load, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Rows with independent y scales

    ```python
    alt.Chart(five).mark_line().encode(x="year:Q", y="fertility:Q").facet(row="country") \
        .resolve_scale(y="independent")
    ```
    """)
    return


@app.cell
def _(Trellis, load, pl):
    gapminder = load("gapminder")
    five = gapminder.filter(
        pl.col("country").is_in(["China", "India", "Iran", "Italy", "United States"]))

    rows = (
        Trellis(five, row="country", share_y=False, panel_height=80)
        .line(x="year", y="fertility", color="country", tooltip=["country"])
    )
    rows
    return (five,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## A trellis of grouped bars

    Barley yields of ten varieties in 1931 and 1932, a panel per site (Vega-Lite's grouped
    bars, faceted). Morris is the odd one: at every other site 1931 yielded more, at Morris
    1932 did, for all ten varieties (Cleveland's famous suspicion: were its years swapped?).
    """)
    return


@app.cell
def _(Trellis, load, pl):
    barley = load("barley").with_columns(pl.col("year").cast(pl.String))

    grouped = (
        Trellis(barley, wrap="site", cols=2, panel_height=150, title="Barley yields")
        .bars(x="variety", y="yield", color="year", position="dodge")
    )
    grouped
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Columns

    ```python
    alt.Chart(gapminder).mark_point().encode(x="fertility", y="life_expect", color="region") \
        .transform_filter(alt.FieldOneOfPredicate("year", [1955, 1980, 2005])).facet(column="year")
    ```
    """)
    return


@app.cell
def _(Trellis, load, pl):
    three = load("gapminder").filter(pl.col("year").is_in([1955, 1980, 2005]))

    columns = (
        Trellis(three, col="year", panel_height=260)
        .points(x="fertility", y="life_expect", color="region", size=7, tooltip=["country"])
    )
    columns
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## A trellis of heatmaps

    ```python
    alt.Chart(weather).mark_rect() \
        .encode(x="date(date):O", y="month(date):O", color="max(temp_max)") \
        .facet(facet="year(date)", columns=2)
    ```

    `rect()` draws a cell per row, centred on x and y (`width=`/`height=` in data units, one by
    default); `x2=`/`y2=` give the corners instead.
    """)
    return


@app.cell
def _(Trellis, load, pl):
    daily = load("seattle_weather").with_columns(
        year=pl.col("date").dt.year(), month=pl.col("date").dt.month(), day=pl.col("date").dt.day()
    )

    heatmap = (
        Trellis(daily, wrap="year", cols=2, panel_height=150, title="Seattle: daily high (°C)")
        .rect(x="day", y="month", color="temp_max", tooltip=["date"])
    )
    heatmap
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Areas

    `mark_area` under `mark_line`, each country's population on its own y scale.
    """)
    return


@app.cell
def _(Trellis, five):
    filled = (
        Trellis(five, wrap="country", cols=3, share_y=False, title="Population")
        .area(x="year", y="pop", color="country", opacity=0.5)
        .line(x="year", y="pop", color="country", tooltip=["country"])
    )
    filled
    return


if __name__ == "__main__":
    app.run()
