// Text next to the data (Python: figure.py does the same): labels at the ends of lines
// (`line(label="end")`), text labels that keep out of each other's way (`repel=True`), and
// placing either in a panel's pixels, frame by frame, as the view zooms.

import type { PanelView } from "./drawing";
import type { Rect } from "./layout";
import type { LayerData } from "./scene";

/** A label at the end of a line: its series' name at the line's last point in view. */
export interface EndLabel {
  panel: number;
  /** The text's left and middle (CSS px), and the point it labels. */
  x: number;
  y: number;
  ax: number;
  ay: number;
  text: string;
  color: string;
  w: number;
  /** The layer (index in scene.layers), its series, and the colour legend whose level it
   * is (null: none): hovering it shows that level's marks, a click selects them. */
  layer: number;
  series: number;
  legend: number | null;
}

/** Room between a line's end and its label, and between labels (px). */
export const END_GAP = 5;

/** The labels at the ends of the lines labelled so: each series once in the plot, in the
 * panel where its line ends rightmost (then the top one), at the line's last point in view;
 * in each panel moved apart up or down so none covers another, and kept inside it.
 * `hidden`: a series not drawn (another shown alone). */
export function endLabels(layers: LayerData[], views: PanelView[], measure: (text: string) => number, fs: number, hidden: (layer: LayerData, series: number) => boolean = () => false): EndLabel[] {
  const out: EndLabel[] = [];
  layers.forEach((layer, li) => {
    const ends = layer.spec.end_labels;
    const series = layer.endSeries;
    if (!ends || !series) return;
    // each series' last point on screen in each panel
    const best = new Map<number, { v: PanelView; px: number; py: number; i: number }>();
    for (const v of views) {
      const { map, rect: r } = v;
      const here = new Map<number, { px: number; py: number; i: number }>();
      const c = layer.coords;
      for (let i = layer.starts[v.panel]; i < layer.starts[v.panel + 1]; i++) {
        const s = series[i];
        for (const k of [0, 2]) {
          const px = map.ox + c[i * 4 + k] * map.sx;
          const py = map.oy + c[i * 4 + k + 1] * map.sy;
          if (!(px >= r.x - 0.5 && px <= r.x + r.w + 0.5) || !Number.isFinite(py)) continue;
          const had = here.get(s);
          if (!had || px > had.px) here.set(s, { px, py, i });
        }
      }
      for (const [s, h] of here) {
        if (hidden(layer, s)) continue;
        const had = best.get(s);
        const better = !had || v.rect.x > had.v.rect.x + 0.5 || (Math.abs(v.rect.x - had.v.rect.x) <= 0.5 && v.rect.y < had.v.rect.y);
        if (better) best.set(s, { v, ...h });
      }
    }
    for (const [s, b] of best) {
      const r = b.v.rect;
      const text = ends.names[s] ?? "";
      const w = measure(text);
      const ay = Math.min(r.y + r.h, Math.max(r.y, b.py));
      const x = Math.max(r.x + 2, Math.min(b.px + END_GAP, r.x + r.w - 2 - w));
      const k = b.i * 4;
      const col = layer.set.colors;
      out.push({ panel: b.v.panel, x, y: ay, ax: b.px, ay, text, color: `rgb(${col[k]},${col[k + 1]},${col[k + 2]})`, w, layer: li, series: s, legend: ends.legend ?? null });
    }
  });
  // in each panel, apart from each other
  const byPanel = new Map<number, EndLabel[]>();
  for (const l of out) byPanel.set(l.panel, [...(byPanel.get(l.panel) ?? []), l]);
  const kept: EndLabel[] = [];
  for (const [p, ls] of byPanel) {
    const r = views.find((v) => v.panel === p)!.rect;
    for (const i of spread(ls, r.y + fs / 2, r.y + r.h - fs / 2, fs + 2, 2 * fs)) kept.push(ls[i]);
  }
  return kept;
}

/** Labels' middles moved apart to at least `gap` from where they want to be (`y`), inside
 * `lo`..`hi`: down past the one above, then (crowded at the bottom) up again. A label that
 * would end up more than `far` from its place is left out (too far to tell whose it is; as
 * many as fit, then, in a crowd). Returns the indices kept, in order of y. */
export function spread(ls: { y: number }[], lo: number, hi: number, gap: number, far: number): number[] {
  const order = ls.map((_, i) => i).sort((a, b) => ls[a].y - ls[b].y);
  const want = ls.map((l) => l.y);
  const kept: number[] = [];
  let last = -Infinity;
  for (const i of order) {
    const y = Math.max(want[i], lo, last + gap);
    if (y - want[i] > far || y > hi + far) continue;
    ls[i].y = y;
    last = y;
    kept.push(i);
  }
  let next = Infinity;
  for (let k = kept.length - 1; k >= 0; k--) {
    const l = ls[kept[k]];
    l.y = Math.min(l.y, hi, next - gap);
    next = l.y;
  }
  return kept;
}

/** A text label placed by `repel`: its text's left and middle, and (moved away from its
 * point) the line back to it. */
export interface Placed {
  index: number;
  x: number;
  y: number;
  /** The point, when the label is a step away from it (a leader line goes back). */
  leader: { x: number; y: number } | null;
}

/** Where each label goes, keeping clear of the others and of the points labelled: the
 * first spot of several around its point (right, left, above, below, the corners, then
 * farther out, a label's height a step) where it covers no label placed before it, inside
 * the panel; none: left out (zooming in makes room). `d`: the distance from the point (px);
 * `h`: a label's height. */
export function repel(points: { index: number; x: number; y: number; w: number }[], h: number, r: Rect, d: number): Placed[] {
  const boxes = new Grid(32);
  for (const p of points) boxes.add(p.x - 2, p.y - 2, 4, 4);
  const out: Placed[] = [];
  for (const p of points) {
    for (const [ring, k] of SPOTS) {
      const far = d + ring * 1.2 * h;
      const [dx, dy] = k;
      // the text's box: beside the point, centred above or below it, or at a corner
      const left = dx > 0 ? p.x + far : dx < 0 ? p.x - far - p.w : p.x - p.w / 2;
      const top = dy > 0 ? p.y + far : dy < 0 ? p.y - far - h : p.y - h / 2;
      if (left < r.x || left + p.w > r.x + r.w || top < r.y || top + h > r.y + r.h) continue;
      if (boxes.hits(left, top, p.w, h)) continue;
      boxes.add(left, top, p.w, h);
      out.push({ index: p.index, x: left, y: top + h / 2, leader: ring > 0 ? { x: p.x, y: p.y } : null });
      break;
    }
  }
  return out;
}

/** The spots tried around a point, in order: [ring, [dx, dy]]; ring k at d + 1.2 k label
 * heights. */
const DIRS: [number, number][] = [[1, 0], [-1, 0], [0, -1], [0, 1], [1, -1], [-1, -1], [1, 1], [-1, 1]];
const SPOTS: [number, [number, number]][] = [0, 1, 2].flatMap((ring) => DIRS.map((k): [number, [number, number]] => [ring, k]));

/** Boxes in buckets of a square grid, to find those a box overlaps quickly. */
class Grid {
  private cells = new Map<string, [number, number, number, number][]>();
  constructor(private size: number) {}
  private keys(x: number, y: number, w: number, h: number): string[] {
    const out: string[] = [];
    for (let i = Math.floor(x / this.size); i <= Math.floor((x + w) / this.size); i++) for (let j = Math.floor(y / this.size); j <= Math.floor((y + h) / this.size); j++) out.push(`${i},${j}`);
    return out;
  }
  add(x: number, y: number, w: number, h: number): void {
    for (const k of this.keys(x, y, w, h)) {
      const list = this.cells.get(k);
      if (list) list.push([x, y, w, h]);
      else this.cells.set(k, [[x, y, w, h]]);
    }
  }
  hits(x: number, y: number, w: number, h: number): boolean {
    for (const k of this.keys(x, y, w, h)) for (const [bx, by, bw, bh] of this.cells.get(k) ?? []) if (x < bx + bw && bx < x + w && y < by + bh && by < y + h) return true;
    return false;
  }
}
