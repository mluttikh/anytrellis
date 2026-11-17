"""Colours: one colour for a layer, or a column mapped to colours (categories to a palette,
numbers to a colormap), decided in Python and sent as RGBA bytes."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

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
by a survey of preference; matplotlib's ``petroff10``. The minimal look's palette."""

PALETTES: dict[str, list[str]] = {
    "petroff10": PETROFF10,
    "petroff8": [
        "#1845fb", "#ff5e02", "#c91f16", "#c849a9", "#adad7d", "#86c8dd", "#578dff", "#656364",
    ],
    "petroff6": ["#5790fc", "#f89c20", "#e42536", "#964a8b", "#9c9ca1", "#7a21dd"],
    "tab10": TAB10,
}  # fmt: skip
"""Named category palettes (``palette="tab10"``)."""

LOOKS = ("minimal", "classic")
"""How a plot looks (``Trellis(theme=)``): ``"minimal"``, the default (no panel fill, strips
as titles, a faint grid where it helps, the y title over the axis, Petroff's colours), or
``"classic"`` (filled panels and strips, a full grid, titles on their side, tab10)."""

LOOK_PALETTES = {"minimal": "petroff10", "classic": "tab10"}
"""Each look's category palette."""


def palette_of(palette: str | Sequence[str] | None, look: str = "minimal") -> list[str]:
    """A palette's colours: a name in ``PALETTES``, a list of colours, or None (the look's)."""
    if palette is None or (not isinstance(palette, str) and not list(palette)):
        palette = LOOK_PALETTES[look]
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

COLORMAPS = {
    "viridis": [
        "#440154", "#472d7b", "#3b528b", "#2c728e", "#21918c",
        "#28ae80", "#5ec962", "#addc30", "#fde725",
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
}  # fmt: skip
COLORMAPS["RdBu_r"] = COLORMAPS["RdBu"][::-1]

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


def colormap_rgba(values: np.ndarray, name: str, lo: float, hi: float) -> np.ndarray:
    """Numbers as RGBA bytes along a colormap, ``lo``..``hi`` spanning it; NaN in grey."""
    if name not in COLORMAPS:
        raise ValueError(f"unknown colormap {name!r}; built in: {sorted(COLORMAPS)}")
    anchors = np.array([rgba(c)[:3] for c in COLORMAPS[name]], dtype=np.float64)
    span = hi - lo if hi > lo else 1.0
    t = np.clip((values - lo) / span, 0.0, 1.0)
    pos = np.nan_to_num(t, nan=0.0) * (len(anchors) - 1)
    i = np.minimum(pos.astype(np.int64), len(anchors) - 2)
    f = (pos - i)[:, None]
    rgb = anchors[i] * (1 - f) + anchors[i + 1] * f
    out = np.empty((len(values), 4), dtype=np.uint8)
    out[:, :3] = np.round(rgb).astype(np.uint8)
    out[:, 3] = 255
    out[np.isnan(values)] = rgba(MISSING_COLOR)
    return out
