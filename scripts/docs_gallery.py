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
HEIGHT = 380
"""A card's plot's height (px), unless it sets its own shape: the picture is 720 x 480,
with room for the toolbar, the axis titles and the legend."""


@dataclass(frozen=True)
class Entry:
    section: str  # a heading of the gallery page
    slug: str
    title: str
    guide: str  # relative to docs/user/, with an anchor
    plot: Callable[[], Trellis]


def _gallery() -> list[Entry]:
    import polars as pl

    from anytrellis import Trellis, pairs
    from anytrellis.datasets import load
    from anytrellis.synthetic import scatter, sensors

    cars = load("cars")
    penguins = load("penguins")
    known = penguins.drop_nulls("sex")
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

    def monthly_rain() -> Trellis:
        monthly = weather.group_by("year", month=pl.col("date").dt.month()).agg(
            pl.col("precipitation").sum()
        )
        return Trellis(monthly, wrap="year", cols=2).line(x="month", y="precipitation", step="mid")

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

    def direct_labels() -> Trellis:
        return Trellis(six, y_scale="log").line(
            x="year", y="pop", color="country", label="end", width=2
        )

    def bars_along_y() -> Trellis:
        return Trellis(by_cyl, wrap="origin", cols=3).bars(y="cyl", stat="count", color="cyl")

    def notes() -> Trellis:
        means = (
            gapminder.filter(pl.col("year") == 2005)
            .group_by("region")
            .agg(mean=pl.col("life_expect").mean())
        )
        return (
            Trellis(gapminder, wrap="region", cols=3)
            .line(x="year", y="life_expect", group="country", width=1, color="#9aa5b1")
            .rule(means, y="mean", dash=(4, 3))
            .annotate("Rwanda, 1990", x=1990, y=23.6, panel="Sub-Saharan Africa", dx=-40, dy=-4)
        )

    def diverging() -> Trellis:
        above = gapminder.with_columns(gap=pl.col("life_expect") - pl.col("life_expect").mean())
        return (
            Trellis(above, wrap="year", cols=4)
            .points(x="fertility", y="life_expect", color="gap", size=5)
            .colormap(scale="diverging", midpoint=0)
        )

    def banked() -> Trellis:
        days = weather.with_columns(
            year=pl.col("year").cast(pl.String),
            day=pl.col("date").dt.ordinal_day().cast(pl.Float64),
        )
        return Trellis(days, wrap="year", cols=2, aspect="bank").smooth(
            x="day", y="temp_max", span=0.1, se=False
        )

    def margins() -> Trellis:
        three = cars.filter(pl.col("cylinders").is_in([4, 6, 8]))
        return (
            Trellis(three, row="origin", col="cylinders", margins=True)
            .points(x="horsepower", y="mpg", size=3)
            .smooth(x="horsepower", y="mpg")
        )

    def horizons() -> Trellis:
        week = sensors(stations=24, sensors=1, hours=24 * 7)
        return Trellis(week, wrap="station", cols=2, panel_height=24).horizon(
            x="time", y="temp", origin=10
        )

    def segments() -> Trellis:
        change = gapminder.filter(pl.col("year").is_in([1955, 2005])).pivot(
            on="year", index=["country", "region"], values=["fertility", "life_expect"]
        )
        return (
            Trellis(change, wrap="region", cols=3, x_title="fertility", y_title="life_expect")
            .segments(
                x="fertility_1955", y="life_expect_1955", x2="fertility_2005", y2="life_expect_2005"
            )
            .points(x="fertility_2005", y="life_expect_2005", size=4)
        )

    return [
        Entry("Points and lines", "points", "Points in a wrap", "how-to/marks.md#points",
              lambda: Trellis(penguins, wrap="species").points(
                  x="flipper_length_mm", y="body_mass_g", color="sex")),
        Entry("Points and lines", "shapes", "Shapes besides colour",
              "how-to/accessibility.md#a-second-encoding-shapes-and-dashes",
              lambda: Trellis(penguins, wrap="island", cols=3, redundant=True).points(
                  x="bill_length_mm", y="bill_depth_mm", color="species")),
        Entry("Points and lines", "lines", "A line per group", "how-to/marks.md#lines",
              lambda: Trellis(gapminder, wrap="region", cols=3).line(
                  x="year", y="life_expect", group="country", width=1)),
        Entry("Points and lines", "steps", "Step lines", "how-to/marks.md#steps", monthly_rain),
        Entry("Points and lines", "direct-labels", "Names at the ends of lines",
              "how-to/marks.md#names-at-the-ends-of-lines", direct_labels),
        Entry("Points and lines", "labels", "Labels", "how-to/more-marks.md#text", labels),
        Entry("Points and lines", "against-the-rest", "Each group against the rest",
              "how-to/marks.md#each-group-against-the-rest",
              lambda: Trellis(gapminder, wrap="region", cols=3)
              .line(x="year", y="life_expect", group="country", facet="exclude", width=1)
              .line(x="year", y="life_expect", group="country", color="region")),
        Entry("Points and lines", "followed", "Following things across panels",
              "tutorials/select.md#3-follow-things-across-panels",
              lambda: Trellis(gapminder, wrap="year", cols=4, link="country")
              .points(x="fertility", y="life_expect", color="region", size=5)
              .select(x=(0, 3), panel="1955")),

        Entry("Bars, areas and tiles", "dodged-bars", "Bars side by side",
              "how-to/marks.md#bars",
              lambda: Trellis(barley, wrap="site", cols=3).bars(
                  x="variety", y="yield", color="year", position="dodge")),
        Entry("Bars, areas and tiles", "counted-bars", "Bars that count, along y",
              "how-to/marks.md#bars-that-summarise-stat", bars_along_y),
        Entry("Bars, areas and tiles", "shares", "Shares of each stack",
              "how-to/marks.md#shares-positionfill",
              lambda: Trellis(barley, wrap="site", cols=3).bars(
                  x="variety", y="yield", color="year", position="fill")),
        Entry("Bars, areas and tiles", "areas", "Stacked areas", "how-to/more-marks.md#areas",
              regions_area),
        Entry("Bars, areas and tiles", "bands", "Bands: a low to a high",
              "how-to/more-marks.md#bands",
              lambda: Trellis(weather, wrap="year", cols=2, share_x=False).band(
                  x="date", ymin="temp_min", ymax="temp_max", color="#d62728")),
        Entry("Bars, areas and tiles", "heatmap", "Heatmaps",
              "how-to/more-marks.md#rects-and-heatmaps", heatmap),
        Entry("Bars, areas and tiles", "diverging", "Above and below a midpoint",
              "how-to/colours.md#number-colours-colormap", diverging),
        Entry("Bars, areas and tiles", "segments", "Segments: from one value to another",
              "how-to/more-marks.md#segments", segments),
        Entry("Bars, areas and tiles", "notes", "Reference lines and notes",
              "how-to/more-marks.md#reference-lines", notes),

        Entry("Distributions", "histograms", "Histograms", "how-to/distributions.md#histograms",
              lambda: Trellis(penguins, wrap="species", cols=3).hist(
                  x="flipper_length_mm", binwidth=2, color="sex")),
        Entry("Distributions", "boxes", "Box plots", "how-to/distributions.md#box-plots",
              lambda: Trellis(by_cyl, wrap="origin", cols=3).box(x="mpg", y="cyl")),
        Entry("Distributions", "violins", "Violins", "how-to/distributions.md#violins",
              lambda: Trellis(known, wrap="species", cols=3).violin(
                  x="sex", y="flipper_length_mm", color="sex")),
        Entry("Distributions", "densities", "Densities", "how-to/distributions.md#densities",
              lambda: Trellis(by_cyl, wrap="origin", cols=3).density(
                  x="mpg", color="cyl", fill=True)),
        Entry("Distributions", "rug", "A density and its values",
              "how-to/distributions.md#the-values-under-the-curve",
              lambda: Trellis(known, wrap="species", cols=3)
              .density(x="body_mass_g", color="sex").rug(x="body_mass_g", color="sex")),
        Entry("Distributions", "ecdf", "Cumulative distributions",
              "how-to/distributions.md#cumulative-distributions",
              lambda: Trellis(penguins, wrap="island", cols=3).ecdf(
                  x="body_mass_g", color="species")),
        Entry("Distributions", "error-bars", "Error bars",
              "how-to/distributions.md#error-bars",
              lambda: Trellis(known, wrap="species", cols=3).errorbar(
                  x="sex", y="body_mass_g", color="sex")),

        Entry("Two columns at once", "smooth", "Smooth fits", "how-to/smooth.md",
              lambda: Trellis(cars, wrap="origin", cols=3)
              .points(x="horsepower", y="mpg", size=4, opacity=0.5)
              .smooth(x="horsepower", y="mpg")),
        Entry("Two columns at once", "hexbin", "Hexagonal bins",
              "how-to/distributions.md#two-columns-at-once",
              lambda: Trellis(gapminder, wrap="region", cols=3).hexbin(
                  x="fertility", y="life_expect", bins=16)),
        Entry("Two columns at once", "contours", "Density contours",
              "how-to/distributions.md#two-columns-at-once",
              lambda: Trellis(penguins, wrap="island", cols=3)
              .points(x="bill_length_mm", y="bill_depth_mm", color="species", opacity=0.4)
              .contour(x="bill_length_mm", y="bill_depth_mm", color="species", levels=4)),
        Entry("Two columns at once", "pairs", "Every pair of columns", "how-to/pairs.md",
              lambda: pairs(penguins, ["bill_length_mm", "bill_depth_mm", "flipper_length_mm"],
                            color="species")),

        Entry("Layout and scales", "grid", "A grid with empty cells",
              "tutorials/facets-and-scales.md#2-empty-cells-stay",
              lambda: Trellis(cars, row="origin", col="cylinders").points(
                  x="horsepower", y="mpg", size=4)),
        Entry("Layout and scales", "margins", "Margins: the rows and columns together",
              "how-to/layout.md#margins-the-rows-and-columns-together", margins),
        Entry("Layout and scales", "free-y", "Free y scales",
              "how-to/scales.md#free-y-shared-x",
              lambda: Trellis(six, wrap="country", cols=3, share_y=False).line(
                  x="year", y="pop")),
        Entry("Layout and scales", "log", "A log scale", "how-to/log.md",
              lambda: Trellis(gapminder, wrap="region", cols=3, y_scale="log").line(
                  x="year", y="pop", group="country", width=1)),
        Entry("Layout and scales", "banked", "Banked to 45 degrees",
              "how-to/layout.md#banking-to-45-degrees", banked),
        Entry("Layout and scales", "dot-plot", "An ordered dot plot",
              "how-to/from-altair-lattice.md#cleveland-and-lattice",
              lambda: Trellis(barley, wrap="site", cols=3, y_title="")
              .order("site", by="median", of="yield", descending=True)
              .order("variety", by="median", of="yield")
              .points(x="yield", y="variety", color="year", size=6)),

        Entry("Many panels, much data", "pages", "Pages of panels, sorted", "how-to/pages.md",
              lambda: Trellis(sensors(stations=150, sensors=1, hours=24 * 7), wrap="station")
              .line(x="time", y="temp", width=1)
              .sort_panels("trend temp", descending=True)),
        Entry("Many panels, much data", "horizons", "Horizon charts",
              "how-to/large.md#horizon-charts-many-series-in-little-height", horizons),
        Entry("Many panels, much data", "many-points", "Many points",
              "how-to/large.md#many-points",
              lambda: Trellis(scatter(n=40_000, groups=16), wrap="group", cols=4).points(
                  x="x", y="y", color="cluster", size=1.5, opacity=0.4)),
        Entry("Many panels, much data", "series", "Long series", "how-to/large.md#long-series",
              lambda: Trellis(sensors(stations=6, hours=24 * 30), wrap="station", cols=3)
              .line(x="time", y="temp", color="sensor", width=0.8)),
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
]


def _glance() -> Trellis:
    from anytrellis import Trellis
    from anytrellis.datasets import load

    cars = load("cars")
    return Trellis(cars, wrap="origin", cols=2, panel_height=150,
                   title="Fuel use and weight, by origin").points(
        x="weight", y="mpg", color="cylinders", size=5)  # fmt: skip


def sections() -> list[str]:
    """The gallery's headings, in order."""
    return list(dict.fromkeys(e.section for e in entries()))


def cards(section: str) -> str:
    """A section's cards, as HTML for docs/user/gallery.md (under its heading)."""
    if section not in sections():
        raise ValueError(f"no gallery section {section!r}: {sections()}")
    items = []
    for e in entries():
        if e.section != section:
            continue
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
            plot = e.plot()
            if plot.height is None and plot.panel_height is None and plot.aspect is None:
                plot.height = HEIGHT  # the picture's height: no card half empty
            page = plot.save_html(work / f"{e.slug}.html")
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
