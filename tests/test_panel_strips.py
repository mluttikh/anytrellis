"""A grid's empty cells left blank (``empty="blank"``), and a strip of each panel's own
naming it from a column (``strip_label=``). The browser and ``save_svg`` lay them out
alike (layout.ts, drawing.ts: labelEnd)."""

from __future__ import annotations

from typing import Any

import duckdb
import polars as pl
import pytest

from anytrellis import Trellis
from anytrellis.figure import _label_end, figure_svg, layout

STEPS = ("s1", "s2", "s3", "s4")


def triangle() -> pl.DataFrame:
    """From a step to the same or a later one: the cells below the diagonal have no rows."""
    parts = []
    for i, a in enumerate(STEPS):
        for b in STEPS[i:]:
            x = [float(v) for v in range(5)]
            parts.append(pl.DataFrame({"from": a, "to": b, "x": x, "y": [v * 2 for v in x]}))
    df = pl.concat(parts)
    return df.with_columns(title=pl.col("from") + " to " + pl.col("to"))


def scene(t: Trellis) -> dict[str, Any]:
    return t._scene()[0]


def test_blank_leaves_the_empty_cells_out_and_the_others_in_place() -> None:
    drawn = scene(Trellis(triangle(), row="from", col="to").points(x="x", y="y"))
    blank = Trellis(triangle(), row="from", col="to", empty="blank").points(x="x", y="y")
    spec = scene(blank)
    assert len(drawn["panels"]) == 16
    assert [(p["row"], p["col"]) for p in spec["panels"]] == [
        (r, c) for r in range(4) for c in range(r, 4)
    ]
    assert blank.panels()[:4] == ["s1 · s1", "s1 · s2", "s1 · s3", "s1 · s4"]
    assert [s.label for s in layout(spec, 800).strips] == [*STEPS, *STEPS]  # margins, as before


def test_blank_cells_take_the_axes_of_the_panels_beside_them() -> None:
    """The panel above a blank cell draws its x axis into it, the panel right of it its y
    axis; the x labels stop short of the y labels ("10" over "4")."""
    t = Trellis(triangle(), row="from", col="to", empty="blank").points(x="x", y="y")
    out = layout(scene(t), 800)
    at = {(t._grid.panels[i].row, t._grid.panels[i].col): b for i, b in enumerate(out.panels)}
    corner, diagonal = at[0, 0], at[1, 1]
    assert corner.show_x
    assert diagonal.show_y
    assert diagonal.y_axis_x is not None
    assert _label_end(out, corner) == diagonal.y_axis_x - 4
    assert _label_end(out, at[3, 3]) == float("inf")


def test_empty_takes_draw_or_blank_and_not_with_page() -> None:
    with pytest.raises(ValueError, match="empty must be one of"):
        Trellis(triangle(), row="from", col="to", empty="hide")
    with pytest.raises(ValueError, match="not supported with page="):
        Trellis(triangle(), page="from", col="to", empty="blank")
    wrap = Trellis(triangle(), wrap="to", empty="blank").points(x="x", y="y")
    assert len(scene(wrap)["panels"]) == 4  # a wrap has no empty cells


def test_a_column_names_each_panel_in_a_strip_of_its_own() -> None:
    t = Trellis(triangle(), row="from", col="to", strip_label="title", empty="blank")
    t.points(x="x", y="y")
    spec = scene(t)
    assert spec["grid"]["strip_label"] is True
    assert [p["strip"] for p in spec["panels"]][:2] == ["s1 to s1", "s1 to s2"]
    out = layout(spec, 800)
    assert out.strips == []  # no margins' strips
    assert [b.label for b in out.panels][:2] == ["s1 to s1", "s1 to s2"]
    for b in out.panels:
        assert b.strip is not None
        assert b.strip.y + b.strip.h + 1 == b.rect.y
    assert t.panels()[:2] == ["s1 · s1", "s1 · s2"]  # the panels' names: their levels
    at = {(p.row, p.col): b for p, b in zip(t._grid.panels, out.panels, strict=True)}
    below = at[1, 1].strip
    assert below is not None
    assert _label_end(out, at[0, 0]) == below.x - 4  # short of the strip below
    assert layout(spec, 800, focused=4).panels[0].label == spec["panels"][4]["strip"]


def test_a_panel_without_a_label_is_named_by_its_levels() -> None:
    df = triangle().with_columns(
        title=pl.when(pl.col("to") == "s4").then(None).otherwise(pl.col("title"))
    )
    t = Trellis(df, row="from", col="to", strip_label="title").points(x="x", y="y")
    strips = {(p["row"], p["col"]): p["strip"] for p in scene(t)["panels"]}
    assert strips[0, 0] == "s1 to s1"
    assert strips[0, 3] == "s1 · s4"  # its label missing
    assert strips[1, 0] == "s2 · s1"  # an empty cell, drawn


def test_a_label_names_one_panel() -> None:
    df = triangle().with_columns(title=pl.col("title") + pl.col("x").cast(pl.String))
    t = Trellis(df, row="from", col="to", strip_label="title").points(x="x", y="y")
    with pytest.raises(ValueError, match="panel 's1 · s1' has several values"):
        t._scene()
    t = Trellis(triangle(), row="from", col="to", strip_label="nope").points(x="x", y="y")
    with pytest.raises(ValueError, match="no data has this column"):
        t._scene()
    with pytest.raises(ValueError, match="names facet panels"):
        Trellis(triangle(), strip_label="title")


def test_a_wrap_and_its_pages_take_the_labels_too() -> None:
    wrap = Trellis(triangle(), wrap=["from", "to"], strip_label="title").points(x="x", y="y")
    out = layout(scene(wrap), 800)
    assert out.strips == []  # no nested strips over them
    assert out.panels[0].label == "s1 to s1"
    df = triangle().with_columns(title=pl.when(pl.col("to") == "s2").then(pl.col("title")))
    paged = Trellis(df, page="from", wrap="to", strip_label="title").points(x="x", y="y")
    strips = [p["strip"] for p in scene(paged)["panels"]]
    assert strips[:3] == ["s1", "s1 to s2", "s3"]  # without a label: the wrap's level alone


def test_a_database_gives_the_labels_with_the_panels() -> None:
    rel = duckdb.from_arrow(triangle().to_arrow())
    t = Trellis(rel, wrap=["from", "to"], strip_label="title", load="pages", rows=2, cols=3)
    t.points(x="x", y="y")
    spec = scene(t)
    assert [p["strip"] for p in spec["panels"]][:3] == ["s1 to s1", "s1 to s2", "s1 to s3"]
    t.show_page(1)
    clash = duckdb.from_arrow(triangle().with_columns(title=pl.col("x").cast(pl.String)).to_arrow())
    t = Trellis(clash, wrap=["from", "to"], strip_label="title", load="pages", rows=2)
    with pytest.raises(ValueError, match="has several values"):
        t.points(x="x", y="y")._scene()


def test_an_svg_draws_the_labels() -> None:
    t = Trellis(triangle(), row="from", col="to", strip_label="title", empty="blank")
    svg = figure_svg(t.points(x="x", y="y"))
    for label in ("s1 to s1", "s3 to s4", "s4 to s4"):
        assert f">{label}<" in svg
    assert ">s2 · s1<" not in svg  # a blank cell: no panel, no strip
