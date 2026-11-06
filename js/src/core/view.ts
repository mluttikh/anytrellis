// TrellisView: one plot in the page. A header (title, the way back from an opened panel,
// the toolbar), then three stacked canvases: behind (panel backgrounds, gridlines; Canvas
// 2D), the marks (the GPU renderer, every panel a scissored viewport of one canvas), and in
// front (axes, strips, rules, crosshair, hover; Canvas 2D). The legend in a wrap's empty
// cells when it fits there, or under the plot.
//
// Each scale group (panels with the same domain) has one view range, so zooming or panning
// a panel moves every panel that shares its scale, also from an opened panel: back in the
// grid, the panels show what the opened one showed.
//
// Opening a panel (double-click, Enter) shows it alone on the whole width ("small
// multiples, large singles", van den Elzen and van Wijk 2013); Page Up and Page Down step to
// the previous and next panel, keeping the zoom. Full screen (f, the toolbar) uses the
// browser's Fullscreen API on the plot's own element.

import { type FrontState, type PanelView, type Theme, drawBack, drawFront, readTheme } from "./drawing";
import { type Layout, type Rect, layout as computeLayout, panelName } from "./layout";
import { createRenderer } from "./renderers/select";
import type { Draw, Renderer } from "./renderers/renderer";
import { type Hit, type LayerData, type PanelMap, type Scene, buildScene, bufferIds, hitPoint, pick } from "./scene";
import { formatValue } from "./ticks";
import type { DataSource, LegendSpec, RendererPreference, TrellisSpec } from "./types";

export interface ViewOptions {
  source: DataSource;
  renderer: RendererPreference;
  /** Python's tooltip columns for one instance of a layer (absent: none). */
  tooltip?: (layer: number, instance: number) => Promise<string[][]>;
  /** The reader opened a panel (its name) or went back to all of them (null). */
  onFocus?: (name: string | null) => void;
}

type Range = [number, number];

const ZOOM_SPEED = 0.0015;
const HOVER_RADIUS = 10;
/** An opened panel's height (not full screen): the grid's, within these bounds. */
const FOCUS_MIN = 320;
const FOCUS_MAX_SCREEN = 0.85;

const ICONS = {
  back: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>',
  prev: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 4 6 8l4 4" /></svg>',
  next: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4" /></svg>',
  reset: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8a5 5 0 1 0 1.5-3.5" /><path d="M3 2.5V5h2.5" /></svg>',
  expand: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10" /></svg>',
  collapse: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 2.5V6H2.5M13.5 6H10V2.5M10 13.5V10h3.5M2.5 10H6v3.5" /></svg>',
};

export class TrellisView {
  readonly root: HTMLDivElement;
  private readonly header: HTMLDivElement;
  private readonly heading: HTMLDivElement;
  private readonly toolbar: HTMLDivElement;
  private readonly backButton: HTMLButtonElement;
  private readonly resetButton: HTMLButtonElement;
  private readonly fullButton: HTMLButtonElement;
  private readonly legend: HTMLDivElement;
  private readonly stage: HTMLDivElement;
  private readonly back: HTMLCanvasElement;
  private readonly front: HTMLCanvasElement;
  private readonly tip: HTMLDivElement;
  private readonly status: HTMLDivElement;
  private readonly notice: HTMLDivElement;
  private readonly badge: HTMLDivElement;
  private renderer: Renderer | null = null;
  private rendererReady: Promise<void>;
  private spec: TrellisSpec | null = null;
  private scene: Scene | null = null;
  private lay: Layout | null = null;
  private theme: Theme;
  private xView = new Map<number, Range>();
  private yView = new Map<number, Range>();
  private views: PanelView[] = [];
  private frameRequested = false;
  private front_: FrontState = { crossX: null, crossGroup: null, hover: null, hoverPanel: null, box: null };
  private drag: { view: number; x: number; y: number; xr: Range; yr: Range; moved: boolean } | null = null;
  private hoverKey = "";
  private tipRequest = 0;
  /** The panel under the pointer (index in spec.panels), for Enter. */
  private pointerPanel: number | null = null;
  /** The opened panel (index in spec.panels), or null: all of them. */
  private focused: number | null = null;
  /** A panel to open once the spec is in (the name Python asked for). */
  private pendingFocus: string | null = null;
  private gridHeight = 0;
  private noticeTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly resizeObserver: ResizeObserver;
  private readonly themeObserver: MutationObserver;
  private readonly abort = new AbortController();
  private width = 0;
  private dpr = 1;
  private specVersion = 0;
  private destroyed = false;

  constructor(
    host: HTMLElement,
    private readonly opts: ViewOptions,
  ) {
    this.root = el("div", "atr-root");
    this.root.tabIndex = 0;
    this.header = el("div", "atr-header");
    this.heading = el("div", "atr-heading");
    this.toolbar = el("div", "atr-toolbar");
    this.backButton = button(ICONS.back, "All panels (Backspace)", () => this.setFocus(null, true));
    this.backButton.hidden = true;
    this.resetButton = button(ICONS.reset, "Reset zoom (r)", () => this.resetZoom());
    this.fullButton = button(ICONS.expand, "Full screen (f)", () => this.toggleFullscreen());
    this.fullButton.hidden = !document.fullscreenEnabled; // in some frames (and iPhones): none
    this.toolbar.append(this.backButton, this.resetButton, this.fullButton);
    this.header.append(this.heading, this.toolbar);
    this.legend = el("div", "atr-legend");
    this.stage = el("div", "atr-stage");
    this.back = el("canvas", "atr-canvas");
    this.front = el("canvas", "atr-canvas atr-front");
    this.tip = el("div", "atr-tip");
    this.status = el("div", "atr-status");
    this.notice = el("div", "atr-notice");
    this.notice.hidden = true;
    this.badge = el("div", "atr-badge");
    this.stage.append(this.back, this.front, this.tip, this.status, this.notice);
    this.root.append(this.header, this.stage, this.legend, this.badge);
    host.append(this.root);
    this.theme = readTheme(this.root);
    this.rendererReady = this.makeRenderer(opts.renderer);
    this.resizeObserver = new ResizeObserver(() => this.relayout());
    this.resizeObserver.observe(this.root);
    // the host's theme (light or dark) changes: read the colours again
    this.themeObserver = new MutationObserver(() => {
      this.theme = readTheme(this.root);
      this.request();
    });
    for (const target of [document.documentElement, document.body]) {
      this.themeObserver.observe(target, { attributes: true, attributeFilter: ["class", "data-theme", "data-jp-theme-light"] });
    }
    this.listen();
  }

  private async makeRenderer(pref: RendererPreference, skip: string[] = []): Promise<void> {
    const make = (): HTMLCanvasElement => {
      const c = el("canvas", "atr-canvas atr-marks");
      this.stage.insertBefore(c, this.front);
      return c;
    };
    try {
      const { renderer } = await createRenderer(pref, make, skip as never);
      if (this.destroyed) {
        renderer.destroy();
        return;
      }
      this.renderer = renderer;
      renderer.onFailure = (reason) => {
        console.warn(`[anytrellis] ${reason}; falling back`);
        const failed = renderer.kind;
        renderer.destroy();
        renderer.canvas.remove();
        this.renderer = null;
        this.rendererReady = this.makeRenderer("auto", [...skip, failed]).then(() => this.relayout());
      };
      this.badge.textContent = renderer.description;
      this.root.dataset.renderer = renderer.kind;
    } catch (err) {
      this.setStatus(`Cannot draw: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  /** Show a spec: wait for its buffers, then draw it. */
  async setSpec(spec: TrellisSpec): Promise<void> {
    const version = ++this.specVersion;
    if (!spec || !spec.panels) return;
    await Promise.all([this.opts.source.ensure(bufferIds(spec)), this.rendererReady]);
    if (version !== this.specVersion || this.destroyed) return;
    const old = this.spec;
    const openName = this.pendingFocus ?? (old && this.focused !== null ? panelName(old, this.focused) : null);
    this.spec = spec;
    this.scene = buildScene(spec, this.opts.source);
    this.renderer?.retain(new Set(this.scene.layers.map((l) => l.set.key)));
    // keep the zoom when only the layers changed (same domains)
    const same = old !== null && JSON.stringify(old.panels) === JSON.stringify(spec.panels);
    if (!same) this.resetViews();
    // the opened panel stays open when the new spec still has it
    this.pendingFocus = null;
    this.focused = this.indexOf(openName);
    this.renderLegend(spec.legends);
    this.setStatus(null);
    this.updateHeader();
    this.relayout();
  }

  /** Open the panel named `name` (Python: Trellis.open), or none. */
  setFocusName(name: string | null): void {
    if (!this.spec) {
      this.pendingFocus = name;
      return;
    }
    const index = this.indexOf(name);
    if (index !== this.focused) this.setFocus(index, false);
  }

  private indexOf(name: string | null): number | null {
    const spec = this.spec;
    if (name === null || !spec || spec.panels.length < 2) return null;
    const i = spec.panels.findIndex((_, k) => panelName(spec, k) === name);
    return i >= 0 ? i : null;
  }

  setStatus(text: string | null): void {
    this.status.textContent = text ?? "";
    this.status.style.display = text ? "block" : "none";
  }

  /** A short message over the plot, for a moment. */
  private notify(text: string): void {
    this.notice.textContent = text;
    this.notice.hidden = false;
    clearTimeout(this.noticeTimer);
    this.noticeTimer = setTimeout(() => (this.notice.hidden = true), 1600);
  }

  private resetViews(): void {
    if (!this.spec) return;
    for (const p of this.spec.panels) {
      this.xView.set(p.xg, [p.x[0], p.x[1]]);
      this.yView.set(p.yg, [p.y[0], p.y[1]]);
    }
  }

  private resetZoom(): void {
    this.resetViews();
    this.hideTip();
    this.request();
  }

  // ---- opening a panel, full screen -------------------------------------------------------

  /** Open panel `index` (null: back to all). `user`: the reader did it (tell Python, and
   * keep the plot in view). */
  private setFocus(index: number | null, user: boolean): void {
    if (!this.spec || this.spec.panels.length < 2) return;
    if (index !== null && !this.spec.panels[index]) return;
    if (index === this.focused) return;
    this.focused = index;
    this.drag = null;
    this.clearHover();
    this.updateHeader();
    this.relayout();
    if (user) {
      this.opts.onFocus?.(index === null ? null : panelName(this.spec, index));
      // a grid taller than the window: the opened panel (or the plot again) into view
      if (!this.isFullscreen()) this.root.scrollIntoView?.({ block: "nearest" });
    }
  }

  /** The previous or next panel, opened at the same zoom (Page Up, Page Down, ‹ ›). */
  private stepPanel(step: number): void {
    if (!this.spec || this.focused === null) return;
    const n = this.spec.panels.length;
    const next = this.focused + step;
    if (next < 0 || next >= n) {
      this.notify(`${panelName(this.spec, this.focused)} is the ${next < 0 ? "first" : "last"} panel`);
      return;
    }
    this.setFocus(next, true);
    this.notify(`${panelName(this.spec, next)} · ${next + 1} of ${n}`);
  }

  private isFullscreen(): boolean {
    // :fullscreen, not document.fullscreenElement: inside a shadow root (marimo puts widgets
    // in one) the document reports the shadow root's host, not this element
    return this.root.matches(":fullscreen");
  }

  private toggleFullscreen(): void {
    if (!document.fullscreenEnabled) {
      this.notify("Full screen is not available here");
      return;
    }
    const done = this.isFullscreen() ? document.exitFullscreen() : this.root.requestFullscreen();
    done.catch((err) => {
      console.warn("[anytrellis] full screen not available:", err);
      this.notify("Full screen is not available here");
    });
  }

  private fullscreenChanged(): void {
    const full = this.isFullscreen();
    this.root.classList.toggle("atr-fullscreen", full);
    this.fullButton.innerHTML = full ? ICONS.collapse : ICONS.expand;
    const tip = full ? "Exit full screen (f, Esc)" : "Full screen (f)";
    this.fullButton.dataset.tip = tip;
    this.fullButton.title = tip;
    this.fullButton.setAttribute("aria-label", full ? "Exit full screen" : "Full screen");
    this.relayout();
  }

  /** The title, and for an opened panel the way back: All panels › ‹ name ›. */
  private updateHeader(): void {
    const spec = this.spec;
    this.heading.replaceChildren();
    if (spec?.title) this.heading.append(el("span", "atr-title", spec.title));
    const open = spec !== null && this.focused !== null;
    this.backButton.hidden = !open;
    this.root.classList.toggle("atr-open", open);
    if (!spec || this.focused === null) return;
    const crumb = el("span", "atr-crumb");
    const all = el("button", "atr-link", "All panels");
    all.type = "button";
    all.title = "Back to all panels (Backspace, double-click)";
    all.addEventListener("click", () => this.setFocus(null, true));
    const prev = button(ICONS.prev, "Previous panel (Page Up)", () => this.stepPanel(-1));
    const next = button(ICONS.next, "Next panel (Page Down)", () => this.stepPanel(1));
    prev.disabled = this.focused === 0;
    next.disabled = this.focused === spec.panels.length - 1;
    crumb.append(all, el("span", "atr-sep", "›"), prev, el("span", "atr-panel-name", panelName(spec, this.focused)), next);
    this.heading.append(crumb);
  }

  // ---- layout and drawing -------------------------------------------------------------------

  private relayout(): void {
    if (!this.spec) return;
    const width = Math.floor(this.stage.clientWidth || this.root.clientWidth);
    if (width <= 0) return;
    this.width = width;
    this.dpr = window.devicePixelRatio || 1;
    this.theme = readTheme(this.root);
    const ctx = this.front.getContext("2d")!;
    ctx.font = `${this.theme.fontSize}px ${this.theme.font}`;
    const base = { width, fontSize: this.theme.fontSize, measure: (t: string) => ctx.measureText(t).width, title: false };
    // full screen: the screen less the header and the legend; an opened panel otherwise:
    // about the grid's height, so the page does not jump
    let height: number | null = null;
    if (this.isFullscreen()) {
      const css = getComputedStyle(this.root);
      const pad = parseFloat(css.paddingTop) + parseFloat(css.paddingBottom);
      height = Math.max(200, this.root.clientHeight - pad - this.header.offsetHeight - 4);
    }
    if (this.focused === null) {
      this.lay = computeLayout(this.spec, { ...base, height });
      const spare = this.spec.legend_position === "bottom" ? null : this.lay.spare;
      if (!this.placeLegend(spare) && height !== null) {
        // under the plot after all: full screen leaves it room
        this.lay = computeLayout(this.spec, { ...base, height: height - this.legend.offsetHeight });
      }
      this.gridHeight = this.lay.height;
    } else {
      this.placeLegend(null);
      if (height !== null) height -= this.legend.offsetHeight;
      if (height === null) this.gridHeight = computeLayout(this.spec, base).height;
      const h = height ?? Math.max(FOCUS_MIN, Math.min(this.gridHeight, window.innerHeight * FOCUS_MAX_SCREEN));
      this.lay = computeLayout(this.spec, { ...base, height: h, focused: this.focused });
    }
    const h = this.lay.height;
    this.stage.style.height = `${h}px`;
    for (const c of [this.back, this.front]) sizeCanvas(c, width, h, this.dpr);
    this.renderer?.resize(width, h, this.dpr);
    if (this.renderer) {
      this.renderer.canvas.style.width = `${width}px`;
      this.renderer.canvas.style.height = `${h}px`;
    }
    this.request();
  }

  private request(): void {
    if (this.frameRequested || this.destroyed) return;
    this.frameRequested = true;
    requestAnimationFrame(() => {
      this.frameRequested = false;
      this.draw();
    });
  }

  private panelViews(): PanelView[] {
    const spec = this.spec!;
    return this.lay!.panels.map((box) => {
      const p = spec.panels[box.index];
      const x = this.xView.get(p.xg) ?? p.x;
      const y = this.yView.get(p.yg) ?? p.y;
      const r = box.rect;
      const sx = r.w / (x[1] - x[0] || 1);
      const sy = -r.h / (y[1] - y[0] || 1);
      const map: PanelMap = { sx, ox: r.x - x[0] * sx, sy, oy: r.y + r.h - y[0] * sy };
      return { panel: box.index, rect: r, map, x: [x[0], x[1]], y: [y[0], y[1]] };
    });
  }

  private draw(): void {
    if (!this.spec || !this.scene || !this.lay) return;
    const views = this.panelViews();
    this.views = views;
    const back = this.back.getContext("2d")!;
    back.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    back.clearRect(0, 0, this.width, this.lay.height);
    drawBack(back, this.spec, views, this.theme);
    if (this.renderer) {
      const draws: Draw[] = [];
      for (const layer of this.scene.layers) {
        for (const v of views) {
          const p = v.panel;
          const start = layer.starts[p];
          const count = layer.starts[p + 1] - start;
          if (!count) continue;
          const { map, rect } = v;
          draws.push({
            set: layer.set,
            start,
            count,
            clip: rect,
            sx: map.sx,
            ox: map.ox + this.scene.baseX[p] * map.sx,
            sy: map.sy,
            oy: map.oy + this.scene.baseY[p] * map.sy,
            kind: layer.kind,
            halfWidth: layer.halfWidth,
            opacity: layer.spec.opacity,
          });
        }
      }
      this.renderer.render({ draws });
    }
    const front = this.front.getContext("2d")!;
    front.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    front.clearRect(0, 0, this.width, this.lay.height);
    drawFront(front, this.spec, this.lay, views, this.theme, this.front_);
  }

  // ---- input ----------------------------------------------------------------------------

  /** The view (index in this.views) under a point of the stage, or -1. */
  private viewAt(x: number, y: number): number {
    const views = this.views;
    for (let i = 0; i < views.length; i++) {
      const r = views[i].rect;
      if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return i;
    }
    return -1;
  }

  private local(e: MouseEvent): [number, number] {
    const r = this.stage.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  /** Scrolling zooms once the plot has the focus (clicked), or in full screen. */
  private isActive(): boolean {
    return this.isFullscreen() || this.root.matches(":focus-within");
  }

  private listen(): void {
    const stage = this.stage;
    const signal = this.abort.signal;
    // entering or leaving full screen (the button, f, Esc or the browser's own controls)
    document.addEventListener("fullscreenchange", () => this.fullscreenChanged(), { signal });
    stage.addEventListener(
      "wheel",
      (e) => {
        if (!this.spec || !this.isActive()) return;
        const [x, y] = this.local(e);
        const vi = this.viewAt(x, y);
        if (vi < 0) return;
        e.preventDefault();
        const factor = Math.exp((e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY) * ZOOM_SPEED);
        const v = this.views[vi];
        const panel = this.spec.panels[v.panel];
        if (e.shiftKey) {
          const at = (y - v.map.oy) / v.map.sy;
          this.yView.set(panel.yg, zoom(v.y, at, factor));
        } else {
          const at = (x - v.map.ox) / v.map.sx;
          this.xView.set(panel.xg, zoom(v.x, at, factor));
        }
        this.hideTip();
        this.request();
      },
      { passive: false, signal },
    );
    stage.addEventListener(
      "pointerdown",
      (e) => {
        if (e.button !== 0) return;
        this.root.focus({ preventScroll: true });
        const [x, y] = this.local(e);
        const vi = this.viewAt(x, y);
        if (vi < 0) return;
        const v = this.views[vi];
        this.drag = { view: vi, x, y, xr: [...v.x], yr: [...v.y], moved: false };
        stage.setPointerCapture(e.pointerId);
      },
      { signal },
    );
    stage.addEventListener(
      "pointermove",
      (e) => {
        const [x, y] = this.local(e);
        if (this.drag && this.spec) {
          const d = this.drag;
          const v = this.views[d.view];
          if (!v) return;
          if (!d.moved && Math.hypot(x - d.x, y - d.y) < 3) return;
          d.moved = true;
          const dx = (x - d.x) / v.map.sx;
          const dy = (y - d.y) / v.map.sy;
          const panel = this.spec.panels[v.panel];
          this.xView.set(panel.xg, [d.xr[0] - dx, d.xr[1] - dx]);
          this.yView.set(panel.yg, [d.yr[0] - dy, d.yr[1] - dy]);
          this.hideTip();
          this.request();
          return;
        }
        this.hover(x, y);
      },
      { signal },
    );
    const end = (e: PointerEvent): void => {
      if (this.drag) stage.releasePointerCapture?.(e.pointerId);
      this.drag = null;
    };
    stage.addEventListener("pointerup", end, { signal });
    stage.addEventListener("pointercancel", end, { signal });
    stage.addEventListener(
      "pointerleave",
      () => {
        this.pointerPanel = null;
        if (!this.drag) this.clearHover();
      },
      { signal },
    );
    // double-click: open the panel, or back to all; a plot of one panel resets its zoom
    stage.addEventListener(
      "dblclick",
      (e) => {
        if (!this.spec) return;
        const [x, y] = this.local(e);
        const vi = this.viewAt(x, y);
        if (this.spec.panels.length < 2) {
          if (vi >= 0) this.resetZoom();
        } else if (this.focused !== null) this.setFocus(null, true);
        else if (vi >= 0) this.setFocus(this.views[vi].panel, true);
      },
      { signal },
    );
    // the keys handled stop here: JupyterLab would also act on them (in command mode, Enter
    // edits a cell, f finds); buttons keep Enter and Space
    this.root.addEventListener(
      "keydown",
      (e) => {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        if ((e.key === "Enter" || e.key === " ") && (e.target as HTMLElement).closest("button")) return;
        if (this.key(e.key)) {
          e.preventDefault();
          e.stopPropagation();
        }
      },
      { signal },
    );
  }

  /** A key pressed with the plot focused; true when it is the plot's. */
  private key(key: string): boolean {
    const many = (this.spec?.panels.length ?? 0) > 1;
    switch (key) {
      case "f":
        this.toggleFullscreen();
        return true;
      case "r":
      case "0":
        this.resetZoom();
        return true;
      case "Enter":
        if (!many || this.focused !== null) return false;
        if (this.pointerPanel === null) {
          this.notify("Point at a panel to open it");
          return true;
        }
        this.setFocus(this.pointerPanel, true);
        return true;
      case "Escape":
      case "Backspace":
        if (this.focused === null) return false;
        this.setFocus(null, true);
        return true;
      case "PageUp":
      case "PageDown":
        if (this.focused === null) return false;
        this.stepPanel(key === "PageDown" ? 1 : -1);
        return true;
      default:
        return false;
    }
  }

  private hover(x: number, y: number): void {
    if (!this.spec || !this.scene) return;
    const vi = this.viewAt(x, y);
    if (vi < 0) {
      this.pointerPanel = null;
      this.clearHover();
      return;
    }
    const v = this.views[vi];
    const p = v.panel;
    this.pointerPanel = p;
    const panel = this.spec.panels[p];
    this.front_.crossX = this.spec.x.kind === "band" ? null : (x - v.map.ox) / v.map.sx;
    this.front_.crossGroup = panel.xg;
    const hit = pick(this.scene, p, v.map, x, y, HOVER_RADIUS);
    if (!hit) {
      this.front_.hover = null;
      this.front_.hoverPanel = null;
      this.hideTip();
      this.request();
      return;
    }
    const pt = hitPoint(hit, v.map, x, y);
    const hx = v.map.ox + pt.x * v.map.sx;
    const hy = v.map.oy + pt.y * v.map.sy;
    const c = hit.layer.set.colors;
    const color = `rgb(${c[hit.instance * 4]},${c[hit.instance * 4 + 1]},${c[hit.instance * 4 + 2]})`;
    this.front_.hover = hit.layer.kind === 0 ? null : { x: hx, y: hy, r: Math.max(3, hit.layer.halfWidth), color };
    this.front_.hoverPanel = p;
    this.showTip(hit, p, pt, x, y, v);
    this.request();
  }

  private clearHover(): void {
    this.front_.crossX = null;
    this.front_.hover = null;
    this.front_.hoverPanel = null;
    this.hideTip();
    this.request();
  }

  private showTip(hit: Hit, p: number, pt: { x: number; y: number; y0: number }, px: number, py: number, v: PanelView): void {
    const spec = this.spec!;
    const layer = hit.layer;
    const rows: [string, string][] = [];
    const keys = spec.panels[p].keys.join(" · ");
    const isBar = layer.kind === 0;
    rows.push([spec.x.title || "x", formatValue(spec.x.kind, pt.x, spec.x.origin, v.x[1] - v.x[0], spec.x.levels)]);
    rows.push([spec.y.title || "y", formatValue(spec.y.kind, isBar ? pt.y - pt.y0 : pt.y, spec.y.origin, v.y[1] - v.y[0], spec.y.levels)]);
    const legend = layer.spec.color.legend;
    if (layer.codes && legend !== null) {
      const lg = spec.legends[legend];
      rows.push([lg.title, lg.labels?.[layer.codes[hit.instance]] ?? ""]);
    }
    const key = `${layer.index}:${hit.instance}`;
    this.renderTip(keys, layer, rows, []);
    this.placeTip(px, py);
    if (key === this.hoverKey) return;
    this.hoverKey = key;
    if (layer.spec.tooltip && this.opts.tooltip) {
      const req = ++this.tipRequest;
      this.opts
        .tooltip(layer.index, hit.instance)
        .then((extra) => {
          if (req !== this.tipRequest || this.hoverKey !== key) return;
          this.renderTip(keys, layer, rows, extra);
        })
        .catch(() => {});
    }
  }

  private renderTip(title: string, layer: LayerData, rows: [string, string][], extra: string[][]): void {
    const multi = (this.spec?.layers.length ?? 0) > 1;
    const head = [title, multi ? layer.spec.name : ""].filter(Boolean).join(" — ");
    const all = [...rows, ...extra.map(([k, v]) => [k, v] as [string, string])];
    this.tip.replaceChildren();
    if (head) this.tip.append(el("div", "atr-tip-head", head));
    const table = el("table");
    for (const [k, val] of all) {
      const tr = el("tr");
      tr.append(el("th", "", k), el("td", "", val));
      table.append(tr);
    }
    this.tip.append(table);
    this.tip.style.display = "block";
  }

  private placeTip(px: number, py: number): void {
    const w = this.tip.offsetWidth;
    const h = this.tip.offsetHeight;
    const left = px + 14 + w > this.width ? px - 14 - w : px + 14;
    const top = Math.max(0, py - h - 10);
    this.tip.style.left = `${Math.max(0, left)}px`;
    this.tip.style.top = `${top}px`;
  }

  private hideTip(): void {
    this.tip.style.display = "none";
    this.hoverKey = "";
  }

  /** The legend in `spare` (a wrap's empty cells) if it fits there, as a list or else in
   * rows; under the plot otherwise. True when it went in. */
  private placeLegend(spare: Rect | null): boolean {
    const lg = this.legend;
    if (spare && this.spec?.legends.length) {
      if (lg.parentElement !== this.stage) this.stage.append(lg);
      lg.classList.add("atr-inset");
      Object.assign(lg.style, { left: `${spare.x}px`, top: `${spare.y}px`, width: `${spare.w}px`, height: `${spare.h}px` });
      for (const rows of [false, true]) {
        lg.classList.toggle("atr-inset-rows", rows);
        if (lg.scrollHeight <= lg.clientHeight + 1 && lg.scrollWidth <= lg.clientWidth + 1) return true;
      }
    }
    lg.classList.remove("atr-inset", "atr-inset-rows");
    Object.assign(lg.style, { left: "", top: "", width: "", height: "" });
    if (lg.parentElement !== this.root || lg.nextSibling !== this.badge) this.root.insertBefore(lg, this.badge);
    return false;
  }

  private renderLegend(legends: LegendSpec[]): void {
    this.legend.replaceChildren();
    for (const lg of legends) {
      const box = el("div", lg.kind === "category" ? "atr-legend-group atr-legend-cat" : "atr-legend-group");
      box.append(el("span", "atr-legend-title", lg.title));
      if (lg.kind === "category") {
        (lg.labels ?? []).forEach((label, i) => {
          const item = el("span", "atr-legend-item");
          const sw = el("span", "atr-swatch");
          sw.style.background = lg.colors[i];
          item.append(sw, document.createTextNode(label));
          box.append(item);
        });
      } else {
        const bar = el("span", "atr-gradient");
        bar.style.background = `linear-gradient(to right, ${lg.colors.join(", ")})`;
        box.append(el("span", "atr-legend-item", fmt(lg.lo ?? 0)), bar, el("span", "atr-legend-item", fmt(lg.hi ?? 1)));
      }
      this.legend.append(box);
    }
    this.legend.style.display = legends.length ? "flex" : "none";
  }

  get rendererKind(): string | null {
    return this.renderer?.kind ?? null;
  }

  /** The opened panel's name, or null. */
  get focusName(): string | null {
    return this.spec && this.focused !== null ? panelName(this.spec, this.focused) : null;
  }

  /** A PNG of the plot as shown: the three canvases composed. */
  async snapshot(): Promise<Blob> {
    const out = document.createElement("canvas");
    out.width = this.back.width;
    out.height = this.back.height;
    const ctx = out.getContext("2d")!;
    ctx.fillStyle = this.theme.bg;
    ctx.fillRect(0, 0, out.width, out.height);
    this.draw();
    ctx.drawImage(this.back, 0, 0);
    if (this.renderer) ctx.drawImage(this.renderer.canvas, 0, 0);
    ctx.drawImage(this.front, 0, 0);
    return new Promise((resolve, reject) => out.toBlob((b) => (b ? resolve(b) : reject(new Error("no image"))), "image/png"));
  }

  destroy(): void {
    this.destroyed = true;
    this.abort.abort();
    clearTimeout(this.noticeTimer);
    if (this.isFullscreen()) document.exitFullscreen().catch(() => {});
    this.resizeObserver.disconnect();
    this.themeObserver.disconnect();
    this.renderer?.destroy();
    this.root.remove();
  }
}

function zoom(range: Range, at: number, factor: number): Range {
  return [at - (at - range[0]) * factor, at + (range[1] - at) * factor];
}

function sizeCanvas(c: HTMLCanvasElement, w: number, h: number, dpr: number): void {
  const pw = Math.max(1, Math.round(w * dpr));
  const ph = Math.max(1, Math.round(h * dpr));
  if (c.width !== pw) c.width = pw;
  if (c.height !== ph) c.height = ph;
  c.style.width = `${w}px`;
  c.style.height = `${h}px`;
}

function fmt(v: number): string {
  return Math.abs(v) >= 1e4 || (Math.abs(v) < 1e-2 && v !== 0) ? v.toExponential(2) : String(Math.round(v * 100) / 100);
}

function button(icon: string, tip: string, onClick: () => void): HTMLButtonElement {
  const b = el("button", "atr-button");
  b.type = "button";
  b.innerHTML = icon;
  b.title = tip;
  b.setAttribute("aria-label", tip.replace(/ \(.*\)$/, ""));
  b.addEventListener("click", (e) => {
    e.stopPropagation();
    onClick();
  });
  return b;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
