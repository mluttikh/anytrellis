"""Colours: one colour for a layer, or a column mapped to colours (categories to a palette,
numbers to a colormap), decided in Python and sent as RGBA bytes."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np

from anytrellis.formats import number_format

TAB10 = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]  # fmt: skip
"""matplotlib's tab10: the categorical colours, in order."""

PETROFF10 = [
    "#3f90da", "#ffa90e", "#bd1f01", "#94a4a2", "#832db6",
    "#a96b59", "#e76300", "#b9ac70", "#717581", "#92dadd",
]  # fmt: skip
"""Petroff's ten colours (arXiv 2107.02270), chosen for colour-vision deficiency and ranked
by a survey of preference; matplotlib's ``petroff10``. The minimal theme's palette."""

PALETTES: dict[str, list[str]] = {
    "petroff10": PETROFF10,
    "petroff8": [
        "#1845fb", "#ff5e02", "#c91f16", "#c849a9", "#adad7d", "#86c8dd", "#578dff", "#656364",
    ],
    "petroff6": ["#5790fc", "#f89c20", "#e42536", "#964a8b", "#9c9ca1", "#7a21dd"],
    "tab10": TAB10,
    "observable10": [
        "#4269d0", "#efb118", "#ff725c", "#6cc5b0", "#3ca951",
        "#ff8ab7", "#a463f2", "#97bbf5", "#9c6b4e", "#9498a0",
    ],
    "okabe-ito": [
        "#e69f00", "#56b4e9", "#009e73", "#f0e442", "#0072b2", "#d55e00", "#cc79a7", "#000000",
    ],
}  # fmt: skip
"""Named category palettes (``palette="tab10"``). observable10 is d3's ``schemeObservable10``,
Observable Plot's default (the framed theme's). okabe-ito: Okabe and Ito's eight colours for
colour-vision deficiency (Color Universal Design), black last."""


def palette_of(palette: str | Sequence[str]) -> list[str]:
    """A palette's colours: a name in ``PALETTES``, or a list of colours (each checked)."""
    if isinstance(palette, str):
        if palette not in PALETTES:
            raise ValueError(f"unknown palette {palette!r}; built in: {sorted(PALETTES)}, "
                             "or give a list of colours")  # fmt: skip
        return list(PALETTES[palette])
    colors = list(palette)
    for c in colors:
        rgba(c)  # an unknown colour raises here, not when it is drawn
    return colors


CONTEXT_COLOR = "#b8bec6"
"""The colour of context layers (``facet="exclude"``): the other panels' data, in grey."""

MISSING_COLOR = "#a8adb3"
"""Rows without a colour value."""

COLORMAPS: dict[str, list[str]] = {
    "viridis": [
        "#440154", "#472d7b", "#3b528b", "#2c728e", "#21918c",
        "#28ae80", "#5ec962", "#addc30", "#fde725",
    ],
    "cividis": [
        "#00204d", "#00336f", "#39486b", "#575c6d", "#707173",
        "#8a8779", "#a69d75", "#c4b56c", "#e4cf5b", "#ffea46",
    ],
    "magma": [
        "#000004", "#1c1044", "#4f127b", "#812581", "#b5367a",
        "#e55064", "#fb8761", "#fec287", "#fcfdbf",
    ],
    "Blues": [
        "#f7fbff", "#deebf7", "#c6dbef", "#9dcae1", "#6aaed6",
        "#4191c6", "#2070b4", "#08509b", "#08306b",
    ],
    "RdBu": [
        "#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#f7f7f7",
        "#d1e5f0", "#92c5de", "#4393c3", "#2166ac", "#053061",
    ],
    "PuOr": [
        "#7f3b08", "#b35806", "#e08214", "#fdb863", "#fee0b6", "#f7f7f7",
        "#d8daeb", "#b2abd2", "#8073ac", "#542788", "#2d004b",
    ],
}  # fmt: skip
COLORMAPS.update({f"{name}_r": colors[::-1] for name, colors in list(COLORMAPS.items())})
"""Colormaps for numbers, low to high, as matplotlib's: viridis, cividis (for colour-vision
deficiency) and magma run dark to light; Blues is one hue; RdBu and PuOr diverge from a light
middle (red and orange low). ``_r``: reversed."""

DIVERGING = ("RdBu", "RdBu_r", "PuOr", "PuOr_r")
COLOR_SCALES = ("linear", "diverging", "binned", "quantile")

_NAMED = {
    "black": "#000000", "white": "#ffffff", "gray": "#808080", "grey": "#808080",
    "red": "#d62728", "green": "#2ca02c", "blue": "#1f77b4", "orange": "#ff7f0e",
    "purple": "#9467bd", "brown": "#8c564b", "pink": "#e377c2", "olive": "#bcbd22",
    "cyan": "#17becf", "yellow": "#ffd43b", "teal": "#0ca678", "navy": "#1c3d78",
    "lightgray": "#c8cdd3", "lightgrey": "#c8cdd3",
}  # fmt: skip
_NAMED.update({f"tab:{n}": c for n, c in zip(
    ("blue", "orange", "green", "red", "purple", "brown", "pink", "gray", "olive", "cyan"),
    TAB10, strict=True,
)})  # fmt: skip
_HEX = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def rgba(color: str) -> tuple[int, int, int, int]:
    """A CSS hex colour or a basic name as RGBA bytes."""
    text = _NAMED.get(color.strip().lower(), color.strip())
    m = _HEX.match(text)
    if not m:
        raise ValueError(
            f"unknown colour {color!r}; use a hex colour such as '#1f77b4' or a basic name"
        )
    h = m.group(1)
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    r, g, b, a = (int(h[i : i + 2], 16) for i in range(0, 8, 2))
    return r, g, b, a


def is_color(text: str) -> bool:
    try:
        rgba(text)
    except ValueError:
        return False
    return True


def hex_of(color: Sequence[int]) -> str:
    return "#" + "".join(f"{int(c):02x}" for c in color[:3])


def palette_colors(palette: Sequence[str] | None, n: int) -> list[str]:
    """``n`` categorical colours, cycling the palette (tab10 by default)."""
    colors = list(palette) if palette else TAB10
    return [colors[i % len(colors)] for i in range(n)]


def colormap_of(colormap: str | Sequence[str]) -> list[str]:
    """A colormap's colours, low to high: a name in ``COLORMAPS``, or a list of colours (at
    least two, each checked)."""
    if isinstance(colormap, str):
        if colormap not in COLORMAPS:
            names = sorted(n for n in COLORMAPS if not n.endswith("_r"))
            raise ValueError(f"unknown colormap {colormap!r}; built in: {names} (and each "
                             "reversed, '_r'), or give a list of colours")  # fmt: skip
        return list(COLORMAPS[colormap])
    colors = list(colormap)
    if len(colors) < 2:
        raise ValueError("a colormap of your own needs at least two colours")
    for c in colors:
        rgba(c)
    return colors


def ramp_rgba(t: np.ndarray, colormap: str | Sequence[str]) -> np.ndarray:
    """Positions 0..1 along a colormap as RGBA bytes (between its colours: mixed); NaN in
    grey."""
    anchors = np.array([rgba(c)[:3] for c in colormap_of(colormap)], dtype=np.float64)
    t = np.asarray(t, dtype=np.float64)
    pos = np.nan_to_num(np.clip(t, 0.0, 1.0), nan=0.0) * (len(anchors) - 1)
    i = np.minimum(pos.astype(np.int64), len(anchors) - 2)
    f = (pos - i)[:, None]
    rgb = anchors[i] * (1 - f) + anchors[i + 1] * f
    out = np.empty((len(t), 4), dtype=np.uint8)
    out[:, :3] = np.round(rgb).astype(np.uint8)
    out[:, 3] = 255
    out[np.isnan(t)] = rgba(MISSING_COLOR)
    return out


def colormap_rgba(values: np.ndarray, name: str | Sequence[str], lo: float,
                  hi: float) -> np.ndarray:  # fmt: skip
    """Numbers as RGBA bytes along a colormap, ``lo``..``hi`` spanning it; NaN in grey."""
    span = hi - lo if hi > lo else 1.0
    return ramp_rgba((np.asarray(values, dtype=np.float64) - lo) / span, name)


def _nice_step(span: float, count: float) -> float:
    """A 1, 2 or 5 times a power of ten step giving about ``count`` steps (ticks.ts)."""
    raw = span / count
    power = 10.0 ** np.floor(np.log10(raw))
    f = raw / power
    return float((1 if f < 1.5 else 2 if f < 3.5 else 5 if f < 7.5 else 10) * power)


@dataclass(frozen=True)
class NumberScale:
    """How a number colour column takes its colours (``Trellis.colormap``).

    ``linear``: lowest to highest along the colormap. ``diverging``: both sides of
    ``midpoint`` equally deep, the middle colour at it. ``binned``: about ``bins`` steps of
    round width, a colour each. ``quantile``: ``bins`` steps holding as many values each."""

    colormap: str | tuple[str, ...] | None = None
    scale: str = "linear"
    midpoint: float = 0.0
    bins: int = 5

    def __post_init__(self) -> None:
        if self.scale not in COLOR_SCALES:
            raise ValueError(f"a colour scale is one of {COLOR_SCALES}, got {self.scale!r}")
        if (
            not isinstance(self.bins, int)
            or isinstance(self.bins, bool)
            or not 2 <= self.bins <= 20
        ):
            raise ValueError(f"bins must be a whole number from 2 to 20, got {self.bins!r}")
        if not np.isfinite(self.midpoint):
            raise ValueError(f"midpoint must be a number, got {self.midpoint!r}")
        if self.colormap is not None:
            colormap_of(self.colormap)

    @property
    def colors(self) -> list[str]:
        """The colormap's colours (default: viridis; diverging, RdBu reversed: red high)."""
        if self.colormap is None:
            return colormap_of("RdBu_r" if self.scale == "diverging" else "viridis")
        return colormap_of(self.colormap)

    def breaks(self, lo: float, hi: float, values: np.ndarray | None) -> list[float] | None:
        """A stepped scale's bin edges, lowest first (others: None)."""
        if self.scale == "binned":
            if not hi > lo:
                return [lo, lo + 1.0]
            step = _nice_step(hi - lo, self.bins)
            first, last = np.floor(lo / step + 1e-9), np.ceil(hi / step - 1e-9)
            return [float(k * step) for k in np.arange(first, max(last, first + 1) + 1)]
        if self.scale == "quantile":
            finite = np.asarray(values if values is not None else [], dtype=np.float64)
            finite = finite[np.isfinite(finite)]
            if len(finite) == 0:
                return [lo, hi if hi > lo else lo + 1.0]
            edges = np.unique(np.quantile(finite, np.linspace(0, 1, self.bins + 1)))
            return edges.tolist() if len(edges) > 1 else [float(edges[0]), float(edges[0]) + 1.0]
        return None

    def positions(self, values: np.ndarray, lo: float, hi: float,
                  breaks: list[float] | None) -> np.ndarray:  # fmt: skip
        """Each value's place along the colormap, 0 to 1 (NaN: NaN)."""
        v = np.asarray(values, dtype=np.float64)
        if breaks is not None:
            k = len(breaks) - 1
            i = np.clip(np.searchsorted(np.asarray(breaks[1:-1]), v, side="right"), 0, k - 1)
            t = (i + 0.5) / k
        elif self.scale == "diverging":
            reach = max(abs(hi - self.midpoint), abs(lo - self.midpoint)) or 1.0
            t = 0.5 + 0.5 * (v - self.midpoint) / reach
        else:
            t = (v - lo) / (hi - lo if hi > lo else 1.0)
        return np.where(np.isnan(v), np.nan, t)

    def rgba(self, values: np.ndarray, lo: float, hi: float,
             breaks: list[float] | None) -> np.ndarray:  # fmt: skip
        return ramp_rgba(self.positions(values, lo, hi, breaks), self.colors)

    def legend(self, lo: float, hi: float, breaks: list[float] | None,
               fmt: Callable[[float], str] | None) -> dict[str, Any]:  # fmt: skip
        """A legend's look: a gradient over lo..hi, or a stepped scale's bins as entries."""
        if breaks is None:
            if self.scale == "diverging":  # the gradient as the values take it
                stops = np.linspace(lo, hi, 17)
                return {
                    "kind": "number",
                    "colors": [hex_of(c) for c in self.rgba(stops, lo, hi, None)],
                }
            return {"kind": "number", "colors": self.colors}
        if fmt is None:
            if self.scale == "binned":
                step = breaks[1] - breaks[0]
                digits = max(0, -int(np.floor(np.log10(step) + 1e-9)))
                fmt = number_format(f",.{digits}f")
            else:
                fmt = number_format(",.3~r")
        mids = [(a + b) / 2 for a, b in pairwise(breaks)]
        colors = [hex_of(c) for c in self.rgba(np.array(mids), lo, hi, breaks)]
        labels = [_span(fmt(a), fmt(b)) for a, b in pairwise(breaks)]
        return {"kind": "bins", "labels": labels, "colors": colors}


def _span(a: str, b: str) -> str:
    """A bin's label: ``10–20``; with a minus in it, spaced: ``−5 – 0``."""
    return f"{a} – {b}" if "−" in a + b else f"{a}–{b}"
