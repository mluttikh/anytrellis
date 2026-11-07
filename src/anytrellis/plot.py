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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import numpy as np

from anytrellis.codec import Buffers
from anytrellis.data import Table
from anytrellis.detail import (
    DENSE,
    START_WIDTH,
    THIN,
    Detail,
    LineDetail,
    PointDetail,
    Shown,
)
from anytrellis.facets import Grid, Order, Summary, build_grid, ordered_levels
from anytrellis.layers import (
    FACET_MODES,
    STEPS,
    SUMMARIES,
    FacetMode,
    Geometry,
    Layer,
    Position,
    area_geometry,
    axis_values,
    band_geometry,
    bar_geometry,
    expand,
    line_geometry,
    point_geometry,
    rect_geometry,
    series_codes,
    step_of,
)
from anytrellis.linking import Link, Masks, highlight_message
from anytrellis.pages import (
    AUTO_PANELS,
    PAGE_COLS,
    PAGE_ROWS,
    Paging,
    Stat,
    builtin_stats,
    given_stats,
    page_count,
    queried_stats,
    trends,
)
from anytrellis.pages import order as panel_order
from anytrellis.query import panel_summaries
from anytrellis.scales import AxisKind, Extent, Share, domains, group_ids, share_mode
from anytrellis.selection import Brush, grow, link_keys, range_in, range_out, row_mask
from anytrellis.stats import Members, Part
from anytrellis.stats import parts as summary_parts
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
        data: The table the layers draw (Polars, PyArrow, pandas, DuckDB, Ibis, or a dict
            of arrays). A layer may bring its own; a layer whose data lacks the facet
            columns is drawn in every panel. A lazy table (a Polars ``LazyFrame``, a
            DuckDB relation, an Ibis table) is read in one query, with only the columns
            the plot uses, and computes the panels' summaries itself.
        row: Facet column(s) whose levels are the grid's rows.
        col: Facet column(s) whose levels are the grid's columns.
        wrap: Facet column(s) whose levels are panels wrapped into ``cols`` columns (not
            with ``row`` or ``col``).
        cols: Columns of a wrap (default: about the square root of the panels; 6 a page).
        rows: Rows of panels a page of a wrap shows: a wrap of more than 100 panels shows 4
            at a time, and the reader turns the pages, sorts and filters the panels (by
            their statistics: see ``panel_stats``). ``rows=3`` pages any wrap; ``"all"``
            never pages.
        share_x: Share the x scale: ``True`` (all panels), ``"row"``, ``"col"`` or
            ``False`` (each panel its own).
        share_y: The same for y.
        x_scale: ``"linear"`` or ``"log"`` (log10: values of 0 or less are left out; a
            histogram's bins and a density are computed on the log scale).
        y_scale: The same for y (not with marks drawn from zero: bars, areas, histograms,
            densities).
        height: The plot's height in CSS pixels (default: from ``panel_height``).
        panel_height: Each panel's height in CSS pixels (default: from its width).
        aspect: Each panel's height as a multiple of its width (``1``: square), unless
            ``height`` or ``panel_height`` is given (default: about 0.62, between 90 and
            300 px).
        title: A title over the plot.
        x_title: The x axis title (default: the x column's name).
        y_title: The y axis title (default: the y column's name).
        palette: Colours for category colour columns (default: tab10).
        legend: ``"auto"``: in a wrap's empty cells after its last panel when it fits there,
            under the plot otherwise; ``"bottom"``: always under the plot.
        fit_y: Start with y fitted to the data in view: zooming or panning x refits each y
            scale (shared ones to all their panels), until y is zoomed by hand. The ``y`` key
            and the toolbar switch it on and off.
        link: Column(s) that identify a thing across panels (a country, a station): a
            selection grows to every row sharing them, in all panels and layers that have
            the columns. Select a few countries in 1955 and see them in every year.
            (Separate plots sharing a selection: ``anytrellis.link``.)
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
        rows: int | str | None = None,
        share_x: bool | str = True,
        share_y: bool | str = True,
        x_scale: str = "linear",
        y_scale: str = "linear",
        height: int | None = None,
        panel_height: int | None = None,
        aspect: float | None = None,
        title: str = "",
        x_title: str | None = None,
        y_title: str | None = None,
        palette: Sequence[str] | None = None,
        legend: str = "auto",
        fit_y: bool = False,
        link: str | Sequence[str] | None = None,
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
        if rows is not None and rows != "all" and (not isinstance(rows, int) or rows < 1):
            raise ValueError(f"rows must be at least 1, or 'all', got {rows!r}")
        if isinstance(rows, int) and not self._wrap:
            raise ValueError("rows= pages a wrap: give wrap= (a grid shows all its cells)")
        self._rows = rows
        self._given_stats: Table | None = None
        self._paging: Paging = {}
        self._stats: list[Stat] = []
        self._share: dict[str, Share] = {"x": share_mode(share_x), "y": share_mode(share_y)}
        self._scales: dict[str, str] = {"x": _scale(x_scale), "y": _scale(y_scale)}
        self._orders: dict[str, Order] = {}
        self._keep_empty = True
        """A grid's cells without data are kept (empty panels), or left out."""
        self._layers: list[Layer] = []
        self._tables: dict[int, Table] = {}
        self.height = height
        self.panel_height = panel_height
        if aspect is not None and not aspect > 0:
            raise ValueError(f"aspect must be positive, got {aspect!r}")
        self.aspect = aspect
        self.title = title
        self.x_title = x_title
        self.y_title = y_title
        self.palette = list(palette) if palette else None
        if legend not in LEGENDS:
            raise ValueError(f"legend must be one of {LEGENDS}, got {legend!r}")
        self.legend = legend
        self.fit_y = bool(fit_y)
        self._link = _names(link)
        self._selection: Brush | None = None
        self._axes: dict[str, tuple[AxisKind, list[str] | None, float]] = {}
        self._keys: dict[int, np.ndarray | None] = {}
        if renderer not in RENDERERS:
            raise ValueError(f"renderer must be one of {RENDERERS}, got {renderer!r}")
        self.renderer = renderer
        self._widget: TrellisWidget | None = None
        self._focus: str | None = None
        self._view: dict[str, Any] | None = None
        """What the browser last showed: its width and each scale group's range (images)."""
        self._link_group: Link | None = None
        self._highlight: Masks | None = None
        """The rows another plot of the link selects (``anytrellis.link``), or None."""
        self._scene_cache: tuple[dict[str, Any], Buffers] | None = None
        self._geometry: list[tuple[Layer, Table, Geometry | None]] = []
        self._drawn: list[_Drawn] = []
        self._window: frozenset[int] | None = None
        """A paged plot's panels whose data the widget has (None: every panel's)."""
        self._full: list[_Sent] = []
        """Each spec layer's entry for every panel (``_sent``: the window's of it)."""
        self._start: list[_Sent] = []
        """``_full`` as the plot starts (a saved page's)."""
        self._full_scene_cache: tuple[dict[str, Any], Buffers] | None = None

    # ---- layers -------------------------------------------------------------------------

    def line(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        group: str | Sequence[str] | None = None,
        step: str | None = None,
        width: float = 1.5,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Lines through the points of each series, sorted by x; or steps between them.

        ```python
        t = Trellis(gapminder, wrap="region")
        t.line(x="year", y="life_expect", group="country", width=1)
        t.line(x="time", y="state", step="post")    # each value holds until the next
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The x column.
            y: The y column.
            color: A colour column (one line per category; numbers along a colormap) or
                one colour.
            group: Column(s) whose combinations are separate lines (besides ``color``).
            step: Steps instead of slopes: ``"post"`` (each value holds until the next
                point: a level that changes at the points, as a counter or a state),
                ``"pre"`` (each value holds back to the point before) or ``"mid"`` (each
                holds to halfway between the points).
            width: Line width in CSS pixels.
            opacity: 0 to 1.
            facet: ``"auto"`` (each row in its panel; every panel when the data has no facet
                columns), ``"include"``, ``"all"`` (every row in every panel) or
                ``"exclude"`` (each panel shows the other panels' rows: grey context).
            tooltip: Columns shown on hover, besides x and y.
            name: The layer's name.
        """
        if step not in (None, *STEPS):
            raise ValueError(f"step must be one of {STEPS} or None, got {step!r}")
        layer = Layer("line", name or self._name("line"), data, x, y, color, _names(group),
                      facet, width=width, opacity=opacity, tooltip=list(tooltip),
                      step=step)  # fmt: skip
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

        ```python
        t = Trellis(penguins, wrap="species")
        t.points(x="flipper_length_mm", y="body_mass_g", color="sex")
        ```

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

        ```python
        Trellis(barley, wrap="site").bars(x="variety", y="yield", color="year", position="dodge")
        ```

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

    def area(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        group: str | Sequence[str] | None = None,
        position: Position = "stack",
        opacity: float = 0.8,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Filled areas under the line of each series, down to 0.

        ```python
        Trellis(by_region).area(x="year", y="pop", color="region")
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The x column.
            y: The y column.
            color: A colour column (one area per category) or one colour.
            group: Column(s) whose combinations are separate areas (besides ``color``).
            position: ``"stack"`` (default: each series on the ones before it, at equal x)
                or ``"identity"`` (each from 0, overlapping).
            opacity: 0 to 1.
            facet: As for ``line``.
            tooltip: Columns shown on hover, besides x and y.
            name: The layer's name.
        """
        if position not in ("stack", "identity"):
            raise ValueError(f"position must be 'stack' or 'identity', got {position!r}")
        return self._add(Layer("area", name or self._name("area"), data, x, y, color,
                               _names(group), facet, opacity=opacity, position=position,
                               tooltip=list(tooltip)))  # fmt: skip

    def band(
        self,
        data: Any = None,
        *,
        x: str,
        ymin: str,
        ymax: str,
        color: str | None = None,
        group: str | Sequence[str] | None = None,
        opacity: float = 0.3,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """A band between two lines: from ``ymin`` to ``ymax`` along x (a range, an
        interval, an envelope), one per group (and colour).

        ```python
        Trellis(weather, wrap="year").band(x="date", ymin="temp_min", ymax="temp_max")
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The x column.
            ymin: The lower line's column.
            ymax: The upper line's column.
            color: A colour column or one colour.
            group: Column(s) splitting the rows into separate bands.
            opacity: 0 to 1.
            facet: As for ``line``.
            tooltip: Columns shown on hover, besides x, ymin and ymax.
            name: The layer's name.
        """
        return self._add(Layer("band", name or self._name("band"), data, x, ymin, color,
                               _names(group), facet, opacity=opacity, y2=ymax,
                               tooltip=list(tooltip)))  # fmt: skip

    def smooth(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        method: str = "loess",
        se: bool = True,
        level: float = 0.95,
        span: float = 0.75,
        n: int = 80,
        fullrange: bool = False,
        width: float = 1.5,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        name: str | None = None,
    ) -> Self:
        """A smooth line through each panel's points (and each colour's), with a
        confidence band for its mean.

        ```python
        t = Trellis(cars, wrap="origin")
        t.points(x="horsepower", y="mpg").smooth(x="horsepower", y="mpg")
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The x column (numbers or times).
            y: The y column.
            color: A category column (a fit per category) or one colour.
            method: ``"loess"`` (local linear regression, tricube weights) or
                ``"linear"`` (least squares).
            se: Draw the confidence band.
            level: The band's confidence level.
            span: Loess: the share of the points each local fit uses.
            n: Points along each line.
            fullrange: Draw each line over every panel's x range, not its own data's.
            width: Line width in CSS pixels.
            opacity: 0 to 1 (the band is lighter).
            facet: As for ``line``.
            name: The layer's name.
        """
        if method not in ("loess", "linear"):
            raise ValueError(f"method must be 'loess' or 'linear', got {method!r}")
        if not 0 < level < 1:
            raise ValueError("level must be between 0 and 1")
        if not span > 0:
            raise ValueError("span must be positive")
        if n < 2:
            raise ValueError("n must be at least 2")
        args = {"method": method, "se": se, "level": level, "span": span, "n": n,
                "fullrange": fullrange}  # fmt: skip
        return self._add(Layer("smooth", name or self._name("smooth"), data, x, y, color, (),
                               facet, width=width, opacity=opacity,
                               stat_args=args))  # fmt: skip

    def rect(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        x2: str | None = None,
        y2: str | None = None,
        color: str | None = None,
        width: float = 1.0,
        height: float = 1.0,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Rectangles: tiles centred on (x, y), one step of the data wide and high (a
        heatmap, with a number colour), or from (x, y) to (x2, y2).

        ```python
        Trellis(daily, wrap="year").rect(x="day", y="month", color="temp_max")
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The x column (the tiles' centres, or their left with ``x2``).
            y: The y column (centres, or bottoms with ``y2``).
            x2: The tiles' right edges.
            y2: The tiles' tops.
            color: A colour column or one colour (numbers: a colormap, as a heatmap).
            width: A tile's width as a fraction of the step between x values.
            height: A tile's height as a fraction of the step between y values.
            opacity: 0 to 1.
            facet: As for ``line``.
            tooltip: Columns shown on hover, besides x and y (a number colour: shown).
            name: The layer's name.
        """
        if not (0 < width <= 1 and 0 < height <= 1):
            raise ValueError("width and height must be in (0, 1]")
        layer = Layer("rect", name or self._name("rect"), data, x, y, color, (), facet,
                      opacity=opacity, bar_width=width, tooltip=list(tooltip), x2=x2, y2=y2,
                      rect_height=height)  # fmt: skip
        return self._add(layer)

    def text(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        text: str,
        color: str | None = None,
        size: float = 11.0,
        align: str = "center",
        dx: float = 0.0,
        dy: float = 0.0,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        name: str | None = None,
    ) -> Self:
        """A label per row: the ``text`` column's value at (x, y).

        ```python
        t.text(x="fertility", y="life_expect", text="country", align="left", dx=6)
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The x column.
            y: The y column.
            text: The column of labels.
            color: A colour column or one colour (default: the theme's text colour).
            size: Font size in CSS pixels.
            align: ``"left"``, ``"center"`` or ``"right"`` of the point.
            dx: Offset to the right, in CSS pixels.
            dy: Offset down, in CSS pixels.
            opacity: 0 to 1.
            facet: As for ``line``.
            name: The layer's name.
        """
        if align not in ("left", "center", "right"):
            raise ValueError(f"align must be 'left', 'center' or 'right', got {align!r}")
        layer = Layer("text", name or self._name("text"), data, x, y, color, (), facet,
                      size=size, opacity=opacity, text=text, align=align,
                      dx=dx, dy=dy)  # fmt: skip
        return self._add(layer)

    def hist(
        self,
        data: Any = None,
        *,
        x: str,
        color: str | None = None,
        bins: int | Sequence[Any] = 30,
        binwidth: Any = None,
        stat: str = "count",
        position: Position = "stack",
        width: float | None = None,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        name: str | None = None,
    ) -> Self:
        """A histogram in each panel: the rows counted in bins that every panel shares.

        ```python
        Trellis(penguins, wrap="species").hist(x="flipper_length_mm", binwidth=2, color="sex")
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The column binned (numbers or times); a category column: its categories
                counted.
            color: A category column (its counts stacked or overlapping) or one colour.
            bins: The number of bins over the values' range, or the edges.
            binwidth: A bin width instead (a time axis: a timedelta, or ``"7D"``, ``"6h"``),
                the edges at its multiples.
            stat: ``"count"``, ``"percent"`` (of each panel's rows) or ``"density"`` (each
                panel's bars cover an area of 1).
            position: With a colour: ``"stack"`` (default) or ``"identity"`` (overlapping).
            width: Bar width as a fraction of the bin (default 1; categories 0.8).
            opacity: 0 to 1.
            facet: As for ``line``; ``"exclude"``: the other panels' histogram, in grey.
            name: The layer's name.
        """
        if stat not in ("count", "percent", "density"):
            raise ValueError(f"stat must be 'count', 'percent' or 'density', got {stat!r}")
        if position not in ("stack", "identity"):
            raise ValueError(f"position must be 'stack' or 'identity', got {position!r}")
        if width is not None and not 0 < width <= 1:
            raise ValueError("width must be in (0, 1]")
        args = {"bins": bins, "binwidth": binwidth, "stat": stat, "width": width}
        return self._add(Layer("hist", name or self._name("hist"), data, x, None, color, (),
                               facet, opacity=opacity, position=position,
                               stat_args=args))  # fmt: skip

    def box(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        position: Position = "dodge",
        width: float = 0.8,
        whis: float = 1.5,
        outliers: bool = True,
        linewidth: float = 1.5,
        size: float = 4.0,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Box plots: a box per position (and colour) in each panel, from the first to the
        third quartile with a line at the median, whiskers to the furthest values within
        ``whis`` times the box's height of it, and the values beyond as points.

        ```python
        Trellis(penguins, wrap="island").box(x="body_mass_g", y="species")
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The positions (categories, or numbers), or the values for horizontal boxes.
            y: The values, or (a category column) the positions of horizontal boxes.
            color: A category column (its boxes side by side) or one colour.
            position: With a colour: ``"dodge"`` (default, side by side) or ``"identity"``.
            width: Box width as a fraction of the step between positions.
            whis: Whisker reach, in interquartile ranges (Tukey: 1.5).
            outliers: Draw the values beyond the whiskers.
            linewidth: The box's outline, median and whiskers, in CSS pixels.
            size: Outlier diameter in CSS pixels.
            opacity: 0 to 1 (the box's fill is lighter).
            facet: As for ``line``.
            tooltip: Columns shown when hovering an outlier.
            name: The layer's name.
        """
        if position not in ("dodge", "identity"):
            raise ValueError(f"position must be 'dodge' or 'identity', got {position!r}")
        if not 0 < width <= 1:
            raise ValueError("width must be in (0, 1]")
        if not whis >= 0:
            raise ValueError("whis must be at least 0")
        args = {"width": width, "whis": whis, "outliers": outliers}
        return self._add(Layer("box", name or self._name("box"), data, x, y, color, (), facet,
                               width=linewidth, size=size, opacity=opacity,
                               position=position, tooltip=list(tooltip),
                               stat_args=args))  # fmt: skip

    def density(
        self,
        data: Any = None,
        *,
        x: str,
        color: str | None = None,
        fill: bool = False,
        bw_adjust: float = 1.0,
        cut: float = 3.0,
        gridsize: int = 200,
        width: float = 1.5,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        name: str | None = None,
    ) -> Self:
        """A density curve in each panel (and for each colour): a Gaussian kernel density
        estimate, each curve covering an area of 1, on x values every panel shares.

        ```python
        Trellis(penguins, wrap="species").density(x="body_mass_g", color="sex", fill=True)
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The column (numbers or times).
            color: A category column (a curve per category) or one colour.
            fill: Fill the area under each curve too.
            bw_adjust: The bandwidth, as a multiple of Scott's rule's.
            cut: How far past the data each curve goes, in bandwidths.
            gridsize: Points along the shared x grid.
            width: Line width in CSS pixels.
            opacity: 0 to 1 (a fill is lighter).
            facet: As for ``line``.
            name: The layer's name.
        """
        if not bw_adjust > 0:
            raise ValueError("bw_adjust must be positive")
        if gridsize < 2:
            raise ValueError("gridsize must be at least 2")
        args = {"fill": fill, "bw_adjust": bw_adjust, "cut": cut, "gridsize": gridsize}
        return self._add(Layer("density", name or self._name("density"), data, x, None, color,
                               (), facet, width=width, opacity=opacity,
                               stat_args=args))  # fmt: skip

    def violin(
        self,
        data: Any = None,
        *,
        x: str,
        y: str,
        color: str | None = None,
        position: Position = "dodge",
        width: float = 0.8,
        scale: str = "area",
        inner: str | None = "quartiles",
        bw_adjust: float = 1.0,
        cut: float = 2.0,
        gridsize: int = 100,
        linewidth: float = 1.0,
        size: float = 3.0,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Violins: the values' distribution at each position (and colour) in each panel,
        as their density mirrored around the position, with the median and quartiles
        inside. Where a box plot shows five numbers, a violin shows the shape: two peaks,
        a long tail.

        ```python
        Trellis(penguins, wrap="island").violin(x="species", y="body_mass_g")
        Trellis(penguins).violin(x="body_mass_g", y="species", color="sex")  # horizontal
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The positions (categories, or numbers), or the values for horizontal violins.
            y: The values, or (a category column) the positions of horizontal violins.
            color: A category column (its violins side by side) or one colour.
            position: With a colour: ``"dodge"`` (default, side by side) or ``"identity"``.
            width: The widest violin's width, as a fraction of the step between positions.
            scale: ``"area"`` (every violin the same area), ``"count"`` (areas as the
                number of values) or ``"width"`` (every violin as wide).
            inner: ``"quartiles"`` (the median across it, the quartiles half way),
                ``"points"`` (the values, along its middle) or None.
            bw_adjust: The bandwidth, as a multiple of Scott's rule's.
            cut: How far past the values each violin goes, in bandwidths.
            gridsize: Points along each violin.
            linewidth: The outline's (and the quartiles') width in CSS pixels.
            size: The values' diameter in CSS pixels (``inner="points"``).
            opacity: 0 to 1 (the fill is lighter).
            facet: As for ``line``.
            tooltip: Columns shown when hovering a value (``inner="points"``).
            name: The layer's name.
        """
        from anytrellis.stats import VIOLIN_INNER, VIOLIN_SCALES

        if position not in ("dodge", "identity"):
            raise ValueError(f"position must be 'dodge' or 'identity', got {position!r}")
        if not 0 < width <= 1:
            raise ValueError("width must be in (0, 1]")
        if scale not in VIOLIN_SCALES:
            raise ValueError(f"scale must be one of {VIOLIN_SCALES}, got {scale!r}")
        if inner not in VIOLIN_INNER:
            raise ValueError(f"inner must be one of {VIOLIN_INNER}, got {inner!r}")
        if not bw_adjust > 0:
            raise ValueError("bw_adjust must be positive")
        if gridsize < 2:
            raise ValueError("gridsize must be at least 2")
        args = {"width": width, "scale": scale, "inner": inner, "bw_adjust": bw_adjust,
                "cut": cut, "gridsize": gridsize}  # fmt: skip
        return self._add(Layer("violin", name or self._name("violin"), data, x, y, color, (),
                               facet, width=linewidth, size=size, opacity=opacity,
                               position=position, tooltip=list(tooltip),
                               stat_args=args))  # fmt: skip

    def errorbar(
        self,
        data: Any = None,
        *,
        x: str | None = None,
        y: str | None = None,
        ymin: str | None = None,
        ymax: str | None = None,
        xmin: str | None = None,
        xmax: str | None = None,
        extent: str = "ci",
        level: float = 0.95,
        color: str | None = None,
        position: Position = "dodge",
        width: float = 0.8,
        cap: float = 0.25,
        points: bool = True,
        linewidth: float = 1.5,
        size: float = 6.0,
        opacity: float = 1.0,
        facet: FacetMode = "auto",
        tooltip: Sequence[str] = (),
        name: str | None = None,
    ) -> Self:
        """Error bars: an interval at each position, with caps, and its centre as a point.

        From the values: the mean of each position's (and colour's) values with an
        interval around it (``extent``). Or as given: from ``ymin`` to ``ymax`` at each x
        (``xmin`` to ``xmax`` at each y: horizontal), centred on ``y`` (``x``) if given.

        ```python
        Trellis(penguins, wrap="island").errorbar(x="species", y="body_mass_g")  # mean, 95% CI
        Trellis(fits, wrap="site").errorbar(x="dose", y="effect", ymin="lo", ymax="hi")
        ```

        Args:
            data: The layer's table (default: the plot's).
            x: The positions; or the values (a category ``y``), or the centres (with
                ``xmin`` and ``xmax``).
            y: The values (a category or number ``x``); or the centres (with ``ymin`` and
                ``ymax``), or the positions (with ``xmin`` and ``xmax``).
            ymin: Each vertical bar's low end (with ``ymax``).
            ymax: Its high end.
            xmin: Each horizontal bar's low end (with ``xmax``).
            xmax: Its high end.
            extent: From the values: ``"ci"`` (the mean's ``level`` confidence interval),
                ``"se"`` (the mean ± its standard error), ``"sd"`` (± one standard
                deviation) or ``"range"`` (the lowest value to the highest). On a log axis,
                of the logs (the centre is the geometric mean).
            level: The confidence level of ``extent="ci"``.
            color: A category column (its bars side by side) or one colour.
            position: With a colour: ``"dodge"`` (default, side by side) or ``"identity"``.
            width: The room the bars of a position share (dodged), as a fraction of the
                step between positions.
            cap: The caps' width, as a fraction of each bar's room: the step between
                positions, or its share of it when dodged (0: no caps).
            points: Draw the centre as a point.
            linewidth: In CSS pixels.
            size: The centre's diameter in CSS pixels.
            opacity: 0 to 1.
            facet: As for ``line``.
            tooltip: Columns shown on hover (bars as given).
            name: The layer's name.
        """
        from anytrellis.stats import EXTENTS

        vertical = ymin is not None or ymax is not None
        horizontal = xmin is not None or xmax is not None
        if vertical and horizontal:
            raise ValueError("errorbar(): give ymin and ymax, or xmin and xmax, not both")
        if (vertical and (ymin is None or ymax is None)) or (
                horizontal and (xmin is None or xmax is None)):  # fmt: skip
            raise ValueError("errorbar(): give both ends: ymin and ymax (or xmin and xmax)")
        if vertical and x is None:
            raise ValueError("errorbar(ymin=, ymax=): x gives the positions")
        if horizontal and y is None:
            raise ValueError("errorbar(xmin=, xmax=): y gives the positions")
        if not (vertical or horizontal) and (x is None or y is None):
            raise ValueError("errorbar(): x and y (the positions and the values), or the ends "
                             "with ymin and ymax (xmin and xmax)")  # fmt: skip
        if extent not in EXTENTS:
            raise ValueError(f"extent must be one of {EXTENTS}, got {extent!r}")
        if not 0 < level < 1:
            raise ValueError("level must be between 0 and 1")
        if position not in ("dodge", "identity"):
            raise ValueError(f"position must be 'dodge' or 'identity', got {position!r}")
        if not 0 < width <= 1:
            raise ValueError("width must be in (0, 1]")
        if not cap >= 0:
            raise ValueError("cap must be at least 0")
        args: dict[str, Any] = {"extent": extent, "level": level, "width": width, "cap": cap,
                                "points": points, "horizontal": horizontal,
                                "lo": ymin or xmin, "hi": ymax or xmax}  # fmt: skip
        if vertical:
            args["y_columns"] = (ymin, ymax)
        if horizontal:
            args["x_columns"] = (xmin, xmax)
        return self._add(Layer("errorbar", name or self._name("errorbar"), data, x, y, color,
                               (), facet, width=linewidth, size=size, opacity=opacity,
                               position=position, tooltip=list(tooltip),
                               stat_args=args))  # fmt: skip

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

        ```python
        t.rule(y=0, color="#888888", dash=(4, 3))
        ```

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

    def scale(self, x: str | None = None, y: str | None = None) -> Self:
        """The axes' scales: ``"linear"`` or ``"log"`` (as ``Trellis(x_scale=...)``)."""
        if x is not None:
            self._scales["x"] = _scale(x)
        if y is not None:
            self._scales["y"] = _scale(y)
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
        self._send_detail()  # an opened panel of another page: its data

    # ---- pages --------------------------------------------------------------------------

    def panel_stats(self, data: Any) -> Self:
        """Statistics of each panel, to sort and filter a paged wrap's panels by: a table
        with the facet columns and one row per panel; each other column is a statistic
        (numbers, or text). They join the ones the plot computes (``rows``, and the mean,
        median, min, max, sd and trend of the values drawn).

        ```python
        info = df.group_by("station").agg(pl.col("temp").quantile(0.9).alias("p90 temp"),
                                          pl.col("region").first())
        t.panel_stats(info)
        ```
        """
        table = Table(data)
        missing = [c for c in self._wrap if c not in table]
        if not self._wrap:
            raise ValueError("panel_stats() is for a wrap (wrap=), whose pages it sorts")
        if missing:
            raise ValueError(f"panel_stats(): the table needs the facet columns {missing}")
        self._given_stats = table
        return self._changed()

    def stats(self) -> dict[str, list[Any]]:
        """The panels' statistics, to sort and filter by: ``{name: [a value per panel]}``,
        in the order of ``panels()`` (empty when the plot does not page)."""
        self._scene()
        return {"panel": self.panels(), **{s.name: list(s.values) for s in self._stats}}

    def sort_panels(self, by: str | None = None, *, descending: bool = False) -> Self:
        """Sort a paged wrap's panels by a statistic (a name from ``stats()``), as the
        reader can in the browser; ``None``: as given (``order``). Panels without a value
        go last.

        ```python
        t.sort_panels("trend temp", descending=True)   # the steepest rise first
        ```
        """
        if by is not None:
            self._stat_named(by)
        return self._set_paging(sort=by, descending=bool(descending), page=0)

    def filter_panels(self, name: str = "", **where: Any) -> Self:
        """Show only the panels whose name has every word of ``name``, and whose
        statistics are in the ranges given: ``(low, high)`` for numbers (``None``: open),
        a piece of text for text. ``filter_panels()`` shows them all again. A statistic's
        name with spaces goes in a dict: ``filter_panels(**{"mean temp": (20, None)})``.

        ```python
        t.filter_panels("north")
        t.filter_panels(rows=(100, None), region="Europe")
        ```
        """
        for key in where:
            self._stat_named(key)
        clean = {k: (list(v) if isinstance(v, tuple | list) else v) for k, v in where.items()}
        return self._set_paging(name=str(name), where=clean, page=0)

    def show_page(self, page: int) -> Self:
        """Turn to a page (from 1) of a paged wrap."""
        self._scene()
        if self._pages_spec() is None:
            raise ValueError("this plot does not page: give rows= (and wrap=)")
        if not 1 <= page <= self.pages:
            raise ValueError(f"page must be from 1 to {self.pages}, got {page!r}")
        return self._set_paging(page=page - 1)

    @property
    def pages(self) -> int:
        """The number of pages, with the panels the filters keep (1 when it does not page)."""
        spec = self._pages_spec()
        if spec is None:
            return 1
        return page_count(len(self._shown_order()), spec["rows"] * spec["cols"])

    @property
    def page(self) -> int:
        """The page shown, from 1."""
        return min(int(self.paging.get("page", 0)), self.pages - 1) + 1

    @property
    def paging(self) -> Paging:
        """The page, sort and filters shown (set here or in the browser)."""
        if self._widget is not None:
            return dict(self._widget.paging)  # ty: ignore[invalid-return-type]
        return dict(self._paging)  # ty: ignore[invalid-return-type]

    def shown_panels(self) -> list[str]:
        """The names of the panels on the page shown, in order (all panels when it does not
        page)."""
        spec = self._pages_spec()
        names = self.panels()
        if spec is None:
            return names
        per = spec["rows"] * spec["cols"]
        start = (self.page - 1) * per
        return [names[i] for i in self._shown_order()[start : start + per]]

    def _shown_order(self) -> list[int]:
        return panel_order(self._stats, self.panels(), self.paging)

    def _pages_spec(self) -> dict[str, Any] | None:
        spec, _ = self._scene()
        return spec["pages"]

    def _stat_named(self, name: str) -> Stat:
        self._scene()
        for s in self._stats:
            if s.name == name:
                return s
        if self._pages_spec() is None:
            raise ValueError("this plot does not page: give rows= (and wrap=)")
        raise ValueError(f"no statistic {name!r}; there are {[s.name for s in self._stats]}")

    def _set_paging(self, **changes: Any) -> Self:
        state: dict[str, Any] = {**self.paging, **changes}
        self._paging = state  # ty: ignore[invalid-assignment]
        if self._widget is not None:
            self._widget.paging = state
        self._send_detail()  # the data of the panels around the page shown
        return self

    def _pages(self, grid: Grid) -> dict[str, Any] | None:
        """A paged wrap's page size and its panels' statistics (None: it does not page), its
        panels placed on the first page."""
        n = len(grid.panels)
        self._stats = []
        if grid.kind != "wrap" or self._rows == "all":
            return None
        if self._rows is None and n <= AUTO_PANELS:
            return None
        cols = max(1, min(self._cols or PAGE_COLS, n))
        rows = max(1, min(self._rows if isinstance(self._rows, int) else PAGE_ROWS,
                          -(-n // cols)))  # fmt: skip
        per = rows * cols
        grid.panels = [replace(p, row=(i % per) // cols, col=i % cols)
                       for i, p in enumerate(grid.panels)]  # fmt: skip
        grid.rows, grid.cols = rows, cols
        self._stats = self._panel_stats(grid)
        return {"rows": rows, "cols": cols, "stats": [s.spec() for s in self._stats]}

    def _panel_stats(self, grid: Grid) -> list[Stat]:
        """The built-in statistics, of the first layer drawing numbers from rows (its y, or
        its x), and those given with ``panel_stats``, which replace any of the same name."""
        n = len(grid.panels)
        stats: list[Stat] = []
        for layer in self._layers:
            if layer.mark == "rule" or layer.facet == "exclude":
                continue
            table = self._table(layer)
            panel_of = grid.assign(table)
            if panel_of is None:
                continue
            numeric = [a for a in (layer.y, layer.x)
                       if a is not None and table.column(a).kind == "number"]  # fmt: skip
            if not numeric:
                continue
            name = numeric[0]
            x_name = None
            if name == layer.y and layer.x is not None and table.kind(layer.x) != "category":
                x_name = layer.x
            values = table.column(name).values
            x = None if x_name is None else table.column(x_name).values
            found = panel_summaries(table, grid.columns, name, x_name)
            if found is None:
                stats = builtin_stats(n, panel_of, values, name, x)
            else:  # the database's medians; the trend from the rows, without sorting them
                trend = None if x is None else trends(n, panel_of, values, x)
                stats = queried_stats(n, grid.assign, found, name, trend)
            break
        if self._given_stats is not None:
            where = grid.assign(self._given_stats)
            assert where is not None  # it has the facet columns
            given = given_stats(self._given_stats, where, n, grid.columns)
            names = {s.name for s in given}
            stats = [s for s in stats if s.name not in names] + given
        return stats

    # ---- selecting ----------------------------------------------------------------------

    def select(self, x: Any = None, y: Any = None, *, color: Any = None,
               panel: Any = None) -> Self:  # fmt: skip
        """Select the marks in a range of x, of y or of both, as a brush drawn in the
        browser does: in every panel, or in ``panel`` alone (a name from ``panels()``, or a
        tuple of its levels); with ``link``, also every row sharing a key with them, in all
        panels. ``color``: only the marks of these colours, as clicking legend entries does.
        ``select()`` clears the selection.

        ```python
        t.select(x=("2026-03-05", "2026-03-08"))   # a time axis: dates, datetimes
        t.select(x=(2, 4), y=(60, 80))             # numbers
        t.select(x=["Europe", "Asia"])             # a category axis: its categories
        t.select(x=(0, 3), panel="1955")           # with link="country": follow them
        t.select(color=["Asia", "Africa"])         # a colour column's categories
        ```
        """
        self._scene()
        brush: Brush | None = None
        if x is not None or y is not None or color is not None:
            brush = {"x": self._range_in("x", x), "y": self._range_in("y", y), "panel": None}
            if color is not None:
                brush["legend"] = self._legend_in(color)
            if panel is not None:
                keys = panel if isinstance(panel, tuple) else (panel,)
                name = " · ".join(str(k) for k in keys)
                names = self.panels()
                if name not in names:
                    raise ValueError(f"no panel {name!r}; the panels are {names[:8]}")
                brush["panel"] = names.index(name)
        self._set_selection(brush)
        return self

    @property
    def selection(self) -> dict[str, Any] | None:
        """The selection (made here or in the browser): ``{"x": ..., "y": ..., "color": ...,
        "panel": ...}``, each axis a ``(low, high)`` range (times as ``datetime64``; a
        category axis: the categories in it) or None for any, the colours chosen in the
        legend (a list of categories) or None for any, and the panel it was drawn in (a
        linked plot) or None for all; None when nothing is selected."""
        brush = self._current_selection()
        if brush is None:
            return None
        self._scene()
        out = {axis: range_out(brush.get(axis), *self._axes[axis]) for axis in ("x", "y")}
        legend = self._legend_out(brush)
        out["color"] = None if legend is None else legend[1]
        panel = brush.get("panel")
        out["panel"] = None if panel is None else self.panels()[int(panel)]
        return out

    def selected(self, layer: str | int | None = None) -> Any:
        """The selected rows of a layer's data (default: the first layer), as the same kind
        of table (Polars, pandas, PyArrow, ...); none selected: no rows. In a linked plot
        (``anytrellis.link``) without a brush of its own: the rows another plot selects."""
        self._scene()
        user = self._user_layer(layer)
        table = self._table(user)
        if self._current_selection() is None and self._highlight is not None:
            mask = self._highlight.get(id(user))
            if mask is None:
                mask = np.zeros(table.n, dtype=bool)
        else:
            mask = self._source_mask(user)
        return table.take(np.flatnonzero(mask))

    def _source_mask(self, user: Layer) -> np.ndarray:
        """The rows of a layer's data its brush selects."""
        entries = [i for i, d in enumerate(self._drawn) if d.user is user]
        if self._drawn[entries[0]].part is None:
            lay, table, geom = self._geometry[entries[0]]
            assert geom is not None
            return self._row_mask(lay, table, geom)
        # a summary: the rows its selected bins, boxes or curve pieces stand for
        mask = np.zeros(self._table(user).n, dtype=bool)
        for i in entries:
            lay, table, geom = self._geometry[i]
            part = self._drawn[i].part
            assert geom is not None
            assert part is not None
            mask[part.members.of(self._row_mask(lay, table, geom))] = True
        return mask

    def _mark_layers(self) -> list[Layer]:
        """The layers with rows (not rules), as given."""
        return [lr for lr in self._layers if lr.mark != "rule"]

    def _selected_masks(self) -> list[tuple[Table, np.ndarray]]:
        """Each layer's data and the rows of it the brush selects (context layers: none)."""
        self._scene()
        return [(self._table(lr), self._source_mask(lr))
                for lr in self._mark_layers() if lr.facet != "exclude"]  # fmt: skip

    def _row_mask(self, layer: Layer, table: Table, geom: Geometry) -> np.ndarray:
        brush = self._current_selection()
        if brush is None:
            return np.zeros(table.n, dtype=bool)
        x = self._absolute("x", brush.get("x"))
        y = self._absolute("y", brush.get("y"))
        panel = None if brush.get("panel") is None else int(brush["panel"])
        legend = self._legend_out(brush)

        def hit(lay: Layer, tb: Table, gm: Geometry) -> np.ndarray:
            mask = row_mask(lay.mark, gm, tb.n, x, y, panel)
            if legend is not None:  # only the chosen colours (another column's: none)
                name, chosen = legend
                if lay.color != name or name not in tb or tb.column(name).kind != "category":
                    return np.zeros(tb.n, dtype=bool)
                mask &= np.isin(tb.column(name).values, chosen)
            return mask

        mask = hit(layer, table, geom)
        keys = self._keys.get(id(layer))
        if keys is None:
            return mask
        # the keys selected in any linked layer
        chosen: list[np.ndarray] = []
        for other, other_table, other_geom in self._geometry:
            other_keys = self._keys.get(id(other))
            if other_geom is None or other_keys is None or other.facet == "exclude":
                continue
            m = mask if other is layer else hit(other, other_table, other_geom)
            chosen.append(other_keys[m])
        return grow(mask, keys, np.unique(np.concatenate(chosen)) if chosen else np.array([]))

    def _user_layer(self, layer: str | int | None) -> Layer:
        """A layer with rows, by name, by index in the spec's layers, or the first."""
        marks = [lr for lr in self._layers if lr.mark != "rule"]
        if not marks:
            raise ValueError("this plot has no layers with marks")
        if layer is None:
            plain = [lr for lr in marks if lr.facet != "exclude"]
            return (plain or marks)[0]
        if isinstance(layer, int):
            drawn = self._drawn[layer]
            if drawn.layer.mark == "rule":
                raise ValueError(f"layer {layer} is a rule: it has no rows to select")
            return drawn.user
        for lr in marks:
            if lr.name == layer:
                return lr
        raise ValueError(f"no layer {layer!r}; the layers are {[lr.name for lr in marks]}")

    def _legend_in(self, color: Any) -> dict[str, Any] | None:
        """``select(color=...)``: the category legend with these levels, and their indices."""
        if color is None:
            return None
        wanted = [str(c) for c in ([color] if isinstance(color, str) else list(color))]
        legends = self._scene()[0]["legends"]
        for index, lg in enumerate(legends):
            labels = lg.get("labels") or []
            if lg["kind"] == "category" and all(w in labels for w in wanted):
                return {"index": index, "levels": sorted({labels.index(w) for w in wanted})}
        known = {lg["title"]: lg.get("labels") for lg in legends if lg["kind"] == "category"}
        if not known:
            raise ValueError("select(color=...) needs a category colour column (a legend)")
        raise ValueError(f"no colour legend has all of {wanted}; the legends are {known}")

    def _legend_out(self, brush: Brush) -> tuple[str, list[str]] | None:
        """The brush's chosen legend entries: the colour column and its categories."""
        legend = brush.get("legend")
        if not legend or not legend.get("levels"):
            return None
        legends = self._scene()[0]["legends"]
        index = int(legend["index"])
        if not 0 <= index < len(legends) or legends[index]["kind"] != "category":
            return None
        labels = legends[index]["labels"]
        chosen = [labels[i] for i in legend["levels"] if 0 <= i < len(labels)]
        return legends[index]["title"], chosen

    def _range_in(self, axis: str, value: Any) -> list[float] | None:
        kind, levels, origin = self._axes[axis]
        return range_in(value, kind, levels, origin, _scalar)

    def _absolute(self, axis: str, r: list[float] | None) -> tuple[float, float] | None:
        if r is None:
            return None
        origin = self._axes[axis][2]
        return (float(r[0]) + origin, float(r[1]) + origin)

    def _current_selection(self) -> Brush | None:
        if self._widget is not None:
            return self._widget.selection or None
        return self._selection

    def _set_selection(self, brush: Brush | None) -> None:
        self._selection = brush
        if self._widget is not None:
            self._widget.selection = brush  # ty: ignore[invalid-assignment]  # allow_none
        else:
            self._selection_changed()  # with a widget: when its trait changes

    def _selection_changed(self) -> None:
        """The brush changed (here or in the browser): a link shows it in its other plots."""
        if self._link_group is not None:
            self._link_group.changed(self)

    def _clear_link(self) -> None:
        """A click in the browser with nothing of its own selected: the link's selection
        goes."""
        if self._link_group is not None:
            self._link_group.clear()

    def _set_highlight(self, masks: Masks | None) -> None:
        if masks is None and self._highlight is None:
            return
        self._highlight = masks
        self._send_highlight()

    def _send_highlight(self) -> None:
        """Tell the browser which marks the link highlights (it asks when it starts)."""
        if self._widget is None:
            return
        entries: list[tuple[Layer, Any, Any]] = []
        if self._highlight is not None:
            entries = self._highlight_entries()
        message, buffers = highlight_message(entries, self._highlight)
        if message.get("layers"):  # as sent: the browser leaves a mask for other data alone
            for entry, of in zip(message["layers"], self._shown_ids(), strict=True):
                if entry is not None:
                    entry["of"] = of
        self._widget.send(message, buffers=buffers)

    def _live(self, on: bool) -> None:
        """Send the brush while it is dragged (a linked plot), not only on release."""
        if self._widget is not None:
            self._widget._live = on

    # ---- showing ------------------------------------------------------------------------

    @property
    def widget(self) -> TrellisWidget:
        """The widget that shows the plot: made the first time the plot is shown or this is
        read, then the same one."""
        if self._widget is None:
            from anytrellis.widget import TrellisWidget

            spec, _ = self._scene()
            state = {"_spec": spec, "renderer": self.renderer, "open_panel": self._focus,
                     "selection": self._selection, "paging": dict(self._paging),
                     "_live": self._link_group is not None}  # fmt: skip
            self._widget = TrellisWidget(self, state)
        return self._widget

    def _repr_mimebundle_(self, **kwargs: Any) -> Any:
        return self.widget._repr_mimebundle_(**kwargs)

    def _display_(self) -> Any:
        """What marimo shows: the widget."""
        import marimo as mo

        return mo.ui.anywidget(self.widget)

    def _embed_html(self) -> str:
        """The plot's data in a ``<div class="anytrellis-embed">``, for a page that loads
        ``standalone.js`` and ``widget.css`` once (the documentation's pages)."""
        spec, buffers = self._full_scene()
        payload = {
            "spec": spec,
            "buffers": {k: base64.b64encode(v).decode("ascii") for k, v in buffers.data.items()},
            "renderer": self.renderer,
            "focus": self.focused,
            "selection": self._current_selection(),
            "paging": self.paging,
        }
        data = json.dumps(payload).replace("</", "<\\/")
        script = f"<script type='application/json'>{data}</script>"
        return f"<div class='anytrellis-embed'>{script}</div>"

    def to_html(self, *, title: str | None = None) -> str:
        """The plot as a standalone HTML page: data and code inside, no kernel needed."""
        script = _STATIC / "standalone.js"
        css = _STATIC / "widget.css"
        if not script.exists():
            raise FileNotFoundError(
                "the JavaScript bundle is not built: run `npm run build` in js/"
            )
        embed = self._embed_html()
        name = html.escape(title or self.title or "anytrellis")
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{name}</title>"
            "<style>body{margin:16px;font-family:system-ui,sans-serif;background:#fff}"
            "@media (prefers-color-scheme: dark){body{background:#12171d}}"
            f"{css.read_text(encoding='utf-8')}</style>"
            f"</head><body>{embed}"
            f"<script>{script.read_text(encoding='utf-8')}</script></body></html>"
        )

    def save_html(self, path: str | Path, *, title: str | None = None) -> Path:
        """Write ``to_html`` to a file; returns its path."""
        out = Path(path)
        out.write_text(self.to_html(title=title), encoding="utf-8")
        return out

    def save_svg(self, path: str | Path, *, width: float | None = None,
                 height: float | None = None, theme: str = "light") -> Path:  # fmt: skip
        """Write the plot as an SVG image, drawn in Python (no browser needed: a script, a
        CI job); returns its path. It is the plot as shown: the zoom it was last shown with,
        the selection and an opened panel, every mark, axis and label a vector element.

        ```python
        t.save_svg("temperatures.svg")
        t.save_svg("slide.svg", width=1200, height=600, theme="dark")
        ```

        Args:
            path: The file to write.
            width: The image's width in CSS pixels (default: the width the plot was last
                shown at, else 800).
            height: The image's height in CSS pixels (default: as the plot lays out).
            theme: ``"light"`` or ``"dark"``.
        """
        from anytrellis.figure import figure_svg

        out = Path(path)
        out.write_text(figure_svg(self, width=width, height=height, theme=theme),
                       encoding="utf-8")  # fmt: skip
        return out

    def save_png(self, path: str | Path, *, width: float | None = None,
                 height: float | None = None, theme: str = "light",
                 scale: float = 2.0) -> Path:  # fmt: skip
        """Write the plot as a PNG image, drawn in Python as ``save_svg`` draws it, with
        ``scale`` pixels per CSS pixel (2: sharp on slides and high-density screens);
        returns its path. Needs ``resvg-py``: ``pip install "anytrellis[png]"``.

        ```python
        t.save_png("temperatures.png")
        t.save_png("thumbnail.png", width=400, scale=1)
        ```
        """
        from anytrellis.figure import THEMES, figure_svg, svg_to_png

        if not scale > 0:
            raise ValueError(f"scale must be above 0, got {scale}")
        svg = figure_svg(self, width=width, height=height, theme=theme)
        out = Path(path)
        out.write_bytes(svg_to_png(svg, scale, THEMES[theme]["bg"]))
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
            ends = [*layer.stat_args.get("x_columns", ()), *layer.stat_args.get("y_columns", ())]
            for name in [layer.x, layer.y, layer.x2, layer.y2, *layer.group, *layer.tooltip,
                         *ends]:  # fmt: skip
                if name is not None:
                    table.check(name)
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
        if self._link_group is not None and self._link_group.source is not None:
            self._link_group.relay()  # the selected rows, or the marks showing them, changed
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

    def _want_columns(self) -> None:
        """Tell each lazy table the columns the plot reads, so it reads them in one query."""
        shared: list[str | None] = [*self._row, *self._col, *self._wrap, *self._link]
        for name, order in self._orders.items():
            shared += [name, order.of]
        tables = [] if self._data is None else [self._data]
        for layer in self._layers:
            if layer.mark == "rule":
                continue
            table = self._table(layer)
            tables.append(table)
            ends = [*layer.stat_args.get("x_columns", ()), *layer.stat_args.get("y_columns", ())]
            table.want(layer.x, layer.y, layer.x2, layer.y2, layer.color, layer.text,
                       *layer.group, *layer.tooltip, *ends)  # fmt: skip
        for table in tables:
            table.want(*shared)

    def _build(self) -> tuple[dict[str, Any], Buffers]:
        self._want_columns()
        marks = [layer for layer in self._layers if layer.mark != "rule"]
        tables = [self._table(layer) for layer in marks]
        if self._data is not None:
            tables.insert(0, self._data)
        grid = build_grid(tables, row=self._row, col=self._col, wrap=self._wrap,
                          cols=self._cols, orders=self._orders,
                          keep_empty=self._keep_empty)  # fmt: skip
        npanels = len(grid.panels)
        pages = self._pages(grid)
        given = self._given_orders(tables)
        # every layer as the plain layers it draws: a summary (hist, box, ...) as its parts
        drawn: list[_Drawn] = []
        logs = [axis for axis in ("x", "y") if self._scales[axis] == "log"]
        for layer in self._layers:
            if layer.mark == "rule":
                drawn.append(_Drawn(layer, layer, self._data or Table({}), None))
                continue
            table = _scaled(layer, self._table(layer), logs)
            if layer.mark not in SUMMARIES:
                drawn.append(_Drawn(layer, layer, table, None))
                continue
            for part in summary_parts(layer, table, grid.assign(table), npanels):
                part.layer.stat = layer.mark
                drawn.append(_Drawn(layer, part.layer, part.table, part))
        self._drawn = drawn
        table_of = {id(d.layer): d.table for d in drawn}.__getitem__
        shown = [d.layer for d in drawn if d.layer.mark != "rule"]
        x_kind, x_levels = _axis(shown, lambda lr: table_of(id(lr)), "x", given)
        y_kind, y_levels = _axis(shown, lambda lr: table_of(id(lr)), "y", given)
        if "x" in logs:
            x_kind = "log"
        if "y" in logs:
            y_kind = "log"
        colors = _ColorScales(shown, lambda lr: table_of(id(lr)), self.palette, given)
        extents = {"x": Extent.empty(npanels), "y": Extent.empty(npanels)}
        plain = [lr for lr in marks if lr.mark not in SUMMARIES]
        bars_step = step_of([axis_values(table_of(id(lr)).column(lr.x), x_levels)  # ty: ignore[invalid-argument-type]
                             for lr in plain if lr.mark == "bars"])  # fmt: skip
        steps = {
            "bars": bars_step,
            "rect_x": 1.0 if x_levels is not None else step_of(
                [axis_values(table_of(id(lr)).column(lr.x), x_levels)  # ty: ignore[invalid-argument-type]
                 for lr in plain if lr.mark == "rect" and lr.x2 is None]),
            "rect_y": 1.0 if y_levels is not None else step_of(
                [axis_values(table_of(id(lr)).column(lr.y), y_levels)  # ty: ignore[invalid-argument-type]
                 for lr in plain if lr.mark == "rect" and lr.y2 is None]),
        }  # fmt: skip
        built: list[tuple[Layer, Table, Geometry | None]] = []
        rule_values: dict[str, list[float]] = {}
        self._plain = _plain_indices(drawn)
        self._colors = colors
        details: list[tuple[int, Detail]] = []
        sent: dict[int, _Sent] = {}
        with_cells: list[_Drawn] = []
        for d in drawn:
            layer = d.layer
            with_cells.append(d)
            if layer.mark == "rule":
                values = [_scalar(v, x_kind if layer.axis == "x" else y_kind,
                                  x_levels if layer.axis == "x" else y_levels)
                          for v in layer.values]  # fmt: skip
                rule_values[layer.name] = values
                extents[layer.axis].add_everywhere(values)
                built.append((layer, d.table, None))
                continue
            table = d.table
            detail: Detail | None = None
            if d.part is not None:
                geom = d.part.build(x_levels, y_levels, colors.levels)
                _paint(layer, table, geom, colors)
            else:
                geom, detail = _geometry(layer, table, grid, x_levels, y_levels, colors, steps,
                                         self._cell_colors(layer, table))  # fmt: skip
            extents["x"].add(geom.panel, geom.x0)
            extents["x"].add(geom.panel, geom.x1)
            extents["y"].add(geom.panel, geom.y0)
            extents["y"].add(geom.panel, geom.y1)
            if geom.base0 is not None and geom.base1 is not None:
                extents["y"].add(geom.panel, geom.base0)
                extents["y"].add(geom.panel, geom.base1)
            built.append((layer, table, geom))
            if detail is None:
                continue
            index = len(built) - 1
            details.append((index, detail))
            if isinstance(detail, LineDetail):
                sent.update(self._sent_of(index, layer, table, detail))
            else:  # its dense panels' cells, a layer after it: once the panels' sizes are known
                none = Table({"points": np.zeros(0)})
                cells = _cells_layer(layer, none)
                with_cells.append(_Drawn(d.user, cells, none, None, cells=True))
                built.append((cells, none, _no_geometry()))
        drawn = with_cells
        self._drawn = drawn
        self._geometry = built
        self._details = details
        zero = any(lr.mark in ("bars", "area") or lr.stat == "density" for lr in shown)
        xg = group_ids(grid, self._share["x"])
        yg = group_ids(grid, self._share["y"])
        xd = domains(extents["x"], xg, x_kind, band_size=len(x_levels or []))
        yd = domains(extents["y"], yg, y_kind, band_size=len(y_levels or []), zero_base=zero)
        x_origin = _origin(xd, x_kind)
        y_origin = _origin(yd, y_kind)
        self._axes = {"x": (x_kind, x_levels, x_origin), "y": (y_kind, y_levels, y_origin)}
        self._keys = {}
        if self._link:
            mark_entries = [(lr, tb) for lr, tb, g in built if g is not None]
            keys = link_keys([tb for _, tb in mark_entries], self._link)
            if all(k is None for k in keys):
                raise ValueError(f"link={list(self._link)}: no layer's data has these columns")
            self._keys = {id(lr): k for (lr, _), k in zip(mark_entries, keys, strict=True)}
        first = shown[0] if shown else None
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
            "layers": [],
            "legends": colors.legends(),
            "height": self.height,
            "panel_height": self.panel_height,
            "aspect": self.aspect,
            "legend_position": self.legend,
            "fit_y": self.fit_y,
            "pages": pages,
        }
        # dense points' cells: over each panel's domain, sized for the panel's pixels
        cell_details = [(i, dt) for i, dt in details if isinstance(dt, PointDetail)]
        if cell_details:
            from anytrellis.figure import layout

            boxes = {b.index: (b.rect.w, b.rect.h) for b in layout(spec, START_WIDTH).panels}
            size = next(iter(boxes.values()), (START_WIDTH, START_WIDTH / 2))
            sizes = [boxes.get(i, size) for i in range(npanels)]
            doms = [(*xd[i], *yd[i]) for i in range(npanels)]
            for index, detail in cell_details:
                assert isinstance(detail, PointDetail)
                detail.start_at(doms, sizes)
                layer, table = drawn[index].layer, drawn[index].table
                sent.update(self._sent_of(index, layer, table, detail))
                cells, cells_table, cells_geom, cells_part = sent[index + 1]
                drawn[index + 1] = replace(drawn[index + 1], layer=cells, table=cells_table,
                                           part=cells_part)  # fmt: skip
                built[index + 1] = (cells, cells_table, cells_geom)
        buffers = Buffers()
        layers_spec = []
        self._npanels = npanels
        self._sent = []
        self._full = []
        self._full_scene_cache = None
        self._window = self._wanted(spec)  # a paged plot: the pages around the one shown
        for i, (d, (layer, _table, geom)) in enumerate(zip(drawn, built, strict=True)):
            if geom is None:
                origin = x_origin if layer.axis == "x" else y_origin
                layers_spec.append(_rule_spec(layer, rule_values[layer.name], origin))
                self._full.append((layer, _table, None, None))
                self._sent.append((layer, _table, None, None))
                continue
            full = (layer, _table, geom, None) if layer.mark == "text" else \
                sent.get(i, (layer, _table, geom, d.part))  # fmt: skip
            self._full.append(full)
            entry = self._windowed(full)
            self._sent.append(entry)
            layers_spec.append(self._layer_spec(d, entry, buffers, self._window))
        self._start = list(self._full)
        # what each layer shows (zoomed in: in more detail), and its tooltips by coords
        self._shown_layers = list(layers_spec)
        self._detail_buffers = Buffers()
        self._history = {}
        for i, spec_layer in enumerate(layers_spec):
            self._remember(i, spec_layer)
        spec["layers"] = layers_spec
        return spec, buffers

    def _layer_spec(self, d: _Drawn, entry: _Sent, buffers: Buffers,
                    panels: frozenset[int] | None = None) -> dict[str, Any]:  # fmt: skip
        """A text or mark layer in the spec, as sent; ``panels``: the only ones it has data
        of (a paged plot's window)."""
        layer, table, geom, _ = entry
        if layer.mark != "text":
            out = self._mark_spec(d, entry, buffers)
        else:
            assert geom is not None
            out = _text_spec(layer, table, geom, self._npanels, buffers, self._axes["x"][2],
                             self._axes["y"][2])  # fmt: skip
        if panels is not None:
            out["panels"] = sorted(panels)
        return out

    def _wanted(self, spec: dict[str, Any]) -> frozenset[int] | None:
        """The panels whose data a paged plot sends (None: it does not page): those of the
        page shown and of the pages either side of it (turned to at once), and an opened
        panel."""
        pages = spec.get("pages")
        if pages is None:
            return None
        names = [_panel_name(p, i) for i, p in enumerate(spec["panels"])]
        paging = self.paging
        shown = panel_order(self._stats, names, paging)
        per = pages["rows"] * pages["cols"]
        page = min(max(int(paging.get("page", 0)), 0), page_count(len(shown), per) - 1)
        want = set(shown[max(0, (page - 1) * per) : (page + 2) * per])
        if self.focused in names:
            want.add(names.index(self.focused))
        return frozenset(want)

    def _windowed(self, entry: _Sent) -> _Sent:
        """A layer's entry with only the instances of the window's panels."""
        layer, table, geom, part = entry
        if self._window is None or geom is None:
            return entry
        inside = np.zeros(self._npanels, dtype=bool)
        inside[list(self._window)] = True
        return (layer, table, geom.take(np.flatnonzero(inside[geom.panel])), part)

    def _mark_spec(self, d: _Drawn, entry: _Sent, buffers: Buffers) -> dict[str, Any]:
        """A mark layer in the spec, as sent (``entry``: zoomed in, in more detail)."""
        layer, table, geom, part = entry
        assert geom is not None
        _, _, x_origin = self._axes["x"]
        _, _, y_origin = self._axes["y"]
        spec_layer = _layer_spec(layer, geom, self._npanels, buffers, self._colors, x_origin,
                                 y_origin, self._plain[id(d.user)])  # fmt: skip
        spec_layer["tooltip"] = bool(_tooltip_columns(layer, table))
        keys = self._keys.get(id(layer))
        spec_layer["link"] = (
            None if keys is None else buffers.add(keys[geom.rows].astype(np.uint32), "uint32")
        )
        spec_layer["hide"] = (
            list(part.hide) if part is not None else ["y"] if layer.mark == "band" else []
        )  # a band's y: its ymin and ymax, from Python
        family = part is not None and part.family
        # a summary's parts drawing the same rows (a box's body and lines) select together
        spec_layer["family"] = self._layers.index(d.user) if family else None
        spec_layer["groups"] = (
            buffers.add(geom.rows.astype(np.uint32), "uint32") if family else None
        )
        if part is not None:
            spec_layer.update(_inline_tips(layer, table, geom, buffers))
        return spec_layer

    def _cell_colors(self, layer: Layer, table: Table) -> Any:
        """RGBA of a points layer's cells, from their colour levels and mean numbers."""
        colors = self._colors
        name = layer.color

        def paint(n: int, mix: np.ndarray | None, means: np.ndarray | None) -> np.ndarray:
            if name is not None and name in table:
                if mix is not None:  # the levels' colours in proportion
                    palette = np.array([rgba(c) for c in colors.colors(name)], dtype=np.float64)
                    rgb = mix @ palette[:, :3] / np.maximum(mix.sum(axis=1), 1)[:, None]
                    out = np.full((n, 4), 255, dtype=np.uint8)
                    out[:, :3] = np.round(rgb).astype(np.uint8)
                    return out
                lo, hi = colors.ranges.get(name, (0.0, 1.0))
                assert means is not None
                return colormap_rgba(means, "viridis", lo, hi)
            solid = name if name is not None else colors.default(layer, self._plain[id(layer)])
            return np.tile(np.array(rgba(solid), dtype=np.uint8), (n, 1))

        return paint

    def _sent_of(self, index: int, layer: Layer, table: Table,
                 detail: Detail) -> dict[int, _Sent]:  # fmt: skip
        """What a layer in detail sends, at its windows: a line thinned; points, and the
        cells of its dense panels (the layer after it)."""
        if isinstance(detail, LineDetail):
            return {index: (layer, table, detail.geometry(), None)}
        cells_table, cells_geom, starts, rows = detail.cells()
        cells = _cells_layer(layer, cells_table)
        part = Part(cells, cells_table, _no_build, Members(starts, rows))
        return {index: (layer, table, detail.points(), None),
                index + 1: (cells, cells_table, cells_geom, part)}  # fmt: skip

    def _remember(self, index: int, spec_layer: dict[str, Any]) -> None:
        """Keep what spec layer ``index`` sent, by its coords: a tooltip asked for as the
        browser showed it finds it (the last ``TIP_HISTORY``)."""
        coords = spec_layer.get("coords")
        if coords is None:
            return
        self._history[(index, coords["id"])] = self._sent[index]
        while len(self._history) > TIP_HISTORY + len(self._sent):
            del self._history[next(iter(self._history))]

    def _shown_ids(self) -> list[str | None]:
        """The coords of each spec layer as shown."""
        return [(lr.get("coords") or {}).get("id") for lr in self._shown_layers]

    def _detail(self, view: dict[str, Any] | None) -> dict[str, Any] | None:
        """The layers to show in more (or less) detail for a view the browser reports, as a
        ``detail`` message; None: none changed."""
        spec, _ = self._scene()
        changed: set[int] = set()
        if self._details and view and view.get("panels"):
            shown = self._shown_panels(spec, view)
            for index, detail in self._details:
                if not detail.update(shown):
                    continue
                user = self._drawn[index].user
                for i, entry in self._sent_of(index, user, self._full[index][1], detail).items():
                    self._full[i] = entry
                    d = self._drawn[i]
                    if d.cells:  # the drawn layer's table and part: the cells', for selection
                        self._drawn[i] = replace(d, layer=entry[0], table=entry[1],
                                                 part=entry[3])  # fmt: skip
                    changed.add(i)
        window = self._wanted(spec)
        if window != self._window:  # another page: its panels' data, and its neighbours'
            self._window = window
            changed |= {i for i, entry in enumerate(self._full) if entry[2] is not None}
        layers: list[dict[str, Any]] = []
        for i in sorted(changed):
            entry = self._windowed(self._full[i])
            self._sent[i] = entry
            spec_layer = self._layer_spec(self._drawn[i], entry, self._detail_buffers,
                                          self._window)  # fmt: skip
            self._shown_layers[i] = spec_layer
            self._remember(i, spec_layer)
            of = spec["layers"][i]["coords"]["id"]
            layers.append({"index": i, "of": of, "layer": spec_layer})
        if not layers:
            return None
        # keep the buffers of the layers shown
        live = {ref for lr in self._shown_layers for ref in _buffer_ids(lr)}
        for buffer_id in [b for b in self._detail_buffers.data if b not in live]:
            del self._detail_buffers.data[buffer_id]
        return {"type": "detail", "layers": layers}

    def _shown_panels(self, spec: dict[str, Any], view: dict[str, Any]) -> dict[int, Shown]:
        """The panels a view shows: their ranges (axis units) and sizes."""
        _, _, x_origin = self._axes["x"]
        _, _, y_origin = self._axes["y"]
        xs = {int(g): r for g, r in view.get("x") or []}
        ys = {int(g): r for g, r in view.get("y") or []}
        out: dict[int, Shown] = {}
        for item in view.get("panels") or []:
            p, w, h = int(item[0]), float(item[1]), float(item[2])
            if not 0 <= p < len(spec["panels"]):
                continue
            panel = spec["panels"][p]
            x = xs.get(panel["xg"], panel["x"])
            y = ys.get(panel["yg"], panel["y"])
            out[p] = Shown(min(x) + x_origin, max(x) + x_origin, min(y) + y_origin,
                           max(y) + y_origin, w, h)  # fmt: skip
        return out

    def _send_detail(self) -> None:
        """Send the layers in detail for the view the browser reported, and a paged plot's
        panels around the page shown, if any changed (without a widget: for the images)."""
        if self._scene_cache is None:  # not built yet: it starts as it is now
            return
        message = self._detail(self._view)
        if message is not None and self._widget is not None:
            self._widget.send(message)

    def _shown_scene(self) -> tuple[dict[str, Any], Buffers]:
        """The spec and buffers as shown: layers zoomed in, in their detail (images)."""
        spec, buffers = self._scene()
        if not self._details and self._window is None:
            return spec, buffers
        both = Buffers()
        both.data = {**buffers.data, **self._detail_buffers.data}
        return {**spec, "layers": list(self._shown_layers)}, both

    def _full_scene(self) -> tuple[dict[str, Any], Buffers]:
        """The spec and buffers with every panel's data, as the plot starts: a saved page's
        (a paged plot's widget gets the panels around the page shown, as they are shown)."""
        spec, buffers = self._scene()
        if self._window is None:  # it does not page: the spec has every panel's data
            return spec, buffers
        if self._full_scene_cache is None:
            out = Buffers()
            layers = [
                spec["layers"][i] if entry[2] is None else self._layer_spec(d, entry, out)
                for i, (d, entry) in enumerate(zip(self._drawn, self._start, strict=True))
            ]
            self._full_scene_cache = ({**spec, "layers": layers}, out)
        return self._full_scene_cache

    def _highlight_entries(self) -> list[tuple[Layer, Any, Any]]:
        """Each spec layer's user layer, summary part and geometry, as sent."""
        self._scene()
        return [(d.user, part, geom)
                for d, (_, _, geom, part) in zip(self._drawn, self._sent, strict=True)]  # fmt: skip

    def _tooltip(self, layer_index: int, instance: int, of: str | None = None) -> list[list[str]]:
        """The tooltip columns of one instance: ``[[name, value], ...]``; ``of``: the
        layer's coords as the browser showed it."""
        self._scene()
        entry = self._history.get((layer_index, of)) if of else None
        layer, table, geom, _ = entry or self._sent[layer_index]
        names = _tooltip_columns(layer, table)
        if geom is None or not names:
            return []
        row = int(geom.rows[instance])
        return [[name, _text(table.raw(name)[row])] for name in names]


# ---- helpers ------------------------------------------------------------------------------

SCALES = ("linear", "log")
FROM_ZERO = ("bars", "area", "hist", "density")
"""Marks drawn from zero up, which a log y axis has no place for."""


def _scale(value: str) -> str:
    if value not in SCALES:
        raise ValueError(f"a scale is one of {SCALES}, got {value!r}")
    return value


def _scaled(layer: Layer, table: Table, logs: list[str]) -> Table:
    """A layer's table with its columns on log axes in log10 units."""
    if "y" in logs and layer.mark in FROM_ZERO:
        raise ValueError(
            f"{layer.mark}() draws from zero, which a log y axis has no place for; use "
            "points or lines, or a linear y"
        )
    names = set()
    if "x" in logs:
        names |= {n for n in (layer.x, layer.x2) if n is not None}
        names |= set(layer.stat_args.get("x_columns", ()))
    if "y" in logs:
        names |= {n for n in (layer.y, layer.y2) if n is not None}
        names |= set(layer.stat_args.get("y_columns", ()))
    return table.log_scaled(names) if names else table


@dataclass
class _Drawn:
    """A layer as drawn: a plain layer as given, or one part of a summary (``user``)."""

    user: Layer
    layer: Layer
    table: Table
    part: Part | None
    cells: bool = False
    """The cells of a points layer's dense panels (``detail``)."""


_Sent = tuple[Layer, Table, "Geometry | None", "Part | None"]
"""What a spec layer sends: its layer, table, geometry and summary part."""

TIP_HISTORY = 32
"""Layers sent in detail before that a tooltip can still be asked for."""


def _plain_indices(drawn: list[_Drawn]) -> dict[int, int]:
    """Per drawn layer (by id), the layers drawn in a default colour before it (a summary's
    parts: one)."""
    out: dict[int, int] = {}
    plain = 0
    last: Layer | None = None
    for d in drawn:
        if last is not None and d.user is not last:
            plain += last.mark != "text" and last.color is None and last.facet != "exclude"
        last = d.user if d.layer.mark != "rule" else last
        out.setdefault(id(d.layer), plain)
        out.setdefault(id(d.user), plain)
    return out


def _cells_layer(layer: Layer, table: Table) -> Layer:
    """The cells of a points layer's dense panels: rects of its colour, telling their
    points (and their colour)."""
    tips = [n for n in table.names if n != "points"]
    return Layer(mark="rect", name=layer.name, color=layer.color, facet=layer.facet,
                 opacity=layer.opacity, tooltip=["points", *tips])  # fmt: skip


def _no_geometry() -> Geometry:
    empty = np.zeros(0)
    return Geometry(np.zeros(0, dtype=np.int64), empty, empty, empty, empty,
                    np.zeros(0, dtype=np.int64))  # fmt: skip


def _no_build(*_: Any) -> Geometry:
    raise AssertionError("cells are built by their detail")


def _buffer_ids(spec_layer: dict[str, Any]) -> list[str]:
    """The buffers a spec layer refers to."""
    refs = [spec_layer.get(k) for k in ("coords", "starts", "base", "link", "groups",
                                         "tip_rows", "labels", "offsets", "colors")]  # fmt: skip
    color = spec_layer.get("color")
    if isinstance(color, dict):
        refs += [color.get("rgba"), color.get("codes")]
    return [r["id"] for r in refs if isinstance(r, dict) and "id" in r]


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
    """A value (a rule's position, a selection's end) in axis units."""
    if kind == "log":
        v = float(value)
        if not v > 0:
            raise ValueError(f"{value!r} is not on a log axis (it holds values above 0)")
        return float(np.log10(v))
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
        # a legend each: numbers with no values have none
        self.order = [n for n in self.order if n in self.levels or n in self.ranges]
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
    steps: dict[str, float],
    cell_colors: Any = None,
) -> tuple[Geometry, Detail | None]:
    """A plain layer's geometry, and its level of detail: a line of many points thinned,
    points drawn as cells where dense (the geometry: what Python selects, all of it)."""
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
        series = series_codes(table, extra)
        if len(panel) and np.bincount(panel).max() > THIN:
            xs, ys, ss = x[rows], y[rows], series[rows]
            order = np.lexsort((xs, ss, panel))
            detail = LineDetail(rows[order], panel[order], xs[order], ys[order], ss[order],
                                len(grid.panels), layer.step,
                                lambda g: _paint(layer, table, g, colors))  # fmt: skip
            if detail.thin.any():
                return detail.points, detail
        geom = line_geometry(rows, panel, x, y, series, layer.step)
    elif layer.mark == "area":
        extra = list(layer.group)
        if color_col is not None and color_col.kind == "category":
            extra.append(color_col.name)
        geom = area_geometry(rows, panel, x, y, series_codes(table, extra),
                             stack=layer.position == "stack")  # fmt: skip
    elif layer.mark == "band":
        assert layer.y2 is not None
        upper = axis_values(table.column(layer.y2), y_levels)
        extra = list(layer.group)
        if color_col is not None and color_col.kind == "category":
            extra.append(color_col.name)
        geom = band_geometry(rows, panel, x, y, upper, series_codes(table, extra))
    elif layer.mark in ("points", "text"):
        geom = point_geometry(rows, panel, x, y)
        numbers = x_levels is None and y_levels is None
        dense = len(geom.panel) > DENSE and np.bincount(geom.panel).max() > DENSE
        if layer.mark == "points" and numbers and cell_colors is not None and dense:
            _paint(layer, table, geom, colors)
            values = None
            if color_col is not None and color_col.kind == "number":
                values = color_col.values[geom.rows]
            levels = colors.levels.get(color_col.name) if color_col is not None else None
            name = None if color_col is None else color_col.name
            detail = PointDetail(geom, len(grid.panels), values, cell_colors, name, levels)
            return geom, detail
    elif layer.mark == "rect":
        x2 = axis_values(table.column(layer.x2), x_levels) if layer.x2 else None
        y2 = axis_values(table.column(layer.y2), y_levels) if layer.y2 else None
        geom = rect_geometry(rows, panel, x, y, x2, y2, x_step=steps["rect_x"],
                             y_step=steps["rect_y"], width=layer.bar_width,
                             height=layer.rect_height)  # fmt: skip
    else:
        step = 1.0 if x_levels is not None else steps["bars"]
        geom = bar_geometry(rows, panel, x, y, step=step, width=layer.bar_width, codes=codes,
                            ncodes=ncodes, position=layer.position)  # fmt: skip
    _paint(layer, table, geom, colors)
    return geom, None


def _paint(layer: Layer, table: Table, geom: Geometry, colors: _ColorScales) -> None:
    """Each instance's colour from the layer's colour column (none: one colour)."""
    if layer.color is None or layer.color not in table:
        return
    column = table.column(layer.color)
    if column.kind == "category":
        codes = axis_values(column, colors.levels[column.name]).astype(np.int64)
        palette = np.array([rgba(c) for c in colors.colors(column.name)], dtype=np.uint8)
        geom.codes = codes[geom.rows]
        geom.rgba = palette[geom.codes]
    else:
        lo, hi = colors.ranges.get(column.name, (0.0, 1.0))
        geom.rgba = colormap_rgba(column.values[geom.rows], "viridis", lo, hi)


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
    base = None
    if geom.base0 is not None and geom.base1 is not None:
        base = buffers.add(
            np.stack([geom.base0 - y_origin, geom.base1 - y_origin], axis=1), "float64",
            components=2,
        )  # fmt: skip
    return {
        "type": layer.mark,
        "name": layer.name,
        "count": geom.count,
        "base": base,
        "coords": buffers.add(coords, "float64", components=4),
        "starts": buffers.add(geom.starts(npanels), "uint32"),
        "color": color,
        "width": layer.width,
        "size": layer.size,
        "opacity": layer.opacity,
        "tooltip": bool(layer.tooltip),
        "context": layer.facet == "exclude",
        "step": layer.step if layer.mark == "line" else None,
    }


TIP_CELLS = 50_000
"""A summary's tooltips go in the spec (no round trip to Python; saved pages show them)
when its table has at most this many cells of them."""


def _inline_tips(layer: Layer, table: Table, geom: Geometry, buffers: Buffers) -> dict[str, Any]:
    """A summary part's tooltip text, per row of its table, and each instance's row."""
    names = _tooltip_columns(layer, table)
    if not names or table.n * len(names) > TIP_CELLS:
        return {}
    columns = [table.raw(name) for name in names]
    values = [[_text(col[r]) for col in columns] for r in range(table.n)]
    rows = buffers.add(geom.rows.astype(np.uint32), "uint32")
    return {"tips": {"names": names, "values": values}, "tip_rows": rows}


def _tooltip_columns(layer: Layer, table: Table) -> list[str]:
    """A layer's tooltip columns: those asked for, and a number colour column."""
    names = list(layer.tooltip)
    if layer.mark == "band" and layer.stat is None:
        names = [n for n in (layer.y, layer.y2) if n is not None] + names
    color = layer.color
    if color is not None and color in table and color not in names:
        names += [color] if table.column(color).kind == "number" else []
    return names


def _text_spec(
    layer: Layer,
    table: Table,
    geom: Geometry,
    npanels: int,
    buffers: Buffers,
    x_origin: float,
    y_origin: float,
) -> dict[str, Any]:
    """A text layer: points, and their labels as UTF-8 with offsets."""
    assert layer.text is not None
    raw = table.raw(layer.text)
    labels = [_text(raw[r]).encode("utf-8") for r in geom.rows]
    offsets = np.zeros(len(labels) + 1, dtype=np.uint32)
    np.cumsum([len(b) for b in labels], out=offsets[1:])
    data = np.frombuffer(b"".join(labels), dtype=np.uint8) if labels else np.zeros(0, np.uint8)
    coords = np.stack([geom.x0 - x_origin, geom.y0 - y_origin], axis=1)
    return {
        "type": "text",
        "name": layer.name,
        "count": geom.count,
        "coords": buffers.add(coords, "float64", components=2),
        "starts": buffers.add(geom.starts(npanels), "uint32"),
        "labels": buffers.add(data, "uint8"),
        "offsets": buffers.add(offsets, "uint32"),
        "colors": None if geom.rgba is None else buffers.add(geom.rgba, "uint8", components=4),
        "color": None if layer.color is None or layer.color in table else list(rgba(layer.color)),
        "size": layer.size,
        "align": layer.align,
        "dx": layer.dx,
        "dy": layer.dy,
        "opacity": layer.opacity,
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
