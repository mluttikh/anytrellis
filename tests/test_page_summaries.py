"""``load="pages"``: summaries of the plot's data (histograms, box plots, violins,
densities, smooth fits, error bars) computed by the database, every panel's, without
reading the rows: drawn as they are from the rows, and a brush over them selects the rows
they stand for, as a query."""

from __future__ import annotations

import datetime as dt
from typing import Any

import duckdb
import narwhals as nw
import numpy as np
import polars as pl
import pytest
from test_query import LAZY

import anytrellis.plot
from anytrellis import Trellis
from anytrellis.data import Table
from anytrellis.stats import _loess, loess_binned


def readings(n: int = 6000, stations: int = 24) -> pl.DataFrame:
    """Stations' readings by sensor, with missing and infinite values, and times."""
    rng = np.random.default_rng(3)
    t = rng.uniform(0, 10, n)
    v = np.sin(t) * 2 + rng.normal(0, 1, n)
    v[::31] = np.nan
    v[::37] = np.inf
    station = np.array([f"s{k:02d}" for k in rng.integers(0, stations, n)], dtype=object)
    station[::53] = None
    start = dt.datetime(2024, 1, 1)  # noqa: DTZ001 - wall-clock times
    return pl.DataFrame({
        "id": np.arange(n),
        "station": station.tolist(),
        "sensor": rng.choice(["a", "b", "c"], n).tolist(),
        "t": t,
        "v": v,
        "w": rng.lognormal(0, 1, n),
        "when": [start + dt.timedelta(minutes=int(m)) for m in rng.integers(0, 43_200, n)],
    })  # fmt: skip


MARKS: list[tuple[str, dict[str, Any], dict[str, str]]] = [
    ("hist", {"x": "v", "color": "sensor"}, {}),
    ("hist", {"x": "v", "bins": [-2, -1, 0, 0.5, 3], "stat": "percent"}, {}),
    ("hist", {"x": "sensor", "stat": "density"}, {}),
    ("hist", {"x": "w", "binwidth": 0.25}, {"x": "log"}),
    ("box", {"x": "sensor", "y": "v", "tooltip": ["id"]}, {}),
    ("box", {"y": "sensor", "x": "w"}, {"x": "log"}),
    ("box", {"x": "t", "y": "v", "outliers": False}, {}),
    ("violin", {"x": "sensor", "y": "v", "color": "sensor", "scale": "count"}, {}),
    ("density", {"x": "v", "color": "sensor", "fill": True}, {}),
    ("density", {"x": "w"}, {"x": "log"}),
    ("smooth", {"x": "t", "y": "v"}, {}),
    ("smooth", {"x": "t", "y": "v", "method": "linear", "color": "sensor"}, {}),
    ("smooth", {"x": "w", "y": "w", "method": "linear", "fullrange": True},
     {"x": "log", "y": "log"}),
    ("errorbar", {"x": "sensor", "y": "v"}, {}),
    ("errorbar", {"x": "sensor", "y": "v", "extent": "range", "color": "sensor"}, {}),
]  # fmt: skip

TIMES: list[tuple[str, dict[str, Any], dict[str, str]]] = [
    ("hist", {"x": "when", "binwidth": "2D"}, {}),
    ("box", {"x": "when", "y": "v"}, {}),
    ("density", {"x": "when"}, {}),
    ("smooth", {"x": "when", "y": "v", "method": "linear"}, {}),
    ("smooth", {"x": "when", "y": "v"}, {}),
]


def pair(make: Any, df: pl.DataFrame, mark: str, kw: dict[str, Any],
         scale: dict[str, str]) -> tuple[Trellis, Trellis]:  # fmt: skip
    """The summary of a lazy table read a page at a time, and of the rows in memory."""
    paged = getattr(Trellis(make(df), wrap="station", load="pages"), mark)(**kw).scale(**scale)
    eager = getattr(Trellis(df, wrap="station"), mark)(**kw).scale(**scale)
    return paged, eager


def reads(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every read of rows of a lazy table: whole (``Table._load``) or a page's."""
    seen: list[Any] = []
    load, query = Table._load, anytrellis.plot.Trellis._query_rows

    def loaded(self: Table) -> None:
        seen.append(("load", list(self._wanted)))
        load(self)

    def queried(self: Any, grid: Any, panels: Any, names: Any) -> Table:
        seen.append(("rows", names))
        return query(self, grid, panels, names)

    monkeypatch.setattr(Table, "_load", loaded)
    monkeypatch.setattr(anytrellis.plot.Trellis, "_query_rows", queried)
    return seen


def drawn(p: Trellis) -> list[np.ndarray]:
    """Each drawn part's instances: panel, x0, y0, x1, y1, each sorted within its panel."""
    out = []
    for _, _, geom in p._geometry:
        if geom is None:
            continue
        a = np.stack([geom.panel, geom.x0, geom.y0, geom.x1, geom.y1], axis=1)
        a = a[np.argsort(a[:, 0], kind="stable")]
        ends = np.searchsorted(a[:, 0], np.unique(a[:, 0]), side="right").tolist()
        for lo, hi in zip([0, *ends][: len(ends)], ends, strict=True):
            a[lo:hi, 1:] = np.sort(a[lo:hi, 1:], axis=0)
        out.append(a)
    return out


def assert_same(paged: Trellis, eager: Trellis, rtol: float = 2e-3) -> None:
    sp, se = paged._scene()[0], eager._scene()[0]
    assert paged.panels() == eager.panels()
    for a, b in zip(sp["panels"], se["panels"], strict=True):
        assert np.allclose(a["x"], b["x"], rtol=rtol), a["label"]
        assert np.allclose(a["y"], b["y"], rtol=rtol), a["label"]
    assert sp["x"] == se["x"]
    assert sp["legends"] == se["legends"]
    for a, b in zip(drawn(paged), drawn(eager), strict=True):
        assert a.shape == b.shape
        assert np.array_equal(a[:, 0], b[:, 0])
        scale = np.nanmax(np.abs(b[:, 1:]), axis=0, initial=1.0)
        diff = np.abs(a[:, 1:] - b[:, 1:]) / scale
        assert np.nanmax(diff, initial=0.0) < rtol


@pytest.mark.parametrize("kind", list(LAZY))
@pytest.mark.parametrize(("mark", "kw", "scale"), MARKS)
def test_summaries_from_the_database_as_from_the_rows(kind: str, mark: str, kw: dict[str, Any],
                                                      scale: dict[str, str],
                                                      monkeypatch) -> None:  # fmt: skip
    seen = reads(monkeypatch)
    paged, eager = pair(LAZY[kind], readings(), mark, kw, scale)
    paged._scene()
    assert seen == []  # no row read: only the summaries
    assert_same(paged, eager)


@pytest.mark.parametrize("kind", list(LAZY))
@pytest.mark.parametrize(("mark", "kw", "scale"), TIMES)
def test_summaries_over_time(kind: str, mark: str, kw: dict[str, Any], scale: dict[str, str],
                             monkeypatch) -> None:  # fmt: skip
    seen = reads(monkeypatch)
    paged, eager = pair(LAZY[kind], readings(), mark, kw, scale)
    assert_same(paged, eager)
    # Ibis has no times as numbers: the rows of the columns drawn, read once
    assert seen == [] if kind != "ibis" or mark == "box" else len(seen) == 1


def panels(entry: Any) -> np.ndarray:
    """A spec layer's instances' panels."""
    geom = entry[2]
    assert geom is not None
    return geom.panel


def test_a_page_turned_asks_nothing_again(monkeypatch) -> None:
    asked: list[str] = []
    original = anytrellis.plot.queried_parts

    def spy(layer: Any, *args: Any) -> Any:
        asked.append(layer.mark)
        return original(layer, *args)

    monkeypatch.setattr(anytrellis.plot, "queried_parts", spy)
    rel = duckdb.from_arrow(readings(stations=60).to_arrow())
    p = Trellis(rel, wrap="station", load="pages", rows=2, cols=3)
    p.hist(x="v").density(x="v")
    p._scene()
    assert asked == ["hist", "density"]
    every = len(panels(p._full[0]))
    sent = len(panels(p._sent[0]))
    assert sent < every  # the panels around the page shown
    p._paging = {"page": 3}
    message = p._detail(None)
    assert message is not None
    assert asked == ["hist", "density"]  # every panel's, already
    shown = {int(i) for i in panels(p._sent[0])}
    assert shown == set(p._window or ())


def test_points_and_a_summary_read_only_the_points_columns(monkeypatch) -> None:
    seen = reads(monkeypatch)
    df = readings()
    rel = duckdb.from_arrow(df.to_arrow())
    p = Trellis(rel, wrap="station", load="pages", rows=2, cols=3)
    p.points(x="t", y="v").hist(x="w")
    p._scene()
    assert [names for what, names in seen] == [("station", "t", "v")]
    eager = Trellis(df, wrap="station", rows=2, cols=3).points(x="t", y="v").hist(x="w")
    assert np.allclose([q["x"] for q in p._scene()[0]["panels"]],
                       [q["x"] for q in eager._scene()[0]["panels"]])  # fmt: skip


def ids(native: Any) -> set[int]:
    frame = nw.from_native(native)
    if isinstance(frame, nw.LazyFrame):
        frame = frame.collect()
    return set(frame["id"].to_list())


BRUSHES: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, str]]] = [
    ("hist", {"x": "v", "color": "sensor"}, {"x": (-0.5, 0.7)}, {}),
    ("hist", {"x": "v", "color": "sensor"}, {"x": (-0.5, 0.7), "color": ["a"]}, {}),
    ("hist", {"x": "sensor"}, {"x": ["b"]}, {}),
    ("hist", {"x": "w"}, {"x": (2, 5)}, {"x": "log"}),
    ("hist", {"x": "when"}, {"x": ("2024-01-05", "2024-01-09")}, {}),
    ("box", {"x": "sensor", "y": "v"}, {"y": (2.5, 9)}, {}),
    ("box", {"x": "t", "y": "v"}, {"x": (2, 3)}, {}),
    ("violin", {"x": "sensor", "y": "v"}, {"x": ["b"]}, {}),
    ("density", {"x": "v", "color": "sensor"}, {"x": (0, 1)}, {}),
    ("smooth", {"x": "t", "y": "v"}, {"x": (2, 3)}, {}),
    ("errorbar", {"x": "sensor", "y": "v"}, {"x": ["a"]}, {}),
]


@pytest.mark.parametrize("kind", list(LAZY))
@pytest.mark.parametrize(("mark", "kw", "brush", "scale"), BRUSHES)
def test_a_brush_selects_the_rows_summarised(kind: str, mark: str, kw: dict[str, Any],
                                             brush: dict[str, Any],
                                             scale: dict[str, str]) -> None:  # fmt: skip
    paged, eager = pair(LAZY[kind], readings(), mark, kw, scale)
    for panel in (None, "s03"):
        paged.select(**brush, panel=panel)
        eager.select(**brush, panel=panel)
        chosen = paged.selected()
        assert not isinstance(nw.from_native(chosen), nw.DataFrame)  # a query, not yet read
        assert ids(chosen) == ids(eager.selected())
        assert ids(chosen)
    paged.select()
    assert ids(paged.selected()) == set()


@pytest.mark.parametrize(("mark", "kw"), [
    ("violin", {"x": "sensor", "y": "v", "inner": "points"}),
    ("errorbar", {"x": "sensor", "y": "v", "ymin": "w", "ymax": "w"}),
])  # fmt: skip
def test_what_the_database_does_not_summarise_comes_from_the_rows(mark: str, kw: dict[str, Any],
                                                                  monkeypatch) -> None:  # fmt: skip
    seen = reads(monkeypatch)
    paged, eager = pair(LAZY["duckdb"], readings(), mark, kw, {})
    assert_same(paged, eager)
    assert len(seen) == 1  # the columns it draws, once
    paged._paging = {"page": 2}
    paged._detail(None)
    assert len(seen) == 1
    paged.select(x=["a"])
    eager.select(x=["a"])
    assert ids(paged.selected()) == ids(eager.selected())


def test_a_saved_page_of_summaries_reads_no_row(monkeypatch, tmp_path) -> None:
    seen = reads(monkeypatch)
    rel = duckdb.from_arrow(readings(stations=60).to_arrow())
    p = Trellis(rel, wrap="station", load="pages", rows=2, cols=3).hist(x="v", color="sensor")
    p.save_html(tmp_path / "hist.html")
    assert seen == []
    assert p._shadow is None  # every panel's summaries, as the plot has them: no rows read
    every = len(panels(p._full[0]))
    assert every > len(panels(p._sent[0]))  # the widget's: the panels around the page


def test_the_same_errors() -> None:
    rel = duckdb.from_arrow(readings(600).to_arrow())
    with pytest.raises(ValueError, match="split by a category"):
        Trellis(rel, wrap="station", load="pages").hist(x="v", color="t")._scene()
    with pytest.raises(ValueError, match="must be numbers"):
        Trellis(rel, wrap="station", load="pages").box(x="sensor", y="station")._scene()
    with pytest.raises(ValueError, match="log y axis"):
        Trellis(rel, wrap="station", load="pages").hist(x="v").scale(y="log")._scene()
    with pytest.raises(ValueError, match="categories"):
        Trellis(rel, wrap="station", load="pages").density(x="sensor")._scene()


def test_loess_of_binned_values_is_loess() -> None:
    rng = np.random.default_rng(5)
    x = np.sort(rng.uniform(0, 1, 400))
    y = np.sin(6 * x) + rng.normal(0, 0.2, 400)
    at = np.linspace(0, 1, 50)
    exact, se, df = _loess(x, y, at, 0.5)
    # a bin per value: the same fit
    fit, se_b, df_b = loess_binned(x, np.ones(400), y, y * y, at, 0.5)
    assert np.allclose(fit, exact)
    assert np.allclose(se_b, se)
    assert df_b == pytest.approx(df)
    # values counted in fine bins: nearly
    edges = np.linspace(0, 1, 129)
    b = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, 127)
    n = np.bincount(b, minlength=128).astype(float)
    keep = n > 0
    xb = np.bincount(b, weights=x, minlength=128)[keep] / n[keep]
    sy = np.bincount(b, weights=y, minlength=128)[keep]
    syy = np.bincount(b, weights=y * y, minlength=128)[keep]
    fit, _, _ = loess_binned(xb, n[keep], sy, syy, at, 0.5)
    assert np.abs(fit - exact).max() < 0.02
