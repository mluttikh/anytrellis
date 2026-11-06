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
    # Large data

    Marks are instances on the GPU: every panel is a viewport of one canvas, and zooming only
    changes a few numbers per panel. The data goes to the browser once, as binary buffers.
    WebGPU draws when the browser has it, else WebGL2, else Canvas 2D (fine for thousands of
    marks, slow for millions). `Trellis(..., renderer="webgl2")` picks one; the plot's
    bottom-right corner says which one draws.

    **Using a plot:** click it, then scroll to zoom along x (Shift+scroll: y), drag to pan, and
    press `r` to reset. Panels that share a scale zoom and pan together. Hover a mark for its
    values. Double-click a panel to see it alone (Page Up and Page Down: the next ones;
    Backspace: all again), and press `f` (or the toolbar's button) for full screen.
    """)
    return


@app.cell
def _():
    from anytrellis import Trellis
    from anytrellis.synthetic import scatter, sensors

    return Trellis, scatter, sensors


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## A million points in 16 panels
    """)
    return


@app.cell
def _(Trellis, scatter):
    million = scatter(n=1_000_000, groups=16)

    clusters = (
        Trellis(million, wrap="group", cols=4, panel_height=170, title="1,000,000 points")
        .points(x="x", y="y", color="cluster", size=1.5, opacity=0.3)
    )
    clusters
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## A year of hourly readings

    24 stations with 4 sensors each, hourly for a year: about 840,000 line segments. Zoomed
    out, the daily cycle fills a band and the seasons show; scroll in on a week and the days
    and the sensors come apart, still sharp.
    """)
    return


@app.cell
def _(Trellis, sensors):
    readings = sensors(stations=24, sensors=4, hours=24 * 365)

    year = (
        Trellis(readings, wrap="station", cols=4, panel_height=110, title="Hourly temperatures")
        .line(x="time", y="temp", color="sensor", width=0.8, opacity=0.7)
    )
    year
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Many panels

    A hundred small panels: a trellis scales to as many panels as fit on the screen.
    """)
    return


@app.cell
def _(Trellis, sensors):
    month = sensors(stations=100, sensors=2, hours=24 * 30)

    hundred = (
        Trellis(month, wrap="station", cols=10, panel_height=60, title="100 stations")
        .line(x="time", y="temp", color="sensor", width=1)
    )
    hundred
    return


if __name__ == "__main__":
    app.run()
