"""Reading columns from tables: Polars, PyArrow, pandas, DuckDB (via narwhals) or a dict of
arrays. Every column is read as one of three kinds: numbers, times or categories."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

Kind = Literal["number", "time", "category"]

MISSING_LABEL = "(missing)"
"""The category of rows without a value."""


class NotFoundError(KeyError):
    """A missing column: a ``KeyError`` whose message reads as written."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""


@dataclass(frozen=True)
class Column:
    """A column read for plotting.

    ``values`` are float64 for numbers (NaN where missing), float64 milliseconds since
    1970 for times (wall-clock time in the column's zone; NaN where missing), and str for
    categories (``MISSING_LABEL`` where missing). ``levels`` is the order of a category
    column: declared (a Polars Enum, a pandas Categorical) or sorted.
    """

    name: str
    kind: Kind
    values: np.ndarray
    levels: tuple[str, ...] = ()
    codes: np.ndarray | None = None
    """A category column's index of each row's value in ``levels`` (computed if not given)."""
    log: bool = False
    """Numbers in log10 units, for a log axis (the data's own values: ``10 ** values``)."""

    def level_codes(self) -> np.ndarray:
        """Each row's index in ``levels`` (−1: not one of them)."""
        if self.codes is not None:
            return self.codes
        distinct, codes = _labels(self.values)
        position = {lv: i for i, lv in enumerate(self.levels)}
        level_of = np.array([position.get(t, -1) for t in distinct], dtype=np.int64)
        out = level_of[codes] if len(codes) else codes
        object.__setattr__(self, "codes", out)
        return out

    def __len__(self) -> int:
        return len(self.values)


class Table:
    """A table whose columns are read once each."""

    def __init__(self, data: Any) -> None:
        if isinstance(data, Table):
            data = data.native
        self.native = data
        self._frame = _frame(data)
        self._cache: dict[str, Column] = {}
        self.names = _column_names(self._frame)
        self.n = _row_count(self._frame, self.names)

    def __contains__(self, name: object) -> bool:
        return name in self.names

    def column(self, name: str) -> Column:
        if name not in self._cache:
            if name not in self.names:
                raise NotFoundError(f"column {name!r} not found; available: {self.names}")
            self._cache[name] = _read(self._frame, name)
        return self._cache[name]

    def log_scaled(self, names: set[str]) -> Table:
        """This table with the columns ``names`` in log10 units, for a log axis: values of 0
        or less are missing. Raw values (tooltips) and rows (``take``) are as they were."""
        import copy

        out = copy.copy(self)
        out._cache = dict(self._cache)
        for name in sorted(names):
            col = self.column(name)
            if col.kind != "number":
                raise ValueError(f"a log scale needs numbers; {name!r} holds {col.kind}s")
            with np.errstate(divide="ignore", invalid="ignore"):
                values = np.where(col.values > 0, np.log10(col.values), np.nan)
            out._cache[name] = Column(name, "number", values, log=True)
        return out

    def take(self, rows: np.ndarray) -> Any:
        """These rows (indices), as the same kind of table as the data given."""
        if isinstance(self._frame, Mapping):
            return {k: np.asarray(v)[rows] for k, v in self._frame.items()}
        import narwhals as nw

        return nw.to_native(self._frame[rows])

    def raw(self, name: str) -> np.ndarray:
        """A column's values as they are (for tooltips)."""
        if isinstance(self._frame, Mapping):
            return np.asarray(self._frame[name]).ravel()
        return self._frame[name].to_numpy()


def _frame(data: Any) -> Any:
    if isinstance(data, Mapping):
        return data
    import narwhals as nw

    try:
        out = nw.from_native(data)
    except TypeError:
        raise TypeError(
            f"unsupported data of type {type(data).__name__}; pass a Polars, PyArrow, pandas "
            "or DuckDB table, or a dict of arrays"
        ) from None
    if isinstance(out, nw.LazyFrame):
        out = out.collect()
    return out


def _column_names(frame: Any) -> list[str]:
    if isinstance(frame, Mapping):
        return [str(k) for k in frame]
    return list(frame.columns)


def _row_count(frame: Any, names: list[str]) -> int:
    if isinstance(frame, Mapping):
        lengths = {len(np.asarray(frame[n]).ravel()) for n in names}
        if len(lengths) > 1:
            raise ValueError(f"the columns have different lengths: {sorted(lengths)}")
        return lengths.pop() if lengths else 0
    return len(frame)


def _read(frame: Any, name: str) -> Column:
    if isinstance(frame, Mapping):
        return _from_array(name, frame[name])
    import narwhals as nw

    series = frame[name]
    dtype = series.dtype
    if isinstance(dtype, nw.Datetime):
        if dtype.time_zone is not None:
            series = series.dt.replace_time_zone(None)  # wall-clock time in its zone
        ms = series.dt.timestamp("ms").cast(nw.Float64)
        missing = series.is_null().to_numpy()
        values = np.array(ms.to_numpy(), dtype=np.float64)  # a copy: it may be read-only
        values[np.asarray(missing, dtype=bool)] = np.nan
        return Column(name, "time", values)
    if isinstance(dtype, nw.Date):
        return _read(frame.with_columns(nw.col(name).cast(nw.Datetime("ms"))), name)
    if dtype.is_numeric() or dtype == nw.Boolean:
        values = series.cast(nw.Float64).to_numpy()
        return Column(name, "number", np.asarray(values, dtype=np.float64))
    levels: list[str] | None = None
    if isinstance(dtype, nw.Enum):
        levels = [str(c) for c in dtype.categories]
    elif dtype == nw.Categorical:
        native = nw.to_native(frame)
        if hasattr(native, "iloc"):  # pandas keeps its declared order
            levels = [str(c) for c in native[name].cat.categories]
    return _categories(name, series.to_numpy(), levels)


def _from_array(name: str, values: Any) -> Column:
    cat = getattr(values, "cat", None)
    declared = getattr(cat, "categories", None) if cat is not None else None
    if declared is None and hasattr(values, "categories") and hasattr(values, "codes"):
        declared = values.categories
    arr = np.asarray(values).ravel()
    if declared is not None:
        return _categories(name, arr, [str(c) for c in declared])
    if arr.dtype.kind == "M":
        ms = arr.astype("datetime64[ms]")
        out = ms.astype(np.int64).astype(np.float64)
        out[np.isnat(ms)] = np.nan
        return Column(name, "time", out)
    if arr.dtype.kind in "biuf":
        return Column(name, "number", arr.astype(np.float64))
    if arr.dtype.kind == "O":
        present = [v for v in arr if v is not None]
        import datetime as dt

        if present and all(isinstance(v, dt.datetime | dt.date) for v in present):
            return _from_array(name, np.array(arr, dtype="datetime64[ms]"))
        if present and all(isinstance(v, int | float | np.number) for v in present):
            return Column(name, "number", np.array(arr, dtype=np.float64))
    return _categories(name, arr, None)


def _categories(name: str, values: np.ndarray, levels: list[str] | None) -> Column:
    distinct, codes = _labels(values)
    seen = set(distinct[np.unique(codes)]) if len(codes) else set()
    if levels is None:
        present = sorted((t for t in seen if t != MISSING_LABEL), key=_natural)
    else:
        present = [lv for lv in levels if lv in seen]
    if MISSING_LABEL in seen:
        present.append(MISSING_LABEL)
    position = {lv: i for i, lv in enumerate(present)}
    level_of = np.array([position.get(t, -1) for t in distinct], dtype=np.int64)
    return Column(name, "category", distinct[codes], tuple(present), level_of[codes])


def _labels(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The distinct labels, and each value's index among them; each distinct value is
    labelled once, so a million rows of a few categories cost a lookup each."""
    arr = np.asarray(values).ravel()
    try:
        if arr.dtype.kind in "US":
            uniq, inverse = np.unique(arr, return_inverse=True)
            codes = inverse.ravel().astype(np.int64)
        else:
            index: dict[Any, int] = {}
            codes = np.fromiter((index.setdefault(v, len(index)) for v in arr),
                                dtype=np.int64, count=arr.size)  # fmt: skip
            uniq = list(index)
    except TypeError:  # unhashable values: one by one
        uniq, codes = [_label(v) for v in arr], np.arange(arr.size, dtype=np.int64)
    labels = [_label(u) for u in uniq]
    # values with one label (1 and "1", or NaN objects): one index
    first: dict[str, int] = {}
    remap = np.array([first.setdefault(t, len(first)) for t in labels], dtype=np.int64)
    distinct = np.array(list(first) or [""], dtype=object)
    return distinct, remap[codes] if len(remap) else codes


def _label(value: Any) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return MISSING_LABEL
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.generic):
        value = value.item()
    return str(value)


def group_order(codes: np.ndarray, n: int, within: np.ndarray | None = None) -> np.ndarray:
    """The order of rows grouped by their code (0 … n−1), in row order within a group, or
    by ``within`` when given. Codes of under 2¹⁶ groups sort by radix: tens of times faster
    than sorting int64 codes, or a lexsort of codes and values."""
    small = codes.astype(np.uint16) if n <= 1 << 16 else codes
    if within is None:
        return np.argsort(small, kind="stable")
    first = np.argsort(within)
    return first[np.argsort(small[first], kind="stable")]


def _natural(text: str) -> tuple[Any, ...]:
    """Sort key: numbers in text by value ("site 2" before "site 10")."""
    import re

    return tuple(int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", text))
