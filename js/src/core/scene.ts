// The spec's data as the renderers want it: per layer, float32 instances relative to each
// panel's base (its initial domain's low end, so float32 keeps precision for times), RGBA
// bytes, and the panel ranges. Also finding the instance nearest the pointer (hover).

import { type InstanceSet, KIND_CAPSULE, KIND_RECT } from "./renderers/renderer";
import type { BufferRef, DataSource, MarkLayerSpec, TrellisSpec } from "./types";
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
  kind: number;
  /** Half the line width or point size (px); 0 for bars. */
  halfWidth: number;
}

export interface Scene {
  spec: TrellisSpec;
  layers: LayerData[];
  /** Each panel's base: its initial domain's low end on x and y. */
  baseX: Float64Array;
  baseY: Float64Array;
}

let nextVersion = 1;

export function bufferIds(spec: TrellisSpec): string[] {
  const ids: string[] = [];
  for (const l of spec.layers) {
    if (!isMark(l)) continue;
    ids.push(l.coords.id, l.starts.id);
    if (l.color.rgba) ids.push(l.color.rgba.id);
    if (l.color.codes) ids.push(l.color.codes.id);
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
    const kind = l.type === "bars" ? KIND_RECT : KIND_CAPSULE;
    const halfWidth = l.type === "line" ? l.width / 2 : l.type === "points" ? l.size / 2 : 0;
    layers.push({
      spec: l,
      index,
      coords,
      starts,
      set: { key: `${l.coords.id}:${l.color.rgba?.id ?? l.color.solid?.join(",")}`, version: nextVersion++, count: n, coords: f32, colors },
      codes: l.color.codes ? (view(source, l.color.codes) as Uint16Array) : null,
      kind,
      halfWidth,
    });
  });
  return { spec, layers, baseX, baseY };
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
      if (layer.kind === KIND_RECT) {
        const dx = Math.max(Math.min(ax, bx) - px, 0, px - Math.max(ax, bx));
        const dy = Math.max(Math.min(ay, by) - py, 0, py - Math.max(ay, by));
        d = Math.hypot(dx, dy);
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
  if (hit.layer.kind === KIND_RECT) return { x: (c[i * 4] + c[i * 4 + 2]) / 2, y: c[i * 4 + 3], y0: c[i * 4 + 1] };
  if (hit.layer.spec.type === "line") {
    const da = Math.hypot(px - (map.ox + c[i * 4] * map.sx), py - (map.oy + c[i * 4 + 1] * map.sy));
    const db = Math.hypot(px - (map.ox + c[i * 4 + 2] * map.sx), py - (map.oy + c[i * 4 + 3] * map.sy));
    if (db < da) return { x: c[i * 4 + 2], y: c[i * 4 + 3], y0: 0 };
  }
  return { x: c[i * 4], y: c[i * 4 + 1], y0: 0 };
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
        add(ay, true); // the base
        add(by, false);
        continue;
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
