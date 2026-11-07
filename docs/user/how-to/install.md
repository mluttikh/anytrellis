# Install anytrellis

anytrellis needs Python 3.12 or newer. Install it into the environment your notebooks run
in:

=== "pip"

    ```bash
    pip install anytrellis
    ```

=== "uv"

    ```bash
    uv add anytrellis
    ```

=== "conda / mamba"

    anytrellis is not on conda-forge yet. Install it with pip into the conda environment:

    ```bash
    pip install anytrellis
    ```

It brings NumPy, narwhals (which reads your tables) and anywidget (which shows the plot in
notebooks). It does not bring a table library: you plot the Polars, pandas or PyArrow
tables you already use.

## With the example datasets

The [bundled datasets](../reference/datasets.md) load as Polars tables when Polars is
installed. The `examples` extra brings it:

```bash
pip install "anytrellis[examples]"
```

## Where it runs

| Notebook | Works | Notes |
| --- | --- | --- |
| JupyterLab 4, Jupyter Notebook 7 | Yes | |
| VS Code (Jupyter extension) | Yes | |
| marimo | Yes | See [Use anytrellis in marimo](marimo.md) |
| Google Colab | Should | anywidget supports it; not tested here |
| A page without Python | Yes | [`save_html`](share.md) |

## Check that it works

Run this in a notebook cell. A plot of three panels should appear under it:

```python
from anytrellis import Trellis
from anytrellis.synthetic import sensors

Trellis(sensors(stations=3), wrap="station").line(x="time", y="temp", color="sensor")
```

Hover over the plot: its bottom-right corner shows which renderer draws it, WebGPU, WebGL2
or Canvas 2D.
If no plot appears, see [Fix a plot that doesn't show](troubleshooting.md).
