// The bar over a paged wrap: turn the pages, sort the panels by a statistic and filter them
// by name and by their statistics. It holds no state of its own: the view gives it the
// paging shown (update) and it asks for changes (onChange).

import type { PagesSpec, Paging } from "./types";

const ICONS = {
  prev: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 4 6 8l4 4" /></svg>',
  next: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4" /></svg>',
  up: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 13V3M2.5 5.5 5 3l2.5 2.5M9 5h5M9 8h3.5M9 11h2" /></svg>',
  down: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3v10M2.5 10.5 5 13l2.5-2.5M9 5h2M9 8h3.5M9 11h5" /></svg>',
  filter: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 3.5h11l-4.25 5v4l-2.5 1v-5z" /></svg>',
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
  private spec: PagesSpec | null = null;
  private paging: Paging = {};
  private menuFor: PagesSpec | null = null;

  constructor(private readonly onChange: (paging: Paging) => void) {
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

    this.el.append(pages, sort, filter);
    this.menu = el("div", "atr-filters");
    this.menu.setAttribute("role", "dialog");
    this.menu.setAttribute("aria-label", "Filter the panels by their statistics");
    this.menu.hidden = true;
    this.el.append(this.menu);
  }

  /** Show `paging` over `shown` of `total` panels, on `pageCount` pages (`names`: each
   * page's name, "" for none). */
  update(spec: PagesSpec, paging: Paging, shown: number, total: number, pageCount: number, names: string[] = []): void {
    const statsChanged = this.spec !== spec;
    this.spec = spec;
    this.paging = paging;
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
      this.sort.replaceChildren(option("", "as given"), ...spec.stats.map((s) => option(s.name, s.name)));
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
  }

  toggleMenu(open?: boolean): void {
    const show = open ?? this.menu.hidden;
    if (show && this.menu.hidden) this.fillMenu();
    this.menu.hidden = !show;
    this.filters.setAttribute("aria-expanded", String(show));
    if (show) this.menu.querySelector<HTMLInputElement>("input")?.focus();
  }

  get menuOpen(): boolean {
    return !this.menu.hidden;
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
    if (!spec) return;
    const table = el("div", "atr-filter-rows");
    for (const s of spec.stats) {
      const row = el("label", "atr-filter-row");
      row.append(el("span", "atr-filter-name", s.name));
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
        const low = numberInput(range[0], lo, `${s.name}: at least`);
        const high = numberInput(range[1], hi, `${s.name}: at most`);
        const apply = (): void => this.setWhere(s.name, [num(low.value), num(high.value)]);
        low.addEventListener("input", apply);
        high.addEventListener("input", apply);
        row.append(low, el("span", "atr-muted", "to"), high);
      } else {
        const text = el("input", "atr-search");
        text.type = "search";
        text.placeholder = "has";
        text.setAttribute("aria-label", `${s.name}: has`);
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
