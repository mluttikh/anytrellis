"""Images for print: sizes in mm, cm, in or pt, a PNG's dpi, and a vector PDF
(``figure.py``: ``length``, ``print_size``, ``png_scale``, ``png_dpi``, ``svg_to_pdf``)."""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path
from typing import Any

import pytest

from anytrellis import Trellis
from anytrellis.data import Table
from anytrellis.datasets import load
from anytrellis.figure import CSS_DPI, length, png_dpi, png_scale, print_size

MM = CSS_DPI / 25.4  # CSS pixels a millimetre


@pytest.fixture
def plot() -> Trellis:
    return Trellis(load("cars"), wrap="origin", title="Cars").points(x="weight", y="mpg")


def test_a_length_in_css_pixels_and_its_unit() -> None:
    assert length(None, "width") == (None, None)
    assert length(640, "width") == (640.0, None)
    assert length("640px", "width") == (640.0, None)
    assert length("180mm", "width") == (pytest.approx(180 * MM), "mm")
    assert length("18 cm", "width") == (pytest.approx(180 * MM), "cm")
    assert length("7in", "width") == (672.0, "in")
    assert length("72pt", "width") == (96.0, "pt")
    assert length(".5in", "width") == (48.0, "in")
    for bad in ("180", "-5mm", "10 furlongs", True, "mm"):
        with pytest.raises(ValueError, match="180mm"):
            length(bad, "width")


def _root(svg: str) -> dict[str, str]:
    head = svg.split(">", 1)[0]
    return dict(re.findall(r'\b(width|height|viewBox)="([^"]*)"', head))


def test_an_svg_printed_at_its_length(plot: Trellis, tmp_path: Path) -> None:
    root = _root(plot.save_svg(tmp_path / "a.svg", width="180mm").read_text())
    view = [float(v) for v in root["viewBox"].split()]
    assert root["width"] == "180mm"
    assert view[2] == pytest.approx(180 * MM, abs=0.01)  # laid out at 680 CSS pixels
    assert float(root["height"].removesuffix("mm")) == pytest.approx(view[3] / MM, abs=0.05)
    tall = _root(plot.save_svg(tmp_path / "b.svg", width=600, height="3in").read_text())
    assert tall["height"] == "3in"
    assert tall["width"] == "6.25in"  # (600 px; the unit the size was given in)
    plain = _root(plot.save_svg(tmp_path / "c.svg", width=600).read_text())
    assert plain["width"] == "600"
    assert (
        print_size(plain_svg := '<svg width="96" height="48" viewBox="0 0 96 48">', None)
        == plain_svg
    )
    assert print_size(plain_svg, "in") == '<svg width="1in" height="0.5in" viewBox="0 0 96 48">'


def _png_size(png: bytes) -> tuple[int, int, float | None]:
    w, h = struct.unpack(">II", png[16:24])
    at = png.find(b"pHYs")
    dpi = struct.unpack(">I", png[at + 4 : at + 8])[0] * 0.0254 if at > 0 else None
    return w, h, dpi


def test_a_png_at_a_dpi_says_so(plot: Trellis, tmp_path: Path) -> None:
    pytest.importorskip("resvg_py")
    w, _, dpi = _png_size(plot.save_png(tmp_path / "a.png", width="180mm", dpi=300).read_bytes())
    assert abs(w - 180 / 25.4 * 300) <= 1  # 2126 pixels: 180 mm at 300 dpi
    assert dpi == pytest.approx(300, abs=0.01)
    w, _, dpi = _png_size(plot.save_png(tmp_path / "b.png", width=400).read_bytes())
    assert w == 800  # scale 2 by default, printed at its CSS size (192 dpi)
    assert dpi == pytest.approx(192, abs=0.01)
    assert png_scale(None, None) == 2.0
    assert png_scale(1.5, None) == 1.5
    assert png_scale(None, 300) == 3.125
    with pytest.raises(ValueError, match="not both"):
        plot.save_png(tmp_path / "c.png", scale=2, dpi=300)
    with pytest.raises(ValueError, match="dpi"):
        png_scale(None, 0)
    png = (tmp_path / "a.png").read_bytes()
    twice = png_dpi(png_dpi(png, 72), 600)  # one pHYs, the last
    assert twice.count(b"pHYs") == 1
    assert _png_size(twice)[2] == pytest.approx(600, abs=0.01)
    assert png_dpi(b"not a png", 300) == b"not a png"


def _page_mm(pdf: bytes) -> list[float]:
    box = re.search(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", pdf)
    assert box is not None
    return [float(v) / 72 * 25.4 for v in box.groups()]


def test_a_pdf_a_page_the_plots_size(plot: Trellis, tmp_path: Path) -> None:
    pytest.importorskip("vl_convert")
    pdf = plot.save_pdf(tmp_path / "a.pdf", width="180mm").read_bytes()
    assert pdf.startswith(b"%PDF")
    w, h = _page_mm(pdf)
    svg_h = _root(plot.save_svg(tmp_path / "a.svg", width="180mm").read_text())["height"]
    assert w == pytest.approx(180, abs=0.01)
    assert h == pytest.approx(float(svg_h.removesuffix("mm")), abs=0.05)
    w, _ = _page_mm(plot.save_pdf(tmp_path / "b.pdf", width=640).read_bytes())
    assert w == pytest.approx(640 / MM, abs=0.01)  # a CSS pixel 0.75 pt
    figure = plot | Trellis(load("cars")).hist(x="mpg")
    w, _ = _page_mm(figure.save_pdf(tmp_path / "f.pdf", width="7in").read_bytes())
    assert w == pytest.approx(177.8, abs=0.01)
    root = _root(figure.save_svg(tmp_path / "f.svg", width="7in").read_text())
    assert root["width"] == "7in"
    pytest.importorskip("resvg_py")
    f_png = figure.save_png(tmp_path / "f.png", width="7in", dpi=150).read_bytes()
    assert _png_size(f_png)[0] == 1050


def test_a_pdf_without_its_library_says_what_to_install(
    plot: Trellis, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "vl_convert", None)
    with pytest.raises(ImportError, match=r"anytrellis\[pdf\]"):
        plot.save_pdf(tmp_path / "a.pdf")


# ---- a paged plot's pages, one PDF ---------------------------------------------------------


def _stations() -> Trellis:
    from anytrellis.synthetic import sensors

    readings = sensors(stations=60, sensors=1, hours=48)
    return Trellis(readings, wrap="station", rows=2, cols=4, title="Stations")


def _pages(path: Path) -> list[tuple[str, str]]:
    """Each page's bookmark and its text."""
    from pypdf import PdfReader
    from pypdf.generic import Destination

    reader = PdfReader(path)
    outline = [o for o in reader.outline if isinstance(o, Destination)]  # (none nested)
    assert len(outline) == len(reader.outline)
    marks = [(o.title or "", reader.get_destination_page_number(o)) for o in outline]
    assert [n for _, n in marks] == list(range(len(reader.pages)))  # one a page, in order
    return [(title, page.extract_text()) for (title, _), page in zip(marks, reader.pages,
                                                                     strict=True)]  # fmt: skip


def test_a_pdf_of_every_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("vl_convert")
    pytest.importorskip("pypdf")
    import anytrellis.figure as figure

    t = _stations().line(x="time", y="temp")
    t.show_page(3)
    t.open("station 20")
    scene = t._scene()
    svgs: list[str] = []
    to_pdf = figure.svg_to_pdf
    monkeypatch.setattr(figure, "svg_to_pdf", lambda svg: svgs.append(svg) or to_pdf(svg))
    pages = _pages(t.save_pdf(tmp_path / "all.pdf", pages="all"))
    for k, svg in enumerate(svgs):  # each the image of the plot turned to that page
        turned = _stations().line(x="time", y="temp").show_page(k + 1)
        assert svg == figure.figure_svg(turned, page_label=f"Page {k + 1} of 8")
    assert [title for title, _ in pages] == [f"Page {k} of 8" for k in range(1, 9)]
    for k, (title, text) in enumerate(pages):
        assert text.startswith(f"Stations\n{title}\n")  # under the title, as the page bar
        first = 8 * k + 1  # the grid of the page (not the panel opened), its own panels
        assert f"station {first} " in text or text.endswith(f"station {first}\n↑ temp")
        assert f"station {first + 8} " not in text
    assert t.page == 3  # the plot shown stays as it is
    assert t.focused == "station 20"
    assert t._scene() is scene


def test_a_pdf_of_some_pages_by_number_or_name(tmp_path: Path) -> None:
    pytest.importorskip("vl_convert")
    pytest.importorskip("pypdf")
    from anytrellis.synthetic import sensors

    readings = sensors(stations=40, sensors=1, hours=48)
    t = Trellis(readings, wrap="station", page="region").line(x="time", y="temp")
    pdf = t.save_pdf(tmp_path / "two.pdf", pages=["south", 1], width="180mm")
    assert [title for title, _ in _pages(pdf)] == ["region: south", "region: coast"]
    w, _ = _page_mm(pdf.read_bytes())
    assert w == pytest.approx(180, abs=0.01)
    s = _stations().line(x="time", y="temp").sort_panels("max temp", descending=True)
    s.filter_panels(**{"max temp": (None, 14)})
    shown = [title for title, _ in _pages(s.save_pdf(tmp_path / "s.pdf", pages="all"))]
    assert shown == [f"Page {k} of {s.pages}" for k in range(1, s.pages + 1)]
    assert s.pages < 8  # sorted and filtered as shown


def test_a_pdf_of_pages_from_a_database_reads_a_page_at_a_time(tmp_path: Path) -> None:
    pytest.importorskip("vl_convert")
    pytest.importorskip("pypdf")
    duckdb = pytest.importorskip("duckdb")
    import polars as pl

    from anytrellis.synthetic import sensors

    readings = pl.DataFrame(sensors(stations=60, sensors=1, hours=48))
    memory = _stations().line(x="time", y="temp")
    db = Trellis(duckdb.from_arrow(readings.to_arrow()), wrap="station", rows=2, cols=4,
                 title="Stations", load="pages").line(x="time", y="temp")  # fmt: skip
    assert db._data is not None
    reads: list[int] = []
    query = Trellis._query_rows

    def counted(self: Trellis, *args: Any) -> Table:
        rows = query(self, *args)
        reads.append(rows.n)
        return rows

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Trellis, "_query_rows", counted)
        pages = _pages(db.save_pdf(tmp_path / "db.pdf", pages="all"))
    assert pages == _pages(memory.save_pdf(tmp_path / "memory.pdf", pages="all"))
    assert max(reads) <= 3 * 8 * 48  # the pages around one: never every row at once


def test_pages_that_are_not_a_paged_plots(plot: Trellis, tmp_path: Path) -> None:
    pytest.importorskip("vl_convert")
    pytest.importorskip("pypdf")
    from pypdf import PdfReader

    one = plot.save_pdf(tmp_path / "one.pdf", pages="all")  # it does not page: as shown
    assert len(PdfReader(one).pages) == 1
    with pytest.raises(ValueError, match="does not page"):
        plot.save_pdf(tmp_path / "x.pdf", pages=[1])
    t = _stations().line(x="time", y="temp")
    for bad, match in (("some", "'all' or a list"), ([0], "from 1 to 8"), ([9], "from 1 to 8"),
                       (["nowhere"], "no page 'nowhere'"), ([], "pages is empty")):  # fmt: skip
        with pytest.raises(ValueError, match=match):
            t.save_pdf(tmp_path / "x.pdf", pages=bad)


def test_pages_without_pypdf_say_what_to_install(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("vl_convert")
    t = _stations().line(x="time", y="temp")
    monkeypatch.setitem(sys.modules, "pypdf", None)
    t.save_pdf(tmp_path / "shown.pdf")  # one page: vl-convert alone
    with pytest.raises(ImportError, match=r"anytrellis\[pdf\]"):
        t.save_pdf(tmp_path / "all.pdf", pages="all")
