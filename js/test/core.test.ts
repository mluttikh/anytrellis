import { describe, expect, it } from "vitest";
import { layout } from "../src/core/layout";
import { type Scene, pick, yExtent } from "../src/core/scene";
import { FADED, filled, highlighted, select, selectionColors } from "../src/core/selection";
import { KIND_CAPSULE, KIND_RECT, KIND_TRAP } from "../src/core/renderers/renderer";
import { deviceClip } from "../src/core/renderers/renderer";
import { formatNumber, formatValue, minorTicks, niceStep, ticks } from "../src/core/ticks";
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

  it("puts log ticks on decades, with 2 and 5 between when they fit", () => {
    const labels = (lo: number, hi: number, count: number) => ticks("log", lo, hi, 0, count).map((t) => t.label);
    expect(labels(0, 3, 5)).toEqual(["1", "10", "100", "1000"]);
    expect(labels(0, 1, 6)).toEqual(["1", "2", "5", "10"]);
    expect(labels(-2, 0, 6)).toEqual(["0.01", "0.02", "0.05", "0.1", "0.2", "0.5", "1"]);
    expect(labels(0, 8, 4)).toEqual(["1", "100", "10000", "1M", "100M"]);
    expect(labels(Math.log10(20), Math.log10(60), 4)).toEqual(["20", "30", "40", "50", "60"]);
    for (const t of ticks("log", Math.log10(20), Math.log10(60), 0, 4)) expect(Number.isFinite(t.value)).toBe(true);
    expect(formatValue("log", 2, 0, 3)).toBe("100");
    // between the labelled decades: the skipped ones, and 2 to 9 times each with room
    const major = ticks("log", 0, 8, 0, 4);
    expect(minorTicks("log", 0, 8, 0, major, 100)).toEqual([1, 3, 5, 7]);
    const fine = minorTicks("log", 0, 1, 0, ticks("log", 0, 1, 0, 6), 400).map((v) => Math.round(10 ** v));
    expect(fine).toEqual([3, 4, 6, 7, 8, 9]);
    expect(minorTicks("number", 0, 1, 0, [], 400)).toEqual([]);
    expect(formatValue("log", Math.log10(1234.5), 0, 0.5)).toBe("1235");
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

  it("knows where each axis is drawn, for zooming one axis there", () => {
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(1, 0), panel(1, 1)], 2, 2), opts);
    const [a, , c] = l.panels;
    expect(a.xAxis).toBeNull(); // shared x: only the bottom row draws it
    expect(c.xAxis).toEqual({ x: c.rect.x, y: c.rect.y + c.rect.h, w: c.rect.w, h: l.xAxisHeight });
    expect(a.yAxis!.x + a.yAxis!.w).toBe(a.rect.x);
    expect(a.yAxis!.w).toBeGreaterThan(0);
    expect(l.panels[1].yAxis).toBeNull();
    const one = layout(spec([panel(0, 0), panel(0, 1)], 1, 2), { ...opts, focused: 1 });
    expect(one.panels[0].xAxis).not.toBeNull();
    expect(one.panels[0].yAxis).not.toBeNull();
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
    link: null as Uint32Array | null,
    groups: null as Uint32Array | null,
    tipRows: null as Uint32Array | null,
    base: null as Float64Array | null,
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

describe("yExtent", () => {
  it("clips a line to the x window, at its y there", () => {
    // a segment from (0, 0) to (10, 10), and one from (10, 10) to (20, 0)
    const line = layer("line", [0, 0, 10, 10, 10, 10, 20, 0], KIND_CAPSULE, 1);
    const scene = { layers: [line] } as unknown as Scene;
    expect(yExtent(scene, 0, 2, 5)).toMatchObject({ lo: 2, hi: 5 });
    expect(yExtent(scene, 0, 5, 15)).toMatchObject({ lo: 5, hi: 10 });
    expect(yExtent(scene, 0, 30, 40)).toBeNull();
  });

  it("keeps bars' base, and skips context layers", () => {
    const bars = layer("bars", [0, 0, 2, 5, 4, 0, 6, 3], KIND_RECT, 0);
    const context = layer("points", [5, 100, 5, 100], KIND_CAPSULE, 3, true);
    const scene = { layers: [bars, context] } as unknown as Scene;
    expect(yExtent(scene, 0, 3, 7)).toEqual({ lo: 0, hi: 3, baseLo: true, baseHi: false });
  });
});

describe("select", () => {
  it("selects points inside, segments with an end inside, bars overlapping", () => {
    const points = layer("points", [1, 1, 1, 1, 5, 5, 5, 5], KIND_CAPSULE, 2);
    const line = layer("line", [0, 0, 2, 2, 2, 2, 9, 9], KIND_CAPSULE, 1);
    const bars = layer("bars", [3, 0, 4, 8], KIND_RECT, 0);
    const scene = { layers: [points, line, bars] } as unknown as Scene;
    const s = select(scene, { x: [0.5, 3.5], y: null });
    expect([...s.masks[0]!]).toEqual([1, 0]);
    expect([...s.masks[1]!]).toEqual([1, 1]); // the second segment starts at x = 2
    expect([...s.masks[2]!]).toEqual([1]);
    expect(s.selected).toBe(4);
    expect(s.total).toBe(5);
    expect(select(scene, { x: [6, 7], y: [6, 7] }).selected).toBe(0);
  });

  it("grows by link keys across layers, and skips context", () => {
    const a = { ...layer("points", [1, 1, 1, 1, 5, 5, 5, 5], KIND_CAPSULE, 2), link: new Uint32Array([7, 8]) };
    const b = { ...layer("points", [9, 9, 9, 9], KIND_CAPSULE, 2), link: new Uint32Array([7]) };
    const context = layer("points", [1, 1, 1, 1], KIND_CAPSULE, 2, true);
    const scene = { layers: [a, b, context] } as unknown as Scene;
    const s = select(scene, { x: [0, 2], y: null });
    expect([...s.masks[0]!]).toEqual([1, 0]);
    expect([...s.masks[1]!]).toEqual([1]); // key 7, far from the brush
    expect(s.masks[2]).toBeNull();
  });

  it("in one panel, selects there and the link follows the keys into the others", () => {
    // panel 0: keys 7 (x 1) and 8 (x 5); panel 1: keys 7 (x 1) and 8 (x 9)
    const l = { ...layer("points", [1, 1, 1, 1, 5, 5, 5, 5, 1, 1, 1, 1, 9, 9, 9, 9], KIND_CAPSULE, 2), link: new Uint32Array([7, 8, 7, 8]) };
    l.starts = new Uint32Array([0, 2, 4]);
    const scene = { layers: [l] } as unknown as Scene;
    expect([...select(scene, { x: [4, 10], y: null, panel: 1 }).masks[0]!]).toEqual([0, 1, 0, 1]);
    expect([...select(scene, { x: [4, 10], y: null }).masks[0]!]).toEqual([0, 1, 0, 1]);
    const unlinked = { ...l, link: null };
    expect([...select({ layers: [unlinked] } as unknown as Scene, { x: [4, 10], y: null, panel: 1 }).masks[0]!]).toEqual([0, 0, 0, 1]);
  });

  it("selects a box whole: what meets its body selects its lines, in its family only", () => {
    // two boxes: bodies at x 0..1 and 2..3; their whiskers (lines) above, at x 0.5 and 2.5
    const body = { ...layer("rect", [0, 1, 1, 2, 2, 1, 3, 2], KIND_RECT, 0), groups: new Uint32Array([0, 1]) };
    body.spec = { ...body.spec, family: 4 };
    const lines = { ...layer("line", [0.5, 2, 0.5, 5, 2.5, 2, 2.5, 5], KIND_CAPSULE, 1), groups: new Uint32Array([0, 1]) };
    lines.spec = { ...lines.spec, family: 4 };
    const other = { ...layer("line", [2.5, 4, 2.5, 5], KIND_CAPSULE, 1), groups: new Uint32Array([0]) };
    other.spec = { ...other.spec, family: 9 };
    const scene = { layers: [body, lines, other] } as unknown as Scene;
    const s = select(scene, { x: [2.2, 2.8], y: [1.2, 1.5] }); // inside the second body only
    expect([...s.masks[0]!]).toEqual([0, 1]);
    expect([...s.masks[1]!]).toEqual([0, 1]); // its whisker, though no end is in the brush
    expect([...s.masks[2]!]).toEqual([0]); // another family's group 0: not selected
  });

  it("fades the rest and draws the selected on top", () => {
    const l = layer("points", [1, 1, 1, 1, 5, 5, 5, 5], KIND_CAPSULE, 2);
    l.set.colors.set([10, 20, 30, 200, 40, 50, 60, 255]);
    const { dim, hi } = selectionColors(l as never, new Uint8Array([0, 1]), null);
    expect(dim[3]).toBe(Math.round(200 * FADED));
    expect([...hi]).toEqual([0, 0, 0, 0, 40, 50, 60, 255]);
  });
});

describe("a linked plot's highlight", () => {
  it("selects the masked marks and fills bars to their share", () => {
    const points = { ...layer("points", [1, 1, 1, 1, 5, 5, 5, 5], KIND_CAPSULE, 2), index: 0 };
    const bars = { ...layer("bars", [0, 0, 1, 10, 1, 0, 2, 4], KIND_RECT, 0), index: 2 };
    const scene = { layers: [points, bars] } as unknown as Scene;
    const h = highlighted(scene, { layers: [{ mask: new Uint8Array([0, 1]) }, null, { fraction: new Float32Array([0.25, 0]) }] });
    expect([...h!.selection.masks[0]!]).toEqual([0, 1]);
    expect([...h!.selection.masks[1]!]).toEqual([1, 0]);
    expect(h!.selection.selected).toBe(2);
    expect([...filled(bars.set.coords, h!.fractions[1]!)]).toEqual([0, 0, 1, 2.5, 1, 0, 2, 0]);
  });

  it("leaves out what no longer fits the layers (an older spec)", () => {
    const points = layer("points", [1, 1, 1, 1], KIND_CAPSULE, 2);
    const scene = { layers: [points] } as unknown as Scene;
    expect(highlighted(scene, { layers: [{ mask: new Uint8Array([1, 1, 1]) }] })).toBeNull();
    expect(highlighted(scene, { layers: [null] })).toBeNull();
  });
});

describe("areas", () => {
  // a trapezoid from (0, 4) to (10, 8), down to a base at 2
  const area = () => {
    const l = layer("area", [0, 4, 10, 8], KIND_TRAP, 0);
    l.base = new Float64Array([2, 2]);
    (l.set as { base?: Float32Array }).base = new Float32Array([2, 2]);
    return l;
  };
  const map = { sx: 10, ox: 0, sy: -10, oy: 100 }; // x px = 10x, y px = 100 - 10y

  it("is hovered inside, between its top and its base", () => {
    const scene = { layers: [area()], baseY: new Float64Array([0]) } as unknown as Scene;
    expect(pick(scene, 0, map, 50, 100 - 10 * 4, 4)?.distance).toBe(0); // x 5, y 4
    expect(pick(scene, 0, map, 50, 100 - 10 * 1, 4)).toBeNull(); // below the base
  });

  it("fits y to its top and its base", () => {
    const scene = { layers: [area()], baseY: new Float64Array([0]) } as unknown as Scene;
    expect(yExtent(scene, 0, 0, 5)).toEqual({ lo: 2, hi: 6, baseLo: true, baseHi: false });
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
