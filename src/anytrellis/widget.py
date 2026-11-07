"""The widget that shows a plot in a notebook (``plot.widget``): a spec plus binary
buffers, drawn in the browser. This module is the protocol between them.

* ``_spec`` (synced): a small JSON description of the plot. Layers refer to buffers by
  content id, with dtype and count.
* The browser asks for buffers it does not have: ``{"type": "need", "ids": [...]}``, and
  Python answers with ``{"type": "put", "id", "chunk", "chunks", "offset", "byteLength"}``
  messages, each with one binary chunk of at most ``CHUNK_BYTES``; an id Python does not
  have is answered ``{"type": "missing", "id"}``.
* ``open_panel`` (synced both ways): the name of the panel shown alone, or None.
* ``selection`` (synced both ways): the brush, ``{"x": [lo, hi] | None, "y": ...}`` in axis
  units relative to the spec's origins, or None (the browser sends it on release).
* ``_live`` (synced): send the brush while it is dragged, about 20 times a second (a
  linked plot), not only on release.
* ``{"type": "highlight", "layers": [...] | None, "selected", "total"}`` (Python to the
  browser, a linked plot): what another plot's selection highlights here. Per spec layer
  ``{"mask": i, "count": n}`` (a bit per instance, in binary buffer ``i``, the first in
  the lowest bit), ``{"fraction": i, "count": n}`` (float32: a histogram bar's selected
  share) or None (drawn as it is); ``layers`` None: nothing.
  The browser asks for it with ``{"type": "ready"}`` when a view starts, and sends
  ``{"type": "clear"}`` for a click that clears the link's selection.
* ``{"type": "tooltip", "request", "layer", "index", "of"}`` asks for the tooltip columns of
  one instance of a layer (``of``: the id of its coords as shown); Python answers
  ``{"type": "answer", "request", "rows"}``.
* ``{"type": "save", "request", "name"}`` with the file's bytes as its buffer: an image from
  the Export menu, saved in Python's working folder (the notebook's, usually) without
  overwriting; Python answers ``{"type": "answer", "request", "path"}``.
* ``{"type": "view", "width", "x": [[group, [lo, hi]], ...], "y": ..., "panels": [[index,
  width, height], ...]}``: the plot's width, each scale group's range as shown (relative to
  the origins) and the panels shown (their size in CSS px), sent a moment after they
  change; ``Trellis.save_png`` and ``save_svg`` draw that view.
* ``{"type": "detail", "layers": [{"index", "of", "layer"}, ...]}`` (Python to the browser):
  layers of many rows (``anytrellis.detail``) for the view reported, in more detail where it
  is zoomed in: spec layer ``index`` is drawn as ``layer`` instead, while the spec's has
  coords ``of``. Its buffers come as any others do. A ``highlight``'s layer has the coords
  it is for (``of``).
* A paged wrap's layers hold the data of some panels only: those of the page shown, the
  pages either side of it and the opened panel, listed in the layer's ``panels``. When
  ``paging`` or ``open_panel`` changes, Python sends a ``detail`` with the layers for the
  new panels; until it comes, the browser says the page is loading. A page saved with
  ``save_html`` has every panel's data, and its layers no ``panels``.

Bulk data never goes into synced traits, so it is not saved into the notebook and only sent
to views that ask for it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import anywidget
import traitlets

from anytrellis.pages import Paging

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
    #: The selection's brush (``Trellis.select``, or one drawn in the browser), or None.
    selection = traitlets.Dict(None, allow_none=True).tag(sync=True)
    #: The page, sort and filters of a paged wrap (``Trellis.show_page``, ``sort_panels``,
    #: ``filter_panels``, or the reader in the browser).
    paging = traitlets.Dict({}).tag(sync=True)
    #: Send the brush while it is dragged, not only on release (a linked plot).
    _live = traitlets.Bool(False).tag(sync=True)

    def __init__(self, plot: Trellis, state: dict[str, Any]) -> None:
        self._plot = plot
        super().__init__(**state)
        self.on_msg(self._on_msg)
        self.observe(self._on_focus, names="open_panel")
        self.observe(self._on_selection, names="selection")
        self.observe(self._on_paging, names="paging")

    def _on_selection(self, change: dict[str, Any]) -> None:
        self._plot._selection = change["new"]  # drawn in the browser: save_html keeps it
        self._plot._selection_changed()

    def _on_paging(self, change: dict[str, Any]) -> None:
        self._plot._paging = Paging(**change["new"])  # turned in the browser: save_html keeps it
        self._plot._send_detail()  # the data of the panels around the page shown

    def _on_focus(self, change: dict[str, Any]) -> None:
        self._plot._focus = change["new"]  # opened in the browser: save_html keeps it
        self._plot._send_detail()  # an opened panel of another page: its data

    def _on_msg(self, _widget: Any, content: dict[str, Any], buffers: Any) -> None:
        kind = content.get("type")
        if kind == "need":
            for buffer_id in content.get("ids", []):
                self._send_buffer(str(buffer_id))
        elif kind == "tooltip":
            answer: dict[str, Any] = {"type": "answer", "request": content.get("request")}
            try:
                of = content.get("of")
                answer["rows"] = self._plot._tooltip(int(content["layer"]), int(content["index"]),
                                                     None if of is None else str(of))  # fmt: skip
            except Exception as err:  # the browser shows what it has; the kernel carries on
                answer["error"] = str(err)
            self.send(answer)
        elif kind == "save":  # the Export menu's "Save ... next to the notebook"
            answer = {"type": "answer", "request": content.get("request")}
            try:
                answer["path"] = str(save_export(str(content.get("name", "")), buffers))
            except Exception as err:  # the browser says what went wrong
                answer["error"] = str(err)
            self.send(answer)
        elif kind == "view":  # what the browser shows: save_png and save_svg draw it
            self._plot._view = {k: content.get(k) for k in ("width", "x", "y", "panels")}
            self._plot._send_detail()  # and its layers in more detail, zoomed in
        elif kind == "ready":  # a view started: what a link highlights in it
            self._plot._send_highlight()
        elif kind == "clear":  # a click in a linked plot with no brush of its own
            self._plot._clear_link()

    def _send_buffer(self, buffer_id: str) -> None:
        _, buffers = self._plot._scene()
        data = buffers.data.get(buffer_id)
        if data is None:  # a layer in detail
            data = self._plot._detail_buffers.data.get(buffer_id)
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


def save_export(name: str, buffers: Any) -> Path:
    """Write an image from the Export menu to the working folder, without overwriting:
    ``plot.png``, then ``plot-2.png``, ... Only a plain ``.png`` or ``.svg`` file name."""
    if not buffers:
        raise ValueError("no image data")
    path = Path(Path(name).name or "anytrellis.png")  # a file name, no folders
    if path.suffix.lower() not in (".png", ".svg"):
        path = path.with_suffix(".png")
    target, n = path, 1
    while target.exists():
        n += 1
        target = path.with_name(f"{path.stem}-{n}{path.suffix}")
    target.write_bytes(bytes(buffers[0]))
    return target.resolve()
