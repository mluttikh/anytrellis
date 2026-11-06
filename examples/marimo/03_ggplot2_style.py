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
    ## `facet_wrap`

    ```r
    ggplot(penguins, aes(flipper_length_mm, body_mass_g, colour = sex)) +
      geom_point() + facet_wrap(~ species)
    ```

    Rows without a sex get a `(missing)` colour of their own.
    """)
    return


@app.cell
def _(Trellis, load):
    penguins = load("penguins")

    wrapped = (
        Trellis(penguins, wrap="species", title="Palmer penguins")
        .points(x="flipper_length_mm", y="body_mass_g", color="sex", size=5, tooltip=["island"])
    )
    wrapped
    return (penguins,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `facet_grid`

    ```r
    ggplot(drop_na(penguins, sex), aes(bill_length_mm, bill_depth_mm)) +
      geom_point() + facet_grid(sex ~ species)
    ```
    """)
    return


@app.cell
def _(Trellis, penguins):
    known = penguins.drop_nulls("sex")

    crossed = (
        Trellis(known, row="sex", col="species", panel_height=160)
        .points(x="bill_length_mm", y="bill_depth_mm", color="island", size=5)
    )
    crossed
    return (known,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `gghighlight`: each group against the rest

    ```r
    ggplot(gapminder, aes(year, life_expect, group = country, colour = region)) +
      geom_line() + gghighlight() + facet_wrap(~ region)
    ```

    The grey layer (`facet="exclude"`) draws every other region's countries behind each
    panel.
    """)
    return


@app.cell
def _(Trellis, load):
    gapminder = load("gapminder")

    highlighted = (
        Trellis(gapminder, wrap="region", cols=3, title="Life expectancy, by region")
        .line(x="year", y="life_expect", group="country", facet="exclude", width=1, name="others")
        .line(x="year", y="life_expect", group="country", color="region", tooltip=["country"])
    )
    highlighted
    return (gapminder,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `scales = "free_y"`

    Population differs by orders of magnitude between regions: free y scales show each
    region's trend (and the tick labels say how far apart they are).
    """)
    return


@app.cell
def _(Trellis, gapminder):
    population = (
        Trellis(gapminder, wrap="region", cols=3, share_y=False, title="Population")
        .line(x="year", y="pop", group="country", width=1, tooltip=["country"])
    )
    population
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `geom_col` with stacked categories

    Days of each kind of weather in Seattle per month, a panel per year. The months and the
    kinds of weather are put in order with `order()`, and `palette=` gives the kinds their
    colours (in that order).
    """)
    return


@app.cell
def _(Trellis, load, pl):
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
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `position = "dodge"`

    ```r
    penguins |> group_by(island, species, sex) |> summarise(mass = mean(body_mass_g)) |>
      ggplot(aes(species, mass, fill = sex)) + geom_col(position = "dodge") + facet_grid(~ island)
    ```
    """)
    return


@app.cell
def _(Trellis, known, pl):
    mass = known.group_by("island", "species", "sex").agg(mass=pl.col("body_mass_g").mean())

    dodged = (
        Trellis(mass, col="island", panel_height=220, title="Mean body mass", y_title="grams")
        .bars(x="species", y="mass", color="sex", position="dodge")
    )
    dodged
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `geom_area`

    ```r
    ggplot(population, aes(year, people, fill = age, group = age)) + geom_area() + facet_wrap(~ sex)
    ```

    Areas stack like bars do (`position="identity"` overlaps them instead); a number column as
    the colour gets a continuous scale.
    """)
    return


@app.cell
def _(Trellis, load):
    by_age = load("population")

    ages = (
        Trellis(by_age, wrap="sex", title="US population by age group")
        .area(x="year", y="people", color="age", group="age", tooltip=["age"])
    )
    ages
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `geom_text`

    ```r
    ggplot(eight, aes(fertility, life_expect, label = country)) + geom_point(aes(colour = region)) +
      geom_text(hjust = 0, nudge_x = 0.1) + facet_wrap(~ year)
    ```

    `dx=` and `dy=` move labels by pixels, so they keep their distance while zooming; a label
    that would run past the panel's edge goes to the other side of its point.
    """)
    return


@app.cell
def _(Trellis, gapminder, pl):
    eight = gapminder.filter(
        pl.col("year").is_in([1955, 2005])
        & pl.col("country").is_in(["China", "India", "Japan", "Netherlands", "Brazil", "Nigeria",
                                   "United States", "Egypt"])
    )

    labelled = (
        Trellis(eight, wrap="year", title="Eight countries, 1955 and 2005")
        .points(x="fertility", y="life_expect", color="region", size=7)
        .text(x="fertility", y="life_expect", text="country", align="left", dx=6)
    )
    labelled
    return


if __name__ == "__main__":
    app.run()
