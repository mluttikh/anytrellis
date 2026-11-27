"""Different plots in one figure (``compose.py``): ``a | b``, ``a / b`` and ``concat()``,
laid out alike in a notebook, a page and an image."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl
import pytest

from anytrellis import Concat, Trellis, concat, link
from anytrellis.compose import GAP, TITLE_SPACE
from anytrellis.datasets import load
from anytrellis.figure import HEADER

HEADER_SPACE = HEADER + TITLE_SPACE  # a figure's title over its plots
SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture
def plots() -> tuple[Trellis, Trellis, Trellis]:
    cars = load("cars")
    a = Trellis(cars, wrap="origin", title="Weight").points(x="weight", y="mpg")
    b = Trellis(cars, title="Horsepower").hist(x="horsepower")
    c = Trellis(cars).box(x="origin", y="mpg")
    return a, b, c


def test_bars_and_slashes_make_rows_and_columns(plots: tuple[Trellis, ...]) -> None:
    a, b, c = plots
    row = a | b | c  # a row added to, not nested
    assert isinstance(row, Concat)
    assert row.items == [a, b, c]
    assert row.cols == 3
    column = a / b / c
    assert column.items == [a, b, c]
    assert column.cols == 1
    mixed = (a | b) / c  # a row over a plot: nested
    assert mixed.cols == 1
    assert isinstance(mixed.items[0], Concat)
    assert mixed.items[1] is c
    assert mixed.plots == [a, b, c]
    titled = concat(a, b, title="Two")
    assert (titled | c).items == [titled, c]  # a titled figure is kept whole
    assert (c | (a | b)).items == [c, a, b]


def test_a_grid_checks_what_it_is_given(plots: tuple[Trellis, ...]) -> None:
    a, b, c = plots
    grid = concat(a, b, c, cols=2, widths=[2, 1])
    assert grid._rows() == [[a, b], [c]]
    assert concat(a, b, cols=5).cols == 2  # no more columns than plots
    with pytest.raises(ValueError, match="widths must be 2"):
        concat(a, b, widths=[1])
    with pytest.raises(ValueError, match="cols"):
        concat(a, b, cols=0)
    with pytest.raises(TypeError, match="Trellis"):
        concat(a, "b")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="a plot or more"):
        concat()


def _num(e: ET.Element, name: str) -> float:
    return float(e.get(name, "nan"))


def _placed(svg: str) -> tuple[ET.Element, list[ET.Element]]:
    root = ET.fromstring(svg)
    return root, [e for e in root if e.tag == f"{SVG}svg"]


def test_an_image_puts_each_plot_where_the_grid_does(plots: tuple[Trellis, ...]) -> None:
    a, b, c = plots
    grid = concat(a, b, c, cols=2, widths=[2, 1], title="Cars")
    root, placed = _placed(grid._svg(824, "light"))
    assert root.get("width") == "824"
    assert root.findtext(f"{SVG}title") == "Cars"
    room = 824 - GAP
    x = [_num(e, "x") for e in placed]
    w = [_num(e, "width") for e in placed]
    assert w[0] == pytest.approx(room * 2 / 3, abs=0.01)
    assert w[1] == pytest.approx(room / 3, abs=0.01)
    assert x == pytest.approx([0, room * 2 / 3 + GAP, 0], abs=0.01)
    y = [_num(e, "y") for e in placed]
    tallest = max(_num(placed[0], "height"), _num(placed[1], "height"))
    assert y[0] == y[1] == HEADER_SPACE
    assert y[2] == pytest.approx(HEADER_SPACE + tallest + GAP, abs=0.01)
    assert _num(root, "height") == pytest.approx(y[2] + _num(placed[2], "height"), abs=0.01)
    # one image, no id twice: each plot's clip paths its own
    ids = re.findall(r' id="([^"]+)"', grid._svg(824, "light"))
    assert ids
    assert len(ids) == len(set(ids))
    with pytest.raises(ValueError, match="at least"):
        grid._svg(150, "light")


def test_nested_figures_and_their_width_as_shown(
    plots: tuple[Trellis, ...], tmp_path: Path
) -> None:
    a, b, c = plots
    fig = (a | b) / c
    _, placed = _placed(fig._svg(800, "dark"))
    assert [_num(e, "width") for e in placed] == [800, 800]
    inner = [e for e in placed[0] if e.tag == f"{SVG}svg"]
    assert [_num(e, "x") for e in inner] == pytest.approx([0, (800 - GAP) / 2 + GAP])
    assert fig._width() == 800  # never shown: 400 a column, at least 800
    for p, width in ((a, 500), (b, 300), (c, 824)):
        p._view = {"width": width}
    assert (a | b)._width() == 500 * 2 + GAP  # the widest column, as an equal share
    assert fig._width() == 1024
    assert fig.save_svg(tmp_path / "f.svg").read_text().startswith("<svg")
    pytest.importorskip("resvg_py")
    assert fig.save_png(tmp_path / "f.png", scale=1).read_bytes()[:4] == b"\x89PNG"


def test_a_page_of_the_grid_keeps_links(plots: tuple[Trellis, ...]) -> None:
    a, b, c = plots
    grid = concat(a, b, c, cols=2, widths=[2, 1], title="Cars")
    page = grid.to_html()
    assert page.count("class='anytrellis-embed'") == 3
    assert "grid-template-columns:minmax(0,2fr) minmax(0,1fr)" in page
    assert "anytrellis-concat-title" in page
    assert "<title>Cars</title>" in page
    assert "class='anytrellis-concat'" in page  # not linked: no anytrellis-link
    link(a, b)
    payloads = [json.loads(s) for s in re.findall(r"<script type='application/json'>(.*?)</script>",
                                                  grid.to_html())]  # fmt: skip
    groups = [p["link"] and p["link"]["group"] for p in payloads]
    assert groups[0]
    assert groups[0] == groups[1]
    assert groups[2] is None
    assert "class='anytrellis-concat anytrellis-link'" in grid.to_html()


def test_in_a_notebook_a_grid_of_the_plots_widgets(plots: tuple[Trellis, ...]) -> None:
    a, b, c = plots
    box = concat(a, b, widths=[2, 1]).widget
    assert list(box.children) == [a.widget, b.widget]
    assert box.layout.grid_template_columns == "minmax(0,2fr) minmax(0,1fr)"
    titled = concat(a, b / c, title="Cars").widget
    heading, grid = titled.children
    assert "Cars" in heading.value
    assert grid.children[1].children == (b.widget, c.widget)
    marimo = pytest.importorskip("marimo")
    assert isinstance((a | b)._display_(), marimo.Html)
    assert (
        repr(concat(a, b, c, cols=2, title="Cars")) == "Concat(3 items in 2 columns, title='Cars')"
    )


def _boxes(fig: Concat, width: float) -> list[tuple[float, float, float, float]]:
    """Each plot's panels' box in the figure's image: left, top, right, bottom."""
    from anytrellis.figure import figure_box

    room = width - GAP * (fig.cols - 1)
    col_w = [room * w / sum(fig.widths) for w in fig.widths]
    aligned = fig._aligned(col_w)
    out = []
    for i, item in enumerate(fig.items):
        assert isinstance(item, Trellis)
        c = i % fig.cols
        frame, height = aligned.get(i, (None, None))
        box = figure_box(item, col_w[c], height, frame)
        x = sum(col_w[:c]) + GAP * c
        out.append((x + box.left, box.top, x + col_w[c] - box.right, box.top + box.height))
    return out


def test_a_figure_lines_its_plots_panels_up(plots: tuple[Trellis, ...]) -> None:
    a, b, c = plots
    cars = load("cars")
    # y labels of different widths, a subtitle over one plot's panels, a narrow column
    d = Trellis(cars, title="Displacement", subtitle="A line under the title").points(
        x="weight", y="displacement")  # fmt: skip
    fig = concat(a, b, c, d, cols=2, widths=[2, 1])
    (al, at, ar, ab), (bl, bt, br, bb), (cl, ct, cr, cb), (dl, dt, dr, db) = _boxes(fig, 900)
    assert al == cl  # a column: the same left and right edges
    assert ar == cr
    assert bl == dl
    assert br == dr
    assert at == bt  # a row: the same top
    assert ct == dt
    assert ab == bb  # heights free: as high as each other
    assert cb == db
    # as each is alone: not lined up
    alone = _boxes(concat(a, b, c, d, cols=2, widths=[2, 1], align=False), 900)
    assert (alone[0][0], alone[0][1]) != (alone[2][0], alone[1][1])
    assert alone[0][3] != alone[1][3]
    # the image is drawn so: each plot as figure_svg draws it, framed and stretched
    from anytrellis.figure import figure_svg

    width = (900 - GAP) / 3
    frame, height = fig._aligned([width * 2, width])[1]
    assert height is not None
    own = figure_svg(b, width=width, height=height, frame=frame, ids="p1-")
    head = '<svg xmlns="http://www.w3.org/2000/svg" '
    assert own[len(head) :] in fig._svg(900, "light")


def test_a_plot_whose_height_is_set_keeps_it(plots: tuple[Trellis, ...]) -> None:
    a, _, c = plots
    cars = load("cars")
    tall = Trellis(cars, title="Tall", height=500).points(x="weight", y="mpg")
    square = Trellis(cars, aspect=1).points(x="weight", y="mpg")
    (_, at, _, ab), (_, tt, _, tb) = _boxes(concat(a, tall), 900)
    assert at == tt  # its top lined up
    assert ab != tb  # not stretched, nor the other to it
    _, placed = _placed(concat(a, tall)._svg(900, "light"))
    _, alone = _placed(concat(a, tall, align=False)._svg(900, "light"))
    assert _num(placed[1], "height") == _num(alone[1], "height")  # as high as it says
    (_, ct, _, _), (sl, st, sr, sb) = _boxes(concat(c, square), 900)
    assert ct == st
    assert sb - st == pytest.approx(sr - sl, abs=1)  # square panels kept square
    with pytest.raises(TypeError, match="align"):
        concat(a, c, align="yes")  # ty: ignore[invalid-argument-type]


def test_the_browser_is_told_where_each_plot_is(plots: tuple[Trellis, ...]) -> None:
    a, b, c = plots
    inner = a | b
    fig = inner / c
    payloads = [json.loads(s) for s in re.findall(r"<script type='application/json'>(.*?)</script>",
                                                  fig.to_html())]  # fmt: skip
    cells = [p["figure"] for p in payloads]
    assert cells[0] == {"group": inner._group, "row": 0, "col": 0}
    assert cells[1] == {"group": inner._group, "row": 0, "col": 1}
    assert cells[2] == {"group": fig._group, "row": 1, "col": 0}
    assert inner._group != fig._group
    fig.widget  # noqa: B018 (made: each plot's widget told its place)
    assert a.widget._figure == cells[0]
    assert c.widget._figure == cells[2]
    concat(a, b, align=False).widget  # noqa: B018
    assert a.widget._figure is None
    # an unaligned row is kept whole: a | b added to it would line b up after all
    assert len((concat(a, b, align=False) | c).items) == 2


@pytest.fixture
def coloured() -> tuple[Trellis, Trellis, Trellis]:
    cars = load("cars")
    d = Trellis(cars, wrap="origin", title="Weight").points(x="weight", y="mpg", color="origin")
    e = Trellis(cars, title="Horsepower").hist(x="horsepower", color="origin")
    f = Trellis(cars, title="Cylinders").points(x="weight", y="mpg", color="cylinders")
    return d, e, f


def test_a_figure_collects_its_plots_legends(coloured: tuple[Trellis, ...]) -> None:
    d, e, f = coloured
    with pytest.raises(ValueError, match="legend must be"):
        concat(d, e, legend="right")
    fig = concat(d, e, f, cols=3, legend="collect")
    assert len((fig | d).items) == 2  # a figure that collects is kept whole
    svg = fig._svg(900, "light")
    _, placed = _placed(svg)
    plots, legend = placed[:3], placed[3:]
    # the plots draw no legend of their own; the figure's, under them, has each once
    for p in plots:
        assert ">origin<" not in ET.tostring(p, encoding="unicode")
    assert len(legend) == 1
    text = ET.tostring(legend[0], encoding="unicode")
    assert text.count(">origin<") == 1
    assert ">cylinders<" in text
    assert _num(legend[0], "y") == pytest.approx(max(_num(p, "height") for p in plots), abs=0.01)
    assert _num(ET.fromstring(svg), "height") == pytest.approx(
        _num(legend[0], "y") + _num(legend[0], "height"), abs=0.01
    )
    # a plot with legend("none") adds none; nothing to show: no legend at all
    f.legend("none")
    text = ET.tostring(_placed(fig._svg(900, "light"))[1][3], encoding="unicode")
    assert ">cylinders<" not in text
    plain = Trellis(load("cars")).points(x="weight", y="mpg")
    assert len(_placed(concat(plain, plain, legend="collect")._svg(900, "light"))[1]) == 2


def test_the_browser_is_told_which_figure_shows_the_legends(
    coloured: tuple[Trellis, ...],
) -> None:
    d, e, f = coloured
    inner = concat(d, e, legend="collect")
    fig = concat(inner, f, cols=1, legend="collect")
    page = fig.to_html()
    payloads = [json.loads(s) for s in re.findall(r"<script type='application/json'>(.*?)</script>",
                                                  page)]  # fmt: skip
    places = [p["figure"] for p in payloads]
    # the outermost figure that collects shows them all: one legend on the page
    assert [p["legend"] for p in places] == [fig._group] * 3
    assert [p["order"] for p in places] == [0, 1, 2]
    assert places[0]["group"] == inner._group  # lined up within its own figure
    assert page.count("class='anytrellis-figure-legend'") == 1
    assert f"data-legend='{fig._group}'" in page
    box = fig.widget
    from anytrellis.widget import FigureLegendWidget

    legends = [w for w in box.children if isinstance(w, FigureLegendWidget)]
    assert [w._legend_hub for w in legends] == [fig._group]
    assert d.widget._figure == places[0]
    # one that keeps them: no legend of the figure's, nor its group on the plots
    kept = concat(d, e)
    kept.widget  # noqa: B018
    assert "legend" not in d.widget._figure
    assert "class='anytrellis-figure-legend'" not in kept.to_html()


def _ranges(t: Trellis, axis: str) -> list[tuple[float, float]]:
    spec, _ = t._scene()
    origin = spec[axis]["origin"]
    return [(p[axis][0] + origin, p[axis][1] + origin) for p in spec["panels"]]


def _sharing_plots() -> tuple[Trellis, Trellis, Trellis]:
    cars = load("cars")
    light = cars.filter(pl.col("weight") < 3000)
    heavy = cars.filter(pl.col("weight") >= 3000)
    a = Trellis(light, wrap="origin").points(x="weight", y="mpg").share(y=False)
    b = Trellis(heavy).points(x="weight", y="mpg")
    c = Trellis(heavy).points(x="horsepower", y="acceleration")
    return a, b, c


def test_a_figure_shares_a_range_among_its_plots() -> None:
    a, b, _c = _sharing_plots()
    own_a, own_b = _ranges(a, "y"), _ranges(b, "y")
    assert len(set(own_a)) > 1  # share(y=False): each panel its own
    fig = (a | b).share(y=True)
    assert not fig._bare()  # added to by |, it is kept whole
    fig._svg(800, "light")
    ya, yb = _ranges(a, "y"), _ranges(b, "y")
    assert len(set(ya)) == 1
    assert ya[0] == yb[0]
    lo, hi = ya[0]
    assert (lo, hi) == (min(r[0] for r in own_a + own_b), max(r[1] for r in own_a + own_b))
    spec, _ = a._scene()
    assert spec["y"]["share"] == "all"
    assert {p["yg"] for p in spec["panels"]} == {0}
    assert _ranges(a, "x") != _ranges(b, "x")  # x is each plot's own
    # a page (the docs embed it) carries the range too
    c, d = _sharing_plots()[:2]
    page = concat(c, d, share_y=True)._embed_html()
    specs = [json.loads(m)["spec"] for m in
             re.findall(r"<script type='application/json'>(.*?)</script>", page)]  # fmt: skip
    assert len(specs) == 2
    shown = {(p["y"][0] + sp["y"]["origin"], p["y"][1] + sp["y"]["origin"])
             for sp in specs for p in sp["panels"]}  # fmt: skip
    assert shown == {c._joined["y"]}
    assert c._joined["y"] == d._joined["y"]
    # a figure that doesn't share gives each plot its own range back
    (a | b)._svg(800, "light")
    assert _ranges(a, "y") == own_a
    assert _ranges(b, "y") == own_b


def test_rows_columns_and_nested_figures_share() -> None:
    a, b, c = _sharing_plots()
    d = Trellis(load("cars")).points(x="weight", y="horsepower")
    fig = concat(a, b, c, d, cols=2, share_y="row", share_x="col")
    groups = {axis: [[id(p) for p in g] for g in fig._share_groups(axis)] for axis in "xy"}
    assert groups["y"] == [[id(a), id(b)], [id(c), id(d)]]
    assert groups["x"] == [[id(a), id(c)], [id(b), id(d)]]
    # a nested figure in a row: all its plots in the row's group; lines meeting are one
    inner = (b / c).share(y=True)
    outer = concat(a, inner, share_y="row")
    assert [sorted(map(id, g)) for g in outer._share_groups("y")] == [sorted([id(a), id(b), id(c)])]
    # a row of one plot shares nothing
    assert concat(a, b, cols=1, share_y="row")._share_groups("y") == []
    with pytest.raises(ValueError, match="share_y must be"):
        concat(a, b, share_y="page")


def test_limits_and_a_plot_changed_later_move_the_shared_range() -> None:
    a, b, _ = _sharing_plots()
    a.limits(y=(0, None))
    fig = concat(a, b, share_y=True)
    assert fig.widget is not None  # shown: its plots' widgets get the range
    assert _ranges(b, "y")[0][0] == 0
    sent = b.widget._spec["panels"][0]["y"]
    assert sent[0] == 0
    a.limits(y=(-10, None))  # a shown plot changed: its peer follows
    assert b.widget._spec["panels"][0]["y"][0] == -10


def test_axes_that_cannot_share() -> None:
    cars = load("cars")
    a = Trellis(cars).points(x="weight", y="mpg")
    log = Trellis(cars).points(x="weight", y="mpg").scale(y="log")
    with pytest.raises(ValueError, match="different kinds"):
        concat(a, log, share_y=True)._svg(800, "light")
    bars = Trellis(cars).bars(x="origin", y="mpg", stat="mean")
    some = Trellis(cars.filter(pl.col("origin") != "Japan")).bars(x="origin", y="mpg", stat="mean")
    with pytest.raises(ValueError, match="different categories"):
        concat(bars, some, share_x=True)._svg(800, "light")
    same = Trellis(cars).bars(x="origin", y="horsepower", stat="mean")
    concat(bars, same, share_x=True, share_y=True)._svg(800, "light")  # the same: fine
    assert "x" not in bars._joined
    assert "y" in bars._joined
