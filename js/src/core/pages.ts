// A paged wrap: which panels a page shows, after the reader's filters and sort. In step with
// `order` in src/anytrellis/pages.py (Trellis.shown_panels, images drawn in Python).

import type { PagesSpec, PanelStat, Paging } from "./types";

/** The panels shown, in order: those the filters keep (every word of `name` in the panel's
 * name; each statistic in its range, or holding its text), sorted stably by a statistic,
 * those without a value last either way. */
export function panelOrder(stats: PanelStat[], names: string[], paging: Paging): number[] {
  const by = new Map(stats.map((s) => [s.name, s]));
  const terms = (paging.name ?? "").toLowerCase().split(/\s+/).filter(Boolean);
  let keep = names.map((_, i) => i).filter((i) => terms.every((t) => names[i].toLowerCase().includes(t)));
  for (const [name, cond] of Object.entries(paging.where ?? {})) {
    const s = by.get(name);
    if (!s) continue;
    if (s.kind === "text") {
      const want = String(cond ?? "").toLowerCase();
      keep = keep.filter((i) => String(s.values[i] ?? "").toLowerCase().includes(want));
      continue;
    }
    const [lo, hi] = Array.isArray(cond) ? cond : [null, null];
    if ((lo ?? null) !== null || (hi ?? null) !== null) keep = keep.filter((i) => within(s.values[i] as number | null, lo ?? null, hi ?? null));
  }
  const s = paging.sort ? by.get(paging.sort) : undefined;
  if (!s) return keep;
  const missing = (i: number): boolean => (s.kind === "text" ? !s.values[i] : s.values[i] === null || Number.isNaN(s.values[i]));
  const present = keep.filter((i) => !missing(i));
  const sign = paging.descending ? -1 : 1;
  present.sort((a, b) => {
    const va = s.values[a]!;
    const vb = s.values[b]!;
    return sign * (va < vb ? -1 : va > vb ? 1 : 0);
  });
  return [...present, ...keep.filter(missing)];
}

function within(v: number | null, lo: number | null, hi: number | null): boolean {
  if (v === null || Number.isNaN(v)) return false;
  return (lo === null || v >= lo) && (hi === null || v <= hi);
}

/** The pages: the panels shown (in order), rows × cols a page; with page columns, each
 * level's panels on pages of their own, the levels in order (one the filters leave empty:
 * none). At least one page, maybe empty. In step with `page_list` in pages.py. */
export function pageList(shown: number[], pages: PagesSpec): number[][] {
  const per = Math.max(1, pages.rows * pages.cols);
  const groups = pages.groups ?? null;
  let members: number[][] = [shown];
  if (groups) {
    const by = new Map<number, number[]>();
    for (const i of shown) {
      const g = groups[i];
      const list = by.get(g);
      if (list) list.push(i);
      else by.set(g, [i]);
    }
    members = [...by.keys()].sort((a, b) => a - b).map((g) => by.get(g)!);
  }
  const out: number[][] = [];
  for (const m of members) for (let k = 0; k < m.length; k += per) out.push(m.slice(k, k + per));
  return out.length ? out : [[]];
}

/** Each page's name: its page level ("2 of 3" after it, when the level has more pages); ""
 * without page columns. In step with `page_labels` in pages.py. */
export function pageLabels(list: number[][], pages: PagesSpec): string[] {
  const groups = pages.groups;
  const levels = pages.levels ?? [];
  if (!groups) return list.map(() => "");
  const first = list.map((p) => (p.length ? (levels[groups[p[0]]] ?? "") : ""));
  return first.map((name, k) => {
    const same = first.flatMap((other, j) => (other === name ? [j] : []));
    return same.length === 1 ? name : `${name} (${same.indexOf(k) + 1} of ${same.length})`;
  });
}
