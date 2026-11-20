// Shape, size and dash (Python: channels.py). Points of a shape column are drawn as their
// shape (KIND_POINT: the shaders' distance functions, here as paths for Canvas 2D and the
// legend); a dashed line's segments are cut into dashes, each a capsule, from its pixel
// lengths (so every renderer draws them, and the export alike).

import type { InstanceSet } from "./renderers/renderer";

/** The shapes by code: circle, square, triangle, diamond, plus, cross, triangle-down. */
export const SHAPES = ["circle", "square", "triangle", "diamond", "plus", "cross", "triangle-down"];

// as the shaders (shaders.ts: sdShape) and figure.py draw them, r a circle's radius
const SQUARE = 0.8;
const TRIANGLE = 1.25;
const ARM = 1.05;
const BAR = 0.33;

/** The corners of a shape (not the circle) around x, y, in CSS px. */
export function shapeCorners(code: number, x: number, y: number, r: number): [number, number][] {
  const s = SQUARE * r;
  if (code === 1) return [[x - s, y - s], [x + s, y - s], [x + s, y + s], [x - s, y + s]];
  if (code === 2 || code === 6) {
    const R = TRIANGLE * r;
    const f = code === 2 ? 1 : -1;
    return [[x, y - f * R], [x + R * 0.8660254, y + (f * R) / 2], [x - R * 0.8660254, y + (f * R) / 2]];
  }
  if (code === 3) {
    const d = s * Math.SQRT2;
    return [[x, y - d], [x + d, y], [x, y + d], [x - d, y]];
  }
  if (code === 4 || code === 5) {
    const a = ARM * r;
    const t = BAR * r;
    const plus: [number, number][] = [[-t, -a], [t, -a], [t, -t], [a, -t], [a, t], [t, t], [t, a], [-t, a], [-t, t], [-a, t], [-a, -t], [-t, -t]];
    const k = code === 5 ? Math.SQRT1_2 : 1;
    const q = code === 5 ? Math.SQRT1_2 : 0;
    return plus.map(([u, v]) => [x + u * k - v * q, y + u * q + v * k]);
  }
  return [];
}

/** A shape's path, added to the context's (filled by the caller). */
export function shapePath(ctx: CanvasRenderingContext2D, code: number, x: number, y: number, r: number): void {
  const corners = shapeCorners(code, x, y, r);
  if (!corners.length) {
    ctx.moveTo(x + r, y);
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.closePath();
    return;
  }
  ctx.moveTo(corners[0][0], corners[0][1]);
  for (let i = 1; i < corners.length; i++) ctx.lineTo(corners[i][0], corners[i][1]);
  ctx.closePath();
}

/** A pattern of dash and gap lengths in line widths, as px of a line `width` wide: the
 * unit is the width (at least 1 px). */
export function dashPx(pattern: number[], width: number): number[] {
  const unit = Math.max(width, 1);
  return pattern.map((v) => v * unit);
}

/** A dash pattern for capsules: each dash's length less its round caps (a dash shorter than
 * them: a dot), its gap the more. */
function capsulePattern(px: number[], width: number): number[] {
  const out = px.slice();
  for (let k = 0; k + 1 < out.length; k += 2) {
    const on = Math.max(0, out[k] - width);
    out[k + 1] += out[k] - on;
    out[k] = on;
  }
  return out;
}

/** The dashes of instances `start` .. `start + count` of a line's set at these scales (px
 * per axis unit): a capsule each, in the set's coordinates, the pattern carried on along
 * each run of joined segments. `codes`: each segment's pattern (null: the first). */
export function dashPieces(
  set: InstanceSet,
  start: number,
  count: number,
  sx: number,
  sy: number,
  codes: Uint8Array | null,
  patterns: number[][],
  width: number,
): { coords: Float32Array; colors: Uint8Array; count: number } {
  const pats = patterns.map((p) => capsulePattern(dashPx(p, width), width));
  const c = set.coords;
  const out: number[] = [];
  const cols: number[] = [];
  let k = 0;
  let left = 0;
  let prevX = NaN;
  let prevY = NaN;
  let prevCode = -1;
  const emit = (i: number, x0: number, y0: number, x1: number, y1: number): void => {
    out.push(x0, y0, x1, y1);
    cols.push(set.colors[i * 4], set.colors[i * 4 + 1], set.colors[i * 4 + 2], set.colors[i * 4 + 3]);
  };
  for (let i = start; i < start + count; i++) {
    const ax = c[i * 4];
    const ay = c[i * 4 + 1];
    const bx = c[i * 4 + 2];
    const by = c[i * 4 + 3];
    const code = codes ? codes[i] : 0;
    const pat = pats[code] ?? [];
    const len = Math.hypot((bx - ax) * sx, (by - ay) * sy);
    if (!Number.isFinite(len)) {
      prevCode = -1;
      continue;
    }
    if (!pat.length) {
      emit(i, ax, ay, bx, by);
      prevCode = -1;
      continue;
    }
    if (!(ax === prevX && ay === prevY && code === prevCode)) {
      k = 0;
      left = pat[0];
    }
    prevX = bx;
    prevY = by;
    prevCode = code;
    let pos = 0;
    for (let guard = 0; guard < 1e6; guard++) {
      const step = Math.min(left, len - pos);
      if (k % 2 === 0) {
        const t0 = len > 0 ? pos / len : 0;
        const t1 = len > 0 ? (pos + step) / len : 0;
        emit(i, ax + (bx - ax) * t0, ay + (by - ay) * t0, ax + (bx - ax) * t1, ay + (by - ay) * t1);
      }
      pos += step;
      left -= step;
      if (left > 1e-9) break; // the segment ends inside this dash or gap
      k = (k + 1) % pat.length;
      left = pat[k];
      if (pos >= len) break; // at the segment's end: the next element starts the next one
    }
  }
  return { coords: new Float32Array(out), colors: new Uint8Array(cols), count: out.length / 4 };
}

/** What a legend entry's swatch shows: a shape, a dash, a size. */
export interface Glyph {
  color: string;
  shape?: number;
  /** Dash and gap lengths in line widths ([] solid). */
  dash?: number[];
  lineWidth?: number;
  /** A point's diameter (px). */
  size?: number;
}

/** A swatch's width and height (CSS px). */
export function glyphBox(g: Glyph): [number, number] {
  if (g.dash) return [22, 10];
  if (g.size !== undefined) return [Math.max(10, g.size + 2), Math.max(10, g.size + 2)];
  return [10, 10];
}

/** A legend entry's swatch, its box's top left at x, y. */
export function drawGlyph(ctx: CanvasRenderingContext2D, g: Glyph, x: number, y: number): void {
  const [w, h] = glyphBox(g);
  ctx.save();
  ctx.fillStyle = g.color;
  ctx.strokeStyle = g.color;
  if (g.dash) {
    const lw = Math.max(1, Math.min(4, g.lineWidth ?? 1.5));
    ctx.lineWidth = lw;
    ctx.lineCap = "round";
    const dash = capsulePattern(dashPx(g.dash, lw), lw);
    ctx.setLineDash(dash.map((v, i) => (i % 2 === 0 ? Math.max(v, 0.001) : v)));
    ctx.beginPath();
    ctx.moveTo(x + lw / 2, y + h / 2);
    ctx.lineTo(x + w - lw / 2, y + h / 2);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  if (g.shape !== undefined || g.size !== undefined) {
    const r = g.size !== undefined ? g.size / 2 : g.dash ? 3 : 4;
    ctx.beginPath();
    shapePath(ctx, g.shape ?? 0, x + w / 2, y + h / 2, r);
    ctx.fill();
  }
  ctx.restore();
}
