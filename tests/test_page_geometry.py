"""``load="pages"``: a page turned keeps the geometry of the panels still read and makes
only that of the rows read now; what it draws is what a plot drawn at that page draws."""

from __future__ import annotations

from typing import Any

import duckdb
import numpy as np
import polars as pl
import pytest
from test_page_summaries import readings

from anytrellis import Trellis
from anytrellis import plot as plot_module
from anytrellis.layers import axis_values


def data() -> pl.DataFrame:
    df = readings(4000, stations=40).filter(pl.col("station").is_not_null())
    return df.with_columns(label=pl.col("sensor") + "!")


MARKS: list[tuple[str, dict[str, Any]]] = [
    ("points", {"x": "t", "y": "v", "color": "w"}),
    ("points", {"x": "t", "y": "v", "color": "sensor"}),
    ("line", {"x": "t", "y": "v", "color": "sensor"}),
    ("line", {"x": "when", "y": "v", "step": "mid"}),
    ("text", {"x": "t", "y": "v", "text": "label"}),
    ("line", {"x": "t", "y": "v", "group": "sensor", "color": "w"}),
]


def drawn(p: Trellis) -> list[dict[int, list[tuple[float, ...]]]]:
    """Per plain layer, per panel: its instances (ends, colour), sorted."""
    out = []
    for layer, table, geom in p._geometry:
        if geom is None or (table.n == 0 and geom.count == 0):
            continue
        assert layer.x is not None
        if layer.step is None:  # each instance's rows: its own (a step's risers: between)
            x = axis_values(table.column(layer.x), None)
            assert np.allclose(x[geom.rows], geom.x0, equal_nan=True)
            if geom.rows_end is not None:
                assert np.allclose(x[geom.rows_end], geom.x1, equal_nan=True)
        rgba = geom.rgba if geom.rgba is not None else np.zeros((geom.count, 4))
        cols = [geom.x0, geom.y0, geom.x1, geom.y1, *np.asarray(rgba, dtype=float).T]
        rows = np.round(np.column_stack(cols), 6)
        out.append({int(k): sorted(map(tuple, rows[geom.panel == k].tolist()))
                    for k in np.unique(geom.panel)})  # fmt: skip
    return out


@pytest.mark.parametrize(("mark", "kw"), MARKS)
def test_a_page_turned_draws_what_a_plot_at_that_page_draws(
    mark: str, kw: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    df = data()
    rel = duckdb.from_arrow(df.to_arrow())

    def make() -> Trellis:
        return getattr(Trellis(rel, wrap="station", rows=2, cols=3, load="pages"), mark)(**kw)

    merged: list[int] = []
    original = plot_module._merged

    def counted(*args: Any, **kws: Any) -> Any:
        merged.append(1)
        return original(*args, **kws)

    monkeypatch.setattr(plot_module, "_merged", counted)
    p = make()
    p._scene()
    for page in (2, 3, 4, 3, 7):
        p.show_page(page)
        fresh = make()
        fresh.show_page(page)
        assert drawn(p) == drawn(fresh), page
    assert merged  # (pages turned to one page further: the kept panels' geometry kept)
