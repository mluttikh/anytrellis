// The 2D canvases around the GPU marks: behind them, panel backgrounds and gridlines; in
// front, axes, strips, titles, rules, the crosshair and the hovered mark.
//
// What is drawn and how follows the look (look.ts): panel fill or a frame, which way the grid
// runs (the text colour at low opacity: Bartram & Stone), which axes draw a line, strips
// filled or as titles, and where the axis titles sit.

import { ANGLE_MAX, type Layout, type PanelBox, type Rect, STRIP_PAD, type Strip, type XLabels, wrapLabel } from "./layout";
import { type Look, lookOf } from "./look";
import { type EndLabel, repel } from "./labels";
import type { PanelMap, TextData } from "./scene";
import { type Tick, formatValue, minorTicks, ticks, yTickCount } from "./ticks";
import type { NoteSpec, RuleLayerSpec, TrellisSpec } from "./types";

export interface Theme {
  bg: string;
  text: string;
  muted: string;
  grid: string;
  panel: string;
  strip: string;
  stripText: string;
  axis: string;
  accent: string;
  font: string;
  fontSize: number;
}

export interface PanelView {
  /** The panel's index in spec.panels. */
  panel: number;
  rect: Rect;
  map: PanelMap;
  x: [number, number];
  y: [number, number];
}

export function readTheme(el: HTMLElement): Theme {
  const css = getComputedStyle(el);
  const v = (name: string, fallback: string): string => css.getPropertyValue(name).trim() || fallback;
  const fontSize = parseFloat(css.fontSize) || 12;
  return {
    bg: v("--atr-bg", "#ffffff"),
    text: v("--atr-text", "#1b2430"),
    muted: v("--atr-muted", "#5e6875"),
    grid: v("--atr-grid", "#e3e7ec"),
    panel: v("--atr-panel", "#f6f7f9"),
    strip: v("--atr-strip", "#e9ecf0"),
    stripText: v("--atr-strip-text", "#2b3440"),
    axis: v("--atr-axis", "#a3abb5"),
    accent: v("--atr-accent", "#1f77b4"),
    font: css.fontFamily || "system-ui, sans-serif",
    fontSize,
  };
}

/** A view's x ticks. Categories: as many as their labels fit side by side (estimated: ~0.6
 * em per character), every one on two lines, or at 45 degrees as many as are a line apart. */
export function xTicks(spec: TrellisSpec, v: PanelView, mode: XLabels = "flat", fs = 12): Tick[] {
  let count = Math.max(3, Math.floor(v.rect.w / 80));
  if (spec.x.kind === "band" && spec.x.levels?.length) {
    const longest = Math.max(...spec.x.levels.map((l) => l.length));
    const shown = Math.max(1, v.x[1] - v.x[0]);
    const per = v.rect.w / shown;
    const room = mode === "wrap" ? 0 : mode === "angle" ? fs * 1.5 : longest * 0.6 * fs + 10;
    count = Math.floor(shown / Math.max(1, Math.ceil(room / per)));
  }
  return ticks(spec.x.kind, v.x[0], v.x[1], spec.x.origin, Math.max(2, count), spec.x.levels, spec.x.format);
}

export function yTicks(spec: TrellisSpec, v: PanelView): Tick[] {
  const count = yTickCount(spec.y.kind, v.y[0], v.y[1], v.rect.h);
  return ticks(spec.y.kind, v.y[0], v.y[1], spec.y.origin, count, spec.y.levels, spec.y.format);
}

/** Which axes draw grid lines (never a band's): as the look says; `auto`, y, and x too for
 * points (a scatter reads off both) or when y is a band (bars along x). */
export function gridAxes(spec: TrellisSpec): { x: boolean; y: boolean } {
  const x = spec.x.kind !== "band";
  const y = spec.y.kind !== "band";
  const grid = lookOf(spec).grid;
  if (grid === "auto") return { x: x && (!y || spec.layers.some((l) => l.type === "points")), y };
  return { x: x && (grid === "x" || grid === "both"), y: y && (grid === "y" || grid === "both") };
}

export function drawBack(ctx: CanvasRenderingContext2D, spec: TrellisSpec, views: PanelView[], theme: Theme): void {
  const look = lookOf(spec);
  const grid = gridAxes(spec);
  const alpha = look.grid_opacity;
  for (const v of views) {
    const r = v.rect;
    if (look.panel_fill) {
      ctx.fillStyle = theme.panel;
      ctx.fillRect(r.x, r.y, r.w, r.h);
    }
    ctx.save();
    ctx.beginPath();
    ctx.rect(r.x, r.y, r.w, r.h);
    ctx.clip();
    ctx.strokeStyle = theme.text;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (grid.x) {
      for (const t of xTicks(spec, v, "flat", theme.fontSize)) {
        const x = Math.round(v.map.ox + t.value * v.map.sx) + 0.5;
        ctx.moveTo(x, r.y);
        ctx.lineTo(x, r.y + r.h);
      }
    }
    if (grid.y) {
      for (const t of yTicks(spec, v)) {
        const y = Math.round(v.map.oy + t.value * v.map.sy) + 0.5;
        ctx.moveTo(r.x, y);
        ctx.lineTo(r.x + r.w, y);
      }
    }
    ctx.stroke();
    // a log axis: fainter lines between its ticks
    const minorX = grid.x ? minorTicks(spec.x.kind, v.x[0], v.x[1], spec.x.origin, spec.x.kind === "log" ? xTicks(spec, v) : [], r.w) : [];
    const minorY = grid.y ? minorTicks(spec.y.kind, v.y[0], v.y[1], spec.y.origin, spec.y.kind === "log" ? yTicks(spec, v) : [], r.h) : [];
    if (minorX.length || minorY.length) {
      ctx.globalAlpha = 0.45 * alpha;
      ctx.beginPath();
      for (const value of minorX) {
        const x = Math.round(v.map.ox + value * v.map.sx) + 0.5;
        ctx.moveTo(x, r.y);
        ctx.lineTo(x, r.y + r.h);
      }
      for (const value of minorY) {
        const y = Math.round(v.map.oy + value * v.map.sy) + 0.5;
        ctx.moveTo(r.x, y);
        ctx.lineTo(r.x + r.w, y);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    ctx.restore();
  }
}

export interface FrontState {
  /** Data x (axis units) of the pointer, drawn in the panels of `crossGroup`. */
  crossX: number | null;
  crossGroup: number | null;
  /** The hovered marks (one, or each series' at the hovered x), in panel `hoverPanel`. */
  hovers: Ring[];
  hoverPanel: number | null;
  /** The marks of a pinned tooltip, in panel `pinPanel`. */
  pins: Ring[];
  pinPanel: number | null;
  /** The pointer's x and y (axis units) in panel `panel`, written on the axes in its column
   * and its row; null: not on that axis (a band, or off the panels). */
  readout: { panel: number; x: number | null; y: number | null } | null;
  /** A zoom box being dragged (px), and where it will zoom the panels linked to it. */
  box: Rect | null;
  ghosts: Rect[];
  /** The selection's brush, where it shows in each panel (px). */
  brushes: Rect[];
  /** The selection's lasso, where it shows in each panel: its corners (px), clipped to the
   * panel. */
  lassos: { clip: Rect; points: [number, number][] }[];
  /** Text layers, drawn over the marks. */
  texts: TextData[];
  /** Labels at the ends of lines (labels.ts: endLabels). */
  ends: EndLabel[];
  /** The panel the arrow keys have reached: a ring round it. */
  ring: Rect | null;
}

/** A ring around a hovered mark: its centre (px), its radius, in its colour. */
export interface Ring {
  x: number;
  y: number;
  r: number;
  color: string;
}

function drawRing(ctx: CanvasRenderingContext2D, ring: Ring, theme: Theme): void {
  ctx.lineWidth = 2;
  ctx.strokeStyle = theme.bg;
  ctx.beginPath();
  ctx.arc(ring.x, ring.y, ring.r + 2, 0, Math.PI * 2);
  ctx.stroke();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = ring.color;
  ctx.beginPath();
  ctx.arc(ring.x, ring.y, ring.r + 3.5, 0, Math.PI * 2);
  ctx.stroke();
  ctx.lineWidth = 1;
}

/** The pointer's x and y written on the axes (as Observable Plot's crosshair does): x on
 * the x axis of the panels in the hovered panel's column, y on the y axis of those in its
 * row, over the tick labels. */
function drawReadout(ctx: CanvasRenderingContext2D, spec: TrellisSpec, layout: Layout, views: PanelView[], theme: Theme, readout: NonNullable<FrontState["readout"]>): void {
  const at = views.findIndex((v) => v.panel === readout.panel);
  if (at < 0) return;
  const here = views[at];
  const fs = theme.fontSize;
  const h = Math.round(fs + 6);
  const label = (text: string, x: number, y: number, align: "center" | "right"): void => {
    const w = Math.ceil(ctx.measureText(text).width) + 8;
    const left = Math.max(1, align === "center" ? x - w / 2 : x - w); // inside the plot
    ctx.fillStyle = theme.text;
    ctx.beginPath();
    ctx.roundRect?.(left, y - h / 2, w, h, 3);
    if (!ctx.roundRect) ctx.rect(left, y - h / 2, w, h);
    ctx.fill();
    ctx.fillStyle = theme.bg;
    ctx.textAlign = "center";
    ctx.fillText(text, left + w / 2, y + 0.5);
  };
  ctx.save();
  views.forEach((v, i) => {
    const box = layout.panels[i];
    const r = v.rect;
    const p = spec.panels[v.panel];
    const hp = spec.panels[here.panel];
    if (readout.x !== null && box.showX && Math.abs(r.x - here.rect.x) < 1 && p.xg === hp.xg) {
      const px = v.map.ox + readout.x * v.map.sx;
      if (px >= r.x - 0.5 && px <= r.x + r.w + 0.5) {
        const text = formatValue(spec.x.kind, readout.x, spec.x.origin, v.x[1] - v.x[0], spec.x.levels, spec.x.format);
        label(text, px, r.y + r.h + 4 + h / 2, "center");
      }
    }
    if (readout.y !== null && box.showY && Math.abs(r.y - here.rect.y) < 1 && p.yg === hp.yg) {
      const py = v.map.oy + readout.y * v.map.sy;
      if (py >= r.y - 0.5 && py <= r.y + r.h + 0.5) {
        const text = formatValue(spec.y.kind, readout.y, spec.y.origin, v.y[1] - v.y[0], spec.y.levels, spec.y.format);
        label(text, r.x - 2, py, "right");
      }
    }
  });
  ctx.restore();
}

export function drawFront(ctx: CanvasRenderingContext2D, spec: TrellisSpec, layout: Layout, views: PanelView[], theme: Theme, state: FrontState): void {
  const fs = theme.fontSize;
  const look = lookOf(spec);
  ctx.font = `${fs}px ${theme.font}`;
  ctx.textBaseline = "middle";

  // rules, crosshair, hover: clipped to their panels
  views.forEach((v) => {
    const r = v.rect;
    ctx.save();
    ctx.beginPath();
    ctx.rect(r.x, r.y, r.w, r.h);
    ctx.clip();
    for (const l of spec.layers) if (l.type === "rule") drawRule(ctx, l, v);
    for (const t of state.texts) drawText(ctx, t, v, theme);
    const halo = look.panel_fill ? theme.panel : theme.bg;
    for (const e of state.ends) if (e.panel === v.panel) drawEndLabel(ctx, e, halo);
    for (const n of spec.notes ?? []) if (!n.panels || n.panels.includes(v.panel)) drawNote(ctx, n, v, theme, halo);
    if (state.crossX !== null && spec.panels[v.panel].xg === state.crossGroup) {
      const x = Math.round(v.map.ox + state.crossX * v.map.sx) + 0.5;
      ctx.strokeStyle = theme.axis;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, r.y);
      ctx.lineTo(x, r.y + r.h);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    if (state.pinPanel === v.panel) for (const ring of state.pins) drawRing(ctx, ring, theme);
    if (state.hoverPanel === v.panel) for (const ring of state.hovers) drawRing(ctx, ring, theme);
    ctx.restore();
  });

  // frames, just outside the panels (where axis lines go)
  if (look.frame) {
    ctx.strokeStyle = theme.axis;
    for (const v of views) ctx.strokeRect(v.rect.x - 0.5, v.rect.y - 0.5, v.rect.w + 1, v.rect.h + 1);
  }
  // the panel the arrow keys have reached
  if (state.ring) {
    const r = state.ring;
    ctx.save();
    ctx.strokeStyle = theme.accent;
    ctx.lineWidth = 2;
    ctx.strokeRect(r.x - 2, r.y - 2, r.w + 4, r.h + 4);
    ctx.restore();
  }

  // axes
  const lineX = look.axis_lines === "x" || look.axis_lines === "both";
  const lineY = look.axis_lines === "y" || look.axis_lines === "both";
  ctx.fillStyle = theme.muted;
  ctx.strokeStyle = theme.axis;
  layout.panels.forEach((box, i) => {
    const v = views[i];
    const r = v.rect;
    if (box.showX) {
      const end = labelEnd(layout, box);
      ctx.textAlign = "center";
      ctx.beginPath();
      if (lineX) {
        ctx.moveTo(r.x, r.y + r.h + 0.5);
        ctx.lineTo(r.x + r.w, r.y + r.h + 0.5);
      }
      let lastRight = -Infinity;
      const per = v.rect.w / Math.max(1, v.x[1] - v.x[0]); // a band's width
      // left to right (a reversed x: its ticks from high to low), each label after the last
      const xs = xTicks(spec, v, layout.xLabels, fs);
      if (v.map.sx < 0) xs.reverse();
      for (const t of xs) {
        const x = v.map.ox + t.value * v.map.sx;
        if (x < r.x - 0.5 || x > r.x + r.w + 0.5) continue;
        ctx.moveTo(Math.round(x) + 0.5, r.y + r.h);
        ctx.lineTo(Math.round(x) + 0.5, r.y + r.h + 4);
        if (layout.xLabels === "wrap") {
          // centred in its band, on a second line when it needs one
          const one = ctx.measureText(t.label).width + 4 <= per;
          (one ? [t.label] : wrapLabel(t.label)).forEach((line, k) => {
            ctx.fillText(fit(ctx, line, per - 4), x, r.y + r.h + 4 + fs * (0.75 + 1.2 * k));
          });
          continue;
        }
        if (layout.xLabels === "angle") {
          // ending at its tick, running down to the left; cut not to leave the plot
          ctx.save();
          ctx.translate(x, r.y + r.h + 4 + fs * 0.5);
          ctx.rotate(-Math.PI / 4);
          ctx.textAlign = "right";
          ctx.fillText(fit(ctx, t.label, Math.min(ANGLE_MAX, (x - 2) / Math.SQRT1_2)), 0, 0);
          ctx.restore();
          continue;
        }
        const w = ctx.measureText(t.label).width;
        // next to a panel's axis: not up to its first label ("AprMar")
        if (x + w / 2 > end) continue;
        const lx = Math.min(Math.max(x, r.x + w / 2), r.x + r.w - w / 2 + 6);
        if (lx - w / 2 < lastRight + 6) continue;
        ctx.fillText(t.label, lx, r.y + r.h + 4 + fs * 0.75);
        lastRight = lx + w / 2;
      }
      ctx.stroke();
    }
    if (box.showY) {
      ctx.textAlign = "right";
      ctx.beginPath();
      if (lineY) {
        ctx.moveTo(r.x - 0.5, r.y);
        ctx.lineTo(r.x - 0.5, r.y + r.h);
      }
      let lastTop = Infinity;
      // bottom to top (a reversed y: its ticks from high to low)
      const ys = yTicks(spec, v);
      if (v.map.sy > 0) ys.reverse();
      for (const t of ys) {
        const y = v.map.oy + t.value * v.map.sy;
        if (y < r.y - 0.5 || y > r.y + r.h + 0.5) continue;
        ctx.moveTo(r.x - 4, Math.round(y) + 0.5);
        ctx.lineTo(r.x, Math.round(y) + 0.5);
        const ly = Math.min(Math.max(y, r.y + fs / 2), r.y + r.h - fs / 2);
        if (ly + fs / 2 > lastTop - 2) continue;
        ctx.fillText(t.label, r.x - 6, ly);
        lastTop = ly - fs / 2;
      }
      ctx.stroke();
    }
  });

  // strips
  const strip = look.strip_fill ? filledStrip : flatStrip;
  for (const box of layout.panels) if (box.strip) strip(ctx, theme, look, { rect: box.strip, label: box.label, vertical: false, side: "top", span: false, pin: box.pinned }, box.note);
  for (const s of layout.strips) strip(ctx, theme, look, s);
  ctx.font = `${fs}px ${theme.font}`;

  // titles
  ctx.fillStyle = theme.text;
  if (layout.title) {
    ctx.font = `600 ${Math.round(fs * 1.2)}px ${theme.font}`;
    ctx.textAlign = "left";
    ctx.fillText(spec.title, layout.title.x, layout.title.y);
  }
  ctx.font = `${fs}px ${theme.font}`;
  ctx.fillStyle = theme.muted;
  if (layout.xTitle && look.x_title === "end") {
    ctx.textAlign = "right";
    ctx.fillText(`${spec.x.title} →`, layout.xTitle.x, layout.xTitle.y);
  } else if (layout.xTitle) {
    ctx.textAlign = "center";
    ctx.fillText(spec.x.title, layout.xTitle.x, layout.xTitle.y);
  }
  if (layout.yTitle && look.y_title === "side") {
    ctx.save();
    ctx.translate(layout.yTitle.x, layout.yTitle.y);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(spec.y.title, 0, 0);
    ctx.restore();
  } else if (layout.yTitle) {
    ctx.textAlign = "left";
    ctx.fillText(`↑ ${spec.y.title}`, layout.yTitle.x, layout.yTitle.y);
  }

  for (const l of state.lassos) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(l.clip.x, l.clip.y, l.clip.w, l.clip.h);
    ctx.clip();
    ctx.beginPath();
    l.points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.fillStyle = theme.accent;
    ctx.globalAlpha = 0.07;
    ctx.fill();
    ctx.globalAlpha = 0.8;
    ctx.strokeStyle = theme.accent;
    ctx.stroke();
    ctx.restore();
  }
  for (const b of state.brushes) {
    ctx.fillStyle = theme.accent;
    ctx.globalAlpha = 0.07;
    ctx.fillRect(b.x, b.y, b.w, b.h);
    ctx.globalAlpha = 0.8;
    ctx.strokeStyle = theme.accent;
    ctx.strokeRect(Math.round(b.x) + 0.5, Math.round(b.y) + 0.5, Math.round(b.w) - 1, Math.round(b.h) - 1);
    ctx.globalAlpha = 1;
  }
  for (const g of state.ghosts) {
    ctx.fillStyle = theme.accent;
    ctx.globalAlpha = 0.06;
    ctx.fillRect(g.x, g.y, g.w, g.h);
    ctx.globalAlpha = 0.5;
    ctx.strokeStyle = theme.accent;
    ctx.setLineDash([3, 3]);
    ctx.strokeRect(g.x + 0.5, g.y + 0.5, g.w, g.h);
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
  }
  if (state.box) {
    const b = state.box;
    ctx.fillStyle = theme.accent;
    ctx.globalAlpha = 0.12;
    ctx.fillRect(b.x, b.y, b.w, b.h);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = theme.accent;
    ctx.strokeRect(b.x + 0.5, b.y + 0.5, b.w, b.h);
  }
  if (state.readout) {
    ctx.font = `${fs}px ${theme.font}`;
    ctx.textBaseline = "middle";
    drawReadout(ctx, spec, layout, views, theme, state.readout);
  }
}

/** Room (px) an x label leaves at its panel's right edge when another panel's x axis follows
 * there: with the gap between them, labels of neighbours stay well apart. */
const LABEL_ROOM = 4;

/** How far right `box`'s x labels may reach: not up to the first label of an x axis right of
 * it ("AprMar"), nor into the y labels or the strip of the panel below and right of it (a
 * grid's empty cell below `box`, drawn into from both sides: "10" over "4"). */
export function labelEnd(layout: Layout, box: PanelBox): number {
  const r = box.rect;
  let end = crowdedRight(layout, box) ? r.x + r.w - LABEL_ROOM : Infinity;
  for (const b of layout.panels) {
    if (b.rect.x <= r.x + r.w) continue;
    const near = (y: number): boolean => y >= r.y + r.h && y < r.y + r.h + layout.xAxisHeight;
    if (b.yAxis && b.yAxis.x < r.x + r.w + 8 && near(b.rect.y)) end = Math.min(end, b.yAxis.x - LABEL_ROOM);
    // its strip (strip_label: a grid's panels have strips of their own)
    const s = b.strip;
    if (s && s.x < r.x + r.w + 8 && near(s.y)) end = Math.min(end, s.x - LABEL_ROOM);
  }
  return end;
}

/** Whether the panel right of `box` (across the gap between panels) draws an x axis too, at
 * the same height: its first label starts where `box`'s last would end. */
export function crowdedRight(layout: Layout, box: PanelBox): boolean {
  const r = box.rect;
  return layout.panels.some((b) => b !== box && b.showX && Math.abs(b.rect.y + b.rect.h - (r.y + r.h)) < 1 && b.rect.x > r.x && b.rect.x - (r.x + r.w) <= 8);
}

/** Text with a halo of the panel's colour round it, so it reads over the marks. */
function haloText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, halo: string): void {
  ctx.save();
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  ctx.strokeStyle = halo;
  ctx.strokeText(text, x, y);
  ctx.restore();
  ctx.fillText(text, x, y);
}

function drawEndLabel(ctx: CanvasRenderingContext2D, e: EndLabel, halo: string): void {
  ctx.save();
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillStyle = e.color;
  haloText(ctx, e.text, e.x, e.y, halo);
  ctx.restore();
}

/** A note (`annotate()`): its text at a data position (x alone: at the panel's top; y
 * alone: at its left), moved by dx, dy, with a line back to the position when moved. */
function drawNote(ctx: CanvasRenderingContext2D, n: NoteSpec, v: PanelView, theme: Theme, halo: string): void {
  const r = v.rect;
  const size = n.size ?? theme.fontSize;
  const lines = n.text.split("\n");
  const lh = size * 1.2;
  const px = n.x !== null ? v.map.ox + n.x * v.map.sx : r.x + 4;
  const py = n.y !== null ? v.map.oy + n.y * v.map.sy : r.y + 4 + (lh * lines.length) / 2;
  if (!Number.isFinite(px) || !Number.isFinite(py)) return;
  const tx = px + n.dx;
  const ty = py + n.dy;
  ctx.save();
  if (n.x !== null && n.y !== null && (n.dx || n.dy)) {
    ctx.strokeStyle = theme.muted;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.lineTo(tx, ty);
    ctx.stroke();
    ctx.fillStyle = theme.muted;
    ctx.beginPath();
    ctx.arc(px, py, 2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.font = `${size}px ${theme.font}`;
  ctx.textAlign = n.align;
  ctx.textBaseline = "middle";
  ctx.fillStyle = n.color ? `rgba(${n.color[0]},${n.color[1]},${n.color[2]},${n.color[3] / 255})` : theme.text;
  lines.forEach((line, k) => haloText(ctx, line, tx, ty + (k - (lines.length - 1) / 2) * lh, halo));
  ctx.restore();
}

function drawText(ctx: CanvasRenderingContext2D, t: TextData, v: PanelView, theme: Theme): void {
  const l = t.spec;
  const r = v.rect;
  const c = t.coords;
  ctx.save();
  ctx.font = `${l.size}px ${theme.font}`;
  ctx.textAlign = l.align;
  ctx.textBaseline = "middle";
  ctx.globalAlpha = l.opacity * (l.context ? 0.35 : 1);
  const solid = l.color ? `rgba(${l.color[0]},${l.color[1]},${l.color[2]},${l.color[3] / 255})` : theme.text;
  ctx.fillStyle = solid;
  const colorOf = (i: number): string => {
    if (!t.colors) return solid;
    const k = i * 4;
    return `rgba(${t.colors[k]},${t.colors[k + 1]},${t.colors[k + 2]},${t.colors[k + 3] / 255})`;
  };
  if (l.repel) {
    // each label where it covers no other, nor a point labelled; else left out
    const points: { index: number; x: number; y: number; w: number }[] = [];
    for (let i = t.starts[v.panel]; i < t.starts[v.panel + 1]; i++) {
      const x = v.map.ox + c[i * 2] * v.map.sx;
      const y = v.map.oy + c[i * 2 + 1] * v.map.sy;
      if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) points.push({ index: i, x, y, w: ctx.measureText(t.labels[i]).width });
    }
    ctx.textAlign = "left";
    for (const p of repel(points, l.size, r, Math.max(4, Math.abs(l.dx), Math.abs(l.dy)))) {
      ctx.fillStyle = colorOf(p.index);
      if (p.leader) {
        ctx.strokeStyle = ctx.fillStyle;
        ctx.globalAlpha = l.opacity * 0.5;
        ctx.beginPath();
        ctx.moveTo(p.leader.x, p.leader.y);
        ctx.lineTo(Math.min(Math.max(p.leader.x, p.x), p.x + ctx.measureText(t.labels[p.index]).width), p.y);
        ctx.stroke();
        ctx.globalAlpha = l.opacity * (l.context ? 0.35 : 1);
      }
      ctx.fillText(t.labels[p.index], p.x, p.y);
    }
    ctx.restore();
    return;
  }
  const margin = 200;
  for (let i = t.starts[v.panel]; i < t.starts[v.panel + 1]; i++) {
    const x = v.map.ox + c[i * 2] * v.map.sx + l.dx;
    const y = v.map.oy + c[i * 2 + 1] * v.map.sy + l.dy;
    if (!(x > r.x - margin && x < r.x + r.w + margin && y > r.y - l.size && y < r.y + r.h + l.size)) continue;
    if (t.colors) {
      const k = i * 4;
      ctx.fillStyle = `rgba(${t.colors[k]},${t.colors[k + 1]},${t.colors[k + 2]},${t.colors[k + 3] / 255})`;
    }
    const px = x - l.dx; // the point the label belongs to
    if (l.align !== "center" && px >= r.x && px <= r.x + r.w) {
      // a label running past the panel's edge goes to the other side of its point
      const w = ctx.measureText(t.labels[i]).width;
      const over = l.align === "left" ? x + w > r.x + r.w : x - w < r.x;
      if (over) {
        ctx.textAlign = l.align === "left" ? "right" : "left";
        ctx.fillText(t.labels[i], px - l.dx, y);
        ctx.textAlign = l.align;
        continue;
      }
    }
    ctx.fillText(t.labels[i], x, y);
  }
  ctx.restore();
}

function drawRule(ctx: CanvasRenderingContext2D, l: RuleLayerSpec, v: PanelView): void {
  const r = v.rect;
  const [cr, cg, cb, ca] = l.color;
  ctx.strokeStyle = `rgba(${cr},${cg},${cb},${ca / 255})`;
  ctx.lineWidth = l.width;
  ctx.setLineDash(l.dash);
  ctx.beginPath();
  l.values.forEach((value, i) => {
    const at = l.panels?.[i] ?? -1; // from data: its panel's (−1: every panel's)
    if (at >= 0 && at !== v.panel) return;
    if (l.axis === "x") {
      const x = Math.round(v.map.ox + value * v.map.sx) + 0.5;
      ctx.moveTo(x, r.y);
      ctx.lineTo(x, r.y + r.h);
    } else {
      const y = Math.round(v.map.oy + value * v.map.sy) + 0.5;
      ctx.moveTo(r.x, y);
      ctx.lineTo(r.x + r.w, y);
    }
  });
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.lineWidth = 1;
}

/** A filled strip: its label centred or at the left (a row's on its side), a paged wrap's
 * sorted value whole at the right. */
function filledStrip(ctx: CanvasRenderingContext2D, theme: Theme, look: Look, s: Strip, note = ""): void {
  const label = s.label;
  ctx.fillStyle = theme.strip;
  ctx.fillRect(s.rect.x, s.rect.y, s.rect.w, s.rect.h);
  // a pinned panel's: a pin, then the label in the room left
  if (s.pin) drawPin(ctx, s.rect.x + STRIP_PAD, s.rect.y + s.rect.h / 2, theme.accent);
  const rect = s.pin ? { ...s.rect, x: s.rect.x + PIN_W, w: s.rect.w - PIN_W } : s.rect;
  ctx.fillStyle = theme.stripText;
  ctx.save();
  if (look.strip_bold) ctx.font = `600 ${theme.fontSize}px ${theme.font}`;
  ctx.beginPath();
  ctx.rect(rect.x, rect.y, rect.w, rect.h);
  ctx.clip();
  if (s.vertical) {
    ctx.translate(rect.x + rect.w / 2, rect.y + rect.h / 2);
    ctx.rotate(Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(fit(ctx, label, rect.h - 6), 0, 0);
  } else if (note) {
    // the name at the left, cut to leave the value whole at the right
    const y = rect.y + rect.h / 2 + 0.5;
    const w = ctx.measureText(note).width;
    ctx.textAlign = "right";
    ctx.fillText(note, rect.x + rect.w - STRIP_PAD, y);
    ctx.textAlign = "left";
    ctx.fillText(fit(ctx, label, rect.w - 3 * STRIP_PAD - w), rect.x + STRIP_PAD, y);
  } else if (look.strip_align === "left" || s.side === "right") {
    ctx.textAlign = "left";
    ctx.fillText(fit(ctx, label, rect.w - 2 * STRIP_PAD), rect.x + STRIP_PAD, rect.y + rect.h / 2 + 0.5);
  } else {
    ctx.textAlign = "center";
    ctx.fillText(fit(ctx, label, rect.w - 6), rect.x + rect.w / 2, rect.y + rect.h / 2 + 0.5);
  }
  ctx.restore();
}

/** A strip with nothing behind it: the label as a title, centred or at the left (a row's
 * level at the left, or on its side); one spanning several panels underlined (a row's: a
 * line at its left) to show which; a paged wrap's sorted value at the right in the muted
 * colour, the name keeping at least half the room. */
function flatStrip(ctx: CanvasRenderingContext2D, theme: Theme, look: Look, s: Strip, note = ""): void {
  const label = s.label;
  const right = s.side === "right";
  if (s.pin) drawPin(ctx, s.rect.x + 1, s.rect.y + s.rect.h / 2, theme.accent);
  const rect = s.pin ? { ...s.rect, x: s.rect.x + PIN_W, w: s.rect.w - PIN_W } : s.rect;
  ctx.save();
  if (s.span) {
    ctx.strokeStyle = theme.axis;
    ctx.beginPath();
    if (right) {
      ctx.moveTo(rect.x + 0.5, rect.y);
      ctx.lineTo(rect.x + 0.5, rect.y + rect.h);
    } else {
      ctx.moveTo(rect.x, rect.y + rect.h - 0.5);
      ctx.lineTo(rect.x + rect.w, rect.y + rect.h - 0.5);
    }
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.rect(rect.x, rect.y, rect.w, rect.h);
  ctx.clip();
  const font = `${look.strip_bold ? "600 " : ""}${theme.fontSize}px ${theme.font}`;
  if (s.vertical) {
    ctx.font = font;
    ctx.fillStyle = theme.text;
    ctx.translate(rect.x + rect.w / 2, rect.y + rect.h / 2);
    ctx.rotate(Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(fit(ctx, label, rect.h - 6), 0, 0);
    ctx.restore();
    return;
  }
  const x = rect.x + (right ? STRIP_PAD : 1);
  const y = rect.y + rect.h / 2 + 0.5;
  let room = rect.x + rect.w - x - 2;
  if (note) {
    const shown = fit(ctx, note, Math.max(0, room / 2));
    ctx.fillStyle = theme.muted;
    ctx.textAlign = "right";
    ctx.fillText(shown, rect.x + rect.w - 1, y);
    room -= ctx.measureText(shown).width + 2 * STRIP_PAD;
  }
  ctx.font = font;
  ctx.fillStyle = theme.text;
  if (look.strip_align === "center" && !right && !note) {
    ctx.textAlign = "center";
    ctx.fillText(fit(ctx, label, rect.w - 6), rect.x + rect.w / 2, y);
  } else {
    ctx.textAlign = "left";
    ctx.fillText(fit(ctx, label, room), x, y);
  }
  ctx.restore();
}

/** The room a pin takes before a pinned panel's label (px). */
export const PIN_W = 11;

/** A pin (a pinned panel's, in its strip): its left at x, centred on y. As figure.py. */
export function drawPin(ctx: CanvasRenderingContext2D, x: number, y: number, color: string): void {
  ctx.save();
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.arc(x + 4, y - 1.5, 3, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(x + 4, y + 1.5);
  ctx.lineTo(x + 4, y + 5.5);
  ctx.stroke();
  ctx.restore();
}

/** `text` cut with an ellipsis to fit `width` px. */
export function fit(ctx: CanvasRenderingContext2D, text: string, width: number): string {
  if (ctx.measureText(text).width <= width) return text;
  let lo = 0;
  let hi = text.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (ctx.measureText(`${text.slice(0, mid)}…`).width <= width) lo = mid;
    else hi = mid - 1;
  }
  return lo ? `${text.slice(0, lo)}…` : "";
}
