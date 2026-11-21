"""anytrellis: GPU-accelerated trellis, facet and small-multiple plots for notebooks."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from anytrellis.compose import Concat, concat
from anytrellis.linking import Link, link
from anytrellis.pairs import Pairs, pairs
from anytrellis.plot import Trellis
from anytrellis.theme import Theme, get_theme, set_theme

__all__ = [
    "Concat",
    "Link",
    "Pairs",
    "Theme",
    "Trellis",
    "concat",
    "get_theme",
    "link",
    "pairs",
    "set_theme",
]
try:
    __version__ = _version("anytrellis")
except PackageNotFoundError:  # run from a source tree that is not installed
    __version__ = "0.0.0"
