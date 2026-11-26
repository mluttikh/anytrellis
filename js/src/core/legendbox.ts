// A plot's legends as HTML: an entry per level (a swatch, or a glyph drawn as the marks
// are), a gradient for a number colour, a search over a long legend. What a click, a hover,
// a double-click or a drag on a gradient does is the owner's (a plot's view: view.ts; a
// figure's legend collected from its plots: figurelegend.ts); the box shows the state it
// is given (the entries chosen, a range, an entry shown alone).
import { type Glyph, drawGlyph, glyphBox } from "./channels";
import { numberFormat } from "./format";
import { type LegendChoice, chooses } from "./selection";
import type { LegendSpec } from "./types";

/** The most entries a legend shows at once (then a search for the rest). */
export const LEGEND_ROWS = 20;

/** What the reader does on a legend; `index` is the legend's (in the legends rendered). */
export interface LegendActions {
  /** A click (or Enter) on a category entry; `add`: with Shift, Cmd or Ctrl. */
  pick(index: number, level: number, add: boolean): void;
  /** A click on a stepped scale's bin. */
  pickBin(index: number, bin: number, add: boolean): void;
  /** A double-click on an entry: shown alone (again: all of them). */
  isolate(index: number, level: number): void;
  /** Hovering or focusing an entry (null: no more). */
  preview(choice: LegendChoice | null): void;
  /** A range dragged on a gradient, on release (null: a click, clearing it). */
  range(index: number, range: [number, number] | null): void;
}

/** What may be chosen on a legend: its entries (`selectable`) or a range of its values. */
export interface LegendPicks {
  selectable: (index: number) => boolean;
  ranged: (index: number) => boolean;
}

export class LegendBox {
  readonly el: HTMLDivElement;
  /** The category legends' entries (legend index, level, element). */
  private items: { index: number; level: number; el: HTMLElement }[] = [];
  /** Number legends' gradients, and the window of a range chosen on them. */
  private gradients: { index: number; bar: HTMLElement; window: HTMLElement; lo: number; hi: number }[] = [];
  private legends: LegendSpec[] = [];

  constructor(el: HTMLDivElement = document.createElement("div")) {
    this.el = el;
    this.el.classList.add("atr-legend");
  }

  /** Draw `legends` (those labelled at the lines' ends left out); `shown`: false hides the box. */
  render(legends: LegendSpec[], picks: LegendPicks, act: LegendActions, shown = true): void {
    this.el.replaceChildren();
    this.items = [];
    this.gradients = [];
    this.legends = legends;
    legends.forEach((lg, index) => {
      if (lg.direct) return; // labelled at the lines' ends instead
      const box = el("div", lg.kind === "number" ? "atr-legend-group" : "atr-legend-group atr-legend-cat");
      box.append(el("span", "atr-legend-title", lg.title));
      if (lg.kind === "number") {
        box.append(...this.gradient(lg, index, picks.ranged(index), act));
        this.el.append(box);
        return;
      }
      const items: HTMLElement[] = [];
      (lg.labels ?? []).forEach((label, i) => {
        const item = el("span", "atr-legend-item");
        item.append(legendSwatch(lg, i), document.createTextNode(label));
        item.dataset.label = label.toLowerCase();
        items.push(item);
        box.append(item);
        // a category's entries select its marks: alone, or added with Shift, Cmd or Ctrl; a
        // stepped scale's bins select a range of its values
        const bins = lg.kind === "bins" && picks.ranged(index) && (lg.breaks?.length ?? 0) > i + 1;
        if (!(lg.kind === "category" && picks.selectable(index)) && !bins) return;
        item.classList.add("atr-legend-pick");
        item.tabIndex = 0;
        item.setAttribute("role", "button");
        item.setAttribute("aria-pressed", "false");
        item.title = bins ? "Click: select its range (Shift+click: widen the range)" : "Click: select its marks (Shift+click: add or remove). Double-click: show it alone";
        const pick = (add: boolean): void => (bins ? act.pickBin(index, i, add) : act.pick(index, i, add));
        item.addEventListener("click", (e) => {
          if (e.detail > 1) return; // a double-click's second click
          pick(e.shiftKey || e.metaKey || e.ctrlKey);
        });
        item.addEventListener("keydown", (e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          e.preventDefault();
          e.stopPropagation();
          pick(e.shiftKey || e.metaKey || e.ctrlKey);
        });
        if (!bins) {
          // hovering an entry shows its marks in every panel; a double-click shows it alone
          item.addEventListener("pointerenter", () => act.preview({ index, levels: [i] }));
          item.addEventListener("pointerleave", () => act.preview(null));
          item.addEventListener("focus", () => act.preview({ index, levels: [i] }));
          item.addEventListener("blur", () => act.preview(null));
          item.addEventListener("dblclick", (e) => {
            e.preventDefault();
            act.isolate(index, i);
          });
        }
        this.items.push({ index, level: i, el: item });
      });
      // many entries: the first ones, and a search for the rest
      if (items.length > LEGEND_ROWS) box.append(...legendSearch(items));
      this.el.append(box);
    });
    this.el.style.display = shown && legends.some((lg) => !lg.direct) ? "flex" : "none";
  }

  /** The chosen entries stand out; the others fade while some are chosen (a range: the
   * bins in it, and its window on a gradient); an entry shown alone, the others struck. */
  update(legend: LegendChoice | null, isolated: { index: number; level: number } | null): void {
    for (const { index, level, el: item } of this.items) {
      const lg = this.legends[index];
      const mine = legend?.index === index;
      let on = mine && legend!.levels.includes(level);
      if (mine && legend!.range && lg?.breaks) on = lg.breaks[level] < legend!.range[1] && lg.breaks[level + 1] > legend!.range[0];
      const chosen = mine && chooses(legend);
      item.classList.toggle("atr-legend-on", on);
      item.classList.toggle("atr-legend-off", chosen && !on);
      item.classList.toggle("atr-legend-hidden", !!isolated && isolated.index === index && isolated.level !== level);
      item.setAttribute("aria-pressed", String(on));
    }
    for (const g of this.gradients) this.showRange(g.index, legend?.index === g.index ? (legend.range ?? null) : null);
  }

  /** A range of a gradient's values, shown on it (null: none). */
  showRange(index: number, range: [number, number] | null): void {
    for (const g of this.gradients) {
      if (g.index !== index) continue;
      if (!range || !(g.hi > g.lo)) {
        g.window.style.display = "none";
        continue;
      }
      const [a, b] = [Math.min(...range), Math.max(...range)].map((v) => Math.max(0, Math.min(1, (v - g.lo) / (g.hi - g.lo))));
      Object.assign(g.window.style, { display: "block", left: `${a * 100}%`, width: `${(b - a) * 100}%` });
    }
  }

  /** A number colour's gradient, between its ends; dragging on it selects a range of its
   * values (a click clears it). */
  private gradient(lg: LegendSpec, index: number, ranged: boolean, act: LegendActions): HTMLElement[] {
    const bar = el("span", "atr-gradient");
    bar.style.background = `linear-gradient(to right, ${lg.colors.join(", ")})`;
    const end = lg.format ? numberFormat(lg.format) : fmt;
    const parts = [el("span", "atr-legend-item", end(lg.lo ?? 0)), bar, el("span", "atr-legend-item", end(lg.hi ?? 1))];
    const lo = lg.lo ?? 0;
    const hi = lg.hi ?? 1;
    const window_ = el("span", "atr-gradient-window");
    bar.append(window_);
    this.gradients.push({ index, bar, window: window_, lo, hi });
    if (!ranged) return parts;
    bar.classList.add("atr-gradient-pick");
    bar.title = "Drag: select a range of values (click: clear it)";
    const valueAt = (clientX: number): number => {
      const r = bar.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (clientX - r.left) / Math.max(1, r.width)));
      return lo + f * (hi - lo);
    };
    let from: number | null = null;
    let moved = false;
    bar.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      bar.setPointerCapture(e.pointerId);
      from = valueAt(e.clientX);
      moved = false;
    });
    bar.addEventListener("pointermove", (e) => {
      if (from === null) return;
      moved = true;
      this.showRange(index, [from, valueAt(e.clientX)]);
    });
    const done = (e: PointerEvent): void => {
      if (from === null) return;
      const start = from;
      from = null;
      const range: [number, number] | null = moved && e.type === "pointerup" ? ([start, valueAt(e.clientX)].sort((a, c) => a - c) as [number, number]) : null;
      act.range(index, range && range[1] > range[0] ? range : null);
    };
    bar.addEventListener("pointerup", done);
    bar.addEventListener("pointercancel", done);
    return parts;
  }
}

/** A search over a long legend's entries: the first LEGEND_ROWS shown, those matching what
 * is typed, and how many more there are. */
function legendSearch(items: HTMLElement[]): HTMLElement[] {
  const input = el("input", "atr-legend-search");
  input.type = "search";
  input.placeholder = `Find (${items.length})`;
  input.setAttribute("aria-label", "Find a legend entry");
  const more = el("span", "atr-legend-more");
  const show = (): void => {
    const q = input.value.trim().toLowerCase();
    let shown = 0;
    let matched = 0;
    for (const item of items) {
      const match = !q || (item.dataset.label ?? "").includes(q);
      if (match) matched++;
      const on = match && shown < LEGEND_ROWS;
      if (on) shown++;
      item.hidden = !on;
    }
    more.textContent = matched > shown ? `${matched - shown} more` : matched === 0 ? "none" : "";
  };
  input.addEventListener("input", show);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && input.value) {
      input.value = "";
      show();
      e.stopPropagation();
    }
  });
  show();
  return [more, input];
}

/** A legend entry's swatch: its colour, or (a shape, dash or size) a small canvas drawn as
 * the marks are, which the export draws again (export.ts: paintHtml, by its glyph). */
export function legendSwatch(lg: LegendSpec, i: number): HTMLElement {
  const glyph: Glyph = { color: lg.colors[i] };
  if (lg.shapes) glyph.shape = lg.shapes[i];
  if (lg.dashes) {
    glyph.dash = lg.dashes[i];
    glyph.lineWidth = lg.line_width;
  }
  if (lg.sizes) glyph.size = lg.sizes[i];
  if (!lg.shapes && !lg.dashes && !lg.sizes) {
    const sw = el("span", "atr-swatch");
    sw.style.background = lg.colors[i];
    return sw;
  }
  const [w, h] = glyphBox(glyph);
  const canvas = document.createElement("canvas");
  canvas.className = "atr-swatch atr-glyph";
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  canvas.dataset.glyph = JSON.stringify(glyph);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.ceil(w * dpr);
  canvas.height = Math.ceil(h * dpr);
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.scale(dpr, dpr);
    drawGlyph(ctx, glyph, 0, 0);
  }
  return canvas;
}

function fmt(v: number): string {
  return Math.abs(v) >= 1e4 || (Math.abs(v) < 1e-2 && v !== 0) ? v.toExponential(2) : String(Math.round(v * 100) / 100);
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
