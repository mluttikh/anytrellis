"""Facets: which panel each row goes to, and where the panels sit.

A trellis is a grid (``row=`` and/or ``col=``: every combination of their levels gets a
cell, empty or not, so rows and columns read as aligned categories) or a wrap (``wrap=``:
the combinations present, wrapped into ``cols`` columns). Several columns may be given to
each; their combinations are the levels, in the order of the first column, then the next.

Page columns (``page=``) split either into pages, one per level: a grid's every cell on each
page (the same rows and columns on all), a wrap's combinations present on each page.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import numpy as np

from anytrellis.data import MISSING_LABEL, Column, Table, group_order

Summary = Literal["median", "mean", "min", "max", "sum", "count"]


@dataclass(frozen=True)
class Order:
    """How a facet column's levels are ordered: given levels, or by a summary of a column."""

    levels: tuple[str, ...] | None = None
    by: Summary | None = None
    of: str | None = None
    descending: bool = False


@dataclass(frozen=True)
class Panel:
    index: int
    row: int
    col: int
    label: str
    """The strip of a wrap ("" in a grid, whose strips are its rows' and columns' labels)."""
    keys: tuple[str, ...] = ()
    """The panel's level of each facet column, in the order page, row, col (or wrap)
    columns."""


@dataclass
class Grid:
    kind: Literal["single", "grid", "wrap"]
    rows: int
    cols: int
    panels: list[Panel]
    row_labels: list[str] = field(default_factory=list)
    col_labels: list[str] = field(default_factory=list)
    row_keys: list[tuple[str, ...]] = field(default_factory=list)
    """A grid's rows: each one's level of each row column (nested strips)."""
    col_keys: list[tuple[str, ...]] = field(default_factory=list)
    """A grid's columns: each one's level of each col column."""
    strip_from: int = 0
    """A wrap's strips: the panels' keys from this one on (those before: the page's)."""
    row_title: str = ""
    col_title: str = ""
    columns: tuple[str, ...] = ()
    """The facet columns (page columns first)."""
    pages: list[str] = field(default_factory=list)
    """The levels of the page columns, in order (none: no page columns)."""
    page_of: np.ndarray | None = None
    """Each panel's page level (an index in ``pages``), or None: no page columns."""
    _levels: dict[str, list[str]] = field(default_factory=dict)
    _row_combos: np.ndarray | None = None
    _col_combos: np.ndarray | None = None
    _row_vars: tuple[str, ...] = ()
    _col_vars: tuple[str, ...] = ()
    _wrap_vars: tuple[str, ...] = ()
    _page_vars: tuple[str, ...] = ()
    _page_combos: np.ndarray | None = None
    _kept: np.ndarray | None = None
    """A grid without its empty cells: each cell's panel (−1: dropped), by row * cols + col."""

    def assign(self, table: Table) -> np.ndarray | None:
        """The panel of each row of ``table`` (−1: a level not in the trellis), or None when
        ``table`` has none of the facet columns (its rows go to every panel)."""
        if self.kind == "single":
            return np.zeros(table.n, dtype=np.int64)
        present = [c for c in self.columns if c in table]
        if not present:
            return None
        if len(present) < len(self.columns):
            missing = [c for c in self.columns if c not in table]
            raise ValueError(
                f"a layer's data has some facet columns but not {missing}; give it all of "
                f"{list(self.columns)} or none (none: its rows are drawn in every panel)"
            )
        if self.kind == "wrap":
            return _combo_index(table, self._wrap_vars, self._levels, self._row_combos)
        r = _combo_index(table, self._row_vars, self._levels, self._row_combos)
        c = _combo_index(table, self._col_vars, self._levels, self._col_combos)
        g = _combo_index(table, self._page_vars, self._levels, self._page_combos)
        out = (g * self.rows + r) * self.cols + c
        out[(r < 0) | (c < 0) | (g < 0)] = -1
        if self._kept is not None:
            out = np.where(out >= 0, self._kept[np.maximum(out, 0)], -1)
        return out

    def spec(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "rows": self.rows,
            "cols": self.cols,
            "row_labels": self.row_labels,
            "col_labels": self.col_labels,
            "row_keys": [list(k) for k in self.row_keys],
            "col_keys": [list(k) for k in self.col_keys],
            "strip_from": self.strip_from,
            "row_title": self.row_title,
            "col_title": self.col_title,
        }


def build_grid(
    tables: Sequence[Table],
    *,
    row: tuple[str, ...],
    col: tuple[str, ...],
    wrap: tuple[str, ...],
    cols: int | None,
    orders: dict[str, Order],
    keep_empty: bool = True,
    page: tuple[str, ...] = (),
) -> Grid:
    """The grid of panels for the facet columns, from the tables that have them; with page
    columns, a grid or wrap per page level, their panels in turn."""
    if wrap and (row or col):
        raise ValueError("use wrap= alone, or row= and/or col= (a grid), not both")
    if page and not keep_empty:
        raise ValueError("page columns keep a grid's empty cells")
    columns = (*page, *row, *col, *wrap)
    if not columns:
        return Grid("single", 1, 1, [Panel(0, 0, 0, "")])
    sources = [t for t in tables if all(c in t for c in columns)]
    if not sources:
        raise ValueError(f"no data has the facet columns {list(columns)}")
    levels = {name: _levels([t.column(name) for t in sources], orders.get(name), sources)
              for name in columns}  # fmt: skip
    page_combos = _present(sources, page, levels) if page else None
    page_keys = [tuple(levels[v][k] for v, k in zip(page, c, strict=True))
                 for c in ([] if page_combos is None else page_combos)]  # fmt: skip
    page_labels = [" · ".join(keys) for keys in page_keys]
    if wrap or not (row or col):
        names = (*page, *wrap)
        combos = _present(sources, names, levels)
        n = len(combos)
        page_of = None
        if page_combos is not None:  # each combination's page level, by its page part
            dims = tuple(len(levels[v]) for v in page)
            flat = np.ravel_multi_index(tuple(combos[:, : len(page)].T), dims)
            known = np.ravel_multi_index(tuple(page_combos.T), dims)
            page_of = np.searchsorted(known, flat).astype(np.int64)
        most = n if page_of is None else int(np.bincount(page_of).max(initial=1))
        ncols = max(1, min(cols or math.ceil(math.sqrt(most)), most))
        nrows = max(1, math.ceil(most / ncols))
        panels = []
        at = 0
        for i, combo in enumerate(combos):
            keys = tuple(levels[v][k] for v, k in zip(names, combo, strict=True))
            if page_of is not None and i and page_of[i] != page_of[i - 1]:
                at = 0  # a page's first panel
            own = keys[len(page) :]  # the strip: the wrap's levels (the page's: above)
            label = " · ".join(own) if own else " · ".join(keys)
            panels.append(Panel(i, at // ncols, at % ncols, label, keys))
            at += 1
        return Grid("wrap", nrows, ncols, panels, columns=columns, pages=page_labels,
                    page_of=page_of, strip_from=len(page) if wrap else 0, _levels=levels,
                    _row_combos=combos, _wrap_vars=names)  # fmt: skip
    row_combos = _present(sources, row, levels) if row else np.zeros((1, 0), dtype=np.int64)
    col_combos = _present(sources, col, levels) if col else np.zeros((1, 0), dtype=np.int64)
    row_keys = [tuple(levels[v][k] for v, k in zip(row, c, strict=True)) for c in row_combos]
    col_keys = [tuple(levels[v][k] for v, k in zip(col, c, strict=True)) for c in col_combos]
    row_labels = [" · ".join(k) for k in row_keys]
    col_labels = [" · ".join(k) for k in col_keys]
    nrows, ncols = len(row_combos), len(col_combos)
    panels = []
    pages = page_keys or [()]
    for g, keys_of_page in enumerate(pages):
        for r in range(nrows):
            for c in range(ncols):
                keys = (
                    keys_of_page
                    + tuple(levels[v][k] for v, k in zip(row, row_combos[r], strict=True))
                    + tuple(levels[v][k] for v, k in zip(col, col_combos[c], strict=True))
                )
                panels.append(Panel((g * nrows + r) * ncols + c, r, c, "", keys))
    page_of = None if page_combos is None else \
        np.repeat(np.arange(len(pages), dtype=np.int64), nrows * ncols)  # fmt: skip
    grid = Grid(
        "grid", nrows, ncols, panels,
        row_labels=row_labels if row else [], col_labels=col_labels if col else [],
        row_keys=row_keys if row else [], col_keys=col_keys if col else [],
        row_title=" · ".join(row), col_title=" · ".join(col), columns=columns,
        pages=page_labels, page_of=page_of,
        _levels=levels, _row_combos=row_combos, _col_combos=col_combos,
        _row_vars=row, _col_vars=col, _page_vars=page,
        _page_combos=page_combos if page_combos is not None else np.zeros((1, 0), np.int64),
    )  # fmt: skip
    if not keep_empty:  # the cells with data, numbered in turn
        used = _used(grid, sources)
        kept = [p for p in grid.panels if p.index in used]
        grid._kept = np.full(nrows * ncols, -1, dtype=np.int64)
        grid._kept[[p.index for p in kept]] = np.arange(len(kept))
        grid.panels = [replace(p, index=i) for i, p in enumerate(kept)]
    return grid


def strip_texts(grid: Grid, tables: Sequence[Table], name: str) -> list[str | None]:
    """Each panel's value of column ``name``, its strip's text (None: the panel has no rows
    with a value). A panel with two values raises: a strip names one panel."""
    having = [t for t in tables if name in t and all(c in t for c in grid.columns)]
    if not having:
        raise ValueError(f"strip_label={name!r}: no data has this column and the facet "
                         f"columns {list(grid.columns)}")  # fmt: skip
    found: list[str | None] = [None] * len(grid.panels)
    for t in having:
        at = grid.assign(t)
        assert at is not None
        labels, codes = _codes(t.column(name))
        ok = (at >= 0) & (codes >= 0)
        pairs = np.unique(np.stack([at[ok], codes[ok]]), axis=1)
        for panel, code in pairs.T.tolist():
            text = labels[code]
            if text == MISSING_LABEL:
                continue
            if found[panel] is None:
                found[panel] = text
            elif found[panel] != text:
                keys = " · ".join(grid.panels[panel].keys)
                raise ValueError(f"strip_label={name!r}: panel {keys!r} has several values "
                                 f"({found[panel]!r}, {text!r}); give it one")  # fmt: skip
    return found


def _used(grid: Grid, tables: Sequence[Table]) -> set[int]:
    used: set[int] = set()
    for t in tables:
        p = grid.assign(t)
        if p is not None:
            used.update(int(v) for v in np.unique(p[p >= 0]))
    return used


def _format(v: float, kind: str) -> str:
    if v != v:
        return MISSING_LABEL
    if kind == "time":
        text = str(np.datetime64(int(v), "ms"))
        return text.removesuffix("T00:00:00.000").removesuffix(".000")
    if float(v).is_integer() and abs(v) < 1e15:
        return str(int(v))
    return f"{v:.12g}"


def _levels(columns: list[Column], order: Order | None, tables: Sequence[Table]) -> list[str]:
    """The ordered levels of a facet column across the tables that have it."""
    first = columns[0]
    if first.kind == "category":
        seen: dict[str, None] = {}
        for c in columns:
            seen.update(dict.fromkeys(c.levels))
        levels = list(seen)
    else:
        values = np.unique(np.concatenate([c.values for c in columns]))
        levels = list(dict.fromkeys(_format(v, first.kind) for v in values))
    if order is None:
        return levels
    if order.levels is not None:
        given = [str(v) for v in order.levels]
        unknown = [v for v in given if v not in levels]
        if unknown:
            raise ValueError(f"order: {unknown} are not levels of {first.name!r}: {levels}")
        return given + [v for v in levels if v not in given]
    if order.by is not None:
        stat = _summaries(first.name, levels, order, tables)
        ranked = sorted(range(len(levels)), key=lambda i: (np.isnan(stat[i]), stat[i]))
        if order.descending:
            ranked = [i for i in ranked if not np.isnan(stat[i])][::-1] + [
                i for i in ranked if np.isnan(stat[i])
            ]
        return [levels[i] for i in ranked]
    return levels[::-1] if order.descending else levels


def ordered_levels(name: str, order: Order, tables: Sequence[Table]) -> list[str]:
    """The levels of category column ``name`` in ``order`` (an axis or colour column)."""
    return _levels([t.column(name) for t in tables], order, tables)


def _summaries(name: str, levels: list[str], order: Order, tables: Sequence[Table]) -> np.ndarray:
    from anytrellis.query import level_summary

    table = tables[0] if tables[0].whole is None else tables[0].whole  # load="pages": all rows
    if order.by != "count":
        if order.of is None:
            raise ValueError(f"order(..., by={order.by!r}) needs of=<a number column>")
        if table.kind(order.of) == "category":
            raise ValueError(f"order: {order.of!r} is not a number or time column")
    found = level_summary(table, name, order.by or "count", order.of)
    if found is not None:  # a lazy table: each level's summary from the database
        out = np.full(len(levels), np.nan)
        level = _index(found, name, {name: levels})
        ok = level >= 0
        out[level[ok]] = found.column("v").values[ok]
        return out
    if order.by == "count":
        values = np.ones(table.n)
    else:
        assert order.of is not None
        values = table.column(order.of).values
    fn = {
        "median": np.median, "mean": np.mean, "min": np.min, "max": np.max,
        "sum": np.sum, "count": np.sum,
    }[order.by or "count"]  # fmt: skip
    level = _index(table, name, {name: levels})
    keep = (level >= 0) & ~np.isnan(values)
    level, values = level[keep], values[keep]
    rows = group_order(level, len(levels))
    starts = np.searchsorted(level[rows], np.arange(len(levels) + 1))
    out = np.full(len(levels), np.nan)
    for i in range(len(levels)):
        if starts[i] < starts[i + 1]:
            out[i] = fn(values[rows[starts[i] : starts[i + 1]]])
    return out


def _index(table: Table, name: str, levels: dict[str, list[str]]) -> np.ndarray:
    """Each row's level index in ``levels[name]`` (−1 when not a level)."""
    labels, codes = _codes(table.column(name))
    lookup = {v: i for i, v in enumerate(levels[name])}
    mapped = np.array([lookup.get(t, -1) for t in labels] + [-1], dtype=np.int64)
    return mapped[codes]  # a code of −1 picks the −1 at the end


def _codes(column: Column) -> tuple[list[str], np.ndarray]:
    """A column's distinct labels, and each row's index among them (−1: none of them).

    Each distinct value is labelled once, so rows are never turned into text one by one."""
    if column.kind == "category":
        return list(column.levels), column.level_codes()
    uniq, inverse = np.unique(column.values, return_inverse=True)  # NaNs: one, at the end
    return [_format(v, column.kind) for v in uniq], inverse.ravel()


def _present(
    tables: Sequence[Table], names: tuple[str, ...], levels: dict[str, list[str]]
) -> np.ndarray:
    """The combinations of levels in the data, as rows of level indices, in order."""
    found = []
    dims = tuple(len(levels[n]) for n in names)
    for t in tables:
        idx = [_index(t, n, levels) for n in names]
        ok = np.all([i >= 0 for i in idx], axis=0)
        flat = np.ravel_multi_index([i[ok] for i in idx], dims)
        found.append(np.unique(flat))
    flat = np.unique(np.concatenate(found))
    return np.stack(np.unravel_index(flat, dims), axis=1).astype(np.int64)


def _combo_index(
    table: Table, names: tuple[str, ...], levels: dict[str, list[str]], combos: np.ndarray | None
) -> np.ndarray:
    """Each row's combination index in ``combos`` (−1 when not one of them)."""
    if not names:
        return np.zeros(table.n, dtype=np.int64)
    assert combos is not None
    dims = tuple(len(levels[n]) for n in names)
    idx = [_index(table, n, levels) for n in names]
    ok = np.all([i >= 0 for i in idx], axis=0)
    flat = np.full(table.n, -1, dtype=np.int64)
    flat[ok] = np.ravel_multi_index([i[ok] for i in idx], dims)
    known = np.ravel_multi_index(tuple(combos.T), dims) if len(combos) else np.zeros(0, np.int64)
    pos = np.searchsorted(known, flat)
    pos = np.clip(pos, 0, max(0, len(known) - 1))
    hit = ok & (len(known) > 0)
    hit[hit] = known[pos[hit]] == flat[hit]
    return np.where(hit, pos, -1).astype(np.int64)
