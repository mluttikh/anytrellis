// A figure's legend, collected from its plots (compose.py: concat(legend="collect")): each
// plot shows none of its own, and the figure shows each legend once, under its plots. The
// plots and the figure's legend meet here by the figure's id, on the page's global object
// (as align.ts's figures do). A click on an entry chooses it in every plot that has that
// legend, and in the others chooses none; hovering it, or showing it alone, does so in
// each. The legend has one state: what a plot chooses by itself (Escape, Python's select)
// the legend shows and the other plots follow.
import { LegendBox } from "./legendbox";
import { type LegendChoice, toggleLegend } from "./selection";
import type { LegendSpec } from "./types";

/** What a plot tells its figure's legend, and lets it do. */
export interface LegendPlot {
  /** Its place among the figure's plots (the legends are collected in this order). */
  order: number;
  /** Its legends (spec.legends), and whether it shows them at all (not legend("none")). */
  legends(): LegendSpec[];
  shows(): boolean;
  /** Whether its marks can be chosen by a category's entries, or by a range of values. */
  selectable(): boolean;
  ranged(): boolean;
  /** Its panels' text size (px). */
  fontSize(): number;
  /** Choose entries of its legend `index` (null: none), the rest of its selection kept. */
  choose(choice: LegendChoice | null): void;
  isolate(choice: { index: number; level: number } | null): void;
  preview(choice: LegendChoice | null): void;
}

/** A legend chosen in the figure's terms: by what the legend is, not where it is. */
interface Chosen {
  key: string;
  levels: number[];
  range?: [number, number] | null;
}

interface Hub {
  plots: Set<LegendPlot>;
  boxes: Set<FigureLegend>;
  chosen: Chosen | null;
  /** Chosen before an entry's click (a double-click puts it back, as in a plot). */
  before: Chosen | null;
  isolated: { key: string; level: number } | null;
}

/** What makes two plots' legends the same one (figure.py: legend_key): all of it. */
export function legendKey(lg: LegendSpec): string {
  return JSON.stringify(sortKeys(lg));
}

function sortKeys(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return Object.fromEntries(Object.keys(o).sort().map((k) => [k, sortKeys(o[k])]));
  }
  return v;
}

type Registry = Map<string, Hub>;

function hubOf(id: string): Hub {
  const g = globalThis as { anytrellisLegends?: Registry };
  const hubs = (g.anytrellisLegends ??= new Map());
  let hub = hubs.get(id);
  if (!hub) hubs.set(id, (hub = { plots: new Set(), boxes: new Set(), chosen: null, before: null, isolated: null }));
  return hub;
}

/** The legends the figure shows: each once, in its plots' order (the first plot's that has
 * it), and the plots that have each. */
function collected(hub: Hub): { legends: LegendSpec[]; keys: string[]; owners: LegendPlot[][] } {
  const legends: LegendSpec[] = [];
  const keys: string[] = [];
  const owners: LegendPlot[][] = [];
  const plots = [...hub.plots].sort((a, b) => a.order - b.order);
  for (const plot of plots) {
    if (!plot.shows()) continue;
    for (const lg of plot.legends()) {
      if (lg.direct) continue;
      const key = legendKey(lg);
      const at = keys.indexOf(key);
      if (at >= 0) {
        owners[at].push(plot);
        continue;
      }
      legends.push(lg);
      keys.push(key);
      owners.push([plot]);
    }
  }
  return { legends, keys, owners };
}

/** Where legend `key` is among a plot's legends (-1: it hasn't it). */
function indexIn(plot: LegendPlot, key: string): number {
  return plot.shows() ? plot.legends().findIndex((lg) => !lg.direct && legendKey(lg) === key) : -1;
}

/** A plot's part in its figure's legend. */
export class LegendMember {
  readonly id: string;
  private readonly hub: Hub;
  private readonly plot: LegendPlot;

  constructor(id: string, plot: LegendPlot) {
    this.id = id;
    this.hub = hubOf(id);
    this.plot = plot;
    this.hub.plots.add(plot);
    redraw(this.hub);
  }

  /** Its legends changed (a new spec). */
  changed(): void {
    redraw(this.hub);
  }

  /** What it has chosen now (its own legend's index), and the entry it shows alone: when
   * that isn't the legend's state, the legend takes it and the other plots follow. */
  report(choice: LegendChoice | null | undefined, isolated: { index: number; level: number } | null): void {
    const hub = this.hub;
    const legends = this.plot.legends();
    const keyOf = (index: number): string | null => (legends[index] ? legendKey(legends[index]) : null);
    const mine = (key: string | undefined): boolean => !!key && indexIn(this.plot, key) >= 0;
    let chosen = hub.chosen;
    const key = choice ? keyOf(choice.index) : null;
    if (choice && key && (choice.levels.length || choice.range)) chosen = { key, levels: choice.levels, range: choice.range ?? null };
    else if (mine(hub.chosen?.key)) chosen = null;
    let iso = hub.isolated;
    const isoKey = isolated ? keyOf(isolated.index) : null;
    if (isolated && isoKey) iso = { key: isoKey, level: isolated.level };
    else if (mine(hub.isolated?.key)) iso = null;
    if (JSON.stringify(chosen) !== JSON.stringify(hub.chosen)) choose(hub, chosen, this.plot);
    if (JSON.stringify(iso) !== JSON.stringify(hub.isolated)) isolateAll(hub, iso, this.plot);
    for (const box of hub.boxes) box.update();
  }

  leave(): void {
    this.hub.plots.delete(this.plot);
    redraw(this.hub);
  }
}

function redraw(hub: Hub): void {
  for (const box of hub.boxes) box.render();
}

/** Choose `chosen` in every plot (but `from`, where it was chosen): its entries in those
 * that have the legend, none in the others. */
function choose(hub: Hub, chosen: Chosen | null, from: LegendPlot | null = null): void {
  hub.chosen = chosen;
  for (const plot of hub.plots) {
    if (plot === from) continue;
    const at = chosen ? indexIn(plot, chosen.key) : -1;
    plot.choose(chosen && at >= 0 ? { index: at, levels: chosen.levels, range: chosen.range ?? null } : null);
  }
  for (const box of hub.boxes) box.update();
}

/** Show entry `iso` alone in every plot that has its legend (but `from`); null: all. */
function isolateAll(hub: Hub, iso: { key: string; level: number } | null, from: LegendPlot | null = null): void {
  hub.isolated = iso;
  for (const plot of hub.plots) {
    if (plot === from) continue;
    const at = iso ? indexIn(plot, iso.key) : -1;
    plot.isolate(iso && at >= 0 ? { index: at, level: iso.level } : null);
  }
  for (const box of hub.boxes) box.update();
}

/** The figure's legend, in `host` (a notebook's legend widget, a saved page's
 * `.anytrellis-figure-legend`). */
export class FigureLegend {
  readonly root: HTMLDivElement;
  private readonly box = new LegendBox();
  private readonly hub: Hub;
  private keys: string[] = [];

  constructor(host: HTMLElement, id: string) {
    this.hub = hubOf(id);
    this.root = document.createElement("div");
    this.root.className = "atr-root atr-figure-legend";
    this.root.append(this.box.el);
    host.append(this.root);
    this.hub.boxes.add(this);
    this.render();
  }

  render(): void {
    const hub = this.hub;
    const { legends, keys, owners } = collected(hub);
    this.keys = keys;
    const first = [...hub.plots].sort((a, b) => a.order - b.order)[0];
    if (first) this.root.style.fontSize = `${first.fontSize()}px`;
    this.root.hidden = legends.length === 0;
    const toChosen = (index: number, c: LegendChoice | null | undefined): Chosen | null => (c && (c.levels.length || c.range) ? { key: keys[index], levels: c.levels, range: c.range ?? null } : null);
    this.box.render(
      legends,
      {
        selectable: (i) => owners[i].some((p) => p.selectable()),
        ranged: (i) => owners[i].some((p) => p.ranged()),
      },
      {
        pick: (index, level, add) => {
          hub.before = hub.chosen;
          choose(hub, toChosen(index, toggleLegend(this.choice(), index, level, add)));
        },
        pickBin: (index, bin, add) => {
          const breaks = legends[index]?.breaks;
          if (!breaks) return;
          hub.before = hub.chosen;
          const now = this.choice();
          const have = now?.index === index ? (now.range ?? null) : null;
          let range: [number, number] | null = [breaks[bin], breaks[bin + 1]];
          if (add && have) range = [Math.min(have[0], range[0]), Math.max(have[1], range[1])];
          else if (have && have[0] === range[0] && have[1] === range[1]) range = null;
          choose(hub, range ? { key: keys[index], levels: [], range } : null);
        },
        isolate: (index, level) => {
          // the double-click's first click chose it: as before it
          if (hub.chosen !== hub.before) choose(hub, hub.before);
          const same = hub.isolated?.key === keys[index] && hub.isolated.level === level;
          isolateAll(hub, same ? null : { key: keys[index], level });
        },
        preview: (choice) => {
          for (const plot of hub.plots) {
            const at = choice ? indexIn(plot, keys[choice.index]) : -1;
            plot.preview(choice && at >= 0 ? { index: at, levels: choice.levels } : null);
          }
        },
        range: (index, range) => choose(hub, range ? { key: keys[index], levels: [], range } : null),
      },
      legends.length > 0,
    );
    this.update();
  }

  /** The entries chosen, and the one shown alone, as the plots have them. */
  update(): void {
    const iso = this.hub.isolated;
    const at = iso ? this.keys.indexOf(iso.key) : -1;
    this.box.update(this.choice(), iso && at >= 0 ? { index: at, level: iso.level } : null);
  }

  /** The choice in this legend's terms (its index), or null. */
  private choice(): LegendChoice | null {
    const c = this.hub.chosen;
    const at = c ? this.keys.indexOf(c.key) : -1;
    return c && at >= 0 ? { index: at, levels: c.levels, range: c.range ?? null } : null;
  }

  destroy(): void {
    this.hub.boxes.delete(this);
    this.root.remove();
  }
}
