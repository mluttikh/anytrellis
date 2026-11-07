// A paged wrap: which panels a page shows, after the reader's filters and sort. In step with
// `order` in src/anytrellis/pages.py (Trellis.shown_panels, images drawn in Python).

import type { PanelStat, Paging } from "./types";

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

export function pageCount(shown: number, perPage: number): number {
  return Math.max(1, Math.ceil(shown / perPage));
}
