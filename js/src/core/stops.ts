// The arrow keys inside a panel: its marks as stops along x, to step through and announce
// (view.ts: stepMark). A point, bar or tile is one stop; a line, area or band each of its
// points, its last segment's end too. ← → step along x, ↑ ↓ to the nearest mark above or
// below, Home and End to the ends.

import { barsAlongY, hitPoint, type LayerData, type PanelMap, type Scene } from "./scene";

/** A mark to stop at: its scene layer and instance, and its point (spec units). */
export interface Stop {
  layer: number;
  instance: number;
  x: number;
  y: number;
}

const UNIT: PanelMap = { ox: 0, oy: 0, sx: 1, sy: 1 };

/** Panel `p`'s stops, by x then y; `hidden`: an instance left out (a legend's isolation). */
export function markStops(scene: Scene, p: number, horizontal: boolean, hidden: (layer: LayerData, i: number) => boolean = () => false): Stop[] {
  const out: Stop[] = [];
  scene.layers.forEach((layer, li) => {
    if (layer.spec.context || layer.spec.pin) return; // grey context, a rug: as hover
    const c = layer.coords;
    const type = layer.spec.type;
    const pieces = (type === "line" || type === "area" || type === "band") && !layer.spec.step;
    const end = layer.starts[p + 1];
    for (let i = layer.starts[p]; i < end; i++) {
      if (hidden(layer, i)) continue;
      if (pieces || (type === "line" && layer.spec.step)) {
        if (!Number.isFinite(c[i * 4]) || !Number.isFinite(c[i * 4 + 1])) continue;
        out.push({ layer: li, instance: i, x: c[i * 4], y: c[i * 4 + 1] });
        // the line's last point: the end of a piece the next does not go on from
        const goesOn = i + 1 < end && c[(i + 1) * 4] === c[i * 4 + 2] && c[(i + 1) * 4 + 1] === c[i * 4 + 3];
        if (!goesOn && Number.isFinite(c[i * 4 + 2]) && Number.isFinite(c[i * 4 + 3])) out.push({ layer: li, instance: i, x: c[i * 4 + 2], y: c[i * 4 + 3] });
        continue;
      }
      const pt = hitPoint({ layer, instance: i, distance: 0 }, UNIT, 0, 0, horizontal);
      if (Number.isFinite(pt.x) && Number.isFinite(pt.y)) out.push({ layer: li, instance: i, x: pt.x, y: pt.y });
    }
  });
  return out.sort((a, b) => a.x - b.x || a.y - b.y || a.layer - b.layer);
}

/** A panel's stops for a spec drawn with bars along y or not (as Python decides). */
export function stopsOf(scene: Scene, p: number, spec: { x: { kind: string }; y: { kind: string } }, hidden?: (layer: LayerData, i: number) => boolean): Stop[] {
  return markStops(scene, p, barsAlongY(spec), hidden);
}

/** The stop to go to from stop `k` (-1: none yet): `step` along the list (← →), or `up`
 * (↑ -1, ↓ 1): the nearest on screen above or below, straight up counting more than aside.
 * `map`: the panel's, to measure on screen. Null: none that way. */
export function nextStop(stops: Stop[], k: number, move: { step?: number; up?: number; to?: "first" | "last" }, map: PanelMap): number | null {
  const n = stops.length;
  if (!n) return null;
  if (move.to === "first") return 0;
  if (move.to === "last") return n - 1;
  if (k < 0 || k >= n) return move.step !== undefined && move.step < 0 ? n - 1 : 0;
  if (move.step) {
    const j = k + move.step;
    return j >= 0 && j < n ? j : null;
  }
  if (!move.up) return k;
  const px = (s: Stop): number => map.ox + s.x * map.sx;
  const py = (s: Stop): number => map.oy + s.y * map.sy;
  const hx = px(stops[k]);
  const hy = py(stops[k]);
  let best: number | null = null;
  let cost = Infinity;
  for (let j = 0; j < n; j++) {
    const dy = py(stops[j]) - hy;
    if (move.up < 0 ? dy >= -0.5 : dy <= 0.5) continue;
    const c = 4 * Math.abs(px(stops[j]) - hx) + Math.abs(dy);
    if (c < cost) {
      cost = c;
      best = j;
    }
  }
  return best;
}
