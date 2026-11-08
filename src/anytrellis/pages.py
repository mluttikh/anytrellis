"""Pages of panels: a wrap of many panels shown a page at a time, which the reader sorts and
filters by statistics of each panel (Tukey's cognostics, as Trelliscope uses them).

The statistics are computed here, one value per panel: the rows in each panel and the mean,
median, extremes, spread and trend of the values the plot draws, and any columns given with
``Trellis.panel_stats``. The browser sorts, filters and pages; ``order`` does the same here,
for ``shown_panels()`` and the images drawn in Python, and must stay in step with
``panelOrder`` in js/src/core/pages.ts.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

import numpy as np

from anytrellis.data import Table, group_order

AUTO_PANELS = 100
"""A wrap of more panels than this pages by itself."""
PAGE_COLS = 6
PAGE_ROWS = 4


class Paging(TypedDict, total=False):
    """What the reader sees: a page (from 0), the panels sorted by a statistic (None: as
    given), and filtered by name and by ranges (numbers) or text (text) of statistics."""

    page: int
    sort: str | None
    descending: bool
    name: str
    where: dict[str, Any]


@dataclass(frozen=True)
class Stat:
    name: str
    kind: Literal["number", "text"]
    values: list[Any]
    """A float per panel (NaN: none) for numbers, a str ("": none) for text."""
    text: list[str]
    """Each value as shown (on the strips, while sorted by it)."""

    def spec(self) -> dict[str, Any]:
        values = [None if isinstance(v, float) and v != v else v for v in self.values]
        return {"name": self.name, "kind": self.kind, "values": values, "text": self.text}


def builtin_stats(npanels: int, panel_of: np.ndarray, values: np.ndarray, name: str,
                  x: np.ndarray | None) -> list[Stat]:  # fmt: skip
    """The rows in each panel, and its values' mean, median, min, max, standard deviation
    and trend (the change of their least-squares line over the panel's x, when x is given).
    ``panel_of``: each row's panel (−1: none); NaN values are left out of the statistics."""
    keep = panel_of >= 0
    rows = np.bincount(panel_of[keep], minlength=npanels).astype(np.float64)
    ok = keep & np.isfinite(values)
    if x is not None:
        ok &= np.isfinite(x)
    p, v = panel_of[ok], values[ok]
    order = group_order(p, npanels, within=v)
    p, v = p[order], v[order]
    xs = x[ok][order] if x is not None else None
    counts = np.bincount(p, minlength=npanels)
    starts = np.r_[0, np.cumsum(counts)]
    out = {k: np.full(npanels, np.nan) for k in ("mean", "median", "min", "max", "sd", "trend")}
    for i in np.flatnonzero(counts):
        s = v[starts[i] : starts[i + 1]]
        out["mean"][i] = s.mean()
        out["median"][i] = np.median(s)
        out["min"][i], out["max"][i] = s[0], s[-1]
        if len(s) > 1:
            out["sd"][i] = s.std(ddof=1)
        if xs is not None:
            t = xs[starts[i] : starts[i + 1]]
            span = t.max() - t.min()
            if span > 0:
                dt = t - t.mean()
                slope = float((dt * (s - s.mean())).sum() / (dt * dt).sum())
                out["trend"][i] = slope * span
    if x is None:
        del out["trend"]
    return _stat_list(rows, out, name)


def queried_stats(npanels: int, assign: Callable[[Table], np.ndarray | None],
                  found: tuple[Table, Table], name: str,
                  trend: np.ndarray | None) -> list[Stat]:  # fmt: skip
    """The statistics of ``builtin_stats`` from a lazy table's grouped queries
    (``query.panel_summaries``): a row per combination of the facet columns, each placed
    in its panel by ``assign``; the trend, computed from the rows, as given."""
    from anytrellis.query import SUMMARIES

    counts, summaries = found
    rows = np.zeros(npanels)
    at = assign(counts)
    assert at is not None  # the counts have the facet columns
    ok = at >= 0
    np.add.at(rows, at[ok], counts.column("rows").values[ok])
    out = {k: np.full(npanels, np.nan) for k in SUMMARIES}
    at = assign(summaries)
    assert at is not None
    ok = at >= 0
    for key in SUMMARIES:
        out[key][at[ok]] = summaries.column(key).values[ok]
    if trend is not None:
        out["trend"] = trend
    return _stat_list(rows, out, name)


def trends(npanels: int, panel_of: np.ndarray, values: np.ndarray,
           x: np.ndarray) -> np.ndarray:  # fmt: skip
    """Each panel's trend, as in ``builtin_stats`` (the change of the least-squares line of
    its finite values over its x), in one pass over the rows, without sorting them."""
    ok = (panel_of >= 0) & np.isfinite(values) & np.isfinite(x)
    p, v, t = panel_of[ok], values[ok], x[ok]
    n = np.bincount(p, minlength=npanels).astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        dt = t - (np.bincount(p, t, npanels) / n)[p]  # centred in each panel: exact sums
        dv = v - (np.bincount(p, v, npanels) / n)[p]
        sxy = np.bincount(p, dt * dv, npanels)
        sxx = np.bincount(p, dt * dt, npanels)
        lo = np.full(npanels, np.inf)
        hi = np.full(npanels, -np.inf)
        np.minimum.at(lo, p, t)
        np.maximum.at(hi, p, t)
        span = hi - lo
        return np.where((n > 0) & (span > 0), sxy / sxx * span, np.nan)


def _stat_list(rows: np.ndarray, out: dict[str, np.ndarray], name: str) -> list[Stat]:
    stats = [Stat("rows", "number", rows.tolist(), [str(int(r)) for r in rows])]
    for key in ("mean", "median", "min", "max", "sd", "trend"):
        if key not in out:
            continue
        vals = out[key].tolist()
        stats.append(Stat(f"{key} {name}", "number", vals, [short(v) for v in vals]))
    return stats


def given_stats(table: Table, panel_of: np.ndarray, npanels: int,
                keys: Sequence[str]) -> list[Stat]:  # fmt: skip
    """The columns of a table with one row per panel (found by its facet columns), but
    those, as statistics: numbers as numbers, the rest as text."""
    from anytrellis.plot import _text

    found = panel_of[panel_of >= 0]
    if len(np.unique(found)) < len(found):
        raise ValueError("panel_stats(): give one row per panel; some panels have several")
    rows = np.full(npanels, -1)
    rows[panel_of[panel_of >= 0]] = np.flatnonzero(panel_of >= 0)
    has = rows >= 0
    stats = []
    for name in table.names:
        if name in keys:
            continue
        col = table.column(name)
        if col.kind == "number":
            vals = np.full(npanels, np.nan)
            vals[has] = col.values[rows[has]]
            stats.append(Stat(name, "number", vals.tolist(), [short(v) for v in vals.tolist()]))
        else:
            raw = table.raw(name)
            text = ["" if not h else _text(raw[r]) for h, r in zip(has, rows, strict=True)]
            stats.append(Stat(name, "text", text, text))
    return stats


def short(v: float) -> str:
    """A statistic as a strip shows it: 4 significant digits, whole numbers in full."""
    if v != v:
        return ""
    if v == int(v) or abs(v) >= 1000:
        return f"{v:.0f}"
    return f"{v:.4g}"


def order(stats: Sequence[Stat], names: Sequence[str], paging: Paging) -> list[int]:
    """The panels shown, in order: those the filters keep, sorted (stably; missing values
    last either way)."""
    by = {s.name: s for s in stats}
    terms = paging.get("name", "").lower().split()
    keep = [i for i, n in enumerate(names) if all(t in n.lower() for t in terms)]
    for stat_name, cond in (paging.get("where") or {}).items():
        s = by.get(stat_name)
        if s is None:
            continue
        if s.kind == "text":
            want = str(cond or "").lower()
            keep = [i for i in keep if want in s.values[i].lower()]
            continue
        lo, hi = [*cond, None, None][:2] if isinstance(cond, list | tuple) else (None, None)
        if lo is not None or hi is not None:
            keep = [i for i in keep if _within(s.values[i], lo, hi)]
    s = by.get(paging.get("sort") or "")
    if s is None:
        return keep
    desc = bool(paging.get("descending"))

    def missing(i: int) -> bool:
        v = s.values[i]
        return v == "" if s.kind == "text" else v != v

    present = [i for i in keep if not missing(i)]
    present.sort(key=lambda i: s.values[i], reverse=desc)  # stable: ties as given, either way
    return present + [i for i in keep if missing(i)]


def _within(v: float, lo: float | None, hi: float | None) -> bool:
    if v != v:
        return False
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def page_count(shown: int, per_page: int) -> int:
    return max(1, -(-shown // per_page))


def page_list(shown: Sequence[int], per: int, groups: Sequence[int] | None) -> list[list[int]]:
    """The pages: the panels shown (in order) ``per`` a page; with page columns (``groups``:
    each panel's page level), each level's panels on pages of their own, the levels in
    order (one the filters leave empty: none). At least one page, maybe empty. In step with
    ``pageList`` in js/src/core/pages.ts."""
    per = max(1, per)
    out: list[list[int]] = []
    if groups is None:
        members = [list(shown)]
    else:
        by: dict[int, list[int]] = {}
        for i in shown:
            by.setdefault(int(groups[i]), []).append(i)
        members = [by[g] for g in sorted(by)]
    for m in members:
        out += [m[k : k + per] for k in range(0, len(m), per)]
    return out or [[]]


def page_labels(pages: list[list[int]], groups: Sequence[int] | None,
                levels: Sequence[str]) -> list[str]:  # fmt: skip
    """Each page's name: its page level ("2 of 3" after it, when the level has more
    pages); "" without page columns."""
    if groups is None:
        return ["" for _ in pages]
    first = [levels[int(groups[p[0]])] if p else "" for p in pages]
    out = []
    for k, name in enumerate(first):
        same = [j for j, other in enumerate(first) if other == name]
        out.append(name if len(same) == 1 else f"{name} ({same.index(k) + 1} of {len(same)})")
    return out
