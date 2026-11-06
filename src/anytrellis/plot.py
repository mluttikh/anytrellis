"""``Trellis``: a plot of panels, one per facet level, each drawn with the same layers.

The plot is a plain Python object: layers are added with methods that return the plot (so
calls chain), and its widget is made when it is first shown. Python owns the tables, the
facets, the scales and the geometry; it describes them in a small JSON spec plus binary
buffers, which the browser draws on the GPU.
"""

from __future__ import annotations

import base64
import html
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import numpy as np

from anytrellis.codec import Buffers
from anytrellis.data import Table
from anytrellis.facets import Grid, Order, Summary, build_grid, ordered_levels
from anytrellis.layers import (
    FACET_MODES,
    FacetMode,
    Geometry,
    Layer,
    Position,
    axis_values,
    bar_geometry,
    expand,
    line_geometry,
    point_geometry,
    series_codes,
    step_of,
)
from anytrellis.scales import AxisKind, Extent, Share, domains, group_ids, share_mode
from anytrellis.styling import (
    CONTEXT_COLOR,
    MISSING_COLOR,
    TAB10,
    colormap_rgba,
    is_color,
    palette_colors,
    rgba,
)

if TYPE_CHECKING:
    from anytrellis.widget import TrellisWidget

SPEC_VERSION = 1
RENDERERS = ("auto", "webgpu", "webgl2", "canvas2d")
LEGENDS = ("auto", "bottom")
_STATIC = Path(__file__).parent / "static"


class Trellis:
    """A trellis of panels: one per level of the facet columns, each drawn with the same
    layers, on shared scales unless told otherwise.

    ```python
    from anytrellis import Trellis

    t = Trellis(df, wrap="station")                  # or row="site", col="year"
    t.line(x="time", y="temp", color="sensor")
    t                                                # scroll to zoom: shared axes zoom together
    ```

    Args:
        data: The table the layers draw (Polars, PyArrow, pandas, DuckDB, or a dict of
            arrays). A layer may bring its own; a layer whose data lacks the facet columns
            is drawn in every panel.
        row: Facet column(s) whose levels are the grid's rows.
        col: Facet column(s) whose levels are the grid's columns.
        wrap: Facet column(s) whose levels are panels wrapped into ``cols`` columns (not
            with ``row`` or ``col``).
        cols: Columns of a wrap (default: about the square root of the panels).
        share_x: Share the x scale: ``True`` (all panels), ``"row"``, ``"col"`` or
            ``False`` (each panel its own).
        share_y: The same for y.
        height: The plot's height in CSS pixels (default: from ``panel_height``).
        panel_height: Each panel's height in CSS pixels (default: from its width).
        title: A title over the plot.
        x_title: The x axis title (default: the x column's name).
        y_title: The y axis title (default: the y column's name).
        palette: Colours for category colour columns (default: tab10).
        legend: ``"auto"``: in a wrap's empty cells after its last panel when it fits there,
            under the plot otherwise; ``"bottom"``: always under the plot.
        renderer: ``"auto"`` (WebGPU, then WebGL2, then Canvas 2D), or one of them.
    """

    def __init__(
        self,
        data: Any = None,
        *,
        row: str | Sequence[str] | None = None,
        col: str | Sequence[str] | None = None,
        wrap: str | Sequence[str] | None = None,
        cols: int | None = None,
        share_x: bool | str = True,
        share_y: bool | str = True,
        height: int | None = None,
        panel_height: int | None = None,
        title: str = "",
        x_title: str | None = None,
        y_title: str | None = None,
        palette: Sequence[str] | None = None,
        legend: str = "auto",
        renderer: str = "auto",
    ) -> None:
        self._data = None if data is None else Table(data)
        self._row = _names(row)
        self._col = _names(col)
        self._wrap = _names(wrap)
        if self._wrap and (self._row or self._col):
            raise ValueError("use wrap= alone, or row= and/or col= (a grid), not both")
        if cols is not None and cols < 1:
            raise ValueError("cols must be at least 1")
        self._cols = cols
        self._share: dict[str, Share] = {"x": share_mode(share_x), "y": share_mode(share_y)}
        self._orders: dict[str, Order] = {}
        self._layers: list[Layer] = []
        self._tables: dict[int, Table] = {}
        self.height = height
        self.panel_height = panel_height
        self.title = title
        self.x_title = x_title
        self.y_title = y_title
        self.palette = list(palette) if palette else None
        if legend not in LEGENDS:
            raise ValueError(f"legend must be one of {LEGENDS}, got {legend!r}")
        self.legend = legend
        if renderer not in RENDERERS:
            raise ValueError(f"renderer must be one of {RENDERERS}, got {renderer!r}")
        self.renderer = renderer
        self._widget: TrellisWidget | None = None
        self._focus: str | None = None
        self._scene_cache: tuple[dict[str, Any], Buffers] | None = None
        self._geometry: list[tuple[Layer, Table, Geometry | None]] = []

    # ---- layers -------------------------------------------------------------------------

    def line(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        group: str | Sequence[str] | None = None,
        width: float = 1.5,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Lines through the points of each series, sorted by x.

        Args:
            data: The layer's table (default: the plot's).
            x: The x column.
            y: The y column.
            color: A colour column (one line per category; numbers along a colormap) or
                one colour.
            group: Column(s) whose combinations are separate lines (besides ``color``).
            width: Line width in CSS pixels.
            opacity: 0 to 1.
            facet: ``"auto"`` (each row in its panel; every panel when the data has no facet
                columns), ``"include"``, ``"all"`` (every row in every panel) or
                ``"exclude"`` (each panel shows the other panels' rows: grey context).
            tooltip: Columns shown on hover, besides x and y.
            name: The layer's name.
        """
        layer = Layer("line", name or self._name("line"), data, x, y, color, _names(group),
                      facet, width=width, opacity=opacity, tooltip=list(tooltip))  # fmt: skip
        return self._add(layer)

    def points(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        size: float = 5.0,
        opacity: float = 0.85,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """A point per row.

        Args:
            data: The layer's table (default: the plot's).
            x: The x column.
            y: The y column.
            color: A colour column or one colour.
            size: Diameter in CSS pixels.
            opacity: 0 to 1.
            facet: As for ``line``.
            tooltip: Columns shown on hover, besides x and y.
            name: The layer's name.
        """
        layer = Layer("points", name or self._name("points"), data, x, y, color, (),
                      facet, size=size, opacity=opacity, tooltip=list(tooltip))  # fmt: skip
        return self._add(layer)

    def bars(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        position: Position = "stack",
        width: float = 0.8,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Bars from 0 to y at each x (categories, numbers or times).

        Args:
            data: The layer's table (default: the plot's).
            x: The x column.
            y: The bar heights.
            color: A colour column or one colour.
            position: With a category colour: ``"stack"`` (default), ``"dodge"`` (side by
                side) or ``"identity"`` (overlapping).
            width: Bar width as a fraction of the step between x values.
            opacity: 0 to 1.
            facet: As for ``line``.
            tooltip: Columns shown on hover, besides x and y.
            name: The layer's name.
        """
        if position not in ("stack", "dodge", "identity"):
            raise ValueError(f"position must be 'stack', 'dodge' or 'identity', got {position!r}")
        if not 0 < width <= 1:
            raise ValueError("width must be in (0, 1]")
        return self._add(Layer("bars", name or self._name("bars"), data, x, y, color, (),
                               facet, opacity=opacity, position=position, bar_width=width,
                               tooltip=list(tooltip)))  # fmt: skip

    def rule(
        self,
        *,
        x: Any = None,
        y: Any = None,
        color: str = "#6b7480",
        width: float = 1.0,
        dash: Sequence[float] = (),
        name: str | None = None,
    ) -> Self:
        """Reference lines across every panel: vertical at ``x``, or horizontal at ``y``
        (a value or a list of values).

        Args:
            x: Position(s) of vertical lines.
            y: Position(s) of horizontal lines.
            color: Their colour.
            width: Line width in CSS pixels.
            dash: A dash pattern in pixels, e.g. ``(4, 3)``.
            name: The layer's name.
        """
        if (x is None) == (y is None):
            raise ValueError("give rule() x= or y=")
        values = x if x is not None else y
        values = list(values) if isinstance(values, list | tuple | np.ndarray) else [values]
        rgba(color)
        layer = Layer("rule", name or self._name("rule"), axis="x" if x is not None else "y",
                      values=values, color=color, width=width, dash=list(dash))  # fmt: skip
        return self._add(layer)

    def share(self, x: bool | str | None = None, y: bool | str | None = None) -> Self:
        """Share scales across panels: ``True`` (all), ``"row"``, ``"col"`` or ``False``
        (each panel its own). Panels that share a scale also zoom together."""
        if x is not None:
            self._share["x"] = share_mode(x)
        if y is not None:
            self._share["y"] = share_mode(y)
        return self._changed()

    def order(
        self,
        column: str,
        levels: Sequence[Any] | None = None,
        *,
        by: Summary | None = None,
        of: str | None = None,
        descending: bool = False,
    ) -> Self:
        """Order a category column's levels: as ``levels`` lists them (the rest after), or
        by a summary of a column per level (Cleveland's ordering by the median, for one),
        rather than alphabetically. This orders panels (facet columns), bands on an axis
        and colours alike.

        ```python
        t.order("site", by="median", of="yield")
        t.order("month", ["Jan", "Feb", "Mar"])
        ```
        """
        if by is None and levels is None:
            raise ValueError("order: give levels, or by= (with of=)")
        if by is not None and by not in ("median", "mean", "min", "max", "sum", "count"):
            raise ValueError(f"by must be median, mean, min, max, sum or count, got {by!r}")
        given = tuple(str(v) for v in levels) if levels is not None else None
        self._orders[column] = Order(given, by, of, descending)
        return self._changed()

    # ---- opening a panel ----------------------------------------------------------------

    def panels(self) -> list[str]:
        """The panels' names, in order: each panel's level of every facet column, joined by
        `` · `` (``"north · s1"`` in a grid of region by sensor)."""
        spec, _ = self._scene()
        return [_panel_name(p, i) for i, p in enumerate(spec["panels"])]

    def open(self, *panel: Any) -> Self:
        """Show one panel alone, on the whole plot (as a double-click on it does): by its
        name (see ``panels()``) or by its level of each facet column.

        ```python
        t.open("station 3")          # wrap="station"
        t.open("north", "s1")        # row="region", col="sensor"
        ```

        The zoom stays linked: back in the grid, the panels sharing its scales show what
        the opened panel showed. ``close()`` (or Backspace, Esc, a double-click) goes back.
        """
        names = self.panels()
        if len(names) < 2:
            raise ValueError("this plot has one panel: there is nothing to open")
        name = " · ".join(str(k) for k in panel) if len(panel) != 1 else str(panel[0])
        if name not in names:
            shown = ", ".join(repr(n) for n in names[:8]) + (", ..." if len(names) > 8 else "")
            raise ValueError(f"no panel {name!r}; the panels are {shown}")
        self._set_focus(name)
        return self

    def close(self) -> Self:
        """Back to all panels from an opened one."""
        self._set_focus(None)
        return self

    @property
    def focused(self) -> str | None:
        """The opened panel's name (opened here or in the browser), or ``None``."""
        if self._widget is not None:
            return self._widget.open_panel
        return self._focus

    def _set_focus(self, name: str | None) -> None:
        self._focus = name
        if self._widget is not None:
            self._widget.open_panel = name

    # ---- showing ------------------------------------------------------------------------

    @property
    def widget(self) -> TrellisWidget:
        """The widget that shows the plot: made the first time the plot is shown or this is
        read, then the same one."""
        if self._widget is None:
            from anytrellis.widget import TrellisWidget

            spec, _ = self._scene()
            state = {"_spec": spec, "renderer": self.renderer, "open_panel": self._focus}
            self._widget = TrellisWidget(self, state)
        return self._widget

    def _repr_mimebundle_(self, **kwargs: Any) -> Any:
        return self.widget._repr_mimebundle_(**kwargs)

    def _display_(self) -> Any:
        """What marimo shows: the widget."""
        import marimo as mo

        return mo.ui.anywidget(self.widget)

    def to_html(self, *, title: str | None = None) -> str:
        """The plot as a standalone HTML page: data and code inside, no kernel needed."""
        script = _STATIC / "standalone.js"
        css = _STATIC / "widget.css"
        if not script.exists():
            raise FileNotFoundError(
                "the JavaScript bundle is not built: run `npm run build` in js/"
            )
        spec, buffers = self._scene()
        payload = {
            "spec": spec,
            "buffers": {k: base64.b64encode(v).decode("ascii") for k, v in buffers.data.items()},
            "renderer": self.renderer,
            "focus": self.focused,
        }
        data = json.dumps(payload).replace("</", "<\\/")
        name = html.escape(title or self.title or "anytrellis")
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{name}</title>"
            "<style>body{margin:16px;font-family:system-ui,sans-serif;background:#fff}"
            "@media (prefers-color-scheme: dark){body{background:#12171d}}"
            f"{css.read_text()}</style>"
            "</head><body><div class='anytrellis-embed'>"
            f"<script type='application/json'>{data}</script></div>"
            f"<script>{script.read_text()}</script></body></html>"
        )

    def save_html(self, path: str | Path, *, title: str | None = None) -> Path:
        """Write ``to_html`` to a file; returns its path."""
        out = Path(path)
        out.write_text(self.to_html(title=title), encoding="utf-8")
        return out

    def __repr__(self) -> str:
        parts = [f"{layer.name}: {layer.mark}" for layer in self._layers]
        facets = []
        if self._row:
            facets.append(f"row={list(self._row)}")
        if self._col:
            facets.append(f"col={list(self._col)}")
        if self._wrap:
            facets.append(f"wrap={list(self._wrap)}")
        return f"Trellis({', '.join(facets) or 'one panel'}; {', '.join(parts) or 'no layers'})"

    # ---- internals ----------------------------------------------------------------------

    def _name(self, mark: str) -> str:
        taken = {layer.name for layer in self._layers}
        n = 1
        while f"{mark}{n if n > 1 else ''}" in taken:
            n += 1
        return f"{mark}{n if n > 1 else ''}"

    def _add(self, layer: Layer) -> Self:
        if layer.name in {existing.name for existing in self._layers}:
            raise ValueError(f"a layer is already named {layer.name!r}")
        if layer.facet not in FACET_MODES:
            raise ValueError(f"facet must be one of {FACET_MODES}, got {layer.facet!r}")
        if layer.mark != "rule":
            table = self._data if layer.data is None else Table(layer.data)
            if table is None:
                raise ValueError(f"{layer.mark}() needs data: give the plot or the layer a table")
            for name in [layer.x, layer.y, *layer.group, *layer.tooltip]:
                if name is not None:
                    table.column(name)
            if layer.color is not None and layer.color not in table and not is_color(layer.color):
                raise ValueError(f"color={layer.color!r} is neither a column nor a colour")
            self._tables[id(layer)] = table
        self._layers.append(layer)
        return self._changed()

    def _changed(self) -> Self:
        self._scene_cache = None
        if self._widget is not None:
            spec, _ = self._scene()
            self._widget._spec = spec
        return self

    def _table(self, layer: Layer) -> Table:
        return self._tables[id(layer)]

    def _scene(self) -> tuple[dict[str, Any], Buffers]:
        if self._scene_cache is None:
            self._scene_cache = self._build()
        return self._scene_cache

    def _given_orders(self, tables: list[Table]) -> dict[str, tuple[str, ...]]:
        """The order of each ordered category column (axes and colours; facets order
        themselves): given levels as they are; by a summary, ranked over the tables."""
        out: dict[str, tuple[str, ...]] = {}
        for name, order in self._orders.items():
            if order.by is None:
                if order.levels is not None:
                    out[name] = order.levels
                continue
            having = [t for t in tables if name in t]
            if having:
                out[name] = tuple(ordered_levels(name, order, having))
        return out

    def _build(self) -> tuple[dict[str, Any], Buffers]:
        marks = [layer for layer in self._layers if layer.mark != "rule"]
        tables = [self._table(layer) for layer in marks]
        if self._data is not None:
            tables.insert(0, self._data)
        grid = build_grid(tables, row=self._row, col=self._col, wrap=self._wrap,
                          cols=self._cols, orders=self._orders)  # fmt: skip
        npanels = len(grid.panels)
        given = self._given_orders(tables)
        x_kind, x_levels = _axis(marks, self._table, "x", given)
        y_kind, y_levels = _axis(marks, self._table, "y", given)
        colors = _ColorScales(marks, self._table, self.palette, given)
        extents = {"x": Extent.empty(npanels), "y": Extent.empty(npanels)}
        bars_step = step_of([axis_values(self._table(lr).column(lr.x), x_levels)  # ty: ignore[invalid-argument-type]
                             for lr in marks if lr.mark == "bars"])  # fmt: skip
        built: list[tuple[Layer, Table, Geometry | None]] = []
        rule_values: dict[str, list[float]] = {}
        for layer in self._layers:
            if layer.mark == "rule":
                values = [_scalar(v, x_kind if layer.axis == "x" else y_kind,
                                  x_levels if layer.axis == "x" else y_levels)
                          for v in layer.values]  # fmt: skip
                rule_values[layer.name] = values
                extents[layer.axis].add_everywhere(values)
                built.append((layer, self._data or Table({}), None))
                continue
            table = self._table(layer)
            geom = _geometry(layer, table, grid, x_levels, y_levels, colors, bars_step)
            extents["x"].add(geom.panel, geom.x0)
            extents["x"].add(geom.panel, geom.x1)
            extents["y"].add(geom.panel, geom.y0)
            extents["y"].add(geom.panel, geom.y1)
            built.append((layer, table, geom))
        self._geometry = built
        zero = any(layer.mark == "bars" for layer in marks)
        xg = group_ids(grid, self._share["x"])
        yg = group_ids(grid, self._share["y"])
        xd = domains(extents["x"], xg, x_kind, band_size=len(x_levels or []))
        yd = domains(extents["y"], yg, y_kind, band_size=len(y_levels or []), zero_base=zero)
        x_origin = _origin(xd, x_kind)
        y_origin = _origin(yd, y_kind)
        buffers = Buffers()
        layers_spec = []
        plain = 0  # layers drawn in a default colour so far
        for layer, _table, geom in built:
            if geom is None:
                origin = x_origin if layer.axis == "x" else y_origin
                layers_spec.append(_rule_spec(layer, rule_values[layer.name], origin))
                continue
            layers_spec.append(
                _layer_spec(layer, geom, npanels, buffers, colors, x_origin, y_origin, plain)
            )
            plain += layer.color is None and layer.facet != "exclude"
        first = marks[0] if marks else None
        x_title = self.x_title if self.x_title is not None else (first.x or "" if first else "")
        y_title = self.y_title if self.y_title is not None else (first.y or "" if first else "")
        spec = {
            "version": SPEC_VERSION,
            "title": self.title,
            "grid": grid.spec(),
            "panels": [
                {
                    "row": p.row,
                    "col": p.col,
                    "label": p.label,
                    "keys": list(p.keys),
                    "x": [xd[i][0] - x_origin, xd[i][1] - x_origin],
                    "y": [yd[i][0] - y_origin, yd[i][1] - y_origin],
                    "xg": xg[i],
                    "yg": yg[i],
                }
                for i, p in enumerate(grid.panels)
            ],
            "x": _axis_spec(x_kind, x_levels, x_origin, self._share["x"], x_title),
            "y": _axis_spec(y_kind, y_levels, y_origin, self._share["y"], y_title),
            "layers": layers_spec,
            "legends": colors.legends(),
            "height": self.height,
            "panel_height": self.panel_height,
            "legend_position": self.legend,
        }
        return spec, buffers

    def _tooltip(self, layer_index: int, instance: int) -> list[list[str]]:
        """The tooltip columns of one instance: ``[[name, value], ...]``."""
        self._scene()
        layer, table, geom = self._geometry[layer_index]
        if geom is None or not layer.tooltip:
            return []
        row = int(geom.rows[instance])
        return [[name, _text(table.raw(name)[row])] for name in layer.tooltip]


# ---- helpers ------------------------------------------------------------------------------


def _panel_name(panel: dict[str, Any], index: int) -> str:
    """As the browser names it (layout.ts: panelName)."""
    return " · ".join(panel["keys"]) or panel["label"] or f"panel {index + 1}"


def _names(value: str | Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _reorder(levels: list[str], given: tuple[str, ...] | None) -> list[str]:
    """``levels`` with those in ``given`` first, in its order."""
    if not given:
        return levels
    present = set(levels)
    first = [v for v in given if v in present]
    chosen = set(first)
    return first + [v for v in levels if v not in chosen]


def _axis(
    marks: list[Layer], table_of: Any, axis: str, given: dict[str, tuple[str, ...]]
) -> tuple[AxisKind, list[str] | None]:
    """The kind of an axis from the layers' columns (all must agree), and its categories."""
    kinds: dict[str, list[str]] = {}
    levels: dict[str, None] = {}
    for layer in marks:
        name = getattr(layer, axis)
        column = table_of(layer).column(name)
        kinds.setdefault(column.kind, []).append(f"{layer.name}.{axis}={name!r}")
        if column.kind == "category":
            levels.update(dict.fromkeys(_reorder(list(column.levels), given.get(name))))
    if len(kinds) > 1:
        detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in kinds.items())
        raise ValueError(f"the layers' {axis} columns are of different kinds ({detail})")
    kind = next(iter(kinds), "number")
    if kind == "category":
        return "band", list(levels)
    return kind, None  # ty: ignore[invalid-return-type]


def _scalar(value: Any, kind: AxisKind, levels: list[str] | None) -> float:
    """A rule's position in axis units."""
    if kind == "band":
        lookup = {v: i for i, v in enumerate(levels or [])}
        if str(value) not in lookup:
            raise ValueError(f"rule at {value!r}: not a category of the axis ({levels})")
        return float(lookup[str(value)])
    if kind == "time" and not isinstance(value, int | float):
        return float(np.datetime64(value, "ms").astype(np.int64))
    return float(value)


def _origin(doms: list[tuple[float, float]], kind: AxisKind) -> float:
    """The value subtracted from an axis's numbers, so they travel small (times!)."""
    if kind != "time" or not doms:
        return 0.0
    return float(np.floor(min(d[0] for d in doms)))


def _axis_spec(
    kind: AxisKind, levels: list[str] | None, origin: float, share: Share, title: str
) -> dict[str, Any]:
    return {"kind": kind, "levels": levels, "origin": origin, "share": share, "title": title}


class _ColorScales:
    """The colour scales of the layers' colour columns, shared by column name."""

    def __init__(
        self,
        marks: list[Layer],
        table_of: Any,
        palette: list[str] | None,
        given: dict[str, tuple[str, ...]],
    ) -> None:
        self.palette = palette
        self.levels: dict[str, list[str]] = {}
        self.ranges: dict[str, tuple[float, float]] = {}
        self.order: list[str] = []
        for layer in marks:
            table = table_of(layer)
            name = layer.color
            if name is None or name not in table:
                continue
            column = table.column(name)
            if name not in self.order:
                self.order.append(name)
            if column.kind == "category":
                seen = self.levels.setdefault(name, [])
                seen.extend(
                    v for v in _reorder(list(column.levels), given.get(name)) if v not in seen
                )
            else:
                finite = column.values[np.isfinite(column.values)]
                if len(finite):
                    lo, hi = self.ranges.get(name, (np.inf, -np.inf))
                    self.ranges[name] = (min(lo, finite.min()), max(hi, finite.max()))
        self.colored = bool(self.order)

    def colors(self, name: str) -> list[str]:
        return palette_colors(self.palette, len(self.levels[name]))

    def legends(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name in self.order:
            if name in self.levels:
                out.append({"title": name, "kind": "category", "labels": self.levels[name],
                            "colors": self.colors(name)})  # fmt: skip
            elif name in self.ranges:
                lo, hi = self.ranges[name]
                from anytrellis.styling import COLORMAPS

                out.append({"title": name, "kind": "number", "colors": COLORMAPS["viridis"],
                            "lo": float(lo), "hi": float(hi)})  # fmt: skip
        return out

    def default(self, layer: Layer, index: int) -> str:
        if layer.facet == "exclude":
            return CONTEXT_COLOR
        return "#4a5260" if self.colored else TAB10[index % len(TAB10)]


def _geometry(
    layer: Layer,
    table: Table,
    grid: Grid,
    x_levels: list[str] | None,
    y_levels: list[str] | None,
    colors: _ColorScales,
    bars_step: float,
) -> Geometry:
    assert layer.x is not None
    assert layer.y is not None
    x = axis_values(table.column(layer.x), x_levels)
    y = axis_values(table.column(layer.y), y_levels)
    rows, panel = expand(grid.assign(table), table.n, len(grid.panels), layer.facet)
    codes: np.ndarray | None = None
    ncodes = 0
    color_col = (
        table.column(layer.color) if layer.color is not None and layer.color in table else None
    )
    if color_col is not None and color_col.kind == "category":
        levels = colors.levels[color_col.name]
        codes = axis_values(color_col, levels).astype(np.int64)
        ncodes = len(levels)
    if layer.mark == "line":
        extra = list(layer.group)
        if color_col is not None and color_col.kind == "category":
            extra.append(color_col.name)
        geom = line_geometry(rows, panel, x, y, series_codes(table, extra))
    elif layer.mark == "points":
        geom = point_geometry(rows, panel, x, y)
    else:
        step = 1.0 if x_levels is not None else bars_step
        geom = bar_geometry(rows, panel, x, y, step=step, width=layer.bar_width, codes=codes,
                            ncodes=ncodes, position=layer.position)  # fmt: skip
    if color_col is not None:
        if codes is not None:
            palette = np.array([rgba(c) for c in colors.colors(color_col.name)], dtype=np.uint8)
            geom.codes = codes[geom.rows]
            geom.rgba = palette[geom.codes]
        else:
            lo, hi = colors.ranges.get(color_col.name, (0.0, 1.0))
            geom.rgba = colormap_rgba(color_col.values[geom.rows], "viridis", lo, hi)
    return geom


def _layer_spec(
    layer: Layer,
    geom: Geometry,
    npanels: int,
    buffers: Buffers,
    colors: _ColorScales,
    x_origin: float,
    y_origin: float,
    index: int,
) -> dict[str, Any]:
    """A layer in the spec; ``index`` counts the layers drawn in a default colour before it."""
    coords = np.stack(
        [geom.x0 - x_origin, geom.y0 - y_origin, geom.x1 - x_origin, geom.y1 - y_origin], axis=1
    )
    color: dict[str, Any] = {"rgba": None, "solid": None, "codes": None, "legend": None}
    if geom.rgba is not None:
        color["rgba"] = buffers.add(geom.rgba, "uint8", components=4)
        if layer.color in colors.order:
            color["legend"] = colors.order.index(layer.color)
        if geom.codes is not None:
            color["codes"] = buffers.add(geom.codes, "uint16")
    else:
        solid = layer.color if layer.color is not None else colors.default(layer, index)
        color["solid"] = list(rgba(solid))
    return {
        "type": layer.mark,
        "name": layer.name,
        "count": geom.count,
        "coords": buffers.add(coords, "float64", components=4),
        "starts": buffers.add(geom.starts(npanels), "uint32"),
        "color": color,
        "width": layer.width,
        "size": layer.size,
        "opacity": layer.opacity,
        "tooltip": bool(layer.tooltip),
        "context": layer.facet == "exclude",
    }


def _rule_spec(layer: Layer, values: list[float], origin: float) -> dict[str, Any]:
    return {
        "type": "rule",
        "name": layer.name,
        "axis": layer.axis,
        "values": [v - origin for v in values],
        "color": list(rgba(layer.color or MISSING_COLOR)),
        "width": layer.width,
        "dash": layer.dash,
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float | np.floating):
        return f"{float(value):.6g}"
    if isinstance(value, np.datetime64):
        return str(value).replace("T", " ")
    return str(value)
