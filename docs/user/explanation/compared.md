# Compared with other libraries

anytrellis does one kind of plot: the trellis, interactive, in a notebook. Many libraries
facet; this page says where anytrellis fits among them.

| Library | Facets | Interactive in a notebook | Large data | Output |
| --- | --- | --- | --- | --- |
| **anytrellis** | wrap, grid; shared, per row or column, free, log | zoom, pan, brush and legend selection linked across panels, selection back to Python | millions of marks, hundreds of panels, in the browser's GPU | widget; one-file HTML page |
| seaborn, matplotlib | `col=`, `row=`, `col_wrap=` | no (static images) | limited by the image | images, PDF, SVG |
| ggplot2, plotnine | `facet_wrap`, `facet_grid` | no | limited by the image | images, PDF, SVG |
| Vega-Altair | `row`, `column`, `facet` channels | selections and zoom, declared per chart | 5,000 rows by default; more with a data server | widget; HTML, images |
| Plotly | `facet_col`, `facet_row`, `facet_col_wrap` | zoom and pan per subplot axis, linked where axes match | WebGL traces for many points | widget; HTML, images |
| hvPlot, HoloViews | `by=`, `subplots=`, layouts and grids | zoom, pan, linked selections | Datashader renders billions of points in the kernel | widget; HTML, apps |

## When to use anytrellis

- You want to **compare groups** side by side, and explore them by zooming and selecting.
- Your data is **large**: hundreds of thousands to millions of rows, or many panels.
- You want the **selection back in Python** as rows, to look at or to filter further.
- You want a **page to share** that keeps working without a kernel.

## When to use something else

- **A figure for print** or a paper: seaborn, matplotlib, ggplot2 or plotnine give finer
  control over every element and write vector images.
- **One plot, not a grid**, with many kinds of chart: Altair, Plotly or Bokeh have far more
  chart types.
- **Billions of points**: Datashader (with hvPlot) renders them to an image in the kernel.
- **A dashboard or an app**: Panel, Dash, Streamlit or Shiny lay out widgets and plots; an
  anytrellis plot can be one of them where anywidget is supported.

## Using them together

anytrellis takes the same tables as the others (Polars, pandas, PyArrow), so exploring
with anytrellis and drawing the final figure with seaborn or ggplot2 is a common split:
`selected()` hands the rows you found to the next step.
