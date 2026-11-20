# Cheat sheet

All of anytrellis on one page, as code. Every block runs, in order, as one script (the
tests run it), so a line copied from here works. The guides linked in each section say
more; the [reference](reference/index.md) lists every argument. For an AI assistant,
[llms.txt](https://mluttikh.github.io/anytrellis/llms.txt) maps the documentation.

## A plot

```python
from anytrellis import Trellis
from anytrellis.datasets import load

cars = load("cars")  # also barley, gapminder, penguins, seattle_weather, anscombe
t = Trellis(cars, wrap="origin")  # a panel per origin
t.points(x="weight", y="mpg", color="cylinders")
t  # the last line of a notebook cell shows it
```

Every method that adds or changes something returns the plot, so calls chain. The data
can be Polars, pandas, PyArrow, DuckDB, Ibis or a dict of arrays
([Plot your own tables](how-to/tables.md)).

## Facets

```python
gapminder = load("gapminder")

Trellis(cars, wrap="origin", cols=3)  # panels wrapped into 3 columns
Trellis(cars, row="origin", col="cylinders")  # a grid: origins by cylinders
Trellis(cars, row="origin", col="cylinders", empty="blank")  # cells without data left out
Trellis(cars, row="origin", col="cylinders", margins=True)  # "(all)" panels: "row", "col"
Trellis(cars, wrap=["origin", "cylinders"], strips="joined")  # one strip, "USA · 4"
Trellis(gapminder, wrap="country", strip_label="region")  # a column names each panel
Trellis(cars, wrap="name", rows=3)  # pages of 3 rows; over 100 panels page anyway
Trellis(cars, wrap="cylinders", page="origin")  # a page per origin
```

See [Choose a facet layout](how-to/layout.md) and [Page through many
panels](how-to/pages.md).

## Scales and size

```python
Trellis(cars, wrap="origin", share_y=False)  # also "row", "col", "page", "sliced"
Trellis(cars, wrap="origin", share_x="row", y_scale="log")  # also "sqrt", "symlog", "linear"
Trellis(cars, wrap="origin", aspect=1)  # square panels; aspect="bank": slopes at 45°
Trellis(cars, wrap="origin", panel_height=150)  # or height=600, the whole plot
Trellis(cars, wrap="origin", fit_y=True)  # y follows the data in view as x zooms

t = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
t.share(x=True, y="row")  # as share_x=, share_y=
t.scale(x="log")  # as x_scale=
t.scale(y=("sqrt", "reverse"))  # high to low; "reverse" alone: a linear axis reversed
t.limits(y=(0, None))  # y from 0; None: the data's own end
t.as_category("cylinders")  # read numbers as categories
t.order("origin", ["USA", "Japan", "Europe"])  # levels in this order
t.order("origin", by="median", of="mpg", descending=True)  # mean, min, max, sum, count
```

See [Share or free the scales](how-to/scales.md) and [Log, sqrt, symlog and reversed
scales](how-to/log.md).

## Marks

```python
barley = load("barley")
penguins = load("penguins")
weather = load("seattle_weather")

Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="cylinders", size=5,
                                    opacity=0.85, tooltip=["name"])
Trellis(barley, wrap="year").points(x="site", y="yield", jitter=0.3)  # spread in its band
Trellis(gapminder, wrap="region").line(x="year", y="life_expect", group="country",
                                       width=1)  # step="post", "pre" or "mid"
Trellis(barley, wrap="site").bars(x="variety", y="yield", color="year",
                                  position="dodge")  # "stack", "fill", "identity"
Trellis(barley, wrap="site").bars(x="yield", y="variety")  # a category y: horizontal
Trellis(gapminder, wrap="region").area(x="year", y="pop", group="country")  # stacked
Trellis(weather, wrap="weather").band(x="date", ymin="temp_min", ymax="temp_max")
Trellis(barley, wrap="year").rect(x="site", y="variety", color="yield")  # tiles
Trellis(cars, wrap="origin").text(x="weight", y="mpg", text="cylinders", size=9)
Trellis(weather, wrap="weather").horizon(x="date", y="temp_max", bands=3)

t = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
t.rule(y=30, dash=(4, 3))  # a line across every panel
t.rule({"origin": ["USA", "Japan"], "goal": [25, 35]}, y="goal")  # a line per panel
Trellis(cars, wrap="origin").points(x="weight", y="mpg", facet="exclude")  # grey context
```

Every mark takes `facet=`: `"auto"`, `"include"`, `"all"` (every row in every panel) or
`"exclude"` (the other panels' rows), and `name=`. See [Draw lines, points and
bars](how-to/marks.md) and [Draw areas, bands, rects and text](how-to/more-marks.md).

## Summaries

Computed per panel (and per colour), on the shared scales:

```python
Trellis(penguins, wrap="island").hist(x="body_mass_g", color="species", bins=30)
Trellis(penguins, wrap="island").hist(x="body_mass_g", stat="percent")  # or "density"
Trellis(penguins, wrap="island").density(x="body_mass_g", color="species", fill=True)
Trellis(penguins, wrap="island").box(x="species", y="body_mass_g")
Trellis(penguins, wrap="island").violin(x="species", y="body_mass_g")
Trellis(penguins, wrap="island").errorbar(x="species", y="body_mass_g")  # extent="sd"
Trellis(penguins, wrap="island").bars(x="species", stat="count")  # rows at each x
Trellis(penguins, wrap="island").bars(x="species", y="body_mass_g", stat="mean")  # sum, median
Trellis(penguins, wrap="island").ecdf(x="body_mass_g", color="species")  # complementary=True
Trellis(cars, wrap="origin").points(x="weight", y="mpg").smooth(x="weight", y="mpg")
Trellis(cars, wrap="origin").smooth(x="weight", y="mpg", method="linear", se=False)
```

See [Show distributions](how-to/distributions.md) and [Fit a smooth line](how-to/smooth.md).

## Every pair of columns

```python
from anytrellis import pairs

p = pairs(penguins, ["bill_length_mm", "bill_depth_mm", "body_mass_g"], color="species",
          diag="hist", corner=True)  # a Pairs, which is a Trellis
p.selected()  # the brushed rows
```

See [Plot every pair of columns](how-to/pairs.md).

## Colours and legend

```python
Trellis(cars, wrap="origin", palette="okabe-ito")  # petroff10, observable10, tab10, ...
Trellis(cars, wrap="cylinders", palette={"USA": "#1f77b4", "Japan": "#d62728"}).points(
    x="weight", y="mpg", color="origin")  # these colours for these categories

t = Trellis(cars, wrap="origin").points(x="weight", y="mpg", color="horsepower")
t.colormap("cividis")  # number colours: viridis, magma, Blues, RdBu, PuOr, "_r" reversed
t.colormap(scale="diverging", midpoint=100)  # also "binned" and "quantile", bins=5
t.legend("right", title="Power (hp)")  # "auto", "top", "bottom", "right", "none"
t.select(color=(100, 150))  # a number colour's range: as dragging on its gradient
Trellis(cars, wrap="origin", legend="none")
```

See [Colours, legends and order](how-to/colours.md).

## Words and numbers

```python
t = Trellis(cars, wrap="origin",
            title="Heavier cars use more fuel",
            subtitle="Fuel economy against weight, 1970 to 1982",
            caption="Source: UCI auto-mpg",
            labels={"mpg": "Fuel economy (mpg)", "weight": "Weight (lb)"},
            x_title="Weight", y_title="Miles per gallon")
t.points(x="weight", y="mpg")
t.format(x=",.0f", y=".1f")  # d3-format; times strftime: "%b %Y"
```

## The look

```python
from anytrellis import Theme, get_theme, set_theme

Trellis(cars, wrap="origin", theme="framed")  # "minimal" (the default), "framed", "classic"
Trellis(cars, wrap="origin", theme=Theme("minimal", grid="both", panel_gap=16))
set_theme("framed")  # every plot from now on
set_theme(strip_fill=True)  # the minimal theme, one setting changed
set_theme(context="talk")  # text, lines and points 1.5 times: "paper", "notebook", "poster"
set_theme(font_size=14)  # px; "auto": 12, 11 in narrow panels, 13 in an opened one
get_theme()
set_theme()  # back to minimal
```

See [Theme and set_theme](reference/theme.md).

## Selection and panels

```python
t = Trellis(gapminder, wrap="year", link="country")  # a selection follows each country
t.points(x="fertility", y="life_expect", color="region")
t.select(x=(1, 3), panel="1955")  # as a brush in the browser; select() clears it
t.select(color=["Europe & Central Asia"])  # as clicking the legend
t.selection  # what is selected
t.selected()  # the selected rows, as the same kind of table

t.panels()  # the panels' names
t.open("2005")  # one panel alone; t.close() goes back
t.focused  # the opened panel's name
t.close()
```

```python
from anytrellis import link

a = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
b = Trellis(cars, wrap="origin").hist(x="horsepower")
both = link(a, b)  # a brush in one selects in both; link(a, b, on="name") by a key
both.clear()  # clear the selection
both.unlink()
```

See [Select data and use it in Python](tutorials/select.md) and
[Link plots](how-to/link.md).

## Many panels

```python
from anytrellis import synthetic

t = Trellis(synthetic.sensors(stations=120), wrap="station")  # over 100 panels: pages
t.line(x="time", y="temp", color="sensor")
t.pages, t.page, t.page_names  # how many pages, the one shown, their names
t.show_page(2)
t.stats()  # rows, mean, median, min, max, sd and trend of each panel
t.sort_panels("trend temp", descending=True)
t.filter_panels("station 1", **{"mean temp": (10, None)})  # filter_panels() clears
t.panel_stats({"station": ["station 1", "station 2"], "region": ["north", "south"]})
t.shown_panels()  # the panels on the page shown
t.paging  # the page, sort and filters shown
```

`synthetic.sales()` and `synthetic.scatter()` make other test tables. See [Page through
many panels](how-to/pages.md).

## Large data and databases

```python
import duckdb
import polars as pl

frame = pl.DataFrame(synthetic.sensors(stations=200))
table = duckdb.sql("select * from frame")  # or a Polars LazyFrame, an Ibis table
t = Trellis(table, wrap="station", load="pages")  # reads the page shown, not every row
t.line(x="time", y="temp")
```

Lines of over 20,000 points and dense points are drawn at a level of detail; zooming
reads more. `renderer="webgl2"` (or `"webgpu"`, `"canvas2d"`, default `"auto"`) picks
how the plot is drawn. See [Plot large data](how-to/large.md).

## Share

```python
t = Trellis(cars, wrap="origin").points(x="weight", y="mpg")
t.save_html("cars.html")  # opens in a browser, no Python needed; t.to_html() as text
t.save_svg("cars.svg", width=800)  # drawn in Python, no browser
t.save_png("cars.png", scale=2)  # needs pip install "anytrellis[png]"
t.widget  # the notebook widget that shows the plot
```

See [Share a plot](how-to/share.md).

## Mouse and keys

Click a plot first, then:

| Do | To |
| --- | --- |
| Scroll, drag | zoom x, pan (Shift+scroll: zoom y; on an axis: that axis alone) |
| Shift+drag, ++z++ | box zoom |
| ++s++ | drag selects |
| Hover, click | the values there (lines by colour: every one at that x); a click pins them |
| Double-click a panel, ++enter++ | see it alone; ++backspace++ back |
| ++page-up++ ++page-down++ | previous or next panel, or page |
| ++y++ | fit y to the data in view |
| ++r++, ++u++ | reset the zoom, undo it |
| ++esc++ | unpin, clear the selection |
| ++e++, ++f++, ++question++ | export, full screen, help |

See [Mouse and keys](reference/mouse-and-keys.md).
