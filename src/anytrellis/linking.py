"""Linked plots: a selection made in one plot shows in the others (crossfiltering).

```python
import anytrellis as at

scatter = at.Trellis(cars).points(x="weight", y="mpg")
counts = at.Trellis(cars).hist(x="horsepower")
at.link(scatter, counts)       # brush cars in the scatter: their share of each bin fills
```

The plots of a link share one selection. A brush drawn in one plot (or ``select()``) selects
rows of its data; the other plots highlight the same rows: the rows of the same table (the
same object passed as data), or with ``on=`` the rows sharing those columns' values, from
any table. Points, lines and boxes of those rows light up, the rest fade; a histogram's bars
fill to the share of their count that is selected. A brush in another plot of the link takes
over: the first plot's brush goes, and it shows the new selection in turn.

Python relays the selection: the plots are linked in a running kernel, not in a saved page.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from anytrellis.selection import link_keys

if TYPE_CHECKING:
    from anytrellis.data import Table
    from anytrellis.plot import Trellis

Masks = dict[int, np.ndarray | None]
"""Per layer of a plot (``id`` of the layer as given): the rows of its data highlighted, or
None (its data is not linked: drawn as it is)."""


class Link:
    """Plots sharing one selection: made by ``link()``."""

    def __init__(self, plots: Sequence[Trellis], on: str | Sequence[str] | None) -> None:
        from anytrellis.plot import Trellis

        plots = list(plots)
        if len(plots) < 2:
            raise ValueError("link() needs two plots or more")
        for p in plots:
            if not isinstance(p, Trellis):
                raise TypeError(f"link() takes Trellis plots, got {type(p).__name__}")
            if p._link_group is not None:
                raise ValueError(f"{p!r} is linked already: unlink() it first")
            if p._load == "pages":
                raise ValueError("a plot reading pages (load='pages') can't be linked yet")
        if len({id(p) for p in plots}) != len(plots):
            raise ValueError("a plot is given twice")
        self.plots = plots
        self.on: tuple[str, ...] = (on,) if isinstance(on, str) else tuple(on or ())
        self.source: Trellis | None = None
        """The plot whose brush makes the selection, or None: nothing selected."""
        self._busy = False
        self._keys: tuple[tuple[int, ...], list[Table], list[np.ndarray | None]] | None = None
        for p in plots:
            p._link_group = self
            p._live(True)
        for p in plots:  # a plot with a selection already: the first one leads
            if p._current_selection() is not None:
                self.changed(p)
                break

    def unlink(self) -> None:
        """Each plot on its own again (a plot's own brush stays; highlights go)."""
        for p in self.plots:
            p._link_group = None
            p._live(False)
            p._set_highlight(None)
        self.source = None

    def changed(self, plot: Trellis) -> None:
        """``plot``'s own selection changed (a brush in the browser, or ``select()``)."""
        if self._busy:
            return
        if plot._current_selection() is None:
            if plot is self.source:
                self.clear()
            return
        self.source = plot
        self._busy = True
        try:  # one brush in a link: the others' go
            for p in self.plots:
                if p is not plot and p._current_selection() is not None:
                    p._set_selection(None)
        finally:
            self._busy = False
        self.relay()

    def clear(self) -> None:
        """Nothing selected, in any plot of the link."""
        source, self.source = self.source, None
        if source is not None and source._current_selection() is not None:
            self._busy = True
            try:
                source._set_selection(None)
            finally:
                self._busy = False
        for p in self.plots:
            p._set_highlight(None)

    def relay(self) -> None:
        """Show the source's selection in the other plots."""
        source = self.source
        if source is None:
            return
        chosen = source._selected_masks()
        for p in self.plots:
            p._set_highlight(None if p is source else self._masks_for(p, chosen))

    def _masks_for(self, plot: Trellis, chosen: list[tuple[Table, np.ndarray]]) -> Masks:
        """The rows of ``plot``'s layers' data that the source's ``chosen`` rows select."""
        layers = plot._mark_layers()
        out: Masks = {}
        if not self.on:  # the same rows of the same table
            for layer in layers:
                native = plot._table(layer).native
                masks = [m for t, m in chosen if t.native is native]
                out[id(layer)] = np.logical_or.reduce(masks) if masks else None
            return out
        tables = [t for t, _ in chosen] + [plot._table(lr) for lr in layers]
        keys = self._link_keys(tables)
        known = [k for k in keys if k is not None]
        if not known:
            return {id(lr): None for lr in layers}
        picked = np.zeros(max(int(k.max(initial=-1)) for k in known) + 1, dtype=bool)
        for (_, mask), k in zip(chosen, keys[: len(chosen)], strict=True):
            if k is not None:
                picked[k[mask]] = True
        for layer, k in zip(layers, keys[len(chosen) :], strict=True):
            out[id(layer)] = None if k is None else picked[k]
        return out

    def _link_keys(self, tables: list[Table]) -> list[np.ndarray | None]:
        """``link_keys`` of these tables (the same integer for the same values), kept while
        the tables are the same: a brush dragged asks for them many times a second."""
        ids = tuple(id(t) for t in tables)
        if self._keys is None or self._keys[0] != ids:
            self._keys = (ids, list(tables), link_keys(tables, self.on))
        return self._keys[2]

    def __repr__(self) -> str:
        on = f", on={list(self.on)}" if self.on else ""
        return f"Link({len(self.plots)} plots{on})"


def link(*plots: Trellis, on: str | Sequence[str] | None = None) -> Link:
    """Link plots: a selection made in one shows in all of them.

    ```python
    at.link(scatter, counts)                 # the same table: the same rows
    at.link(by_year, by_country, on="iso")   # any tables: rows with the same "iso"
    ```

    Args:
        plots: Two plots or more, each in one link at most.
        on: Column(s) whose values identify a thing across the plots' tables: selecting
            rows selects every row sharing their values. Default: the plots draw the same
            table (the same object), and a selection is its rows.

    Returns:
        The link: ``unlink()`` it to set the plots apart again.
    """
    return Link(plots, on)


def highlight_message(
    entries: list[Any], masks: Masks | None
) -> tuple[dict[str, Any], list[bytes]]:
    """The ``highlight`` message for a plot's drawn layers (``(user layer, part, geometry)``
    per spec layer): per layer a mask of its instances (bits, the first in the lowest bit of
    the first byte), a histogram bar's selected
    share (float32), or None (drawn as it is)."""
    if masks is None:
        return {"type": "highlight", "layers": None}, []
    layers: list[dict[str, Any] | None] = []
    buffers: list[bytes] = []
    selected = total = 0
    for user, part, geom in entries:
        rows = masks.get(id(user)) if geom is not None else None
        if rows is None or geom is None:
            layers.append(None)
            continue
        if part is None:
            hit = rows[geom.rows]
            if geom.rows_end is not None:
                hit = hit | rows[geom.rows_end]
            value, kind = hit, "mask"
        else:  # a summary's row: the share of the rows it stands for that are selected
            starts = part.members.starts
            sizes = np.diff(starts)
            inside = np.r_[0, np.cumsum(rows[part.members.rows], dtype=np.int64)]
            count = inside[starts[1:]] - inside[starts[:-1]]
            share = np.divide(count, sizes, out=np.zeros(len(sizes)), where=sizes > 0)
            if part.layer.stat == "hist" and part.layer.mark in ("bars", "rect"):
                value, kind = share[geom.rows].astype(np.float32), "fraction"
            else:
                value, kind = count[geom.rows] > 0, "mask"
        layers.append({kind: len(buffers), "count": len(value)})
        packed = np.packbits(value, bitorder="little") if kind == "mask" else value
        buffers.append(packed.tobytes())
        selected += int(np.count_nonzero(value))
        total += len(value)
    message = {"type": "highlight", "layers": layers, "selected": selected, "total": total}
    return message, buffers
