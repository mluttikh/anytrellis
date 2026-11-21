"""Write the save_html pages the browser checks run on: ``uv run python js/test/pages.py
<dir>``, then ``node js/test/select.mjs <dir>/years.html`` (and legend.mjs, zoom.mjs,
many.mjs, details.mjs, paging.mjs, levels.mjs, reverse.mjs, tooltip.mjs, legends.mjs,
channels.mjs, labels.mjs, panels.mjs, settings.mjs, marks.mjs, layout.mjs, lasso.mjs,
savedlink.mjs, views.mjs)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

import anytrellis
from anytrellis import Trellis
from anytrellis.datasets import load
from anytrellis.synthetic import sensors


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    gapminder = load("gapminder")
    years = Trellis(gapminder, wrap="year", cols=4, panel_height=150,
                    title="Fertility and life expectancy, 1955-2005")  # fmt: skip
    years.points(x="fertility", y="life_expect", color="region", size=6,
                 tooltip=["country", "pop"])  # fmt: skip
    years.save_html(out / "years.html")
    # reversed axes (reverse.mjs): x high to low, y a sqrt scale high at the bottom
    flipped = Trellis(gapminder, wrap="year", cols=4, panel_height=150, x_scale="reverse",
                      y_scale=("sqrt", "reverse"))  # fmt: skip
    flipped.points(x="fertility", y="pop", color="region", size=6, tooltip=["country"])
    flipped.save_html(out / "reversed.html")
    labelled = Trellis(gapminder, wrap="year", cols=4, panel_height=150,
                       title="Fertility and life expectancy, 1955-2005",
                       subtitle="Each point is a country, five years apart. As families got "
                       "smaller, people lived longer, in every region, and the regions drew "
                       "closer together over the fifty years. Brush a panel to follow its "
                       "countries through the others.",
                       caption="Source: Gapminder",
                       labels={"fertility": "Children per woman", "life_expect": "Life expectancy",
                               "region": "Region"})  # fmt: skip
    labelled.points(x="fertility", y="life_expect", color="region", size=6)
    labelled.save_html(out / "labelled.html")
    right = Trellis(gapminder, wrap="year", cols=4, panel_height=150,
                    title="Fertility and life expectancy, 1955-2005")  # fmt: skip
    right.points(x="fertility", y="life_expect", color="region", size=6, tooltip=["country"])
    right.legend("right").format(y=".0f").limits(y=(20, 90))
    right.save_html(out / "legend-right.html")
    # legends (legends.mjs): a number colour's gradient, a stepped scale's bins, and a long
    # legend over the panels
    number = Trellis(gapminder, wrap="year", cols=4, panel_height=150)
    number.points(x="fertility", y="life_expect", color="life_expect", size=6)
    number.save_html(out / "legend-number.html")
    bins = Trellis(gapminder, wrap="year", cols=4, panel_height=150)
    bins.points(x="fertility", y="life_expect", color="life_expect", size=6)
    bins.colormap(scale="binned", bins=5).save_html(out / "legend-bins.html")
    countries = gapminder["country"].unique(maintain_order=True).head(30).to_list()
    many = Trellis(gapminder.filter(pl.col("country").is_in(countries)), wrap="region", cols=3,
                   panel_height=150, title="Life expectancy")  # fmt: skip
    many.line(x="year", y="life_expect", color="country").legend("top")
    many.save_html(out / "legend-many.html")
    linked = Trellis(gapminder, wrap="year", cols=4, panel_height=150, link="country",
                     title="Fertility and life expectancy, 1955-2005")  # fmt: skip
    linked.points(x="fertility", y="life_expect", color="region", size=6, tooltip=["country"])
    linked.save_html(out / "gap-link.html")
    # tooltips (tooltip.mjs): every series at one x; lines grouped within a colour: one
    some = gapminder.filter(pl.col("country").is_in(
        ["Japan", "Chile", "Brazil", "India", "Kenya", "Iceland"]))  # fmt: skip
    series = Trellis(some, labels={"life_expect": "Life expectancy", "year": "Year"})
    series.line(x="year", y="life_expect", color="country").save_html(out / "series.html")
    grouped = Trellis(gapminder, wrap="region", cols=3, panel_height=150)
    grouped.line(x="year", y="life_expect", color="region", group="country", tooltip=["country"])
    grouped.save_html(out / "grouped.html")
    temps = Trellis(sensors(stations=6), wrap="station", title="Temperature")
    temps.line(x="time", y="temp", color="sensor").save_html(out / "sensors.html")
    cars = load("cars").with_columns(cyl=pl.col("cylinders").cast(pl.String))
    density = Trellis(cars, wrap="origin", cols=3, panel_height=150)
    density.density(x="mpg", color="cyl", fill=True).save_html(out / "density.html")
    Trellis(cars).hist(x="mpg").save_html(out / "hist.html")
    steps = {"t": [0.0, 1.0, 3.0], "v": [1.0, 2.0, 5.0]}
    Trellis(steps).line(x="t", y="v", step="post").save_html(out / "steps.html")
    Trellis(cars).violin(x="origin", y="mpg").save_html(out / "violin.html")
    Trellis(cars).errorbar(x="origin", y="mpg").save_html(out / "errorbar.html")
    paged = Trellis(sensors(stations=150, sensors=1, hours=24 * 7), wrap="station",
                    title="150 stations")  # fmt: skip
    paged.line(x="time", y="temp", width=1).save_html(out / "paged.html")
    regions = Trellis(sensors(stations=40, sensors=1, hours=48), wrap="station", page="region",
                      rows=2, cols=4, title="Stations by region")  # fmt: skip
    regions.line(x="time", y="temp", width=1).save_html(out / "regions.html")
    sites = Trellis(site_readings(), row="sensor", col="metric", page="site", share_y="page",
                    title="A grid per site")  # fmt: skip
    sites.line(x="t", y="v").save_html(out / "sites.html")
    many_plots(out / "many.html", gapminder)
    # shapes, sizes and dashes (channels.mjs)
    penguins = load("penguins")
    Trellis(penguins, wrap="island", cols=3, panel_height=200).points(
        x="bill_length_mm", y="bill_depth_mm", color="species", shape="species",
        size="body_mass_g", tooltip=["sex"]).save_html(out / "channels.html")  # fmt: skip
    flat = pl.DataFrame({"x": [0.0, 100.0, 0.0, 100.0], "y": [1.0, 1.0, 2.0, 2.0],
                         "k": ["first", "first", "second", "second"]})  # fmt: skip
    Trellis(flat, panel_height=200).line(x="x", y="y", dash="k", color="k", width=2).save_html(
        out / "dashes.html")  # fmt: skip
    dense_points(out / "dense.html")
    # names at the lines' ends, labels kept apart, notes (labels.mjs)
    some = gapminder.filter(pl.col("country").is_in(["Japan", "Brazil", "India", "Nigeria"]))
    some = some.with_columns(half=pl.when(pl.col("year") < 1980).then(pl.lit("before 1980"))
                             .otherwise(pl.lit("from 1980")))  # fmt: skip
    ends = Trellis(some, wrap="half", panel_height=220)
    ends.line(x="year", y="life_expect", color="country", label="end")
    ends.save_html(out / "ends.html")
    y05 = gapminder.filter(pl.col("year") == 2005)
    notes = Trellis(y05, wrap="region", cols=3, panel_height=200).points(
        x="fertility", y="life_expect").text(x="fertility", y="life_expect", text="country",
                                             repel=True)  # fmt: skip
    notes.annotate("Long lives", x=1.5, y=82, panel="Europe & Central Asia", dx=40, dy=20)
    notes.annotate("Replacement", x=2.1, dx=4)
    notes.save_html(out / "notes.html")
    # pins, the arrow keys, comparing (panels.mjs)
    countries = Trellis(gapminder, wrap="country", rows=2, cols=4, panel_height=110)
    countries.line(x="year", y="life_expect", color="region").save_html(out / "pins.html")
    # the settings panel left out (settings.mjs)
    Trellis(gapminder, wrap="region", controls=False).points(
        x="fertility", y="life_expect").save_html(out / "nocontrols.html")  # fmt: skip
    # hexagons, contours, rugs and segments (marks.mjs)
    Trellis(gapminder, wrap="region", cols=3, panel_height=180).hexbin(
        x="fertility", y="life_expect", bins=14).save_html(out / "hexbin.html")  # fmt: skip
    penguins = load("penguins")
    (Trellis(penguins, wrap="island", cols=3, panel_height=220)
     .points(x="bill_length_mm", y="bill_depth_mm", color="species", opacity=0.4)
     .contour(x="bill_length_mm", y="bill_depth_mm", color="species", levels=4)
     .rug(x="bill_length_mm", y="bill_depth_mm", color="species")
     .save_html(out / "contours.html"))  # fmt: skip
    change = gapminder.filter(pl.col("year").is_in([1955, 2005])).pivot(
        on="year", index=["country", "region"], values=["fertility", "life_expect"])  # fmt: skip
    Trellis(change, wrap="region", cols=3, panel_height=180).segments(
        x="fertility_1955", y="life_expect_1955", x2="fertility_2005", y2="life_expect_2005",
        tooltip=["country"]).save_html(out / "segments.html")  # fmt: skip
    layouts(out)
    lassos(out)
    saved_links(out)
    views(out)


def lassos(out: Path) -> None:
    """A lasso and marks clicked, selected in Python, and the rows Python selects
    (``<name>.selected.json``): the browser selects as many marks (lasso.mjs)."""
    import json

    gapminder = load("gapminder")
    tri = [(2.0, 50.0), (7.0, 50.0), (4.0, 80.0), (2.5, 70.0)]
    first = gapminder.row(0, named=True)
    for name, chosen in {"lasso": {"lasso": tri},
                         "clicked": {"at": [(first["fertility"], first["life_expect"])],
                                     "panel": str(first["year"])}}.items():  # fmt: skip
        t = Trellis(gapminder, wrap="year", cols=4, panel_height=150)
        t.points(x="fertility", y="life_expect", color="region", size=6)
        t.select(**chosen)
        t.save_html(out / f"{name}.html")
        (out / f"{name}.selected.json").write_text(json.dumps(len(t.selected())))


def views(out: Path) -> None:
    """A paged wrap with views kept in Python (views.mjs): "warm" (sorted, filtered, a page
    on), "zoomed" (the first half of x) and "pinned"; per view, the panels Python shows and
    its zoom (``views.json``)."""
    import json

    t = Trellis(pl.DataFrame(sensors(stations=60, sensors=1, hours=48)), wrap="station",
                rows=2, cols=4, title="Stations")  # fmt: skip
    t.line(x="time", y="temp", width=1)
    spec, _ = t._scene()
    lo, hi = spec["panels"][0]["x"]
    t.sort_panels("mean temp", descending=True).filter_panels(**{"mean temp": (8, None)})
    t.show_page(2).save_view("warm")
    t.sort_panels(None).filter_panels().show_page(1)
    t.save_view("zoomed", {"zoom": {"x": [[0, [lo, (lo + hi) / 2]]], "y": []}})
    t.pin("station 7").save_view("pinned").unpin()
    want = {}
    for name in t.views:
        t.show_view(name)
        panels = [t.panels().index(n) for n in t.shown_panels()]
        want[name] = {"panels": panels, "zoom": t.views[name]["zoom"]}
    t.sort_panels(None).filter_panels().unpin().show_page(1)
    t._start_zoom = None  # the page opens as the plot starts
    t._view = None
    t.save_html(out / "views.html")
    (out / "views.json").write_text(json.dumps(want))


def saved_links(out: Path) -> None:
    """Plots linked in a saved page (savedlink.mjs): cars' weight and mpg beside a histogram
    of horsepower per origin, with a brush made in Python and the shares Python's link fills
    the bars to (``link-saved.json``); and a link on="country" of two plots reading DuckDB
    (``load="pages"``), with the marks the second lights (``link-db.json``)."""
    import json

    import duckdb
    import numpy as np

    from anytrellis import link
    from anytrellis.linking import highlight_message

    cars = load("cars")
    scatter = Trellis(cars, title="Weight and mpg").points(x="weight", y="mpg")
    counts = Trellis(cars, wrap="origin", cols=3, title="Horsepower").hist(x="horsepower")
    both = link(scatter, counts)
    scatter.select(x=(2000, 3000), y=(20, 40))
    message, buffers = highlight_message(counts._highlight_entries(), counts._highlight)
    shares = [None if e is None or "fraction" not in e
              else np.frombuffer(buffers[e["fraction"]], dtype=np.float32).tolist()
              for e in message["layers"]]  # fmt: skip
    both.save_html(out / "link-saved.html", cols=2)
    (out / "link-saved.json").write_text(json.dumps(shares))
    gapminder = load("gapminder")
    rel = duckdb.from_arrow(gapminder.to_arrow())
    years = Trellis(rel, wrap="year", rows=1, cols=3, load="pages")
    years.points(x="fertility", y="life_expect")
    growth = Trellis(rel, wrap="region", rows=1, cols=3, load="pages")
    growth.line(x="year", y="pop", color="country")
    db = link(years, growth, on="country")
    years._scene()
    years.select(x=(6, 9), y=(20, 40), panel="1955")
    memory = Trellis(gapminder, wrap="year", rows=1, cols=3).points(x="fertility", y="life_expect")
    memory.select(x=(6, 9), y=(20, 40), panel="1955")
    chosen = memory.selected()["country"].unique().to_list()
    db.save_html(out / "link-db.html")
    lit = gapminder.filter(pl.col("country").is_in(chosen) & pl.col("pop").is_not_null()).height
    (out / "link-db.json").write_text(json.dumps({"countries": len(chosen), "rows": lit}))


def layouts(out: Path) -> None:
    """Panels placed by a layout table, sized by their range, columns repeated as rows and a
    paged wrap filled down its columns (layout.mjs), each with figure.py's boxes at the
    widths the browser may lay it out at (``<name>.boxes.json``)."""
    import json

    from anytrellis.figure import layout

    gapminder = load("gapminder")
    europe = pl.DataFrame(
        [("Iceland", 1, 1), ("Norway", 1, 4), ("Finland", 1, 5), ("Ireland", 2, 1),
         ("United Kingdom", 2, 2), ("Netherlands", 2, 3), ("Germany", 2, 4), ("Poland", 2, 5),
         ("France", 3, 2), ("Belgium", 3, 3), ("Switzerland", 3, 4), ("Austria", 3, 5),
         ("Portugal", 4, 1), ("Spain", 4, 2), ("Italy", 4, 4), ("Croatia", 4, 5),
         ("Georgia", 4, 7), ("Greece", 5, 5), ("Turkey", 5, 6)],
        schema=["country", "row", "col"], orient="row",
    )  # fmt: skip
    cars = load("cars").with_columns(cyl=pl.col("cylinders").cast(pl.String))
    weather = load("seattle_weather")
    plots = {
        "geo": Trellis(gapminder.filter(pl.col("region") == "Europe & Central Asia"),
                       wrap="country", layout=europe, panel_height=70)
        .area(x="year", y="life_expect"),
        "space": Trellis(cars, col="origin", share_x="col", space="free_x", panel_height=200)
        .bars(x="cyl", stat="count"),
        "repeat": Trellis(weather, repeat=["temp_max", "precipitation", "wind"],
                          labels={"temp_max": "High (°C)"}, space="free_y", height=420)
        .line(x="date", y="value", width=0.8),
        "downwards": Trellis(gapminder, wrap="country", rows=2, cols=3, direction="v",
                             panel_height=90).line(x="year", y="life_expect"),
    }  # fmt: skip
    for name, plot in plots.items():
        plot.save_html(out / f"{name}.html")
        spec, _ = plot._scene()
        boxes = {w: [[b.index, b.rect.x, b.rect.y, b.rect.w, b.rect.h]
                     for b in layout(spec, w).panels] for w in range(900, 1001)}  # fmt: skip
        (out / f"{name}.boxes.json").write_text(json.dumps(boxes))


def site_readings() -> pl.DataFrame:
    """Three sites (the higher their number, the higher their readings), each two sensors by
    three metrics; site C has no sensor b."""
    rng = np.random.default_rng(5)
    rows = []
    for k, site in enumerate("ABC"):
        for sensor in "ab":
            if site == "C" and sensor == "b":
                continue
            for metric in ("temp", "rain", "wind"):
                t = np.arange(50.0)
                rows.append(pl.DataFrame({"site": site, "sensor": sensor, "metric": metric, "t": t,
                                          "v": 10.0 * (k + 1) + rng.normal(0, 1, 50)}))  # fmt: skip
    return pl.concat(rows)


def dense_points(path: Path, n: int = 150_000) -> None:
    """Two panels of more points than anytrellis.detail.DENSE: drawn as cells."""
    rng = np.random.default_rng(3)
    cloud = {
        "x": rng.normal(size=2 * n),
        "y": rng.normal(size=2 * n),
        "kind": rng.choice(["a", "b"], 2 * n, p=[0.7, 0.3]),
        "half": np.repeat(["left", "right"], n),
    }
    Trellis(cloud, wrap="half", title="Dense").points(x="x", y="y", color="kind").save_html(path)


def many_plots(path: Path, gapminder: pl.DataFrame, count: int = 20) -> None:
    """A page as the documentation makes one: many plots (``_embed_html``) between text,
    the bundle and its CSS once."""
    static = Path(anytrellis.__file__).parent / "static"
    css = (static / "widget.css").read_text(encoding="utf-8")
    script = (static / "standalone.js").read_text(encoding="utf-8")
    text = "<p style='height:500px'>Text between the plots.</p>"
    plots = []
    for i, year in enumerate(sorted(gapminder["year"].unique())[:count] * 2):
        if len(plots) == count:
            break
        rows = gapminder.filter(pl.col("year") == year)
        plot = Trellis(rows, wrap="region", panel_height=90, title=f"{year} ({i + 1})")
        plots.append(plot.points(x="fertility", y="life_expect")._embed_html())
    body = text.join(plots)
    path.write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head>"
        f"<body>{body}<script>{script}</script></body></html>",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "pages"))
