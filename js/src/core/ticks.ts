// Axis ticks and their labels: numbers (1-2-5 steps), times (calendar steps in UTC, the
// wall-clock time Python sent), bands (one tick per category, thinned to fit), and log
// scales (decades, with 2 and 5 between when there is room; within a decade, round values).

import type { AxisKind } from "./types";

export interface Tick {
  /** Position in axis units (relative to the origin). */
  value: number;
  label: string;
}

/** How many ticks a y axis of `h` px draws over [lo, hi]: one per 36 px; bands, one per
 * label height (about 15 px). */
export function yTickCount(kind: AxisKind, lo: number, hi: number, h: number): number {
  if (kind !== "band") return Math.max(2, Math.floor(h / 36));
  const shown = Math.max(1, hi - lo);
  return Math.max(2, Math.floor(shown / Math.max(1, Math.ceil(15 / (h / shown)))));
}

/** Ticks for [lo, hi] (axis units relative to `origin`), about `count` of them. */
export function ticks(kind: AxisKind, lo: number, hi: number, origin: number, count: number, levels: string[] | null = null): Tick[] {
  if (!(hi > lo) || !Number.isFinite(lo) || !Number.isFinite(hi)) return [];
  count = Math.max(1, count);
  if (kind === "band") return bandTicks(lo, hi, levels ?? [], count);
  if (kind === "time") return timeTicks(lo + origin, hi + origin, count).map((t) => ({ value: t.value - origin, label: t.label }));
  if (kind === "log") return logTicks(lo + origin, hi + origin, count).map((t) => ({ value: t.value - origin, label: t.label }));
  const step = niceStep(hi - lo, count);
  const first = Math.ceil(lo / step - 1e-9);
  const last = Math.floor(hi / step + 1e-9);
  const out: Tick[] = [];
  const decimals = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
  for (let i = first; i <= last && out.length < 1000; i++) {
    const v = i * step || 0; // not -0
    out.push({ value: v, label: formatNumber(v + origin, step, decimals) });
  }
  return out;
}

/** A 1, 2 or 5 times a power of ten step giving about `count` steps over `span`. */
export function niceStep(span: number, count: number): number {
  const raw = span / count;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / power;
  const nice = f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10;
  return nice * power;
}

export function formatNumber(v: number, step: number, decimals: number): string {
  if (Math.abs(v) < step * 1e-6) v = 0;
  const a = Math.abs(v);
  if (a >= 1e5 && step >= 1e3) {
    const [div, suffix] = a >= 1e12 ? [1e12, "T"] : a >= 1e9 ? [1e9, "G"] : a >= 1e6 ? [1e6, "M"] : [1e3, "k"];
    const d = Math.max(0, -Math.floor(Math.log10(step / div) + 1e-9));
    return `${(v / div).toFixed(Math.min(d, 6))}${suffix}`;
  }
  return v.toFixed(Math.min(decimals, 12)).replace("-", "−");
}

/** A value at the precision of its axis (tooltips): `span` the visible range. */
export function formatValue(kind: AxisKind, v: number, origin: number, span: number, levels: string[] | null = null): string {
  if (kind === "band") return levels?.[Math.round(v)] ?? "";
  if (kind === "time") return formatTime(v + origin, span / 200);
  if (kind === "log") {
    // the value, as precise as a 200th of the view's (log) span there
    const value = Math.pow(10, v + origin);
    const step = value * (Math.pow(10, span / 200) - 1) || value * 1e-6;
    const decimals = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
    return formatNumber(value, step, Math.min(decimals, 12));
  }
  const step = span / 1000 || 1;
  const decimals = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
  return formatNumber(v + origin, step, Math.min(decimals, 6));
}

/** Log ticks over [lo, hi] (log10 units): decades (every few when there are many), with
 * 2 and 5 between when they fit; less than a decade: round values, evenly spaced. */
function logTicks(lo: number, hi: number, count: number): Tick[] {
  const out: Tick[] = [];
  const label = (v: number): string => formatNumber(v, v, Math.max(0, -Math.floor(Math.log10(v) + 1e-9)));
  if (hi - lo < 1) {
    const a = Math.pow(10, lo);
    const b = Math.pow(10, hi);
    const step = niceStep(b - a, count);
    const decimals = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
    for (let i = Math.ceil(a / step - 1e-9); i * step <= b * (1 + 1e-12) && out.length < 1000; i++) {
      const v = i * step;
      if (v > 0) out.push({ value: Math.log10(v), label: formatNumber(v, step, decimals) });
    }
    return out;
  }
  const decades = hi - lo;
  const every = Math.max(1, Math.ceil(decades / count));
  const mults = every === 1 && decades * 3 <= count * 1.5 ? [1, 2, 5] : [1];
  for (let e = Math.floor(lo); e <= Math.ceil(hi) && out.length < 1000; e++) {
    if (e % every !== 0) continue;
    for (const m of mults) {
      const value = Math.log10(m) + e;
      if (value >= lo - 1e-9 && value <= hi + 1e-9) out.push({ value, label: label(m * Math.pow(10, e)) });
    }
  }
  return out;
}

/** Fainter gridlines between a log axis's ticks (axis units relative to `origin`): every
 * decade the ticks skip, and 2 to 9 times each when they are at least 5 px apart over the
 * axis's `pixels`. Other axes: none. */
export function minorTicks(kind: AxisKind, lo: number, hi: number, origin: number, major: Tick[], pixels: number): number[] {
  if (kind !== "log" || !(hi > lo)) return [];
  const a = lo + origin;
  const b = hi + origin;
  const taken = new Set(major.map((t) => Math.round((t.value + origin) * 1e6)));
  const pick = (mults: number[]): number[] => {
    const out: number[] = [];
    for (let e = Math.floor(a); e <= Math.ceil(b) && out.length < 2000; e++) {
      for (const m of mults) {
        const v = e + Math.log10(m);
        if (v >= a && v <= b && !taken.has(Math.round(v * 1e6))) out.push(v - origin);
      }
    }
    return out;
  };
  const fine = pick([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  // the closest pair of a decade's lines: 9 and 10, log10(10/9) of a decade apart
  if ((pixels / (b - a)) * Math.log10(10 / 9) >= 5) return fine;
  const decades = pick([1]);
  return (pixels / (b - a)) >= 5 ? decades : [];
}

function bandTicks(lo: number, hi: number, levels: string[], count: number): Tick[] {
  const first = Math.max(0, Math.ceil(lo));
  const last = Math.min(levels.length - 1, Math.floor(hi));
  const n = last - first + 1;
  if (n <= 0) return [];
  const every = Math.max(1, Math.ceil(n / count));
  const out: Tick[] = [];
  for (let i = first; i <= last; i += every) out.push({ value: i, label: levels[i] });
  return out;
}

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Fixed steps (ms) up to a week; then calendar months and years. */
const FIXED = [
  1, 2, 5, 10, 20, 50, 100, 200, 500,
  SECOND, 2 * SECOND, 5 * SECOND, 15 * SECOND, 30 * SECOND,
  MINUTE, 2 * MINUTE, 5 * MINUTE, 15 * MINUTE, 30 * MINUTE,
  HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR,
  DAY, 2 * DAY, 7 * DAY,
];

function timeTicks(lo: number, hi: number, count: number): Tick[] {
  const target = (hi - lo) / count;
  const out: Tick[] = [];
  const fixed = FIXED.find((s) => s >= target);
  if (fixed !== undefined) {
    // weeks start on Mondays (1970-01-01 was a Thursday)
    const shift = fixed === 7 * DAY ? 4 * DAY : 0;
    for (let t = Math.ceil((lo - shift) / fixed) * fixed + shift; t <= hi && out.length < 1000; t += fixed) {
      out.push({ value: t, label: timeLabel(t, fixed) });
    }
    return out;
  }
  const months = [1, 2, 3, 6].find((m) => m * 30 * DAY >= target);
  if (months !== undefined) {
    const d = new Date(lo);
    for (let y = d.getUTCFullYear(), m = d.getUTCMonth(); out.length < 1000; m++) {
      if (m === 12) {
        m = 0;
        y++;
      }
      const t = Date.UTC(y, m, 1);
      if (t > hi) break;
      if (t >= lo && m % months === 0) out.push({ value: t, label: m === 0 ? String(y) : MONTHS[m] });
    }
    return out;
  }
  const years = niceStep(target / (365.25 * DAY), 1);
  const step = Math.max(1, years);
  const y0 = Math.ceil(new Date(lo).getUTCFullYear() / step) * step;
  for (let y = y0; out.length < 1000; y += step) {
    const t = Date.UTC(y, 0, 1);
    if (t > hi) break;
    if (t >= lo) out.push({ value: t, label: String(y) });
  }
  return out;
}

function pad(n: number, width = 2): string {
  return String(n).padStart(width, "0");
}

function timeLabel(t: number, step: number): string {
  const d = new Date(t);
  const hm = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  const day = `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
  if (step < SECOND) return `${hm}:${pad(d.getUTCSeconds())}.${pad(d.getUTCMilliseconds(), 3)}`;
  if (step < MINUTE) return `${hm}:${pad(d.getUTCSeconds())}`;
  if (step < DAY) return t % DAY === 0 ? day : hm;
  return day;
}

/** A moment, as precise as `resolution` (ms) needs. */
export function formatTime(t: number, resolution: number): string {
  const d = new Date(t);
  const date = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  if (resolution >= DAY) return date;
  const hm = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  if (resolution >= MINUTE) return `${date} ${hm}`;
  if (resolution >= SECOND) return `${date} ${hm}:${pad(d.getUTCSeconds())}`;
  return `${date} ${hm}:${pad(d.getUTCSeconds())}.${pad(d.getUTCMilliseconds(), 3)}`;
}
