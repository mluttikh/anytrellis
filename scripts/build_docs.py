"""Build the user documentation (docs/user/ -> site/), or serve it while writing.

    uv run python scripts/build_docs.py          # build into site/, strict: warnings fail
    uv run python scripts/build_docs.py serve    # preview at http://localhost:8000

The example plots in the pages are live: ``Trellis._embed_html`` puts each plot's data in
the page, and the JavaScript bundle (``standalone.js``) draws it. Build the bundle first
(cd js && npm run build); this script copies it into the documentation, and draws the
gallery's pictures (scripts/docs_gallery.py) when they are missing or ``--gallery`` asks.

A build fails on warnings, also on those Zensical's strict mode does not count: an example
that raises (markdown-exec) and a docstring the API reference cannot read (griffe). It also
fails when a page weighs more than ``PAGE_BUDGET`` gzipped (the plots' data is in the
page), or when a public name (a method, a parameter of ``Trellis``) is in no guide: the
reference lists everything, but a reader finds a feature through the guides.

The build runs in Python's UTF-8 mode (as ``python -X utf8``), it and every process it
starts: the pages and the code are UTF-8 (°, ×, µ), and on Windows Python otherwise reads
and writes text in the locale's encoding (cp1252), also in tools we don't control (the
API reference formats signatures through a subprocess).
"""

from __future__ import annotations

import gzip
import inspect
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "anytrellis" / "static"
DOCS = ROOT / "docs" / "user"
ASSETS = DOCS / "assets"
SITE = ROOT / "site"
PAGE_BUDGET = 3_000_000  # bytes, gzipped, as a server sends it


def copy_bundle() -> None:
    target = ASSETS / "anytrellis"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("standalone.js", "widget.css"):
        source = STATIC / name
        if not source.is_file():
            sys.exit(f"{source} is missing; build the JavaScript first: cd js && npm run build")
        shutil.copyfile(source, target / name)


def gallery(force: bool) -> None:
    """The gallery's pictures: drawn by a browser, so only when missing or asked for."""
    if not force and (ASSETS / "gallery").is_dir() and any((ASSETS / "gallery").glob("*.png")):
        return
    script = ROOT / "scripts" / "docs_gallery.py"
    if subprocess.run([sys.executable, str(script)], cwd=ROOT, check=False).returncode:
        sys.exit("the gallery's pictures could not be drawn (scripts/docs_gallery.py)")


class Warnings(logging.Handler):
    """Collects the warnings of the plugins that run examples and read docstrings."""

    SOURCES = ("markdown_exec", "griffe", "mkdocstrings", "mkdocs")

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.seen: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.split(".")[0] in self.SOURCES:
            self.seen.append(f"{record.name}: {record.getMessage()}")


def build() -> int:
    import zensical

    warnings = Warnings()
    logging.getLogger().addHandler(warnings)
    os.chdir(ROOT)
    try:
        zensical.build(str(ROOT / "zensical.toml"), {"clean": True, "strict": True})
    except RuntimeError as err:  # strict mode: a warning of Zensical itself
        print(err, file=sys.stderr)
        return 1
    for line in warnings.seen:
        print(f"warning: {line}", file=sys.stderr)
    return 1 if warnings.seen else 0


def check() -> list[str]:
    """The pages' weight, and the public names no guide uses."""
    problems = []
    for page in sorted(SITE.rglob("*.html")):
        size = len(gzip.compress(page.read_bytes()))
        if size > PAGE_BUDGET:
            problems.append(f"{page.relative_to(SITE)} weighs {size / 1e6:.1f} MB gzipped")

    from anytrellis import Trellis, pairs, synthetic

    guides = "\n".join(p.read_text(encoding="utf-8") for p in DOCS.rglob("*.md")
                       if "reference" not in p.relative_to(DOCS).parts)  # fmt: skip
    methods = [f"Trellis.{n}" for n in dir(Trellis) if not n.startswith("_")]
    methods += [f"Link.{n}" for n in ("unlink", "clear")]
    methods += [f"synthetic.{n}" for n, f in vars(synthetic).items()
                if inspect.isfunction(f) and f.__module__ == synthetic.__name__
                and not n.startswith("_")]  # fmt: skip
    for name in methods:
        short = name.split(".")[1]
        if not re.search(rf"\.{short}\b|\b{short}\(", guides):
            problems.append(f"{name} is in no guide")
    problems += [f"Trellis({p}=...) is in no guide" for p in inspect.signature(Trellis).parameters
                 if p != "data" and not re.search(rf"\b{p}=", guides)]  # fmt: skip
    problems += [f"pairs({p}=...) is in no guide" for p in inspect.signature(pairs).parameters
                 if p != "data" and not re.search(rf"\b{p}=", guides)]  # fmt: skip
    return problems


def main() -> None:
    if not sys.flags.utf8_mode:
        # again in UTF-8 mode; PYTHONUTF8 reaches the processes it starts too
        env = {**os.environ, "PYTHONUTF8": "1"}
        sys.exit(subprocess.run([sys.executable, *sys.argv], env=env, check=False).returncode)
    args = sys.argv[1:]
    copy_bundle()
    gallery(force="--gallery" in args)
    if "serve" in args:
        sys.exit(subprocess.run(["zensical", "serve"], cwd=ROOT, check=False).returncode)
    if code := build():
        sys.exit(code)
    for problem in check():
        print(f"check: {problem}", file=sys.stderr)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
