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

    The bins are shared by every panel; `stat="percent"` or `"density"` scales each panel's
    counts.
    """)
    return


@app.cell
def _(Trellis, penguins):
    known = penguins.drop_nulls("sex")

    histograms = (
        Trellis(known, row="sex", col="species", panel_height=140)
        .hist(x="flipper_length_mm", binwidth=5)
    )
    histograms
    return (known,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `displot(kind="kde")`

    ```python
    sns.displot(data=penguins, x="bill_length_mm", hue="sex", col="species", kind="kde", fill=True)
    ```

    Each curve covers an area of 1, on x values every panel shares; `bw_adjust=` scales the
    bandwidth as in seaborn.
    """)
    return


@app.cell
def _(Trellis, known):
    bills = (
        Trellis(known, col="species", panel_height=220)
        .density(x="bill_length_mm", color="sex", fill=True)
    )
    bills
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `lmplot`

    ```python
    sns.lmplot(data=penguins, x="flipper_length_mm", y="body_mass_g", hue="sex", col="species")
    ```

    A least-squares line per colour in each panel, with its 95% confidence band.
    """)
    return


@app.cell
def _(Trellis, known):
    fits = (
        Trellis(known, col="species", panel_height=240)
        .points(x="flipper_length_mm", y="body_mass_g", color="sex", size=5)
        .smooth(x="flipper_length_mm", y="body_mass_g", color="sex", method="linear")
    )
    fits
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `catplot(kind="box")`

    ```python
    sns.catplot(data=penguins, x="species", y="body_mass_g", hue="sex", col="island", kind="box")
    ```

    The boxes of each colour side by side; the points beyond the whiskers are the outliers.
    """)
    return


@app.cell
def _(Trellis, known):
    masses = (
        Trellis(known, col="island", panel_height=240)
        .box(x="species", y="body_mass_g", color="sex")
    )
    masses
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
