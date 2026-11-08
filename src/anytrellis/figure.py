"""Images of a plot without a browser: the plot as an SVG drawn in Python, as the browser
draws it (``js/src/core``: layout, ticks, drawing, the Canvas 2D marks, the selection and
the legend), and that SVG as a PNG with the optional ``resvg_py``.

What it shows is the plot as shown: the zoom the browser last reported (``plot._view``),
the selection, a linked plot's highlight and the opened panel. A plot never shown: all of
its data, ``DEFAULT_WIDTH`` pixels wide.

Text is measured with Helvetica's widths, near enough the system font the browser uses:
labels sit, thin out and fit as they do on screen.
"""

from __future__ import annotations

import datetime as dt
import itertools
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

import numpy as np

from anytrellis.codec import DTYPES, Buffers
from anytrellis.pages import page_list

if TYPE_CHECKING:
    from anytrellis.pages import Paging
    from anytrellis.plot import Trellis

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#ffffff", "text": "#1b2430", "muted": "#5e6875", "grid": "#e3e7ec",
        "panel": "#f6f7f9", "strip": "#e9ecf0", "strip_text": "#2b3440", "axis": "#a3abb5",
        "accent": "#1f77b4",
    },
    "dark": {
        "bg": "#12171d", "text": "#e5e9ed", "muted": "#98a3af", "grid": "#232b34",
        "panel": "#171d24", "strip": "#222a33", "strip_text": "#d5dbe1", "axis": "#4a5562",
        "accent": "#4dabf7",
    },
}  # fmt: skip
"""The widget's colours (widget.css), light and dark."""

FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, 'DejaVu Sans', sans-serif"
FONT_SIZE = 12.0
DEFAULT_WIDTH = 800
"""The width of a plot never shown (CSS pixels)."""
PNG_SCALE = 2.0

GAP = 6
TICK = 4
STRIP_PAD = 4
"""A strip's room at either end, and between a name and its value."""
MIN_PANEL = 24
HEADER = 26
"""The header over the plot (its title), when there is a title."""
TITLE_SIZE = FONT_SIZE * 1.15
FOCUS_MIN = 320
FOCUS_MAX = 720
"""An opened panel's plot is about the grid's height, within these (px)."""
FADED = 0.15
"""How much of its opacity an unselected mark keeps."""
LINE = FONT_SIZE * 1.35
"""A legend line's height."""

KIND_CAPSULE, KIND_RECT, KIND_TRAP = 0, 1, 2


# ---- text -----------------------------------------------------------------------------------

_WIDTHS = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
)  # fmt: skip
"""Helvetica's advance widths (1/1000 em) of the printable ASCII characters."""
_OTHER = {"·": 278, "−": 584, "…": 1000, "–": 556, "—": 1000, "°": 400, "µ": 556, "×": 584}


def text_width(text: str, size: float = FONT_SIZE, *, bold: bool = False) -> float:
    """About how wide ``text`` is at ``size`` px."""
    total = 0
    for ch in text:
        o = ord(ch)
        if 32 <= o < 127:
            total += _WIDTHS[o - 32]
        elif ch in _OTHER:
            total += _OTHER[ch]
        else:
            total += 1000 if o >= 0x2E80 else 556
    return total * size / 1000 * (1.06 if bold else 1.0)


def fit(text: str, width: float, size: float = FONT_SIZE) -> str:
    """``text`` cut with an ellipsis to fit ``width`` px."""
    if text_width(text, size) <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) >> 1
        if text_width(text[:mid] + "…", size) <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + "…" if lo else ""


# ---- numbers as JavaScript writes them ------------------------------------------------------


def _round(v: float) -> float:
    """``Math.round``: halves up."""
    return float(math.floor(v + 0.5))


def _fixed(v: float, digits: int) -> str:
    """``Number.prototype.toFixed``: halves away from zero; no minus on zero."""
    if v == 0:
        v = 0.0
    if abs(v) >= 1e21:  # as String(v): 1e+24
        return repr(float(v))
    q = Decimal(v).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return f"{q:f}"


def _js(v: float) -> str:
    """``String(number)`` for the numbers drawn: no ``.0`` on whole ones."""
    if v == 0:
        return "0"
    if float(v).is_integer() and abs(v) < 1e21:
        return str(int(v))
    return repr(float(v))


def _n(v: float) -> str:
    """A coordinate in the SVG: at most two decimals."""
    return _js(_round(v * 100) / 100)


# ---- ticks (ticks.ts) -----------------------------------------------------------------------

Tick = tuple[float, str]


def y_tick_count(kind: str, lo: float, hi: float, h: float) -> int:
    """How many ticks a y axis of ``h`` px draws over [lo, hi]."""
    if kind != "band":
        return max(2, math.floor(h / 36))
    shown = max(1.0, hi - lo)
    return max(2, math.floor(shown / max(1, math.ceil(15 / (h / shown)))))


def ticks(kind: str, lo: float, hi: float, origin: float, count: int,
          levels: list[str] | None = None) -> list[Tick]:  # fmt: skip
    """Ticks over [lo, hi] (axis units relative to ``origin``), about ``count`` of them."""
    if not (hi > lo) or not math.isfinite(lo) or not math.isfinite(hi):
        return []
    count = max(1, count)
    if kind == "band":
        return _band_ticks(lo, hi, levels or [], count)
    if kind == "time":
        return [(v - origin, s) for v, s in _time_ticks(lo + origin, hi + origin, count)]
    if kind == "log":
        return [(v - origin, s) for v, s in _log_ticks(lo + origin, hi + origin, count)]
    step = nice_step(hi - lo, count)
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    decimals = max(0, -math.floor(math.log10(step) + 1e-9))
    out: list[Tick] = []
    i = first
    while i <= last and len(out) < 1000:
        v = i * step or 0.0
        out.append((v, format_number(v + origin, step, decimals)))
        i += 1
    return out


def nice_step(span: float, count: float) -> float:
    """A 1, 2 or 5 times a power of ten step giving about ``count`` steps over ``span``."""
    raw = span / count
    power = 10.0 ** math.floor(math.log10(raw))
    f = raw / power
    nice = 1 if f < 1.5 else 2 if f < 3.5 else 5 if f < 7.5 else 10
    return nice * power


def format_number(v: float, step: float, decimals: int) -> str:
    if abs(v) < step * 1e-6:
        v = 0.0
    a = abs(v)
    if a >= 1e5 and step >= 1e3:
        div, suffix = ((1e12, "T") if a >= 1e12 else (1e9, "G") if a >= 1e9
                       else (1e6, "M") if a >= 1e6 else (1e3, "k"))  # fmt: skip
        d = max(0, -math.floor(math.log10(step / div) + 1e-9))
        return f"{_fixed(v / div, min(d, 6))}{suffix}"
    return _fixed(v, min(decimals, 12)).replace("-", "−", 1)


def _log_ticks(lo: float, hi: float, count: int) -> list[Tick]:
    out: list[Tick] = []

    def label(v: float) -> str:
        return format_number(v, v, max(0, -math.floor(math.log10(v) + 1e-9)))

    if hi - lo < 1:
        a, b = 10.0**lo, 10.0**hi
        step = nice_step(b - a, count)
        decimals = max(0, -math.floor(math.log10(step) + 1e-9))
        i = math.ceil(a / step - 1e-9)
        while i * step <= b * (1 + 1e-12) and len(out) < 1000:
            v = i * step
            if v > 0:
                out.append((math.log10(v), format_number(v, step, decimals)))
            i += 1
        return out
    decades = hi - lo
    every = max(1, math.ceil(decades / count))
    mults = [1, 2, 5] if every == 1 and decades * 3 <= count * 1.5 else [1]
    for e in range(math.floor(lo), math.ceil(hi) + 1):
        if len(out) >= 1000:
            break
        if e % every:
            continue
        for m in mults:
            value = math.log10(m) + e
            if lo - 1e-9 <= value <= hi + 1e-9:
                out.append((value, label(m * 10.0**e)))
    return out


def minor_ticks(kind: str, lo: float, hi: float, origin: float, major: list[Tick],
                pixels: float) -> list[float]:  # fmt: skip
    """Fainter gridlines between a log axis's ticks; other axes: none."""
    if kind != "log" or not (hi > lo):
        return []
    a, b = lo + origin, hi + origin
    taken = {_round((v + origin) * 1e6) for v, _ in major}

    def pick(mults: list[int]) -> list[float]:
        out: list[float] = []
        for e in range(math.floor(a), math.ceil(b) + 1):
            if len(out) >= 2000:
                break
            for m in mults:
                v = e + math.log10(m)
                if a <= v <= b and _round(v * 1e6) not in taken:
                    out.append(v - origin)
        return out

    if (pixels / (b - a)) * math.log10(10 / 9) >= 5:
        return pick([1, 2, 3, 4, 5, 6, 7, 8, 9])
    return pick([1]) if pixels / (b - a) >= 5 else []


def _band_ticks(lo: float, hi: float, levels: list[str], count: int) -> list[Tick]:
    first = max(0, math.ceil(lo))
    last = min(len(levels) - 1, math.floor(hi))
    n = last - first + 1
    if n <= 0:
        return []
    every = max(1, math.ceil(n / count))
    return [(float(i), levels[i]) for i in range(first, last + 1, every)]


SECOND = 1000
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FIXED = [
    1, 2, 5, 10, 20, 50, 100, 200, 500,
    SECOND, 2 * SECOND, 5 * SECOND, 15 * SECOND, 30 * SECOND,
    MINUTE, 2 * MINUTE, 5 * MINUTE, 15 * MINUTE, 30 * MINUTE,
    HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR,
    DAY, 2 * DAY, 7 * DAY,
]  # fmt: skip
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)


def _date(t: float) -> dt.datetime:
    return _EPOCH + dt.timedelta(milliseconds=math.floor(t))


def _utc(year: int, month: int) -> float:
    """``Date.UTC(year, month, 1)``, month from 0."""
    year += month // 12
    month %= 12
    return (dt.datetime(year, month + 1, 1, tzinfo=dt.UTC) - _EPOCH) / dt.timedelta(milliseconds=1)


def _time_ticks(lo: float, hi: float, count: int) -> list[Tick]:
    target = (hi - lo) / count
    out: list[Tick] = []
    fixed = next((s for s in FIXED if s >= target), None)
    try:
        if fixed is not None:
            shift = 4 * DAY if fixed == 7 * DAY else 0  # weeks start on Mondays
            t = math.ceil((lo - shift) / fixed) * fixed + shift
            while t <= hi and len(out) < 1000:
                out.append((float(t), _time_label(t, fixed)))
                t += fixed
            return out
        months = next((m for m in (1, 2, 3, 6) if m * 30 * DAY >= target), None)
        if months is not None:
            d = _date(lo)
            y, m = d.year, d.month - 1
            while len(out) < 1000:
                if m == 12:
                    m, y = 0, y + 1
                t = _utc(y, m)
                if t > hi:
                    break
                if t >= lo and m % months == 0:
                    out.append((t, str(y) if m == 0 else MONTHS[m]))
                m += 1
            return out
        step = max(1.0, nice_step(target / (365.25 * DAY), 1))
        year = math.ceil(_date(lo).year / step) * step
        while len(out) < 1000:
            t = _utc(int(year), 0)
            if t > hi:
                break
            if t >= lo:
                out.append((t, _js(year)))
            year += step
    except (OverflowError, ValueError):  # beyond the years datetime knows
        pass
    return out


def _time_label(t: float, step: float) -> str:
    d = _date(t)
    hm = f"{d.hour:02d}:{d.minute:02d}"
    day = f"{MONTHS[d.month - 1]} {d.day}"
    if step < SECOND:
        return f"{hm}:{d.second:02d}.{d.microsecond // 1000:03d}"
    if step < MINUTE:
        return f"{hm}:{d.second:02d}"
    if step < DAY:
        return day if t % DAY == 0 else hm
    return day


# ---- layout (layout.ts) ---------------------------------------------------------------------


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass
class PanelBox:
    index: int
    rect: Rect
    show_x: bool
    show_y: bool
    strip: Rect | None
    label: str
    note: str = ""
    """A paged wrap's value of the statistic sorted by, at the strip's right end."""
    y_axis_x: float | None = None
    """Where its y axis's labels may start (left), or None: it draws none."""


@dataclass
class Strip:
    rect: Rect
    label: str
    vertical: bool


@dataclass
class Layout:
    width: float
    height: float
    panels: list[PanelBox]
    strips: list[Strip]
    x_title: tuple[float, float] | None
    y_title: tuple[float, float] | None
    spare: Rect | None
    x_axis_h: float = 0
    """An x axis's height, its tick labels included."""


def panel_name(spec: dict[str, Any], index: int) -> str:
    p = spec["panels"][index]
    return " · ".join(p["keys"]) or p["label"] or f"panel {index + 1}"


def _y_labels_width(spec: dict[str, Any], domain: list[float], h: float | None) -> float:
    y = spec["y"]
    count = (1000 if y["kind"] == "band" else 5 if h is None
             else y_tick_count(y["kind"], domain[0], domain[1], h))  # fmt: skip
    labels = ticks(y["kind"], domain[0], domain[1], y["origin"], count, y["levels"])
    return math.ceil(max([0.0, *(text_width(s) for _, s in labels)])) + TICK + 4


def layout(spec: dict[str, Any], width: float, height: float | None = None,
           focused: int | None = None, page: list[int] | None = None) -> Layout:  # fmt: skip
    """Where the panels, strips and titles sit, ``width`` px wide; ``height``: the plot's
    height, overriding the spec's; ``focused``: that panel alone; ``page``: a paged wrap's
    panels on the page shown (default: the first page's)."""
    if focused is not None and 0 <= focused < len(spec["panels"]):
        return _focus_layout(spec, width, height, focused)
    grid = spec["grid"]
    pages = spec.get("pages")
    shown: list[int] | None = None
    panels = spec["panels"]
    if pages:  # the page's panels in turn, on a grid of the page's size
        per = pages["rows"] * pages["cols"]
        shown = page if page is not None else \
            page_list(range(len(panels)), per, pages.get("groups"))[0]  # fmt: skip
        if pages.get("grid"):  # a grid's page: each cell in its place
            panels = [spec["panels"][index] for index in shown]
        else:
            panels = [{**spec["panels"][index], "row": k // pages["cols"],
                       "col": k % pages["cols"]} for k, index in enumerate(shown)]  # fmt: skip
    fs = FONT_SIZE
    rows = max(1, pages["rows"] if pages else grid["rows"])
    cols = max(1, pages["cols"] if pages else grid["cols"])
    at = {(p["row"], p["col"]): i for i, p in enumerate(panels)}

    show_x = []
    show_y = []
    for p in panels:
        below = at.get((p["row"] + 1, p["col"]))
        show_x.append(below is None or panels[below]["xg"] != p["xg"])
        left_cell = at.get((p["row"], p["col"] - 1))
        show_y.append(left_cell is None or panels[left_cell]["yg"] != p["yg"])

    y_label = [_y_labels_width(spec, p["y"], None) if show_y[i] else 0.0
               for i, p in enumerate(panels)]  # fmt: skip
    y_axis = [0.0] * cols

    def gutters() -> None:
        for c in range(cols):
            y_axis[c] = 0.0
        for i, p in enumerate(panels):
            if not show_y[i] or (p["col"] > 0 and (p["row"], p["col"] - 1) not in at):
                continue
            y_axis[p["col"]] = max(y_axis[p["col"]], y_label[i])

    gutters()
    x_axis_h = fs + TICK + 6
    row_has_x = [False] * rows
    for i, p in enumerate(panels):
        if show_x[i] and (p["row"] == rows - 1 or (p["row"] + 1, p["col"]) in at):
            row_has_x[p["row"]] = True
    if pages:
        row_has_x[rows - 1] = True  # a short last page keeps the full pages' height

    strip_h = _round(fs * 1.5 + 4)
    nested = grid.get("strips") != "joined"
    own = bool(grid.get("strip_label"))  # each panel's own strip, and no others
    start = grid.get("strip_from", 0)

    def depth(keys: list[list[str]] | None) -> int:
        return max(1, len(keys[0]) if keys else 1) if nested else 1

    wrap_depth = 1 if own else depth([panels[0]["keys"][start:]] if panels else None) \
        if grid["kind"] == "wrap" else 0  # fmt: skip
    col_depth = depth(grid.get("col_keys")) \
        if not own and grid["kind"] == "grid" and grid.get("col_labels") else 0  # fmt: skip
    row_depth = depth(grid.get("row_keys")) \
        if not own and grid["kind"] == "grid" and grid.get("row_labels") else 0  # fmt: skip
    wrap_strip = wrap_depth * strip_h
    top_strip = col_depth * strip_h
    right_strip = row_depth * strip_h
    x_title_h = _round(fs * 1.4 + 4) if spec["x"]["title"] else 0
    y_title_w = _round(fs * 1.4 + 4) if spec["y"]["title"] else 0
    left = 4 + y_title_w
    right = 10
    top = 6
    bottom = 4 + x_title_h
    axis_rows = sum(x_axis_h for r in row_has_x if r)

    def panel_size() -> tuple[float, float]:
        free = (width - left - right - sum(y_axis) - (cols - 1) * GAP - right_strip
                - (GAP if right_strip else 0))  # fmt: skip
        w = max(MIN_PANEL, math.floor(free / cols))
        fixed = top + bottom + top_strip + axis_rows + rows * wrap_strip + (rows - 1) * GAP
        if height:
            h = (height - fixed) / rows
        elif spec.get("panel_height"):
            h = spec["panel_height"]
        elif spec.get("height"):
            h = (spec["height"] - fixed) / rows
        elif spec.get("aspect"):
            h = w * spec["aspect"]
        else:
            h = min(300, max(90, w * 0.62))
        return w, max(MIN_PANEL, math.floor(h))

    pw, ph = panel_size()
    for i, p in enumerate(panels):
        if show_y[i]:
            y_label[i] = max(y_label[i], _y_labels_width(spec, p["y"], ph))
    gutters()
    pw, ph = panel_size()

    col_x: list[float] = []
    x = float(left)
    for c in range(cols):
        x += y_axis[c]
        col_x.append(x)
        x += pw + GAP
    row_y: list[float] = []
    y = float(top + top_strip)
    for r in range(rows):
        y += wrap_strip
        row_y.append(y)
        y += ph + (x_axis_h if row_has_x[r] else 0) + GAP
    plot_bottom = y - GAP
    plot_right = col_x[cols - 1] + pw

    boxes = []
    for i, p in enumerate(panels):
        rect = Rect(col_x[p["col"]], row_y[p["row"]], pw, ph)
        # a wrap's own strip: its innermost level's (the outer levels': strips over it)
        strip = Rect(rect.x, rect.y - strip_h, pw, strip_h - 1) if wrap_strip else None
        index = shown[i] if shown is not None else i
        label = p.get("strip", p["label"]) if own \
            else p["keys"][-1] if wrap_depth > 1 else p["label"]  # fmt: skip
        y_axis_x = rect.x - y_label[i] if show_y[i] else None
        boxes.append(PanelBox(index, rect, show_x[i], show_y[i], strip, label,
                              y_axis_x=y_axis_x))  # fmt: skip
    strips = []
    if col_depth == 1:
        for c, label in enumerate(grid["col_labels"]):
            strips.append(Strip(Rect(col_x[c], top, pw, strip_h - 1), label, False))
    elif col_depth > 1:
        for k, a, b in nest(grid["col_keys"], col_depth):
            strips.append(Strip(Rect(col_x[a], top + k * strip_h, col_x[b] + pw - col_x[a],
                                     strip_h - 1), grid["col_keys"][a][k], False))  # fmt: skip
    if row_depth == 1:
        for r, label in enumerate(grid["row_labels"]):
            strips.append(Strip(Rect(plot_right + GAP, row_y[r], strip_h - 1, ph), label, True))
    elif row_depth > 1:
        for k, a, b in nest(grid["row_keys"], row_depth):
            x0 = plot_right + GAP + (row_depth - 1 - k) * strip_h  # the first column outermost
            strips.append(Strip(Rect(x0, row_y[a], strip_h - 1, row_y[b] + ph - row_y[a]),
                                grid["row_keys"][a][k], True))  # fmt: skip
    if wrap_depth > 1:  # the outer levels' strips over the panels side by side sharing them
        for r in range(rows):
            in_row = sorted((p for p in panels if p["row"] == r), key=lambda p: p["col"])
            runs: list[list[dict[str, Any]]] = []
            for i, p in enumerate(in_row):
                if i and p["col"] == in_row[i - 1]["col"] + 1:
                    runs[-1].append(p)
                else:
                    runs.append([p])
            for run in runs:
                keys = [p["keys"][start:] for p in run]
                for k, a, b in nest(keys, wrap_depth - 1):
                    x0, x1 = col_x[run[a]["col"]], col_x[run[b]["col"]] + pw
                    strips.append(Strip(Rect(x0, row_y[r] - wrap_strip + k * strip_h, x1 - x0,
                                             strip_h - 1), keys[a][k], False))  # fmt: skip

    spare = None
    if grid["kind"] == "wrap" and panels and not pages:
        last = rows - 1
        used = max((p["col"] + 1 for p in panels if p["row"] == last), default=0)
        if 0 < used < cols:
            sx = col_x[used] - y_axis[used] + 8
            sy = row_y[last - 1] + ph + x_axis_h + GAP if last > 0 else row_y[last] - wrap_strip
            sb = row_y[last] + ph
            if plot_right - sx >= 60 and sb - sy >= 30:
                spare = Rect(sx, sy, plot_right - sx, sb - sy)

    centre_x = (col_x[0] + plot_right) / 2
    centre_y = (top + top_strip + plot_bottom) / 2
    return Layout(
        width=width,
        height=math.ceil(plot_bottom + bottom + 2),
        panels=boxes,
        strips=strips,
        x_title=(centre_x, plot_bottom + x_title_h - 2) if x_title_h else None,
        y_title=(4 + fs, centre_y) if y_title_w else None,
        spare=spare,
        x_axis_h=x_axis_h,
    )


def nest(keys: list[list[str]], depth: int) -> list[tuple[int, int, int]]:
    """Nested strips: for each of the first ``depth`` levels, the runs of items in turn whose
    levels up to it are the same, as (level, first, last)."""
    out = []
    for k in range(depth):
        a = 0
        for i in range(1, len(keys) + 1):
            if i < len(keys) and keys[i][: k + 1] == keys[a][: k + 1]:
                continue
            out.append((k, a, i - 1))
            a = i
    return out


def _focus_layout(spec: dict[str, Any], width: float, height: float | None,
                  index: int) -> Layout:  # fmt: skip
    fs = FONT_SIZE
    p = spec["panels"][index]
    strip_h = _round(fs * 1.5 + 4)
    x_axis_h = fs + TICK + 6
    x_title_h = _round(fs * 1.4 + 4) if spec["x"]["title"] else 0
    y_title_w = _round(fs * 1.4 + 4) if spec["y"]["title"] else 0
    left, right, top, bottom = 4 + y_title_w, 10, 6, 4 + x_title_h
    total = height if height is not None else 360
    h = max(MIN_PANEL, math.floor(total - top - strip_h - x_axis_h - bottom - 2))
    yw = _y_labels_width(spec, p["y"], h)
    w = max(MIN_PANEL, width - left - yw - right)
    rect = Rect(left + yw, top + strip_h, w, h)
    plot_bottom = rect.y + h + x_axis_h
    box = PanelBox(index, rect, True, True, Rect(rect.x, top, w, strip_h - 1),
                   p.get("strip", panel_name(spec, index)), y_axis_x=rect.x - yw)  # fmt: skip
    return Layout(
        width=width,
        height=math.ceil(plot_bottom + bottom + 2),
        panels=[box],
        strips=[],
        x_title=(rect.x + w / 2, plot_bottom + x_title_h - 2) if x_title_h else None,
        y_title=(4 + fs, rect.y + h / 2) if y_title_w else None,
        spare=None,
        x_axis_h=x_axis_h,
    )


# ---- the scene: the spec's layers, read from their buffers ----------------------------------


def _array(buffers: Buffers, ref: dict[str, Any]) -> np.ndarray:
    data = np.frombuffer(buffers.data[ref["id"]], dtype=DTYPES[ref["dtype"]])
    data = data[: ref["count"] * ref["components"]]
    return data.reshape(-1, ref["components"]) if ref["components"] > 1 else data


@dataclass
class _Marks:
    index: int
    spec: dict[str, Any]
    kind: int
    half_width: float
    coords: np.ndarray  # (n, 4), relative to the axis origins
    starts: np.ndarray
    colors: np.ndarray  # (n, 4) uint8
    base: np.ndarray | None
    codes: np.ndarray | None
    link: np.ndarray | None
    groups: np.ndarray | None


@dataclass
class _Texts:
    spec: dict[str, Any]
    coords: np.ndarray
    starts: np.ndarray
    labels: list[str]
    colors: np.ndarray | None


def _scene(spec: dict[str, Any], buffers: Buffers) -> tuple[list[_Marks], list[_Texts]]:
    marks: list[_Marks] = []
    texts: list[_Texts] = []
    for index, lr in enumerate(spec["layers"]):
        kind = lr["type"]
        if kind == "rule":
            continue
        if kind == "text":
            raw = bytes(_array(buffers, lr["labels"]))
            offsets = _array(buffers, lr["offsets"])
            labels = [raw[offsets[i] : offsets[i + 1]].decode("utf-8") for i in range(lr["count"])]
            texts.append(_Texts(lr, _array(buffers, lr["coords"]), _array(buffers, lr["starts"]),
                                labels, None if lr["colors"] is None
                                else _array(buffers, lr["colors"])))  # fmt: skip
            continue
        n = lr["count"]
        color = lr["color"]
        if color["rgba"] is not None:
            colors = _array(buffers, color["rgba"]).reshape(n, 4)
        else:
            colors = np.tile(np.array(color["solid"] or [76, 86, 106, 255], np.uint8), (n, 1))

        def opt(ref: dict[str, Any] | None) -> np.ndarray | None:
            return None if ref is None else _array(buffers, ref)

        marks.append(_Marks(
            index=index,
            spec=lr,
            kind=(KIND_RECT if kind in ("bars", "rect") else KIND_TRAP if kind in ("area", "band")
                  else KIND_CAPSULE),
            half_width=lr["width"] / 2 if kind == "line" else lr["size"] / 2 if kind == "points"
            else 0.0,
            coords=_array(buffers, lr["coords"]).reshape(n, 4),
            starts=_array(buffers, lr["starts"]),
            colors=colors,
            base=None if lr.get("base") is None else _array(buffers, lr["base"]).reshape(n, 2),
            codes=opt(color.get("codes")),
            link=opt(lr.get("link")),
            groups=opt(lr.get("groups")),
        ))  # fmt: skip
    return marks, texts


# ---- the selection (selection.ts) -----------------------------------------------------------


def select(marks: list[_Marks], brush: dict[str, Any]) -> list[np.ndarray | None]:
    """Per mark layer, the instances a brush selects (None: a context layer), grown by link
    keys and by a summary's parts, as the browser selects them."""
    x0, x1 = sorted(brush["x"]) if brush.get("x") else (-np.inf, np.inf)
    y0, y1 = sorted(brush["y"]) if brush.get("y") else (-np.inf, np.inf)
    legend = brush.get("legend")
    if not legend or not legend.get("levels"):
        legend = None
    panel = brush.get("panel")
    masks: list[np.ndarray | None] = []
    keys: list[np.ndarray] = []
    for layer in marks:
        if layer.spec.get("context"):
            masks.append(None)
            continue
        n = len(layer.coords)
        mask = np.zeros(n, dtype=bool)
        lo = 0 if panel is None else int(layer.starts[panel])
        hi = n if panel is None else int(layer.starts[panel + 1])
        codes = (layer.codes if legend and layer.spec["color"].get("legend") == legend["index"]
                 else None)  # fmt: skip
        if legend and codes is None:
            hi = lo
        c = layer.coords[lo:hi]
        ax, ay, bx, by = c[:, 0], c[:, 1], c[:, 2], c[:, 3]
        if layer.spec["type"] == "band" and layer.base is not None:
            b = layer.base[lo:hi]
            low = np.minimum.reduce([ay, by, b[:, 0], b[:, 1]])
            high = np.maximum.reduce([ay, by, b[:, 0], b[:, 1]])
            hit = ((np.maximum(ax, bx) >= x0) & (np.minimum(ax, bx) <= x1)
                   & (high >= y0) & (low <= y1))  # fmt: skip
        elif layer.kind == KIND_RECT:
            hit = ((np.maximum(ax, bx) >= x0) & (np.minimum(ax, bx) <= x1)
                   & (np.maximum(ay, by) >= y0) & (np.minimum(ay, by) <= y1))  # fmt: skip
        else:
            hit = ((ax >= x0) & (ax <= x1) & (ay >= y0) & (ay <= y1)) | (
                (bx >= x0) & (bx <= x1) & (by >= y0) & (by <= y1))  # fmt: skip
        if codes is not None and legend is not None:
            hit &= np.isin(codes[lo:hi], legend["levels"])
        mask[lo:hi] = hit
        if layer.link is not None:
            keys.append(layer.link[mask])
        masks.append(mask)
    chosen = np.unique(np.concatenate(keys)) if keys else np.array([], dtype=np.uint32)
    if len(chosen):
        for i, layer in enumerate(marks):
            mask = masks[i]
            if mask is not None and layer.link is not None:
                masks[i] = mask | np.isin(layer.link, chosen)
    families: dict[int, list[np.ndarray]] = {}
    for layer, mask in zip(marks, masks, strict=True):
        f = layer.spec.get("family")
        if mask is not None and f is not None and layer.groups is not None:
            families.setdefault(f, []).append(layer.groups[mask])
    for i, layer in enumerate(marks):
        mask = masks[i]
        f = layer.spec.get("family")
        if mask is None or f is None or layer.groups is None or f not in families:
            continue
        groups = np.unique(np.concatenate(families[f]))
        if len(groups):
            masks[i] = mask | np.isin(layer.groups, groups)
    return masks


# ---- drawing --------------------------------------------------------------------------------


@dataclass
class _View:
    panel: int
    rect: Rect
    sx: float
    ox: float
    sy: float
    oy: float
    x: tuple[float, float]
    y: tuple[float, float]


def _views(spec: dict[str, Any], lay: Layout, shown: dict[str, Any]) -> list[_View]:
    out = []
    for box in lay.panels:
        p = spec["panels"][box.index]
        x = shown.get("x", {}).get(p["xg"], p["x"])
        y = shown.get("y", {}).get(p["yg"], p["y"])
        r = box.rect
        sx = r.w / ((x[1] - x[0]) or 1)
        sy = -r.h / ((y[1] - y[0]) or 1)
        out.append(_View(box.index, r, sx, r.x - x[0] * sx, sy, r.y + r.h - y[0] * sy,
                         (x[0], x[1]), (y[0], y[1])))  # fmt: skip
    return out


def _x_ticks(spec: dict[str, Any], v: _View) -> list[Tick]:
    ax = spec["x"]
    count = max(3, math.floor(v.rect.w / 80))
    if ax["kind"] == "band" and ax.get("levels"):
        longest = max(len(s) for s in ax["levels"])
        shown = max(1.0, v.x[1] - v.x[0])
        per = v.rect.w / shown
        count = math.floor(shown / max(1, math.ceil((longest * 7.2 + 10) / per)))
    return ticks(ax["kind"], v.x[0], v.x[1], ax["origin"], max(2, count), ax["levels"])


def _y_ticks(spec: dict[str, Any], v: _View) -> list[Tick]:
    ax = spec["y"]
    count = y_tick_count(ax["kind"], v.y[0], v.y[1], v.rect.h)
    return ticks(ax["kind"], v.y[0], v.y[1], ax["origin"], count, ax["levels"])


def _hex(rgb: Any) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(c) for c in rgb[:3]))


def _alpha(name: str, a: float) -> str:
    return f' {name}="{_n(a)}"' if a < 1 else ""


class _Svg:
    """An SVG being written: elements, and clip paths shared by their rectangles."""

    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height
        self.out: list[str] = []
        self.defs: list[str] = []
        self._clips: dict[tuple[str, ...], str] = {}

    def add(self, element: str) -> None:
        self.out.append(element)

    def clip(self, r: Rect) -> str:
        key = (_n(r.x), _n(r.y), _n(r.w), _n(r.h))
        if key not in self._clips:
            cid = f"c{len(self._clips)}"
            self._clips[key] = cid
            self.defs.append(f'<clipPath id="{cid}"><rect x="{key[0]}" y="{key[1]}" '
                             f'width="{key[2]}" height="{key[3]}"/></clipPath>')  # fmt: skip
        return f'clip-path="url(#{self._clips[key]})"'

    def open(self, attrs: str) -> None:
        self.add(f"<g {attrs}>")

    def close(self) -> None:
        self.add("</g>")

    def rect(self, r: Rect, fill: str, extra: str = "") -> None:
        self.add(f'<rect x="{_n(r.x)}" y="{_n(r.y)}" width="{_n(r.w)}" height="{_n(r.h)}" '
                 f'fill="{fill}"{extra}/>')  # fmt: skip

    def text(self, x: float, y: float, text: str, fill: str, *, size: float = FONT_SIZE,
             anchor: str = "start", baseline: str = "middle", bold: bool = False,
             extra: str = "") -> None:  # fmt: skip
        y += {"middle": 0.35, "top": 0.8, "bottom": -0.2}.get(baseline, 0.0) * size
        attrs = f'x="{_n(x)}" y="{_n(y)}"'
        if size != FONT_SIZE:
            attrs += f' font-size="{_n(size)}"'
        if bold:
            attrs += ' font-weight="600"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        self.add(f'<text {attrs} fill="{fill}"{extra}>{escape(text)}</text>')

    def __str__(self) -> str:
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        w, h = _n(self.width), _n(self.height)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                f'viewBox="0 0 {w} {h}" font-family="{FONT}" font-size="{_n(FONT_SIZE)}">'
                f"{defs}{''.join(self.out)}</svg>")  # fmt: skip


def _draw_back(svg: _Svg, spec: dict[str, Any], views: list[_View], th: dict[str, str]) -> None:
    for v in views:
        r = v.rect
        svg.rect(r, th["panel"])
        d: list[str] = []
        if spec["x"]["kind"] != "band":
            for value, _ in _x_ticks(spec, v):
                x = _round(v.ox + value * v.sx) + 0.5
                d.append(f"M{_n(x)} {_n(r.y)}V{_n(r.y + r.h)}")
        if spec["y"]["kind"] != "band":
            for value, _ in _y_ticks(spec, v):
                y = _round(v.oy + value * v.sy) + 0.5
                d.append(f"M{_n(r.x)} {_n(y)}H{_n(r.x + r.w)}")
        minor: list[str] = []
        xk, yk = spec["x"]["kind"], spec["y"]["kind"]
        if xk == "log":
            for value in minor_ticks(xk, *v.x, spec["x"]["origin"], _x_ticks(spec, v), r.w):
                x = _round(v.ox + value * v.sx) + 0.5
                minor.append(f"M{_n(x)} {_n(r.y)}V{_n(r.y + r.h)}")
        if yk == "log":
            for value in minor_ticks(yk, *v.y, spec["y"]["origin"], _y_ticks(spec, v), r.h):
                y = _round(v.oy + value * v.sy) + 0.5
                minor.append(f"M{_n(r.x)} {_n(y)}H{_n(r.x + r.w)}")
        if not d and not minor:
            continue
        svg.open(svg.clip(r))
        if d:
            svg.add(f'<path d="{"".join(d)}" fill="none" stroke="{th["grid"]}"/>')
        if minor:
            svg.add(f'<path d="{"".join(minor)}" fill="none" stroke="{th["grid"]}" '
                    'stroke-opacity="0.45"/>')  # fmt: skip
        svg.close()


def _draw_marks(svg: _Svg, layer: _Marks, coords: np.ndarray, colors: np.ndarray,
                views: list[_View], base_x: np.ndarray, base_y: np.ndarray) -> None:  # fmt: skip
    """One pass over a layer's marks in every view: runs of one colour as one path, as the
    Canvas 2D renderer draws them."""
    opacity = float(layer.spec["opacity"])
    kind = layer.kind
    width = max(0.5, layer.half_width * 2)
    for v in views:
        p = v.panel
        start, end = int(layer.starts[p]), int(layer.starts[p + 1])
        if end <= start:
            continue
        # the spec's coordinates less the panel's base, in float32, as the GPU gets them
        c = coords[start:end].astype(np.float64)
        bx_, by_ = float(base_x[p]), float(base_y[p])
        c32 = (c - [bx_, by_, bx_, by_]).astype(np.float32).astype(np.float64)
        ox, oy = v.ox + bx_ * v.sx, v.oy + by_ * v.sy
        ax, ay = ox + c32[:, 0] * v.sx, oy + c32[:, 1] * v.sy
        bx, by = ox + c32[:, 2] * v.sx, oy + c32[:, 3] * v.sy
        rgba = colors[start:end]
        keep = np.isfinite(ax + ay + bx + by) & (rgba[:, 3] > 0)
        r = v.rect
        reach = width / 2 + 1
        keep &= (np.maximum(ax, bx) >= r.x - reach) & (np.minimum(ax, bx) <= r.x + r.w + reach)
        ba = bb = None
        if kind == KIND_TRAP and layer.base is not None:
            b = layer.base[start:end].astype(np.float64) - by_
            b32 = b.astype(np.float32).astype(np.float64)
            ba, bb = oy + b32[:, 0] * v.sy, oy + b32[:, 1] * v.sy
            keep &= np.isfinite(ba + bb)
        else:
            keep &= (np.maximum(ay, by) >= r.y - reach) & (np.minimum(ay, by) <= r.y + r.h + reach)
        idx = np.flatnonzero(keep)
        if not len(idx):
            continue
        if kind == KIND_RECT:
            x = np.minimum(ax, bx)
            y = np.minimum(ay, by)
            w = np.maximum(1, np.abs(bx - ax))
            h = np.maximum(1, np.abs(by - ay))
            pieces = np.stack([x, y, w, h, -w], axis=1)[idx]
            fmt = "M%.2f %.2fh%.2fv%.2fh%.2fz"
        elif kind == KIND_TRAP and ba is not None and bb is not None:
            pieces = np.stack([ax, ay, bx, by, bx, bb, ax, ba], axis=1)[idx]
            fmt = "M%.2f %.2fL%.2f %.2fL%.2f %.2fL%.2f %.2fz"
        else:
            nudge = np.where((ax == bx) & (ay == by), 0.01, 0.0)
            pieces = np.stack([ax, ay, bx + nudge, by], axis=1)[idx]
            fmt = "M%.2f %.2fL%.2f %.2f"
        packed = rgba[idx].astype(np.uint32)
        packed = (packed[:, 0] << 24) | (packed[:, 1] << 16) | (packed[:, 2] << 8) | packed[:, 3]
        cuts = [0, *(np.flatnonzero(np.diff(packed)) + 1).tolist(), len(idx)]
        rows = pieces.tolist()
        svg.open(svg.clip(r))
        for a, z in itertools.pairwise(cuts):
            color = rgba[idx[a]]
            d = "".join(fmt % tuple(row) for row in rows[a:z])
            alpha = color[3] / 255 * opacity
            if kind == KIND_CAPSULE:
                svg.add(f'<path d="{d}" fill="none" stroke="{_hex(color)}" '
                        f'stroke-width="{_n(width)}" stroke-linecap="round"'
                        f'{_alpha("stroke-opacity", alpha)}/>')  # fmt: skip
            else:
                # rects edge to edge (tiles, cells): no seams between them
                crisp = ' shape-rendering="crispEdges"' if kind == KIND_RECT else ""
                svg.add(f'<path d="{d}" fill="{_hex(color)}"{_alpha("fill-opacity", alpha)}'
                        f"{crisp}/>")  # fmt: skip
        svg.close()


def _draw_rule(svg: _Svg, lr: dict[str, Any], v: _View) -> None:
    r = v.rect
    d = []
    for value in lr["values"]:
        if lr["axis"] == "x":
            x = _round(v.ox + value * v.sx) + 0.5
            d.append(f"M{_n(x)} {_n(r.y)}V{_n(r.y + r.h)}")
        else:
            y = _round(v.oy + value * v.sy) + 0.5
            d.append(f"M{_n(r.x)} {_n(y)}H{_n(r.x + r.w)}")
    if not d:
        return
    color = lr["color"]
    dash = lr.get("dash") or []
    extra = f' stroke-dasharray="{" ".join(_n(s) for s in dash)}"' if dash else ""
    svg.add(f'<path d="{"".join(d)}" fill="none" stroke="{_hex(color)}" '
            f'stroke-width="{_n(lr["width"])}"{_alpha("stroke-opacity", color[3] / 255)}'
            f"{extra}/>")  # fmt: skip


def _draw_text(svg: _Svg, t: _Texts, v: _View, th: dict[str, str]) -> None:
    lr = t.spec
    r = v.rect
    size = float(lr["size"])
    align = lr["align"]
    anchor = {"left": "start", "center": "middle", "right": "end"}
    flip = {"left": "end", "right": "start"}
    opacity = lr["opacity"] * (0.35 if lr.get("context") else 1)
    solid = (_hex(lr["color"]), lr["color"][3] / 255) if lr.get("color") else (th["text"], 1.0)
    margin = 200
    for i in range(int(t.starts[v.panel]), int(t.starts[v.panel + 1])):
        x = v.ox + float(t.coords[i, 0]) * v.sx + lr["dx"]
        y = v.oy + float(t.coords[i, 1]) * v.sy + lr["dy"]
        if not (r.x - margin < x < r.x + r.w + margin and r.y - size < y < r.y + r.h + size):
            continue
        fill, a = solid
        if t.colors is not None:
            fill, a = _hex(t.colors[i]), t.colors[i][3] / 255
        extra = _alpha("fill-opacity", a * opacity)
        label = t.labels[i]
        px = x - lr["dx"]
        if align != "center" and r.x <= px <= r.x + r.w:
            w = text_width(label, size)
            over = x + w > r.x + r.w if align == "left" else x - w < r.x
            if over:
                svg.text(px - lr["dx"], y, label, fill, size=size, anchor=flip[align],
                         extra=extra)  # fmt: skip
                continue
        svg.text(x, y, label, fill, size=size, anchor=anchor[align], extra=extra)


def _draw_front(svg: _Svg, spec: dict[str, Any], lay: Layout, views: list[_View],
                th: dict[str, str], texts: list[_Texts], brushes: list[Rect]) -> None:  # fmt: skip
    fs = FONT_SIZE
    rules = [lr for lr in spec["layers"] if lr["type"] == "rule"]
    for v in views:
        if not rules and not any(t.starts[v.panel + 1] > t.starts[v.panel] for t in texts):
            continue
        svg.open(svg.clip(v.rect))
        for lr in rules:
            _draw_rule(svg, lr, v)
        for t in texts:
            _draw_text(svg, t, v, th)
        svg.close()

    # axes
    for box, v in zip(lay.panels, views, strict=True):
        r = v.rect
        d: list[str] = []
        if box.show_x:
            end = _label_end(lay, box)
            d.append(f"M{_n(r.x)} {_n(r.y + r.h + 0.5)}H{_n(r.x + r.w)}")
            last_right = -math.inf
            for value, label in _x_ticks(spec, v):
                x = v.ox + value * v.sx
                if x < r.x - 0.5 or x > r.x + r.w + 0.5:
                    continue
                tx = _round(x) + 0.5
                d.append(f"M{_n(tx)} {_n(r.y + r.h)}V{_n(r.y + r.h + 4)}")
                w = text_width(label)
                if x + w / 2 > end:
                    continue  # next to a panel's axis: not up to its labels
                lx = min(max(x, r.x + w / 2), r.x + r.w - w / 2 + 6)
                if lx - w / 2 < last_right + 6:
                    continue
                svg.text(lx, r.y + r.h + 4 + fs * 0.75, label, th["muted"], anchor="middle")
                last_right = lx + w / 2
        if box.show_y:
            d.append(f"M{_n(r.x - 0.5)} {_n(r.y)}V{_n(r.y + r.h)}")
            last_top = math.inf
            for value, label in _y_ticks(spec, v):
                y = v.oy + value * v.sy
                if y < r.y - 0.5 or y > r.y + r.h + 0.5:
                    continue
                ty = _round(y) + 0.5
                d.append(f"M{_n(r.x - 4)} {_n(ty)}H{_n(r.x)}")
                ly = min(max(y, r.y + fs / 2), r.y + r.h - fs / 2)
                if ly + fs / 2 > last_top - 2:
                    continue
                svg.text(r.x - 6, ly, label, th["muted"], anchor="end")
                last_top = ly - fs / 2
        if d:
            svg.add(f'<path d="{"".join(d)}" fill="none" stroke="{th["axis"]}"/>')

    # strips
    def strip(rect: Rect, label: str, vertical: bool, note: str = "") -> None:
        svg.rect(rect, th["strip"])
        svg.open(svg.clip(rect))
        cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
        if vertical:
            svg.open(f'transform="translate({_n(cx)} {_n(cy)}) rotate(90)"')
            svg.text(0, 0, fit(label, rect.h - 6), th["strip_text"], anchor="middle")
            svg.close()
        elif note:  # the name at the left, cut to leave the value whole at the right
            w = text_width(note)
            svg.text(rect.x + rect.w - STRIP_PAD, cy + 0.5, note, th["strip_text"], anchor="end")
            svg.text(rect.x + STRIP_PAD, cy + 0.5, fit(label, rect.w - 3 * STRIP_PAD - w),
                     th["strip_text"])  # fmt: skip
        else:
            svg.text(cx, cy + 0.5, fit(label, rect.w - 6), th["strip_text"], anchor="middle")
        svg.close()

    for box in lay.panels:
        if box.strip is not None:
            strip(box.strip, box.label, False, box.note)
    for s in lay.strips:
        strip(s.rect, s.label, s.vertical)

    # axis titles
    if lay.x_title:
        svg.text(*lay.x_title, spec["x"]["title"], th["muted"], anchor="middle")
    if lay.y_title:
        x, y = lay.y_title
        svg.open(f'transform="translate({_n(x)} {_n(y)}) rotate(-90)"')
        svg.text(0, 0, spec["y"]["title"], th["muted"], anchor="middle")
        svg.close()

    for b in brushes:
        svg.rect(b, th["accent"], ' fill-opacity="0.07"')
        edge = Rect(_round(b.x) + 0.5, _round(b.y) + 0.5, _round(b.w) - 1, _round(b.h) - 1)
        svg.add(f'<rect x="{_n(edge.x)}" y="{_n(edge.y)}" width="{_n(edge.w)}" '
                f'height="{_n(edge.h)}" fill="none" stroke="{th["accent"]}" '
                'stroke-opacity="0.8"/>')  # fmt: skip


LABEL_ROOM = 4
"""Room (px) an x label leaves at its panel's right edge when another panel's x axis follows."""


def _label_end(lay: Layout, box: PanelBox) -> float:
    """How far right ``box``'s x labels may reach: not up to the first label of an x axis
    right of it, nor into the y labels or the strip of the panel below and right of it (a
    grid's empty cell below ``box``, drawn into from both sides) (drawing.ts: labelEnd)."""
    r = box.rect
    end = r.x + r.w - LABEL_ROOM if _crowded_right(lay, box) else math.inf
    for b in lay.panels:
        if b.rect.x <= r.x + r.w:
            continue

        def near(y: float) -> bool:
            return r.y + r.h <= y < r.y + r.h + lay.x_axis_h

        if b.y_axis_x is not None and b.y_axis_x < r.x + r.w + 8 and near(b.rect.y):
            end = min(end, b.y_axis_x - LABEL_ROOM)
        s = b.strip  # its strip (strip_label: a grid's panels have strips of their own)
        if s is not None and s.x < r.x + r.w + 8 and near(s.y):
            end = min(end, s.x - LABEL_ROOM)
    return end


def _crowded_right(lay: Layout, box: PanelBox) -> bool:
    """Whether the panel right of ``box`` (across the gap) draws an x axis at the same
    height (drawing.ts: crowdedRight)."""
    r = box.rect
    return any(
        b is not box and b.show_x and abs(b.rect.y + b.rect.h - (r.y + r.h)) < 1
        and b.rect.x > r.x and b.rect.x - (r.x + r.w) <= 8
        for b in lay.panels
    )  # fmt: skip


def _brush_rect(brush: dict[str, Any] | None, v: _View) -> Rect | None:
    """The brush where it shows in view ``v`` (px), or None."""
    if not brush or (not brush.get("x") and not brush.get("y")):
        return None
    if brush.get("panel") is not None and brush["panel"] != v.panel:
        return None
    r = v.rect
    x0, x1, y0, y1 = r.x, r.x + r.w, r.y, r.y + r.h
    if brush.get("x"):
        a, c = (v.ox + e * v.sx for e in brush["x"])
        x0, x1 = max(x0, min(a, c)), min(x1, max(a, c))
    if brush.get("y"):
        a, c = (v.oy + e * v.sy for e in brush["y"])
        y0, y1 = max(y0, min(a, c)), min(y1, max(a, c))
    return Rect(x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None


# ---- the legend (widget.css .atr-legend) ----------------------------------------------------


@dataclass
class _Entry:
    """A piece of a legend: its title, an entry (a swatch and its label), a number legend's
    end or its gradient."""

    kind: str  # "title", "item", "text" or "gradient"
    label: str = ""
    color: str = ""
    colors: tuple[str, ...] = ()
    state: str = ""  # "on", "off" or ""

    @property
    def width(self) -> float:
        bold = self.kind == "title" or self.state == "on"
        if self.kind == "gradient":
            return 90.0
        w = text_width(self.label, bold=bold)
        return w + 14 if self.kind == "item" else w


def _legend_label(v: float) -> str:
    """As the widget writes a number legend's ends (view.ts: fmt)."""
    if abs(v) >= 1e4 or (abs(v) < 1e-2 and v != 0):
        mantissa, exp = f"{v:.2e}".split("e")
        return f"{mantissa}e{'+' if int(exp) >= 0 else '-'}{abs(int(exp))}"
    return _js(_round(v * 100) / 100)


def _legend_groups(spec: dict[str, Any], brush: dict[str, Any] | None) -> list[list[_Entry]]:
    chosen = (brush or {}).get("legend") or None
    groups = []
    for index, lg in enumerate(spec["legends"]):
        entries = [_Entry("title", lg["title"])]
        if lg["kind"] == "category":
            for i, (label, color) in enumerate(zip(lg["labels"], lg["colors"], strict=False)):
                state = ""
                if chosen and chosen.get("index") == index and chosen.get("levels"):
                    state = "on" if i in chosen["levels"] else "off"
                entries.append(_Entry("item", label, color, state=state))
        else:
            entries += [_Entry("text", _legend_label(lg.get("lo", 0))),
                        _Entry("gradient", colors=tuple(lg["colors"])),
                        _Entry("text", _legend_label(lg.get("hi", 1)))]  # fmt: skip
        groups.append(entries)
    return groups


def _flow(widths: list[float], room: float, gap: float) -> list[list[tuple[int, float]]]:
    """Pieces placed in lines (flex-wrap): each line's (index, x)."""
    lines: list[list[tuple[int, float]]] = []
    x = 0.0
    for i, w in enumerate(widths):
        if not lines or (x > 0 and x + gap + w > room + 0.5):
            lines.append([])
            x = 0.0
        else:
            x += gap if lines[-1] else 0.0
        lines[-1].append((i, x))
        x += w
    return lines


@dataclass
class _Placed:
    entry: _Entry
    x: float
    y: float  # the line's top


def _wrapped(entries: list[_Entry], room: float) -> tuple[list[_Placed], float, float]:
    """A group as a flex row that wraps: its pieces, width and height."""
    lines = _flow([e.width for e in entries], room, 10)
    placed = []
    width = 0.0
    for n, line in enumerate(lines):
        for i, x in line:
            placed.append(_Placed(entries[i], x, n * (LINE + 2)))
            width = max(width, x + entries[i].width)
    return placed, width, len(lines) * LINE + (len(lines) - 1) * 2


def _column(entries: list[_Entry]) -> tuple[list[_Placed], float, float]:
    """A category group in a list: its title, then an entry a line."""
    placed, y = [], 0.0
    for n, e in enumerate(entries):
        placed.append(_Placed(e, 0.0, y))
        y += LINE + (4 if n == 0 else 3)
    return placed, max(e.width for e in entries), y - 3


def _legend_below(groups: list[list[_Entry]], width: float) -> tuple[list[_Placed], float]:
    """The legend under the plot: its pieces (from its top left) and height."""
    room = width - 16
    blocks = [_wrapped(g, room) for g in groups]
    lines = _flow([min(b[1], room) for b in blocks], room, 16)
    placed: list[_Placed] = []
    y = 2.0
    for line in lines:
        tallest = 0.0
        for i, x in line:
            pieces, _, h = blocks[i]
            placed += [_Placed(p.entry, 8 + x + p.x, y + p.y) for p in pieces]
            tallest = max(tallest, h)
        y += tallest + 4
    return placed, y - 4 + 6


def _legend_inset(groups: list[list[_Entry]], spare: Rect) -> list[_Placed] | None:
    """The legend in a wrap's empty cells, as a list, else in rows; None: it does not fit."""
    room = spare.w - 8
    for rows in (False, True):
        # a category legend: a list (rows when that is too tall); a number legend: a row
        blocks = [_wrapped(g, room) if rows or not any(e.kind == "item" for e in g)
                  else _column(g) for g in groups]  # fmt: skip
        height = sum(b[2] for b in blocks) + 8 * (len(blocks) - 1)
        if height <= spare.h + 1 and all(b[1] <= room + 1 for b in blocks):
            y = spare.y + (spare.h - height) / 2
            placed: list[_Placed] = []
            for pieces, _, h in blocks:
                placed += [_Placed(p.entry, spare.x + 4 + p.x, y + p.y) for p in pieces]
                y += h + 8
            return placed
    return None


def _draw_legend(svg: _Svg, placed: list[_Placed], dy: float, th: dict[str, str]) -> None:
    for p in placed:
        e, x, y = p.entry, p.x, p.y + dy
        mid = y + LINE / 2
        if e.kind == "title":
            svg.text(x, mid, e.label, th["text"], bold=True)
        elif e.kind == "text":
            svg.text(x, mid, e.label, th["muted"])
        elif e.kind == "gradient":
            gid = f"g{len(svg.defs)}"
            last = max(1, len(e.colors) - 1)
            stops = "".join(f'<stop offset="{_n(i / last)}" stop-color="{c}"/>'
                            for i, c in enumerate(e.colors))  # fmt: skip
            svg.defs.append(f'<linearGradient id="{gid}">{stops}</linearGradient>')
            svg.add(f'<rect x="{_n(x)}" y="{_n(mid - 4)}" width="90" height="8" rx="2" '
                    f'fill="url(#{gid})"/>')  # fmt: skip
        else:
            off = e.state == "off"
            if off:
                svg.open('opacity="0.4"')
            svg.add(f'<rect x="{_n(x)}" y="{_n(mid - 5)}" width="10" height="10" rx="2" '
                    f'fill="{escape(e.color)}"/>')  # fmt: skip
            on = e.state == "on"
            svg.text(x + 14, mid, e.label, th["text"] if on else th["muted"], bold=on)
            if off:
                svg.close()


# ---- the image ------------------------------------------------------------------------------


def _shown(plot: Trellis) -> dict[str, Any]:
    """The view the browser last reported: its width and each scale group's range."""
    view = getattr(plot, "_view", None) or {}
    return {
        "width": view.get("width"),
        "x": {int(g): (float(r[0]), float(r[1])) for g, r in view.get("x", [])},
        "y": {int(g): (float(r[0]), float(r[1])) for g, r in view.get("y", [])},
    }


def _page(plot: Trellis, spec: dict[str, Any]) -> list[int] | None:
    """A paged wrap's panels on the page shown (as the browser's ``pagePanels``)."""
    pages = spec.get("pages")
    if not pages:
        return None
    return plot._page_list()[plot.page - 1]


def _note_sorted(spec: dict[str, Any], lay: Layout, paging: Paging) -> None:
    """Each strip's value of the statistic sorted by, at its right (``noteSorted``)."""
    stats = (spec.get("pages") or {}).get("stats", [])
    stat = next((s for s in stats if s["name"] == paging.get("sort")), None)
    if stat is None:
        return
    for box in lay.panels:
        box.note = stat["text"][box.index]


def figure_svg(plot: Trellis, *, width: float | None = None, height: float | None = None,
               theme: str = "light") -> str:  # fmt: skip
    """The plot as shown, as an SVG ``width`` by ``height`` CSS pixels (default: the
    width it was last shown at, else ``DEFAULT_WIDTH``; the height its layout's)."""
    if theme not in THEMES:
        raise ValueError(f"theme must be one of {list(THEMES)}, got {theme!r}")
    th = THEMES[theme]
    spec, buffers = plot._shown_scene()
    shown = _shown(plot)
    width = float(width or shown["width"] or DEFAULT_WIDTH)
    if width < 100:
        raise ValueError(f"width must be at least 100 px, got {width}")
    header = HEADER if spec["title"] else 0
    stage_h = None if height is None else height - header
    if stage_h is not None and stage_h < 60:
        raise ValueError(f"height {height} leaves no room for the plot")

    names = [panel_name(spec, i) for i in range(len(spec["panels"]))]
    focus_name = plot.focused
    focused = names.index(focus_name) if focus_name in names else None
    brush = plot._current_selection()
    groups = _legend_groups(spec, brush)

    placed: list[_Placed] = []
    legend_h = 0.0
    page = _page(plot, spec)
    if focused is None:
        lay = layout(spec, width, stage_h, page=page)
        spare = None if spec.get("legend_position") == "bottom" else lay.spare
        inset = _legend_inset(groups, spare) if groups and spare is not None else None
        if inset is not None:
            placed = inset
        elif groups:
            placed, legend_h = _legend_below(groups, width)
            if stage_h is not None:
                lay = layout(spec, width, stage_h - legend_h, page=page)
        _note_sorted(spec, lay, plot.paging)
    else:
        if groups:
            placed, legend_h = _legend_below(groups, width)
        h = stage_h - legend_h if stage_h is not None else max(
            FOCUS_MIN, min(layout(spec, width).height, FOCUS_MAX))  # fmt: skip
        lay = layout(spec, width, h, focused)
    inset_legend = bool(placed) and legend_h == 0

    total = _round(header + lay.height + legend_h)  # as the page rounds the plot's box
    svg = _Svg(width, total if height is None else float(height))
    svg.add(f'<rect width="100%" height="100%" fill="{th["bg"]}"/>')
    if header:
        svg.text(8, 14, fit(spec["title"], width - 16, TITLE_SIZE), th["text"], size=TITLE_SIZE,
                 bold=True)  # fmt: skip
    svg.open(f'transform="translate(0 {header})"' if header else 'class="plot"')

    views = _views(spec, lay, shown)
    marks, texts = _scene(spec, buffers)
    base_x = np.array([p["x"][0] for p in spec["panels"]], dtype=np.float64)
    base_y = np.array([p["y"][0] for p in spec["panels"]], dtype=np.float64)
    _draw_back(svg, spec, views, th)
    if focused is None and page == []:  # as the browser's .atr-empty
        svg.text(width / 2, lay.height * 0.4, "No panel matches the filters", th["muted"],
                 anchor="middle", baseline="top")  # fmt: skip

    masks: list[np.ndarray | None] = []
    fractions: list[np.ndarray | None] = [None] * len(marks)
    if brush:
        masks = select(marks, brush)
    elif getattr(plot, "_highlight", None) is not None:
        masks, fractions = _highlighted(plot, marks)
    for layer, mask in zip(marks, masks or [None] * len(marks), strict=True):
        colors = layer.colors
        if mask is not None:
            colors = colors.copy()
            colors[:, 3] = np.floor(colors[:, 3] * FADED + 0.5).astype(np.uint8)
        _draw_marks(svg, layer, layer.coords, colors, views, base_x, base_y)
    for layer, mask, fraction in zip(marks, masks, fractions, strict=False):
        if mask is None or not mask.any():
            continue
        colors = layer.colors.copy()
        colors[~mask] = 0
        coords = layer.coords
        if fraction is not None:  # a bar's selected share, from its base up
            coords = coords.copy()
            share = np.clip(fraction, 0, 1)
            coords[:, 3] = coords[:, 1] + share * (coords[:, 3] - coords[:, 1])
        _draw_marks(svg, layer, coords, colors, views, base_x, base_y)

    rects = [b for v in views if (b := _brush_rect(brush, v)) is not None]
    _draw_front(svg, spec, lay, views, th, texts, rects)
    if inset_legend:
        _draw_legend(svg, placed, 0, th)
    svg.close()
    if placed and not inset_legend:
        _draw_legend(svg, placed, header + lay.height, th)
    return str(svg)


Masks = list[np.ndarray | None]


def _highlighted(plot: Trellis, marks: list[_Marks]) -> tuple[Masks, Masks]:
    """What another plot's selection highlights here (``anytrellis.link``): per mark layer a
    mask, and a histogram bar's selected share."""
    from anytrellis.linking import highlight_message

    message, buffers = highlight_message(plot._highlight_entries(), plot._highlight)
    masks: list[np.ndarray | None] = []
    fractions: list[np.ndarray | None] = []
    for layer in marks:
        entry = (message.get("layers") or [None] * (layer.index + 1))[layer.index]
        n = len(layer.coords)
        if layer.spec.get("context") or not entry:
            masks.append(None)
            fractions.append(None)
        elif "mask" in entry:
            bits = np.frombuffer(buffers[entry["mask"]], dtype=np.uint8)
            masks.append(np.unpackbits(bits, bitorder="little")[:n].astype(bool))
            fractions.append(None)
        else:
            share = np.frombuffer(buffers[entry["fraction"]], dtype=np.float32)[:n]
            masks.append(share > 0)
            fractions.append(share.astype(np.float64))
    return masks, fractions


def svg_to_png(svg: str, scale: float = PNG_SCALE, background: str | None = None) -> bytes:
    """PNG bytes of ``svg``, ``scale`` pixels per CSS pixel (needs the optional
    ``resvg_py``)."""
    try:
        import resvg_py
    except ImportError:
        raise ImportError(
            "PNG images need resvg-py: pip install 'anytrellis[png]' (or save as .svg)"
        ) from None
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=scale, background=background))
