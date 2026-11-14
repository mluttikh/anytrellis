import { describe, expect, it } from "vitest";
import { fileName, fontAttributes, paint, SvgContext, svgMessage } from "../src/core/export";
import { crowdedRight, labelEnd } from "../src/core/drawing";
import { layout } from "../src/core/layout";
import { pageLabels, pageList, panelOrder } from "../src/core/pages";
import { type Scene, buildScene, hitPoint, pick, yExtent } from "../src/core/scene";
import { BufferStore } from "../src/core/transport";
import { FADED, filled, highlighted, select, selectionColors, selects, toggleLegend } from "../src/core/selection";
import { KIND_CAPSULE, KIND_RECT, KIND_TRAP } from "../src/core/renderers/renderer";
import { drawMarks } from "../src/core/renderers/canvas2d";
import { deviceClip } from "../src/core/renderers/renderer";
import { formatNumber, formatValue, minorTicks, niceStep, ticks } from "../src/core/ticks";
import type { MarkLayerSpec, PanelSpec, PanelStat, Paging, TrellisSpec } from "../src/core/types";

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

describe("nested strips", () => {
  const keyed = (row: number, col: number, keys: string[]): PanelSpec => ({ ...panel(row, col), keys, label: keys.join(" · ") });

  it("span the columns and rows of a grid sharing a level", () => {
    const s = spec([0, 1, 2].flatMap((c) => [panel(0, c), panel(1, c)]), 2, 3, "grid");
    s.grid = { ...s.grid, col_labels: ["A · x", "A · y", "B · x"], col_keys: [["A", "x"], ["A", "y"], ["B", "x"]], row_labels: ["n · 1", "n · 2"], row_keys: [["n", "1"], ["n", "2"]] };
    const l = layout(s, opts);
    const top = l.strips.filter((t) => !t.vertical);
    const [a, b] = top.filter((t) => t.rect.y === top[0].rect.y);
    expect([a.label, b.label]).toEqual(["A", "B"]);
    const cols = l.panels.filter((p) => p.rect.y === l.panels[0].rect.y).map((p) => p.rect);
    expect(a.rect.x).toBe(cols[0].x);
    expect(a.rect.x + a.rect.w).toBe(cols[1].x + cols[1].w); // A over its two columns
    expect(top.filter((t) => t.rect.y > a.rect.y).map((t) => t.label)).toEqual(["x", "y", "x"]);
    const right = l.strips.filter((t) => t.vertical);
    const outer = right.filter((t) => t.label === "n");
    expect(outer).toHaveLength(1); // n over both rows, outermost on the right
    expect(Math.min(...right.map((t) => t.rect.x))).toBeLessThan(outer[0].rect.x);
    expect(right.filter((t) => t.label !== "n").map((t) => t.label)).toEqual(["1", "2"]);
    // joined: a strip a column and a row, as before
    s.grid.strips = "joined";
    const j = layout(s, opts);
    expect(j.strips.map((t) => t.label)).toEqual(["A · x", "A · y", "B · x", "n · 1", "n · 2"]);
    expect(l.panels[0].rect.y).toBeGreaterThan(j.panels[0].rect.y); // two strips high
  });

  it("span a wrap's panels side by side in a row", () => {
    const s = spec([keyed(0, 0, ["north", "a"]), keyed(0, 1, ["north", "b"]), keyed(0, 2, ["south", "a"]), keyed(1, 0, ["south", "b"])], 2, 3);
    const l = layout(s, opts);
    expect(l.panels.map((p) => p.label)).toEqual(["a", "b", "a", "b"]);
    expect(l.strips.map((t) => t.label)).toEqual(["north", "south", "south"]);
    const north = l.strips[0].rect;
    expect(north.x + north.w).toBe(l.panels[1].rect.x + l.panels[1].rect.w);
    expect(north.y + north.h + 1).toBe(l.panels[0].strip!.y); // over the panels' own strips
    s.grid.strips = "joined";
    expect(layout(s, opts).panels.map((p) => p.label)).toEqual(["north · a", "north · b", "south · a", "south · b"]);
  });
});

describe("a grid's blank cells and panels' own strips", () => {
  // a triangle: (0,0) (0,1) over (1,1), the cell below (0,0) left out (empty="blank")
  const triangle = (): TrellisSpec => spec([panel(0, 0), panel(0, 1), panel(1, 1)], 2, 2, "grid");

  it("draws both axes into a blank cell, the x labels short of the y labels", () => {
    const l = layout(triangle(), opts);
    const [corner, , diagonal] = l.panels;
    expect([corner.showX, diagonal.showY]).toEqual([true, true]);
    expect(diagonal.rect.x).toBe(l.panels[1].rect.x); // no gutter: the labels go in the cell
    expect(crowdedRight(l, corner)).toBe(false);
    expect(labelEnd(l, corner)).toBe(diagonal.yAxis!.x - 4); // "10" over "4": not drawn
    expect(labelEnd(l, diagonal)).toBe(Infinity);
  });

  it("gives each panel a strip of its own naming it, and no others", () => {
    const s = triangle();
    s.grid.strip_label = true;
    s.panels = s.panels.map((p, i) => ({ ...p, keys: ["r", String(i)], strip: `step ${i}` }));
    const l = layout(s, opts);
    expect(l.strips).toEqual([]);
    expect(l.panels.map((b) => b.label)).toEqual(["step 0", "step 1", "step 2"]);
    for (const b of l.panels) expect(b.strip!.y + b.strip!.h + 1).toBe(b.rect.y);
    // the x labels of the panel above the blank cell: short of the strip right of it
    const [corner, , diagonal] = l.panels;
    expect(labelEnd(l, corner)).toBe(diagonal.strip!.x - 4);
    // opened: its own strip's text too
    expect(layout(s, { ...opts, focused: 2 }).panels[0].label).toBe("step 2");
  });

  it("pages a grid with the same blank cells on every page, so turning them moves nothing", () => {
    const s = spec([panel(0, 0), panel(0, 1), panel(1, 1), panel(0, 0), panel(0, 1), panel(1, 1)], 2, 2, "grid");
    s.pages = { rows: 2, cols: 2, stats: [], grid: true, groups: [0, 0, 0, 1, 1, 1], levels: ["a", "b"] };
    const [a, b] = [[0, 1, 2], [3, 4, 5]].map((page) => layout(s, { ...opts, page }));
    expect(b.panels.map((p) => p.index)).toEqual([3, 4, 5]);
    expect(b.panels.map((p) => p.rect)).toEqual(a.panels.map((p) => p.rect));
    expect(labelEnd(b, b.panels[0])).toBe(b.panels[2].yAxis!.x - 4); // the blank cell's axes
  });
});

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

  it("knows where x labels would run into the next panel's", () => {
    // a wrap's bottom row: each x axis next to another; the last panel's has room on its right
    const l = layout(spec([panel(0, 0), panel(0, 1), panel(0, 2)], 1, 3), opts);
    expect(l.panels.map((b) => crowdedRight(l, b))).toEqual([true, true, false]);
    // free y scales: the next panel's y axis between them, so room enough
    const free = layout(spec([panel(0, 0, 0, 0), panel(0, 1, 1, 1)], 1, 2), opts);
    expect(free.panels.map((b) => crowdedRight(free, b))).toEqual([false, false]);
    // over a wrap's empty cells: the axes drawn into them, the last row's alone
    const wrap = layout(spec([panel(0, 0), panel(0, 1), panel(0, 2), panel(1, 0)], 2, 3), opts);
    const drawn = wrap.panels.filter((b) => b.showX);
    expect(drawn.map((b) => b.index)).toEqual([1, 2, 3]);
    expect(drawn.map((b) => crowdedRight(wrap, b))).toEqual([true, false, false]);
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

  it("makes room for the y labels a tall panel draws", () => {
    // 5 ticks over 0-4.2G step by 1G (labels 1.0G); a 300 px panel draws 8, by 0.5G: 500M
    const tall = (s: TrellisSpec) => ({ ...s, panel_height: 300, panels: s.panels.map((q) => ({ ...q, y: [0, 4.2e9] as [number, number] })) });
    const widest = (h: number) => Math.max(...ticks("number", 0, 4.2e9, 0, Math.floor(h / 36)).map((t) => t.label.length * 7));
    const l = layout(tall(spec([panel(0, 0), panel(0, 1)], 1, 2)), opts);
    expect(l.panels[0].rect.h).toBe(300);
    expect(l.yAxisWidth[0]).toBeGreaterThanOrEqual(widest(300) + 4);
    const one = layout(tall(spec([panel(0, 0), panel(0, 1)], 1, 2)), { ...opts, focused: 0, height: 600 });
    expect(one.yAxisWidth[0]).toBeGreaterThanOrEqual(widest(one.panels[0].rect.h) + 4);
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

  it("follows a step line's levels and shows the point each starts at", () => {
    // step="post" through (0, 1), (1, 2), (3, 5): levels, risers and the last point
    const steps = layer("line", [0, 1, 1, 1, 1, 2, 3, 2, 1, 2, 1, 1, 3, 5, 3, 2, 3, 5, 3, 5], KIND_CAPSULE, 1);
    steps.spec.step = "post";
    const scene = { layers: [steps] } as unknown as Scene;
    const level = pick(scene, 0, map, 25, 80, 4)!; // x 2.5 on the level at 2
    expect(level.instance).toBe(1);
    expect(hitPoint(level, map, 25, 80)).toEqual({ x: 1, y: 2, y0: 0 });
    const end = pick(scene, 0, map, 9, 87, 4)!; // by the riser at x 1: the level at 1
    expect(end.instance).toBe(0);
    expect(hitPoint(end, map, 9, 87)).toEqual({ x: 0, y: 1, y0: 0 }); // its point, not its end
    expect(pick(scene, 0, map, 30, 65, 4)).toBeNull(); // half way up the riser at x 3
    const last = pick(scene, 0, map, 30, 50, 4)!;
    expect(hitPoint(last, map, 30, 50)).toEqual({ x: 3, y: 5, y0: 0 });
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

describe("legend entries", () => {
  // points coloured by legend 0: levels 0, 1, 2; a plain line; a layer coloured by legend 1
  const coloured = () => {
    const points = { ...layer("points", [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3], KIND_CAPSULE, 2), codes: new Uint16Array([0, 1, 2]) };
    points.spec = { ...points.spec, color: { legend: 0 } } as MarkLayerSpec;
    const plain = layer("line", [0, 0, 9, 9], KIND_CAPSULE, 1);
    plain.spec = { ...plain.spec, color: { legend: null } } as MarkLayerSpec;
    const other = { ...layer("points", [1, 1, 1, 1], KIND_CAPSULE, 2), codes: new Uint16Array([1]) };
    other.spec = { ...other.spec, color: { legend: 1 } } as MarkLayerSpec;
    return { layers: [points, plain, other] } as unknown as Scene;
  };

  it("select the marks of their colours, and with a range only those in it", () => {
    const s = select(coloured(), { x: null, y: null, legend: { index: 0, levels: [1, 2] } });
    expect([...s.masks[0]!]).toEqual([0, 1, 1]);
    expect([...s.masks[1]!]).toEqual([0]); // no colour column: faded
    expect([...s.masks[2]!]).toEqual([0]); // another legend's colours: faded
    const both = select(coloured(), { x: [2.5, 9], y: null, legend: { index: 0, levels: [1, 2] } });
    expect([...both.masks[0]!]).toEqual([0, 0, 1]);
  });

  it("toggle: a click picks one (again: none), Shift adds and takes away", () => {
    expect(toggleLegend(null, 0, 2, false)).toEqual({ index: 0, levels: [2] });
    expect(toggleLegend({ index: 0, levels: [2] }, 0, 2, false)).toBeNull();
    expect(toggleLegend({ index: 0, levels: [2] }, 0, 1, true)).toEqual({ index: 0, levels: [1, 2] });
    expect(toggleLegend({ index: 0, levels: [1, 2] }, 0, 1, true)).toEqual({ index: 0, levels: [2] });
    expect(toggleLegend({ index: 0, levels: [1, 2] }, 1, 0, true)).toEqual({ index: 1, levels: [0] }); // another legend
    expect(selects({ x: null, y: null, legend: { index: 0, levels: [] } })).toBe(false);
    expect(selects({ x: null, y: null, legend: { index: 0, levels: [0] } })).toBe(true);
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

  it("leaves a layer in detail alone when the mask is for other data", () => {
    const points = layer("points", [1, 1, 1, 1], KIND_CAPSULE, 2);
    points.spec = { ...points.spec, coords: { id: "detail" } } as MarkLayerSpec;
    const scene = { layers: [points] } as unknown as Scene;
    expect(highlighted(scene, { layers: [{ mask: new Uint8Array([1]), of: "start" }] })).toBeNull();
    expect(highlighted(scene, { layers: [{ mask: new Uint8Array([1]), of: "detail" }] })!.selection.selected).toBe(1);
  });
});

describe("layers in detail", () => {
  const ref = (id: string, dtype: "float64" | "uint32", count: number, components = 1) => ({ id, dtype, count, components, byteLength: 0 });
  const line = (id: string, n: number): MarkLayerSpec =>
    ({
      type: "line",
      name: "line",
      count: n,
      coords: ref(id, "float64", n, 4),
      starts: ref(`${id}-starts`, "uint32", 2),
      color: { rgba: null, solid: [0, 0, 0, 255], codes: null, legend: null },
      width: 1,
      size: 1,
      opacity: 1,
      tooltip: false,
      context: false,
    }) as MarkLayerSpec;
  const source = (layers: MarkLayerSpec[]) => {
    const data = new Map<string, ArrayBuffer>();
    for (const l of layers) {
      data.set(l.coords.id, new Float64Array(l.count * 4).fill(1).buffer);
      data.set(l.starts.id, new Uint32Array([0, l.count]).buffer);
    }
    return { has: (id: string) => data.has(id), get: (id: string) => data.get(id)!, ensure: async () => {} };
  };
  const spec = (layers: MarkLayerSpec[]) => ({ panels: [{ ...panel(0, 0), x: [0, 1], y: [0, 1] }], layers }) as unknown as TrellisSpec;

  it("rebuilds only the layers that changed", () => {
    const a = line("a", 3);
    const b = line("b", 5);
    const first = buildScene(spec([a, b]), source([a, b]));
    const b2 = line("b2", 2);
    const next = buildScene(spec([a, b2]), source([a, b, b2]), first);
    expect(next.layers[0]).toBe(first.layers[0]);
    expect(next.layers[1]).not.toBe(first.layers[1]);
    expect(next.layers[1].set.count).toBe(2);
  });

  it("forgets the buffers drawn no more, not those on their way", () => {
    const store = new BufferStore(() => {});
    const put = (id: string) => store.receive({ type: "put", id, chunk: 0, chunks: 1, offset: 0, byteLength: 4 }, new Uint8Array(4));
    put("old");
    put("kept");
    void store.ensure(["coming"]);
    store.prune(new Set(["kept"]));
    expect([store.has("old"), store.has("kept")]).toEqual([false, true]);
    put("coming");
    expect(store.has("coming")).toBe(true);
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

describe("panels with a shape (aspect)", () => {
  const shaped = (aspect: number) => ({ ...spec([panel(0, 0), panel(0, 1), panel(1, 0), panel(1, 1)], 2, 2), panel_height: null, aspect });
  const ratio = (r: { w: number; h: number }) => r.h / r.w;

  it("keep it in full screen, narrowed and centred when the screen is too low", () => {
    const low = layout(shaped(1), { ...opts, height: 300 });
    const [a, b] = low.panels;
    expect(ratio(a.rect)).toBeCloseTo(1, 1);
    expect(low.height).toBeLessThanOrEqual(302);
    const left = a.rect.x - low.yAxisWidth[0];
    const right = 600 - (b.rect.x + b.rect.w);
    expect(Math.abs(left - right)).toBeLessThan(16); // centred
    expect(right).toBeGreaterThan(100);
  });

  it("keep it in full screen at the whole width when the screen is high enough", () => {
    const wide = layout(shaped(0.25), { ...opts, height: 900 });
    expect(wide.panels[0].rect).toEqual(layout(shaped(0.25), opts).panels[0].rect);
    expect(wide.height).toBeLessThan(400); // shorter than the screen, not stretched
  });

  it("keep it in an opened panel, within the height given", () => {
    const flat = layout(shaped(0.2), { ...opts, focused: 0, height: 600 });
    expect(flat.panels[0].rect.w).toBeGreaterThan(500);
    expect(ratio(flat.panels[0].rect)).toBeCloseTo(0.2, 2);
    const tall = layout(shaped(2), { ...opts, focused: 0, height: 400 });
    const box = tall.panels[0];
    expect(ratio(box.rect)).toBeCloseTo(2, 1);
    expect(tall.height).toBeLessThanOrEqual(402);
    expect(box.yAxis!.x + box.yAxis!.w).toBe(box.rect.x);
    expect(box.rect.x).toBeGreaterThan(150); // centred
  });

  it("are not kept when a height sets the panels' height", () => {
    const s = { ...shaped(1), panel_height: 100 };
    const full = layout(s, { ...opts, height: 900 });
    expect(full.panels[0].rect.h).toBeGreaterThan(300);
  });
});

describe("exported images", () => {
  const measure = (text: string): number => text.length * 6;
  const svg = (draw: (ctx: CanvasRenderingContext2D) => void): string => {
    const rec = new SvgContext(200, 100, measure);
    draw(rec.context);
    return rec.toString("#ffffff");
  };

  it("takes colours apart into a paint and an opacity, as SVG readers want", () => {
    expect(paint("rgba(31,119,180,0.5)")).toEqual(["rgb(31,119,180)", 0.5]);
    expect(paint("rgb(1, 2, 3)")).toEqual(["rgb(1,2,3)", 1]);
    expect(paint("#1f77b480")).toEqual(["#1f77b4", 128 / 255]);
    expect(paint("#123")).toEqual(["#123", 1]);
    expect(paint("transparent")[1]).toBe(0);
  });

  it("reads a canvas font into SVG font attributes", () => {
    expect(fontAttributes("12px system-ui, sans-serif")).toBe('font-size="12" font-family="system-ui, sans-serif"');
    expect(fontAttributes('600 14.4px "Segoe UI", Roboto')).toBe('font-size="14.4" font-family="&quot;Segoe UI&quot;, Roboto" font-weight="600"');
    expect(fontAttributes("normal 400 12px serif")).toBe('font-size="12" font-family="serif"');
  });

  it("records fills, strokes and text as SVG elements", () => {
    const out = svg((ctx) => {
      ctx.fillStyle = "rgba(255,0,0,0.5)";
      ctx.fillRect(10, 10, 20, 5);
      ctx.strokeStyle = "#0000ff";
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(50, 50);
      ctx.stroke();
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#111111";
      ctx.fillText("a < b & c", 100, 50);
    });
    expect(out).toMatch(/^<svg xmlns="http:\/\/www.w3.org\/2000\/svg" width="200" height="100" viewBox="0 0 200 100">/);
    expect(out).toContain('<rect width="100%" height="100%" fill="#ffffff"/>');
    expect(out).toContain('<path d="M10 10L30 10L30 15L10 15Z" fill="rgb(255,0,0)" fill-opacity="0.5"/>');
    expect(out).toContain('<path d="M0 0L50 50" fill="none" stroke="#0000ff" stroke-width="2" stroke-dasharray="3 3"/>');
    // middle baseline: about 0.35 em down from the alphabetic one
    expect(out).toContain('<text x="100" y="54.2" font-size="12" font-family="sans-serif" text-anchor="middle" fill="#111111">a &lt; b &amp; c</text>');
  });

  it("applies translations and rotations, and globalAlpha", () => {
    const out = svg((ctx) => {
      ctx.save();
      ctx.translate(20, 30);
      ctx.globalAlpha = 0.5;
      ctx.fillStyle = "#000000";
      ctx.fillRect(0, 0, 1, 1);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText("y", 0, 0);
      ctx.restore();
      ctx.fillRect(0, 0, 1, 1);
    });
    expect(out).toContain('<path d="M20 30L21 30L21 31L20 31Z" fill="#000000" fill-opacity="0.5"/>');
    expect(out).toContain('<text transform="matrix(0 -1 1 0 20 30)" x="0" y="0"');
    expect(out).toContain('<path d="M0 0L1 0L1 1L0 1Z" fill="#000"/>'); // restored
  });

  it("opens a clip only around what is drawn in it, and shares its path", () => {
    const out = svg((ctx) => {
      for (let i = 0; i < 2; i++) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, 50, 50);
        ctx.clip();
        if (i === 1) ctx.fillRect(5, 5, 10, 10);
        ctx.restore();
      }
      ctx.fillRect(60, 60, 1, 1);
    });
    expect(out.match(/<clipPath/g)?.length).toBe(1);
    expect(out.match(/<g clip-path/g)?.length).toBe(1);
    expect(out).toMatch(/<g clip-path="url\(#c0\)"><path d="M5 5L15 5L15 15L5 15Z" fill="#000"\/><\/g><path d="M60 60/);
  });

  it("draws the marks of a renderer's draws: a run of one colour is one path", () => {
    const set = {
      key: "k",
      version: 1,
      count: 3,
      // two points of one colour, a third of another (zero-length capsules)
      coords: new Float32Array([1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]),
      colors: new Uint8Array([255, 0, 0, 255, 255, 0, 0, 255, 0, 0, 255, 128]),
    };
    const out = svg((ctx) =>
      drawMarks(ctx, [{ set, start: 0, count: 3, clip: { x: 0, y: 0, w: 200, h: 100 }, sx: 10, ox: 0, sy: -10, oy: 100, kind: KIND_CAPSULE, halfWidth: 3, opacity: 0.85 }]),
    );
    const paths = out.match(/<path d="M[^"]*" fill="none"[^>]*>/g) ?? [];
    expect(paths.length).toBe(2);
    expect(paths[0]).toContain('d="M10 90L10.01 90M20 80L20.01 80"');
    expect(paths[0]).toContain('stroke="rgb(255,0,0)" stroke-width="6" stroke-opacity="0.85" stroke-linecap="round"');
    expect(paths[1]).toContain(`stroke-opacity="${Math.round((128 / 255) * 0.85 * 100) / 100}"`);
  });

  it("names files after the title and the opened panel", () => {
    expect(fileName("Fuel use, by origin", null, "png")).toBe("Fuel-use-by-origin.png");
    expect(fileName("Sales", "Oslo · tea", "svg")).toBe("Sales-Oslo-tea.svg");
    expect(fileName("", null, "png")).toBe("anytrellis.png");
    expect(svgMessage("Copied", 2_500_000)).toContain("large");
    expect(svgMessage("Copied", 40_000)).toBe("Copied as SVG (40 kB)");
  });
});

describe("pages", () => {
  // the same cases as tests/test_pages.py's test_order_filters_then_sorts (Python's order)
  const names = ["north a", "north b", "south a", "south b", "east"];
  const stats: PanelStat[] = [
    { name: "v", kind: "number", values: [3, 1, null, 1, 2], text: [] },
    { name: "zone", kind: "text", values: ["cold", "cold", "warm", "", "warm"], text: [] },
  ];
  const cases: [Paging, number[]][] = [
    [{}, [0, 1, 2, 3, 4]],
    [{ name: "North" }, [0, 1]],
    [{ name: "a north" }, [0]],
    [{ sort: "v" }, [1, 3, 4, 0, 2]],
    [{ sort: "v", descending: true }, [0, 4, 1, 3, 2]],
    [{ sort: "zone" }, [0, 1, 2, 4, 3]],
    [{ sort: "zone", descending: true }, [2, 4, 0, 1, 3]],
    [{ where: { v: [1.5, null] } }, [0, 4]],
    [{ where: { v: [null, 2] } }, [1, 3, 4]],
    [{ where: { zone: "WAR" } }, [2, 4]],
    [{ where: { zone: "", v: [null, null] } }, [0, 1, 2, 3, 4]],
    [{ where: { nothing: [1, 2] } }, [0, 1, 2, 3, 4]],
    [{ name: "south", sort: "v", descending: true }, [3, 2]],
  ];
  it.each(cases)("orders %j as Python does", (paging, expected) => {
    expect(panelOrder(stats, names, paging)).toEqual(expected);
  });

  it("counts pages, at least one", () => {
    const page = { rows: 4, cols: 6, stats: [] };
    const n = (count: number): number[] => Array.from({ length: count }, (_, i) => i);
    expect([pageList(n(0), page).length, pageList(n(24), page).length, pageList(n(25), page).length]).toEqual([1, 1, 2]);
  });

  it("pages page columns' levels apart, as Python does", () => {
    // panels 0-2 of level 0, 3-7 of level 1, 8 of level 2; three a page
    const page = { rows: 1, cols: 3, stats: [], groups: [0, 0, 0, 1, 1, 1, 1, 1, 2], levels: ["a", "b", "c"] };
    const all = [0, 1, 2, 3, 4, 5, 6, 7, 8];
    expect(pageList(all, page)).toEqual([[0, 1, 2], [3, 4, 5], [6, 7], [8]]);
    expect(pageLabels(pageList(all, page), page)).toEqual(["a", "b (1 of 2)", "b (2 of 2)", "c"]);
    // sorted and filtered: each level's panels in the order shown; a level left empty, no page
    expect(pageList([7, 1, 0, 5], page)).toEqual([[1, 0], [7, 5]]);
    expect(pageList([], page)).toEqual([[]]);
    expect(pageLabels([[]], page)).toEqual([""]);
  });

  it("lays out a page's panels in turn, on a page of the same size every time", () => {
    const many = Array.from({ length: 10 }, (_, i) => panel(Math.floor((i % 6) / 3), i % 3));
    const paged = { ...spec(many, 2, 3), pages: { rows: 2, cols: 3, stats: [] } };
    const first = layout(paged, opts);
    expect(first.panels.map((b) => b.index)).toEqual([0, 1, 2, 3, 4, 5]);
    const last = layout(paged, { ...opts, page: [9, 6] });
    expect(last.panels.map((b) => b.index)).toEqual([9, 6]);
    expect(last.panels[0].rect).toEqual(first.panels[0].rect);
    expect(last.panels[1].rect).toEqual(first.panels[1].rect);
    expect(last.height).toBe(first.height); // the page does not shrink
    expect(last.panels.map((b) => b.showX)).toEqual([true, true]); // nothing under them
    expect(last.spare).toBeNull(); // the legend goes under every page alike
    const none = layout(paged, { ...opts, page: [] });
    expect(none.panels).toEqual([]);
    expect(none.height).toBe(first.height);
  });
});
