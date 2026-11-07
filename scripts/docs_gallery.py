"""The documentation's gallery: a picture of each kind of plot, each linking to the guide
that makes it, and the labelled picture on "At a glance".

    uv run python scripts/docs_gallery.py     # the pictures, into docs/user/assets/gallery/

scripts/build_docs.py draws them when they are missing (they are not committed), and
docs/user/gallery.md prints the cards with ``cards()``. Each plot is made the way its guide
makes it, with less data; ``save_html`` writes it and js/scripts/shots.mjs takes its
picture in Chromium (Playwright), drawn with Canvas 2D so it is the same on every machine.
tests/test_docs.py checks that every guide linked exists.
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anytrellis import Trellis

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "user" / "assets" / "gallery"


@dataclass(frozen=True)
class Entry:
    slug: str
    title: str
    guide: str  # relative to docs/user/, with an anchor
    plot: Callable[[], Trellis]


def _gallery() -> list[Entry]:
    import polars as pl

    from anytrellis import Trellis
    from anytrellis.datasets import load
    from anytrellis.synthetic import scatter, sensors

    cars = load("cars")
    penguins = load("penguins")
    gapminder = load("gapminder")
    weather = load("seattle_weather").with_columns(year=pl.col("date").dt.year())
    barley = load("barley").with_columns(pl.col("year").cast(pl.String))
    six = gapminder.filter(
        pl.col("country").is_in(["China", "India", "United States", "Nigeria", "Japan",
                                 "Iceland"])
    )  # fmt: skip
    by_cyl = cars.with_columns(cyl=pl.col("cylinders").cast(pl.String))

    def regions_area() -> Trellis:
        by_region = gapminder.group_by("region", "year").agg(pl.col("pop").sum())
        return Trellis(by_region).area(x="year", y="pop", color="region")

    def heatmap() -> Trellis:
        daily = weather.with_columns(month=pl.col("date").dt.month(), day=pl.col("date").dt.day())
        return Trellis(daily, wrap="year", cols=2).rect(x="day", y="month", color="temp_max")

    def labels() -> Trellis:
        eight = gapminder.filter(
            pl.col("year").is_in([1955, 2005])
            & pl.col("country").is_in(["China", "India", "Japan", "Brazil", "Nigeria",
                                       "United States", "Egypt"])
        )  # fmt: skip
        return (
            Trellis(eight, wrap="year")
            .points(x="fertility", y="life_expect", color="region", size=7)
            .text(x="fertility", y="life_expect", text="country", align="left", dx=6)
        )

    return [
        Entry("points", "Points in a wrap", "how-to/marks.md#points",
              lambda: Trellis(penguins, wrap="species").points(
                  x="flipper_length_mm", y="body_mass_g", color="sex")),
        Entry("lines", "A line per group", "how-to/marks.md#lines",
              lambda: Trellis(gapminder, wrap="region", cols=3).line(
                  x="year", y="life_expect", group="country", width=1)),
        Entry("dodged-bars", "Bars side by side", "how-to/marks.md#bars",
              lambda: Trellis(barley, wrap="site", cols=3).bars(
                  x="variety", y="yield", color="year", position="dodge")),
        Entry("grid", "A grid with empty cells",
              "tutorials/facets-and-scales.md#2-empty-cells-stay",
              lambda: Trellis(cars, row="origin", col="cylinders").points(
                  x="horsepower", y="mpg", size=4)),
        Entry("free-y", "Free y scales", "how-to/scales.md#free-y-shared-x",
              lambda: Trellis(six, wrap="country", cols=3, share_y=False).line(
                  x="year", y="pop")),
        Entry("log", "A log scale", "how-to/log.md",
              lambda: Trellis(gapminder, wrap="region", cols=3, y_scale="log").line(
                  x="year", y="pop", group="country", width=1)),
        Entry("against-the-rest", "Each group against the rest",
              "how-to/marks.md#each-group-against-the-rest",
              lambda: Trellis(gapminder, wrap="region", cols=3)
              .line(x="year", y="life_expect", group="country", facet="exclude", width=1)
              .line(x="year", y="life_expect", group="country", color="region")),
        Entry("areas", "Stacked areas", "how-to/more-marks.md#areas", regions_area),
        Entry("bands", "Bands: a low to a high", "how-to/more-marks.md#bands",
              lambda: Trellis(weather, wrap="year", cols=2, share_x=False).band(
                  x="date", ymin="temp_min", ymax="temp_max", color="#d62728")),
        Entry("heatmap", "Heatmaps", "how-to/more-marks.md#rects-and-heatmaps", heatmap),
        Entry("labels", "Labels", "how-to/more-marks.md#text", labels),
        Entry("histograms", "Histograms", "how-to/distributions.md#histograms",
              lambda: Trellis(penguins, wrap="species", cols=3).hist(
                  x="flipper_length_mm", binwidth=2, color="sex")),
        Entry("boxes", "Box plots", "how-to/distributions.md#box-plots",
              lambda: Trellis(by_cyl, wrap="origin", cols=3).box(x="mpg", y="cyl")),
        Entry("densities", "Densities", "how-to/distributions.md#densities",
              lambda: Trellis(by_cyl, wrap="origin", cols=3).density(
                  x="mpg", color="cyl", fill=True)),
        Entry("smooth", "Smooth fits", "how-to/smooth.md",
              lambda: Trellis(cars, wrap="origin", cols=3)
              .points(x="horsepower", y="mpg", size=4, opacity=0.5)
              .smooth(x="horsepower", y="mpg")),
        Entry("dot-plot", "An ordered dot plot",
              "how-to/from-altair-lattice.md#cleveland-and-lattice",
              lambda: Trellis(barley, wrap="site", cols=3, y_title="")
              .order("site", by="median", of="yield", descending=True)
              .order("variety", by="median", of="yield")
              .points(x="yield", y="variety", color="year", size=6)),
        Entry("many-points", "Many points", "how-to/large.md#many-points",
              lambda: Trellis(scatter(n=40_000, groups=16), wrap="group", cols=4).points(
                  x="x", y="y", color="cluster", size=1.5, opacity=0.4)),
        Entry("series", "Long series", "how-to/large.md#long-series",
              lambda: Trellis(sensors(stations=6, hours=24 * 30), wrap="station", cols=3)
              .line(x="time", y="temp", color="sensor", width=0.8)),
        Entry("followed", "Following things across panels",
              "tutorials/select.md#3-follow-things-across-panels",
              lambda: Trellis(gapminder, wrap="year", cols=4, link="country")
              .points(x="fertility", y="life_expect", color="region", size=5)
              .select(x=(0, 3), panel="1955")),
    ]  # fmt: skip


def entries() -> list[Entry]:
    return _gallery()


# the parts of a plot, numbered on "At a glance" (docs/user/glance.md says what each is)
GLANCE_LABELS = [
    {"n": 1, "target": "title"},
    {"n": 2, "target": "toolbar"},
    {"n": 3, "target": "strip:0"},
    {"n": 4, "target": "panel:0"},
    {"n": 5, "target": "yaxis:0"},
    {"n": 6, "target": "xaxis:2"},
    {"n": 7, "target": "legend"},
    {"n": 8, "target": "badge"},
]


def _glance() -> Trellis:
    from anytrellis import Trellis
    from anytrellis.datasets import load

    cars = load("cars")
    return Trellis(cars, wrap="origin", cols=2, panel_height=150,
                   title="Fuel use and weight, by origin").points(
        x="weight", y="mpg", color="cylinders", size=5)  # fmt: skip


def cards() -> str:
    """The gallery's cards, as HTML for docs/user/gallery.md."""
    items = []
    for e in entries():
        guide = e.guide.replace(".md", ".html")
        items.append(
            f'<a href="{html.escape(guide)}"><img src="assets/gallery/{e.slug}.png" '
            f'alt="{html.escape(e.title)}" loading="lazy"><span>{html.escape(e.title)}</span></a>'
        )
    return '<div class="atr-gallery">\n' + "\n".join(items) + "\n</div>"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shots = []
        for e in entries():
            page = e.plot().save_html(work / f"{e.slug}.html")
            shots.append({"page": str(page), "out": str(OUT / f"{e.slug}.png"),
                          "width": 720, "height": 480})  # fmt: skip
        page = _glance().save_html(work / "glance.html")
        shots.append({"page": str(page), "out": str(OUT / "glance.png"), "width": 820,
                      "height": 640, "scale": 2, "labels": GLANCE_LABELS})  # fmt: skip
        manifest = work / "shots.json"
        manifest.write_text(json.dumps(shots), encoding="utf-8")
        done = subprocess.run(["node", "scripts/shots.mjs", str(manifest)], cwd=ROOT / "js",
                              check=False)  # fmt: skip
        if done.returncode:
            sys.exit("the pictures could not be taken (js/scripts/shots.mjs)")
    print(f"{len(shots)} pictures in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
