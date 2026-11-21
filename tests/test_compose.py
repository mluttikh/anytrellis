"""Different plots in one figure (``compose.py``): ``a | b``, ``a / b`` and ``concat()``,
laid out alike in a notebook, a page and an image."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

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
