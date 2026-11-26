# Upgrading

What to change in your code when you upgrade anytrellis. While anytrellis is 0.x, a
minor version (0.1 to 0.2) may change the API; each change is listed here with the code
before and after.

## Unreleased

No code stops working; figures look different.

**A figure's plots line up.** Plots side by side (`a | b`) or one under another
(`a / b`, `concat()`) have their panels lined up: the panels' edges in a column, their
tops in a row, and in a row the plots whose height is free as high as each other. Their
panels may move, or get narrower or higher than in 0.8. To keep the 0.8 layout:

```python
# 0.8: each plot laid out on its own
scatter | counts

# now: the same
concat(scatter, counts, align=False)
```

## 0.8.0

No code stops working. Two things a reader does work differently:

- **With select (or the new lasso) on, a click on a mark selects it**; a click on no mark
  still clears the selection, as before.
- **In a panel opened (or a plot of one panel), the arrow keys step through its marks**,
  showing each one's tooltip; in a grid they still move from panel to panel.

`save_png` takes `dpi=` for the printed size (`dpi=300`); `scale=` still works, but not
both together. `stats()` now gives the panels' statistics of any plot, not only of a paged
wrap.

## 0.7.0

No code stops working. Tooltips have a title line and a row a value, and in the minimal
and framed themes text is a pixel smaller in narrow panels and larger in an opened one
(`Theme(font_size=12)` keeps it at 12 px).

**Of a panel shape and a height set after the plot is made, the later one decides.** A
height given to the constructor still sets the panels' height over `aspect=` given with
it; but `t.aspect = 1` now lets a height go, and `t.panel_height = 200` lets a shape go,
as the new settings panel does:

```python
t = Trellis(cars, wrap="origin", panel_height=200)

# 0.6: the panels stay 200 px high
t.aspect = 1

# now: square panels; to keep the height, set it again
t.panel_height = 200
```

`t.title`, `t.subtitle`, `t.caption`, `t.height` and `t.panel_height` now redraw a shown
plot when set, and a height that isn't a positive number of pixels is refused
(`ValueError`).

## 0.6.0

No code stops working; the default look changes.

**Plots are drawn in the minimal theme.** Panels have no fill, strips read as titles, the
grid is fainter and runs across y only (across x too for points), the y title sits level
over the plot, a grid's row labels are level, a time axis has no title unless you give one,
and category colours come from Petroff's palette instead of tab10. To keep the old look, or
only its colours:

```python
# 0.5: filled panels and strips, a full grid, tab10
Trellis(cars, wrap="origin")

# now: the same
Trellis(cars, wrap="origin", theme="classic")

# the new look with the old colours
Trellis(cars, wrap="origin", palette="tab10")
```

## 0.5.0

No code stops working, and plots show what they did. New: `as_category()` reads a number
column as categories, so a column cast to text for that (`pl.col("year").cast(pl.String)`)
no longer needs to be.

## 0.4.0

No code stops working; one change in what a plot shows.

**Several facet columns get nested strips.** A plot faceted by a list of columns shows a
strip per column, each spanning the panels next to each other that share its level, not
one strip per panel naming the levels together. To keep the old strips:

```python
# 0.3: one strip per panel, "Adelie · Biscoe"
Trellis(penguins, wrap=["species", "island"])

# 0.4: the same
Trellis(penguins, wrap=["species", "island"], strips="joined")
```

## 0.3.0

No code stops working; two changes in what a plot shows, or when it reads its data.

**Long lines and dense points are drawn at the level of detail shown.** A panel of more
than 20,000 points of a line sends each series thinned to what its pixels show, and a
panel of more than 100,000 points is drawn as cells, coloured by the points in them. Zoom
in to see them in more detail, down to every point. Selections and `selected()` still use
every row; a saved page and an image show the detail shown
([Plot large data](../how-to/large.md)).

**A lazy table is read when the plot is first drawn**, not when the plot is made: a Polars
`LazyFrame`, a DuckDB relation or an Ibis table, with only the columns the plot uses. A
table that changes in between is drawn as it is then. To plot the rows as they are when
the plot is made, read them first:

```python
# 0.2: the rows as they were when the plot was made
Trellis(rel, wrap="station")

# 0.3: the same
Trellis(rel.pl(), wrap="station")   # a DuckDB relation, read (lazy.collect() for Polars)
```

Everything else in 0.3 is new: tables read a page at a time from a database
(`load="pages"`), a page per level of a column (`page=`), `pairs()` and `aspect=`. See the
[changelog](changelog.md).

## 0.2.0

One change in what a plot shows; no code stops working.

**A wrap of more than 100 panels pages.** It shows 6 by 4 panels at a time, with a bar to
turn the pages, sort and filter them ([Page through many panels](../how-to/pages.md)).
To draw every panel at once, as 0.1 did:

```python
# 0.1: all 300 panels in one grid
Trellis(df, wrap="station")

# 0.2: the same
Trellis(df, wrap="station", rows="all")
```

Everything else in 0.2 is new: images from the toolbar and from Python (`save_png`,
`save_svg`), violins, error bars, step lines and pages of panels. See the
[changelog](changelog.md).

## 0.1.0

The first release: nothing to change.
