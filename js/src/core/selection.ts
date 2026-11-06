// A selection: a brush, an interval on x, on y or on both, in axis units (the spec's,
// relative to the axis origins). Without a panel it holds in every panel alike, as one
// predicate on the data (Vega-Lite's interval selection, resolved globally): the same
// range compared across panels. In one panel (what a brush drawn on a linked plot is), it
// selects there, and link keys (Trellis(link=)) grow it to every mark sharing a key with a
// selected one, in all panels: brush some countries in 1955 and follow them in every year.
//
// A mark meets the brush: a point inside it; a line segment with either end inside; a bar
// or rect overlapping it (an area: like a line). Grey context layers are never selected.

import { KIND_RECT } from "./renderers/renderer";
import type { LayerData, Scene } from "./scene";

export type Range = [number, number];

export interface Brush {
  x: Range | null;
  y: Range | null;
  /** The panel it selects in (index in spec.panels), or null/absent: every panel. */
  panel?: number | null;
}

export interface Selection {
  /** Per layer of the scene: 1 where the instance is selected (null: a context layer). */
  masks: (Uint8Array | null)[];
  selected: number;
  total: number;
}

/** The marks a brush selects, grown by link keys. */
export function select(scene: Scene, brush: Brush): Selection {
  const [x0, x1] = brush.x ? sorted(brush.x) : [-Infinity, Infinity];
  const [y0, y1] = brush.y ? sorted(brush.y) : [-Infinity, Infinity];
  const inside = (x: number, y: number): boolean => x >= x0 && x <= x1 && y >= y0 && y <= y1;
  const masks: (Uint8Array | null)[] = [];
  const keys = new Set<number>();
  let linked = false;
  for (const layer of scene.layers) {
    if (layer.spec.context) {
      masks.push(null);
      continue;
    }
    const c = layer.coords;
    const n = layer.set.count;
    const mask = new Uint8Array(n);
    const rect = layer.kind === KIND_RECT;
    const p = brush.panel ?? null;
    const from = p === null ? 0 : (layer.starts[p] ?? 0);
    const to = p === null ? n : (layer.starts[p + 1] ?? 0);
    for (let i = from; i < to; i++) {
      const ax = c[i * 4];
      const ay = c[i * 4 + 1];
      const bx = c[i * 4 + 2];
      const by = c[i * 4 + 3];
      const hit = rect
        ? Math.max(ax, bx) >= x0 && Math.min(ax, bx) <= x1 && Math.max(ay, by) >= y0 && Math.min(ay, by) <= y1
        : inside(ax, ay) || inside(bx, by);
      if (hit) mask[i] = 1;
    }
    if (layer.link) {
      linked = true;
      for (let i = 0; i < n; i++) if (mask[i]) keys.add(layer.link[i]);
    }
    masks.push(mask);
  }
  if (linked && keys.size) {
    scene.layers.forEach((layer, li) => {
      const mask = masks[li];
      if (!mask || !layer.link) return;
      for (let i = 0; i < mask.length; i++) if (keys.has(layer.link[i])) mask[i] = 1;
    });
  }
  let selected = 0;
  let total = 0;
  for (const m of masks) {
    if (!m) continue;
    total += m.length;
    for (let i = 0; i < m.length; i++) selected += m[i];
  }
  return { masks, selected, total };
}

/** Colours for drawing a selection: everything faded, and the selected marks again on top
 * (the others transparent there). */
export function selectionColors(layer: LayerData, mask: Uint8Array, dim: Uint8Array | null): { dim: Uint8Array; hi: Uint8Array } {
  const src = layer.set.colors;
  const n = layer.set.count;
  let faded = dim;
  if (!faded) {
    faded = new Uint8Array(n * 4);
    for (let i = 0; i < n; i++) {
      faded[i * 4] = src[i * 4];
      faded[i * 4 + 1] = src[i * 4 + 1];
      faded[i * 4 + 2] = src[i * 4 + 2];
      faded[i * 4 + 3] = Math.round(src[i * 4 + 3] * FADED);
    }
  }
  const hi = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    if (!mask[i]) continue;
    hi[i * 4] = src[i * 4];
    hi[i * 4 + 1] = src[i * 4 + 1];
    hi[i * 4 + 2] = src[i * 4 + 2];
    hi[i * 4 + 3] = src[i * 4 + 3];
  }
  return { dim: faded, hi };
}

/** How much of its opacity an unselected mark keeps. */
export const FADED = 0.15;

function sorted(r: Range): Range {
  return r[0] <= r[1] ? r : [r[1], r[0]];
}
