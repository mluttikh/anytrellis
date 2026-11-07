# At a glance

The parts of a plot, and what each one does.

![A trellis of three panels, with its parts numbered](assets/gallery/glance.png)

```python
Trellis(cars, wrap="origin", cols=2, panel_height=150,
        title="Fuel use and weight, by origin").points(
    x="weight", y="mpg", color="cylinders", size=5)
```

1. **Title**: `title=`.
2. **Toolbar**: select, box zoom, fit y, reset and full screen. Each has a key; see
   [Mouse and keys](reference/mouse-and-keys.md#the-toolbar).
3. **Strip**: the value of the facet column for the panel under it (`wrap=`, or `row=`
   and `col=` for a grid). With a panel opened, it holds *All panels* and the previous and
   next buttons. See [Choose a facet layout](how-to/layout.md).
4. **Panel**: the rows with that value. Scroll to zoom, drag to pan, double-click to see
   it alone. See [Mouse and keys](reference/mouse-and-keys.md).
5. **Y axis**: shared by every panel, so the heights compare across them; only the outer
   panels label it. Scroll or drag on it to zoom or pan y alone. See
   [Share or free the scales](how-to/scales.md).
6. **X axis**: the same, for x.
7. **Legend**: a colour per category, or a colour scale for numbers as here. Click an
   entry to select its marks. See [Colours, legends and order](how-to/colours.md).
8. **Renderer**: WebGPU, WebGL2 or Canvas 2D, shown when the pointer is over the plot. See
   [How the plot is drawn](explanation/drawing.md).
