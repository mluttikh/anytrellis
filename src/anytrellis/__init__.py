"""anytrellis: GPU-accelerated trellis, facet and small-multiple plots for notebooks."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from anytrellis.linking import Link, link
from anytrellis.pairs import Pairs, pairs
from anytrellis.plot import Trellis

__all__ = ["Link", "Pairs", "Trellis", "link", "pairs"]
try:
    __version__ = _version("anytrellis")
except PackageNotFoundError:  # run from a source tree that is not installed
    __version__ = "0.0.0"
