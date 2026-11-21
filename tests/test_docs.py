"""The documentation's own checks: every page in the nav exists, every link between pages
leads to a page and a heading that exist, and every gallery plot can be made."""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "user"


def _gallery() -> Any:
    path = ROOT / "scripts" / "docs_gallery.py"
    spec = importlib.util.spec_from_file_location("docs_gallery", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["docs_gallery"] = module  # a dataclass looks its module up here
    spec.loader.exec_module(module)
    return module


def _nav_pages(items: list[Any]) -> list[str]:
    pages = []
    for item in items:
        if isinstance(item, str):
            pages.append(item)
        else:
            for value in item.values():
                pages += _nav_pages(value) if isinstance(value, list) else [value]
    return pages


def _slug(heading: str) -> str:
    """The id Python-Markdown's toc gives a heading."""
    text = re.sub(r"`|\*\*|\*", "", heading).strip().lower()
    return re.sub(r"[\s]+", "-", re.sub(r"[^\w\s-]", "", text))


def _anchors(page: Path) -> set[str]:
    text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.DOTALL)
    return {_slug(h) for h in re.findall(r"^#{1,6} (.+)$", text, flags=re.MULTILINE)}


def test_every_page_in_the_nav_exists_and_every_page_is_in_it() -> None:
    config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))
    nav = _nav_pages(config["project"]["nav"])
    assert [p for p in nav if not (DOCS / p).exists()] == []
    pages = {p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*.md")}
    assert pages - set(nav) == set()


def _links() -> list[tuple[str, str]]:
    found = []
    for page in sorted(DOCS.rglob("*.md")):
        text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.DOTALL)
        found += [(page.relative_to(DOCS).as_posix(), target)
                  for target in re.findall(r"\]\(([^)\s]+)\)", text)
                  if not re.match(r"^(https?:|mailto:|#)", target) and ".md" in target]  # fmt: skip
    found += [("gallery.md", e.guide) for e in _gallery().entries()]
    return found


@pytest.mark.parametrize(("page", "target"), _links())
def test_a_link_between_pages_leads_to_a_page_and_heading(page: str, target: str) -> None:
    path, _, anchor = target.partition("#")
    linked = ((DOCS / page).parent / path).resolve()
    assert linked.exists(), f"{page} links to {target}: no such page"
    if anchor:
        assert anchor in _anchors(linked), f"{page} links to {target}: no such heading"


def test_every_gallery_section_is_on_the_page_once() -> None:
    """docs/user/gallery.md has a heading and the cards of each section, in order."""
    text = (ROOT / "docs" / "user" / "gallery.md").read_text(encoding="utf-8")
    sections = _gallery().sections()
    assert re.findall(r"^## (.+)$", text, re.MULTILINE) == sections
    assert re.findall(r'print\(cards\("([^"]+)"\)\)', text) == sections


def test_every_gallery_plot_can_be_made() -> None:
    gallery = _gallery()
    entries = gallery.entries()
    assert len({e.slug for e in entries}) == len(entries)
    for e in entries:
        plot = e.plot()
        for p in getattr(plot, "plots", [plot]):  # a figure (Concat): each of its plots
            p._scene()
    gallery._glance()._scene()
    targets = {label["target"].split(":")[0] for label in gallery.GLANCE_LABELS}
    assert targets <= {"title", "toolbar", "strip", "panel", "yaxis", "xaxis", "legend", "badge"}


def _code_blocks(page: Path) -> list[str]:
    return re.findall(r"^```python\n(.*?)^```", page.read_text(encoding="utf-8"),
                      flags=re.MULTILINE | re.DOTALL)  # fmt: skip


def test_the_cheat_sheet_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Its blocks run in order as one script; each plot a line shows (an expression, as
    a notebook cell's last line) is drawn, so a wrong argument fails here."""
    import ast

    from anytrellis import Trellis, set_theme

    monkeypatch.chdir(tmp_path)  # it saves files
    namespace: dict[str, Any] = {}
    try:
        for block in _code_blocks(DOCS / "cheat-sheet.md"):
            for node in ast.parse(block).body:
                if isinstance(node, ast.Expr):
                    value = eval(compile(ast.Expression(node.value), "<cheat sheet>", "eval"),
                                 namespace)  # fmt: skip
                    if isinstance(value, Trellis):
                        value._scene()
                else:
                    module = ast.Module(body=[node], type_ignores=[])
                    exec(compile(module, "<cheat sheet>", "exec"), namespace)
    finally:
        set_theme()
    assert {"cars.html", "cars.svg", "cars.png"} <= {p.name for p in tmp_path.iterdir()}


def test_llms_txt_lists_every_page_and_each_page_is_plain_markdown(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("docs_llms", ROOT / "scripts" / "docs_llms.py")
    assert spec
    assert spec.loader
    llms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(llms)
    llms.write(tmp_path)

    config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))
    nav = _nav_pages(config["project"]["nav"])
    index = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert index.startswith("# anytrellis\n\n> ")
    url = config["project"]["site_url"]
    listed = re.findall(rf"^- \[[^\]]+\]\({re.escape(url)}(\S+)\)", index, flags=re.MULTILINE)
    assert sorted(listed) == sorted(nav)
    assert "## Optional" in index

    full = (tmp_path / "llms-full.txt").read_text(encoding="utf-8")
    for page in nav:
        text = (tmp_path / page).read_text(encoding="utf-8")
        assert text.startswith("# "), page
        for syntax in (r'exec="on"', "markdown-exec", r"^::: ", r"^--8<--", r"^\s*</?div"):
            assert not re.search(syntax, text, flags=re.MULTILINE), f"{page} keeps {syntax}"
        if page not in llms.OPTIONAL:
            assert text in full, page
    trellis = (tmp_path / "reference" / "trellis.md").read_text(encoding="utf-8")
    assert "### Trellis.points" in trellis
    assert "Select the marks in a range of x" in trellis  # a docstring, written out
    assert "- [Points in a wrap](how-to/marks.md#points)" in (tmp_path / "gallery.md").read_text(
        encoding="utf-8"
    )
