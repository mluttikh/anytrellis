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
    | `.facet(row="symbol")`                          | `row="symbol"`                 |
    | `.facet(column="island")`                       | `col="island"`                 |
    | `.facet(facet="year", columns=3)`               | `wrap="year", cols=3`          |
    | `.resolve_scale(y="independent")`               | `share_y=False`                |
    | `alt.Color("sex")`                              | `color="sex"`                  |

    **Using a plot:** click it, then scroll to zoom along x (Shift+scroll: y), drag to pan, and
    press `r` to reset. Panels that share a scale zoom and pan together. Hover a mark for its
    values. Double-click a panel to see it alone (Page Up and Page Down: the next ones;
    Backspace: all again), and press `f` (or the toolbar's button) for full screen.
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
    alt.Chart(stocks).mark_line().encode(x="date:T", y="price:Q").facet(row="symbol") \
        .resolve_scale(y="independent")
    ```
    """)
    return


@app.cell
def _(Trellis, load):
    stocks = load("stocks")

    rows = (
        Trellis(stocks, row="symbol", share_y=False, panel_height=80)
        .line(x="date", y="price", color="symbol", tooltip=["symbol"])
    )
    rows
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## A trellis of grouped bars

    The US population by age and sex, a panel per census (Vega-Lite's population example,
    faceted).
    """)
    return


@app.cell
def _(Trellis, load, pl):
    census = load("population").filter(pl.col("year").is_in([1900, 1930, 1960, 1990, 2000]))

    pyramids = (
        Trellis(census, wrap="year", cols=2, panel_height=150, title="US population by age",
                palette=["#e377c2", "#1f77b4"])
        .order("sex", ["female", "male"])
        .bars(x="age", y="people", color="sex", position="dodge")
    )
    pyramids
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


if __name__ == "__main__":
    app.run()
