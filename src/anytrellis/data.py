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
    text = np.array([_label(v) for v in values], dtype=object)
    if levels is None:
        present = sorted({t for t in text if t != MISSING_LABEL}, key=_natural)
    else:
        seen = set(text)
        present = [lv for lv in levels if lv in seen]
    if MISSING_LABEL in set(text):
        present.append(MISSING_LABEL)
    return Column(name, "category", text, tuple(present))


def _label(value: Any) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return MISSING_LABEL
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.generic):
        value = value.item()
    return str(value)


def _natural(text: str) -> tuple[Any, ...]:
    """Sort key: numbers in text by value ("site 2" before "site 10")."""
    import re

    return tuple(int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", text))
