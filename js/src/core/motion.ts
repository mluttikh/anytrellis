// Panels moving to their new places (Heer & Robertson 2007: animated transitions help the
// eye keep track): a sort, a filter, a page turned or a panel opened or closed slides each
// panel shown before and after from where it was, and grows the new ones from their middle,
// in MOTION_MS. Only the panels' places move: their marks are drawn in them as they go
// (view.ts: draw), and a reader asking for reduced motion sees the new places at once.

import type { Layout, PanelBox, Rect } from "./layout";

/** How long a move takes (ms). */
export const MOTION_MS = 250;

/** A panel coming in starts at this share of its size, about its middle. */
const ENTER_SCALE = 0.6;

/** Where each panel of `after` starts from, by spec index: where it was in `before`, or (a
 * panel new to the plot) a smaller rect about its middle. Null: nothing to move (no panel
 * shown in both, or none moved). */
export function motionFrom(before: Layout, after: Layout): Map<number, Rect> | null {
  const was = new Map(before.panels.map((b) => [b.index, b.rect]));
  const from = new Map<number, Rect>();
  let moved = false;
  let shared = false;
  for (const box of after.panels) {
    const r = box.rect;
    const old = was.get(box.index);
    if (old) {
      shared = true;
      if (Math.abs(old.x - r.x) > 0.5 || Math.abs(old.y - r.y) > 0.5 || Math.abs(old.w - r.w) > 0.5 || Math.abs(old.h - r.h) > 0.5) moved = true;
      from.set(box.index, old);
    } else {
      const w = r.w * ENTER_SCALE;
      const h = r.h * ENTER_SCALE;
      from.set(box.index, { x: r.x + (r.w - w) / 2, y: r.y + (r.h - h) / 2, w, h });
      moved = true;
    }
  }
  return shared && moved ? from : null;
}

/** Slow at both ends (cubic). */
export function ease(t: number): number {
  const u = Math.min(1, Math.max(0, t));
  return u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2;
}

const mix = (a: number, b: number, t: number): number => a + (b - a) * t;

/** `r`, drawn about the panel `last` (where it ends), about the panel at `now` instead: past
 * an edge (a strip above it, an axis left of it or under it) it keeps its size and its gap to
 * that edge; along the panel it stretches with it. */
export function placeBy(r: Rect, last: Rect, now: Rect): Rect {
  const along = (start: number, size: number, from: number, length: number, at: number, to: number): [number, number] => {
    if (start + size <= from + 0.5) return [at - (from - start), size]; // before the panel
    if (start >= from + length - 0.5) return [at + to + (start - from - length), size]; // after it
    const k = length > 0 ? to / length : 1;
    return [at + (start - from) * k, size * k];
  };
  const [x, w] = along(r.x, r.w, last.x, last.w, now.x, now.w);
  const [y, h] = along(r.y, r.h, last.y, last.h, now.y, now.h);
  return { x, y, w, h };
}

/** The layout `t` (0 to 1) of the way from `from` to `lay`: each panel, its strip and axes
 * between; a grid's strips, which belong to no one panel, wait for the end. */
export function tween(lay: Layout, from: Map<number, Rect>, t: number): Layout {
  if (t >= 1) return lay;
  const e = ease(t);
  const panels = lay.panels.map((box): PanelBox => {
    const start = from.get(box.index);
    if (!start) return box;
    const last = box.rect;
    const now = { x: mix(start.x, last.x, e), y: mix(start.y, last.y, e), w: mix(start.w, last.w, e), h: mix(start.h, last.h, e) };
    return {
      ...box,
      rect: now,
      strip: box.strip && placeBy(box.strip, last, now),
      xAxis: box.xAxis && placeBy(box.xAxis, last, now),
      yAxis: box.yAxis && placeBy(box.yAxis, last, now),
    };
  });
  return { ...lay, panels, strips: [] };
}

/** The reader asks for less motion (the system's setting). */
export function reducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}
