"""Formats for axes and legends (``Trellis.format``): numbers by d3-format strings
(``",.0f"``, ``".1%"``, ``"$,.2s"``), times by strftime strings (``"%b %Y"``), in UTC.

The browser formats with ``js/src/core/format.ts``; this is the same, so images drawn in
Python read the same, and a format is checked when it is given. Numbers round as
JavaScript's ``toFixed``, ``toPrecision`` and ``toExponential`` do (halves away from zero),
not as Python's ``format`` (halves to even).
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_SPEC = re.compile(
    r"^(?:(.)?([<>=^]))?([+\-( ])?([$#])?(0)?(\d+)?(,)?(\.\d+)?(~)?([bdeEfgGoprsxX%])?$"
)
MINUS = "−"
_PREFIXES = ["y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T", "P", "E",
             "Z", "Y"]  # fmt: skip


@dataclass(frozen=True)
class _Spec:
    fill: str
    align: str
    sign: str
    symbol: str
    zero: bool
    width: int
    comma: bool
    precision: int | None
    trim: bool
    type: str


def _parse(spec: str) -> _Spec:
    m = _SPEC.match(spec)
    if not m:
        raise ValueError(f"invalid number format {spec!r}: give a d3-format string such as "
                         "',.0f', '.1%' or '.3s'")  # fmt: skip
    zero = m.group(5) == "0"
    return _Spec(
        fill="0" if zero and not m.group(2) else (m.group(1) or " "),
        align="=" if zero and not m.group(2) else (m.group(2) or ">"),
        sign=m.group(3) or "-",
        symbol=m.group(4) or "",
        zero=zero,
        width=int(m.group(6)) if m.group(6) else 0,
        comma=m.group(7) == ",",
        precision=int(m.group(8)[1:]) if m.group(8) else None,
        trim=m.group(9) == "~",
        type=m.group(10) or "",
    )


# ---- JavaScript's number to string ----------------------------------------------------------


def _quantum(digits: int) -> Decimal:
    return Decimal(1).scaleb(-digits)


def to_fixed(x: float, digits: int) -> str:
    """``x.toFixed(digits)`` for ``x >= 0``."""
    if x >= 1e21:
        return _js_string(x)
    return f"{Decimal(x).quantize(_quantum(digits), rounding=ROUND_HALF_UP):f}"


def _exponent_parts(x: float, digits: int) -> tuple[str, int]:
    """``x`` (>= 0) in ``digits`` significant digits: its digits and decimal exponent."""
    if x == 0:
        return "0" * digits, 0
    d = Decimal(x)
    e = d.adjusted()
    q = d.scaleb(-e).quantize(_quantum(digits - 1), rounding=ROUND_HALF_UP)
    if q >= 10:  # 9.99 → 10.0: one more decade
        e += 1
        q = d.scaleb(-e).quantize(_quantum(digits - 1), rounding=ROUND_HALF_UP)
    return f"{q:f}".replace(".", ""), e


def to_exponential(x: float, digits: int) -> str:
    """``x.toExponential(digits)`` for ``x >= 0``."""
    c, e = _exponent_parts(x, digits + 1)
    mantissa = c[0] + ("." + c[1:] if len(c) > 1 else "")
    return f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def to_precision(x: float, digits: int) -> str:
    """``x.toPrecision(digits)`` for ``x >= 0``."""
    c, e = _exponent_parts(x, digits)
    if e < -6 or e >= digits:
        mantissa = c[0] + ("." + c[1:] if len(c) > 1 else "")
        return f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"
    if e >= 0:
        return c[: e + 1] + ("." + c[e + 1 :] if len(c) > e + 1 else "")
    return "0." + "0" * (-e - 1) + c


def _js_string(x: float) -> str:
    """``String(x)`` for a large ``x >= 1e21``: ``1e+21``."""
    mantissa, exp = repr(float(x)).split("e")
    mantissa = mantissa.removesuffix(".0")
    return f"{mantissa}e{'+' if int(exp) >= 0 else '-'}{abs(int(exp))}"


def _radix(n: int, base: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    out = ""
    while n:
        n, r = divmod(n, base)
        out = digits[r] + out
    return out


def _js_number(text: str) -> float:
    """``Number(text)``: NaN for what isn't a decimal number (hex digits: ``"4d3"``)."""
    try:
        return float(text)
    except ValueError:
        return math.nan


def _js_round(x: float) -> int:
    """``Math.round``: halves up."""
    return math.floor(x + 0.5)


# ---- d3-format --------------------------------------------------------------------------------


def _trim(s: str) -> str:
    s = re.sub(r"(\.\d*?)0+(?=$|e)", r"\1", s, count=1)
    return re.sub(r"\.(?=$|e)", "", s, count=1)


def _decimal_parts(x: float, digits: int) -> tuple[str, int]:
    """d3's formatDecimalParts: the digits of ``x`` in ``digits`` significant ones, and its
    exponent (``x.toExponential(digits - 1)``)."""
    m, e = to_exponential(x, max(0, digits - 1)).split("e")
    return m.replace(".", ""), int(e)


def _rounded(x: float, digits: int) -> str:
    c, e = _decimal_parts(x, digits)
    if e < 0:
        return "0." + "0" * (-e - 1) + c
    if len(c) > e + 1:
        return c[: e + 1] + "." + c[e + 1 :]
    return c + "0" * (e - len(c) + 1)


def _prefixed(x: float, digits: int) -> tuple[str, str]:
    c, e = _decimal_parts(x, digits)
    k = max(-8, min(8, math.floor(e / 3)))
    i = e - k * 3 + 1
    n = len(c)
    if i == n:
        out = c
    elif i > n:
        out = c + "0" * (i - n)
    elif i > 0:
        out = c[:i] + "." + c[i:]
    else:
        out = "0." + "0" * (-i) + _decimal_parts(x, max(0, digits + i - 1))[0]
    return out, _PREFIXES[8 + k]


def _body(x: float, t: str, p: int | None) -> tuple[str, str]:
    if t in ("e", "E"):
        s = to_exponential(x, 6 if p is None else p)
        return (s.upper() if t == "E" else s), ""
    if t == "f":
        return to_fixed(x, 6 if p is None else p), ""
    if t in ("g", "G"):
        s = to_precision(x, max(1, 6 if p is None else p))
        return (s.upper() if t == "G" else s), ""
    if t == "r":
        return _rounded(x, max(1, 6 if p is None else p)), ""
    if t == "%":
        return to_fixed(x * 100, 6 if p is None else p), "%"
    if t == "p":
        return _rounded(x * 100, max(1, 6 if p is None else p)), "%"
    if t == "s":
        return _prefixed(x, max(1, 6 if p is None else p))
    n = _js_round(x)
    if t == "d":
        return str(n), ""
    base = {"b": 2, "o": 8, "x": 16, "X": 16}[t]
    s = _radix(n, base)
    return (s.upper() if t == "X" else s), ""


def _group(value: str, width: float) -> str:
    """Digits in groups of three, as d3 groups them: from the right, until ``width``."""
    parts: list[str] = []
    i = len(value)
    length = 0
    g = 3
    while i > 0 and g > 0:
        if length + g + 1 > width:
            g = max(1, int(width - length))
        i -= g
        parts.append(value[max(0, i) : i + g])
        length += g + 1
        if length > width:
            break
        g = 3
    return ",".join(reversed(parts))


def number_format(spec: str) -> Callable[[float], str]:
    """A function writing numbers as the d3-format specifier ``spec`` says (format.ts:
    numberFormat); a ``ValueError`` for one it can't read."""
    s = _parse(spec)
    t = s.type or "g"
    trim = s.trim or not s.type
    p = s.precision if s.type else (12 if s.precision is None else s.precision)
    prefix = "$" if s.symbol == "$" else ({"b": "0b", "o": "0o", "x": "0x", "X": "0x"}.get(t, "")
                                          if s.symbol == "#" else "")  # fmt: skip
    decimal = t in "efgEGprs%"

    def fmt(x: float) -> str:
        x = float(x)
        if not math.isfinite(x):
            return "NaN" if math.isnan(x) else "∞" if x > 0 else f"{MINUS}∞"
        negative = x < 0 or math.copysign(1, x) < 0
        value, unit = _body(abs(x), t, p)
        if trim:
            value = _trim(value)
        if negative and _js_number(value) == 0 and s.sign != "+":
            negative = False
        sign = "" if s.sign in ("-", "(") else s.sign
        head = ("(" if s.sign == "(" else MINUS) if negative else sign
        head += prefix
        tail = unit + (")" if negative and s.sign == "(" else "")
        if decimal:
            m = re.search(r"[^0-9]", value)
            if m:
                tail = value[m.start() :] + tail
                value = value[: m.start()]
        if s.comma and not s.zero:
            value = _group(value, math.inf)
        length = len(head) + len(value) + len(tail)
        padding = s.fill * (s.width - length) if length < s.width else ""
        if s.comma and s.zero:
            value = _group(padding + value, s.width - len(tail) if padding else math.inf)
            padding = ""
        if s.align == "<":
            return head + value + tail + padding
        if s.align == "=":
            return head + padding + value + tail
        if s.align == "^":
            half = len(padding) >> 1
            return padding[:half] + head + value + tail + padding[half:]
        return padding + head + value + tail

    return fmt


# ---- strftime -----------------------------------------------------------------------------------

_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]  # fmt: skip
_DIRECTIVES = "aAbBdeHIjLmMpSyYZ%"


def time_format(spec: str) -> Callable[[float], str]:
    """A function writing times (ms since 1970, UTC) as the strftime string ``spec`` says
    (format.ts: timeFormat): %Y %y %m %B %b %d %e %j %a %A %H %I %p %M %S %L %Z %%, padded
    with zeros, or as ``%-d`` (none), ``%_d`` (spaces), ``%0d`` (zeros)."""
    parts: list[str | tuple[str, str | None]] = []
    i = 0
    while i < len(spec):
        if spec[i] != "%":
            parts.append(spec[i])
            i += 1
            continue
        i += 1
        pad: str | None = None
        c = spec[i] if i < len(spec) else ""
        if c in ("-", "_", "0"):
            pad = {"-": "", "_": " ", "0": "0"}[c]
            i += 1
            c = spec[i] if i < len(spec) else ""
        if not c or c not in _DIRECTIVES:
            raise ValueError(f"invalid time format {spec!r}: directives are "
                             f"{', '.join('%' + d for d in _DIRECTIVES)}")  # fmt: skip
        parts.append((c, pad))
        i += 1

    def fmt(t: float) -> str:
        d = dt.datetime(1970, 1, 1, tzinfo=dt.UTC) + dt.timedelta(milliseconds=math.trunc(t))
        return "".join(p if isinstance(p, str) else _directive(d, *p) for p in parts)

    return fmt


def _padded(n: int, width: int, pad: str | None, fallback: str = "0") -> str:
    fill = fallback if pad is None else pad
    s = str(n)
    return s if fill == "" else s.rjust(width, fill)


def _directive(d: dt.datetime, c: str, pad: str | None) -> str:
    weekday = (d.weekday() + 1) % 7  # Sunday first, as getUTCDay
    if c == "a":
        return _DAYS[weekday][:3]
    if c == "A":
        return _DAYS[weekday]
    if c == "b":
        return _MONTHS[d.month - 1][:3]
    if c == "B":
        return _MONTHS[d.month - 1]
    if c == "d":
        return _padded(d.day, 2, pad)
    if c == "e":
        return _padded(d.day, 2, pad, " ")
    if c == "H":
        return _padded(d.hour, 2, pad)
    if c == "I":
        return _padded(d.hour % 12 or 12, 2, pad)
    if c == "j":
        return _padded(d.timetuple().tm_yday, 3, pad)
    if c == "L":
        return _padded(d.microsecond // 1000, 3, pad)
    if c == "m":
        return _padded(d.month, 2, pad)
    if c == "M":
        return _padded(d.minute, 2, pad)
    if c == "p":
        return "AM" if d.hour < 12 else "PM"
    if c == "S":
        return _padded(d.second, 2, pad)
    if c == "y":
        return _padded(d.year % 100, 2, pad)
    if c == "Y":
        return _padded(d.year, 4, pad)
    if c == "Z":
        return "+0000"
    return "%"


def axis_format(kind: str, spec: str | None) -> Callable[[float], str] | None:
    """A formatter for an axis's values (format.ts: axisFormat); None: none given."""
    if not spec or kind == "band":
        return None
    return time_format(spec) if kind == "time" else number_format(spec)
