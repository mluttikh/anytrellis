"""Write the save_html pages the browser checks run on: ``uv run python js/test/pages.py
<dir>``, then ``node js/test/select.mjs <dir>/years.html`` (and legend.mjs, zoom.mjs,
many.mjs, details.mjs, paging.mjs)."""

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
    linked = Trellis(gapminder, wrap="year", cols=4, panel_height=150, link="country",
                     title="Fertility and life expectancy, 1955-2005")  # fmt: skip
    linked.points(x="fertility", y="life_expect", color="region", size=6, tooltip=["country"])
    linked.save_html(out / "gap-link.html")
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
    many_plots(out / "many.html", gapminder)
    dense_points(out / "dense.html")


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
