"""Selections: a brush (an interval on x, on y or both) that selects the marks it meets, in
every panel or in one, grown by link keys to every row sharing a key with a selected one.

The browser and Python agree on what a brush selects: a point inside it, a line segment
with either end inside (both its rows), a bar overlapping it (its row). Context layers
(``facet="exclude"``) are never selected.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from anytrellis.data import Table
from anytrellis.layers import Geometry

Brush = dict[str, Any]
"""``{"x": [lo, hi] or None, "y": [lo, hi] or None, "panel": index or None}``, the ranges
in axis units relative to the axis origins (as the spec's coordinates are); no panel:
every panel."""


def row_mask(mark: str, geom: Geometry, n: int, x: tuple[float, float] | None,
             y: tuple[float, float] | None, panel: int | None = None) -> np.ndarray:  # fmt: skip
    """The rows of a layer's table (``n`` of them) whose marks meet the brush; ``x`` and
    ``y`` in the geometry's units (absolute), None: any; ``panel``: only its marks."""
    x0, x1 = sorted(x) if x is not None else (-np.inf, np.inf)
    y0, y1 = sorted(y) if y is not None else (-np.inf, np.inf)
    rows = np.zeros(n, dtype=bool)
    here = np.ones(geom.count, dtype=bool) if panel is None else geom.panel == panel
    if mark == "bars":
        hit = here & (
            (np.maximum(geom.x0, geom.x1) >= x0) & (np.minimum(geom.x0, geom.x1) <= x1)
            & (np.maximum(geom.y0, geom.y1) >= y0) & (np.minimum(geom.y0, geom.y1) <= y1)
        )  # fmt: skip
        rows[geom.rows[hit]] = True
        return rows
    start = here & (geom.x0 >= x0) & (geom.x0 <= x1) & (geom.y0 >= y0) & (geom.y0 <= y1)
    rows[geom.rows[start]] = True
    if geom.rows_end is not None:
        end = here & (geom.x1 >= x0) & (geom.x1 <= x1) & (geom.y1 >= y0) & (geom.y1 <= y1)
        rows[geom.rows_end[end]] = True
    return rows


def link_keys(tables: Sequence[Table], names: Sequence[str]) -> list[np.ndarray | None]:
    """One integer per row for each table's combination of the link columns, the same
    integer for the same values across tables; None for a table without all of them."""
    parts: list[np.ndarray | None] = []
    for table in tables:
        if not all(name in table for name in names):
            parts.append(None)
            continue
        cols = [table.column(name).values.astype(str) for name in names]
        key = cols[0]
        for col in cols[1:]:
            key = np.char.add(np.char.add(key, "\x1f"), col)
        parts.append(key)
    present = [p for p in parts if p is not None]
    if not present:
        return [None] * len(tables)
    _, inverse = np.unique(np.concatenate(present), return_inverse=True)
    inverse = inverse.ravel().astype(np.int64)
    out: list[np.ndarray | None] = []
    at = 0
    for part in parts:
        if part is None:
            out.append(None)
            continue
        out.append(inverse[at : at + len(part)])
        at += len(part)
    return out


def grow(mask: np.ndarray, keys: np.ndarray | None, selected_keys: np.ndarray) -> np.ndarray:
    """The rows of ``mask`` and every row whose key is selected."""
    if keys is None or not len(selected_keys):
        return mask
    return mask | np.isin(keys, selected_keys)


def range_in(value: Any, kind: str, levels: list[str] | None, origin: float,
             to_scalar: Any) -> list[float] | None:  # fmt: skip
    """A range from Python (``(lo, hi)``; a category axis: one category or several) in axis
    units relative to the origin."""
    if value is None:
        return None
    if kind == "band":
        wanted = [value] if isinstance(value, str) or not isinstance(value, Sequence) else value
        index = [to_scalar(v, kind, levels) for v in wanted]
        return [min(index) - 0.5, max(index) + 0.5]
    if isinstance(value, str) or not isinstance(value, Sequence) or len(value) != 2:
        raise ValueError(f"a range is (low, high); got {value!r}")
    lo, hi = (to_scalar(v, kind, levels) - origin for v in value)
    return [min(lo, hi), max(lo, hi)]


def range_out(r: list[float] | None, kind: str, levels: list[str] | None, origin: float) -> Any:
    """A range in axis units (relative) as Python values: times as datetime64, a category
    axis as the categories whose band centre is inside."""
    if r is None:
        return None
    lo, hi = sorted(float(v) + origin for v in r)
    if kind == "band":
        return [lv for i, lv in enumerate(levels or []) if lo <= i <= hi]
    if kind == "time":
        return (np.datetime64(round(lo), "ms"), np.datetime64(round(hi), "ms"))
    return (lo, hi)
