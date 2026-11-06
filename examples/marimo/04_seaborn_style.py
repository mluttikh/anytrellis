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
    # seaborn style

    seaborn's figure-level functions (`relplot`, `displot`, `catplot`) and `FacetGrid` take
    `col=`, `row=`, `col_wrap=` and `hue=`; in anytrellis they are `col=`, `row=`,
    `wrap=` with `cols=`, and `color=`. `facet_kws={"sharey": False}` is `share_y=False`.

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
    ## `relplot`: scatter plots

    ```python
    sns.relplot(data=penguins, x="bill_length_mm", y="bill_depth_mm", hue="species", col="island")
    ```
    """)
    return


@app.cell
def _(Trellis, load):
    penguins = load("penguins")

    scatter = (
        Trellis(penguins, col="island", panel_height=240)
        .points(x="bill_length_mm", y="bill_depth_mm", color="species", size=6, tooltip=["sex"])
    )
    scatter
    return (penguins,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `relplot(kind="line")` with `col_wrap`

    ```python
    sns.relplot(data=weather, x="date", y="temp_max", col="year", col_wrap=2, kind="line",
                facet_kws={"sharex": False})
    ```

    Two layers here: the day's high and low. `share_x=False` gives each year its own dates.
    """)
    return


@app.cell
def _(Trellis, load, pl):
    weather = load("seattle_weather").with_columns(year=pl.col("date").dt.year())

    temperatures = (
        Trellis(weather, wrap="year", cols=2, share_x=False, title="Seattle temperatures",
                y_title="°C")
        .line(x="date", y="temp_max", color="#d62728", width=1, name="high")
        .line(x="date", y="temp_min", color="#1f77b4", width=1, name="low")
        .rule(y=0, color="#888888")
    )
    temperatures
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `FacetGrid` with histograms

    ```python
    g = sns.FacetGrid(penguins, row="sex", col="species")
    g.map(sns.histplot, "flipper_length_mm", binwidth=5)
    ```

    Bin the values (here with Polars), then draw the counts as bars a whole bin wide.
    """)
    return


@app.cell
def _(Trellis, penguins, pl):
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
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `catplot(kind="bar")`

    ```python
    sns.catplot(data=penguins, x="species", y="body_mass_g", hue="sex", col="island", kind="bar")
    ```

    seaborn computes the means (and confidence intervals) itself; here Polars computes the
    means, and `order()` puts the species in the same order in every panel.
    """)
    return


@app.cell
def _(Trellis, penguins, pl):
    means = penguins.drop_nulls("sex").group_by("island", "species", "sex").agg(
        body_mass_g=pl.col("body_mass_g").mean()
    )

    bars = (
        Trellis(means, col="island", panel_height=220)
        .order("species", ["Adelie", "Chinstrap", "Gentoo"])
        .bars(x="species", y="body_mass_g", color="sex", position="dodge")
    )
    bars
    return


if __name__ == "__main__":
    app.run()
