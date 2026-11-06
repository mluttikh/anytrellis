// Axis ticks and their labels: numbers (1-2-5 steps), times (calendar steps in UTC, the
// wall-clock time Python sent), and bands (one tick per category, thinned to fit).

import type { AxisKind } from "./types";

export interface Tick {
  /** Position in axis units (relative to the origin). */
  value: number;
  label: string;
}

/** Ticks for [lo, hi] (axis units relative to `origin`), about `count` of them. */
export function ticks(kind: AxisKind, lo: number, hi: number, origin: number, count: number, levels: string[] | null = null): Tick[] {
  if (!(hi > lo) || !Number.isFinite(lo) || !Number.isFinite(hi)) return [];
  count = Math.max(1, count);
  if (kind === "band") return bandTicks(lo, hi, levels ?? [], count);
  if (kind === "time") return timeTicks(lo + origin, hi + origin, count).map((t) => ({ value: t.value - origin, label: t.label }));
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
  const step = span / 1000 || 1;
  const decimals = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
  return formatNumber(v + origin, step, Math.min(decimals, 6));
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
