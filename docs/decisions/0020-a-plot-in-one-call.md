# 0020: A plot in one call, and df.plot

- Status: **implemented**, 21 November 2026 (design review, Phase 3: a df.plot-style entry
  point).
- Changes: `src/anytrellis/shortcuts.py` (`line`, `points`, ... `SHORTCUTS`, `plot`,
  `KINDS`, `Accessor`), `pandas.py` and `polars.py` (`df.trellis`), `__init__.py`,
  `pyproject.toml` (the `pandas_plotting_backends` entry point); `tests/test_shortcuts.py`;
  `docs/user/how-to/one-call.md`, `reference/shortcuts.md`.

## Context

A plot takes two steps: `Trellis(df, wrap=...)`, then a mark. People arriving from
Plotly Express (`px.line(df, x=, y=, facet_col=)`) or pandas (`df.plot(...)`, hvPlot's
`df.hvplot`) expect one call. The review asked for `at.line(df, x=, y=, wrap=)` returning
a `Trellis`, and a `df.plot`-style entry point.

## Decision

- **A shortcut a common mark**, named as the method: `at.line`, `at.points`, `at.bars`,
  `at.area`, `at.hist`, `at.density`, `at.box`, `at.violin`, `at.ecdf`, `at.hexbin`. Each
  argument goes to `Trellis()` or to the mark by its name; the two share none (but
  `rect(height=)`, which has no shortcut). An unknown name is a `TypeError` naming the
  closest. The table is positional-only, so a mark's own `data=` is not offered. It
  returns the `Trellis`, so `t.code()` writes the long form and more layers chain on.
- **Their signatures are made, not written out**: each shortcut's `__signature__` joins
  the mark's arguments and `Trellis()`'s, so `help()` and a notebook's Shift+Tab list all
  of them, and they never fall behind the methods. Static checkers see
  `(data, /, **kwargs) -> Trellis`.
- **pandas' backend, through an entry point** (`pandas_plotting_backends: anytrellis =
  anytrellis.shortcuts`): `pd.options.plotting.backend = "anytrellis"` makes `df.plot`
  call `shortcuts.plot`. It maps pandas' kinds (`scatter`, `bar`, `barh`, `kde`) to marks
  and its arguments (`by=` as `wrap=`, `logx=`, `logy=`, `loglog=`, `xlabel=`, `ylabel=`,
  `legend=False`, `stacked=`, `figsize=` as the height); pandas' own arguments it passes
  as None are dropped. As in pandas, no x is the index, and no y, or several, is every
  number column as a series of its own: the table made long (narwhals `unpivot`), the
  columns' names in `column`, coloured by it. `pie` is refused.
- **`df.trellis`, opted into**: `import anytrellis.pandas` (DataFrames and Series) or
  `import anytrellis.polars` (DataFrames and LazyFrames) registers the accessor, its
  methods the shortcuts by way of `plot`. `import anytrellis` imports neither library
  (it stays at about 70 ms; pandas and Polars would add 300), as hvPlot's
  `import hvplot.pandas` does. Polars' own `df.plot` stays Altair's.
- **Any table**: the shortcuts and `plot` take what `Trellis` takes, DuckDB relations
  with `load="pages"` included (0004).

## Known limits

- No `at.plot` at the top: `anytrellis.plot` is the module that holds `Trellis`. The
  function is `anytrellis.shortcuts.plot`, and pandas reaches it by the entry point.
- pandas' matplotlib arguments (`ax=`, `subplots=`, `grid=`, `rot=`, colours as `color=`)
  are errors: `color=` names a column here.
- Several columns as series are ordered by name in boxes and legends, not as given.
