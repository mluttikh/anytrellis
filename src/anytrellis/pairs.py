"""``pairs``: a scatterplot matrix, every pair of number columns against each other.

Each column of panels is one variable on x and each row one on y, so a variable's scale is
shared along its column and its row; the diagonal shows each variable alone (a density
curve or a histogram, drawn over the variable's own range so the row's scale reads for it
too). Brushing a panel selects its rows in every panel (the rows are linked by their index
in the data), and ``selected()`` gives them as rows of the data.

The plot is a ``Trellis`` of the data reshaped: a row per pair of variables and row of the
data, faceted by the y variable (rows) and the x variable (columns).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

import numpy as np

from anytrellis.data import Column, Table
from anytrellis.plot import Trellis, _text
from anytrellis.stats import _kde
from anytrellis.styling import TAB10

Diag = Literal["auto", "density", "hist"]

ROW, COL = "_y_var", "_x_var"
"""The facet columns: each melted row's y variable and x variable."""
X, Y, KEY = "_x", "_y", "_row"
"""Each melted row's x and y values, and its row in the data (the link)."""
LO, X2 = "_lo", "_x2"
"""The diagonal's: the base of its curves and bars, and a bar's right edge."""
GRID = 128
"""Points along a diagonal density curve."""
DIAG_GREY = "#8c8c8c"
"""The diagonal's colour when the points are coloured by numbers."""


def pairs(
    data: Any,
    columns: Sequence[str] | None = None,
    *,
    color: str | None = None,
    diag: Diag | None = "auto",
    corner: bool = False,
    bins: int = 20,
    size: float = 3.0,
    opacity: float = 0.6,
    tooltip: Sequence[str] = (),
    palette: Sequence[str] | None = None,
    height: int | None = None,
    panel_height: int | None = None,
    title: str = "",
    legend: str = "auto",
    renderer: str = "auto",
) -> Pairs:
    """A scatterplot matrix: each pair of ``columns`` plotted against each other, x by
    column and y by row, with each variable alone on the diagonal.

    ```python
    from anytrellis import pairs

    p = pairs(penguins, ["bill_length_mm", "bill_depth_mm", "body_mass_g"], color="species")
    p                     # brush a panel: its rows light up in every panel
    p.selected()          # the brushed rows of the data
    ```

    Args:
        data: The table (Polars, PyArrow, pandas, DuckDB, Ibis, or a dict of arrays).
        columns: The number columns, in order (default: every number column but
            ``color``).
        color: A colour column (categories: a colour each, and a curve or a bar each on the
            diagonal; numbers: a colormap) or one colour.
        diag: The diagonal: ``"density"`` (a density curve, per colour), ``"hist"`` (a
            histogram, stacked by colour), ``"auto"`` (density with a colour column,
            otherwise a histogram) or None (empty).
        corner: Only the panels below the diagonal (each pair once), and the diagonal.
        bins: The diagonal histograms' bins.
        size: Point diameter in CSS pixels.
        opacity: The points' opacity, 0 to 1.
        tooltip: More columns shown on hover (the plotted columns and ``color`` always are).
        palette: Colours for a category colour column (default: tab10).
        height: The plot's height in CSS pixels (default: square panels).
        panel_height: Each panel's height in CSS pixels (default: square panels).
        title: A title over the plot.
        legend: As for ``Trellis``.
        renderer: As for ``Trellis``.
    """
    return Pairs(data, columns, color=color, diag=diag, corner=corner, bins=bins, size=size,
                 opacity=opacity, tooltip=tooltip, palette=palette, height=height,
                 panel_height=panel_height, title=title, legend=legend,
                 renderer=renderer)  # fmt: skip


class Pairs(Trellis):
    """A scatterplot matrix (``anytrellis.pairs``): a ``Trellis`` whose ``selected()`` gives
    rows of the data, and whose panels are named ``"<y column> · <x column>"``."""

    def __init__(
        self,
        data: Any,
        columns: Sequence[str] | None = None,
        *,
        color: str | None = None,
        diag: Diag | None = "auto",
        corner: bool = False,
        bins: int = 20,
        size: float = 3.0,
        opacity: float = 0.6,
        tooltip: Sequence[str] = (),
        palette: Sequence[str] | None = None,
        height: int | None = None,
        panel_height: int | None = None,
        title: str = "",
        legend: str = "auto",
        renderer: str = "auto",
    ) -> None:
        if diag not in ("auto", "density", "hist", None):
            raise ValueError(f"diag must be 'auto', 'density', 'hist' or None, got {diag!r}")
        if bins < 1:
            raise ValueError("bins must be at least 1")
        source = Table(data)
        from anytrellis.styling import is_color

        color_column = color if color is not None and color in source else None
        if color is not None and color_column is None and not is_color(color):
            raise ValueError(f"color={color!r} is neither a column nor a colour")
        names = _columns(source, columns, color_column)
        source.want(*names, color_column, *tooltip)  # a lazy table: read in one query
        for name in tooltip:
            source.check(name)
        super().__init__(
            None, row=ROW, col=COL, share_x="col", share_y="row", x_title="", y_title="",
            height=height, panel_height=panel_height,
            aspect=None if height or panel_height else 1.0, title=title, palette=palette,
            legend=legend, link=KEY, renderer=renderer,
        )  # fmt: skip
        self._source = source
        self._columns = names
        self._color_column = color_column
        self._tips = [n for n in (*names, color_column, *tooltip) if n is not None]
        self._keep_empty = not corner
        cat = color_column is not None and source.column(color_column).kind == "category"
        one = (palette or TAB10)[0] if color is None else color
        self._data = _melt(source, names, color_column, corner)
        self.points(x=X, y=Y, color=color_column or one, size=size, opacity=opacity,
                    name="points")  # fmt: skip
        if diag == "auto":
            diag = "density" if cat else "hist"
        if diag is None:
            self._frozen = True
            return
        by = color_column if cat else None
        shade = color_column if cat else (one if color_column is None else DIAG_GREY)
        if diag == "density":
            curves = _densities(source, names, by)
            self.band(curves, x=X, ymin=LO, ymax=Y, color=shade, opacity=0.25, name="density")
            self.line(curves, x=X, y=Y, color=shade, width=1.5, name="density line")
        else:
            bars = _histograms(source, names, by, bins)
            self.rect(bars, x=X, x2=X2, y=LO, y2=Y, color=shade, opacity=0.8, name="hist")
        self._frozen = True

    def _add(self, layer: Any) -> Any:
        if getattr(self, "_frozen", False):
            raise TypeError("a pairs() plot draws its own layers; add none to it")
        return super()._add(layer)

    def selected(self, layer: str | int | None = None) -> Any:
        """The selected rows of the data, as the same kind of table; none selected: no
        rows."""
        if layer is not None:
            raise ValueError("a pairs() plot selects rows of its data: give no layer")
        self._scene()
        points = self._layers[0]
        table = self._table(points)
        if self._current_selection() is None and self._highlight is not None:
            mask = self._highlight.get(id(points))
            if not isinstance(mask, np.ndarray):
                mask = np.zeros(table.n, dtype=bool)
        else:
            mask = self._source_mask(points)
        rows = np.unique(table.column(KEY).values[mask]).astype(np.int64)
        return self._source.take(rows)

    def _tooltip(self, layer_index: int, instance: int, of: str | None = None) -> list[list[str]]:
        self._scene()
        entry = self._history.get((layer_index, of)) if of else None
        _, table, geom, _ = entry or self._sent[layer_index]
        if geom is None:
            return []
        row = int(geom.rows[instance])
        if KEY in table:  # a point: its row of the data
            at = int(table.column(KEY).values[row])
            return [[n, _text(self._source.raw(n)[at])] for n in self._tips]
        if COL not in table:  # cells of dense points
            return super()._tooltip(layer_index, instance, of)
        var = str(table.column(COL).values[row])
        x = table.column(X).values[row]
        if X2 in table:
            tips = [[var, f"{_text(x)} – {_text(table.column(X2).values[row])}"],
                    ["count", _text(table.raw("count")[row])]]  # fmt: skip
        else:
            tips = [[var, _text(x)], ["density", f"{table.column('density').values[row]:.4g}"]]
        if self._color_column is not None and self._color_column in table:
            tips.append([self._color_column, _text(table.raw(self._color_column)[row])])
        return tips


def _columns(source: Table, columns: Sequence[str] | None, color: str | None) -> list[str]:
    if columns is None:
        names = [n for n in source.names if n != color and source.kind(n) == "number"]
    else:
        names = list(dict.fromkeys(columns))
    for name in names:
        kind = source.kind(name)
        if kind != "number":
            raise ValueError(f"pairs() plots number columns; {name!r} holds {kind}s")
    if len(names) < 2:
        raise ValueError(f"pairs() needs at least two number columns, got {names}")
    return names


def _category(name: str, levels: Sequence[str], codes: np.ndarray) -> Column:
    labels = np.array(list(levels), dtype=object)
    return Column(name, "category", labels[codes], tuple(levels), codes)


def _melt(source: Table, names: list[str], color: str | None, corner: bool) -> Table:
    """A row per pair of variables (y, x) and row of the data: panels below the diagonal,
    and above it unless ``corner``."""
    n = source.n
    pairs = [(i, j) for i in range(len(names)) for j in range(len(names))
             if i > j or (i < j and not corner)]  # fmt: skip
    values = [source.column(name).values for name in names]
    m = len(pairs)
    y = np.concatenate([values[i] for i, _ in pairs])
    x = np.concatenate([values[j] for _, j in pairs])
    row_codes = np.repeat(np.array([i for i, _ in pairs], dtype=np.int64), n)
    col_codes = np.repeat(np.array([j for _, j in pairs], dtype=np.int64), n)
    key = np.tile(np.arange(n, dtype=np.float64), m)
    arrays: dict[str, Any] = {X: x, Y: y, KEY: key, ROW: row_codes, COL: col_codes}
    columns = {
        X: Column(X, "number", x),
        Y: Column(Y, "number", y),
        KEY: Column(KEY, "number", key),
        ROW: _category(ROW, names, row_codes),
        COL: _category(COL, names, col_codes),
    }
    if color is not None:
        c = source.column(color)
        tiled = np.tile(c.values, m)
        arrays[color] = tiled
        columns[color] = (
            Column(color, c.kind, tiled, c.levels, np.tile(c.level_codes(), m))
            if c.kind == "category"
            else Column(color, c.kind, tiled)
        )
    table = Table(arrays)
    table._cache.update(columns)
    return table


def _diagonal(names: list[str], i: int, size: int) -> dict[str, Any]:
    """The facet columns of ``size`` rows of variable ``i``'s diagonal panel."""
    return {ROW: [names[i]] * size, COL: [names[i]] * size}


def _span(v: np.ndarray) -> tuple[float, float]:
    finite = v[np.isfinite(v)]
    if not len(finite):
        return 0.0, 1.0
    lo, hi = float(finite.min()), float(finite.max())
    return lo, hi if hi > lo else lo + 1.0


def _groups(source: Table, by: str | None) -> list[tuple[str | None, np.ndarray]]:
    """The rows of each colour (or all rows), with the colour's label."""
    if by is None:
        return [(None, np.ones(source.n, dtype=bool))]
    c = source.column(by)
    codes = c.level_codes()
    return [(level, codes == k) for k, level in enumerate(c.levels)]


def _densities(source: Table, names: list[str], by: str | None) -> dict[str, Any]:
    """Each variable's density curves (one per colour, each weighted by its share of the
    rows), over the variable's range, from its low end up to its high end at the highest."""
    parts: dict[str, list[Any]] = {k: [] for k in (ROW, COL, X, LO, Y, "density")}
    if by is not None:
        parts[by] = []
    groups = _groups(source, by)
    for i, name in enumerate(names):
        v = source.column(name).values
        lo, hi = _span(v)
        at = np.linspace(lo, hi, GRID)
        curves = []
        total = np.isfinite(v).sum()
        for level, rows in groups:
            s = np.sort(v[rows & np.isfinite(v)])
            if len(s) < 2 or s[-1] == s[0]:
                continue
            bw = float(np.std(s, ddof=1)) * len(s) ** -0.2
            curves.append((level, _kde(s, at, bw) * len(s) / total))
        top = max((float(d.max()) for _, d in curves), default=0.0) or 1.0
        for level, d in curves:
            for key, value in _diagonal(names, i, GRID).items():
                parts[key] += value
            parts[X].append(at)
            parts[LO].append(np.full(GRID, lo))
            parts[Y].append(lo + d / top * (hi - lo))
            parts["density"].append(d)
            if by is not None:
                parts[by] += [level] * GRID
    return _table(parts)


def _histograms(source: Table, names: list[str], by: str | None, bins: int) -> dict[str, Any]:
    """Each variable's histogram (stacked by colour), from its low end up to its high end at
    the highest bar."""
    parts: dict[str, list[Any]] = {k: [] for k in (ROW, COL, X, X2, LO, Y, "count")}
    if by is not None:
        parts[by] = []
    groups = _groups(source, by)
    for i, name in enumerate(names):
        v = source.column(name).values
        lo, hi = _span(v)
        edges = np.linspace(lo, hi, bins + 1)
        counts = [np.histogram(v[rows], bins=edges)[0] for _, rows in groups]
        stacked = np.cumsum(counts, axis=0)
        scale = (hi - lo) / (stacked[-1].max() or 1)
        for k, (level, _) in enumerate(groups):
            keep = counts[k] > 0
            size = int(keep.sum())
            for key, value in _diagonal(names, i, size).items():
                parts[key] += value
            below = stacked[k - 1] if k else np.zeros(bins, dtype=np.int64)
            parts[X].append(edges[:-1][keep])
            parts[X2].append(edges[1:][keep])
            parts[LO].append(lo + below[keep] * scale)
            parts[Y].append(lo + stacked[k][keep] * scale)
            parts["count"].append(counts[k][keep])
            if by is not None:
                parts[by] += [level] * size
    return _table(parts)


def _table(parts: dict[str, list[Any]]) -> dict[str, Any]:
    """The columns of the diagonal's rows: numbers from arrays, the rest as text."""
    out: dict[str, Any] = {}
    for key, value in parts.items():
        if key in (ROW, COL) or not value or not isinstance(value[0], np.ndarray):
            out[key] = np.array(value, dtype=object) if value else np.array([], dtype=object)
        else:
            out[key] = np.concatenate(value)
    for key in (X, X2, LO, Y, "count", "density"):
        if key in out and out[key].dtype == object:  # no curves or bars at all
            out[key] = np.zeros(0)
    return out
