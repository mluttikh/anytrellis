import { describe, expect, it } from "vitest";
import { layout } from "../src/core/layout";
import { type Scene, pick } from "../src/core/scene";
import { KIND_CAPSULE, KIND_RECT } from "../src/core/renderers/renderer";
import { deviceClip } from "../src/core/renderers/renderer";
import { formatNumber, formatValue, niceStep, ticks } from "../src/core/ticks";
import type { MarkLayerSpec, PanelSpec, TrellisSpec } from "../src/core/types";

const DAY = 86_400_000;

describe("ticks", () => {
  it("steps by 1, 2 or 5 times a power of ten", () => {
    expect(niceStep(10, 5)).toBe(2);
    expect(niceStep(1, 4)).toBe(0.2);
    expect(niceStep(700, 5)).toBe(100);
    expect(ticks("number", 0, 10, 0, 5).map((t) => t.value)).toEqual([0, 2, 4, 6, 8, 10]);
  });

  it("labels relative to the origin", () => {
    const t = ticks("number", -1, 1, 1000, 2);
    expect(t.map((x) => x.label)).toEqual(["999", "1000", "1001"]);
  });

  it("formats large numbers with suffixes and minus signs", () => {
    expect(formatNumber(2_500_000, 500_000, 0)).toBe("2.5M");
    expect(formatNumber(-3, 1, 0)).toBe("−3");
    expect(formatNumber(1e-12, 0.1, 1)).toBe("0.0");
  });

  it("puts time ticks on calendar days, weeks starting Monday, and months", () => {
    const origin = Date.UTC(2026, 2, 1);
    const days = ticks("time", 0, 5 * DAY, origin, 5);
    expect(days.map((t) => t.label)).toEqual(["Mar 1", "Mar 2", "Mar 3", "Mar 4", "Mar 5", "Mar 6"]);
    const weeks = ticks("time", 0, 28 * DAY, origin, 4);
    for (const t of weeks) expect(new Date(t.value + origin).getUTCDay()).toBe(1);
    const months = ticks("time", 0, 365 * DAY, Date.UTC(2026, 0, 1), 6);
    expect(months.map((t) => t.label)).toEqual(["2026", "Apr", "Jul", "Oct", "2027"]);
  });

  it("thins band ticks to fit", () => {
    const levels = Array.from({ length: 12 }, (_, i) => `L${i}`);
    expect(ticks("band", -0.5, 11.5, 0, 12, levels)).toHaveLength(12);
    expect(ticks("band", -0.5, 11.5, 0, 4, levels).map((t) => t.label)).toEqual(["L0", "L3", "L6", "L9"]);
  });

  it("formats values at the precision of the view", () => {
    expect(formatValue("band", 2, 0, 1, ["a", "b", "c"])).toBe("c");
    expect(formatValue("time", DAY / 2, Date.UTC(2026, 0, 1), DAY)).toBe("2026-01-01 12:00");
    expect(formatValue("number", 1.23456, 0, 10)).toBe("1.23");
  });
});

function panel(row: number, col: number, xg = 0, yg = 0): PanelSpec {
  return { row, col, label: "", keys: [], x: [0, 1], y: [0, 1], xg, yg };
}

function spec(panels: PanelSpec[], rows: number, cols: number, kind: "grid" | "wrap" = "wrap"): TrellisSpec {
  return {
    version: 1,
    title: "",
    grid: { kind, rows, cols, row_labels: kind === "grid" ? ["r0", "r1"] : [], col_labels: kind === "grid" ? ["c0", "c1"] : [], row_title: "", col_title: "" },
    panels,
    x: { kind: "number", levels: null, origin: 0, share: "all", title: "" },
    y: { kind: "number", levels: null, origin: 0, share: "all", title: "" },
    layers: [],
    legends: [],
    height: null,
    panel_height: 100,
  };
}

const opts = { width: 600, fontSize: 12, measure: (t: string) => t.length * 7 };

describe("layout", () => {
  it("labels only the outer panels when scales are shared", () => {
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(1, 0), panel(1, 1)], 2, 2), opts);
    expect(l.panels.map((p) => p.showX)).toEqual([false, false, true, true]);
    expect(l.panels.map((p) => p.showY)).toEqual([true, false, true, false]);
    expect(l.yAxisWidth[1]).toBe(0);
  });

  it("labels every panel when scales are free", () => {
    const l = layout(spec([panel(0, 0, 0, 0), panel(0, 1, 1, 1), panel(1, 0, 2, 2), panel(1, 1, 3, 3)], 2, 2), opts);
    expect(l.panels.every((p) => p.showX && p.showY)).toBe(true);
  });

  it("labels the x axis of a panel above an empty cell of a wrap", () => {
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(0, 2), panel(1, 0)], 2, 3), opts);
    expect(l.panels.map((p) => p.showX)).toEqual([false, true, true, true]);
  });

  it("draws that axis into the empty cell, keeping the rows evenly spaced", () => {
    const full = layout(spec([panel(0, 0), panel(0, 1), panel(0, 2), panel(1, 0), panel(1, 1), panel(1, 2)], 2, 3), opts);
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(0, 2), panel(1, 0)], 2, 3), opts);
    expect(l.panels[3].rect.y).toBe(full.panels[3].rect.y);
    expect(l.height).toBe(full.height);
    // the axis fits in the space the empty cell leaves
    const above = l.panels[2].rect;
    expect(l.panels[3].strip!.y + l.panels[3].rect.h - (above.y + above.h)).toBeGreaterThan(l.xAxisHeight);
  });

  it("gives the legend a wrap's empty cells, below the axes drawn into them", () => {
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(0, 2), panel(1, 0)], 2, 3), opts);
    const spare = l.spare!;
    const [, b, c, d] = l.panels.map((p) => p.rect);
    expect(spare.x).toBeGreaterThan(d.x + d.w);
    expect(spare.x + spare.w).toBe(c.x + c.w);
    expect(spare.y).toBeGreaterThanOrEqual(b.y + b.h + l.xAxisHeight);
    expect(spare.y + spare.h).toBe(d.y + d.h);
    const full = layout(spec([panel(0, 0), panel(0, 1), panel(1, 0), panel(1, 1)], 2, 2), opts);
    expect(full.spare).toBeNull();
    expect(layout(spec([panel(0, 0), panel(1, 1)], 2, 2, "grid"), opts).spare).toBeNull();
  });

  it("puts y labels into an empty cell on the left, with no gutter", () => {
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(1, 1)], 2, 2, "grid"), opts);
    expect(l.panels.map((p) => p.showY)).toEqual([true, false, true]);
    expect(l.yAxisWidth[1]).toBe(0);
  });

  it("fits the panels in the width, with equal sizes and no overlap", () => {
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(1, 0), panel(1, 1)], 2, 2, "grid"), opts);
    const [a, b, c] = l.panels.map((p) => p.rect);
    expect(a.w).toBe(b.w);
    expect(a.h).toBe(100);
    expect(b.x).toBeGreaterThanOrEqual(a.x + a.w);
    expect(c.y).toBeGreaterThanOrEqual(a.y + a.h);
    expect(l.strips.filter((s) => s.vertical)).toHaveLength(2);
    const right = Math.max(...l.strips.map((s) => s.rect.x + s.rect.w));
    expect(right).toBeLessThanOrEqual(600);
    expect(l.height).toBeGreaterThan(c.y + c.h);
  });

  it("puts a strip over every panel of a wrap", () => {
    const l = layout(spec([panel(0, 0), panel(0, 1)], 1, 2), opts);
    for (const p of l.panels) expect(p.strip!.y + p.strip!.h).toBeLessThanOrEqual(p.rect.y);
  });
});

function layer(type: MarkLayerSpec["type"], coords: number[], kind: number, halfWidth: number, context = false) {
  const n = coords.length / 4;
  return {
    spec: { type, context } as MarkLayerSpec,
    index: 0,
    coords: new Float64Array(coords),
    starts: new Uint32Array([0, n]),
    set: { key: "k", version: 1, count: n, coords: new Float32Array(coords), colors: new Uint8Array(n * 4) },
    codes: null,
    kind,
    halfWidth,
  };
}

describe("pick", () => {
  const map = { sx: 10, ox: 0, sy: -10, oy: 100 }; // x px = 10x, y px = 100 - 10y

  it("finds the nearest point within the radius", () => {
    const scene = { layers: [layer("points", [1, 1, 1, 1, 5, 5, 5, 5], KIND_CAPSULE, 2)] } as unknown as Scene;
    expect(pick(scene, 0, map, 52, 50, 4)?.instance).toBe(1);
    expect(pick(scene, 0, map, 30, 30, 4)).toBeNull();
  });

  it("is inside a bar, and skips context layers", () => {
    const bars = layer("bars", [0, 0, 2, 5], KIND_RECT, 0);
    const context = layer("points", [1, 2, 1, 2], KIND_CAPSULE, 3, true);
    const scene = { layers: [bars, context] } as unknown as Scene;
    const hit = pick(scene, 0, map, 10, 80, 4)!;
    expect(hit.layer).toBe(bars);
    expect(hit.distance).toBe(0);
  });
});

describe("deviceClip", () => {
  it("scales by the pixel ratio and stays in the canvas", () => {
    expect(deviceClip({ x: 10, y: 10, w: 20, h: 20 }, 2, 1000, 1000)).toEqual([20, 20, 40, 40]);
    expect(deviceClip({ x: -5, y: 0, w: 10, h: 10 }, 1, 100, 100)).toEqual([0, 0, 5, 10]);
    expect(deviceClip({ x: 200, y: 0, w: 10, h: 10 }, 1, 100, 100)).toBeNull();
  });
});

describe("an opened panel", () => {
  it("takes the whole width and height, with both axes and a strip naming it", () => {
    const s = spec([panel(0, 0), panel(0, 1), panel(1, 0)], 2, 2);
    s.panels[1].keys = ["north", "s1"];
    const l = layout(s, { ...opts, focused: 1, height: 400 });
    expect(l.panels).toHaveLength(1);
    const [box] = l.panels;
    expect(box.index).toBe(1);
    expect(box.showX && box.showY).toBe(true);
    expect(box.label).toBe("north · s1");
    expect(box.rect.x + box.rect.w).toBeLessThanOrEqual(600);
    expect(box.rect.w).toBeGreaterThan(500);
    expect(l.height).toBeLessThanOrEqual(402);
    expect(box.strip!.y + box.strip!.h).toBeLessThanOrEqual(box.rect.y);
  });

  it("fills a given height in the grid too (full screen)", () => {
    const s = spec([panel(0, 0), panel(0, 1), panel(1, 0), panel(1, 1)], 2, 2);
    const small = layout(s, opts);
    const full = layout(s, { ...opts, height: 900 });
    expect(full.panels[0].rect.h).toBeGreaterThan(small.panels[0].rect.h);
    expect(Math.abs(full.height - 900)).toBeLessThan(4);
  });
});
