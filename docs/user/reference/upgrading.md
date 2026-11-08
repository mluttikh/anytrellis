# Upgrading

What to change in your code when you upgrade anytrellis. While anytrellis is 0.x, a
minor version (0.1 to 0.2) may change the API; each change is listed here with the code
before and after.

## Unreleased

No code stops working; one change in what a plot shows.

**Several facet columns get nested strips.** A plot faceted by a list of columns shows a
strip per column, each spanning the panels next to each other that share its level, not
one strip per panel naming the levels together. To keep the old strips:

```python
# 0.3: one strip per panel, "Adelie · Biscoe"
Trellis(penguins, wrap=["species", "island"])

# next: the same
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
