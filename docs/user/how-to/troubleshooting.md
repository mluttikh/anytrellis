# Fix a plot that doesn't show

## Nothing appears under the cell, or only text

The notebook shows the plot's text form, `Trellis(...)`, when it cannot show widgets.

- **JupyterLab and Jupyter Notebook**: anywidget needs JupyterLab 4 or Notebook 7. Update
  them, and restart the server (not only the kernel) after installing anytrellis.
- **VS Code**: install the Jupyter extension, and pick the kernel of the environment
  anytrellis is installed in.
- **The kernel and the browser disagree**: after `pip install` in a running notebook,
  restart the kernel and reload the page.

## The plot is blank, or says it could not draw

Hover over the plot: its bottom-right corner says which renderer draws. If it says Canvas
2D on a machine with a GPU, or the plot is blank:

- The browser may have no GPU access (remote desktops, some virtual machines, a GPU
  blocklist). Canvas 2D still draws, more slowly with many marks.
- Force a renderer to compare: `Trellis(..., renderer="canvas2d")` or `"webgl2"`.
- Open the browser's console (F12) and look for messages starting with `[anytrellis]`.

## A column is not found

The message lists the table's columns. Column names are case-sensitive, and each mark
takes names, not the values: `x="weight"`, not `x=df["weight"]`.

## Colours are a scale, not categories

A column of numbers gets a colour scale. `t.as_category("year")` reads it as categories,
for a colour per value. See [Colours, legends and order](colours.md).

## Bars or a histogram on a log scale fail

Marks drawn from zero have no place on a log y. Use points or lines, or a linear y. See
[Use a log scale](log.md).

## Scrolling scrolls the page, not the plot

Click the plot first: before a click, scrolling scrolls the page, so a plot in a long
notebook doesn't catch the wheel by accident.

## Keys do something else

Keys go to the plot only while it has focus (after a click), and stay there, so JupyterLab's
own shortcuts don't also act on them. Click outside the plot to give the keys back.

## The page from `save_html` is very large

It holds the data. Sample the rows, or summarise them, before saving. See
[Share a plot](share.md).

## Still stuck

Open an [issue](https://github.com/mluttikh/anytrellis/issues) with the code, the notebook
(JupyterLab, VS Code or marimo, and its version), the browser, and the renderer the plot's
corner names when you hover over it.
