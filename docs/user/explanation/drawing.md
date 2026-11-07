# How the plot is drawn

## One canvas, many viewports

A trellis of a hundred panels is not a hundred plots. anytrellis draws every panel into one
canvas: each panel is a viewport, a rectangle with its own transform from data to pixels.
The marks are uploaded to the GPU once, as instances (a point, a line segment, a bar), and
each panel draws its share of them through its viewport.

Zooming or panning changes a few numbers per panel, the transforms, and redraws. Nothing
is sent again, and nothing is recomputed in Python. That is why a plot of a million
points zooms as smoothly as one of a hundred.

The canvas sits between two others: one behind it with the panels' backgrounds, grid lines
and axes, and one in front with the brush, the crosshair and the tooltip's highlight.
Those are drawn with the browser's 2D canvas, which is fast for the few hundred shapes they
hold.

## Three renderers

| Renderer | Draws with | Falls back when |
| --- | --- | --- |
| WebGPU | the GPU, through the newest browser API | the browser or the machine doesn't offer it |
| WebGL2 | the GPU, through the older, universal API | there is no usable GPU, or the context is lost |
| Canvas 2D | the CPU | never: it always works |

The plot tries them in this order; hover over it, and its bottom-right corner says which
one draws.
`renderer=` picks one, which helps compare them or work around a driver problem.

## When a GPU context is lost

A browser keeps a limited number of GPU contexts: Chrome keeps 16 WebGL contexts per page,
and phones fewer. When a page makes more, the browser drops the oldest. anytrellis then
draws that plot with Canvas 2D: it keeps working, without the GPU.

A page of many plots, such as these docs, starts each plot only when it comes near the
screen, so a reader who never scrolls to the end doesn't use contexts for plots they don't
see.

## Data from Python

When a plot is shown, Python reads only the columns its layers use, once, computes the
summaries (`hist`, `box`, `density`, `smooth`) per panel, and sends the result to the
browser as binary arrays. The widget keeps them: changing the zoom, the brush or the panel
opened never sends the data again. A page from `save_html` holds the same arrays, so it
draws exactly as the notebook did.
