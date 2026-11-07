// A selection: a brush, an interval on x, on y or on both, in axis units (the spec's,
// relative to the axis origins). Without a panel it holds in every panel alike, as one
// predicate on the data (Vega-Lite's interval selection, resolved globally): the same
// range compared across panels. In one panel (what a brush drawn on a linked plot is), it
// selects there, and link keys (Trellis(link=)) grow it to every mark sharing a key with a
// selected one, in all panels: brush some countries in 1955 and follow them in every year.
//
// A mark meets the brush: a point inside it; a line segment with either end inside; a bar
// or rect overlapping it (an area: like a line; a band: overlapping it). Grey context layers
// are never selected.
// A summary mark drawn as several layers (a box: body, lines, outliers) selects a box
// whole: what meets its body or its lines.
// Clicking legend entries selects their colours: the marks of those colours (and, with a
// range too, only those meeting it); marks coloured by another column, or by none, fade.

import { KIND_RECT } from "./renderers/renderer";
import type { LayerData, Scene } from "./scene";

export type Range = [number, number];

export interface Brush {
  x: Range | null;
  y: Range | null;
  /** The panel it selects in (index in spec.panels), or null/absent: every panel. */
  panel?: number | null;
  /** Only marks of these colours: levels of the category legend `index` (spec.legends). */
  legend?: { index: number; levels: number[] } | null;
}

/** A brush that selects something: a range, or legend entries. */
export function selects(brush: Brush | null): boolean {
  return !!brush && (!!brush.x || !!brush.y || (brush.legend?.levels.length ?? 0) > 0);
}

/** The legend entries chosen after a click on entry `level` of legend `index`: alone (again:
 * none), or with `add` (Shift, Cmd or Ctrl) added to or taken from those chosen. */
export function toggleLegend(current: Brush["legend"], index: number, level: number, add: boolean): Brush["legend"] {
  const chosen = current?.index === index ? current.levels : [];
  let levels: number[];
  if (add) levels = chosen.includes(level) ? chosen.filter((l) => l !== level) : [...chosen, level].sort((a, b) => a - b);
  else levels = chosen.length === 1 && chosen[0] === level ? [] : [level];
  return levels.length ? { index, levels } : null;
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
  const legend = brush.legend?.levels.length ? brush.legend : null;
  const chosen = new Uint8Array(65536);
  for (const l of legend?.levels ?? []) chosen[l] = 1;
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
    const band = layer.spec.type === "band" ? layer.base : null;
    const p = brush.panel ?? null;
    const from = p === null ? 0 : (layer.starts[p] ?? 0);
    // legend entries chosen: only the marks of their colours (none in another legend's colours)
    const codes = legend && layer.spec.color.legend === legend.index ? layer.codes : null;
    const to = legend && !codes ? from : p === null ? n : (layer.starts[p + 1] ?? 0);
    for (let i = from; i < to; i++) {
      if (codes && !chosen[codes[i]]) continue;
      const ax = c[i * 4];
      const ay = c[i * 4 + 1];
      const bx = c[i * 4 + 2];
      const by = c[i * 4 + 3];
      let hit: boolean;
      if (band) {
        // a piece of band: overlapping it, from its lower line to its upper
        const lo = Math.min(ay, by, band[i * 2], band[i * 2 + 1]);
        const hi = Math.max(ay, by, band[i * 2], band[i * 2 + 1]);
        hit = Math.max(ax, bx) >= x0 && Math.min(ax, bx) <= x1 && hi >= y0 && lo <= y1;
      } else if (rect) {
        hit = Math.max(ax, bx) >= x0 && Math.min(ax, bx) <= x1 && Math.max(ay, by) >= y0 && Math.min(ay, by) <= y1;
      } else hit = inside(ax, ay) || inside(bx, by);
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
  // a summary's parts (a box's body and lines): a group selected in one, in all of them
  const families = new Map<number, Set<number>>();
  scene.layers.forEach((layer, li) => {
    const mask = masks[li];
    const f = layer.spec.family;
    if (!mask || f === null || f === undefined || !layer.groups) return;
    const set = families.get(f) ?? new Set<number>();
    for (let i = 0; i < mask.length; i++) if (mask[i]) set.add(layer.groups[i]);
    families.set(f, set);
  });
  scene.layers.forEach((layer, li) => {
    const mask = masks[li];
    const f = layer.spec.family;
    const set = f === null || f === undefined ? undefined : families.get(f);
    if (!mask || !set?.size || !layer.groups) return;
    for (let i = 0; i < mask.length; i++) if (set.has(layer.groups[i])) mask[i] = 1;
  });
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

/** What another plot's selection highlights here (a linked plot): per layer of the spec,
 * a mask of its instances, the selected share of each bar (filled from its base), or null:
 * drawn as it is. */
export interface Highlight {
  /** Per spec layer; `of`: the id of the coords it is for (a layer in detail). */
  layers: (({ mask: Uint8Array } | { fraction: Float32Array }) & { of?: string | null } | null)[];
}

/** A highlight as a selection of the scene's layers, or null when it fits none of them (a
 * spec that changed since: Python sends the new one). A bar's share: selected if above 0. */
export function highlighted(scene: Scene | null, h: Highlight): { selection: Selection; fractions: (Float32Array | null)[] } | null {
  if (!scene) return null;
  const masks: (Uint8Array | null)[] = [];
  const fractions: (Float32Array | null)[] = [];
  let selected = 0;
  let total = 0;
  let any = false;
  scene.layers.forEach((layer) => {
    const given = h.layers[layer.index];
    const entry = given && (!given.of || given.of === layer.spec.coords.id) ? given : null;
    const n = layer.set.count;
    let mask: Uint8Array | null = null;
    let fraction: Float32Array | null = null;
    if (entry && "mask" in entry && entry.mask.length === n) mask = entry.mask;
    else if (entry && "fraction" in entry && entry.fraction.length === n) {
      fraction = entry.fraction;
      mask = new Uint8Array(n);
      for (let i = 0; i < n; i++) mask[i] = fraction[i] > 0 ? 1 : 0;
    }
    if (mask && !layer.spec.context) {
      any = true;
      total += n;
      for (let i = 0; i < n; i++) selected += mask[i];
    } else mask = null;
    masks.push(mask);
    fractions.push(mask ? fraction : null);
  });
  return any ? { selection: { masks, selected, total }, fractions } : null;
}

/** Bars filled to a share of their height: each from its base (y0) up. */
export function filled(coords: Float32Array, fraction: Float32Array): Float32Array {
  const out = new Float32Array(coords);
  for (let i = 0; i < fraction.length; i++) {
    const y0 = coords[i * 4 + 1];
    out[i * 4 + 3] = y0 + Math.min(1, Math.max(0, fraction[i])) * (coords[i * 4 + 3] - y0);
  }
  return out;
}

/** How much of its opacity an unselected mark keeps. */
export const FADED = 0.15;

function sorted(r: Range): Range {
  return r[0] <= r[1] ? r : [r[1], r[0]];
}
