"""The example notebooks run, and every plot in them builds; the datasets load."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from anytrellis import Trellis
from anytrellis.datasets import NAMES, load

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "jupyter"
NOTEBOOKS = sorted(EXAMPLES.glob("*.ipynb"))


def test_there_are_examples() -> None:
    assert len(NOTEBOOKS) >= 6
    marimo = EXAMPLES.parent / "marimo"
    assert sorted(p.stem for p in marimo.glob("*.py")) == [p.stem for p in NOTEBOOKS]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_runs(path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # save_html writes here
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    namespace: dict[str, Any] = {}
    for cell in cells:
        if cell["cell_type"] == "code":
            exec(compile("".join(cell["source"]), f"{path.name}", "exec"), namespace)
    plots = [v for v in namespace.values() if isinstance(v, Trellis)]
    assert plots
    for plot in plots:
        spec, _ = plot._scene()
        assert spec["panels"]


@pytest.mark.parametrize("backend", ["polars", "pandas", "pyarrow"])
def test_datasets_load(backend: str) -> None:
    for name in NAMES:
        table = load(name, backend)  # ty: ignore[invalid-argument-type]
        assert len(table) > 0 if backend != "pyarrow" else table.num_rows > 0


def test_unknown_dataset() -> None:
    with pytest.raises(ValueError, match="no dataset"):
        load("iris")
