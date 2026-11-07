"""Write the save_html pages the browser checks run on: ``uv run python js/test/pages.py
<dir>``, then ``node js/test/select.mjs <dir>/years.html`` (and legend.mjs, zoom.mjs)."""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

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


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "pages"))
