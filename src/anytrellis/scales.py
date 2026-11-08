"""Position scales: each axis's kind, and each panel's domain after scale sharing.

``share`` per axis: ``"all"`` (every panel the same domain: the default, so panels compare),
``"row"`` / ``"col"`` (the same within a grid row / column), ``"page"`` (the same within a
page of ``page=``), or ``"none"`` (each panel its own). Panels with the same domain form a
group, zoomed together in the browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from anytrellis.facets import Grid

AxisKind = Literal["number", "time", "band", "log"]
"""``log``: numbers in log10 units (a log scale); padded and zoomed like numbers."""
Share = Literal["all", "row", "col", "page", "none"]

PAD = 0.04
"""Room on each side of a continuous domain, as a fraction of its span."""


def share_mode(value: bool | str) -> Share:
    """``True``/``"all"``, ``False``/``"none"``/``"free"``, ``"row"``, ``"col"`` or
    ``"page"``."""
    if value is True or value == "all":
        return "all"
    if value is False or value in ("none", "free"):
        return "none"
    if value in ("row", "col", "page"):
        return value
    raise ValueError(f"share: expected True, False, 'row', 'col' or 'page', got {value!r}")


@dataclass
class Extent:
    """The data range in each panel along one axis (NaN where a panel has none)."""

    lo: np.ndarray
    hi: np.ndarray
    hard_lo: np.ndarray
    """True where the low end is a bar's base at 0, kept without padding."""

    @classmethod
    def empty(cls, panels: int) -> Extent:
        return cls(np.full(panels, np.nan), np.full(panels, np.nan), np.zeros(panels, bool))

    def add(self, panel: np.ndarray, values: np.ndarray) -> None:
        ok = np.isfinite(values)
        if not ok.any():
            return
        p, v = panel[ok], values[ok]
        lo = np.full(len(self.lo), np.inf)
        hi = np.full(len(self.hi), -np.inf)
        np.minimum.at(lo, p, v)
        np.maximum.at(hi, p, v)
        self.lo = np.fmin(self.lo, np.where(np.isinf(lo), np.nan, lo))
        self.hi = np.fmax(self.hi, np.where(np.isinf(hi), np.nan, hi))

    def add_everywhere(self, values: list[float]) -> None:
        finite = [v for v in values if np.isfinite(v)]
        if finite:
            self.lo = np.fmin(self.lo, min(finite))
            self.hi = np.fmax(self.hi, max(finite))


def group_ids(grid: Grid, share: Share) -> list[int]:
    """The group of each panel: panels in one group share a domain."""
    if share == "all":
        return [0] * len(grid.panels)
    if share == "row":
        return [p.row for p in grid.panels]
    if share == "col":
        return [p.col for p in grid.panels]
    if share == "page":
        if grid.page_of is None:
            raise ValueError("share 'page' shares a scale within each page: give page=")
        return grid.page_of.tolist()
    return [p.index for p in grid.panels]


def domains(
    extent: Extent,
    groups: list[int],
    kind: AxisKind,
    *,
    band_size: int = 0,
    zero_base: bool = False,
) -> list[tuple[float, float]]:
    """Each panel's domain: the union of its group's extents, padded."""
    out: list[tuple[float, float]] = []
    cache: dict[int, tuple[float, float]] = {}
    groups_arr = np.asarray(groups)
    for g in groups:
        if g not in cache:
            cache[g] = _padded(extent, groups_arr == g, kind, band_size, zero_base)
        out.append(cache[g])
    return out


def _padded(
    extent: Extent, members: np.ndarray, kind: AxisKind, band_size: int, zero_base: bool
) -> tuple[float, float]:
    lo = np.nanmin(extent.lo[members]) if np.isfinite(extent.lo[members]).any() else np.nan
    hi = np.nanmax(extent.hi[members]) if np.isfinite(extent.hi[members]).any() else np.nan
    if kind == "band":
        if not np.isfinite(lo):
            return (-0.5, max(band_size, 1) - 0.5)
        return (float(np.floor(lo + 0.5)) - 0.5, float(np.ceil(hi - 0.5)) + 0.5)
    if not np.isfinite(lo):
        return (0.0, 1.0)
    if hi == lo:
        half = abs(lo) * 0.05 or (3_600_000.0 if kind == "time" else 0.5)
        return (float(lo - half), float(hi + half))
    span = hi - lo
    keep_lo = zero_base and lo == 0
    keep_hi = zero_base and hi == 0
    return (float(lo if keep_lo else lo - PAD * span), float(hi if keep_hi else hi + PAD * span))
