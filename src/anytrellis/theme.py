"""How a plot looks: a dozen settings, of which the named themes are presets.

```python
import anytrellis as at

Trellis(cars, wrap="origin", theme="framed")                      # a preset
Trellis(cars, wrap="origin", theme=at.Theme("minimal", frame=True, panel_gap=12))
at.set_theme("framed", palette="tab10")                           # every plot from now on
at.set_theme(context="talk")                                      # bigger, for slides
```

The browser (``js/src/core/look.ts``) and the images drawn in Python (``figure.py``) read
the same settings, sent in the spec.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields, replace
from typing import Any, Literal

from anytrellis.styling import palette_of

Grid = Literal["auto", "x", "y", "both", "none"]
Lines = Literal["x", "y", "both", "none"]
Context = Literal["paper", "notebook", "talk", "poster"]

CONTEXTS: dict[str, float] = {"paper": 0.8, "notebook": 1.0, "talk": 1.5, "poster": 2.0}
"""How much each context scales text, line widths and point sizes (as seaborn's do)."""
FONT_SIZE = 12.0
"""The text's size (px) in the notebook context, and with ``font_size="auto"`` the size
it steps from: 11 px in panels under ``NARROW`` px wide, 13 px in an opened panel."""
NARROW = 160

PRESETS: dict[str, dict[str, Any]] = {
    "minimal": {
        "panel_fill": False, "frame": False, "grid": "auto", "grid_opacity": 0.1,
        "axis_lines": "x", "strip_fill": False, "strip_align": "left", "strip_bold": True,
        "y_title": "top", "x_title": "center", "row_labels": "level", "panel_gap": 6,
        "palette": "petroff10", "font_size": "auto", "context": "notebook",
    },
    "framed": {
        "panel_fill": False, "frame": True, "grid": "auto", "grid_opacity": 0.1,
        "axis_lines": "none", "strip_fill": False, "strip_align": "center",
        "strip_bold": False, "y_title": "top", "x_title": "end", "row_labels": "level",
        "panel_gap": 10, "palette": "observable10", "font_size": "auto",
        "context": "notebook",
    },
    "classic": {
        "panel_fill": True, "frame": False, "grid": "both", "grid_opacity": 0.12,
        "axis_lines": "both", "strip_fill": True, "strip_align": "center",
        "strip_bold": False, "y_title": "side", "x_title": "center", "row_labels": "side",
        "panel_gap": 6, "palette": "tab10", "font_size": 12, "context": "notebook",
    },
}  # fmt: skip
"""The named themes. minimal (the default): nothing behind the data but a faint grid,
strips as titles at the left. framed (after Observable Plot): a thin frame around each
panel and more room between them, so each facet reads as one, strips centred over them.
classic (anytrellis before 0.6): grey panels and strips, a full grid, titles on their side."""

_CHOICES: dict[str, tuple[Any, ...]] = {
    "grid": ("auto", "x", "y", "both", "none"),
    "axis_lines": ("x", "y", "both", "none"),
    "strip_align": ("left", "center"),
    "y_title": ("top", "side"),
    "x_title": ("center", "end"),
    "row_labels": ("level", "side"),
    "context": tuple(CONTEXTS),
}


@dataclass(frozen=True)
class Theme:
    """How a plot looks: a named theme's settings, with any of them changed.

    ```python
    at.Theme("minimal", frame=True, panel_gap=12)
    at.Theme("classic", palette="petroff10").replace(grid="y")
    ```

    Args:
        base: The theme it starts from: ``"minimal"``, ``"framed"`` or ``"classic"``.
        panel_fill: Fill each panel with a light grey.
        frame: A thin line around each panel.
        grid: Which way grid lines run: ``"auto"`` (across y, and across x too for points
            or when y is a category axis), ``"x"``, ``"y"``, ``"both"`` or ``"none"``.
        grid_opacity: The grid: the text colour at this opacity, 0 to 1.
        axis_lines: Which axes draw a line along the panels' edge: ``"x"``, ``"y"``,
            ``"both"`` or ``"none"``.
        strip_fill: Strips filled grey; else the label alone, as a title.
        strip_align: A strip's label at the ``"left"`` or in the ``"center"``.
        strip_bold: Strip labels semibold.
        y_title: The y title level over the plot (``"top"``: ``↑ temp``) or on its side
            at its left (``"side"``).
        x_title: The x title centred under the plot (``"center"``) or at its right end
            (``"end"``: ``weight →``).
        row_labels: A grid's row labels level at the right, as wide as they need
            (``"level"``), or on their side in a strip (``"side"``).
        panel_gap: Pixels between panels.
        palette: Category colours: a name (``"petroff10"``, ``"observable10"``,
            ``"tab10"``, ...) or a list of colours. ``Trellis(palette=)`` overrides it.
        font_size: The text's size in pixels, or ``"auto"``: 12, stepping to 11 in
            panels under 160 px wide and to 13 in an opened panel (minimal and framed;
            classic: 12). The title is 1.15 times as big.
        context: Where the plot is shown, scaling the text, line widths and point
            sizes together: ``"paper"`` (0.8), ``"notebook"`` (1), ``"talk"`` (1.5) or
            ``"poster"`` (2).
    """

    base: str = "minimal"
    panel_fill: bool | None = None
    frame: bool | None = None
    grid: Grid | None = None
    grid_opacity: float | None = None
    axis_lines: Lines | None = None
    strip_fill: bool | None = None
    strip_align: Literal["left", "center"] | None = None
    strip_bold: bool | None = None
    y_title: Literal["top", "side"] | None = None
    x_title: Literal["center", "end"] | None = None
    row_labels: Literal["level", "side"] | None = None
    panel_gap: int | None = None
    palette: str | Sequence[str] | None = None
    font_size: float | Literal["auto"] | None = None
    context: Context | None = None

    def __post_init__(self) -> None:
        if self.base not in PRESETS:
            raise ValueError(f"theme must be one of {list(PRESETS)}, got {self.base!r}")
        for name, value in PRESETS[self.base].items():
            given = getattr(self, name)
            if given is None or (name == "palette" and not isinstance(given, str) and
                                 not list(given)):  # fmt: skip
                object.__setattr__(self, name, value)
        for name, choices in _CHOICES.items():
            if getattr(self, name) not in choices:
                raise ValueError(f"{name} must be one of {choices}, got {getattr(self, name)!r}")
        for name in ("panel_fill", "frame", "strip_fill", "strip_bold"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be True or False, got {getattr(self, name)!r}")
        opacity = self.grid_opacity
        if not isinstance(opacity, int | float) or not 0 <= opacity <= 1:
            raise ValueError(f"grid_opacity must be between 0 and 1, got {opacity!r}")
        gap = self.panel_gap
        if not isinstance(gap, int) or isinstance(gap, bool) or not 0 <= gap <= 100:
            raise ValueError(f"panel_gap must be a whole number of pixels, 0 to 100, got {gap!r}")
        size = self.font_size
        if size != "auto" and (not isinstance(size, int | float) or isinstance(size, bool)
                               or not 6 <= size <= 48):  # fmt: skip
            raise ValueError(f'font_size must be "auto" or pixels from 6 to 48, got {size!r}')
        if not isinstance(self.palette, str):
            object.__setattr__(self, "palette", tuple(self.palette or ()))
        palette_of(self.palette or ())  # an unknown name or colour raises here

    def replace(self, **changes: Any) -> Theme:
        """This theme with some settings changed."""
        return replace(self, **changes)

    def colors(self) -> list[str]:
        """Its category colours."""
        return palette_of(self.palette or ())

    @property
    def scale(self) -> float:
        """How much the context scales text, line widths and point sizes."""
        return CONTEXTS[self.context or "notebook"]

    def spec(self) -> dict[str, Any]:
        """The settings the browser draws with (look.ts ``Look``): the text's size in
        pixels, its context applied, and whether it steps with the panels' width."""
        out = asdict(self)
        del out["palette"]
        size = FONT_SIZE if self.font_size == "auto" else float(self.font_size or FONT_SIZE)
        out["font_size"] = size * self.scale
        out["font_step"] = self.font_size == "auto"
        out["mark_scale"] = self.scale
        return out


THEME_FIELDS = tuple(f.name for f in fields(Theme) if f.name != "base")

_session = {"theme": Theme()}
"""The theme of plots made without ``theme=`` (``set_theme``)."""


def theme_of(theme: str | Theme | None) -> Theme:
    """A theme given by name, as is, or (None) the session's default."""
    if theme is None:
        return _session["theme"]
    if isinstance(theme, Theme):
        return theme
    if isinstance(theme, str):
        return Theme(theme)
    raise TypeError(f"theme must be a name or a Theme, got {type(theme).__name__}")


def set_theme(theme: str | Theme = "minimal", **changes: Any) -> Theme:
    """The theme of every plot made from now on (in this session) without ``theme=``.

    ```python
    at.set_theme("framed")                        # a preset
    at.set_theme("minimal", panel_gap=12)         # a preset, changed
    at.set_theme()                                # back to the default
    ```
    """
    base = theme_of(theme)
    _session["theme"] = base.replace(**changes) if changes else base
    return _session["theme"]


def get_theme() -> Theme:
    """The session's default theme (``set_theme``)."""
    return _session["theme"]
