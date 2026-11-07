"""Check the built sdist and wheel before they are published:

    uv build && uv run python scripts/check_dist.py [--tag v0.1.0]

Each must hold the JavaScript bundle (it is built, not committed), the datasets with their
sources, and the licence; their version must be pyproject's (and the tag's, if given). The
wheel is then installed into a fresh virtual environment and a plot is drawn into a page.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

IN_PACKAGE = [
    "anytrellis/__init__.py",
    "anytrellis/py.typed",
    "anytrellis/static/widget.js",
    "anytrellis/static/widget.css",
    "anytrellis/static/standalone.js",
    "anytrellis/datasets/SOURCES.md",
    "anytrellis/datasets/gapminder.csv",
]

SMOKE = """
import anytrellis
from anytrellis import Trellis
from anytrellis.datasets import load

assert anytrellis.__version__ == {version!r}, anytrellis.__version__
page = Trellis(load("gapminder"), wrap="year").points(x="fertility", y="life_expect",
                                                     color="region").to_html()
assert "anytrellis-embed" in page and len(page) > 50_000, len(page)
widget = Trellis({{"x": [1.0, 2.0], "y": [3.0, 4.0]}}).points(x="x", y="y").widget
assert widget._esm and widget._css
print("installed", anytrellis.__version__, "and drew a page of", len(page), "characters")
"""


def fail(message: str) -> None:
    print(f"FAIL {message}", flush=True)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--tag", help="the release's git tag: v<version>")
    args = parser.parse_args()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    if args.tag is not None and args.tag != f"v{version}":
        fail(f"tag {args.tag} is not v{version}, pyproject's version")
    wheels = sorted(args.dist.glob(f"anytrellis-{version}-*.whl"))
    sdists = sorted(args.dist.glob(f"anytrellis-{version}.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        fail(f"expected one wheel and one sdist of {version} in {args.dist}: {wheels + sdists}")
    wheel, sdist = wheels[0], sdists[0]

    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
        metadata = z.read(f"anytrellis-{version}.dist-info/METADATA").decode()
    missing = [n for n in IN_PACKAGE if n not in names]
    licences = [n for n in names if "/licenses/" in n]
    if missing:
        fail(f"{wheel.name} lacks {missing}")
    if not any(n.endswith("LICENSE") for n in licences):
        fail(f"{wheel.name} has no LICENSE: {licences}")
    if "Requires-Python: >=3.12" not in metadata or "Project-URL" not in metadata:
        fail(f"{wheel.name}'s metadata lacks Requires-Python or Project-URL")
    print(f"ok   {wheel.name}: {len(names)} files, the bundle, datasets and licences", flush=True)

    with tarfile.open(sdist) as t:
        names = {n.split("/", 1)[1] for n in t.getnames() if "/" in n}
    wanted = ["pyproject.toml", "README.md", "LICENSE", "CHANGELOG.md", "js/package.json",
              "js/package-lock.json"] + [f"src/{n}" for n in IN_PACKAGE]  # fmt: skip
    missing = [n for n in wanted if n not in names]
    if missing:
        fail(f"{sdist.name} lacks {missing}")
    if any("node_modules" in n for n in names):
        fail(f"{sdist.name} holds node_modules")
    print(f"ok   {sdist.name}: {len(names)} files, the built bundle and the sources", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        subprocess.run(["uv", "venv", "-q", "--python", sys.executable, str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(["uv", "pip", "install", "-q", "--python", str(python), str(wheel),
                        "polars"], check=True)  # fmt: skip
        script = Path(tmp) / "smoke.py"
        script.write_text(SMOKE.format(version=version), encoding="utf-8")
        subprocess.run([str(python), str(script)], check=True, cwd=tmp)
    print("ok   the wheel installs and draws", flush=True)


if __name__ == "__main__":
    main()
