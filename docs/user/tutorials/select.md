# Select data and use it in Python

In this tutorial you select marks with a brush and with the legend, follow countries
through fifty years of panels, and get the selected rows back in Python. It takes about
ten minutes, and follows [Facets and scales](facets-and-scales.md).

!!! note "On this page, the plots are live but Python is not"

    The plots here zoom, brush and pick colours as they do in a notebook, but nothing on
    the page runs Python. The Python results below were made when the page was built. In
    your notebook, a brush you draw reaches Python as soon as you let go.

## 1. Brush some marks

Fifty years of fertility and life expectancy, a panel per year:

```python exec="on" source="above" session="select" html="true"
from anytrellis import Trellis
from anytrellis.datasets import load

gapminder = load("gapminder")
years = Trellis(gapminder, wrap="year", cols=4, panel_height=130)
years.points(x="fertility", y="life_expect", color="region", size=5, tooltip=["country"])
years
print(years._embed_html())  # markdown-exec: hide
```

Click the plot, press **s** (or the toolbar's select button), and drag across the top-left
corner of a panel: few children, long lives. The brush selects the marks inside it in
*every* panel, and the rest fade: the same range, compared across the years.

- Drag the brush to move it.
- A brush shaped mostly sideways selects a range of x only; mostly up or down, of y only.
- A click outside it, or **Esc**, clears it.
- Press **s** again to go back to panning.

## 2. Pick colours in the legend

Click **South Asia** in the legend: its marks stay, the others fade. Shift+click
**East Asia & Pacific** to add it. With a brush too, a mark must be in both: brush a range,
then pick a colour in it. Click the only chosen entry again to clear.

## 3. Follow things across panels

A brush in one year selects different countries in each panel. To follow the *same*
countries through the years, say which column identifies them with `link=`:

```python exec="on" source="above" session="select" html="true"
followed = Trellis(gapminder, wrap="year", cols=4, panel_height=130, link="country",
                   title="Fewer than three children per woman in 1955: where they went")
followed.points(x="fertility", y="life_expect", color="region", size=5, tooltip=["country"])
followed.select(x=(0, 3), panel="1955")
followed
print(followed._embed_html())  # markdown-exec: hide
```

Here Python made the selection: `select(x=(0, 3), panel="1955")` brushes fertility below
three in the 1955 panel, and `link="country"` grows it to every row of the same countries,
in all the panels. Draw a brush in another year to follow other countries.

## 4. The selection in Python

`selection` says what is selected, whether you brushed it in the browser or called
`select()`:

```python exec="on" source="above" result="python" session="select"
print(followed.selection)
```

`selected()` gives the selected rows, as the same kind of table you gave the plot (here
Polars):

```python exec="on" source="above" session="select" html="true"
rows = followed.selected()
rows.head()
print(rows.head()._repr_html_())  # markdown-exec: hide
```

So the countries are a line of Polars away:

```python exec="on" source="above" result="python" session="select"
print(rows["country"].unique().sort().to_list())
```

`select()` with no arguments clears the selection, and `select(color=["South Asia"])`
picks colours as the legend does.

## What you learned

- **s** and a drag brush marks in every panel; a legend click picks colours.
- `link="column"` follows the things that column names across panels.
- `select()` selects from Python; `selection` and `selected()` read what is selected,
  also when you selected it in the browser.

To share one selection between *separate* plots (a scatter and a histogram of the same
cars), see [Link plots](../how-to/link.md).
