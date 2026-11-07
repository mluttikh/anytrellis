"""Small, well-known datasets for the examples: ``load("barley")``.

name | rows | columns
--- | --- | ---
anscombe | 44 | dataset, x, y
barley | 120 | site, variety, year, yield
cars | 406 | name, mpg, cylinders, displacement, horsepower, weight, acceleration, year, origin
gapminder | 693 | country, region, year, pop, life_expect, fertility
penguins | 344 | species, island, bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, sex
seattle_weather | 1461 | date, precipitation, temp_max, temp_min, wind, weather

``anscombe`` is Anscombe's quartet; ``barley`` is Immer et al. (1934), made famous by
Cleveland (1993); ``cars`` is the classic auto-mpg data; ``gapminder`` runs from 1955 to
2005; ``penguins`` are the Palmer penguins.

``cars`` is the UCI Machine Learning Repository's Auto MPG (CC BY 4.0); the others are
taken from vega-datasets 2.8.0, with snake_case column names and readable categories
(``gapminder.region``). Each keeps its source's licence: see ``SOURCES.md`` here. The
gapminder data is based on free material from GAPMINDER.ORG, CC-BY LICENSE.
"""

from __future__ import annotations

from importlib import resources
from typing import Any, Literal

NAMES = ("anscombe", "barley", "cars", "gapminder", "penguins", "seattle_weather")
_DATES = {"seattle_weather": "date"}

Backend = Literal["polars", "pandas", "pyarrow"]


def load(name: str, backend: Backend | None = None) -> Any:
    """Dataset ``name`` as a table of ``backend`` (default: Polars, else pandas, else
    PyArrow, whichever is installed)."""
    import narwhals as nw

    if name not in NAMES:
        raise ValueError(f"no dataset {name!r}; there are {', '.join(NAMES)}")
    path = resources.files(__name__) / f"{name}.csv"
    with resources.as_file(path) as file:
        frame = nw.read_csv(str(file), backend=backend or _backend())
    column = _DATES.get(name)
    if column is not None and frame.schema[column] == nw.String:  # PyArrow parses dates itself
        frame = frame.with_columns(nw.col(column).str.to_datetime("%Y-%m-%d").cast(nw.Date))
    return frame.to_native()


def _backend() -> Backend:
    import importlib.util

    for backend in ("polars", "pandas", "pyarrow"):
        if importlib.util.find_spec(backend) is not None:
            return backend
    raise ModuleNotFoundError("load() needs Polars, pandas or PyArrow: pip install polars")
