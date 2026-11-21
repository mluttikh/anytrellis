"""``import anytrellis.pandas``: ``df.trellis`` on pandas tables and Series, the shortcuts
as their methods (``df.trellis.line(x="year", y="pop", wrap="country")``); ``df.trellis(
kind=...)`` is ``anytrellis.shortcuts.plot``. For ``df.plot(...)`` itself:
``pd.options.plotting.backend = "anytrellis"``."""

from __future__ import annotations

import pandas as pd

from anytrellis.shortcuts import Accessor

pd.api.extensions.register_dataframe_accessor("trellis")(Accessor)
pd.api.extensions.register_series_accessor("trellis")(Accessor)
