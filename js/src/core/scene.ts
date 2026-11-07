// The spec's data as the renderers want it: per layer, float32 instances relative to each
// panel's base (its initial domain's low end, so float32 keeps precision for times), RGBA
// bytes, and the panel ranges. Also finding the instance nearest the pointer (hover).

import { type InstanceSet, KIND_CAPSULE, KIND_RECT, KIND_TRAP } from "./renderers/renderer";
import type { BufferRef, DataSource, MarkLayerSpec, TextLayerSpec, TrellisSpec } from "./types";
import { isMark } from "./types";

export interface LayerData {
  spec: MarkLayerSpec;
  /** Index of the layer in spec.layers. */
  index: number;
  /** x0, y0, x1, y1 per instance, relative to the axis origins (float64). */
  coords: Float64Array;
  starts: Uint32Array;
  set: InstanceSet;
  codes: Uint16Array | null;
  /** Areas: the base at each end of an instance (axis units, relative to the origin). */
  base: Float64Array | null;
  /** Each instance's link key, or null: the layer is not linked. */
  link: Uint32Array | null;
  /** Each instance's group in its family (spec.family), or null. */
  groups: Uint32Array | null;
  /** Each instance's row in spec.tips, or null. */
  tipRows: Uint32Array | null;
  kind: number;
  /** Half the line width or point size (px); 0 for bars. */
  halfWidth: number;
}

/** A text layer: its labels decoded, at points (axis units, relative to the origins). */
export interface TextData {
  spec: TextLayerSpec;
  coords: Float64Array;
  starts: Uint32Array;
  labels: string[];
  colors: Uint8Array | null;
}

export interface Scene {
  spec: TrellisSpec;
  layers: LayerData[];
  texts: TextData[];
  /** Each panel's base: its initial domain's low end on x and y. */
  baseX: Float64Array;
  baseY: Float64Array;
}

let nextVersion = 1;

export function bufferIds(spec: TrellisSpec): string[] {
  const ids: string[] = [];
  for (const l of spec.layers) {
    if (l.type === "text") {
      ids.push(l.coords.id, l.starts.id, l.labels.id, l.offsets.id);
      if (l.colors) ids.push(l.colors.id);
    }
    if (!isMark(l)) continue;
    ids.push(l.coords.id, l.starts.id);
    if (l.color.rgba) ids.push(l.color.rgba.id);
    if (l.color.codes) ids.push(l.color.codes.id);
    if (l.link) ids.push(l.link.id);
    if (l.base) ids.push(l.base.id);
    if (l.groups) ids.push(l.groups.id);
    if (l.tip_rows) ids.push(l.tip_rows.id);
  }
  return ids;
}

function view(source: DataSource, ref: BufferRef): ArrayBufferView {
  const buf = source.get(ref.id);
  const n = ref.count * ref.components;
  switch (ref.dtype) {
    case "float64":
      return new Float64Array(buf, 0, n);
    case "float32":
      return new Float32Array(buf, 0, n);
    case "uint32":
      return new Uint32Array(buf, 0, n);
    case "int32":
      return new Int32Array(buf, 0, n);
    case "uint16":
      return new Uint16Array(buf, 0, n);
    default:
      return new Uint8Array(buf, 0, n);
  }
}

export function buildScene(spec: TrellisSpec, source: DataSource): Scene {
  const np = spec.panels.length;
  const baseX = new Float64Array(np);
  const baseY = new Float64Array(np);
  spec.panels.forEach((p, i) => {
    baseX[i] = p.x[0];
    baseY[i] = p.y[0];
  });
  const layers: LayerData[] = [];
  spec.layers.forEach((l, index) => {
    if (!isMark(l)) return;
    const coords = view(source, l.coords) as Float64Array;
    const starts = view(source, l.starts) as Uint32Array;
    const n = l.count;
    const f32 = new Float32Array(n * 4);
    for (let p = 0; p < np; p++) {
      const bx = baseX[p];
      const by = baseY[p];
      for (let i = starts[p]; i < starts[p + 1]; i++) {
        f32[i * 4] = coords[i * 4] - bx;
        f32[i * 4 + 1] = coords[i * 4 + 1] - by;
        f32[i * 4 + 2] = coords[i * 4 + 2] - bx;
        f32[i * 4 + 3] = coords[i * 4 + 3] - by;
      }
    }
    let colors: Uint8Array;
    if (l.color.rgba) colors = view(source, l.color.rgba) as Uint8Array;
    else {
      colors = new Uint8Array(n * 4);
      const [r, g, b, a] = l.color.solid ?? [76, 86, 106, 255];
      for (let i = 0; i < n; i++) colors.set([r, g, b, a], i * 4);
    }
    let base: Float32Array | undefined;
    const b64 = l.base ? (view(source, l.base) as Float64Array) : null;
    if (b64) {
      base = new Float32Array(n * 2);
      for (let p = 0; p < np; p++) {
        for (let i = starts[p]; i < starts[p + 1]; i++) {
          base[i * 2] = b64[i * 2] - baseY[p];
          base[i * 2 + 1] = b64[i * 2 + 1] - baseY[p];
        }
      }
    }
    const kind = l.type === "bars" || l.type === "rect" ? KIND_RECT : l.type === "area" || l.type === "band" ? KIND_TRAP : KIND_CAPSULE;
    const halfWidth = l.type === "line" ? l.width / 2 : l.type === "points" ? l.size / 2 : 0;
    layers.push({
      spec: l,
      index,
      coords,
      starts,
      // the layer's index too: two layers can draw the same data (a density's fill and line)
      set: { key: `${index}:${l.coords.id}:${l.color.rgba?.id ?? l.color.solid?.join(",")}`, version: nextVersion++, count: n, coords: f32, colors, base },
      codes: l.color.codes ? (view(source, l.color.codes) as Uint16Array) : null,
      link: l.link ? (view(source, l.link) as Uint32Array) : null,
      groups: l.groups ? (view(source, l.groups) as Uint32Array) : null,
      tipRows: l.tip_rows ? (view(source, l.tip_rows) as Uint32Array) : null,
      base: b64,
      kind,
      halfWidth,
    });
  });
  const decoder = new TextDecoder();
  const texts: TextData[] = [];
  for (const l of spec.layers) {
    if (l.type !== "text") continue;
    const bytes = view(source, l.labels) as Uint8Array;
    const offsets = view(source, l.offsets) as Uint32Array;
    const labels: string[] = new Array(l.count);
    for (let i = 0; i < l.count; i++) labels[i] = decoder.decode(bytes.subarray(offsets[i], offsets[i + 1]));
    texts.push({
      spec: l,
      coords: view(source, l.coords) as Float64Array,
      starts: view(source, l.starts) as Uint32Array,
      labels,
      colors: l.colors ? (view(source, l.colors) as Uint8Array) : null,
    });
  }
  return { spec, layers, texts, baseX, baseY };
}

/** Maps a panel's data (axis units) to CSS px: screen = o + v * s. */
export interface PanelMap {
  sx: number;
  ox: number;
  sy: number;
  oy: number;
}

export interface Hit {
  layer: LayerData;
  instance: number;
  /** Distance to the pointer (px; 0 inside a bar). */
  distance: number;
}

/** The instance of panel `p` nearest the pointer (px), within `radius` px. */
export function pick(scene: Scene, p: number, map: PanelMap, px: number, py: number, radius: number): Hit | null {
  let best: Hit | null = null;
  for (let li = scene.layers.length - 1; li >= 0; li--) {
    const layer = scene.layers[li];
    if (layer.spec.context) continue;
    const c = layer.coords;
    const reach = radius + layer.halfWidth;
    for (let i = layer.starts[p]; i < layer.starts[p + 1]; i++) {
      const ax = map.ox + c[i * 4] * map.sx;
      const ay = map.oy + c[i * 4 + 1] * map.sy;
      const bx = map.ox + c[i * 4 + 2] * map.sx;
      const by = map.oy + c[i * 4 + 3] * map.sy;
      let d: number;
      if (layer.kind === KIND_TRAP && layer.set.base) {
        // inside the area: 0; else the nearer end of its top
        const sb = layer.set.base;
        const off = map.oy + scene.baseY[p] * map.sy;
        const lo = Math.min(ax, bx);
        const hi = Math.max(ax, bx);
        const t = hi > lo ? (px - ax) / (bx - ax) : 0;
        const top = ay + (by - ay) * t;
        const bottom = off + (sb[i * 2] + (sb[i * 2 + 1] - sb[i * 2]) * t) * map.sy;
        const inside = px >= lo && px <= hi && py >= Math.min(top, bottom) && py <= Math.max(top, bottom);
        d = inside ? 0 : Math.min(Math.hypot(px - ax, py - ay), Math.hypot(px - bx, py - by));
      } else if (layer.kind === KIND_RECT) {
        const dx = Math.max(Math.min(ax, bx) - px, 0, px - Math.max(ax, bx));
        const dy = Math.max(Math.min(ay, by) - py, 0, py - Math.max(ay, by));
        d = Math.hypot(dx, dy);
      } else if (layer.spec.step) {
        // a step line: its levels, each starting at its point (not its risers)
        if (ax === bx && ay !== by) continue;
        const t = bx !== ax ? Math.max(0, Math.min(1, (px - ax) / (bx - ax))) : 0;
        d = Math.hypot(px - (ax + t * (bx - ax)), py - ay);
      } else {
        // the nearest end of a segment: lines report their points
        const da = Math.hypot(px - ax, py - ay);
        const db = Math.hypot(px - bx, py - by);
        d = layer.spec.type === "line" ? Math.min(da, db) : da;
      }
      if (d <= reach && (!best || d < best.distance)) best = { layer, instance: i, distance: d };
    }
    if (best && best.distance === 0) break;
  }
  return best;
}

/** The data point of a hit: for a line, the segment end nearer the pointer. */
export function hitPoint(hit: Hit, map: PanelMap, px: number, py: number): { x: number; y: number; y0: number } {
  const c = hit.layer.coords;
  const i = hit.instance;
  const type = hit.layer.spec.type;
  if (type === "rect") return { x: (c[i * 4] + c[i * 4 + 2]) / 2, y: (c[i * 4 + 1] + c[i * 4 + 3]) / 2, y0: 0 };
  if (hit.layer.kind === KIND_RECT) return { x: (c[i * 4] + c[i * 4 + 2]) / 2, y: c[i * 4 + 3], y0: c[i * 4 + 1] };
  // y0: an area's base there (its value is y - y0); 0 otherwise
  const base = hit.layer.base;
  if ((type === "line" && !hit.layer.spec.step) || type === "area" || type === "band") {
    const da = Math.hypot(px - (map.ox + c[i * 4] * map.sx), py - (map.oy + c[i * 4 + 1] * map.sy));
    const db = Math.hypot(px - (map.ox + c[i * 4 + 2] * map.sx), py - (map.oy + c[i * 4 + 3] * map.sy));
    if (db < da) return { x: c[i * 4 + 2], y: c[i * 4 + 3], y0: base ? base[i * 2 + 1] : 0 };
  }
  return { x: c[i * 4], y: c[i * 4 + 1], y0: base ? base[i * 2] : 0 };
}

/** The y extent of panel `p`'s own marks (not grey context) where x is in [x0, x1]: a line
 * segment crossing an end counts with its y at that end. `base`: the low or high end is a
 * bar's base, which a fit keeps unpadded. Null: nothing there. */
export function yExtent(scene: Scene, p: number, x0: number, x1: number): { lo: number; hi: number; baseLo: boolean; baseHi: boolean } | null {
  let lo = Infinity;
  let hi = -Infinity;
  let baseLo = false;
  let baseHi = false;
  const add = (y: number, base: boolean): void => {
    if (y < lo || (y === lo && base)) {
      lo = y;
      baseLo = base;
    }
    if (y > hi || (y === hi && base)) {
      hi = y;
      baseHi = base;
    }
  };
  for (const layer of scene.layers) {
    if (layer.spec.context) continue;
    const c = layer.coords;
    const rect = layer.kind === KIND_RECT;
    for (let i = layer.starts[p]; i < layer.starts[p + 1]; i++) {
      let ax = c[i * 4];
      let ay = c[i * 4 + 1];
      let bx = c[i * 4 + 2];
      let by = c[i * 4 + 3];
      if (Math.max(ax, bx) < x0 || Math.min(ax, bx) > x1) continue;
      if (rect) {
        add(ay, layer.spec.type === "bars"); // a bar's base
        add(by, false);
        continue;
      }
      const base = layer.set.base;
      if (base) {
        // an area's base (relative to the panel's): kept unpadded; a band's lower line: padded
        const area = layer.spec.type === "area";
        add(base[i * 2] + scene.baseY[p], area);
        add(base[i * 2 + 1] + scene.baseY[p], area);
      }
      if (ax !== bx) {
        // clip the segment to [x0, x1]
        if (ax > bx) [ax, ay, bx, by] = [bx, by, ax, ay];
        const slope = (by - ay) / (bx - ax);
        if (ax < x0) [ax, ay] = [x0, ay + (x0 - ax) * slope];
        if (bx > x1) [bx, by] = [x1, by - (bx - x1) * slope];
      }
      add(ay, false);
      add(by, false);
    }
  }
  return lo <= hi && Number.isFinite(lo) && Number.isFinite(hi) ? { lo, hi, baseLo, baseHi } : null;
}
