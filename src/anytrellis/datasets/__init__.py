"""Small, well-known datasets for the examples: ``load("barley")``.

=================  =====  ==============================================================
name               rows   columns
=================  =====  ==============================================================
anscombe           44     dataset, x, y (Anscombe's quartet)
barley             120    site, variety, year, yield (Immer et al. 1934; Cleveland 1993)
cars               406    name, mpg, cylinders, displacement, horsepower, weight,
                          acceleration, year, origin (the classic auto-mpg data)
gapminder          693    country, region, year, pop, life_expect, fertility (1955-2005)
penguins           344    species, island, bill_length_mm, bill_depth_mm,
                          flipper_length_mm, body_mass_g, sex (Palmer penguins)
population         570    year, age, sex, people (US census, 1850-2000)
seattle_weather    1461   date, precipitation, temp_max, temp_min, wind, weather
stocks             560    symbol, date, price (monthly, 2000-2010)
=================  =====  ==============================================================

Taken from vega-datasets 2.8.0 (BSD-3-Clause; each dataset's own source is listed there),
with snake_case column names and readable categories (``gapminder.region``,
``population.sex``).
"""

from __future__ import annotations

from importlib import resources
from typing import Any, Literal

NAMES = ("anscombe", "barley", "cars", "gapminder", "penguins", "population", "seattle_weather",
         "stocks")  # fmt: skip
_DATES = {"seattle_weather": "date", "stocks": "date"}

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
