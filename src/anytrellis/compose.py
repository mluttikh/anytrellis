"""Different plots in one figure: ``a | b`` side by side, ``a / b`` one under the other,
``concat(a, b, c, d, cols=2)`` a grid, nested as deep as you like.

One layout everywhere, so the notebook, a saved page and an image agree: a grid of
``cols`` columns as wide as ``widths`` say (shares of the width left after the gaps),
``GAP`` px between plots, each row as high as its highest plot and each plot at its top.
In a notebook it is an ipywidgets ``GridBox`` of the plots' widgets (marimo: stacks of
them), in a page a CSS grid of their embeds (linked plots stay linked), in an image their
SVGs side by side (``figure.py``).
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from anytrellis.plot import Trellis

GAP = 24
"""Space between the plots (CSS px), across and down."""

TITLE_SPACE = 8
"""Space under a figure's title (CSS px)."""

Item = Union["Trellis", "Concat"]


class Concat:
    """Plots in one figure, side by side and one under another: made by ``a | b``,
    ``a / b`` or ``concat()``. Shown in a notebook, saved as one page (``save_html``) or
    one image (``save_svg``, ``save_png``)."""

    def __init__(
        self,
        items: Sequence[Item],
        *,
        cols: int | None = None,
        widths: Sequence[float] | None = None,
        title: str | None = None,
    ) -> None:
        from anytrellis.plot import Trellis

        items = list(items)
        if not items:
            raise ValueError("concat() needs a plot or more")
        for item in items:
            if not isinstance(item, Trellis | Concat):
                raise TypeError(
                    f"concat() takes Trellis plots and concat()s, got {type(item).__name__}"
                )
        cols = len(items) if cols is None else cols
        if not (isinstance(cols, int) and cols >= 1):
            raise ValueError(f"cols must be a whole number from 1, got {cols!r}")
        cols = min(cols, len(items))
        if widths is None:
            widths = [1.0] * cols
        widths = [float(w) for w in widths]
        if len(widths) != cols or not all(w > 0 for w in widths):
            raise ValueError(
                f"widths must be {cols} numbers above 0 (one per column), got {widths}"
            )
        if title is not None and not isinstance(title, str):
            raise TypeError(f"title must be a string, got {type(title).__name__}")
        self.items: list[Item] = items
        """The plots (and figures) in it, row by row."""
        self.cols = cols
        """How many columns."""
        self.widths = widths
        """Each column's share of the width."""
        self.title = title
        """The figure's title, over its plots (None: none)."""
        self._widget: Any = None

    # ---- making figures ----------------------------------------------------------------

    def __or__(self, other: Item) -> Concat:
        return beside(self, other)

    def __ror__(self, other: Item) -> Concat:
        return beside(other, self)

    def __truediv__(self, other: Item) -> Concat:
        return under(self, other)

    def __rtruediv__(self, other: Item) -> Concat:
        return under(other, self)

    @property
    def plots(self) -> list[Trellis]:
        """Every plot in it, nested figures' too, row by row."""
        out: list[Trellis] = []
        for item in self.items:
            out += item.plots if isinstance(item, Concat) else [item]
        return out

    def _rows(self) -> list[list[Item]]:
        return [self.items[i : i + self.cols] for i in range(0, len(self.items), self.cols)]

    def _bare(self) -> bool:
        """A plain row or column to add to: no title, its columns alike."""
        return self.title is None and len(set(self.widths)) <= 1

    # ---- in a notebook -------------------------------------------------------------------

    @property
    def widget(self) -> Any:
        """The figure in Jupyter: an ipywidgets ``GridBox`` of the plots' widgets."""
        if self._widget is None:
            import ipywidgets as widgets

            children = [item.widget for item in self.items]
            grid = widgets.GridBox(children, layout=widgets.Layout(
                grid_template_columns=_columns(self.widths), grid_gap=f"{GAP}px",
                align_items="flex-start", width="100%"))  # fmt: skip
            if self.title is None:
                self._widget = grid
            else:
                heading = widgets.HTML(_title_html(self.title))
                self._widget = widgets.VBox([heading, grid],
                                            layout=widgets.Layout(width="100%"))  # fmt: skip
        return self._widget

    def _repr_mimebundle_(self, **kwargs: Any) -> Any:
        return self.widget._repr_mimebundle_(**kwargs)

    def _display_(self) -> Any:
        """What marimo shows: stacks of the plots' widgets."""
        import marimo as mo

        rows = []
        for row in self._rows():
            shown = [item._display_() for item in row]
            shown += [mo.md("") for _ in range(self.cols - len(row))]  # a short last row
            rows.append(mo.hstack(shown, widths=list(self.widths), gap=GAP / 16, align="start"))
        body = rows[0] if len(rows) == 1 else mo.vstack(rows, gap=GAP / 16)
        if self.title is None:
            return body
        return mo.vstack([mo.Html(_title_html(self.title)), body], gap=0)

    # ---- a page --------------------------------------------------------------------------

    def _embed_html(self, links: dict[int, list[dict[str, Any]]] | None = None) -> str:
        """The figure's ``<div>``: a CSS grid of its plots' embeds (each with its marks'
        keys when it is linked, ``links``: a link's payloads, made once per link)."""
        from anytrellis.linking import saved_links

        if links is None:
            links = {}
        cells = []
        for item in self.items:
            if isinstance(item, Concat):
                inner = item._embed_html(links)
            else:
                group = item._link_group
                payload = None
                if group is not None:
                    if id(group) not in links:
                        links[id(group)] = saved_links(group)
                    payload = links[id(group)][group.plots.index(item)]
                inner = item._embed_html(payload)
            cells.append(f"<div style='min-width:0'>{inner}</div>")
        style = (f"display:grid;grid-template-columns:{_columns(self.widths)};"
                 f"gap:{GAP}px;align-items:start")  # fmt: skip
        grid = f"<div style='{html.escape(style)}'>{''.join(cells)}</div>"
        # its plots start together, a link's selection shown in each (standalone.ts)
        linked = any(p._link_group is not None for p in self.plots)
        kind = "anytrellis-concat anytrellis-link" if linked else "anytrellis-concat"
        title = _title_html(self.title) if self.title is not None else ""
        return f"<div class='{kind}'>{title}{grid}</div>"

    def to_html(self, *, title: str | None = None) -> str:
        """The figure as one standalone HTML page: data and code inside, no kernel needed;
        linked plots stay linked."""
        from anytrellis.plot import page_html

        name = title or self.title or next((p.title for p in self.plots if p.title), None)
        return page_html(self._embed_html(), name or "anytrellis")

    def save_html(self, path: str | Path, *, title: str | None = None) -> Path:
        """Write ``to_html`` to a file; returns its path.

        ```python
        (scatter | counts).save_html("cars.html")
        ```
        """
        out = Path(path)
        out.write_text(self.to_html(title=title), encoding="utf-8")
        return out

    # ---- an image ----------------------------------------------------------------------

    def _width(self) -> float:
        """The width it was last shown at (its plots', laid out), else ``DEFAULT_WIDTH`` a
        column (at least ``DEFAULT_WIDTH``)."""
        from anytrellis.figure import DEFAULT_WIDTH

        known = [self._shown_width(item) for item in self.items]
        shown = [w for w in known if w is not None]
        if len(shown) == len(known):
            cols = [max(shown[c :: self.cols]) for c in range(self.cols)]
            # a column of a share `s` of the width less the gaps: the whole, from each
            total = max(w * sum(self.widths) / s for w, s in zip(cols, self.widths, strict=True))
            return total + GAP * (self.cols - 1)
        return max(DEFAULT_WIDTH, DEFAULT_WIDTH / 2 * self.cols + GAP * (self.cols - 1))

    @staticmethod
    def _shown_width(item: Item) -> float | None:
        if isinstance(item, Concat):
            known = [Concat._shown_width(i) for i in item.items]
            return item._width() if all(w is not None for w in known) else None
        view = getattr(item, "_view", None) or {}
        width = view.get("width")
        return float(width) if width else None

    def _svg_parts(self, width: float, theme: str, ids: str) -> tuple[list[str], float]:
        """Its plots' SVGs, placed (``<svg x y>`` elements), and the height they take."""
        from anytrellis.figure import FONT_SIZE, HEADER, THEMES, TITLE, _n, figure_svg, fit

        th = THEMES[theme]
        room = width - GAP * (self.cols - 1)
        col_w = [room * w / sum(self.widths) for w in self.widths]
        col_x = [sum(col_w[:c]) + GAP * c for c in range(self.cols)]
        out: list[str] = []
        y = 0.0
        if self.title is not None:
            size = FONT_SIZE * TITLE
            text = html.escape(fit(self.title, width - 16, size, bold=True))
            out.append(f'<text x="8" y="{_n(1 + HEADER / 2 + 0.35 * size)}" '
                       f'font-size="{_n(size)}" font-weight="600" fill="{th["text"]}">'
                       f"{text}</text>")  # fmt: skip
            y = HEADER + TITLE_SPACE
        n = 0
        for r, row in enumerate(self._rows()):
            tallest = 0.0
            for c, item in enumerate(row):
                key = f"{ids}p{n}-"
                n += 1
                w = col_w[c]
                if isinstance(item, Concat):
                    parts, h = item._svg_parts(w, theme, key)
                    body = "".join(parts)
                    out.append(f'<svg x="{_n(col_x[c])}" y="{_n(y)}" width="{_n(w)}" '
                               f'height="{_n(h)}" overflow="visible">{body}</svg>')  # fmt: skip
                else:
                    svg = figure_svg(item, width=w, theme=theme, ids=key)
                    h = float(svg.split('height="', 1)[1].split('"', 1)[0])
                    head = '<svg xmlns="http://www.w3.org/2000/svg" '
                    out.append(svg.replace(head, f'<svg x="{_n(col_x[c])}" y="{_n(y)}" ', 1))
                tallest = max(tallest, h)
            y += tallest + (GAP if r < len(self._rows()) - 1 else 0)
        return out, y

    def _svg(self, width: float | None, theme: str) -> str:
        from anytrellis.figure import FONT, FONT_SIZE, THEMES, _n

        if theme not in THEMES:
            raise ValueError(f"theme must be one of {list(THEMES)}, got {theme!r}")
        width = float(width or self._width())
        least = 100 * self.cols + GAP * (self.cols - 1)
        if width < least:
            raise ValueError(
                f"width must be at least {least} px for {self.cols} columns, got {width}"
            )
        parts, height = self._svg_parts(width, theme, "")
        names = [p.title for p in self.plots if p.title]
        label = self.title or "; ".join(names) or f"{len(self.plots)} plots"
        w, h = _n(width), _n(height)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                f'viewBox="0 0 {w} {h}" font-family="{FONT}" font-size="{_n(FONT_SIZE)}" '
                f'role="img"><title>{html.escape(label)}</title>'
                f'<rect width="100%" height="100%" fill="{THEMES[theme]["bg"]}"/>'
                f"{''.join(parts)}</svg>")  # fmt: skip

    def _image_svg(self, width: float | str | None, theme: str) -> tuple[str, str | None]:
        """The figure's SVG at a width in CSS pixels or a length (``"180mm"``), and the
        unit for print it was given in (None: pixels)."""
        from anytrellis.figure import length

        w, unit = length(width, "width")
        return self._svg(w, theme), unit

    def save_svg(self, path: str | Path, *, width: float | str | None = None,
                 theme: str = "light") -> Path:  # fmt: skip
        """Write the figure as one SVG image, drawn in Python as each plot's ``save_svg``
        draws it, the plots where the notebook and the page put them; returns its path.

        Args:
            path: The file to write.
            width: The image's width in CSS pixels (default: as it was last shown, else
                400 a column, at least 800), or a length for print (``"180mm"``, as
                ``Trellis.save_svg``); each row is as high as its plots.
            theme: ``"light"`` or ``"dark"``.
        """
        from anytrellis.figure import print_size

        svg, unit = self._image_svg(width, theme)
        out = Path(path)
        out.write_text(print_size(svg, unit), encoding="utf-8")
        return out

    def save_png(self, path: str | Path, *, width: float | str | None = None,
                 theme: str = "light", scale: float | None = None,
                 dpi: float | None = None) -> Path:  # fmt: skip
        """Write the figure as a PNG image, as ``save_svg`` draws it, with ``scale`` pixels
        per CSS pixel (default 2) or ``dpi`` pixels per inch, recorded in the PNG; returns
        its path. Needs ``resvg-py``: ``pip install "anytrellis[png]"``."""
        from anytrellis.figure import THEMES, png_scale, svg_to_png

        zoom = png_scale(scale, dpi)
        svg, _ = self._image_svg(width, theme)
        out = Path(path)
        out.write_bytes(svg_to_png(svg, zoom, THEMES[theme]["bg"]))
        return out

    def save_pdf(self, path: str | Path, *, width: float | str | None = None,
                 theme: str = "light") -> Path:  # fmt: skip
        """Write the figure as one vector PDF, as ``save_svg`` draws it (``Trellis.save_pdf``);
        returns its path. Needs ``vl-convert-python``: ``pip install "anytrellis[pdf]"``."""
        from anytrellis.figure import svg_to_pdf

        svg, _ = self._image_svg(width, theme)
        out = Path(path)
        out.write_bytes(svg_to_pdf(svg))
        return out

    def __repr__(self) -> str:
        shape = f"{self.cols} column{'s' if self.cols != 1 else ''}"
        title = f", title={self.title!r}" if self.title else ""
        return f"Concat({len(self.items)} items in {shape}{title})"


def concat(*plots: Item, cols: int | None = None, widths: Sequence[float] | None = None,
           title: str | None = None) -> Concat:  # fmt: skip
    """Plots (or figures) in one figure: a row of them, or a grid of ``cols`` columns,
    filled row by row.

    ```python
    from anytrellis import concat

    concat(scatter, counts)                       # side by side, as scatter | counts
    concat(a, b, c, d, cols=2)                    # a grid: two rows of two
    concat(scatter, counts, widths=[2, 1], title="Cars")  # the first twice as wide
    ```

    Args:
        plots: The plots, and figures made by ``concat``, ``|`` or ``/``.
        cols: How many columns (default: every plot in one row; 1: one under another).
        widths: Each column's share of the width (default: equal).
        title: The figure's title, over its plots.
    """
    return Concat(plots, cols=cols, widths=widths, title=title)


def beside(left: Item, right: Item) -> Concat:
    """``left | right``: a row; a plain row on either side is added to, not nested."""
    items: list[Item] = []
    for side in (left, right):
        row = isinstance(side, Concat) and side._bare() and len(side._rows()) == 1
        items += side.items if row else [side]  # type: ignore[union-attr]
    return Concat(items)


def under(top: Item, bottom: Item) -> Concat:
    """``top / bottom``: a column; a plain column on either side is added to, not nested."""
    items: list[Item] = []
    for side in (top, bottom):
        column = isinstance(side, Concat) and side._bare() and side.cols == 1
        items += side.items if column else [side]  # type: ignore[union-attr]
    return Concat(items, cols=1)


def _columns(widths: Sequence[float]) -> str:
    """CSS grid columns: shares of the width less the gaps, none wider than its share."""
    return " ".join(f"minmax(0,{w:g}fr)" for w in widths)


def _title_html(title: str) -> str:
    """A figure's title, as a plot's own (widget.css .atr-title)."""
    from anytrellis.figure import FONT_SIZE, HEADER, TITLE

    style = (f"font-weight:600;font-size:{FONT_SIZE * TITLE:g}px;line-height:{HEADER}px;"
             f"padding:0 8px;margin-bottom:{TITLE_SPACE}px")  # fmt: skip
    return f"<div class='anytrellis-concat-title' style='{style}'>{html.escape(title)}</div>"
