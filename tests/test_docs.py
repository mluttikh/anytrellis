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


def test_every_gallery_plot_can_be_made() -> None:
    gallery = _gallery()
    entries = gallery.entries()
    assert len({e.slug for e in entries}) == len(entries)
    for e in entries:
        e.plot()._scene()
    gallery._glance()._scene()
    targets = {label["target"].split(":")[0] for label in gallery.GLANCE_LABELS}
    assert targets <= {"title", "toolbar", "strip", "panel", "yaxis", "xaxis", "legend", "badge"}
