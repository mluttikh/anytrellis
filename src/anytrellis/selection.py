"""Selections: a brush (an interval on x, on y or both, or a lasso) that selects the marks
it meets, in every panel or in one, or marks clicked; grown by link keys to every row
sharing a key with a selected one.

The browser and Python agree on what a brush selects: a point inside it, a line or area
segment with either end inside (both its rows), a bar or rect overlapping it (its row). A
lasso is a polygon (the brush's ranges its bounding box) and selects the same way: a point
inside it by the even-odd rule, a bar or rect it overlaps. A click selects the marks within
``near`` of the point clicked, as a brush that small would. Context layers
(``facet="exclude"``) are never selected.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from anytrellis.data import Column, Table
from anytrellis.layers import Geometry
from anytrellis.transforms import TRANSFORMS, inverse

Brush = dict[str, Any]
"""``{"x": [lo, hi] or None, "y": [lo, hi] or None, "panel": index or None}``, the ranges
in axis units relative to the axis origins (as the spec's coordinates are); no panel:
every panel. A lasso adds ``"lasso": [[x, y], ...]``, its corners (the ranges: their
bounding box); marks clicked are ``"at": [[x, y, panel or None], ...]`` with ``"near":
[dx, dy]``, how far from each a mark may be (the ranges: None)."""

Polygon = np.ndarray
"""A lasso's corners, ``(m, 2)``, in order."""


def in_polygon(x: np.ndarray, y: np.ndarray, poly: Polygon) -> np.ndarray:
    """The points inside the polygon, by the even-odd rule: a ray to the right crosses an
    edge when the edge's ends lie on either side of the point's y (one at or under it, the
    other over it) and it meets the edge right of the point (selection.ts: inPolygon)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    inside = np.zeros(np.broadcast(x, y).shape, dtype=bool)
    m = len(poly)
    for i in range(m):
        xi, yi = poly[i]
        xj, yj = poly[i - 1]
        if yi == yj:
            continue  # (a ray along it crosses nothing)
        with np.errstate(invalid="ignore", divide="ignore"):  # (the order query.py has)
            cross = ((yi > y) != (yj > y)) & (x < (y - yi) * (xj - xi) / (yj - yi) + xi)
        inside ^= cross
    return inside


def boxes_meet_polygon(x0: np.ndarray, x1: np.ndarray, y0: np.ndarray, y1: np.ndarray,
                       poly: Polygon) -> np.ndarray:  # fmt: skip
    """The boxes (bars, rects, ``x0 <= x1``, ``y0 <= y1``) that overlap the polygon: a
    corner inside it, one of its corners inside the box, or an edge of each crossing."""
    hit = np.zeros(len(x0), dtype=bool)
    for cx, cy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        hit |= in_polygon(cx, cy, poly)
    for vx, vy in poly:
        hit |= (vx >= x0) & (vx <= x1) & (vy >= y0) & (vy <= y1)
    sides = ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0))
    m = len(poly)
    for i in range(m):
        px, py = poly[i - 1]
        qx, qy = poly[i]
        for ax, ay, bx, by in sides:
            hit |= _cross(px, py, qx, qy, ax, ay, bx, by)
    return hit


def _cross(px: float, py: float, qx: float, qy: float, ax: Any, ay: Any, bx: Any,
           by: Any) -> np.ndarray:  # fmt: skip
    """Whether segment p-q crosses each segment a-b (strictly: each's ends either side of
    the other)."""

    def side(ox: Any, oy: Any, ux: Any, uy: Any, vx: Any, vy: Any) -> Any:
        return np.sign((ux - ox) * (vy - oy) - (uy - oy) * (vx - ox))

    return (side(px, py, qx, qy, ax, ay) * side(px, py, qx, qy, bx, by) < 0) & (
        side(ax, ay, bx, by, px, py) * side(ax, ay, bx, by, qx, qy) < 0)  # fmt: skip


def row_mask(mark: str, geom: Geometry, n: int, x: tuple[float, float] | None,
             y: tuple[float, float] | None, panel: int | None = None,
             lasso: Polygon | None = None,
             at: Sequence[tuple[float, float, int | None]] | None = None,
             near: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:  # fmt: skip
    """The rows of a layer's table (``n`` of them) whose marks meet the brush; ``x`` and
    ``y`` in the geometry's units (absolute), None: any; ``panel``: only its marks;
    ``lasso``: only those meeting the polygon too. ``at``: the marks within ``near`` of
    these points (each in its panel, or in all), in place of the brush."""
    rows = np.zeros(n, dtype=bool)
    if at is not None:
        nx, ny = near
        for px, py, p in at:
            rows |= row_mask(mark, geom, n, (px - nx, px + nx), (py - ny, py + ny), p)
        return rows
    x0, x1 = sorted(x) if x is not None else (-np.inf, np.inf)
    y0, y1 = sorted(y) if y is not None else (-np.inf, np.inf)
    here = np.ones(geom.count, dtype=bool) if panel is None else geom.panel == panel

    def boxes(hit: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
        """Those of the boxes ``hit`` that meet the lasso."""
        if lasso is not None:
            i = np.flatnonzero(hit)
            ax, bx = geom.x0[i], geom.x1[i]
            hit[i] = boxes_meet_polygon(np.minimum(ax, bx), np.maximum(ax, bx), lo[i], hi[i],
                                        lasso)  # fmt: skip
        return hit

    if mark == "band" and geom.base0 is not None and geom.base1 is not None:
        lo = np.minimum.reduce([geom.y0, geom.y1, geom.base0, geom.base1])
        hi = np.maximum.reduce([geom.y0, geom.y1, geom.base0, geom.base1])
        hit = here & (np.maximum(geom.x0, geom.x1) >= x0) & (np.minimum(geom.x0, geom.x1) <= x1)
        hit = boxes(hit & (hi >= y0) & (lo <= y1), lo, hi)
        rows[geom.rows[hit]] = True
        if geom.rows_end is not None:
            rows[geom.rows_end[hit]] = True
        return rows
    if mark in ("bars", "rect"):
        lo, hi = np.minimum(geom.y0, geom.y1), np.maximum(geom.y0, geom.y1)
        hit = here & (
            (np.maximum(geom.x0, geom.x1) >= x0) & (np.minimum(geom.x0, geom.x1) <= x1)
            & (hi >= y0) & (lo <= y1)
        )  # fmt: skip
        rows[geom.rows[boxes(hit, lo, hi)]] = True
        return rows

    def points(hit: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
        """Those of the points ``hit`` inside the lasso."""
        if lasso is not None:
            i = np.flatnonzero(hit)
            hit[i] = in_polygon(px[i], py[i], lasso)
        return hit

    start = here & (geom.x0 >= x0) & (geom.x0 <= x1) & (geom.y0 >= y0) & (geom.y0 <= y1)
    rows[geom.rows[points(start, geom.x0, geom.y0)]] = True
    if geom.rows_end is not None:
        end = here & (geom.x1 >= x0) & (geom.x1 <= x1) & (geom.y1 >= y0) & (geom.y1 <= y1)
        rows[geom.rows_end[points(end, geom.x1, geom.y1)]] = True
    return rows


def link_keys(tables: Sequence[Table], names: Sequence[str]) -> list[np.ndarray | None]:
    """One integer per row for each table's combination of the link columns, the same
    integer for the same values across tables; None for a table without all of them."""
    have = [t for t in tables if all(name in t for name in names)]
    if not have:
        return [None] * len(tables)
    key = _shared_codes([t.column(names[0]) for t in have])
    for name in names[1:]:
        _, key = np.unique(key, return_inverse=True)  # small, before the next column's
        codes = _shared_codes([t.column(name) for t in have])
        key = key.ravel().astype(np.int64) * (int(codes.max(initial=0)) + 1) + codes
    if len(names) > 1:
        _, key = np.unique(key, return_inverse=True)
        key = key.ravel().astype(np.int64)
    out: list[np.ndarray | None] = []
    at = 0
    for table in tables:
        if not all(name in table for name in names):
            out.append(None)
            continue
        out.append(key[at : at + table.n])
        at += table.n
    return out


def _shared_codes(columns: list[Column]) -> np.ndarray:
    """The tables' values of one link column, concatenated, as one integer per value."""
    if all(c.kind != "category" for c in columns) and len({c.kind for c in columns}) == 1:
        values = np.concatenate([c.values for c in columns])
        if len(values) and np.isfinite(values).all():  # whole numbers (ids): the keys
            lo, hi = values.min(), values.max()
            if lo >= 0 and hi < 2**32 and (values == np.floor(values)).all():
                return values.astype(np.int64)
    elif all(c.kind == "category" for c in columns):
        labels = list(dict.fromkeys(lv for c in columns for lv in c.levels))
        lookup = {lv: i for i, lv in enumerate(labels)}
        parts = []
        for c in columns:
            codes = c.level_codes()
            mapped = np.array([lookup[lv] for lv in c.levels] + [-1], dtype=np.int64)[codes]
            if (codes < 0).any():  # values outside declared levels: by their text
                return _text_codes(columns)
            parts.append(mapped)
        return np.concatenate(parts)
    else:
        return _text_codes(columns)
    _, inverse = np.unique(values, return_inverse=True)
    return inverse.ravel().astype(np.int64)


def _text_codes(columns: list[Column]) -> np.ndarray:
    values = np.concatenate([c.values.astype(str) for c in columns])
    _, inverse = np.unique(values, return_inverse=True)
    return inverse.ravel().astype(np.int64)


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
    if kind in TRANSFORMS:  # a log, sqrt or symlog axis: the values its units stand for
        return (inverse(kind, lo), inverse(kind, hi))
    return (lo, hi)


def value_out(v: float, kind: str, levels: list[str] | None, origin: float) -> Any:
    """A point's coordinate in axis units (relative) as a Python value: a time as
    datetime64, a transformed axis's the value it stands for, a category axis's its
    position (0: the first category)."""
    v = float(v) + origin
    if kind == "time":
        return np.datetime64(round(v), "ms")
    if kind in TRANSFORMS:
        return inverse(kind, v)
    return v
