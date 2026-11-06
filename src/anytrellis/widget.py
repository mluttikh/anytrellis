"""The widget that shows a plot in a notebook (``plot.widget``): a spec plus binary
buffers, drawn in the browser. This module is the protocol between them.

* ``_spec`` (synced): a small JSON description of the plot. Layers refer to buffers by
  content id, with dtype and count.
* The browser asks for buffers it does not have: ``{"type": "need", "ids": [...]}``, and
  Python answers with ``{"type": "put", "id", "chunk", "chunks", "offset", "byteLength"}``
  messages, each with one binary chunk of at most ``CHUNK_BYTES``; an id Python does not
  have is answered ``{"type": "missing", "id"}``.
* ``open_panel`` (synced both ways): the name of the panel shown alone, or None.
* ``{"type": "tooltip", "request", "layer", "index"}`` asks for the tooltip columns of one
  instance of a layer; Python answers ``{"type": "answer", "request", "rows"}``.

Bulk data never goes into synced traits, so it is not saved into the notebook and only sent
to views that ask for it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import anywidget
import traitlets

if TYPE_CHECKING:
    from anytrellis.plot import Trellis

CHUNK_BYTES = 4 * 1024 * 1024

_STATIC = Path(__file__).parent / "static"


class TrellisWidget(anywidget.AnyWidget):
    """The widget that shows a plot: ``plot.widget``."""

    _esm = _STATIC / "widget.js"
    _css = _STATIC / "widget.css"

    _spec = traitlets.Dict().tag(sync=True)
    renderer = traitlets.Unicode("auto").tag(sync=True)
    #: The opened panel's name (``Trellis.open``, or a double-click in the browser), or None.
    open_panel = traitlets.Unicode(None, allow_none=True).tag(sync=True)

    def __init__(self, plot: Trellis, state: dict[str, Any]) -> None:
        self._plot = plot
        super().__init__(**state)
        self.on_msg(self._on_msg)
        self.observe(self._on_focus, names="open_panel")

    def _on_focus(self, change: dict[str, Any]) -> None:
        self._plot._focus = change["new"]  # opened in the browser: save_html keeps it

    def _on_msg(self, _widget: Any, content: dict[str, Any], buffers: Any) -> None:
        kind = content.get("type")
        if kind == "need":
            for buffer_id in content.get("ids", []):
                self._send_buffer(str(buffer_id))
        elif kind == "tooltip":
            answer: dict[str, Any] = {"type": "answer", "request": content.get("request")}
            try:
                answer["rows"] = self._plot._tooltip(int(content["layer"]), int(content["index"]))
            except Exception as err:  # the browser shows what it has; the kernel carries on
                answer["error"] = str(err)
            self.send(answer)

    def _send_buffer(self, buffer_id: str) -> None:
        _, buffers = self._plot._scene()
        data = buffers.data.get(buffer_id)
        if data is None:
            self.send({"type": "missing", "id": buffer_id})
            return
        chunks = max(1, -(-len(data) // CHUNK_BYTES))
        for i in range(chunks):
            part = data[i * CHUNK_BYTES : (i + 1) * CHUNK_BYTES]
            self.send(
                {
                    "type": "put",
                    "id": buffer_id,
                    "chunk": i,
                    "chunks": chunks,
                    "offset": i * CHUNK_BYTES,
                    "byteLength": len(data),
                },
                buffers=[part],
            )

    def __repr__(self) -> str:
        return f"TrellisWidget of {self._plot!r}"
