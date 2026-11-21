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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

import numpy as np

from anytrellis.channels import dash_pattern, dash_pieces, shape_paths
from anytrellis.codec import DTYPES, Buffers
from anytrellis.formats import axis_format, number_format
from anytrellis.pages import page_list, pins_of
from anytrellis.theme import CONTEXTS, NARROW, PRESETS
from anytrellis.transforms import TRANSFORMS, forward, inverse

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

ROW_LABEL_MAX = 120
"""The widest a level row label gets (px); a longer one is cut."""
BOLD = 1.06
"""Strip text is semibold: about this much wider."""

FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, 'DejaVu Sans', sans-serif"
FONT_SIZE = 12.0
"""The text's size (px) unless the theme sets another (look ``font_size``)."""
DEFAULT_WIDTH = 800
"""The width of a plot never shown (CSS pixels)."""
PNG_SCALE = 2.0

TICK = 4
STRIP_PAD = 4
"""A strip's room at either end, and between a name and its value."""
MIN_PANEL = 24
HEADER = 26
"""The header over the plot (its title), when there is a title: at least this high."""
TITLE = 1.15
"""The title's size, in the page's text size (widget.css .atr-title)."""
CAPTION = 11 / 12
"""The caption's size, in the page's text size (widget.css .atr-caption)."""
FOCUS_MIN = 320
RIGHT_MOST = 0.35
"""A legend right of the plot takes at most this share of its width."""
FOCUS_MAX = 720
"""An opened panel's plot is about the grid's height, within these (px)."""
FADED = 0.15
"""How much of its opacity an unselected mark keeps."""
LINE = 1.35
"""A line's height, in its text size (widget.css .atr-root)."""

KIND_CAPSULE, KIND_RECT, KIND_TRAP, KIND_POINT = 0, 1, 2, 3


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


def wrap_text(text: str, width: float, size: float = FONT_SIZE) -> list[str]:
    """``text`` in lines at most ``width`` px wide, broken between words (a longer word: a
    line of its own, cut); its own line breaks kept."""
    lines: list[str] = []
    for para in text.splitlines() or [""]:
        line = ""
        for word in para.split():
            wider = f"{line} {word}" if line else word
            if line and text_width(wider, size) > width:
                lines.append(line)
                line = word
            else:
                line = wider
        lines.append(fit(line, width, size))
    return lines


def fit(text: str, width: float, size: float = FONT_SIZE, *, bold: bool = False) -> str:
    """``text`` cut with an ellipsis to fit ``width`` px."""
    if text_width(text, size, bold=bold) <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) >> 1
        if text_width(text[:mid] + "…", size, bold=bold) <= width:
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
          levels: list[str] | None = None, format: str | None = None) -> list[Tick]:  # fmt: skip
    """Ticks over [lo, hi] (axis units relative to ``origin``), about ``count`` of them,
    labelled by ``format`` when one is given (formats.py)."""
    out = _placed_ticks(kind, lo, hi, origin, count, levels)
    f = axis_format(kind, format)
    if f is None:
        return out
    return [(v, f(inverse(kind, v + origin) if kind in TRANSFORMS else v + origin))
            for v, _ in out]  # fmt: skip


def _placed_ticks(kind: str, lo: float, hi: float, origin: float, count: int,
                  levels: list[str] | None) -> list[Tick]:  # fmt: skip
    if not (hi > lo) or not math.isfinite(lo) or not math.isfinite(hi):
        return []
    count = max(1, count)
    if kind == "band":
        return _band_ticks(lo, hi, levels or [], count)
    if kind == "time":
        return [(v - origin, s) for v, s in _time_ticks(lo + origin, hi + origin, count)]
    if kind == "log":
        return [(v - origin, s) for v, s in _log_ticks(lo + origin, hi + origin, count)]
    if kind in ("sqrt", "symlog"):
        return [(v - origin, s) for v, s in _scale_ticks(kind, lo + origin, hi + origin, count)]
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


def _scale_ticks(kind: str, lo: float, hi: float, count: int) -> list[Tick]:
    """A sqrt or symlog axis's ticks (ticks.ts: scaleTicks), none closer than 0.4 of an
    even step: round values, the finest step not crowded; or a symlog axis's decades either
    side of 0, thinned where they crowd."""
    found: list[tuple[float, str, int]] = []
    gap = (hi - lo) / count * 0.4

    def add(v: float, label: str, rank: int) -> None:
        u = float(forward(kind, v))
        if lo - 1e-9 <= u <= hi + 1e-9:
            found.append((u, label, rank))

    if kind == "symlog" and hi - lo >= 1:
        decades = hi - lo
        every = max(1, math.ceil(decades / count))
        mults = [1, 2, 5] if every == 1 and decades * 3 <= count * 1.5 else [1]
        add(0.0, "0", 0)
        top = math.ceil(max(abs(lo), abs(hi)))
        for e in range(top + 1):
            if len(found) >= 1000:
                break
            if e % every:
                continue
            for m in mults:
                v = m * 10.0**e
                label = format_number(v, v, max(0, -math.floor(math.log10(v) + 1e-9)))
                add(v, label, 1 if m == 1 else 2)
                add(-v, "−" + label, 1 if m == 1 else 2)
    else:
        a, b = float(inverse(kind, lo)), float(inverse(kind, hi))
        for c in range(count, 0, -1):
            found.clear()
            step = nice_step(b - a, c)
            decimals = max(0, -math.floor(math.log10(step) + 1e-9))
            i = math.ceil(a / step - 1e-9)
            while i * step <= b + step * 1e-9 and len(found) < 1000:
                v = i * step or 0.0
                i += 1
                if kind == "sqrt" and v < 0:
                    continue
                add(v, format_number(v, step, decimals), 0 if v == 0 else 2)
            if all(q[0] - p[0] >= gap - 1e-12 for p, q in itertools.pairwise(found)):
                break
    kept: list[tuple[float, str, int]] = []
    for t in sorted(found, key=lambda t: (t[2], abs(t[0]), t[0])):
        if all(abs(k[0] - t[0]) >= gap - 1e-12 for k in kept):
            kept.append(t)
    return [(u, label) for u, label, _ in sorted(kept)]


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


def _time_steps(most: float) -> list[tuple[str, float, float]]:
    """The time steps from 1 ms to ``most`` ms, smallest first: (kind, size, length in ms),
    kind "fixed" (size: ms), "months" or "years" (drawing.ts: timeSteps)."""
    out = [("fixed", float(ms), float(ms)) for ms in FIXED]
    out += [("months", float(m), m * 30 * DAY) for m in (1, 2, 3, 6)]
    p = 1
    while True:
        out += [("years", float(m * p), m * p * 365.25 * DAY) for m in (1, 2, 5)]
        if p * 365.25 * DAY > most:
            return out
        p *= 10


def _time_ticks(lo: float, hi: float, count: int) -> list[Tick]:
    """The calendar step nearest the span over ``count``, smaller while it gives fewer than
    two ticks (ticks.ts: timeTicks)."""
    target = (hi - lo) / count
    steps = _time_steps(target * 10)
    best = 0
    for i, (_, _, ms) in enumerate(steps):
        if abs(math.log(ms / target)) < abs(math.log(steps[best][2] / target)):
            best = i
    out = _time_ticks_by(lo, hi, steps[best][0], steps[best][1])
    i = best - 1
    while len(out) < 2 and i >= 0:
        out = _time_ticks_by(lo, hi, steps[i][0], steps[i][1])
        i -= 1
    return out


def _time_ticks_by(lo: float, hi: float, kind: str, size: float) -> list[Tick]:
    out: list[Tick] = []
    try:
        if kind == "fixed":
            shift = 4 * DAY if size == 7 * DAY else 0  # weeks start on Mondays
            t = math.ceil((lo - shift) / size) * size + shift
            while t <= hi and len(out) < 1000:
                out.append((float(t), _time_label(t, size)))
                t += size
            return out
        if kind == "months":
            d = _date(lo)
            y, m = d.year, d.month - 1
            while len(out) < 1000:
                if m == 12:
                    m, y = 0, y + 1
                t = _utc(y, m)
                if t > hi:
                    break
                if t >= lo and m % size == 0:
                    out.append((t, str(y) if m == 0 else MONTHS[m]))
                m += 1
            return out
        year = math.ceil(_date(lo).year / size) * size
        while len(out) < 1000:
            t = _utc(int(year), 0)
            if t > hi:
                break
            if t >= lo:
                out.append((t, _js(year)))
            year += size
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
    pinned: bool = False
    """Pinned first on every page: a pin at its strip's left."""
    y_axis_x: float | None = None
    """Where its y axis's labels may start (left), or None: it draws none."""


@dataclass
class Strip:
    rect: Rect
    label: str
    vertical: bool
    """Its text turned on its side (``row_labels="side"``)."""
    side: str = "top"
    """Over the columns (``"top"``) or right of the rows (``"right"``)."""
    span: bool = False
    """It spans several panels (a nested strip's outer level)."""
    pin: bool = False
    """A pinned panel's: a pin before its label."""


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
    x_labels: str = "flat"
    """How a band x axis sets its labels: ``"flat"``, ``"wrap"`` or ``"angle"``."""
    font_size: float = FONT_SIZE
    """The panels' text size (px): the look's, or stepped with the panels' width."""


def panel_name(spec: dict[str, Any], index: int) -> str:
    p = spec["panels"][index]
    return " · ".join(p["keys"]) or p["label"] or f"panel {index + 1}"


def _y_labels_width(spec: dict[str, Any], domain: list[float], h: float | None,
                    fs: float) -> float:  # fmt: skip
    y = spec["y"]
    count = (1000 if y["kind"] == "band" else 5 if h is None
             else y_tick_count(y["kind"], domain[0], domain[1], h))  # fmt: skip
    labels = ticks(y["kind"], domain[0], domain[1], y["origin"], count, y["levels"],
                   y.get("format"))  # fmt: skip
    return math.ceil(max([0.0, *(text_width(s, fs) for _, s in labels)])) + TICK + 4


def look_of(spec: dict[str, Any]) -> dict[str, Any]:
    """The spec's look (theme.py, look.ts): a preset's, with what the spec sets over it;
    its text size in pixels, the context applied (as ``Theme.spec`` sends it)."""
    t = spec.get("theme")
    if not t:
        look = PRESETS["minimal"]
    elif isinstance(t, str):
        look = PRESETS.get(t, PRESETS["minimal"])
    else:
        look = {**PRESETS[t.get("base") or "minimal"], **t}
    if "font_step" not in look:  # a preset's: "auto" or pixels, and a context
        size, k = look["font_size"], CONTEXTS[look.get("context") or "notebook"]
        auto = size == "auto"
        look = {**look, "font_size": (FONT_SIZE if auto else float(size)) * k,
                "font_step": auto, "mark_scale": k}  # fmt: skip
    return look


ANGLE_MAX = 90
"""The longest an angled x label gets (px); a longer one is cut."""
SQRT1_2 = math.sqrt(0.5)


def wrap_label(label: str) -> list[str]:
    """A label on two lines, split at the space nearest its middle (one line: no space)."""
    spaces = [i for i, c in enumerate(label) if c == " "]
    if not spaces:
        return [label]
    best = spaces[0]
    for i in spaces[1:]:
        if abs(i - len(label) / 2) < abs(best - len(label) / 2):
            best = i
    return [label[:best], label[best + 1 :]]


def x_label_mode(spec: dict[str, Any], panel_w: float, fs: float = FONT_SIZE) -> tuple[str, float]:
    """How a band x axis ``panel_w`` px wide sets its labels, and the axis's height: side by
    side when the longest fits its band (estimated, as the ticks thin them), else on two
    lines when each fits, else at 45 degrees (layout.ts: xLabelMode)."""
    flat = fs + TICK + 6
    levels = spec["x"]["levels"] if spec["x"]["kind"] == "band" else None
    if not levels:
        return "flat", flat
    per = panel_w / len(levels)
    if max(len(lv) for lv in levels) * 0.6 * fs + 10 <= per:
        return "flat", flat

    def fits(t: str) -> bool:
        return text_width(t, fs) + 4 <= per

    if all(fits(lv) or all(fits(t) for t in wrap_label(lv)) for lv in levels):
        return "wrap", flat + _round(fs * 1.2)
    widest = min(ANGLE_MAX, max(text_width(lv, fs) for lv in levels))
    return "angle", math.ceil((widest + fs) * SQRT1_2) + TICK + 6


def _y_title_room(spec: dict[str, Any], fs: float) -> tuple[float, float]:
    """The width of the column left of the plot holding the y title on its side, or the
    height of the line over the plot holding it level."""
    if not spec["y"]["title"]:
        return 0, 0
    if look_of(spec)["y_title"] == "side":
        return _round(fs * 1.4 + 4), 0
    return 0, _round(fs * 1.4 + 2)


def _y_title_at(spec: dict[str, Any], fs: float, side: tuple[float, float],
                left: float) -> tuple[float, float] | None:  # fmt: skip
    """Where the y title goes: on its side at ``side``, or level at the left of the line over
    the plot, from ``left``."""
    w, h = _y_title_room(spec, fs)
    return side if w else (left, 6 + h / 2) if h else None


def panel_shape(spec: dict[str, Any]) -> float | None:
    """The panels' shape, height over width, that full screen and an opened panel keep: the
    spec's aspect, unless its height or panel_height sets their height instead."""
    aspect = spec.get("aspect")
    return aspect if aspect and not spec.get("height") and not spec.get("panel_height") else None


def layout(spec: dict[str, Any], width: float, height: float | None = None,
           focused: int | None = None, page: list[int] | None = None) -> Layout:  # fmt: skip
    """Where the panels, strips and titles sit, ``width`` px wide; ``height``: the plot's
    height, overriding the spec's; ``focused``: that panel alone; ``page``: a paged wrap's
    panels on the page shown (default: the first page's).

    The panels' text is the look's size; ``"auto"`` text (``font_step``) steps from it, to
    11/12 of it when the panels would be under ``NARROW`` px wide (a paged wrap's: those of
    its first page, so every page, even an empty one, has the same) and to 13/12 in an
    opened panel (layout.ts: layout)."""
    look = look_of(spec)
    base = look["font_size"]
    one = focused is not None and 0 <= focused < len(spec["panels"])

    def at(fs: float, page: list[int] | None = page) -> Layout:
        if one:
            assert focused is not None
            return _focus_layout(spec, width, height, focused, fs)
        return _layout_at(spec, width, height, page, fs)

    if not look["font_step"]:
        return at(base)
    if one:
        return at(base * 13 / 12)
    lay = at(base)
    probe = at(base, None) if page is not None else lay
    narrowest = min([b.rect.w for b in probe.panels], default=math.inf)
    return at(base * 11 / 12) if narrowest < NARROW * base / 12 else lay


def _layout_at(spec: dict[str, Any], width: float, height: float | None,
               page: list[int] | None, fs: float) -> Layout:  # fmt: skip
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
    look = look_of(spec)
    GAP = look["panel_gap"]
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

    y_label = [_y_labels_width(spec, p["y"], None, fs) if show_y[i] else 0.0
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
    x_labels = "flat"
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
    # the row strips' widths, outermost level first: on their side, a strip's height; level,
    # as wide as their longest label
    row_w: list[float] = []
    for k in range(row_depth):
        if look["row_labels"] == "side":
            row_w.append(strip_h)
            continue
        labels = grid["row_labels"] if row_depth == 1 else [keys[k] for keys in grid["row_keys"]]
        widest = max([0.0, *(text_width(label, fs) for label in labels)])
        bold = BOLD if look["strip_bold"] else 1
        row_w.append(min(ROW_LABEL_MAX, math.ceil(widest * bold) + 2 * STRIP_PAD + 4))
    right_strip = sum(row_w)
    x_title_h = _round(fs * 1.4 + 4) if spec["x"]["title"] else 0
    y_title_w, y_title_h = _y_title_room(spec, fs)
    left = 4 + y_title_w
    right = 10
    top = 6 + y_title_h
    bottom = 4 + x_title_h
    axis_rows = sum(x_axis_h for r in row_has_x if r)

    shape = panel_shape(spec)

    def free_width() -> float:  # the width the panels share
        return (width - left - right - sum(y_axis) - (cols - 1) * GAP - right_strip
                - (GAP if right_strip else 0))  # fmt: skip

    def panel_size() -> tuple[float, float]:
        w = max(MIN_PANEL, math.floor(free_width() / cols))
        fixed = top + bottom + top_strip + axis_rows + rows * wrap_strip + (rows - 1) * GAP
        if height:
            h = (height - fixed) / rows
            # the panels' shape kept, as large as fits: narrower when the height is too low
            if shape and w * shape <= h:
                h = w * shape
            elif shape:
                w = max(MIN_PANEL, math.floor(h / shape))
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
            y_label[i] = max(y_label[i], _y_labels_width(spec, p["y"], ph, fs))
    gutters()
    pw, ph = panel_size()
    # categories that don't fit side by side: on two lines or angled, the axis that high
    x_labels, x_axis_h = x_label_mode(spec, pw, fs)
    if x_labels != "flat":
        axis_rows = sum(x_axis_h for r in row_has_x if r)
        pw, ph = panel_size()
    shift = max(0, math.floor((free_width() - cols * pw) / 2))  # narrowed panels: centred

    col_x: list[float] = []
    x = float(left + shift)
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
                                     strip_h - 1), grid["col_keys"][a][k], False,
                                span=b > a))  # fmt: skip
    vertical = look["row_labels"] == "side"

    def row_x(k: int) -> float:  # a level's strips: right of the inner levels' (outermost last)
        return plot_right + GAP + sum(row_w[k + 1 :])

    if row_depth == 1:
        for r, label in enumerate(grid["row_labels"]):
            strips.append(Strip(Rect(row_x(0), row_y[r], row_w[0] - 1, ph), label, vertical,
                                side="right"))  # fmt: skip
    elif row_depth > 1:
        for k, a, b in nest(grid["row_keys"], row_depth):
            strips.append(Strip(Rect(row_x(k), row_y[a], row_w[k] - 1, row_y[b] + ph - row_y[a]),
                                grid["row_keys"][a][k], vertical, side="right",
                                span=b > a))  # fmt: skip
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
                                             strip_h - 1), keys[a][k], False,
                                        span=b > a))  # fmt: skip

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

    centre_x = plot_right if look["x_title"] == "end" else (col_x[0] + plot_right) / 2
    centre_y = (top + top_strip + plot_bottom) / 2
    return Layout(
        width=width,
        height=math.ceil(plot_bottom + bottom + 2),
        panels=boxes,
        strips=strips,
        x_title=(centre_x, plot_bottom + x_title_h - 2) if x_title_h else None,
        y_title=_y_title_at(spec, fs, (shift + 4 + fs, centre_y), left + shift),
        spare=spare,
        x_axis_h=x_axis_h,
        x_labels=x_labels,
        font_size=fs,
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
                  index: int, fs: float) -> Layout:  # fmt: skip
    p = spec["panels"][index]
    strip_h = _round(fs * 1.5 + 4)
    x_title_h = _round(fs * 1.4 + 4) if spec["x"]["title"] else 0
    y_title_w, y_title_h = _y_title_room(spec, fs)
    left, right, top, bottom = 4 + y_title_w, 10, 6 + y_title_h, 4 + x_title_h
    total = height if height is not None else 360
    x_labels, x_axis_h = x_label_mode(
        spec, width - left - right - _y_labels_width(spec, p["y"], None, fs), fs
    )
    most = max(MIN_PANEL, math.floor(total - top - strip_h - x_axis_h - bottom - 2))
    h = most
    yw = _y_labels_width(spec, p["y"], h, fs)
    w = max(MIN_PANEL, width - left - yw - right)
    shift = 0
    shape = panel_shape(spec)
    if shape:
        # the panel's shape, as large as fits the height given: on the whole width, or
        # narrower and centred
        def fit(yw: float) -> tuple[float, float, int]:
            room = max(MIN_PANEL, width - left - yw - right)
            if room * shape <= most:
                w, h = room, max(MIN_PANEL, math.floor(room * shape))
            else:
                w, h = max(MIN_PANEL, math.floor(most / shape)), most
            return w, h, max(0, math.floor((room - w) / 2))

        w, h, shift = fit(yw)
        yw = _y_labels_width(spec, p["y"], h, fs)  # the ticks the panel's height draws
        w, h, shift = fit(yw)
    rect = Rect(left + shift + yw, top + strip_h, w, h)
    plot_bottom = rect.y + h + x_axis_h
    x_end = rect.x + w if look_of(spec)["x_title"] == "end" else rect.x + w / 2
    box = PanelBox(index, rect, True, True, Rect(rect.x, top, w, strip_h - 1),
                   p.get("strip", panel_name(spec, index)), y_axis_x=rect.x - yw)  # fmt: skip
    return Layout(
        width=width,
        height=math.ceil(plot_bottom + bottom + 2),
        panels=[box],
        strips=[],
        x_title=(x_end, plot_bottom + x_title_h - 2) if x_title_h else None,
        y_title=_y_title_at(spec, fs, (shift + 4 + fs, rect.y + h / 2), left + shift),
        spare=None,
        x_axis_h=x_axis_h,
        x_labels=x_labels,
        font_size=fs,
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
    values: np.ndarray | None = None
    """A number colour's value per instance (a legend's range selects by it)."""
    dash: list[list[float]] | None = None
    """A dashed line's patterns (line widths), and each segment's (None: the first)."""
    dash_codes: np.ndarray | None = None
    ends: dict[str, Any] | None = None
    """A line labelled at its ends: its series' names and colour legend (labels.ts)."""
    end_series: np.ndarray | None = None


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

        base = None if lr.get("base") is None else _array(buffers, lr["base"]).reshape(n, 2)
        marker = lr.get("marker") if kind == "points" else None
        if marker:  # a point's shape code and size factor, as scene.ts
            shapes, sizes = opt(marker.get("shapes")), opt(marker.get("sizes"))
            code = np.full(n, float(marker["shape"])) if shapes is None else shapes
            factor = np.ones(n) if sizes is None else sizes
            base = np.stack([code.astype(np.float64), factor.astype(np.float64)], 1)
        dash = lr.get("dash") if kind == "line" else None
        marks.append(_Marks(
            index=index,
            spec=lr,
            kind=(KIND_RECT if kind in ("bars", "rect") else KIND_TRAP if kind in ("area", "band")
                  else KIND_POINT if marker else KIND_CAPSULE),
            half_width=lr["width"] / 2 if kind == "line" else lr["size"] / 2 if kind == "points"
            else 0.0,
            coords=_array(buffers, lr["coords"]).reshape(n, 4),
            starts=_array(buffers, lr["starts"]),
            colors=colors,
            base=base,
            codes=opt(color.get("codes")),
            link=opt(lr.get("link")),
            groups=opt(lr.get("groups")),
            values=opt(color.get("values")),
            dash=None if not dash else dash["patterns"],
            dash_codes=None if not dash else opt(dash.get("codes")),
            ends=lr.get("end_labels"),
            end_series=opt((lr.get("end_labels") or {}).get("series")),
        ))  # fmt: skip
    return marks, texts


# ---- the selection (selection.ts) -----------------------------------------------------------


def select(marks: list[_Marks], brush: dict[str, Any]) -> list[np.ndarray | None]:
    """Per mark layer, the instances a brush selects (None: a context layer), grown by link
    keys and by a summary's parts, as the browser selects them."""
    x0, x1 = sorted(brush["x"]) if brush.get("x") else (-np.inf, np.inf)
    y0, y1 = sorted(brush["y"]) if brush.get("y") else (-np.inf, np.inf)
    legend = brush.get("legend")
    if not legend or not (legend.get("levels") or legend.get("range")):
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
        # legend entries chosen: only the marks of their colours (a number colour's range:
        # of the values in it); none in another legend's colours
        mine = legend is not None and layer.spec["color"].get("legend") == legend["index"]
        codes = layer.codes if mine and legend is not None and legend.get("levels") else None
        values = layer.values if mine and legend is not None and legend.get("range") else None
        if legend and codes is None and values is None:
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
        if values is not None and legend is not None:
            a, b = sorted(legend["range"])
            v = values[lo:hi]
            hit &= (v >= a) & (v <= b)
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
        # (scene.ts panelMap) a reversed x runs right to left, a reversed y top to bottom
        rx, ry = bool(spec["x"].get("reverse")), bool(spec["y"].get("reverse"))
        sx = (-r.w if rx else r.w) / ((x[1] - x[0]) or 1)
        sy = (r.h if ry else -r.h) / ((y[1] - y[0]) or 1)
        ox = (r.x + r.w if rx else r.x) - x[0] * sx
        oy = (r.y if ry else r.y + r.h) - y[0] * sy
        out.append(_View(box.index, r, sx, ox, sy, oy, (x[0], x[1]), (y[0], y[1])))
    return out


def _x_ticks(spec: dict[str, Any], v: _View, mode: str = "flat",
             fs: float = FONT_SIZE) -> list[Tick]:  # fmt: skip
    ax = spec["x"]
    count = max(3, math.floor(v.rect.w / 80))
    if ax["kind"] == "band" and ax.get("levels"):
        longest = max(len(s) for s in ax["levels"])
        shown = max(1.0, v.x[1] - v.x[0])
        per = v.rect.w / shown
        room = 0 if mode == "wrap" else fs * 1.5 if mode == "angle" else longest * 0.6 * fs + 10
        count = math.floor(shown / max(1, math.ceil(room / per)))
    return ticks(ax["kind"], v.x[0], v.x[1], ax["origin"], max(2, count), ax["levels"],
                 ax.get("format"))  # fmt: skip


def _y_ticks(spec: dict[str, Any], v: _View) -> list[Tick]:
    ax = spec["y"]
    count = y_tick_count(ax["kind"], v.y[0], v.y[1], v.rect.h)
    return ticks(ax["kind"], v.y[0], v.y[1], ax["origin"], count, ax["levels"], ax.get("format"))


def _hex(rgb: Any) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(c) for c in rgb[:3]))


def _alpha(name: str, a: float) -> str:
    return f' {name}="{_n(a)}"' if a < 1 else ""


class _Svg:
    """An SVG being written: elements, and clip paths shared by their rectangles."""

    def __init__(self, width: float, height: float, fs: float = FONT_SIZE) -> None:
        self.width = width
        self.height = height
        self.fs = fs
        """The panels' text size, its text's default."""
        self.out: list[str] = []
        self.defs: list[str] = []
        self._clips: dict[tuple[str, ...], str] = {}
        self.title = ""
        self.description = ""
        """For screen readers: the plot's title and description (export.ts ``label``)."""

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

    def text(self, x: float, y: float, text: str, fill: str, *, size: float | None = None,
             anchor: str = "start", baseline: str = "middle", bold: bool = False,
             extra: str = "") -> None:  # fmt: skip
        size = self.fs if size is None else size
        y += {"middle": 0.35, "top": 0.8, "bottom": -0.2}.get(baseline, 0.0) * size
        attrs = f'x="{_n(x)}" y="{_n(y)}"'
        if size != self.fs:
            attrs += f' font-size="{_n(size)}"'
        if bold:
            attrs += ' font-weight="600"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        self.add(f'<text {attrs} fill="{fill}"{extra}>{escape(text)}</text>')

    def __str__(self) -> str:
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        w, h = _n(self.width), _n(self.height)
        role, about = "", ""
        if self.title or self.description:
            role = ' role="img"'
            about = f"<title>{escape(self.title or self.description)}</title>"
            if self.title and self.description:
                about += f"<desc>{escape(self.description)}</desc>"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                f'viewBox="0 0 {w} {h}" font-family="{FONT}" font-size="{_n(self.fs)}"{role}>'
                f"{about}{defs}{''.join(self.out)}</svg>")  # fmt: skip


def grid_axes(spec: dict[str, Any]) -> tuple[bool, bool]:
    """Which axes draw grid lines (never a band's): as the look says; ``"auto"``, y, and x
    too for points (a scatter reads off both) or when y is a band (bars along x)."""
    x, y = spec["x"]["kind"] != "band", spec["y"]["kind"] != "band"
    grid = look_of(spec)["grid"]
    if grid == "auto":
        return x and (not y or any(lr["type"] == "points" for lr in spec["layers"])), y
    return x and grid in ("x", "both"), y and grid in ("y", "both")


def _draw_back(svg: _Svg, spec: dict[str, Any], views: list[_View], th: dict[str, str]) -> None:
    look = look_of(spec)
    grid_x, grid_y = grid_axes(spec)
    alpha = look["grid_opacity"]
    stroke = f'stroke="{th["text"]}" stroke-opacity="{_n(alpha)}"'
    minor_stroke = f'stroke="{th["text"]}" stroke-opacity="{_n(0.45 * alpha)}"'
    for v in views:
        r = v.rect
        if look["panel_fill"]:
            svg.rect(r, th["panel"])
        d: list[str] = []
        if grid_x:
            for value, _ in _x_ticks(spec, v, "flat", svg.fs):
                x = _round(v.ox + value * v.sx) + 0.5
                d.append(f"M{_n(x)} {_n(r.y)}V{_n(r.y + r.h)}")
        if grid_y:
            for value, _ in _y_ticks(spec, v):
                y = _round(v.oy + value * v.sy) + 0.5
                d.append(f"M{_n(r.x)} {_n(y)}H{_n(r.x + r.w)}")
        minor: list[str] = []
        xk, yk = spec["x"]["kind"], spec["y"]["kind"]
        if xk == "log" and grid_x:
            for value in minor_ticks(xk, *v.x, spec["x"]["origin"], _x_ticks(spec, v), r.w):
                x = _round(v.ox + value * v.sx) + 0.5
                minor.append(f"M{_n(x)} {_n(r.y)}V{_n(r.y + r.h)}")
        if yk == "log" and grid_y:
            for value in minor_ticks(yk, *v.y, spec["y"]["origin"], _y_ticks(spec, v), r.h):
                y = _round(v.oy + value * v.sy) + 0.5
                minor.append(f"M{_n(r.x)} {_n(y)}H{_n(r.x + r.w)}")
        if not d and not minor:
            continue
        svg.open(svg.clip(r))
        if d:
            svg.add(f'<path d="{"".join(d)}" fill="none" {stroke}/>')
        if minor:
            svg.add(f'<path d="{"".join(minor)}" fill="none" {minor_stroke}/>')
        svg.close()


def _draw_marks(svg: _Svg, layer: _Marks, coords: np.ndarray, colors: np.ndarray,
                views: list[_View], base_x: np.ndarray, base_y: np.ndarray,
                source: int | None = None) -> None:  # fmt: skip
    """One pass over a layer's marks in every view: runs of one colour as one path, as the
    Canvas 2D renderer draws them. ``source``: panel ``source``'s marks in every other."""
    opacity = float(layer.spec["opacity"])
    kind = layer.kind
    width = max(0.5, layer.half_width * 2)
    for v in views:
        if source is not None and v.panel == source:
            continue
        p = v.panel if source is None else source
        start, end = int(layer.starts[p]), int(layer.starts[p + 1])
        if end <= start:
            continue
        # the spec's coordinates less the panel's base, in float32, as the GPU gets them
        c = coords[start:end].astype(np.float64)
        pin = layer.spec.get("pin")
        # a pinned axis (a rug's): pixels from the panel's left or bottom edge (scene.ts)
        bx_ = 0.0 if pin == "x" else float(base_x[p])
        by_ = 0.0 if pin == "y" else float(base_y[p])
        c32 = (c - [bx_, by_, bx_, by_]).astype(np.float32).astype(np.float64)
        sx, sy = (1.0 if pin == "x" else v.sx), (-1.0 if pin == "y" else v.sy)
        ox = v.rect.x if pin == "x" else v.ox + bx_ * v.sx
        oy = v.rect.y + v.rect.h if pin == "y" else v.oy + by_ * v.sy
        ax, ay = ox + c32[:, 0] * sx, oy + c32[:, 1] * sy
        bx, by = ox + c32[:, 2] * sx, oy + c32[:, 3] * sy
        rgba = colors[start:end]
        keep = np.isfinite(ax + ay + bx + by) & (rgba[:, 3] > 0)
        r = v.rect
        reach = width / 2 + 1
        keep &= (np.maximum(ax, bx) >= r.x - reach) & (np.minimum(ax, bx) <= r.x + r.w + reach)
        ba = bb = None
        if layer.dash is not None:  # a dashed line: its dashes, each a capsule (channels.ts)
            codes = None if layer.dash_codes is None else layer.dash_codes[start:end]
            pieces, src = dash_pieces(ax, ay, bx, by, codes, layer.dash, width)
            ax, ay, bx, by = pieces[:, 0], pieces[:, 1], pieces[:, 2], pieces[:, 3]
            rgba = rgba[src]
            keep = keep[src]
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
        shapes: list[str] = []
        if kind == KIND_POINT and layer.base is not None:  # each point's shape
            b = layer.base[start:end][idx]
            shapes = shape_paths(np.rint(b[:, 0]), ax[idx], ay[idx], layer.half_width * b[:, 1])
            pieces = np.zeros((len(idx), 0))
            fmt = ""
        elif kind == KIND_RECT:
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
            d = "".join(shapes[a:z]) if shapes else "".join(fmt % tuple(row) for row in rows[a:z])
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


# ---- text by the data (labels.ts) ------------------------------------------------------------

END_GAP = 5.0
"""Room between a line's end and its name (px)."""


@dataclass
class EndLabel:
    """A line's series name at its last point in view (labels.ts: EndLabel)."""

    panel: int
    x: float
    y: float
    text: str
    color: str
    w: float


def end_labels(marks: list[_Marks], views: list[_View], measure: Callable[[str], float],
               fs: float) -> list[EndLabel]:  # fmt: skip
    """The names at the ends of the lines labelled so: each series once, in the panel where
    its line ends rightmost (then the top one), moved apart up or down in each panel; those
    too far from their lines left out."""
    out: list[EndLabel] = []
    for layer in marks:
        if layer.ends is None or layer.end_series is None:
            continue
        best: dict[int, tuple[_View, float, float, int]] = {}
        for v in views:
            r = v.rect
            lo, hi = int(layer.starts[v.panel]), int(layer.starts[v.panel + 1])
            if hi <= lo:
                continue
            c = layer.coords[lo:hi].astype(np.float64)
            px = v.ox + c[:, [0, 2]] * v.sx
            py = v.oy + c[:, [1, 3]] * v.sy
            ok = (px >= r.x - 0.5) & (px <= r.x + r.w + 0.5) & np.isfinite(py)
            series = layer.end_series[lo:hi]
            here: dict[int, tuple[float, float, int]] = {}
            for j, k in zip(*np.nonzero(ok), strict=True):
                s, x = int(series[j]), float(px[j, k])
                if s not in here or x > here[s][0]:
                    here[s] = (x, float(py[j, k]), lo + int(j))
            for s, (x, y, i) in here.items():
                had = best.get(s)
                if had is None or r.x > had[0].rect.x + 0.5 or \
                        (abs(r.x - had[0].rect.x) <= 0.5 and r.y < had[0].rect.y):  # fmt: skip
                    best[s] = (v, x, y, i)
        for s, (v, x, y, i) in best.items():
            r = v.rect
            text = layer.ends["names"][s] if s < len(layer.ends["names"]) else ""
            w = measure(text)
            ay = min(r.y + r.h, max(r.y, y))
            lx = max(r.x + 2, min(x + END_GAP, r.x + r.w - 2 - w))
            out.append(EndLabel(v.panel, lx, ay, text, _hex(layer.colors[i]), w))
    kept: list[EndLabel] = []
    for v in views:
        mine = [e for e in out if e.panel == v.panel]
        r = v.rect
        kept += [mine[i] for i in spread(mine, r.y + fs / 2, r.y + r.h - fs / 2, fs + 2, 2 * fs)]
    return kept


def spread(ls: Sequence[Any], lo: float, hi: float, gap: float, far: float) -> list[int]:
    """Labels' ``y`` moved apart to at least ``gap`` inside ``lo``..``hi``; one that would
    move more than ``far`` left out. The indices kept, by y (labels.ts: spread)."""
    order = sorted(range(len(ls)), key=lambda i: ls[i].y)
    want = [lb.y for lb in ls]
    kept: list[int] = []
    last = -math.inf
    for i in order:
        y = max(want[i], lo, last + gap)
        if y - want[i] > far or y > hi + far:
            continue
        ls[i].y = y
        last = y
        kept.append(i)
    nxt = math.inf
    for i in reversed(kept):
        ls[i].y = min(ls[i].y, hi, nxt - gap)
        nxt = ls[i].y
    return kept


_DIRS = [(1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1)]
_SPOTS = [(ring, d) for ring in (0, 1, 2) for d in _DIRS]
"""The spots tried around a point: ring k at d + 1.2 k label heights."""


def repel(points: list[tuple[int, float, float, float]], h: float, r: Rect,
          d: float) -> list[tuple[int, float, float, tuple[float, float] | None]]:  # fmt: skip
    """Each label (index, x, y, width) at the first spot around its point where it covers
    no label placed before it nor a point, inside the panel; none: left out. Returns
    (index, the text's left, its middle, the point when a leader line goes back)
    (labels.ts: repel)."""
    boxes: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
    size = 32.0

    def keys(x: float, y: float, w: float, hh: float) -> list[tuple[int, int]]:
        return [(i, j) for i in range(math.floor(x / size), math.floor((x + w) / size) + 1)
                for j in range(math.floor(y / size), math.floor((y + hh) / size) + 1)]  # fmt: skip

    def add(x: float, y: float, w: float, hh: float) -> None:
        for k in keys(x, y, w, hh):
            boxes.setdefault(k, []).append((x, y, w, hh))

    def hits(x: float, y: float, w: float, hh: float) -> bool:
        return any(x < bx + bw and bx < x + w and y < by + bh and by < y + hh
                   for k in keys(x, y, w, hh) for bx, by, bw, bh in boxes.get(k, ()))  # fmt: skip

    for _, x, y, _ in points:
        add(x - 2, y - 2, 4, 4)
    out: list[tuple[int, float, float, tuple[float, float] | None]] = []
    for i, x, y, w in points:
        for ring, (dx, dy) in _SPOTS:
            far = d + ring * 1.2 * h
            left = x + far if dx > 0 else x - far - w if dx < 0 else x - w / 2
            top = y + far if dy > 0 else y - far - h if dy < 0 else y - h / 2
            if left < r.x or left + w > r.x + r.w or top < r.y or top + h > r.y + r.h:
                continue
            if hits(left, top, w, h):
                continue
            add(left, top, w, h)
            out.append((i, left, top + h / 2, (x, y) if ring > 0 else None))
            break
    return out


def _draw_rule(svg: _Svg, lr: dict[str, Any], v: _View) -> None:
    r = v.rect
    d = []
    panels = lr.get("panels") or [-1] * len(lr["values"])
    for value, at in zip(lr["values"], panels, strict=True):
        if at >= 0 and at != v.panel:  # from data: its panel's (−1: every panel's)
            continue
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
    if lr.get("repel"):  # each label where it covers no other, nor a point; else left out
        points = []
        for i in range(int(t.starts[v.panel]), int(t.starts[v.panel + 1])):
            x = v.ox + float(t.coords[i, 0]) * v.sx
            y = v.oy + float(t.coords[i, 1]) * v.sy
            if r.x <= x <= r.x + r.w and r.y <= y <= r.y + r.h:
                points.append((i, x, y, text_width(t.labels[i], size)))
        far = max(4.0, abs(lr["dx"]), abs(lr["dy"]))
        for i, x, y, leader in repel(points, size, r, far):
            fill, a = solid
            if t.colors is not None:
                fill, a = _hex(t.colors[i]), t.colors[i][3] / 255
            if leader is not None:
                to = min(max(leader[0], x), x + text_width(t.labels[i], size))
                faint = _alpha("stroke-opacity", a * opacity * 0.5)
                svg.add(f'<path d="M{_n(leader[0])} {_n(leader[1])}L{_n(to)} {_n(y)}" '
                        f'fill="none" stroke="{fill}"{faint}/>')  # fmt: skip
            svg.text(x, y, t.labels[i], fill, size=size,
                     extra=_alpha("fill-opacity", a * opacity))  # fmt: skip
        return
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


def _halo(color: str) -> str:
    """A text's halo, of the panel's colour, so it reads over the marks."""
    return (f' stroke="{color}" stroke-width="3" stroke-linejoin="round" '
            'paint-order="stroke"')  # fmt: skip


def _draw_note(svg: _Svg, n: dict[str, Any], v: _View, th: dict[str, str], fs: float,
               halo: str) -> None:  # fmt: skip
    """A note (``annotate()``), as drawing.ts draws it."""
    r = v.rect
    size = n["size"] if n.get("size") is not None else fs
    lines = n["text"].split("\n")
    lh = size * 1.2
    px = v.ox + n["x"] * v.sx if n["x"] is not None else r.x + 4
    py = v.oy + n["y"] * v.sy if n["y"] is not None else r.y + 4 + lh * len(lines) / 2
    if not (math.isfinite(px) and math.isfinite(py)):
        return
    tx, ty = px + n["dx"], py + n["dy"]
    if n["x"] is not None and n["y"] is not None and (n["dx"] or n["dy"]):
        svg.add(f'<path d="M{_n(px)} {_n(py)}L{_n(tx)} {_n(ty)}" fill="none" '
                f'stroke="{th["muted"]}"/>')  # fmt: skip
        svg.add(f'<circle cx="{_n(px)}" cy="{_n(py)}" r="2" fill="{th["muted"]}"/>')
    color = n.get("color")
    fill = th["text"] if color is None else _hex(color)
    extra = _halo(halo) + ("" if color is None else _alpha("fill-opacity", color[3] / 255))
    anchor = {"left": "start", "center": "middle", "right": "end"}[n["align"]]
    for k, line in enumerate(lines):
        svg.text(tx, ty + (k - (len(lines) - 1) / 2) * lh, line, fill, size=size,
                 anchor=anchor, extra=extra)  # fmt: skip


def _draw_front(svg: _Svg, spec: dict[str, Any], lay: Layout, views: list[_View],
                th: dict[str, str], texts: list[_Texts], brushes: list[Rect],
                marks: list[_Marks] | None = None) -> None:  # fmt: skip
    fs = lay.font_size
    look = look_of(spec)
    rules = [lr for lr in spec["layers"] if lr["type"] == "rule"]
    notes = spec.get("notes") or []
    ends = end_labels(marks or [], views, lambda s: text_width(s, fs), fs)
    halo = th["panel"] if look["panel_fill"] else th["bg"]
    for v in views:
        here = [n for n in notes if n["panels"] is None or v.panel in n["panels"]]
        mine = [e for e in ends if e.panel == v.panel]
        if not rules and not here and not mine and \
                not any(t.starts[v.panel + 1] > t.starts[v.panel] for t in texts):  # fmt: skip
            continue
        svg.open(svg.clip(v.rect))
        for lr in rules:
            _draw_rule(svg, lr, v)
        for t in texts:
            _draw_text(svg, t, v, th)
        for e in mine:
            svg.text(e.x, e.y, e.text, e.color, size=fs, extra=_halo(halo))
        for n in here:
            _draw_note(svg, n, v, th, fs, halo)
        svg.close()

    if look["frame"]:  # just outside the panels (where axis lines go)
        d = "".join(f"M{_n(v.rect.x - 0.5)} {_n(v.rect.y - 0.5)}h{_n(v.rect.w + 1)}"
                    f"v{_n(v.rect.h + 1)}h{_n(-v.rect.w - 1)}Z" for v in views)  # fmt: skip
        if d:
            svg.add(f'<path d="{d}" fill="none" stroke="{th["axis"]}"/>')

    # axes
    line_x = look["axis_lines"] in ("x", "both")
    line_y = look["axis_lines"] in ("y", "both")
    for box, v in zip(lay.panels, views, strict=True):
        r = v.rect
        d: list[str] = []
        if box.show_x:
            end = _label_end(lay, box)
            if line_x:
                d.append(f"M{_n(r.x)} {_n(r.y + r.h + 0.5)}H{_n(r.x + r.w)}")
            last_right = -math.inf
            per = r.w / max(1.0, v.x[1] - v.x[0])  # a band's width
            # left to right (a reversed x: its ticks from high to low), each after the last
            xs = _x_ticks(spec, v, lay.x_labels, fs)
            for value, label in xs[::-1] if v.sx < 0 else xs:
                x = v.ox + value * v.sx
                if x < r.x - 0.5 or x > r.x + r.w + 0.5:
                    continue
                tx = _round(x) + 0.5
                d.append(f"M{_n(tx)} {_n(r.y + r.h)}V{_n(r.y + r.h + 4)}")
                if lay.x_labels == "wrap":  # centred in its band, on two lines when it needs
                    lines = [label] if text_width(label, fs) + 4 <= per else wrap_label(label)
                    for k, line in enumerate(lines):
                        svg.text(x, r.y + r.h + 4 + fs * (0.75 + 1.2 * k), fit(line, per - 4, fs),
                                 th["muted"], anchor="middle")  # fmt: skip
                    continue
                if lay.x_labels == "angle":  # ending at its tick, cut not to leave the plot
                    svg.open(f'transform="translate({_n(x)} {_n(r.y + r.h + 4 + fs * 0.5)}) '
                             'rotate(-45)"')  # fmt: skip
                    svg.text(0, 0, fit(label, min(ANGLE_MAX, (x - 2) / SQRT1_2), fs), th["muted"],
                             anchor="end")  # fmt: skip
                    svg.close()
                    continue
                w = text_width(label, fs)
                if x + w / 2 > end:
                    continue  # next to a panel's axis: not up to its labels
                lx = min(max(x, r.x + w / 2), r.x + r.w - w / 2 + 6)
                if lx - w / 2 < last_right + 6:
                    continue
                svg.text(lx, r.y + r.h + 4 + fs * 0.75, label, th["muted"], anchor="middle")
                last_right = lx + w / 2
        if box.show_y:
            if line_y:
                d.append(f"M{_n(r.x - 0.5)} {_n(r.y)}V{_n(r.y + r.h)}")
            last_top = math.inf
            ys = _y_ticks(spec, v)  # bottom to top (a reversed y: from high to low)
            for value, label in ys[::-1] if v.sy > 0 else ys:
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
    strip = _filled_strip if look["strip_fill"] else _flat_strip
    for box in lay.panels:
        if box.strip is not None:
            strip(svg, th, look, Strip(box.strip, box.label, False, pin=box.pinned), box.note)
    for s in lay.strips:
        strip(svg, th, look, s)

    # axis titles
    if lay.x_title and look["x_title"] == "end":
        svg.text(*lay.x_title, f"{spec['x']['title']} →", th["muted"], anchor="end")
    elif lay.x_title:
        svg.text(*lay.x_title, spec["x"]["title"], th["muted"], anchor="middle")
    if lay.y_title and look["y_title"] == "side":
        x, y = lay.y_title
        svg.open(f'transform="translate({_n(x)} {_n(y)}) rotate(-90)"')
        svg.text(0, 0, spec["y"]["title"], th["muted"], anchor="middle")
        svg.close()
    elif lay.y_title:
        svg.text(*lay.y_title, f"↑ {spec['y']['title']}", th["muted"])

    for b in brushes:
        svg.rect(b, th["accent"], ' fill-opacity="0.07"')
        edge = Rect(_round(b.x) + 0.5, _round(b.y) + 0.5, _round(b.w) - 1, _round(b.h) - 1)
        svg.add(f'<rect x="{_n(edge.x)}" y="{_n(edge.y)}" width="{_n(edge.w)}" '
                f'height="{_n(edge.h)}" fill="none" stroke="{th["accent"]}" '
                'stroke-opacity="0.8"/>')  # fmt: skip


PIN_W = 11
"""The room a pin takes before a pinned panel's label (px)."""
GHOST = (184, 190, 198)
"""The compared panel's marks in the others: the context grey, at a share of their opacity."""
GHOST_ALPHA = 0.7


def _draw_pin(svg: _Svg, x: float, y: float, color: str) -> None:
    """A pin (a pinned panel's, in its strip): its left at x, centred on y (drawing.ts)."""
    svg.add(f'<circle cx="{_n(x + 4)}" cy="{_n(y - 1.5)}" r="3" fill="{color}"/>')
    svg.add(f'<path d="M{_n(x + 4)} {_n(y + 1.5)}V{_n(y + 5.5)}" stroke="{color}" '
            'stroke-width="1.5" stroke-linecap="round"/>')  # fmt: skip


def _filled_strip(svg: _Svg, th: dict[str, str], look: dict[str, Any], s: Strip,
                  note: str = "") -> None:  # fmt: skip
    """A filled strip: its label centred or at the left (a row's on its side), a paged wrap's
    sorted value whole at the right (drawing.ts: filledStrip)."""
    rect, label = s.rect, s.label
    bold = look["strip_bold"]
    svg.rect(rect, th["strip"])
    if s.pin:  # a pin, then the label in the room left
        _draw_pin(svg, rect.x + STRIP_PAD, rect.y + rect.h / 2, th["accent"])
        rect = Rect(rect.x + PIN_W, rect.y, rect.w - PIN_W, rect.h)
    svg.open(svg.clip(rect))
    cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
    if s.vertical:
        svg.open(f'transform="translate({_n(cx)} {_n(cy)}) rotate(90)"')
        svg.text(0, 0, fit(label, rect.h - 6, svg.fs, bold=bold), th["strip_text"], anchor="middle",
                 bold=bold)  # fmt: skip
        svg.close()
    elif note:  # the name at the left, cut to leave the value whole at the right
        w = text_width(note, svg.fs, bold=bold)
        svg.text(rect.x + rect.w - STRIP_PAD, cy + 0.5, note, th["strip_text"], anchor="end",
                 bold=bold)  # fmt: skip
        svg.text(rect.x + STRIP_PAD, cy + 0.5,
                 fit(label, rect.w - 3 * STRIP_PAD - w, svg.fs, bold=bold), th["strip_text"],
                 bold=bold)  # fmt: skip
    elif look["strip_align"] == "left" or s.side == "right":
        svg.text(rect.x + STRIP_PAD, cy + 0.5,
                 fit(label, rect.w - 2 * STRIP_PAD, svg.fs, bold=bold), th["strip_text"],
                 bold=bold)  # fmt: skip
    else:
        svg.text(cx, cy + 0.5, fit(label, rect.w - 6, svg.fs, bold=bold), th["strip_text"],
                 anchor="middle", bold=bold)  # fmt: skip
    svg.close()


def _flat_strip(svg: _Svg, th: dict[str, str], look: dict[str, Any], s: Strip,
                note: str = "") -> None:  # fmt: skip
    """A strip with nothing behind it: the label as a title, centred or at the left (a row's
    level at the left, or on its side); one spanning several panels underlined (a row's: a
    line at its left); a paged wrap's sorted value at the right in the muted colour, the
    name keeping at least half the room (drawing.ts: flatStrip)."""
    rect, label = s.rect, s.label
    bold = look["strip_bold"]
    right = s.side == "right"
    if s.pin:
        _draw_pin(svg, rect.x + 1, rect.y + rect.h / 2, th["accent"])
        rect = Rect(rect.x + PIN_W, rect.y, rect.w - PIN_W, rect.h)
    if s.span:
        d = (f"M{_n(rect.x + 0.5)} {_n(rect.y)}V{_n(rect.y + rect.h)}" if right
             else f"M{_n(rect.x)} {_n(rect.y + rect.h - 0.5)}H{_n(rect.x + rect.w)}")  # fmt: skip
        svg.add(f'<path d="{d}" fill="none" stroke="{th["axis"]}"/>')
    svg.open(svg.clip(rect))
    if s.vertical:
        cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
        svg.open(f'transform="translate({_n(cx)} {_n(cy)}) rotate(90)"')
        svg.text(0, 0, fit(label, rect.h - 6, svg.fs, bold=bold), th["text"], anchor="middle",
                 bold=bold)  # fmt: skip
        svg.close()
        svg.close()
        return
    x = rect.x + (STRIP_PAD if right else 1)
    y = rect.y + rect.h / 2 + 0.5
    room = rect.x + rect.w - x - 2
    if note:
        shown = fit(note, max(0.0, room / 2), svg.fs)
        svg.text(rect.x + rect.w - 1, y, shown, th["muted"], anchor="end")
        room -= text_width(shown, svg.fs) + 2 * STRIP_PAD
    if look["strip_align"] == "center" and not right and not note:
        svg.text(rect.x + rect.w / 2, y, fit(label, rect.w - 6, svg.fs, bold=bold), th["text"],
                 anchor="middle", bold=bold)  # fmt: skip
    else:
        svg.text(x, y, fit(label, room, svg.fs, bold=bold), th["text"], bold=bold)
    svg.close()


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
    size: float = FONT_SIZE  # its text's (the page's)
    glyph: dict[str, Any] | None = None
    """An item's shape, dash or size (channels.ts: Glyph); None: a square of its colour."""

    @property
    def width(self) -> float:
        bold = self.kind == "title" or self.state == "on"
        if self.kind == "gradient":
            return 90.0
        w = text_width(self.label, self.size, bold=bold)
        return w + self.swatch[0] + 4 if self.kind == "item" else w

    @property
    def swatch(self) -> tuple[float, float]:
        """The swatch's width and height (channels.ts: glyphBox)."""
        g = self.glyph or {}
        if "dash" in g:
            return 22.0, 10.0
        if "size" in g:
            side = max(10.0, g["size"] + 2)
            return side, side
        return 10.0, 10.0


def _legend_label(v: float) -> str:
    """As the widget writes a number legend's ends (view.ts: fmt)."""
    if abs(v) >= 1e4 or (abs(v) < 1e-2 and v != 0):
        mantissa, exp = f"{v:.2e}".split("e")
        return f"{mantissa}e{'+' if int(exp) >= 0 else '-'}{abs(int(exp))}"
    return _js(_round(v * 100) / 100)


LEGEND_ROWS = 20
"""The most entries a legend shows (the page: then a search for the rest)."""


def _legend_groups(spec: dict[str, Any], brush: dict[str, Any] | None) -> list[list[_Entry]]:
    chosen = (brush or {}).get("legend") or None
    size = look_of(spec)["font_size"]
    groups = []
    for index, lg in enumerate(spec["legends"]):
        if lg.get("direct"):  # its levels name the lines at their ends instead
            continue
        entries = [_Entry("title", lg["title"], size=size)]
        if lg["kind"] != "number":  # an entry each (a stepped scale's ranges; shapes, sizes)
            labels = lg["labels"]
            for i, (label, color) in enumerate(zip(labels[:LEGEND_ROWS], lg["colors"],
                                                   strict=False)):  # fmt: skip
                state = ""
                if chosen and chosen.get("index") == index and chosen.get("levels"):
                    state = "on" if i in chosen["levels"] else "off"
                elif (
                    chosen
                    and chosen.get("index") == index
                    and chosen.get("range")
                    and lg.get("breaks")
                ):  # a stepped scale's bins: those in the range
                    a, b = sorted(chosen["range"])
                    inside = lg["breaks"][i] < b and lg["breaks"][i + 1] > a
                    state = "on" if inside else "off"
                entries.append(_Entry("item", label, color, state=state, size=size,
                                      glyph=_glyph(lg, i)))  # fmt: skip
            if len(labels) > LEGEND_ROWS:  # as the page shows a long legend: the first ones
                entries.append(_Entry("text", f"{len(labels) - LEGEND_ROWS} more", size=size))
        else:
            end = number_format(lg["format"]) if lg.get("format") else _legend_label
            entries += [_Entry("text", end(lg.get("lo", 0)), size=size),
                        _Entry("gradient", colors=tuple(lg["colors"]), size=size),
                        _Entry("text", end(lg.get("hi", 1)), size=size)]  # fmt: skip
        groups.append(entries)
    return groups


def _glyph(lg: dict[str, Any], i: int) -> dict[str, Any] | None:
    """A legend entry's shape, dash or size (view.ts: legendSwatch)."""
    glyph: dict[str, Any] = {}
    if lg.get("shapes"):
        glyph["shape"] = lg["shapes"][i]
    if lg.get("dashes"):
        glyph["dash"] = lg["dashes"][i]
        glyph["line_width"] = lg.get("line_width") or 1.5
    if lg.get("sizes"):
        glyph["size"] = lg["sizes"][i]
    return glyph or None


def _draw_glyph(svg: _Svg, e: _Entry, x: float, y: float) -> None:
    """A legend entry's shape, dash or size, its box's top left at x, y (channels.ts:
    drawGlyph)."""
    g = e.glyph or {}
    w, h = e.swatch
    color = escape(e.color)
    if "dash" in g:
        lw = max(1.0, min(4.0, g["line_width"]))
        dash = dash_pattern(g["dash"], lw)
        dashes = f' stroke-dasharray="{" ".join(_n(v) for v in dash)}"' if dash else ""
        line = f"M{_n(x + lw / 2)} {_n(y + h / 2)}H{_n(x + w - lw / 2)}"
        svg.add(f'<path d="{line}" fill="none" stroke="{color}" stroke-width="{_n(lw)}" '
                f'stroke-linecap="round"{dashes}/>')  # fmt: skip
    if "shape" in g or "size" in g:
        r = g["size"] / 2 if "size" in g else 3.0 if "dash" in g else 4.0
        d = shape_paths(np.array([g.get("shape", 0)]), np.array([x + w / 2]),
                        np.array([y + h / 2]), np.array([r]))[0]  # fmt: skip
        svg.add(f'<path d="{d}" fill="{color}"/>')


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
    line_h = entries[0].size * LINE
    placed = []
    width = 0.0
    for n, line in enumerate(lines):
        for i, x in line:
            placed.append(_Placed(entries[i], x, n * (line_h + 2)))
            width = max(width, x + entries[i].width)
    return placed, width, len(lines) * line_h + (len(lines) - 1) * 2


def _column(entries: list[_Entry]) -> tuple[list[_Placed], float, float]:
    """A category group in a list: its title, then an entry a line."""
    placed, y = [], 0.0
    for n, e in enumerate(entries):
        placed.append(_Placed(e, 0.0, y))
        y += e.size * LINE + (4 if n == 0 else 3)
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


def legend_width(groups: list[list[_Entry]], most: float) -> float:
    """A legend right of the plot: as wide as its widest group set as a list (a category's
    entries a line each), its padding included, at most ``most``."""
    widths = [(_column(g) if any(e.kind == "item" for e in g) else _wrapped(g, most))[1]
              for g in groups]  # fmt: skip
    return min(most, math.ceil(max(widths, default=0.0)) + 8)


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
        mid = y + e.size * LINE / 2
        if e.kind == "title":
            svg.text(x, mid, e.label, th["text"], size=e.size, bold=True)
        elif e.kind == "text":
            svg.text(x, mid, e.label, th["muted"], size=e.size)
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
            sw, sh = e.swatch
            if e.glyph:
                _draw_glyph(svg, e, x, mid - sh / 2)
            else:
                svg.add(f'<rect x="{_n(x)}" y="{_n(mid - 5)}" width="10" height="10" rx="2" '
                        f'fill="{escape(e.color)}"/>')  # fmt: skip
            on = e.state == "on"
            svg.text(x + sw + 4, mid, e.label, th["text"] if on else th["muted"], size=e.size,
                     bold=on)  # fmt: skip
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


def _note_sorted(spec: dict[str, Any], lay: Layout, paging: Paging,
                 pins: Sequence[int] = ()) -> None:  # fmt: skip
    """Each strip's value of the statistic sorted by, at its right, and a pinned panel's
    pin (``noteSorted``)."""
    for box in lay.panels:
        box.pinned = box.index in pins
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
    # the page's text: the header's (its title 1.15 times as big, beside the 24 px buttons),
    # the subtitle's and the caption's (widget.css .atr-header, .atr-subtitle, .atr-caption,
    # these wrapped to the width less their padding)
    size = look_of(spec)["font_size"]
    title_size = size * TITLE
    header = max(HEADER, 2 + title_size * LINE) if spec["title"] else 0
    subtitle = (
        wrap_text(spec.get("subtitle") or "", width - 16, size) if spec.get("subtitle") else []
    )
    caption = (
        wrap_text(spec.get("caption") or "", width - 16, size * CAPTION)
        if spec.get("caption")
        else []
    )
    sub_h = len(subtitle) * size * LINE + 4 if subtitle else 0
    cap_line = size * CAPTION * LINE
    cap_h = len(caption) * cap_line + 8 if caption else 0
    top = header + sub_h
    stage_h = None if height is None else height - top - cap_h
    if stage_h is not None and stage_h < 60:
        raise ValueError(f"height {height} leaves no room for the plot")

    names = [panel_name(spec, i) for i in range(len(spec["panels"]))]
    focus_name = plot.focused
    focused = names.index(focus_name) if focus_name in names else None
    brush = plot._current_selection()
    position = spec.get("legend_position") or "auto"
    groups = [] if position == "none" else _legend_groups(spec, brush)

    placed: list[_Placed] = []
    legend_h = 0.0
    page = _page(plot, spec)

    def focus_height(legend_h: float) -> float:
        # with a shape (aspect): at most FOCUS_MAX high, the layout keeping the shape
        most = FOCUS_MAX if panel_shape(spec) else layout(spec, width).height
        return stage_h - legend_h if stage_h is not None else max(FOCUS_MIN, min(most, FOCUS_MAX))

    def plot_layout(w: float, legend_h: float) -> Layout:
        if focused is not None:
            return layout(spec, w, focus_height(legend_h), focused)
        return layout(spec, w, None if stage_h is None else stage_h - legend_h, page=page)

    right = None
    above = position == "top" and bool(groups)
    if above:  # over the panels, under the title, as wide as the plot
        placed, legend_h = _legend_below(groups, width)
        lay = plot_layout(width, legend_h)
    elif position == "right" and groups:
        # a column right of the plot, the plot narrowed for it (layout as wide as the rest)
        lw = legend_width(groups, width * RIGHT_MOST)
        lay = plot_layout(width - lw, 0.0)
        right = _legend_inset(groups, Rect(width - lw, 0, lw, lay.height))
        placed = right or []
    if above or right is not None:
        pass  # placed
    elif focused is None:
        lay = layout(spec, width, stage_h, page=page)
        spare = lay.spare if position == "auto" else None
        inset = _legend_inset(groups, spare) if groups and spare is not None else None
        if inset is not None:
            placed = inset
        elif groups:
            placed, legend_h = _legend_below(groups, width)
            if stage_h is not None:
                lay = layout(spec, width, stage_h - legend_h, page=page)
    else:
        if groups:
            placed, legend_h = _legend_below(groups, width)
        lay = plot_layout(width, legend_h)
    if focused is None:
        pages = spec.get("pages") or {}
        pins = pins_of(plot._pin_indices(pages), pages["rows"] * pages["cols"]) if pages else []
        _note_sorted(spec, lay, plot.paging, pins)
    inset_legend = bool(placed) and legend_h == 0

    total = _round(top + lay.height + legend_h + cap_h)  # as the page rounds the plot's box
    svg = _Svg(width, total if height is None else float(height), lay.font_size)
    svg.title, svg.description = spec.get("title") or "", spec.get("description") or ""
    svg.add(f'<rect width="100%" height="100%" fill="{th["bg"]}"/>')
    if header:
        svg.text(8, 1 + header / 2, fit(spec["title"], width - 16, title_size), th["text"],
                 size=title_size, bold=True)  # fmt: skip
    for k, line in enumerate(subtitle):
        svg.text(8, header + (k + 0.5) * size * LINE, line, th["muted"], size=size)
    plot_top = top + legend_h if above else top
    svg.open(f'transform="translate(0 {_n(plot_top)})"' if plot_top else 'class="plot"')

    views = _views(spec, lay, shown)
    marks, texts = _scene(spec, buffers)
    base_x = np.array([p["x"][0] for p in spec["panels"]], dtype=np.float64)
    base_y = np.array([p["y"][0] for p in spec["panels"]], dtype=np.float64)
    _draw_back(svg, spec, views, th)
    if focused is None and page == []:  # as the browser's .atr-empty
        svg.text(width / 2, lay.height * 0.4, "No panel matches the filters", th["muted"],
                 size=size, anchor="middle", baseline="top")  # fmt: skip

    ref = names.index(plot.compared) if plot.compared in names else None
    if ref is not None:  # the compared panel's marks, grey, in every other (view.ts)
        for layer in marks:
            if layer.spec.get("context"):
                continue
            grey = np.empty_like(layer.colors)
            grey[:, :3] = GHOST
            grey[:, 3] = np.round(layer.colors[:, 3] * GHOST_ALPHA).astype(np.uint8)
            _draw_marks(svg, layer, layer.coords, grey, views, base_x, base_y, source=ref)
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
    _draw_front(svg, spec, lay, views, th, texts, rects, marks)
    if inset_legend:
        _draw_legend(svg, placed, 0, th)
    svg.close()
    if placed and not inset_legend:
        _draw_legend(svg, placed, top if above else top + lay.height, th)
    for k, line in enumerate(caption):
        y = top + lay.height + legend_h + 2 + (k + 0.5) * cap_line
        svg.text(8, y, line, th["muted"], size=size * CAPTION)
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
