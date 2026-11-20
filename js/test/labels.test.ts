import { describe, expect, it } from "vitest";
import type { PanelView } from "../src/core/drawing";
import { END_GAP, endLabels, repel, spread } from "../src/core/labels";
import type { LayerData } from "../src/core/scene";

const rect = { x: 0, y: 0, w: 200, h: 100 };

describe("labels at the ends of lines", () => {
  it("moves labels apart and leaves out those too far from their lines", () => {
    const ls = [50, 51, 52, 200].map((y) => ({ y }));
    const kept = spread(ls, 0, 300, 10, 15);
    expect(kept).toEqual([0, 1, 3]); // the third would move 20 px
    const crowd = [95, 95, 95].map((y) => ({ y }));
    for (const i of spread(crowd, 0, 100, 10, 30)) expect(crowd[i].y).toBeLessThanOrEqual(100);
  });

  it("names each series once, at its last point in the rightmost panel", () => {
    // two panels side by side, a series each of two segments in both
    const coords = new Float32Array([0, 0, 1, 1, 1, 1, 2, 0, 0, 1, 1, 2, 1, 2, 2, 2]);
    const colors = new Uint8Array(16).fill(255);
    const layer = {
      spec: { end_labels: { names: ["a", "b"], series: { id: "s", dtype: "uint16", count: 4 }, legend: 0 } },
      endSeries: new Uint16Array([0, 0, 1, 1]),
      coords,
      starts: new Uint32Array([0, 4, 4]),
      set: { colors },
    } as unknown as LayerData;
    const map = (ox: number) => ({ ox, oy: 90, sx: 40, sy: -40 });
    const views = [0, 1].map((p): PanelView => ({ panel: p, rect: { x: p * 300, y: 0, w: 200, h: 100 }, map: map(p * 300 + 10), x: [0, 4], y: [0, 2] }));
    // the second panel's slice: the same instances, shown there too
    (layer as unknown as { starts: Uint32Array }).starts = new Uint32Array([0, 4, 8]);
    (layer as unknown as { coords: Float32Array }).coords = new Float32Array([...coords, ...coords]);
    (layer as unknown as { endSeries: Uint16Array }).endSeries = new Uint16Array([0, 0, 1, 1, 0, 0, 1, 1]);
    const out = endLabels([layer], views, (t) => t.length * 6, 12);
    expect(out.map((e) => [e.text, e.panel]).sort()).toEqual([["a", 1], ["b", 1]]);
    const a = out.find((e) => e.text === "a")!;
    expect(a.ax).toBe(300 + 10 + 2 * 40);
    expect(a.x).toBe(a.ax + END_GAP);
    expect(a.legend).toBe(0);
    const hidden = endLabels([layer], views, (t) => t.length * 6, 12, (_, s) => s === 0);
    expect(hidden.map((e) => e.text)).toEqual(["b"]);
  });
});

describe("labels kept apart (repel)", () => {
  it("places labels right of their point first, then around it, inside the panel", () => {
    const pts = [0, 1, 2, 3].map((i) => ({ index: i, x: 100, y: 50, w: 40 }));
    const placed = repel(pts, 10, rect, 4);
    expect(placed[0]).toEqual({ index: 0, x: 104, y: 50, leader: null });
    expect(placed[1].x).toBe(100 - 4 - 40); // left
    const boxes = placed.map((p) => [p.x, p.y - 5, 40, 10]);
    boxes.forEach((a, i) => {
      for (const b of boxes.slice(i + 1)) expect(a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3]).toBe(false);
    });
  });

  it("leaves out labels with no room, and draws a line back from farther out", () => {
    const pts = Array.from({ length: 30 }, (_, i) => ({ index: i, x: 100, y: 50, w: 40 }));
    const placed = repel(pts, 10, rect, 4);
    expect(placed.length).toBeGreaterThan(4);
    expect(placed.length).toBeLessThan(30);
    expect(placed.some((p) => p.leader !== null)).toBe(true);
    for (const p of placed) expect(p.x >= 0 && p.x + 40 <= 200 && p.y - 5 >= 0 && p.y + 5 <= 100).toBe(true);
  });
});
