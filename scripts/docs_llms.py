"""The documentation for language models and coding assistants (https://llmstxt.org).

    uv run python scripts/docs_llms.py site    # into site/, after the site is built

scripts/build_docs.py writes them after each build:

- ``llms.txt``: what anytrellis is, and a link to each page with what it holds;
- ``<page>.md`` beside each ``<page>.html``: the page as Markdown, the examples' code
  without their output, and the API reference written out from the docstrings;
- ``llms-full.txt``: every page in one file, in the order of the nav.

Everything comes from docs/user/ and the docstrings, so it never falls behind the site.
tests/test_docs.py checks that no page keeps Zensical's own syntax.
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "user"

SUMMARY = """\
> Trellis plots (small multiples, facets) for Jupyter and marimo notebooks, drawn on the
> GPU. One class, `Trellis`, draws the same layers in a panel per level of the facet
> columns, on shared scales, and stays smooth with hundreds of panels and millions of
> marks.

- Install: `pip install anytrellis` (Python 3.12 or newer). Import: `from anytrellis
  import Trellis`.
- A plot: `Trellis(table, wrap="column")` (or `row=`, `col=` for a grid), then a method
  per layer, `.points(x=, y=, color=)`, `.line()`, `.bars()`, `.hist()`, `.box()`,
  `.smooth()`, ...; each returns the plot, so calls chain. The last line of a notebook
  cell shows it.
- Tables: Polars, pandas, PyArrow, DuckDB, Ibis or a dict of arrays. A lazy table is
  read in one query; `load="pages"` reads only the panels on the page shown.
- Selections reach Python: brush marks in the browser (or `plot.select()`), and
  `plot.selected()` returns the rows.
- Images and pages without a browser: `save_svg`, `save_png`, `save_html`.
- The cheat sheet has the whole API as code that runs. Each page below is also Markdown
  at the same address with `.md` for `.html`; `llms-full.txt` holds them all in one file.
"""

# pages a reader can skip (the "Optional" section of llms.txt)
OPTIONAL = {"reference/changelog.md"}


def config() -> dict[str, Any]:
    return tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))["project"]


def sections() -> list[tuple[str, list[str]]]:
    """The nav as (section, pages): the top level's single pages first, as "Start here"."""
    start: list[str] = []
    found: list[tuple[str, list[str]]] = [("Start here", start)]

    def pages(items: list[Any]) -> list[str]:
        out = []
        for item in items:
            values = [item] if isinstance(item, str) else list(item.values())
            for value in values:
                out += pages(value) if isinstance(value, list) else [value]
        return out

    for item in config()["nav"]:
        ((name, value),) = item.items()
        if isinstance(value, list):
            found.append((name, pages(value)))
        else:
            start.append(value)
    return found


# a page as Markdown


def _snippet(spec: str) -> str:
    """``--8<-- "path:start:end"`` (pymdownx.snippets): the file's lines, from 1."""
    path, *span = spec.split(":")
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    start = int(span[0]) - 1 if span and span[0] else 0
    end = int(span[1]) if len(span) > 1 and span[1] else len(lines)
    return "\n".join(lines[start:end])


def _annotation(value: Any) -> str:
    return value if isinstance(value, str) else inspect.formatannotation(value)


def _signature(name: str, obj: Any) -> str:
    """``name(arg: type = default, *, ...) -> type``, the annotations as written."""
    sig = inspect.signature(obj)
    parts: list[str] = []
    star = False
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind is p.KEYWORD_ONLY and not star:
            parts.append("*")
            star = True
        prefix = {p.VAR_POSITIONAL: "*", p.VAR_KEYWORD: "**"}.get(p.kind, "")
        star |= p.kind is p.VAR_POSITIONAL
        text = prefix + p.name
        if p.annotation is not p.empty:
            text += f": {_annotation(p.annotation)}"
        if p.default is not p.empty:
            text += f" = {p.default!r}"
        parts.append(text)
    ret = sig.return_annotation
    tail = "" if ret is sig.empty or ret in ("None", None) else f" -> {_annotation(ret)}"
    one = f"{name}({', '.join(parts)}){tail}"
    if len(one) <= 88:
        return one
    return f"{name}(\n" + "".join(f"    {p},\n" for p in parts) + f"){tail}"


def _entry(name: str, obj: Any, level: int) -> str:
    """One object's heading, signature and docstring."""
    out = [f"{'#' * level} {name}", ""]
    if isinstance(obj, property):
        out += ["(a property)", ""]
        obj = obj.fget
    elif callable(obj):
        out += ["```python", _signature(name.rsplit(".", 1)[-1], obj), "```", ""]
    out.append(inspect.getdoc(obj) or "")
    return "\n".join(out).rstrip()


def api(target: str, options: dict[str, Any]) -> str:
    """``::: anytrellis.Name`` (mkdocstrings, as zensical.toml sets it): the object and
    its public members, in source order."""
    module_name, _, attr = target.rpartition(".")
    obj = getattr(importlib.import_module(module_name), attr, None)  # pairs: the function
    if obj is None:
        obj = importlib.import_module(target)
    root = options.get("show_root_heading", True)
    level = 2 if root else 1
    out: list[str] = []
    if inspect.ismodule(obj):
        if root:
            out.append(f"## {target}")
        out.append(inspect.getdoc(obj) or "")
        members = [(n, f) for n, f in vars(obj).items()
                   if inspect.isfunction(f) and f.__module__ == obj.__name__
                   and not n.startswith("_")]  # fmt: skip
        out += [_entry(n, f, level + 1) for n, f in members]
        return "\n\n".join(out)
    out.append(_entry(attr, obj, 2) if root else inspect.getdoc(obj) or "")
    if inspect.isclass(obj):
        wanted = options.get("members")
        names = wanted or [n for n in vars(obj) if not n.startswith("_")]
        for n in names:
            member = inspect.getattr_static(obj, n)
            if isinstance(member, (staticmethod, classmethod)):
                member = member.__func__
            if callable(member) or isinstance(member, property):
                out.append(_entry(f"{attr}.{n}", member, level + 1))
    return "\n\n".join(out)


def _options(lines: list[str]) -> dict[str, Any]:
    """The few mkdocstrings options the pages use: ``members:`` and a boolean or two."""
    options: dict[str, Any] = {}
    key = None
    for line in lines:
        item = re.match(r"\s*- (\S+)", line)
        if item and key:
            options.setdefault(key, []).append(item.group(1))
        elif m := re.match(r"\s*(\w+):\s*(\S*)", line):
            key, value = m.groups()
            if key != "options" and value:
                options[key] = {"true": True, "false": False}.get(value, value)
    return options


def markdown(page: str) -> str:
    """A page of docs/user/ as plain Markdown."""
    lines = (DOCS / page).read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if m := re.match(r'--8<-- "(.+)"$', line):
            out.append(_snippet(m.group(1)))
        elif m := re.match(r"::: (\S+)$", line):
            block = []
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                block.append(lines[i])
                i += 1
            out += [api(m.group(1), _options(block)), ""]
        elif re.match(r"```python .*exec=", line):
            end = lines.index("```", i)
            code = [c for c in lines[i:end] if not c.endswith("# markdown-exec: hide")]
            i = end + 1
            if "source=" in line:  # its code is shown; otherwise only its output was
                out += ["```python", *code, "```"]
            elif page == "gallery.md":
                out += _gallery()
            elif out and not out[-1].strip():
                out.pop()  # the block's blank line before
        elif re.fullmatch(r"</?div( [^>]*)?>", line.strip()):
            continue
        else:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def _gallery() -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from docs_gallery import entries

    return [f"- [{e.title}]({e.guide})" for e in entries()]


# llms.txt


def _plain(text: str) -> str:
    """Markdown links as their text, on one line."""
    return " ".join(re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text).split())


def describe(page: str, text: str) -> tuple[str, str]:
    """A page's title (its first heading) and what it holds: its first paragraph of
    text (on an API page, the first object's docstring's)."""
    title = re.search(r"^# (.+)$", text, flags=re.MULTILINE)
    name = title.group(1).strip() if title else page
    prose = re.sub(r"^```.*?^```", "", text, flags=re.MULTILINE | re.DOTALL)
    for part in re.split(r"\n\s*\n", prose):
        paragraph = part.strip()
        if paragraph and not paragraph.startswith(("#", "!", "<", "|", "-", "(")):
            return name, _plain(paragraph)
    return name, ""


def write(site: Path) -> list[Path]:
    """llms.txt, llms-full.txt and a .md beside each page, into the built site."""
    project = config()
    url = project["site_url"].rstrip("/") + "/"
    index = [f"# {project['site_name']}", "", SUMMARY]
    full = [f"# {project['site_name']}", "", SUMMARY]
    optional = []
    written = []
    for section, pages in sections():
        index += [f"## {section}", ""]
        for page in pages:
            text = markdown(page)
            target = site / page
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            written.append(target)
            name, what = describe(page, text)
            line = f"- [{name}]({url}{page})" + (f": {what}" if what else "")
            if page in OPTIONAL:
                optional.append(line)
            else:
                index.append(line)
                full += ["---", "", f"Page: {url}{page.removesuffix('.md')}.html", "", text]
        index.append("")
    index += ["## Optional", "", *optional, ""]
    for name, lines in (("llms.txt", index), ("llms-full.txt", full)):
        path = site / name
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "site")
    print(f"{len(write(out))} files written into {out}")
