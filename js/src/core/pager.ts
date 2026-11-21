// The bar over a paged wrap: turn the pages, sort the panels by a statistic and filter them
// by name and by their statistics (each number's distribution over the panels a histogram
// to brush), and show or save views. It holds no state of its own: the view gives it the
// paging shown (update) and the views (setViews), and it asks for changes (onChange, and
// the ViewActions).

import { panelOrder } from "./pages";
import type { PagesSpec, PanelStat, Paging } from "./types";

/** What the Views menu asks of the view: show, save (the view as shown) or delete one. */
export interface ViewActions {
  show(name: string): void;
  save(name: string): void;
  drop(name: string): void;
}

/** A statistic's histogram in the filters: its bins, and the width and height (px). */
const BINS = 20;
const HIST_W = 140;
const HIST_H = 26;

const ICONS = {
  prev: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 4 6 8l4 4" /></svg>',
  next: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4" /></svg>',
  up: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 13V3M2.5 5.5 5 3l2.5 2.5M9 5h5M9 8h3.5M9 11h2" /></svg>',
  down: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3v10M2.5 10.5 5 13l2.5-2.5M9 5h2M9 8h3.5M9 11h5" /></svg>',
  filter: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 3.5h11l-4.25 5v4l-2.5 1v-5z" /></svg>',
  views: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 2.5h7v11L8 10.5l-3.5 3z" /></svg>',
};

export class Pager {
  readonly el: HTMLDivElement;
  readonly menu: HTMLDivElement;
  private readonly prev: HTMLButtonElement;
  private readonly next: HTMLButtonElement;
  private readonly where: HTMLSpanElement;
  private readonly named: HTMLSelectElement;
  private readonly namedTitle: HTMLSpanElement;
  private readonly sorting: HTMLLabelElement;
  private readonly filtering: HTMLSpanElement;
  private readonly count: HTMLSpanElement;
  private readonly sort: HTMLSelectElement;
  private readonly direction: HTMLButtonElement;
  private readonly search: HTMLInputElement;
  private readonly filters: HTMLButtonElement;
  private readonly viewsButton: HTMLButtonElement;
  private readonly viewsLabel: HTMLSpanElement;
  readonly viewsMenu: HTMLDivElement;
  private spec: PagesSpec | null = null;
  private paging: Paging = {};
  private menuFor: PagesSpec | null = null;
  /** The panels' names: the panels each filter but one keeps, in its histogram. */
  private panels: string[] = [];
  private hists: (() => void)[] = [];
  private viewNames: string[] = [];
  private current: string | null = null;

  constructor(
    private readonly onChange: (paging: Paging) => void,
    private readonly views?: ViewActions,
  ) {
    this.el = el("div", "atr-pager");
    this.prev = button(ICONS.prev, "Previous page (Page Up)", () => this.turn(-1));
    this.next = button(ICONS.next, "Next page (Page Down)", () => this.turn(1));
    this.where = el("span", "atr-page");
    // pages of page columns: picked by their level
    this.named = el("select", "atr-page-select");
    this.named.addEventListener("change", () => this.change({ page: Number(this.named.value) }));
    this.named.hidden = true;
    this.namedTitle = el("span", "atr-muted");
    this.namedTitle.hidden = true;
    this.count = el("span", "atr-count");
    const pages = el("span", "atr-pager-group");
    pages.append(this.prev, this.namedTitle, this.named, this.where, this.next, this.count);

    this.sort = el("select", "atr-select");
    this.sort.title = "Sort the panels by a statistic of each";
    this.sort.setAttribute("aria-label", "Sort the panels by");
    this.sort.addEventListener("change", () => this.change({ sort: this.sort.value || null, page: 0 }));
    this.direction = button(ICONS.up, "Ascending: click for descending", () => this.change({ descending: !this.paging.descending, page: 0 }));
    const sort = el("label", "atr-pager-group");
    sort.append(el("span", "atr-muted", "Sort"), this.sort, this.direction);
    this.sorting = sort;

    this.search = el("input", "atr-search");
    this.search.type = "search";
    this.search.placeholder = "Filter by name";
    this.search.setAttribute("aria-label", "Show the panels whose name has these words");
    this.search.addEventListener("input", () => this.change({ name: this.search.value, page: 0 }));
    this.filters = button(ICONS.filter, "Filter by statistics", () => this.toggleMenu());
    this.filters.setAttribute("aria-haspopup", "dialog");
    this.filters.setAttribute("aria-expanded", "false");
    const filter = el("span", "atr-pager-group");
    filter.append(this.search, this.filters);
    this.filtering = filter;

    this.viewsButton = button(ICONS.views, "Views: show one kept, or keep this one", () => this.toggleViews());
    this.viewsButton.classList.add("atr-views-button");
    this.viewsButton.setAttribute("aria-haspopup", "dialog");
    this.viewsButton.setAttribute("aria-expanded", "false");
    this.viewsLabel = el("span", "atr-views-label", "Views");
    this.viewsButton.append(this.viewsLabel);
    const viewing = el("span", "atr-pager-group");
    viewing.append(this.viewsButton);
    viewing.hidden = !views;

    this.el.append(pages, sort, filter, viewing);
    this.menu = el("div", "atr-filters");
    this.menu.setAttribute("role", "dialog");
    this.menu.setAttribute("aria-label", "Filter the panels by their statistics");
    this.menu.hidden = true;
    this.viewsMenu = el("div", "atr-filters atr-views");
    this.viewsMenu.setAttribute("role", "dialog");
    this.viewsMenu.setAttribute("aria-label", "Views: show one kept, or keep this one");
    this.viewsMenu.hidden = true;
    this.el.append(this.menu, this.viewsMenu);
  }

  /** The views kept (their names), and the one the plot shows now, or null. */
  setViews(names: string[], current: string | null): void {
    const changed = names.join("\u0000") !== this.viewNames.join("\u0000") || current !== this.current;
    this.viewNames = names;
    this.current = current;
    this.viewsLabel.textContent = current ?? "Views";
    this.viewsButton.title = current ? `View: ${current} (click for the views)` : "Views: show one kept, or keep this one";
    this.viewsButton.setAttribute("aria-label", current ? `View: ${current}` : "Views");
    if (changed && !this.viewsMenu.hidden) this.fillViews();
  }

  toggleViews(open?: boolean): void {
    const show = open ?? this.viewsMenu.hidden;
    if (show) {
      this.toggleMenu(false);
      if (this.viewsMenu.hidden) this.fillViews();
    }
    this.viewsMenu.hidden = !show;
    this.viewsButton.setAttribute("aria-expanded", String(show));
    if (show) {
      // under its button, within the bar
      const room = this.el.clientWidth - this.viewsMenu.offsetWidth - 8;
      this.viewsMenu.style.left = `${Math.max(8, Math.min(this.viewsButton.offsetLeft, room))}px`;
    }
    if (show) this.viewsMenu.querySelector<HTMLElement>("input, button")?.focus();
  }

  /** The views as buttons (each with a delete), and a name to keep the one shown under. */
  private fillViews(): void {
    const views = this.views;
    this.viewsMenu.replaceChildren();
    if (!views) return;
    const list = el("div", "atr-view-rows");
    if (!this.viewNames.length) list.append(el("span", "atr-muted", "No views kept yet."));
    for (const name of this.viewNames) {
      const show = el("button", "atr-link atr-view-name", name);
      show.type = "button";
      show.title = `Show the view ${name}: its sort, filters, page and zoom`;
      if (name === this.current) show.setAttribute("aria-current", "true");
      show.addEventListener("click", () => {
        views.show(name);
        this.toggleViews(false);
      });
      const drop = el("button", "atr-button atr-view-drop", "×");
      drop.type = "button";
      drop.title = `Delete the view ${name}`;
      drop.setAttribute("aria-label", `Delete the view ${name}`);
      drop.addEventListener("click", () => {
        views.drop(name);
        this.viewsMenu.querySelector<HTMLInputElement>("input")?.focus(); // (the list is new)
      });
      list.append(show, drop);
    }
    const form = el("form", "atr-view-save");
    const input = el("input", "atr-search");
    input.type = "text";
    input.placeholder = "Name this view";
    input.setAttribute("aria-label", "Keep the view shown as");
    const save = el("button", "atr-link", "Keep");
    save.type = "submit";
    form.append(input, save);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const name = input.value.trim();
      if (!name) return;
      views.save(name);
      this.viewsMenu.querySelector<HTMLInputElement>("input")?.focus(); // (the list is new)
    });
    this.viewsMenu.append(list, form);
  }

  /** Show `paging` over `shown` of `total` panels, on `pageCount` pages (`names`: each
   * page's name, "" for none). */
  update(spec: PagesSpec, paging: Paging, shown: number, total: number, pageCount: number, names: string[] = [], panels: string[] = []): void {
    const statsChanged = this.spec !== spec;
    this.spec = spec;
    this.paging = paging;
    this.panels = panels;
    const page = Math.min(paging.page ?? 0, pageCount - 1);
    this.where.textContent = `Page ${page + 1} of ${pageCount}`;
    const named = names.some(Boolean);
    this.where.hidden = named;
    this.named.hidden = !named;
    this.namedTitle.hidden = !named || !spec.title;
    this.namedTitle.textContent = spec.title ?? "";
    if (named) {
      if (this.named.options.length !== names.length || names.some((n, k) => this.named.options[k].text !== n)) {
        this.named.replaceChildren(...names.map((n, k) => option(String(k), n)));
      }
      this.named.value = String(page);
      const title = spec.title ? `${spec.title}: ` : "";
      this.named.title = `${title}the page shown (Page Up, Page Down)`;
      this.named.setAttribute("aria-label", spec.title ? `Show the page of ${spec.title}` : "Show the page");
    }
    // a grid's pages: every cell, in its place
    this.sorting.hidden = spec.grid === true;
    this.filtering.hidden = spec.grid === true;
    this.prev.disabled = page <= 0;
    this.next.disabled = page >= pageCount - 1;
    this.count.textContent = shown === total ? `${total} panels` : `${shown} of ${total} panels`;
    if (statsChanged) {
      this.sort.replaceChildren(option("", "as given"), ...spec.stats.map((s) => option(s.name, s.label ?? s.name)));
    }
    this.sort.value = paging.sort && spec.stats.some((s) => s.name === paging.sort) ? paging.sort : "";
    const desc = paging.descending === true;
    this.direction.innerHTML = desc ? ICONS.down : ICONS.up;
    const tip = desc ? "Descending: click for ascending" : "Ascending: click for descending";
    this.direction.title = tip;
    this.direction.setAttribute("aria-label", desc ? "Descending" : "Ascending");
    this.direction.disabled = !this.sort.value;
    if (document.activeElement !== this.search) this.search.value = paging.name ?? "";
    const active = Object.values(paging.where ?? {}).filter(isActive).length;
    this.filters.setAttribute("aria-pressed", String(active > 0));
    this.filters.dataset.count = active ? String(active) : "";
    if (!this.menu.hidden && (statsChanged || this.menuFor !== spec)) this.fillMenu();
    else if (!this.menu.hidden) this.hists.forEach((draw) => draw());
  }

  toggleMenu(open?: boolean): void {
    const show = open ?? this.menu.hidden;
    if (show) this.toggleViews(false);
    if (show && this.menu.hidden) this.fillMenu();
    this.menu.hidden = !show;
    this.filters.setAttribute("aria-expanded", String(show));
    if (show) this.menu.querySelector<HTMLInputElement>("input")?.focus();
  }

  get menuOpen(): boolean {
    return !this.menu.hidden || !this.viewsMenu.hidden;
  }

  /** Close the filters and the views. */
  closeMenus(): void {
    this.toggleMenu(false);
    this.toggleViews(false);
  }

  private turn(step: number): void {
    this.change({ page: Math.max(0, (this.paging.page ?? 0) + step) });
  }

  private change(changes: Paging): void {
    this.onChange({ ...this.paging, ...changes });
  }

  private setWhere(name: string, value: [number | null, number | null] | string | null): void {
    const where = { ...(this.paging.where ?? {}) };
    if (value === null || !isActive(value)) delete where[name];
    else where[name] = value;
    this.change({ where, page: 0 });
  }

  /** A row per statistic: low and high for numbers (their range as placeholders), a piece
   * of text for text. */
  private fillMenu(): void {
    const spec = this.spec;
    this.menuFor = spec;
    this.menu.replaceChildren();
    this.hists = [];
    if (!spec) return;
    const table = el("div", "atr-filter-rows");
    for (const s of spec.stats) {
      const row = el("label", "atr-filter-row");
      row.append(el("span", "atr-filter-name", s.label ?? s.name));
      const cond = this.paging.where?.[s.name];
      if (s.kind === "number") {
        let lo: number | null = null;
        let hi: number | null = null;
        for (const v of s.values) {
          if (typeof v !== "number" || Number.isNaN(v)) continue;
          if (lo === null || v < lo) lo = v;
          if (hi === null || v > hi) hi = v;
        }
        const range = Array.isArray(cond) ? cond : [null, null];
        const low = numberInput(range[0], lo, `${s.label ?? s.name}: at least`);
        const high = numberInput(range[1], hi, `${s.label ?? s.name}: at most`);
        const apply = (): void => this.setWhere(s.name, [num(low.value), num(high.value)]);
        low.addEventListener("input", apply);
        high.addEventListener("input", apply);
        const hist = lo !== null && hi !== null && hi > lo ? this.histogram(s, lo, hi, low, high) : el("span", "");
        row.append(hist, low, el("span", "atr-muted", "to"), high);
      } else {
        const text = el("input", "atr-search");
        text.type = "search";
        text.placeholder = "has";
        text.setAttribute("aria-label", `${s.label ?? s.name}: has`);
        text.value = typeof cond === "string" ? cond : "";
        text.addEventListener("input", () => this.setWhere(s.name, text.value));
        row.append(text);
      }
      table.append(row);
    }
    const clear = el("button", "atr-link", "Clear the filters");
    clear.type = "button";
    clear.addEventListener("click", () => {
      this.change({ where: {}, name: "", page: 0 });
      this.fillMenu();
    });
    this.menu.append(table, clear);
  }

  /** Statistic `s`'s values over the panels, `lo` to `hi`, in bins: every panel's faint,
   * those the other filters keep on top, and its range as a band. A drag across it sets the
   * range (to an end: open there), a click clears it; `low` and `high` follow. */
  private histogram(s: PanelStat, lo: number, hi: number, low: HTMLInputElement, high: HTMLInputElement): SVGSVGElement {
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "atr-hist");
    svg.setAttribute("width", String(HIST_W));
    svg.setAttribute("height", String(HIST_H));
    svg.setAttribute("viewBox", `0 0 ${HIST_W} ${HIST_H}`);
    svg.setAttribute("role", "img");
    const label = s.label ?? s.name;
    const bin = (v: number): number => Math.min(BINS - 1, Math.max(0, Math.floor(((v - lo) / (hi - lo)) * BINS)));
    const all = new Array<number>(BINS).fill(0);
    s.values.forEach((v) => {
      if (typeof v === "number" && !Number.isNaN(v)) all[bin(v)]++;
    });
    const top = Math.max(...all);
    const w = HIST_W / BINS;
    const bar = (i: number, n: number, cls: string): SVGRectElement => {
      const r = document.createElementNS(NS, "rect");
      const h = n ? Math.max(1.5, (n / top) * (HIST_H - 2)) : 0;
      r.setAttribute("class", cls);
      r.setAttribute("x", String(i * w + 0.5));
      r.setAttribute("width", String(Math.max(1, w - 1)));
      r.setAttribute("y", String(HIST_H - h));
      r.setAttribute("height", String(h));
      return r;
    };
    const xOf = (v: number): number => ((v - lo) / (hi - lo)) * HIST_W;
    const draw = (): void => {
      const others = { ...(this.paging.where ?? {}) };
      delete others[s.name];
      const kept = new Array<number>(BINS).fill(0);
      for (const i of panelOrder(this.spec?.stats ?? [], this.panels, { name: this.paging.name, where: others })) {
        const v = s.values[i];
        if (typeof v === "number" && !Number.isNaN(v)) kept[bin(v)]++;
      }
      const range = this.paging.where?.[s.name];
      const [a, b] = Array.isArray(range) ? range : [null, null];
      svg.replaceChildren(...all.map((n, i) => bar(i, n, "atr-hist-all")), ...kept.map((n, i) => bar(i, n, "atr-hist-kept")));
      if (a !== null || b !== null) {
        const x0 = a === null ? 0 : Math.max(0, xOf(a));
        const x1 = b === null ? HIST_W : Math.min(HIST_W, xOf(b));
        const band = document.createElementNS(NS, "rect");
        band.setAttribute("class", "atr-hist-range");
        band.setAttribute("x", String(Math.min(x0, x1)));
        band.setAttribute("width", String(Math.max(1, Math.abs(x1 - x0))));
        band.setAttribute("y", "0");
        band.setAttribute("height", String(HIST_H));
        svg.append(band);
      }
      const n = kept.reduce((p, q) => p + q, 0);
      svg.setAttribute("aria-label", `${label} over the panels: ${n} the other filters keep. Drag across to filter by it, click to clear.`);
    };
    // a drag sets the range, to rounder numbers than the pixel gives (an end: open)
    const unit = 10 ** (Math.floor(Math.log10(hi - lo)) - 2);
    const at = (e: PointerEvent): number => Math.min(HIST_W, Math.max(0, e.clientX - svg.getBoundingClientRect().left));
    let start: number | null = null;
    const set = (x0: number, x1: number): void => {
      const [p, q] = x0 <= x1 ? [x0, x1] : [x1, x0];
      const a = p <= 1 ? null : +(Math.floor((lo + (p / HIST_W) * (hi - lo)) / unit) * unit).toPrecision(8);
      const b = q >= HIST_W - 1 ? null : +(Math.ceil((lo + (q / HIST_W) * (hi - lo)) / unit) * unit).toPrecision(8);
      low.value = a === null ? "" : String(a);
      high.value = b === null ? "" : String(b);
      this.setWhere(s.name, a === null && b === null ? null : [a, b]);
    };
    svg.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      svg.setPointerCapture(e.pointerId);
      start = at(e);
    });
    svg.addEventListener("pointermove", (e) => {
      if (start === null || Math.abs(at(e) - start) < 3) return;
      set(start, at(e));
    });
    svg.addEventListener("pointerup", (e) => {
      if (start === null) return;
      const moved = Math.abs(at(e) - start) >= 3;
      if (moved) set(start, at(e));
      else {
        low.value = "";
        high.value = "";
        this.setWhere(s.name, null);
      }
      start = null;
    });
    draw();
    this.hists.push(draw);
    return svg;
  }
}

function isActive(v: [number | null, number | null] | string | null | undefined): boolean {
  if (typeof v === "string") return v.trim() !== "";
  return Array.isArray(v) && (v[0] !== null || v[1] !== null);
}

function num(text: string): number | null {
  const v = parseFloat(text);
  return Number.isFinite(v) ? v : null;
}

function numberInput(value: number | null, hint: number | null, label: string): HTMLInputElement {
  const input = el("input", "atr-number");
  input.type = "number";
  input.step = "any";
  input.value = value === null ? "" : String(value);
  input.placeholder = hint === null ? "" : String(+hint.toPrecision(4));
  input.setAttribute("aria-label", label);
  return input;
}

function option(value: string, text: string): HTMLOptionElement {
  const o = el("option", "", text);
  o.value = value;
  return o;
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

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
