"""``import anytrellis.polars``: ``df.trellis`` on Polars DataFrames and LazyFrames, the
shortcuts as their methods (``df.trellis.line(x="year", y="pop", wrap="country")``);
``df.trellis(kind=...)`` is ``anytrellis.shortcuts.plot``. (Polars' own ``df.plot`` draws
with Altair.)"""

from __future__ import annotations

import polars as pl

from anytrellis.shortcuts import Accessor

pl.api.register_dataframe_namespace("trellis")(Accessor)
pl.api.register_lazyframe_namespace("trellis")(Accessor)
