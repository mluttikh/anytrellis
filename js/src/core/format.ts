// Formats given from Python (`Trellis.format`): numbers by d3-format strings (",.0f",
// ".1%", "$,.2s", "+.3~g", ...), times by strftime strings ("%b %Y", "%-d %b %H:%M"), in
// UTC as the axis is. formats.py does the same, so images drawn in Python read the same.

/** A d3-format specifier, parsed: [[fill]align][sign][symbol][0][width][,][.precision][~][type]. */
interface Specifier {
  fill: string;
  align: string;
  sign: string;
  symbol: string;
  zero: boolean;
  width: number;
  comma: boolean;
  precision: number | null;
  trim: boolean;
  type: string;
}

const SPEC = /^(?:(.)?([<>=^]))?([+\-( ])?([$#])?(0)?(\d+)?(,)?(\.\d+)?(~)?([bdeEfgGoprsxX%])?$/;
const MINUS = "−";
const PREFIXES = ["y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T", "P", "E", "Z", "Y"];

function parse(spec: string): Specifier {
  const m = SPEC.exec(spec);
  if (!m) throw new Error(`invalid number format: ${spec}`);
  const zero = m[5] === "0";
  return {
    fill: zero && !m[2] ? "0" : (m[1] ?? " "),
    align: zero && !m[2] ? "=" : (m[2] ?? ">"),
    sign: m[3] ?? "-",
    symbol: m[4] ?? "",
    zero,
    width: m[6] ? Number(m[6]) : 0,
    comma: m[7] === ",",
    precision: m[8] ? Number(m[8].slice(1)) : null,
    trim: m[9] === "~",
    type: m[10] ?? "",
  };
}

/** Trailing zeros of the fraction, and a lone point, cut ("1.500" → "1.5", "2.0e+3" → "2e+3"). */
function trimZeros(s: string): string {
  return s.replace(/(\.\d*?)0+(?=$|e)/, "$1").replace(/\.(?=$|e)/, "");
}

/** The digits of `x` rounded to `digits` significant ones, and its decimal exponent
 * (d3's formatDecimalParts: 1234.5 at 3 → ["123", 3]). */
function decimalParts(x: number, digits: number): [string, number] {
  const [m, e] = x.toExponential(Math.max(0, digits - 1)).split("e");
  return [m.replace(".", ""), Number(e)];
}

/** The number in `digits` significant digits, in fixed notation (d3's "r"). */
function rounded(x: number, digits: number): string {
  const [c, e] = decimalParts(x, digits);
  if (e < 0) return `0.${"0".repeat(-e - 1)}${c}`;
  if (c.length > e + 1) return `${c.slice(0, e + 1)}.${c.slice(e + 1)}`;
  return c + "0".repeat(e - c.length + 1);
}

/** The number in `digits` significant digits over an SI prefix, and the prefix (d3's "s"). */
function prefixed(x: number, digits: number): [string, string] {
  const [c, e] = decimalParts(x, digits);
  const k = Math.max(-8, Math.min(8, Math.floor(e / 3)));
  const i = e - k * 3 + 1;
  const n = c.length;
  const out = i === n ? c : i > n ? c + "0".repeat(i - n) : i > 0 ? `${c.slice(0, i)}.${c.slice(i)}` : `0.${"0".repeat(-i)}${decimalParts(x, Math.max(0, digits + i - 1))[0]}`;
  return [out, PREFIXES[8 + k]];
}

function body(x: number, s: Specifier): [string, string] {
  const p = s.precision;
  switch (s.type) {
    case "e":
    case "E": {
      const t = x.toExponential(p ?? 6);
      return [s.type === "E" ? t.toUpperCase() : t, ""];
    }
    case "f":
      return [x.toFixed(p ?? 6), ""];
    case "g":
    case "G": {
      const t = x.toPrecision(Math.max(1, p ?? 6));
      return [s.type === "G" ? t.toUpperCase() : t, ""];
    }
    case "r":
      return [rounded(x, Math.max(1, p ?? 6)), ""];
    case "%":
      return [(x * 100).toFixed(p ?? 6), "%"];
    case "p":
      return [rounded(x * 100, Math.max(1, p ?? 6)), "%"];
    case "s":
      return prefixed(x, Math.max(1, p ?? 6));
    case "d": {
      const r = Math.round(x);
      return [r >= 1e21 ? BigInt(r).toString() : r.toString(10), ""];
    }
    case "b":
      return [Math.round(x).toString(2), ""];
    case "o":
      return [Math.round(x).toString(8), ""];
    case "x":
      return [Math.round(x).toString(16), ""];
    case "X":
      return [Math.round(x).toString(16).toUpperCase(), ""];
    default:
      return [x.toPrecision(Math.max(1, p ?? 6)), ""];
  }
}

/** Digits in groups of three, as d3 groups them: from the right, until `width` is reached. */
function group(value: string, width: number): string {
  const t: string[] = [];
  let i = value.length;
  let length = 0;
  let g = 3;
  while (i > 0 && g > 0) {
    if (length + g + 1 > width) g = Math.max(1, width - length);
    t.push(value.substring((i -= g), i + g));
    if ((length += g + 1) > width) break;
    g = 3;
  }
  return t.reverse().join(",");
}

/** A function writing numbers as a d3-format specifier says (throws on one it can't read). */
export function numberFormat(spec: string): (x: number) => string {
  const s = parse(spec);
  // no type: d3's default, up to 12 significant digits, trailing zeros cut
  const type = s.type || "g";
  const trim = s.trim || !s.type;
  const precision = s.type ? s.precision : (s.precision ?? 12);
  const f: Specifier = { ...s, type, precision };
  const prefix = s.symbol === "$" ? "$" : s.symbol === "#" ? (({ b: "0b", o: "0o", x: "0x", X: "0x" }) as Record<string, string>)[type] ?? "" : "";
  const decimal = "efgEGprs%".includes(type); // its digits may run on past a point
  return (x: number): string => {
    if (!Number.isFinite(x)) return Number.isNaN(x) ? "NaN" : x > 0 ? "∞" : `${MINUS}∞`;
    let negative = x < 0 || Object.is(x, -0);
    let [value, unit] = body(Math.abs(x), f);
    if (trim) value = trimZeros(value);
    // what reads as zero has no minus (-0.001 at ".2f": "0.00")
    if (negative && Number(value) === 0 && s.sign !== "+") negative = false;
    const head = (negative ? (s.sign === "(" ? "(" : MINUS) : s.sign === "-" || s.sign === "(" ? "" : s.sign) + prefix;
    let tail = unit + (negative && s.sign === "(" ? ")" : "");
    if (decimal) {
      const i = value.search(/[^0-9]/);
      if (i >= 0) {
        tail = value.slice(i) + tail;
        value = value.slice(0, i);
      }
    }
    if (s.comma && !s.zero) value = group(value, Infinity);
    const length = head.length + value.length + tail.length;
    let padding = length < s.width ? s.fill.repeat(s.width - length) : "";
    if (s.comma && s.zero) {
      value = group(padding + value, padding.length ? s.width - tail.length : Infinity);
      padding = "";
    }
    switch (s.align) {
      case "<":
        return head + value + tail + padding;
      case "=":
        return head + padding + value + tail;
      case "^": {
        const half = padding.length >> 1;
        return padding.slice(0, half) + head + value + tail + padding.slice(half);
      }
      default:
        return padding + head + value + tail;
    }
  };
}

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const DIRECTIVES = "aAbBdeHIjLmMpSyYZ%";

/** A function writing times (ms since 1970, UTC) as a strftime string says: %Y %y %m %B %b
 * %d %e %j %a %A %H %I %p %M %S %L %Z %%, each padded with 0 by default, or as `%-d`
 * (none), `%_d` (spaces), `%0d` (zeros). Throws on a directive it doesn't know. */
export function timeFormat(spec: string): (t: number) => string {
  const parts: (string | [string, string | null])[] = [];
  for (let i = 0; i < spec.length; i++) {
    if (spec[i] !== "%") {
      parts.push(spec[i]);
      continue;
    }
    let pad: string | null = null;
    let c = spec[++i];
    if (c === "-" || c === "_" || c === "0") {
      pad = c === "-" ? "" : c === "_" ? " " : "0";
      c = spec[++i];
    }
    if (c === undefined || !DIRECTIVES.includes(c)) throw new Error(`invalid time format: ${spec}`);
    parts.push([c, pad]);
  }
  return (t: number): string => {
    const d = new Date(t);
    return parts.map((p) => (typeof p === "string" ? p : directive(d, p[0], p[1]))).join("");
  };
}

function padded(n: number, width: number, pad: string | null, fallback = "0"): string {
  const fill = pad ?? fallback;
  const s = String(n);
  return fill === "" ? s : s.padStart(width, fill);
}

function directive(d: Date, c: string, pad: string | null): string {
  const hours = d.getUTCHours();
  switch (c) {
    case "a":
      return DAYS[d.getUTCDay()].slice(0, 3);
    case "A":
      return DAYS[d.getUTCDay()];
    case "b":
      return MONTH_NAMES[d.getUTCMonth()].slice(0, 3);
    case "B":
      return MONTH_NAMES[d.getUTCMonth()];
    case "d":
      return padded(d.getUTCDate(), 2, pad);
    case "e":
      return padded(d.getUTCDate(), 2, pad, " ");
    case "H":
      return padded(hours, 2, pad);
    case "I":
      return padded(hours % 12 || 12, 2, pad);
    case "j": {
      const day = Math.floor((d.getTime() - Date.UTC(d.getUTCFullYear(), 0, 1)) / 86400000) + 1;
      return padded(day, 3, pad);
    }
    case "L":
      return padded(d.getUTCMilliseconds(), 3, pad);
    case "m":
      return padded(d.getUTCMonth() + 1, 2, pad);
    case "M":
      return padded(d.getUTCMinutes(), 2, pad);
    case "p":
      return hours < 12 ? "AM" : "PM";
    case "S":
      return padded(d.getUTCSeconds(), 2, pad);
    case "y":
      return padded(((d.getUTCFullYear() % 100) + 100) % 100, 2, pad);
    case "Y":
      return padded(d.getUTCFullYear(), 4, pad);
    case "Z":
      return "+0000";
    default:
      return "%";
  }
}

const made = new Map<string, (v: number) => string>();

/** A formatter for an axis's values, from its format (null: none given); made once a format. */
export function axisFormat(kind: string, format: string | null | undefined): ((v: number) => string) | null {
  if (!format || kind === "band") return null;
  const key = `${kind === "time" ? "t" : "n"}${format}`;
  let f = made.get(key);
  if (!f) {
    f = kind === "time" ? timeFormat(format) : numberFormat(format);
    made.set(key, f);
  }
  return f;
}
