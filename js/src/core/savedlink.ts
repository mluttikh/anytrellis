// Plots linked in a saved page (Link.save_html), with no Python to relay the selection.
// Each mark carries the keys of its rows (linking.py: saved_links): a plain mark its row's
// (a line's piece also its end's), a summary's mark the keys of the rows it stands for. A
// selection in one plot chooses the keys of its selected marks' rows; the others highlight
// the marks whose rows have a key chosen, a histogram's bar filled to the share of its rows
// chosen: what Python's link would send them (linking.py: highlight_message).

import type { Highlight } from "./selection";

/** A plot's link in a saved page, as Python writes it: per spec layer, base64 uint32. */
export interface SavedLink {
  group: string;
  /** Keys are below this. */
  size: number;
  layers: (SavedLinkLayer | null)[];
}

export interface SavedLinkLayer {
  keys?: string;
  ends?: string | null;
  starts?: string;
  members?: string;
  share?: boolean;
}

/** A layer's keys, read. */
export interface LinkKeys {
  /** A plain mark's row's key, and a line piece's end's. */
  keys?: Uint32Array;
  ends?: Uint32Array | null;
  /** A summary's mark: the keys of its rows, members[starts[i]..starts[i + 1]]. */
  starts?: Uint32Array;
  members?: Uint32Array;
  /** A histogram's bar: filled to the share of its rows chosen. */
  share?: boolean;
}

function uint32(b64: string): Uint32Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Uint32Array(bytes.buffer, 0, bytes.length >> 2);
}

export function readLink(link: SavedLink): (LinkKeys | null)[] {
  return link.layers.map((l) => {
    if (!l) return null;
    if (l.members !== undefined && l.starts !== undefined) return { starts: uint32(l.starts), members: uint32(l.members), share: !!l.share };
    if (l.keys !== undefined) return { keys: uint32(l.keys), ends: l.ends ? uint32(l.ends) : null };
    return null;
  });
}

/** The keys a selection chooses: those of the rows of its selected marks (`masks`: per spec
 * layer, 1 where a mark is selected), as a set of `size` flags. */
export function chosenKeys(layers: (LinkKeys | null)[], masks: (Uint8Array | null)[], size: number): Uint8Array {
  const chosen = new Uint8Array(size);
  layers.forEach((l, li) => {
    const m = masks[li];
    if (!l || !m) return;
    for (let i = 0; i < m.length; i++) {
      if (!m[i]) continue;
      if (l.keys) {
        chosen[l.keys[i]] = 1;
        if (l.ends) chosen[l.ends[i]] = 1;
      } else if (l.starts && l.members) {
        for (let j = l.starts[i]; j < l.starts[i + 1]; j++) chosen[l.members[j]] = 1;
      }
    }
  });
  return chosen;
}

/** What the keys chosen highlight in a plot: per spec layer, its marks with a row chosen
 * (a histogram's bars: the share of their rows chosen); null: a layer not linked. */
export function linkHighlight(layers: (LinkKeys | null)[], chosen: Uint8Array): Highlight {
  return {
    layers: layers.map((l) => {
      if (!l) return null;
      if (l.keys) {
        const mask = new Uint8Array(l.keys.length);
        for (let i = 0; i < mask.length; i++) mask[i] = chosen[l.keys[i]] || (l.ends ? chosen[l.ends[i]] : 0) ? 1 : 0;
        return { mask };
      }
      const starts = l.starts!;
      const members = l.members!;
      const n = starts.length - 1;
      const fraction = new Float32Array(n);
      const mask = new Uint8Array(n);
      for (let i = 0; i < n; i++) {
        let hit = 0;
        for (let j = starts[i]; j < starts[i + 1]; j++) hit += chosen[members[j]];
        const size = starts[i + 1] - starts[i];
        fraction[i] = size ? hit / size : 0;
        mask[i] = hit ? 1 : 0;
      }
      return l.share ? { fraction } : { mask };
    }),
  };
}

/** The plots of one link on a page. One plot's selection leads: the others' brushes go, and
 * they highlight its keys; a plot that starts later (near the screen) is highlighted too. */
export interface LinkedView {
  /** Its own selection's marks per spec layer, or null: nothing of its own selected. */
  ownSelection(): (Uint8Array | null)[] | null;
  setSelection(brush: null): void;
  setHighlight(h: Highlight | null): void;
}

export class LinkGroup {
  private readonly members = new Map<LinkedView, (LinkKeys | null)[]>();
  private source: LinkedView | null = null;
  private chosen: Uint8Array | null = null;

  constructor(private readonly size: number) {}

  add(view: LinkedView, layers: (LinkKeys | null)[]): void {
    this.members.set(view, layers);
    if (this.chosen && view !== this.source) view.setHighlight(linkHighlight(layers, this.chosen));
  }

  /** `view`'s own selection changed (a brush, a lasso, a click, a legend entry). */
  changed(view: LinkedView): void {
    const layers = this.members.get(view);
    if (!layers) return;
    const masks = view.ownSelection();
    if (!masks) {
      if (view === this.source) this.clear();
      return;
    }
    this.source = view;
    this.chosen = chosenKeys(layers, masks, this.size);
    for (const [other, its] of this.members) {
      if (other === view) {
        other.setHighlight(null);
        continue;
      }
      other.setSelection(null); // one brush in a link
      other.setHighlight(linkHighlight(its, this.chosen));
    }
  }

  /** Nothing selected in any plot of the link. */
  clear(): void {
    this.source?.setSelection(null);
    this.source = null;
    this.chosen = null;
    for (const view of this.members.keys()) view.setHighlight(null);
  }
}
