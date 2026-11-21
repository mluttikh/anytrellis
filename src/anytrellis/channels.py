"""Shape, size and dash: columns drawn as a point's shape or size, or a line's dash.

Each is a scale shared by column name across the layers, as colours are: a category
column's levels get a shape or a dash each, in order (cycling when there are more levels
than shapes or dashes); a number column's values a point's size, by area. The browser
draws them from codes and factors per instance (scene.ts), and ``figure.py`` alike.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import Any

import numpy as np

from anytrellis.data import Table
from anytrellis.layers import Geometry, Layer

SHAPES = ("circle", "square", "triangle", "diamond", "plus", "cross", "triangle-down")
"""A shape column's shapes, a level each, in this order (renderers: the same codes)."""

DASHES: dict[str, tuple[float, ...]] = {
    "solid": (),
    "dashed": (4, 4),
    "dotted": (1, 3),
    "dotdash": (1, 3, 4, 3),
    "longdash": (7, 3),
    "twodash": (2, 2, 6, 2),
}
"""A dash column's patterns, a level each, in this order: dash and gap lengths in line
widths (as ggplot2's), each dash with its caps."""

GREY = "#4a5260"
"""A channel legend's swatches when its marks are coloured by a column."""

SIZE_RANGE = (2.0, 14.0)
"""A size column's smallest and largest points (diameters, CSS px)."""


def shape_code(shape: str) -> int:
    """A shape's code (its index in SHAPES)."""
    if shape not in SHAPES:
        raise ValueError(f"shape must be a column or one of {SHAPES}, got {shape!r}")
    return SHAPES.index(shape)


def dash_units(dash: Iterable[float], width: float) -> list[float]:
    """A dash given in px (``dash=(4, 3)``, as a rule's) in line widths."""
    out = [float(v) for v in dash]
    if len(out) % 2 or any(not v >= 0 for v in out) or (out and not sum(out) > 0):
        raise ValueError(f"dash: pairs of dash and gap lengths (px), got {tuple(dash)!r}")
    unit = max(width, 1.0)
    return [v / unit for v in out]


def size_factors(values: np.ndarray, lo: float, hi: float, smallest: float,
                 largest: float) -> np.ndarray:  # fmt: skip
    """Each value's diameter as a share of the largest: by area, so that a value twice
    another has twice its ink above the smallest point (as ggplot2's scale_size)."""
    span = hi - lo
    t = np.clip((values - lo) / span, 0, 1) if span > 0 else np.full(len(values), 0.5)
    diameter = smallest + (largest - smallest) * np.sqrt(t)
    return np.where(np.isfinite(values), diameter / largest, np.nan).astype(np.float32)


def size_breaks(lo: float, hi: float) -> list[float]:
    """A size legend's values: round numbers inside ``lo`` to ``hi``, at most five (the
    smallest round step that gives no more)."""
    if not hi > lo:
        return [float(lo)]
    power = 10.0 ** np.floor(np.log10((hi - lo) / 6))
    for step in (m * power * k for k in (1, 10, 100) for m in (1, 2, 2.5, 5)):
        first = np.ceil(lo / step - 1e-9) * step
        out = [float(v) for v in np.arange(first, hi + step * 1e-9, step)]
        if len(out) <= 5:
            return [round(v, 12) + 0.0 for v in out] if len(out) >= 2 else [float(lo), float(hi)]
    return [float(lo), float(hi)]


def size_label(v: float) -> str:
    """A size legend's value: ``40``, ``2.5``, ``20k``, ``1.5M``."""
    a = abs(v)
    for div, suffix in ((1e12, "T"), (1e9, "G"), (1e6, "M"), (1e4, "k")):
        if a >= div:
            return f"{v / div:.3g}{suffix}"
    return f"{v:.4g}"


class Channels:
    """The shape, dash and size scales of the layers' columns, shared by column name."""

    def __init__(
        self,
        layers: list[Layer],
        table_of: Callable[[Layer], Table],
        given: dict[str, tuple[str, ...]],
        reorder: Callable[[list[str], tuple[str, ...] | None], list[str]],
    ) -> None:
        self.shapes: dict[str, list[str]] = {}
        """A shape column's levels."""
        self.dashes: dict[str, list[str]] = {}
        """A dash column's levels."""
        self.sizes: dict[str, tuple[float, float]] = {}
        """A size column's range, and the points' smallest and largest diameters."""
        self.size_px: dict[str, tuple[float, float]] = {}
        self.drawn: dict[tuple[str, str], list[Layer | None]] = {}
        """A channel legend's layers not coloured by a column (None: one that is): their
        colour is its swatches'."""
        self.width: dict[str, float] = {}
        """A dash column's line width, for its legend."""
        for layer in layers:
            table = table_of(layer)
            for kind, name in (("shape", layer.shape), ("dash", layer.dash_by)):
                if name is None or name not in table:
                    continue
                column = table.column(name)
                if column.kind != "category" and layer.second:
                    continue  # a number colour: its colormap alone
                if column.kind != "category":
                    raise ValueError(
                        f"{layer.name}: {kind}={name!r} draws a {kind} a category, and "
                        f"{name!r} holds {column.kind}s (as_category() reads it as "
                        "categories)"
                    )
                seen = (self.shapes if kind == "shape" else self.dashes).setdefault(name, [])
                seen.extend(v for v in reorder(list(column.levels), given.get(name))
                            if v not in seen)  # fmt: skip
                self._swatch(kind, name, layer, table)
                if kind == "dash":
                    self.width[name] = max(self.width.get(name, 0.0), layer.width)
            name = layer.size_by
            if name is None:
                continue
            if name not in table:
                raise ValueError(f"{layer.name}: size={name!r} is not a column")
            column = table.column(name)
            if column.kind != "number":
                raise ValueError(f"{layer.name}: size={name!r} sizes points by a number "
                                 f"column, and {name!r} holds {column.kind}s")  # fmt: skip
            whole = table.span(name)  # load="pages": of every row
            if whole is None:
                finite = column.values[np.isfinite(column.values)]
                whole = (float(finite.min()), float(finite.max())) if len(finite) else None
            if whole is not None:
                lo, hi = self.sizes.get(name, (np.inf, -np.inf))
                self.sizes[name] = (min(lo, whole[0]), max(hi, whole[1]))
            a, b = self.size_px.get(name, (np.inf, -np.inf))
            self.size_px[name] = (min(a, layer.size_range[0]), max(b, layer.size_range[1]))
            self._swatch("size", name, layer, table)

    def _swatch(self, kind: str, name: str, layer: Layer, table: Table) -> None:
        colored = layer.color is not None and layer.color in table
        self.drawn.setdefault((kind, name), []).append(None if colored else layer)

    def _color(self, kind: str, name: str, color_of: Callable[[Layer], str]) -> str:
        """A channel legend's swatches' colour: its layers' one colour, else grey."""
        seen = {None if lr is None else color_of(lr) for lr in self.drawn.get((kind, name), [])}
        one = seen.pop() if len(seen) == 1 else None
        return one or GREY

    def key(self) -> tuple[Any, ...]:
        """What the codes and sizes are made from."""
        return (tuple((k, tuple(v)) for k, v in self.shapes.items()),
                tuple((k, tuple(v)) for k, v in self.dashes.items()),
                tuple(self.sizes.items()), tuple(self.size_px.items()))  # fmt: skip

    def paint(self, layer: Layer, table: Table, geom: Geometry) -> None:
        """Each instance's shape, size and dash from the layer's columns."""
        if layer.shape is not None and layer.shape in table and layer.shape in self.shapes:
            geom.shapes = self._codes(table, layer.shape, self.shapes, len(SHAPES))[geom.rows]
        if layer.dash_by is not None and layer.dash_by in table and \
                layer.dash_by in self.dashes:  # fmt: skip
            geom.dashes = self._codes(table, layer.dash_by, self.dashes, len(DASHES))[geom.rows]
        name = layer.size_by
        if name is not None and name in table:
            lo, hi = self.sizes.get(name, (0.0, 1.0))
            values = table.column(name).values[geom.rows].astype(np.float64)
            geom.sizes = size_factors(values, lo, hi, *layer.size_range)

    @staticmethod
    def _codes(table: Table, name: str, scale: dict[str, list[str]], n: int) -> np.ndarray:
        column = table.column(name)
        levels = scale[name]
        lookup = np.array([levels.index(v) % n if v in levels else 0 for v in column.levels]
                          + [0], dtype=np.uint8)  # fmt: skip
        return lookup[column.level_codes()]

    def shape_of(self, name: str, label: str) -> int:
        return self.shapes[name].index(label) % len(SHAPES)

    def dash_of(self, name: str, label: str) -> list[float]:
        return list(list(DASHES.values())[self.dashes[name].index(label) % len(DASHES)])

    def legends(self, colored: dict[str, dict[str, Any]], color_of: Callable[[Layer], str],
                scale: float) -> list[dict[str, Any]]:  # fmt: skip
        """The colour legends (``colored``: by column) given these columns' shapes and
        dashes, when a column is both; and a legend each for the others, and for sizes.
        ``scale``: the theme's context, as the marks are scaled."""
        out: list[dict[str, Any]] = []
        for kind, scales in (("shape", self.shapes), ("dash", self.dashes)):
            for name, levels in scales.items():
                lg: dict[str, Any] | None = colored.get(name)
                if lg is None or lg["kind"] != "category":
                    lg = {"title": name, "kind": kind, "labels": list(levels),
                          "colors": [self._color(kind, name, color_of)] * len(levels)}  # fmt: skip
                    out.append(lg)
                if kind == "shape":
                    lg["shapes"] = [self.shape_of(name, v) if v in levels else 0
                                    for v in lg["labels"]]  # fmt: skip
                else:
                    lg["dashes"] = [self.dash_of(name, v) if v in levels else []
                                    for v in lg["labels"]]  # fmt: skip
                    lg["line_width"] = max(lg.get("line_width", 0.0), self.width[name] * scale)
        for name, (lo, hi) in self.sizes.items():
            smallest, largest = self.size_px[name]
            values = size_breaks(lo, hi)
            factors = size_factors(np.array(values), lo, hi, smallest, largest)
            out.append({"title": name, "kind": "size", "labels": [size_label(v) for v in values],
                        "sizes": [round(float(f) * largest * scale, 3) for f in factors],
                        "colors": [self._color("size", name, color_of)] * len(values)})  # fmt: skip
        return out


# ---- drawn in Python (figure.py), as the browser draws them (channels.ts) -----------------

_SQUARE, _TRIANGLE, _ARM, _BAR = 0.8, 1.25, 1.05, 0.33


def _unit_corners(code: int) -> np.ndarray:
    """A shape's corners at radius 1 about 0 (screen y down); none: a circle."""
    s = _SQUARE
    if code == 1:
        return np.array([[-s, -s], [s, -s], [s, s], [-s, s]])
    if code in (2, 6):
        f = 1 if code == 2 else -1
        R, h = _TRIANGLE, _TRIANGLE * 0.8660254
        return np.array([[0, -f * R], [h, f * R / 2], [-h, f * R / 2]])
    if code == 3:
        d = s * np.sqrt(2)
        return np.array([[0, -d], [d, 0], [0, d], [-d, 0]])
    if code in (4, 5):
        a, t = _ARM, _BAR
        plus = np.array([[-t, -a], [t, -a], [t, -t], [a, -t], [a, t], [t, t], [t, a], [-t, a],
                         [-t, t], [-a, t], [-a, -t], [-t, -t]])  # fmt: skip
        if code == 4:
            return plus
        k = np.sqrt(0.5)
        return np.stack([plus[:, 0] * k - plus[:, 1] * k, plus[:, 0] * k + plus[:, 1] * k], 1)
    return np.zeros((0, 2))


def shape_paths(codes: np.ndarray, x: np.ndarray, y: np.ndarray, r: np.ndarray) -> list[str]:
    """Each point's shape as an SVG path (``d``)."""
    out: list[str] = []
    for code, cx, cy, rr in zip(codes.tolist(), x.tolist(), y.tolist(), r.tolist(), strict=True):
        corners = _unit_corners(int(code))
        if not len(corners):
            out.append(f"M{cx - rr:.2f} {cy:.2f}a{rr:.2f} {rr:.2f} 0 1 0 {2 * rr:.2f} 0"
                       f"a{rr:.2f} {rr:.2f} 0 1 0 {-2 * rr:.2f} 0z")  # fmt: skip
            continue
        pts = corners * rr + [cx, cy]
        out.append("M" + "L".join(f"{px:.2f} {py:.2f}" for px, py in pts.tolist()) + "z")
    return out


def _capsule_pattern(px: list[float], width: float) -> list[float]:
    """As channels.ts: each dash less its round caps, its gap the more."""
    out = list(px)
    for k in range(0, len(out) - 1, 2):
        on = max(0.0, out[k] - width)
        out[k + 1] += out[k] - on
        out[k] = on
    return out


def dash_pattern(dash: list[float], width: float) -> list[float]:
    """A legend's dash (line widths) as an SVG dasharray of round-capped dashes (px; a
    dot's dash nearly 0), as channels.ts's drawGlyph sets it."""
    px = _capsule_pattern([v * max(width, 1.0) for v in dash], width)
    return [max(v, 0.001) if k % 2 == 0 else v for k, v in enumerate(px)]


def dash_pieces(ax: np.ndarray, ay: np.ndarray, bx: np.ndarray, by: np.ndarray,
                codes: np.ndarray | None, patterns: list[list[float]],
                width: float) -> tuple[np.ndarray, np.ndarray]:  # fmt: skip
    """A dashed line's segments (screen px) cut into dashes, as channels.ts cuts them: each
    dash's ends (n, 4) and its segment's index."""
    unit = max(width, 1.0)
    pats = [_capsule_pattern([v * unit for v in p], width) for p in patterns]
    out: list[tuple[float, float, float, float]] = []
    src: list[int] = []
    k, left = 0, 0.0
    prev: tuple[float, float, int] | None = None
    rows = zip(ax.tolist(), ay.tolist(), bx.tolist(), by.tolist(), strict=True)
    for i, (x0, y0, x1, y1) in enumerate(rows):
        code = 0 if codes is None else int(codes[i])
        pat = pats[code] if code < len(pats) else []
        length = math.hypot(x1 - x0, y1 - y0)
        if not math.isfinite(length):
            prev = None
            continue
        if not pat:
            out.append((x0, y0, x1, y1))
            src.append(i)
            prev = None
            continue
        if prev != (x0, y0, code):
            k, left = 0, pat[0]
        prev = (x1, y1, code)
        pos = 0.0
        for _ in range(1_000_000):
            step = min(left, length - pos)
            if k % 2 == 0:
                t0 = pos / length if length > 0 else 0.0
                t1 = (pos + step) / length if length > 0 else 0.0
                out.append((x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0,
                            x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1))  # fmt: skip
                src.append(i)
            pos += step
            left -= step
            if left > 1e-9:
                break
            k = (k + 1) % len(pat)
            left = pat[k]
            if pos >= length:
                break
    return np.array(out, dtype=np.float64).reshape(-1, 4), np.array(src, dtype=np.int64)
