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
// Zooming: the wheel zooms x (Shift: y; over an axis: that axis), drag pans (over an axis:
// that axis alone), Shift+drag (or the toolbar's box zoom, z) draws a zoom box. A box
// follows the drag: mostly sideways zooms x alone, mostly up or down y alone, else both
// (the rule plotly.js uses); while it is drawn, the panels it will also zoom show where.
// Fitting y (y, the toolbar) keeps every y group fitted to its data in view as x changes,
// until y is zoomed by hand. u (or Cmd/Ctrl+Z) undoes a zoom, r resets all.
//
// Selecting (s, the toolbar): drag a brush, shaped like a zoom box; it selects the marks it
// meets in every panel (and, with link keys, every mark sharing a key with them); the rest
// fade. Drag the brush to move it; a click or Esc clears it. Python sees it on release.
//
// Opening a panel (double-click, Enter) shows it alone on the whole width ("small
// multiples, large singles", van den Elzen and van Wijk 2013); Page Up and Page Down step to
// the previous and next panel, keeping the zoom. Full screen (f, the toolbar) uses the
// browser's Fullscreen API on the plot's own element.
//
// Exporting (e, the toolbar): an image of the plot as shown, its zoom, selection, opened
// panel and theme, without the toolbar or what the pointer points at. paint() draws it on a
// 2D context: a canvas at PNG_SCALE for a PNG, or SvgContext for an SVG. It is copied, or
// downloaded, or (in a notebook) saved by Python next to the notebook.

import { type FrontState, type PanelView, type Theme, drawBack, drawFront, readTheme } from "./drawing";
import { canCopyImages, canCopySvg, canDownload, copyPng, copySvg, download, fileName, NO_DOWNLOADS, PNG_SCALE, pageMeasure, paintHtml, SvgContext, svgMessage } from "./export";
import { drawMarks } from "./renderers/canvas2d";
import { type Layout, type Rect, layout as computeLayout, panelName } from "./layout";
import { Pager } from "./pager";
import { pageLabels, pageList, panelOrder } from "./pages";
import { createRenderer } from "./renderers/select";
import type { Draw, InstanceSet, Renderer } from "./renderers/renderer";
import { type Brush, type Highlight, type Selection, filled, highlighted, select, selectionColors, selects, toggleLegend } from "./selection";

export type { Highlight } from "./selection";
import { type Hit, type LayerData, type PanelMap, type Scene, buildScene, bufferIds, hitPoint, pick, yExtent } from "./scene";
import { formatValue } from "./ticks";
import { type DataSource, type LegendSpec, type MarkLayerSpec, type Paging, type RendererPreference, type TrellisSpec, isMark } from "./types";

/** Versions of the selected marks' sets: never used twice, as the renderers keep a set's
 * buffers by key and version (a selection cleared and made again under the same key must
 * not find the old one's colours). */
let selectionVersion = 0;

export interface ViewOptions {
  source: DataSource;
  renderer: RendererPreference;
  /** Python's tooltip columns for one instance of a layer (absent: none); `of`: the id of
   * the layer's coords as shown (a layer in detail). */
  tooltip?: (layer: number, instance: number, of: string) => Promise<string[][]>;
  /** The reader opened a panel (its name) or went back to all of them (null). */
  onFocus?: (name: string | null) => void;
  /** The reader drew, moved or cleared the selection (on release). */
  onSelect?: (brush: Brush | null) => void;
  /** The brush as it is dragged (many times a second). */
  onBrushing?: (brush: Brush | null) => void;
  /** The reader cleared a highlight (a click or Escape with no brush of their own). */
  onClear?: () => void;
  /** Save an exported image where Python runs (a notebook's folder); resolves with its
   * path. Absent (a saved page): the Export menu only copies and downloads. */
  onSaveFile?: (name: string, data: Blob) => Promise<string>;
  /** What the plot shows, a moment after it changes: its width and each scale group's
   * range (Python draws the same view in its images). */
  onView?: (view: ShownView) => void;
  /** The reader turned a page, sorted or filtered a paged wrap's panels. */
  onPaging?: (paging: Paging) => void;
  /** Layers in detail were drawn (Python sends a highlight for them again). */
  onDetail?: () => void;
}

/** A layer Python sends in more detail for the view shown (a long line thinned less, dense
 * points as finer cells or points): spec layer `index` is drawn as `layer` while the spec's
 * own has coords `of`. */
export interface DetailLayer {
  index: number;
  of: string;
  layer: MarkLayerSpec;
}

export interface ShownView {
  width: number;
  x: [number, [number, number]][];
  y: [number, [number, number]][];
  /** The panels shown: index, width and height (CSS px). */
  panels: [number, number, number][];
}

/** How long the view stays put before it is reported. */
const VIEW_REPORT_MS = 250;
/** How long the paging stays put before Python hears of it (typing a filter). */
const PAGING_REPORT_MS = 200;

type ExportHow = "copy" | "copy-svg" | "png" | "svg" | "save-png" | "save-svg";


type Range = [number, number];
type Axis = "x" | "y";

interface Drag {
  kind: "pan" | "box" | "brush" | "move" | Axis;
  /** The view (index in views) where it started. */
  view: number;
  x: number;
  y: number;
  xr: Range;
  yr: Range;
  moved: boolean;
}

type Mode = "pan" | "zoom" | "select";

interface Snapshot {
  x: [number, Range][];
  y: [number, Range][];
  fitY: boolean;
}

/** A box zoom along one axis when the other side is this small (px; plotly.js's rule). */
const MIN_DRAG = 8;
const MIN_ZOOM = 20;
/** Wheel events this close together (ms) are one zoom, for undo. */
const WHEEL_GESTURE = 600;
const HISTORY = 100;
/** A fitted y range's padding (a fraction of it each side), as Python pads domains. */
const FIT_PAD = 0.04;

const ZOOM_SPEED = 0.0015;
const HOVER_RADIUS = 10;
/** An opened panel's height (not full screen): the grid's, within these bounds. */
const FOCUS_MIN = 320;
const FOCUS_MAX_SCREEN = 0.85;
/** A box flipping between two widths at most this far apart (px) keeps the narrower: a
 * scrollbar that comes and goes with the plot's height (17 px on Windows). */
const FLIP_MAX = 30;
/** ... and goes back within this time (ms): a flip happens every frame. */
const FLIP_MS = 100;

const ICONS = {
  back: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>',
  prev: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 4 6 8l4 4" /></svg>',
  next: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4" /></svg>',
  reset: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8a5 5 0 1 0 1.5-3.5" /><path d="M3 2.5V5h2.5" /></svg>',
  expand: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10" /></svg>',
  collapse: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 2.5V6H2.5M13.5 6H10V2.5M10 13.5V10h3.5M2.5 10H6v3.5" /></svg>',
  box: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="2.5" width="8" height="8" stroke-dasharray="2 1.6" /><path d="m10.5 10.5 3 3" /></svg>',
  select: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="4.5" width="11" height="7" rx="1" stroke-dasharray="2 1.6" /><path d="M6 8h4" /></svg>',
  export: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v7.5M5 7l3 3 3-3M2.5 10.5v3h11v-3" /></svg>',
  fitY: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2.5h10M3 13.5h10M8 5v6M6 7l2-2 2 2M6 9l2 2 2-2" /></svg>',
};

export class TrellisView {
  readonly root: HTMLDivElement;
  private readonly header: HTMLDivElement;
  private readonly heading: HTMLDivElement;
  private readonly toolbar: HTMLDivElement;
  private readonly backButton: HTMLButtonElement;
  private readonly resetButton: HTMLButtonElement;
  private readonly boxButton: HTMLButtonElement;
  private readonly selectButton: HTMLButtonElement;
  private readonly fitButton: HTMLButtonElement;
  private readonly fullButton: HTMLButtonElement;
  private readonly exportButton: HTMLButtonElement;
  /** The Export menu: copy, download or save an image of the plot (e). */
  private readonly exportMenu: HTMLDivElement;
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
  /** Layers drawn in more detail than the spec's (Python, for the view shown), by index. */
  private readonly detail = new Map<number, MarkLayerSpec>();
  private detailQueue: Promise<void> = Promise.resolve();
  private lay: Layout | null = null;
  private theme: Theme;
  private xView = new Map<number, Range>();
  private yView = new Map<number, Range>();
  private views: PanelView[] = [];
  private frameRequested = false;
  private frameId = 0;
  private front_: FrontState = { crossX: null, crossGroup: null, hover: null, hoverPanel: null, box: null, ghosts: [], brushes: [], texts: [] };
  private drag: Drag | null = null;
  /** What plain drag does: pan, draw a zoom box, or draw a brush. Shift+drag: a zoom box
   * (in zoom mode: pan). */
  private mode: Mode = "pan";
  /** The selection: a brush (axis units), the marks it selects, and the sets drawing it. */
  private brush: Brush | null = null;
  private selection: Selection | null = null;
  private selectionSets: ({ dim: InstanceSet; hi: InstanceSet } | null)[] = [];
  /** A linked plot's selection, shown when there is no brush here. */
  private highlight: Highlight | null = null;
  /** The category legends' entries (spec.legends index, level, element). */
  private legendItems: { index: number; level: number; el: HTMLElement }[] = [];
  /** Every y group follows its data in view as x changes. */
  private fitY = false;
  private needFit = false;
  private history: Snapshot[] = [];
  private lastWheel = 0;
  private hoverKey = "";
  /** The brush as a move started. */
  private dragBrush: Brush | null = null;
  private needSelect = false;
  private tipRequest = 0;
  /** The panel under the pointer (index in spec.panels), for Enter. */
  private pointerPanel: number | null = null;
  /** The opened panel (index in spec.panels), or null: all of them. */
  private focused: number | null = null;
  /** A panel to open once the spec is in (the name Python asked for). */
  private pendingFocus: string | null = null;
  private gridHeight = 0;
  private readonly pager: Pager;
  /** A paged wrap's page, sort and filters, and the panels they show, in order (null: it
   * does not page). */
  private paging: Paging = {};
  private order: number[] | null = null;
  /** The panels of each page, in order (null: it does not page). */
  private pageList: number[][] | null = null;
  private pagingTimer: ReturnType<typeof setTimeout> | undefined;
  /** The notice says the panels shown are loading. */
  private loading = false;
  private readonly empty: HTMLDivElement;
  private noticeTimer: ReturnType<typeof setTimeout> | undefined;
  private viewTimer: ReturnType<typeof setTimeout> | undefined;
  /** The view last reported (as JSON), so an unchanged one is not sent again. */
  private reportedView = "";
  private readonly resizeObserver: ResizeObserver;
  private readonly themeObserver: MutationObserver;
  private readonly abort = new AbortController();
  private width = 0;
  /** The width laid out before `width`, and two widths the plot's box flips between (the
   * narrower first), while it does: see steadyWidth. */
  private widthBefore = 0;
  private widthAt = 0;
  private flip: [number, number] | null = null;
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
    this.boxButton = button(ICONS.box, "Box zoom: drag a box (z; Shift+drag at any time)", () => this.setMode(this.mode === "zoom" ? "pan" : "zoom"));
    this.selectButton = button(ICONS.select, "Select: drag a brush (s)", () => this.setMode(this.mode === "select" ? "pan" : "select"));
    this.selectButton.setAttribute("aria-pressed", "false");
    this.fitButton = button(ICONS.fitY, "Fit y to the data in view (y)", () => this.setFitY(!this.fitY, true));
    for (const b of [this.boxButton, this.fitButton]) b.setAttribute("aria-pressed", "false");
    this.fullButton = button(ICONS.expand, "Full screen (f)", () => this.toggleFullscreen());
    this.fullButton.hidden = !document.fullscreenEnabled; // in some frames (and iPhones): none
    this.exportButton = button(ICONS.export, "Export an image: copy or download a PNG or SVG (e)", () => this.toggleExport());
    this.exportButton.setAttribute("aria-haspopup", "menu");
    this.exportButton.setAttribute("aria-expanded", "false");
    this.exportMenu = el("div", "atr-export");
    this.exportMenu.setAttribute("role", "menu");
    this.exportMenu.hidden = true;
    this.toolbar.append(this.backButton, this.selectButton, this.boxButton, this.fitButton, this.resetButton, this.exportButton, this.fullButton);
    this.header.append(this.heading, this.toolbar);
    this.pager = new Pager((paging) => this.setPaging(paging, true));
    this.pager.el.hidden = true;
    this.legend = el("div", "atr-legend");
    this.stage = el("div", "atr-stage");
    this.back = el("canvas", "atr-canvas");
    this.front = el("canvas", "atr-canvas atr-front");
    this.tip = el("div", "atr-tip");
    this.status = el("div", "atr-status");
    this.notice = el("div", "atr-notice");
    this.notice.hidden = true;
    this.badge = el("div", "atr-badge");
    this.empty = el("div", "atr-empty", "No panel matches the filters");
    this.empty.hidden = true;
    this.stage.append(this.back, this.front, this.tip, this.status, this.notice, this.empty);
    this.root.append(this.header, this.pager.el, this.stage, this.legend, this.badge, this.exportMenu);
    host.append(this.root);
    this.theme = readTheme(this.root);
    this.rendererReady = this.makeRenderer(opts.renderer);
    this.resizeObserver = new ResizeObserver(() => this.relayout());
    this.resizeObserver.observe(this.root);
    // the host's theme (light or dark) changes: read the colours again (data-md-color-scheme:
    // the documentation's light/dark toggle)
    this.themeObserver = new MutationObserver(() => {
      this.theme = readTheme(this.root);
      this.request();
    });
    const themeAttributes = ["class", "data-theme", "data-jp-theme-light", "data-md-color-scheme"];
    for (const target of [document.documentElement, document.body]) {
      this.themeObserver.observe(target, { attributes: true, attributeFilter: themeAttributes });
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
    this.reportedView = ""; // a new spec: report the view again
    await Promise.all([this.opts.source.ensure(bufferIds(spec)), this.rendererReady]);
    if (version !== this.specVersion || this.destroyed) return;
    const old = this.spec;
    const openName = this.pendingFocus ?? (old && this.focused !== null ? panelName(old, this.focused) : null);
    this.spec = spec;
    this.detail.clear(); // Python sends them again for the view shown
    this.scene = buildScene(spec, this.opts.source);
    this.renderer?.retain(new Set(this.scene.layers.map((l) => l.set.key)));
    // keep the zoom when only the layers changed (same domains)
    const same = old !== null && JSON.stringify(old.panels) === JSON.stringify(spec.panels);
    if (!same) {
      this.resetViews();
      this.history = [];
      this.setFitY(spec.fit_y === true, false);
    }
    this.fitButton.hidden = spec.y.kind === "band";
    this.selectionSets = [];
    this.needSelect = false;
    this.computeSelection();
    // the opened panel stays open when the new spec still has it
    this.pendingFocus = null;
    this.focused = this.indexOf(openName);
    this.computeOrder();
    this.renderLegend(spec.legends);
    this.setStatus(null);
    this.updateHeader();
    this.relayout();
    this.updateLoading();
  }

  /** Layers in more detail for the view shown (Python): drawn instead of the spec's, in the
   * order sent, each once its buffers are here. One whose buffers Python no longer has was
   * replaced by a later message. */
  setDetail(layers: DetailLayer[]): Promise<void> {
    this.detailQueue = this.detailQueue.then(() => this.applyDetail(layers)).catch((err) => console.warn("[anytrellis] detail:", err));
    return this.detailQueue;
  }

  private async applyDetail(layers: DetailLayer[]): Promise<void> {
    const spec = this.spec;
    const ofSpec = (d: DetailLayer): boolean => {
      const l = spec?.layers[d.index];
      return !!l && (isMark(l) || l.type === "text") && l.coords.id === d.of;
    };
    const fits = layers.filter(ofSpec);
    if (!spec || !fits.length) return;
    const ids = (d: DetailLayer): string[] => bufferIds({ ...spec, layers: [d.layer] });
    await this.opts.source.ensure(fits.flatMap(ids));
    if (this.spec !== spec || this.destroyed) return;
    const source = this.opts.source;
    const here = fits.filter((d) => ids(d).every((id) => source.has(id)));
    if (!here.length) return;
    for (const d of here) this.detail.set(d.index, d.layer);
    this.scene = buildScene(this.shownSpec(spec), source, this.scene);
    this.renderer?.retain(new Set(this.scene.layers.map((l) => l.set.key)));
    this.selectionSets = [];
    this.needSelect = false;
    this.computeSelection();
    this.clearHover();
    this.request();
    this.updateLoading();
    this.opts.onDetail?.();
  }

  /** "Loading" while a panel shown has data Python has not sent yet (a paged plot turned
   * to a page further than the next or the previous one). */
  private updateLoading(): void {
    const spec = this.spec;
    if (!spec) return;
    const shown = this.focused !== null ? [this.focused] : (this.pagePanels() ?? []);
    const layers = this.shownSpec(spec).layers;
    const missing = shown.some((p) => layers.some((l) => "panels" in l && l.panels && !l.panels.includes(p)));
    if (missing) {
      this.loading = true;
      this.notice.textContent = "Loading the panels…";
      this.notice.hidden = false;
      clearTimeout(this.noticeTimer);
    } else if (this.loading) {
      this.loading = false;
      this.notice.hidden = true;
    }
  }

  /** The spec as drawn: with the layers in detail. */
  private shownSpec(spec: TrellisSpec): TrellisSpec {
    if (!this.detail.size) return spec;
    return { ...spec, layers: spec.layers.map((l, i) => this.detail.get(i) ?? l) };
  }

  /** The buffers the plot draws now. */
  shownBufferIds(): string[] {
    return this.spec ? bufferIds(this.shownSpec(this.spec)) : [];
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

  // ---- pages ------------------------------------------------------------------------------

  /** Show a page, sort and filters (Python: show_page, sort_panels, filter_panels; or the
   * reader, `user`: tell Python). */
  setPaging(paging: Paging | null, user = false): void {
    const before = this.paging;
    this.paging = { ...(paging ?? {}) };
    if (!this.spec) return;
    this.computeOrder();
    // a page turned goes to Python at once (its panels' data comes back); a filter typed,
    // once it stays put a moment
    const typed = before.name !== this.paging.name || JSON.stringify(before.where ?? {}) !== JSON.stringify(this.paging.where ?? {});
    if (user) this.reportPaging(typed ? PAGING_REPORT_MS : 0);
    this.clearHover();
    this.updateHeader();
    this.relayout();
    this.updateLoading();
  }

  /** Tell Python the paging after `ms` (typing a filter: once it has stayed put a moment). */
  private reportPaging(ms: number): void {
    clearTimeout(this.pagingTimer);
    const sent = { ...this.paging };
    this.pagingTimer = setTimeout(() => !this.destroyed && this.opts.onPaging?.(sent), ms);
  }

  /** The panels the filters keep, sorted; the page within their pages. */
  private computeOrder(): void {
    const spec = this.spec;
    const pages = spec?.pages;
    if (!spec || !pages) {
      this.order = null;
      this.pageList = null;
      return;
    }
    const names = spec.panels.map((_, i) => panelName(spec, i));
    this.order = panelOrder(pages.stats, names, this.paging);
    this.pageList = pageList(this.order, pages);
    const last = this.pageList.length - 1;
    this.paging.page = Math.max(0, Math.min(this.paging.page ?? 0, last));
  }

  /** The panels on the page shown (null: it does not page). */
  private pagePanels(): number[] | null {
    if (!this.spec?.pages || !this.pageList) return null;
    return this.pageList[this.paging.page ?? 0] ?? [];
  }

  /** The previous or next page (Page Up, Page Down). */
  private turnPage(step: number): void {
    if (!this.spec?.pages || !this.pageList) return;
    const count = this.pageList.length;
    const next = (this.paging.page ?? 0) + step;
    if (next < 0 || next >= count) {
      this.notify(next < 0 ? "This is the first page" : "This is the last page");
      return;
    }
    this.setPaging({ ...this.paging, page: next }, true);
  }

  /** A paged wrap's strips: each panel's value of the statistic sorted by, at the right. */
  private noteSorted(lay: Layout): void {
    const stat = this.spec?.pages?.stats.find((s) => s.name === this.paging.sort);
    if (!stat) return;
    for (const box of lay.panels) box.note = stat.text[box.index] || undefined;
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
  private notify(text: string, ms = 1600): void {
    this.notice.textContent = text;
    this.notice.hidden = false;
    clearTimeout(this.noticeTimer);
    this.noticeTimer = setTimeout(() => (this.notice.hidden = true), ms);
  }

  private resetViews(): void {
    if (!this.spec) return;
    for (const p of this.spec.panels) {
      this.xView.set(p.xg, [p.x[0], p.x[1]]);
      this.yView.set(p.yg, [p.y[0], p.y[1]]);
    }
  }

  private resetZoom(): void {
    this.remember();
    this.resetViews();
    this.setFitY(this.spec?.fit_y === true, false);
    this.hideTip();
    this.request();
  }

  // ---- zooming --------------------------------------------------------------------------

  private zoomState(): Snapshot {
    return { x: [...this.xView].map(([g, r]) => [g, [...r]]), y: [...this.yView].map(([g, r]) => [g, [...r]]), fitY: this.fitY };
  }

  /** Keep the zoom as it is now, for undo. */
  private remember(): void {
    this.history.push(this.zoomState());
    if (this.history.length > HISTORY) this.history.shift();
  }

  private undo(): void {
    const last = this.history.pop();
    if (!last) {
      this.notify("Nothing to undo");
      return;
    }
    this.xView = new Map(last.x);
    this.yView = new Map(last.y);
    this.setFitY(last.fitY, false);
    this.needFit = false;
    this.hideTip();
    this.request();
  }

  /** x of group `xg` changed: y follows when it is fitted. */
  private setX(xg: number, range: Range): void {
    this.xView.set(xg, range);
    if (this.fitY) this.needFit = true;
  }

  /** y zoomed or panned by hand: it is no longer fitted. */
  private setY(yg: number, range: Range): void {
    this.yView.set(yg, range);
    if (this.fitY) {
      this.setFitY(false, false);
      this.notify("y zoomed by hand: no longer fitted (y fits again)");
    }
  }

  private setFitY(on: boolean, user: boolean): void {
    if (on && this.spec?.y.kind === "band") on = false;
    if (user && on !== this.fitY) this.remember();
    this.fitY = on;
    this.fitButton.setAttribute("aria-pressed", String(on));
    this.root.classList.toggle("atr-fit-y", on);
    if (on) this.needFit = true;
    if (user) {
      this.notify(on ? "y follows the data in view" : "y stays as it is");
      this.request();
    }
  }

  private setMode(mode: Mode): void {
    this.mode = mode;
    this.boxButton.setAttribute("aria-pressed", String(mode === "zoom"));
    this.selectButton.setAttribute("aria-pressed", String(mode === "select"));
    this.notify(
      mode === "zoom"
        ? "Drag a box to zoom (z or Shift+drag: pan)"
        : mode === "select"
          ? "Drag to select (s: back to panning; Shift+drag: box zoom)"
          : "Drag pans (Shift+drag: box zoom)",
    );
  }

  // ---- selecting ------------------------------------------------------------------------

  /** The selection is this brush (null: none). `user`: the reader made it (tell Python). */
  private setBrush(brush: Brush | null, user: boolean): void {
    this.brush = selects(brush) ? brush : null;
    this.updateLegend();
    this.needSelect = true; // once per frame: a brush moves faster than frames come
    if (user) this.opts.onSelect?.(this.brush);
    this.request();
  }

  /** The selection from Python (Trellis.select), or none. */
  setSelection(brush: Brush | null): void {
    const same = JSON.stringify(brush ?? null) === JSON.stringify(this.brush);
    if (!same) this.setBrush(brush, false);
  }

  /** What a linked plot's selection highlights here, or none. */
  setHighlight(highlight: Highlight | null): void {
    this.highlight = highlight;
    this.needSelect = true;
    this.request();
  }

  get selected(): { selected: number; total: number } | null {
    this.settleSelection();
    return this.selection ? { selected: this.selection.selected, total: this.selection.total } : null;
  }

  private settleSelection(): void {
    if (!this.needSelect) return;
    this.needSelect = false;
    this.computeSelection();
  }

  private computeSelection(): void {
    const scene = this.scene;
    const shared = !this.brush && this.highlight ? highlighted(scene, this.highlight) : null;
    if (!scene || (!this.brush && !shared)) {
      this.selection = null;
      this.selectionSets = []; // drawn as they are again, not faded
      return;
    }
    this.selection = shared?.selection ?? select(scene, this.brush!);
    const old = this.selectionSets;
    this.selectionSets = scene.layers.map((layer, i) => {
      const mask = this.selection!.masks[i];
      if (!mask) return null;
      const prev = old[i]?.dim.key === `${layer.set.key}:dim` ? old[i] : null;
      const { dim, hi } = selectionColors(layer, mask, prev?.dim.colors ?? null);
      // a bar's selected share (a linked plot's highlight): the faded bar whole, the share
      // filled from its base on top
      const fraction = shared?.fractions[i];
      const coords = fraction ? filled(layer.set.coords, fraction) : layer.set.coords;
      return {
        dim: prev?.dim ?? { key: `${layer.set.key}:dim`, version: layer.set.version, count: layer.set.count, coords: layer.set.coords, colors: dim, base: layer.set.base },
        hi: { key: `${layer.set.key}:hi`, version: ++selectionVersion, count: layer.set.count, coords, colors: hi, base: layer.set.base },
      };
    });
  }

  /** The brush where it shows in view `v` (px, in the panel), or null. */
  private brushRect(v: PanelView): Rect | null {
    const b = this.brush;
    if (!b || (!b.x && !b.y) || (b.panel !== null && b.panel !== undefined && b.panel !== v.panel)) return null;
    const r = v.rect;
    let x0 = r.x;
    let x1 = r.x + r.w;
    let y0 = r.y;
    let y1 = r.y + r.h;
    if (b.x) {
      const a = v.map.ox + b.x[0] * v.map.sx;
      const c = v.map.ox + b.x[1] * v.map.sx;
      x0 = Math.max(x0, Math.min(a, c));
      x1 = Math.min(x1, Math.max(a, c));
    }
    if (b.y) {
      const a = v.map.oy + b.y[0] * v.map.sy;
      const c = v.map.oy + b.y[1] * v.map.sy;
      y0 = Math.max(y0, Math.min(a, c));
      y1 = Math.min(y1, Math.max(a, c));
    }
    return x1 > x0 && y1 > y0 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
  }

  /** A brush from a drag in views[d.view], shaped as a zoom box would be. */
  private brushOf(d: Drag, x: number, y: number): Brush | null {
    const b = this.boxOf(d, x, y);
    if (!b) return null;
    const v = this.views[d.view];
    const r = b.rect;
    // linked: in its own panel (the link spreads it); else the same range in all of them
    const linked = this.scene?.layers.some((l) => l.link) ?? false;
    return {
      x: b.along === "y" ? null : [(r.x - v.map.ox) / v.map.sx, (r.x + r.w - v.map.ox) / v.map.sx],
      y: b.along === "x" ? null : [(r.y + r.h - v.map.oy) / v.map.sy, (r.y - v.map.oy) / v.map.sy],
      panel: linked ? v.panel : null,
      legend: this.brush?.legend ?? null, // chosen legend entries: only their colours
    };
  }

  private selectedNotice(): void {
    this.settleSelection();
    const s = this.selection;
    if (s) this.notify(`${s.selected.toLocaleString()} of ${s.total.toLocaleString()} marks selected`);
  }

  /** Each y group fitted to its panels' data where their x is now. */
  private fitGroups(): void {
    const spec = this.spec;
    const scene = this.scene;
    if (!spec || !scene || spec.y.kind === "band") return;
    const ext = new Map<number, { lo: number; hi: number; baseLo: boolean; baseHi: boolean }>();
    spec.panels.forEach((p, i) => {
      const xr = this.xView.get(p.xg) ?? p.x;
      const e = yExtent(scene, i, Math.min(xr[0], xr[1]), Math.max(xr[0], xr[1]));
      if (!e) return;
      const g = ext.get(p.yg);
      if (!g) {
        ext.set(p.yg, { ...e });
        return;
      }
      if (e.lo < g.lo || (e.lo === g.lo && e.baseLo)) [g.lo, g.baseLo] = [e.lo, e.baseLo || (e.lo === g.lo && g.baseLo)];
      if (e.hi > g.hi || (e.hi === g.hi && e.baseHi)) [g.hi, g.baseHi] = [e.hi, e.baseHi || (e.hi === g.hi && g.baseHi)];
    });
    for (const [g, e] of ext) {
      let { lo, hi } = e;
      const span = hi - lo;
      if (span > 0) {
        if (!e.baseLo) lo -= FIT_PAD * span;
        if (!e.baseHi) hi += FIT_PAD * span;
      } else {
        const d = Math.abs(lo) * 0.05 || 1;
        lo -= d;
        hi += d;
      }
      this.yView.set(g, [lo, hi]);
    }
  }

  /** The axis (of views[view]) under a point, or null. */
  private axisAt(x: number, y: number): { view: number; axis: Axis } | null {
    const boxes = this.lay?.panels ?? [];
    const inside = (r: { x: number; y: number; w: number; h: number } | null): boolean => r !== null && x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h;
    for (let i = 0; i < boxes.length && i < this.views.length; i++) {
      if (inside(boxes[i].xAxis)) return { view: i, axis: "x" };
      if (inside(boxes[i].yAxis)) return { view: i, axis: "y" };
    }
    return null;
  }

  /** The zoom box of a drag from (d.x, d.y) to (x, y), kept in its panel: along x, y or
   * both, by its shape; null while too small. */
  private boxOf(d: Drag, x: number, y: number): { rect: Rect; along: "x" | "y" | "xy" } | null {
    const r = this.views[d.view].rect;
    const cx = Math.min(Math.max(x, r.x), r.x + r.w);
    const cy = Math.min(Math.max(y, r.y), r.y + r.h);
    const dx = Math.abs(cx - d.x);
    const dy = Math.abs(cy - d.y);
    const left = Math.min(cx, d.x);
    const top = Math.min(cy, d.y);
    if (dy < Math.min(Math.max(dx * 0.6, MIN_DRAG), MIN_ZOOM)) {
      if (dx < MIN_DRAG) return null;
      return { rect: { x: left, y: r.y, w: dx, h: r.h }, along: "x" };
    }
    if (dx < Math.min(dy * 0.6, MIN_ZOOM)) return { rect: { x: r.x, y: top, w: r.w, h: dy }, along: "y" };
    return { rect: { x: left, y: top, w: dx, h: dy }, along: "xy" };
  }

  /** Where a box in views[vi] also zooms the other panels shown: the same x range in the
   * panels of its x group, the same y range in those of its y group. */
  private ghostsOf(vi: number, rect: Rect, along: "x" | "y" | "xy"): Rect[] {
    const spec = this.spec!;
    const src = this.views[vi];
    const sp = spec.panels[src.panel];
    const [x0, x1] = [(rect.x - src.map.ox) / src.map.sx, (rect.x + rect.w - src.map.ox) / src.map.sx];
    const [y0, y1] = [(rect.y + rect.h - src.map.oy) / src.map.sy, (rect.y - src.map.oy) / src.map.sy];
    const out: Rect[] = [];
    this.views.forEach((v, i) => {
      if (i === vi) return;
      const p = spec.panels[v.panel];
      const sameX = along !== "y" && p.xg === sp.xg;
      const sameY = along !== "x" && p.yg === sp.yg;
      if (!sameX && !sameY) return;
      const r = v.rect;
      const gx = sameX ? [v.map.ox + x0 * v.map.sx, v.map.ox + x1 * v.map.sx] : [r.x, r.x + r.w];
      const gy = sameY ? [v.map.oy + y1 * v.map.sy, v.map.oy + y0 * v.map.sy] : [r.y, r.y + r.h];
      out.push({ x: gx[0], y: gy[0], w: gx[1] - gx[0], h: gy[1] - gy[0] });
    });
    return out;
  }

  private applyBox(d: Drag, x: number, y: number): void {
    const b = this.boxOf(d, x, y);
    if (!b || !this.spec) return;
    const v = this.views[d.view];
    const p = this.spec.panels[v.panel];
    const r = b.rect;
    this.remember();
    if (b.along !== "y") this.setX(p.xg, [(r.x - v.map.ox) / v.map.sx, (r.x + r.w - v.map.ox) / v.map.sx]);
    if (b.along !== "x") this.setY(p.yg, [(r.y + r.h - v.map.oy) / v.map.sy, (r.y - v.map.oy) / v.map.sy]);
  }

  /** One axis of a group back to its full domain (double-click on the axis). */
  private resetAxis(vi: number, axis: Axis): void {
    const v = this.views[vi];
    const p = this.spec!.panels[v.panel];
    this.remember();
    if (axis === "x") this.setX(p.xg, [p.x[0], p.x[1]]);
    else this.setY(p.yg, [p.y[0], p.y[1]]);
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
    const was = this.focused;
    this.focused = index;
    // back to a paged wrap: the page that has the panel that was open
    const page = index === null && was !== null && this.pageList ? this.pageList.findIndex((p) => p.includes(was)) : -1;
    if (page >= 0) {
      if (page !== (this.paging.page ?? 0)) {
        this.paging = { ...this.paging, page };
        this.reportPaging(0);
      }
    }
    this.drag = null;
    this.clearHover();
    this.updateHeader();
    this.relayout();
    this.updateLoading();
    if (user) {
      this.opts.onFocus?.(index === null ? null : panelName(this.spec, index));
      // a grid taller than the window: the opened panel (or the plot again) into view
      if (!this.isFullscreen()) this.root.scrollIntoView?.({ block: "nearest" });
    }
  }

  /** The panels an opened one steps through: a paged wrap's, as sorted and filtered (when
   * they hold the opened one); all of them otherwise. */
  private sequence(): number[] {
    if (this.order && this.focused !== null && this.order.includes(this.focused)) return this.order;
    return this.spec ? this.spec.panels.map((_, i) => i) : [];
  }

  /** The previous or next panel, opened at the same zoom (Page Up, Page Down, ‹ ›). */
  private stepPanel(step: number): void {
    if (!this.spec || this.focused === null) return;
    const seq = this.sequence();
    const at = seq.indexOf(this.focused);
    const next = at + step;
    if (next < 0 || next >= seq.length) {
      this.notify(`${panelName(this.spec, this.focused)} is the ${next < 0 ? "first" : "last"} panel`);
      return;
    }
    this.setFocus(seq[next], true);
    this.notify(`${panelName(this.spec, seq[next])} · ${next + 1} of ${seq.length}`);
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
    const paged = !open && !!spec?.pages && this.order !== null;
    this.pager.el.hidden = !paged;
    if (paged) {
      const pages = spec!.pages!;
      const list = this.pageList ?? [[]];
      this.pager.update(pages, this.paging, this.order!.length, spec!.panels.length, list.length, pageLabels(list, pages));
    } else this.pager.toggleMenu(false);
    this.root.classList.toggle("atr-open", open);
    if (!spec || this.focused === null) return;
    const crumb = el("span", "atr-crumb");
    const all = el("button", "atr-link", "All panels");
    all.type = "button";
    all.title = "Back to all panels (Backspace, double-click)";
    all.addEventListener("click", () => this.setFocus(null, true));
    const prev = button(ICONS.prev, "Previous panel (Page Up)", () => this.stepPanel(-1));
    const next = button(ICONS.next, "Next panel (Page Down)", () => this.stepPanel(1));
    const seq = this.sequence();
    prev.disabled = seq[0] === this.focused;
    next.disabled = seq[seq.length - 1] === this.focused;
    crumb.append(all, el("span", "atr-sep", "›"), prev, el("span", "atr-panel-name", panelName(spec, this.focused)), next);
    this.heading.append(crumb);
  }

  // ---- layout and drawing -------------------------------------------------------------------

  private relayout(): void {
    if (!this.spec) return;
    const box = Math.floor(this.stage.clientWidth || this.root.clientWidth);
    if (box <= 0) return;
    const width = this.steadyWidth(box);
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
      const page = this.pagePanels();
      this.lay = computeLayout(this.spec, { ...base, height, page });
      const spare = this.spec.legend_position === "bottom" ? null : this.lay.spare;
      if (!this.placeLegend(spare) && height !== null) {
        // under the plot after all: full screen leaves it room
        this.lay = computeLayout(this.spec, { ...base, height: height - this.legend.offsetHeight, page });
      }
      this.gridHeight = this.lay.height;
      this.noteSorted(this.lay);
      this.empty.hidden = page === null || page.length > 0;
    } else {
      this.empty.hidden = true;
      this.placeLegend(null);
      if (height !== null) height -= this.legend.offsetHeight;
      if (height === null) this.gridHeight = computeLayout(this.spec, base).height;
      const h = height ?? Math.max(FOCUS_MIN, Math.min(this.gridHeight, window.innerHeight * FOCUS_MAX_SCREEN));
      this.lay = computeLayout(this.spec, { ...base, height: h, focused: this.focused });
    }
    const h = this.lay.height;
    this.stage.style.height = `${h}px`;
    let resized = false;
    for (const c of [this.back, this.front]) resized = sizeCanvas(c, width, h, this.dpr) || resized;
    this.renderer?.resize(width, h, this.dpr);
    if (this.renderer) {
      this.renderer.canvas.style.width = `${width}px`;
      this.renderer.canvas.style.height = `${h}px`;
    }
    if (!resized) {
      this.request();
      return;
    }
    // a resized canvas is cleared: draw now, or the browser paints it blank (a resize
    // observer runs after the frame's animation frame callbacks)
    if (this.frameRequested) {
      cancelAnimationFrame(this.frameId);
      this.frameRequested = false;
    }
    this.draw();
  }

  /** The width to lay out at in a box `box` px wide. A plot whose height follows its width
   * can be tall enough for the page to need a scrollbar at one width and short enough not to
   * 17 px narrower: laid out at each in turn, its box would flip between them every frame,
   * each relayout clearing the canvases. Back at the width before the last at once, close
   * to it, the plot keeps the narrower of the two while its box stays at either. */
  private steadyWidth(box: number): number {
    if (this.flip && (box === this.flip[0] || box === this.flip[1])) return this.flip[0];
    this.flip = null;
    if (box === this.width) return box;
    const now = performance.now();
    if (box === this.widthBefore && Math.abs(box - this.width) <= FLIP_MAX && now - this.widthAt < FLIP_MS) {
      this.flip = [Math.min(box, this.width), Math.max(box, this.width)];
      return this.flip[0];
    }
    this.widthBefore = this.width;
    this.widthAt = now;
    return box;
  }

  private request(): void {
    if (this.frameRequested || this.destroyed) return;
    this.frameRequested = true;
    this.frameId = requestAnimationFrame(() => {
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
    if (this.needFit) {
      this.needFit = false;
      this.fitGroups();
    }
    this.settleSelection();
    const views = this.panelViews();
    this.views = views;
    const back = this.back.getContext("2d")!;
    back.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    back.clearRect(0, 0, this.width, this.lay.height);
    drawBack(back, this.spec, views, this.theme);
    if (this.renderer) this.renderer.render({ draws: this.markDraws(views) });
    const front = this.front.getContext("2d")!;
    front.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    front.clearRect(0, 0, this.width, this.lay.height);
    this.front_.texts = this.scene.texts;
    this.front_.brushes = this.brush ? (views.map((v) => this.brushRect(v)).filter(Boolean) as Rect[]) : [];
    drawFront(front, this.spec, this.lay, views, this.theme, this.front_);
    this.reportView();
  }

  /** Tell Python what the plot shows, once it has stayed put a moment. */
  private reportView(): void {
    if (!this.opts.onView || !this.spec) return;
    const ranges = (views: Map<number, Range>): [number, Range][] => [...views].map(([g, r]) => [g, [r[0], r[1]]]);
    const panels = this.views.map((v): [number, number, number] => [v.panel, Math.round(v.rect.w), Math.round(v.rect.h)]);
    const view: ShownView = { width: this.width, x: ranges(this.xView), y: ranges(this.yView), panels };
    const json = JSON.stringify(view);
    if (json === this.reportedView) return;
    clearTimeout(this.viewTimer);
    this.viewTimer = setTimeout(() => {
      if (this.destroyed) return;
      this.reportedView = json;
      this.opts.onView?.(view);
    }, VIEW_REPORT_MS);
  }

  /** The marks of every layer in `views`, for a renderer: faded under a selection, the
   * selected marks again on top. */
  private markDraws(views: PanelView[]): Draw[] {
    const scene = this.scene!;
    const draws: Draw[] = [];
    // with a selection: every layer faded, then the selected marks on top
    const passes: { layer: LayerData; set: InstanceSet }[] = [];
    scene.layers.forEach((layer, i) => passes.push({ layer, set: this.selectionSets[i]?.dim ?? layer.set }));
    if (this.selection) scene.layers.forEach((layer, i) => this.selectionSets[i] && passes.push({ layer, set: this.selectionSets[i]!.hi }));
    for (const { layer, set } of passes) {
      for (const v of views) {
        const p = v.panel;
        const start = layer.starts[p];
        const count = layer.starts[p + 1] - start;
        if (!count) continue;
        const { map, rect } = v;
        draws.push({
          set,
          start,
          count,
          clip: rect,
          sx: map.sx,
          ox: map.ox + scene.baseX[p] * map.sx,
          sy: map.sy,
          oy: map.oy + scene.baseY[p] * map.sy,
          kind: layer.kind,
          halfWidth: layer.halfWidth,
          opacity: layer.spec.opacity,
        });
      }
    }
    return draws;
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
    // a click outside the Export menu (or the filters) closes it (its path, not its target: in a shadow root,
    // marimo's, the document sees the target as the shadow's host)
    document.addEventListener(
      "pointerdown",
      (e) => {
        const path = e.composedPath();
        if (!this.exportMenu.hidden && !path.includes(this.exportMenu) && !path.includes(this.exportButton)) this.toggleExport(false);
        if (this.pager.menuOpen && !path.includes(this.pager.el)) this.pager.toggleMenu(false);
      },
      { signal, capture: true },
    );
    stage.addEventListener(
      "wheel",
      (e) => {
        if (!this.spec || !this.isActive()) return;
        const [x, y] = this.local(e);
        const onAxis = this.axisAt(x, y);
        const vi = onAxis ? onAxis.view : this.viewAt(x, y);
        if (vi < 0) return;
        e.preventDefault();
        const scale = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
        const dx = e.deltaX * scale;
        const dy = e.deltaY * scale;
        const v = this.views[vi];
        const panel = this.spec.panels[v.panel];
        if (e.timeStamp - this.lastWheel > WHEEL_GESTURE) this.remember();
        this.lastWheel = e.timeStamp;
        // a trackpad's sideways swipe pans x; macOS turns Shift+wheel into a sideways scroll
        const sideways = Math.abs(dx) > Math.abs(dy);
        const axis: Axis = onAxis ? onAxis.axis : e.shiftKey ? "y" : "x";
        if (sideways && !e.shiftKey && !onAxis) {
          const shift = dx / v.map.sx;
          this.setX(panel.xg, [v.x[0] + shift, v.x[1] + shift]);
        } else {
          const factor = Math.exp((sideways ? dx : dy) * ZOOM_SPEED);
          if (axis === "y") this.setY(panel.yg, zoom(v.y, (y - v.map.oy) / v.map.sy, factor));
          else this.setX(panel.xg, zoom(v.x, (x - v.map.ox) / v.map.sx, factor));
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
        const onAxis = this.axisAt(x, y);
        const vi = onAxis ? onAxis.view : this.viewAt(x, y);
        if (vi < 0) return;
        const v = this.views[vi];
        let kind: Drag["kind"];
        if (onAxis) kind = onAxis.axis;
        else if (this.mode === "zoom") kind = e.shiftKey ? "pan" : "box";
        else if (e.shiftKey) kind = "box";
        else if (this.mode === "select") {
          const br = this.brushRect(v);
          kind = br && x >= br.x && x <= br.x + br.w && y >= br.y && y <= br.y + br.h ? "move" : "brush";
          this.dragBrush = this.brush;
        } else kind = "pan";
        this.drag = { kind, view: vi, x, y, xr: [...v.x], yr: [...v.y], moved: false };
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
          if (!d.moved && d.kind !== "box" && d.kind !== "brush" && d.kind !== "move") this.remember();
          d.moved = true;
          this.hideTip();
          if (d.kind === "box") {
            const b = this.boxOf(d, x, y);
            this.front_.box = b?.rect ?? null;
            this.front_.ghosts = b ? this.ghostsOf(d.view, b.rect, b.along) : [];
            this.front_.crossX = null;
            this.front_.hover = null;
            this.request();
            return;
          }
          if (d.kind === "brush") {
            this.front_.hover = null;
            this.setBrush(this.brushOf(d, x, y), false);
            this.opts.onBrushing?.(this.brush);
            return;
          }
          if (d.kind === "move" && this.dragBrush) {
            const b = this.dragBrush;
            const mx = (x - d.x) / v.map.sx;
            const my = (y - d.y) / v.map.sy;
            this.front_.hover = null;
            this.setBrush({ x: b.x ? [b.x[0] + mx, b.x[1] + mx] : null, y: b.y ? [b.y[0] + my, b.y[1] + my] : null, panel: b.panel ?? null, legend: b.legend ?? null }, false);
            this.opts.onBrushing?.(this.brush);
            return;
          }
          const dx = (x - d.x) / v.map.sx;
          const dy = (y - d.y) / v.map.sy;
          const panel = this.spec.panels[v.panel];
          // a fitted y follows x: dragging pans x alone
          if (d.kind !== "y") this.setX(panel.xg, [d.xr[0] - dx, d.xr[1] - dx]);
          if (d.kind === "y" || (d.kind === "pan" && !this.fitY)) this.setY(panel.yg, [d.yr[0] - dy, d.yr[1] - dy]);
          this.request();
          return;
        }
        const onAxis = this.axisAt(x, y);
        this.front.style.cursor = onAxis ? (onAxis.axis === "x" ? "ew-resize" : "ns-resize") : "";
        this.hover(x, y);
      },
      { signal },
    );
    const end = (e: PointerEvent): void => {
      const d = this.drag;
      if (d) stage.releasePointerCapture?.(e.pointerId);
      this.drag = null;
      if (d?.kind === "brush" || d?.kind === "move") {
        this.dragBrush = null;
        if (e.type === "pointercancel") return;
        if (!d.moved) {
          // a click clears the selection (a linked plot's too)
          if (this.brush) this.setBrush(null, true);
          else if (this.highlight) this.opts.onClear?.();
          return;
        }
        this.opts.onSelect?.(this.brush);
        this.selectedNotice();
        return;
      }
      if (d?.kind === "box" && (this.front_.box || this.front_.ghosts.length)) {
        if (e.type === "pointerup" && d.moved) {
          const [x, y] = this.local(e);
          this.applyBox(d, x, y);
        }
        this.front_.box = null;
        this.front_.ghosts = [];
        this.request();
      }
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
        const onAxis = this.axisAt(x, y);
        if (onAxis) {
          this.resetAxis(onAxis.view, onAxis.axis);
          return;
        }
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
        if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "z") {
          this.undo();
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        if ((e.key === "Enter" || e.key === " ") && (e.target as HTMLElement).closest("button")) return;
        // typing in the pager's fields: Escape closes the filters, other keys are the field's
        if ((e.target as HTMLElement).closest("input, select, textarea")) {
          if (e.key === "Escape" && this.pager.menuOpen) {
            this.pager.toggleMenu(false);
            this.root.focus();
            e.preventDefault();
            e.stopPropagation();
          }
          return;
        }
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
      case "e":
        this.toggleExport();
        return true;
      case "r":
      case "0":
        this.resetZoom();
        return true;
      case "u":
        this.undo();
        return true;
      case "z":
        this.setMode(this.mode === "zoom" ? "pan" : "zoom");
        return true;
      case "s":
        this.setMode(this.mode === "select" ? "pan" : "select");
        return true;
      case "y":
        if (this.spec?.y.kind === "band") return false;
        this.setFitY(!this.fitY, true);
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
        if (!this.exportMenu.hidden) {
          this.toggleExport(false);
          return true;
        }
        if (this.pager.menuOpen) {
          this.pager.toggleMenu(false);
          return true;
        }
        if (this.brush) {
          this.setBrush(null, true);
          return true;
        }
        if (this.highlight && this.focused === null && this.opts.onClear) {
          this.opts.onClear();
          return true;
        }
        if (this.focused === null) return false;
        this.setFocus(null, true);
        return true;
      case "Backspace":
        if (this.focused === null) return false;
        this.setFocus(null, true);
        return true;
      case "PageUp":
      case "PageDown":
        if (this.focused === null) {
          if (!this.order) return false;
          this.turnPage(key === "PageDown" ? 1 : -1);
          return true;
        }
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
    // a bar's or a stacked area's own value: from its base
    const isBar = layer.spec.type === "bars" || layer.spec.type === "area";
    const hide = layer.spec.hide ?? [];
    if (!hide.includes("x")) rows.push([spec.x.title || "x", formatValue(spec.x.kind, pt.x, spec.x.origin, v.x[1] - v.x[0], spec.x.levels)]);
    if (!hide.includes("y")) rows.push([spec.y.title || "y", formatValue(spec.y.kind, isBar ? pt.y - pt.y0 : pt.y, spec.y.origin, v.y[1] - v.y[0], spec.y.levels)]);
    const legend = layer.spec.color.legend;
    if (layer.codes && legend !== null) {
      const lg = spec.legends[legend];
      rows.push([lg.title, lg.labels?.[layer.codes[hit.instance]] ?? ""]);
    }
    const key = `${layer.index}:${layer.spec.coords.id}:${hit.instance}`;
    const tips = layer.spec.tips;
    if (tips && layer.tipRows) {
      // given with the spec: no need to ask Python
      const values = tips.values[layer.tipRows[hit.instance]] ?? [];
      this.renderTip(keys, layer, rows, tips.names.map((n, k) => [n, values[k] ?? ""]));
      this.placeTip(px, py);
      this.hoverKey = key;
      return;
    }
    this.renderTip(keys, layer, rows, []);
    this.placeTip(px, py);
    if (key === this.hoverKey) return;
    this.hoverKey = key;
    if (layer.spec.tooltip && this.opts.tooltip) {
      const req = ++this.tipRequest;
      this.opts
        .tooltip(layer.index, hit.instance, layer.spec.coords.id)
        .then((extra) => {
          if (req !== this.tipRequest || this.hoverKey !== key) return;
          this.renderTip(keys, layer, rows, extra);
        })
        .catch(() => {});
    }
  }

  private renderTip(title: string, layer: LayerData, rows: [string, string][], extra: string[][]): void {
    const multi = new Set(this.spec?.layers.map((l) => l.name)).size > 1; // a box's parts: one
    const head = [title, multi ? layer.spec.name : ""].filter(Boolean).join(" — ");
    const all = [...rows, ...extra.map(([k, v]) => [k, v] as [string, string])];
    this.tip.replaceChildren();
    if (head) this.tip.append(el("div", "atr-tip-head", head));
    // a class: page styles for plain tables (a docs theme's, `table:not([class])`) leave it be
    const table = el("table", "atr-tip-table");
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
    this.legendItems = [];
    // a category's entries select its marks: alone, or added with Shift, Cmd or Ctrl
    const selectable = this.scene?.layers.some((l) => l.codes && !l.spec.context) ?? false;
    legends.forEach((lg, index) => {
      const box = el("div", lg.kind === "category" ? "atr-legend-group atr-legend-cat" : "atr-legend-group");
      box.append(el("span", "atr-legend-title", lg.title));
      if (lg.kind === "category") {
        (lg.labels ?? []).forEach((label, i) => {
          const item = el("span", "atr-legend-item");
          const sw = el("span", "atr-swatch");
          sw.style.background = lg.colors[i];
          item.append(sw, document.createTextNode(label));
          box.append(item);
          if (!selectable) return;
          item.classList.add("atr-legend-pick");
          item.tabIndex = 0;
          item.setAttribute("role", "button");
          item.setAttribute("aria-pressed", "false");
          item.title = "Click: select its marks (Shift+click: add or remove)";
          const pick = (add: boolean): void => this.pickLegend(index, i, add);
          item.addEventListener("click", (e) => pick(e.shiftKey || e.metaKey || e.ctrlKey));
          item.addEventListener("keydown", (e) => {
            if (e.key !== "Enter" && e.key !== " ") return;
            e.preventDefault();
            e.stopPropagation();
            pick(e.shiftKey || e.metaKey || e.ctrlKey);
          });
          this.legendItems.push({ index, level: i, el: item });
        });
      } else {
        const bar = el("span", "atr-gradient");
        bar.style.background = `linear-gradient(to right, ${lg.colors.join(", ")})`;
        box.append(el("span", "atr-legend-item", fmt(lg.lo ?? 0)), bar, el("span", "atr-legend-item", fmt(lg.hi ?? 1)));
      }
      this.legend.append(box);
    });
    this.legend.style.display = legends.length ? "flex" : "none";
    this.updateLegend();
  }

  /** A click on legend entry `level` of legend `index`: select its colour (with `add`: add
   * it to those chosen, or take it away). A range brushed stays: both must hold. */
  private pickLegend(index: number, level: number, add: boolean): void {
    const b = this.brush;
    const legend = toggleLegend(b?.legend ?? null, index, level, add);
    this.setBrush({ x: b?.x ?? null, y: b?.y ?? null, panel: b?.panel ?? null, legend }, true);
    this.selectedNotice();
  }

  /** The chosen legend entries stand out; the others fade while some are chosen. */
  private updateLegend(): void {
    const legend = this.brush?.legend ?? null;
    for (const { index, level, el: item } of this.legendItems) {
      const on = legend?.index === index && legend.levels.includes(level);
      item.classList.toggle("atr-legend-on", on);
      item.classList.toggle("atr-legend-off", !!legend && legend.index === index && !on);
      item.setAttribute("aria-pressed", String(on));
    }
  }

  get rendererKind(): string | null {
    return this.renderer?.kind ?? null;
  }

  /** The opened panel's name, or null. */
  get focusName(): string | null {
    return this.spec && this.focused !== null ? panelName(this.spec, this.focused) : null;
  }

  // ---- exporting ---------------------------------------------------------------------------

  /** The size of an exported image (CSS px): the plot's, less nothing (the toolbar is left out,
   * its place stays). */
  private imageSize(): { width: number; height: number } {
    const r = this.root.getBoundingClientRect();
    return { width: Math.max(1, Math.round(r.width)), height: Math.max(1, Math.round(r.height)) };
  }

  /**
   * The plot as shown, painted on `ctx` in CSS pixels from its top left: the title, the
   * panels with their marks, axes, strips and the selection, and the legend. Not the
   * toolbar, tooltips, notices, or the crosshair and hovered mark.
   */
  paint(ctx: CanvasRenderingContext2D): void {
    if (!this.spec || !this.scene || !this.lay) return;
    const origin = this.root.getBoundingClientRect();
    // the title; an opened panel's name is in its strip (the header's way back is left out)
    for (const e of Array.from(this.heading.querySelectorAll(".atr-title"))) paintHtml(ctx, e, origin);
    const stage = this.stage.getBoundingClientRect();
    const views = this.panelViews();
    ctx.save();
    ctx.translate(stage.left - origin.left, stage.top - origin.top);
    ctx.beginPath();
    ctx.rect(0, 0, stage.width, stage.height);
    ctx.clip();
    drawBack(ctx, this.spec, views, this.theme);
    drawMarks(ctx, this.markDraws(views));
    const front: FrontState = { crossX: null, crossGroup: null, hover: null, hoverPanel: null, box: null, ghosts: [], brushes: this.front_.brushes, texts: this.scene.texts };
    drawFront(ctx, this.spec, this.lay, views, this.theme, front);
    ctx.restore();
    if (this.spec.legends.length) paintHtml(ctx, this.legend, origin);
  }

  /** A PNG of the plot as shown, `scale` pixels per CSS pixel. */
  async pngImage(scale = PNG_SCALE): Promise<Blob> {
    const { width, height } = this.imageSize();
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const ctx = canvas.getContext("2d")!;
    ctx.scale(scale, scale);
    ctx.fillStyle = this.theme.bg;
    ctx.fillRect(0, 0, width, height);
    this.paint(ctx);
    return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("no image"))), "image/png"));
  }

  /** An SVG of the plot as shown: every mark, axis and label a vector element. */
  svgImage(): string {
    const { width, height } = this.imageSize();
    const svg = new SvgContext(width, height, pageMeasure());
    this.paint(svg.context);
    return svg.toString(this.theme.bg);
  }

  /** Show or hide the Export menu (its toolbar button, e): what this page can do. */
  private toggleExport(show = this.exportMenu.hidden): void {
    this.exportMenu.hidden = !show;
    this.exportButton.setAttribute("aria-expanded", String(show));
    if (!show) return;
    this.hideTip();
    const actions: [string, string, ExportHow][] = [];
    if (canCopyImages()) actions.push(["Copy image", "a PNG, to paste into slides", "copy"]);
    if (canCopySvg()) actions.push(["Copy as vector", "an SVG, sharp at any size (and a PNG)", "copy-svg"]);
    actions.push(["Download PNG", "an image file", "png"], ["Download SVG", "a vector image (PowerPoint, Word, Inkscape)", "svg"]);
    if (this.opts.onSaveFile) {
      actions.push(["Save PNG next to the notebook", "a file where Python runs", "save-png"], ["Save SVG next to the notebook", "a vector file where Python runs", "save-svg"]);
    }
    this.exportMenu.replaceChildren(
      ...actions.map(([label, note, how]) => {
        const b = el("button", "atr-export-item");
        b.type = "button";
        b.setAttribute("role", "menuitem");
        b.dataset.export = how;
        b.append(el("span", "", label), el("span", "atr-export-note", note));
        b.addEventListener("click", (e) => {
          e.stopPropagation();
          this.toggleExport(false);
          this.exportImage(how).catch(() => {}); // the plot says what went wrong
        });
        return b;
      }),
    );
    (this.exportMenu.firstElementChild as HTMLElement | null)?.focus();
  }

  /** Export the plot as shown: to the clipboard, a download, or a file Python saves. */
  exportImage(how: ExportHow): Promise<string> {
    const name = (ext: string): string => fileName(this.spec?.title ?? "", this.focusName, ext);
    // made on demand, once: each is a promise, so a copy claims the clipboard in the click
    let svgText: Promise<string> | null = null;
    let pngBlob: Promise<Blob> | null = null;
    const svg = (): Promise<string> => (svgText ??= Promise.resolve().then(() => this.svgImage()));
    const png = (): Promise<Blob> => (pngBlob ??= this.pngImage());
    const svgBlob = (): Promise<Blob> => svg().then((t) => new Blob([t], { type: "image/svg+xml" }));
    const save = this.opts.onSaveFile;
    // the file's name (Python answers its whole path; logged, for finding it)
    const saved = (path: string): string => {
      console.info(`[anytrellis] saved ${path}`);
      return `Saved ${path.split(/[\\/]/).pop()} next to the notebook`;
    };
    let done: Promise<string>;
    if ((how === "png" || how === "svg") && !canDownload()) done = Promise.reject(new Error(NO_DOWNLOADS));
    else if (how === "copy") done = copyPng(png()).then(() => "Copied: paste it into your slides");
    else if (how === "copy-svg") done = copySvg(svg(), png()).then(() => svgBlob().then((b) => svgMessage("Copied", b.size)));
    else if (how === "png") done = png().then((b) => (download(b, name("png")), `Downloaded ${name("png")}`));
    else if (how === "svg") done = svgBlob().then((b) => (download(b, name("svg")), svgMessage(`Downloaded ${name("svg")}`, b.size)));
    else if (!save) done = Promise.reject(new Error("no Python to save the file"));
    else if (how === "save-png") done = png().then((b) => save(name("png"), b)).then(saved);
    else done = svgBlob().then((b) => save(name("svg"), b)).then(saved);
    this.notify("Making the image…");
    return done.then(
      (message) => {
        this.notify(message, 3000);
        return message;
      },
      (err) => {
        console.warn("[anytrellis] export failed:", err);
        const copying = how === "copy" || how === "copy-svg";
        const why = err instanceof Error ? err.message : String(err);
        this.notify(copying ? "Copying is not allowed here: download the image instead" : why === NO_DOWNLOADS ? why : `Export failed: ${why}`, 4000);
        throw err;
      },
    );
  }

  destroy(): void {
    this.destroyed = true;
    this.abort.abort();
    clearTimeout(this.noticeTimer);
    clearTimeout(this.viewTimer);
    clearTimeout(this.pagingTimer);
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

/** Size a canvas; true if its pixels changed size (which clears it). */
function sizeCanvas(c: HTMLCanvasElement, w: number, h: number, dpr: number): boolean {
  const pw = Math.max(1, Math.round(w * dpr));
  const ph = Math.max(1, Math.round(h * dpr));
  const resized = c.width !== pw || c.height !== ph;
  if (c.width !== pw) c.width = pw;
  if (c.height !== ph) c.height = ph;
  c.style.width = `${w}px`;
  c.style.height = `${h}px`;
  return resized;
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

