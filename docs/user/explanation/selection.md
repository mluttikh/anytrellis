# How selection works

A selection in anytrellis is a description, not a list of marks: a range of x, of y or of
both, the colours chosen in the legend, and the panel it was drawn in. The browser and
Python each apply that description to the rows, so a selection made in one is understood
by the other.

## The brush is a range in data units

A brush is stored as `{"x": (low, high), "y": (low, high), "color": [...], "panel": ...}`,
in the data's own units: numbers, datetimes, or categories. That is why the same brush
selects in every panel: it is the same range, compared across the panels. It is also why
`select(x=(2, 4))` in Python and a drag in the browser are the same thing.

A mark is selected when it meets the range:

- a point, when it is inside;
- a line or area segment, when either end is inside;
- a bar or rect, when it overlaps;
- a box, when its body or lines are met;
- a histogram bin, when it overlaps.

The legend's colours narrow the brush: a mark must meet the range *and* have a chosen
colour. Marks coloured by another column, or by none, fade, because they have none of the
chosen colours.

## Keys follow things across panels

With `link="country"`, a brush first selects the rows it meets in the panel it was drawn
in, and then every row sharing their country, in all panels and layers that have the
column. A range in 1955 becomes a set of countries in every year.

## Selection in Python

The browser sends the brush to Python when you let go of it. Python applies the same
description to the table, and `selected()` returns those rows as your own kind of table.
Summaries are selected whole: a brush that meets a histogram bin or a box selects all the
rows it stands for.

## Linked plots

`link(a, b)` connects separate plots through Python. When one plot's selection changes,
Python works out its rows and sends each other plot which of *its* marks those rows are:
a bit per row for points and lines, and for each histogram bar the share of its count
that is selected. That is why linking needs a running kernel, and why a histogram's bars
fill partly while a scatter's points are either bright or faded.

While you drag, the brush is sent to Python every 50 milliseconds, so the other plots
follow it as it moves.

## Why fade, not hide

The unselected marks fade rather than disappear, so the selection is seen against the
whole: where the selected rows sit among the rest is often the point.
