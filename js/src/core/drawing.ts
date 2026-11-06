// The 2D canvases around the GPU marks: behind them, panel backgrounds and gridlines; in
// front, axes, strips, titles, rules, the crosshair and the hovered mark.

import type { Layout, Rect } from "./layout";
import type { PanelMap } from "./scene";
import { type Tick, ticks } from "./ticks";
import type { RuleLayerSpec, TrellisSpec } from "./types";

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

export function xTicks(spec: TrellisSpec, v: PanelView): Tick[] {
  let count = Math.max(3, Math.floor(v.rect.w / 80));
  if (spec.x.kind === "band" && spec.x.levels?.length) {
    // as many categories as their labels fit (estimated: ~0.6 em per character)
    const longest = Math.max(...spec.x.levels.map((l) => l.length));
    const shown = Math.max(1, v.x[1] - v.x[0]);
    const per = v.rect.w / shown;
    count = Math.floor(shown / Math.max(1, Math.ceil((longest * 7.2 + 10) / per)));
  }
  return ticks(spec.x.kind, v.x[0], v.x[1], spec.x.origin, Math.max(2, count), spec.x.levels);
}

export function yTicks(spec: TrellisSpec, v: PanelView): Tick[] {
  let count = Math.floor(v.rect.h / 36);
  if (spec.y.kind === "band") {
    // a category per label height (about 15 px)
    const shown = Math.max(1, v.y[1] - v.y[0]);
    count = Math.floor(shown / Math.max(1, Math.ceil(15 / (v.rect.h / shown))));
  }
  return ticks(spec.y.kind, v.y[0], v.y[1], spec.y.origin, Math.max(2, count), spec.y.levels);
}

export function drawBack(ctx: CanvasRenderingContext2D, spec: TrellisSpec, views: PanelView[], theme: Theme): void {
  for (const v of views) {
    const r = v.rect;
    ctx.fillStyle = theme.panel;
    ctx.fillRect(r.x, r.y, r.w, r.h);
    ctx.save();
    ctx.beginPath();
    ctx.rect(r.x, r.y, r.w, r.h);
    ctx.clip();
    ctx.strokeStyle = theme.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (spec.x.kind !== "band") {
      for (const t of xTicks(spec, v)) {
        const x = Math.round(v.map.ox + t.value * v.map.sx) + 0.5;
        ctx.moveTo(x, r.y);
        ctx.lineTo(x, r.y + r.h);
      }
    }
    if (spec.y.kind !== "band") {
      for (const t of yTicks(spec, v)) {
        const y = Math.round(v.map.oy + t.value * v.map.sy) + 0.5;
        ctx.moveTo(r.x, y);
        ctx.lineTo(r.x + r.w, y);
      }
    }
    ctx.stroke();
    ctx.restore();
  }
}

export interface FrontState {
  /** Data x (axis units) of the pointer, drawn in the panels of `crossGroup`. */
  crossX: number | null;
  crossGroup: number | null;
  /** The hovered mark: centre (px) and radius, in panel `hoverPanel`. */
  hover: { x: number; y: number; r: number; color: string } | null;
  hoverPanel: number | null;
  /** A zoom box being dragged (px). */
  box: Rect | null;
}

export function drawFront(ctx: CanvasRenderingContext2D, spec: TrellisSpec, layout: Layout, views: PanelView[], theme: Theme, state: FrontState): void {
  const fs = theme.fontSize;
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
    if (state.hover && state.hoverPanel === v.panel) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = theme.bg;
      ctx.beginPath();
      ctx.arc(state.hover.x, state.hover.y, state.hover.r + 2, 0, Math.PI * 2);
      ctx.stroke();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = state.hover.color;
      ctx.beginPath();
      ctx.arc(state.hover.x, state.hover.y, state.hover.r + 3.5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.lineWidth = 1;
    }
    ctx.restore();
  });

  // axes
  ctx.fillStyle = theme.muted;
  ctx.strokeStyle = theme.axis;
  layout.panels.forEach((box, i) => {
    const v = views[i];
    const r = v.rect;
    if (box.showX) {
      ctx.textAlign = "center";
      ctx.beginPath();
      ctx.moveTo(r.x, r.y + r.h + 0.5);
      ctx.lineTo(r.x + r.w, r.y + r.h + 0.5);
      let lastRight = -Infinity;
      for (const t of xTicks(spec, v)) {
        const x = v.map.ox + t.value * v.map.sx;
        if (x < r.x - 0.5 || x > r.x + r.w + 0.5) continue;
        ctx.moveTo(Math.round(x) + 0.5, r.y + r.h);
        ctx.lineTo(Math.round(x) + 0.5, r.y + r.h + 4);
        const w = ctx.measureText(t.label).width;
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
      ctx.moveTo(r.x - 0.5, r.y);
      ctx.lineTo(r.x - 0.5, r.y + r.h);
      let lastTop = Infinity;
      for (const t of yTicks(spec, v)) {
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
  const strip = (rect: Rect, label: string, vertical: boolean): void => {
    ctx.fillStyle = theme.strip;
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    ctx.fillStyle = theme.stripText;
    ctx.save();
    ctx.beginPath();
    ctx.rect(rect.x, rect.y, rect.w, rect.h);
    ctx.clip();
    if (vertical) {
      ctx.translate(rect.x + rect.w / 2, rect.y + rect.h / 2);
      ctx.rotate(Math.PI / 2);
      ctx.textAlign = "center";
      ctx.fillText(fit(ctx, label, rect.h - 6), 0, 0);
    } else {
      ctx.textAlign = "center";
      ctx.fillText(fit(ctx, label, rect.w - 6), rect.x + rect.w / 2, rect.y + rect.h / 2 + 0.5);
    }
    ctx.restore();
  };
  for (const box of layout.panels) if (box.strip) strip(box.strip, box.label, false);
  for (const s of layout.strips) strip(s.rect, s.label, s.vertical);

  // titles
  ctx.fillStyle = theme.text;
  if (layout.title) {
    ctx.font = `600 ${Math.round(fs * 1.2)}px ${theme.font}`;
    ctx.textAlign = "left";
    ctx.fillText(spec.title, layout.title.x, layout.title.y);
  }
  ctx.font = `${fs}px ${theme.font}`;
  ctx.fillStyle = theme.muted;
  if (layout.xTitle) {
    ctx.textAlign = "center";
    ctx.fillText(spec.x.title, layout.xTitle.x, layout.xTitle.y);
  }
  if (layout.yTitle) {
    ctx.save();
    ctx.translate(layout.yTitle.x, layout.yTitle.y);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(spec.y.title, 0, 0);
    ctx.restore();
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
}

function drawRule(ctx: CanvasRenderingContext2D, l: RuleLayerSpec, v: PanelView): void {
  const r = v.rect;
  const [cr, cg, cb, ca] = l.color;
  ctx.strokeStyle = `rgba(${cr},${cg},${cb},${ca / 255})`;
  ctx.lineWidth = l.width;
  ctx.setLineDash(l.dash);
  ctx.beginPath();
  for (const value of l.values) {
    if (l.axis === "x") {
      const x = Math.round(v.map.ox + value * v.map.sx) + 0.5;
      ctx.moveTo(x, r.y);
      ctx.lineTo(x, r.y + r.h);
    } else {
      const y = Math.round(v.map.oy + value * v.map.sy) + 0.5;
      ctx.moveTo(r.x, y);
      ctx.lineTo(r.x + r.w, y);
    }
  }
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.lineWidth = 1;
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
