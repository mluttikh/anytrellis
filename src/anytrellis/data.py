"""Reading columns from tables: Polars, PyArrow, pandas, DuckDB, Ibis (via narwhals) or a
dict of arrays. Every column is read as one of three kinds: numbers, times or categories.

A lazy table (a Polars ``LazyFrame``, a DuckDB relation, an Ibis table) is read once, with
only the columns the plot uses, when the first of them is needed; a column needed later
reads them all again, with it. Its rows must come back in the same order each time, as
they do from Polars, DuckDB and Ibis on DuckDB. Text columns are encoded by Arrow when
PyArrow is installed, rather than labelled row by row.

A plot that reads a lazy table a page at a time (``load="pages"``) reads some of its rows
into a table of their own, whose ``whole`` is the lazy table: its category columns have the
whole table's levels, so axes and colours stay the same from page to page."""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
        frame = _frame(data)
        self._cache: dict[str, Column] = {}
        self._lazy: Any = None
        """A lazy table's query (narwhals ``LazyFrame``), or None: the rows are in memory."""
        self._wanted: dict[str, None] = {}
        """A lazy table's columns to read, in the order asked for."""
        self._read_names: set[str] = set()
        """The columns of the lazy table read into ``_frame``."""
        self._n: int | None = None
        self.whole: Table | None = None
        """The lazy table these rows were read from (``load="pages"``), or None."""
        self._memo: dict[Any, Any] = {}
        import narwhals as nw

        if isinstance(frame, nw.LazyFrame):
            self._lazy = frame
            self._schema = dict(frame.collect_schema())
            self._frame: Any = None
            self.names = list(self._schema)
        else:
            self._frame = frame
            self.names = _column_names(frame)
            self._n = _row_count(frame, self.names)

    @property
    def n(self) -> int:
        """The number of rows."""
        if self._n is None:
            if self._wanted:
                self._load()
            else:  # nothing to read yet: count them
                import narwhals as nw

                counted = self._lazy.select(nw.len().alias("n")).collect()
                self._n = int(counted["n"][0])
        assert self._n is not None
        return self._n

    @property
    def lazy(self) -> Any:
        """The query of a lazy table (a narwhals ``LazyFrame``), or None."""
        return self._lazy

    def __contains__(self, name: object) -> bool:
        return name in self.names

    def want(self, *names: str | None) -> None:
        """Columns to read with the others, in one query, when a lazy table is first read
        (names not in the table are ignored)."""
        if self._lazy is None:
            return
        for name in names:
            if name is not None and name in self.names:
                self._wanted[name] = None

    def check(self, name: str) -> None:
        """Raise ``NotFoundError`` for a column the table doesn't have; a lazy table's
        column is read later, with the others."""
        if name not in self.names:
            raise NotFoundError(f"column {name!r} not found; available: {self.names}")
        if self._lazy is None:
            self.column(name)
        else:
            self.want(name)

    def dtype(self, name: str) -> Any:
        """A lazy table's column type (a narwhals dtype), from its schema."""
        return self._schema[name]

    def kind(self, name: str) -> Kind:
        """A column's kind, from a lazy table's schema without reading it."""
        if self._lazy is None or name in self._cache:
            return self.column(name).kind
        if name not in self.names:
            raise NotFoundError(f"column {name!r} not found; available: {self.names}")
        return _kind_of(self._schema[name])

    def column(self, name: str) -> Column:
        if name not in self._cache:
            if name not in self.names:
                raise NotFoundError(f"column {name!r} not found; available: {self.names}")
            if self._lazy is not None and name not in self._read_names:
                self._wanted[name] = None
                self._load()
            column = _read(self._frame, name)
            if self.whole is not None and column.kind == "category":
                column = _recoded(column, self.whole.levels(name))
            self._cache[name] = column
        return self._cache[name]

    def memo(self, key: Any, compute: Callable[[], Any]) -> Any:
        """A lazy table's answer to a query, computed once (its rows are taken not to
        change while it is plotted)."""
        if key not in self._memo:
            self._memo[key] = compute()
        return self._memo[key]

    def levels(self, name: str) -> tuple[str, ...]:
        """A category column's levels: of all its rows (a lazy table: from a query for its
        distinct values; not read)."""
        if self._lazy is None:
            return self.column(name).levels
        from anytrellis.query import distinct

        return self.memo(("levels", name), lambda: distinct(self, [name]).column(name).levels)

    def span(self, name: str) -> tuple[float, float] | None:
        """The finite range of a number or time column over the whole table these rows
        were read from (None: these rows are the whole table, or it has no such values)."""
        if self.whole is None:
            return None
        from anytrellis.query import span

        whole = self.whole
        return whole.memo(("span", name), lambda: span(whole, name))

    def values(self, name: str) -> list[Any]:
        """A column's values as Python objects (rows in memory)."""
        if isinstance(self._frame, Mapping):
            return np.asarray(self._frame[name]).ravel().tolist()
        if self._lazy is not None and name not in self._read_names:
            self.column(name)
        return self._frame[name].to_list()

    def _load(self) -> None:
        """Read a lazy table's wanted columns, all in one query (again, when one was added
        since: the columns read before are dropped, so all come from the same rows)."""
        names = list(self._wanted)
        self._frame = self._lazy.select(names).collect()
        self._read_names = set(names)
        self._cache = {}
        self._n = len(self._frame)

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
        """These rows (indices), as the same kind of table as the data given (a lazy
        table's: every column, as the table it collects to)."""
        if isinstance(self._frame, Mapping):
            return {k: np.asarray(v)[rows] for k, v in self._frame.items()}
        import narwhals as nw

        if self._lazy is not None:
            return nw.to_native(self._lazy.collect()[rows])
        return nw.to_native(self._frame[rows])

    def raw(self, name: str) -> np.ndarray:
        """A column's values as they are (for tooltips)."""
        if isinstance(self._frame, Mapping):
            return np.asarray(self._frame[name]).ravel()
        if self._lazy is not None and name not in self._read_names:
            self.column(name)
        return self._frame[name].to_numpy()


def _frame(data: Any) -> Any:
    """The rows in memory (a narwhals ``DataFrame``, or a dict of arrays), or a lazy
    table's query (a narwhals ``LazyFrame``), not yet read."""
    if isinstance(data, Mapping):
        return data
    import narwhals as nw

    try:
        return nw.from_native(data)
    except TypeError:
        raise TypeError(
            f"unsupported data of type {type(data).__name__}; pass a Polars, PyArrow, pandas, "
            "DuckDB or Ibis table, or a dict of arrays"
        ) from None


def _kind_of(dtype: Any) -> Kind:
    """The kind a column of this narwhals dtype is read as."""
    import narwhals as nw

    if isinstance(dtype, nw.Datetime | nw.Date):
        return "time"
    if dtype.is_numeric() or dtype == nw.Boolean:
        return "number"
    return "category"


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
    elif dtype == nw.String:
        encoded = _arrow_codes(series)
        if encoded is not None:
            return _coded(name, *encoded, None)
    return _categories(name, series.to_numpy(), levels)


def _arrow_codes(series: Any) -> tuple[np.ndarray, np.ndarray] | None:
    """A text column's distinct labels and each row's index among them, encoded by Arrow
    (tens of times faster than labelling the rows in Python); None without PyArrow."""
    try:
        import pyarrow as pa
    except ImportError:
        return None
    try:
        arr = series.to_arrow()
    except (ImportError, ModuleNotFoundError, NotImplementedError):
        return None
    if isinstance(arr, pa.ChunkedArray):
        arr = arr.combine_chunks()
    encoded = arr.dictionary_encode()
    labels = [_label(v) for v in encoded.dictionary.to_pylist()]
    missing = len(labels)
    labels.append(MISSING_LABEL)  # the code of rows without a value
    codes = encoded.indices.fill_null(missing).to_numpy(zero_copy_only=False)
    return np.array(labels, dtype=object), codes.astype(np.int64)


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
    return _coded(name, *_labels(values), levels)


def _coded(name: str, distinct: np.ndarray, codes: np.ndarray,
           levels: list[str] | None) -> Column:  # fmt: skip
    """A category column from its distinct labels (each once) and each row's index among
    them; ``levels``: a declared order (else natural, the missing label last)."""
    present_codes = np.flatnonzero(np.bincount(codes, minlength=len(distinct))) \
        if len(codes) else np.zeros(0, dtype=np.int64)  # fmt: skip
    seen = set(distinct[present_codes])
    if levels is None:
        present = sorted((t for t in seen if t != MISSING_LABEL), key=_natural)
    else:
        present = [lv for lv in levels if lv in seen]
    if MISSING_LABEL in seen:
        present.append(MISSING_LABEL)
    position = {lv: i for i, lv in enumerate(present)}
    level_of = np.array([position.get(t, -1) for t in distinct], dtype=np.int64)
    return Column(name, "category", distinct[codes], tuple(present), level_of[codes])


def _recoded(column: Column, levels: tuple[str, ...]) -> Column:
    """A category column with the given levels (a superset of its own), in their order."""
    if levels == column.levels:
        return column
    position = {lv: i for i, lv in enumerate(levels)}
    level_of = np.array([position.get(lv, -1) for lv in column.levels] + [-1], dtype=np.int64)
    codes = level_of[column.level_codes()]
    return Column(column.name, "category", column.values, levels, codes)


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
    by ``within`` when given. Codes sort by radix, 16 bits at a time (one pass for under
    2¹⁶ groups, two for under 2³²): tens of times faster than sorting int64 codes, or a
    lexsort of codes and values."""
    order = np.argsort(within) if within is not None else None
    if n > 1 << 32:  # too many groups for two passes
        c = codes if order is None else codes[order]
        step = np.argsort(c, kind="stable")
        return step if order is None else order[step]
    for shift in (0,) if n <= 1 << 16 else (0, 16):  # low bits first; each pass is stable
        c = codes if order is None else codes[order]
        step = np.argsort(((c >> shift) & 0xFFFF).astype(np.uint16), kind="stable")
        order = step if order is None else order[step]
    assert order is not None
    return order


def _natural(text: str) -> tuple[Any, ...]:
    """Sort key: numbers in text by value ("site 2" before "site 10")."""
    import re

    return tuple(int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", text))
