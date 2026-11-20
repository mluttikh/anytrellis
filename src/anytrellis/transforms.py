"""Axis scales that transform numbers: log, sqrt and symlog.

A transformed axis draws its numbers in transformed units (axis units): the layers' values,
the bins of a histogram and a density's grid are on it, and zooming, panning and brushing
are even in it. Ticks, selections, limits and rules convert between the units and the
data's own values with ``forward`` and ``inverse``; a database computes ``expr`` itself.

    log      log10(v), for v > 0 (others are not drawn)
    sqrt     √v, for v ≥ 0
    symlog   sign(v)·log10(1 + |v|): log-like away from zero, linear near it, any v

The browser converts back for its labels (ticks.ts: ``untransform``).
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

Scale = Literal["linear", "log", "sqrt", "symlog"]
SCALES: tuple[str, ...] = ("linear", "log", "sqrt", "symlog")
TRANSFORMS: tuple[str, ...] = ("log", "sqrt", "symlog")
"""The scales that transform values (an axis kind of the same name)."""

DOMAIN = {"log": "above 0", "sqrt": "0 or above", "symlog": "any number"}


def forward(scale: str, values: Any) -> np.ndarray:
    """Values in axis units (NaN: not on the scale, as 0 on a log axis)."""
    v = np.asarray(values, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        if scale == "log":
            return np.where(v > 0, np.log10(v), np.nan)
        if scale == "sqrt":
            return np.where(v >= 0, np.sqrt(v), np.nan)
        if scale == "symlog":
            return np.sign(v) * np.log10(1 + np.abs(v))
    return v


def inverse(scale: str, values: Any) -> Any:
    """Axis units as the data's own values (a float for a float). Every scale increases, so
    a range's ends stay in order; sqrt mirrors below 0 (a padded axis' end)."""
    v = np.asarray(values, dtype=np.float64)
    if scale == "log":
        out = 10.0**v
    elif scale == "sqrt":
        out = np.sign(v) * v * v
    elif scale == "symlog":
        out = np.sign(v) * (10.0 ** np.abs(v) - 1)
    else:
        out = v
    return float(out) if np.ndim(out) == 0 else out


def on_scale(scale: str, values: Any) -> np.ndarray:
    """Which values the scale has a place for."""
    v = np.asarray(values, dtype=np.float64)
    if scale == "log":
        return v > 0
    if scale == "sqrt":
        return v >= 0
    return np.isfinite(v)


def scalar(scale: str, value: Any, what: str = "") -> float:
    """One value (a limit, a rule's position) in axis units; one off the scale raises."""
    v = float(value)
    if not bool(on_scale(scale, v)):
        where = f" {what}" if what else ""
        raise ValueError(f"{value!r} is not on a {scale}{where} axis (it holds values "
                         f"{DOMAIN[scale]})")  # fmt: skip
    return float(forward(scale, v))


def expr(scale: str, value: Any) -> Any:
    """A narwhals expression of numbers in axis units (a database computes it)."""
    import narwhals as nw

    if scale == "log":
        return value.log(10)
    if scale == "sqrt":
        return value.sqrt()
    if scale == "symlog":
        size = (value.abs() + 1).log(10)
        return nw.when(value < 0).then(-size).otherwise(size)
    return value


def on_scale_expr(scale: str, value: Any) -> Any:
    """A narwhals condition: the rows the scale has a place for (with a finite value)."""
    if scale == "log":
        return value > 0
    if scale == "sqrt":
        return value >= 0
    return None
