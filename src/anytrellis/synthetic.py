"""Made-up data for examples and tests: a dict of columns, deterministic for a seed."""

from __future__ import annotations

import numpy as np


def sensors(
    stations: int = 6, sensors: int = 3, hours: int = 24 * 14, seed: int = 0
) -> dict[str, np.ndarray]:
    """Hourly temperatures at weather stations, each with a few sensors: columns ``time``
    (datetime64), ``station``, ``region``, ``sensor``, ``temp`` and ``humidity``."""
    rng = np.random.default_rng(seed)
    start = np.datetime64("2026-03-01T00:00", "h")
    times = (start + np.arange(hours).astype("timedelta64[h]")).astype("datetime64[ms]")
    regions = ["north", "south", "coast"]
    names = ("time", "station", "region", "sensor", "temp", "humidity")
    cols: dict[str, list[np.ndarray]] = {k: [] for k in names}
    t = np.arange(hours) / 24.0  # days since the start (1 March)
    season = -np.cos(2 * np.pi * (t + 59 - 15) / 365.25)  # coldest mid-January
    kernel = np.hanning(49)
    kernel /= np.sqrt((kernel**2).sum())  # smoothed noise of unit variance: weather
    for s in range(stations):
        base = rng.uniform(4, 18)
        swing = rng.uniform(3, 9)
        winter = rng.uniform(4, 10)
        drift = rng.uniform(-4, 6) * t / max(t[-1], 1)  # over the whole period
        weather = 1.6 * np.convolve(rng.normal(0, 1, hours + 48), kernel, "valid")[:hours]
        for k in range(sensors):
            own = 0.5 * np.convolve(rng.normal(0, 1, hours + 48), kernel, "valid")[:hours]
            daily = swing * np.sin(2 * np.pi * (t - 0.3))
            temp = base + winter * season + drift + daily + weather + own + k * 0.6
            cols["time"].append(times)
            cols["station"].append(np.full(hours, f"station {s + 1}", dtype=object))
            cols["region"].append(np.full(hours, regions[s % len(regions)], dtype=object))
            cols["sensor"].append(np.full(hours, f"s{k + 1}", dtype=object))
            cols["temp"].append(temp)
            cols["humidity"].append(
                np.clip(70 - 2 * (temp - base) + rng.normal(0, 4, hours), 5, 100)
            )
    return {k: np.concatenate(v) for k, v in cols.items()}


def sales(seed: int = 0) -> dict[str, np.ndarray]:
    """Monthly sales per store and product: columns ``month`` (text, Jan..Dec), ``store``,
    ``product`` and ``units``."""
    rng = np.random.default_rng(seed)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    rows: dict[str, list] = {"month": [], "store": [], "product": [], "units": []}
    for store in ("Amsterdam", "Berlin", "Lisbon", "Oslo"):
        scale = rng.uniform(0.6, 1.6)
        for product in ("tea", "coffee", "cocoa"):
            level = rng.uniform(20, 80) * scale
            for i, month in enumerate(months):
                season = 1 + 0.35 * np.cos(2 * np.pi * i / 12) * (1 if product != "tea" else -1)
                rows["month"].append(month)
                rows["store"].append(store)
                rows["product"].append(product)
                rows["units"].append(round(level * season + rng.normal(0, 4), 1))
    return {k: np.array(v, dtype=object if k != "units" else float) for k, v in rows.items()}


def scatter(n: int = 200_000, groups: int = 9, seed: int = 0) -> dict[str, np.ndarray]:
    """Many points in a few clusters per group: columns ``group``, ``x``, ``y`` and
    ``cluster``."""
    rng = np.random.default_rng(seed)
    g = rng.integers(0, groups, n)
    c = rng.integers(0, 4, n)
    centers = rng.normal(0, 3, (groups, 4, 2))
    spread = rng.uniform(0.3, 1.2, (groups, 4))
    xy = centers[g, c] + rng.normal(0, 1, (n, 2)) * spread[g, c, None]
    return {
        "group": np.array([f"g{v + 1}" for v in g], dtype=object),
        "x": xy[:, 0],
        "y": xy[:, 1],
        "cluster": np.array([f"c{v + 1}" for v in c], dtype=object),
    }
