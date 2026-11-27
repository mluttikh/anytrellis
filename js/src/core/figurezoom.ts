// A figure's plots that share a range zoom together (compose.py: Shared, share_x/share_y).
// Each plot is its own view, so they meet here, on the page's global object (as align.ts's
// figures do), by the range's key: the spec's axis `joined` (the figure's id, the axis, its
// group) and the range itself, so a range Python changes starts again from there.
//
// A view tells the others where its axis is zoomed whenever that differs from where the
// group last was (`tell`); they follow without telling back. Ranges are in the data's own
// units (the view's plus the axis's origin), so plots of different origins agree. A view
// that joins after the others zoomed starts where they are (`at`).

/** An axis's range, in the data's own units (a transformed axis's: in its units). */
export type Span = [number, number];

interface Hub {
  members: Set<ZoomMember>;
  /** Where the group was last zoomed, or null: where it started. */
  at: Span | null;
}

type Registry = Map<string, Hub>;

function registry(): Registry {
  const g = globalThis as { anytrellisZooms?: Registry };
  return (g.anytrellisZooms ??= new Map());
}

/** The same range, but for the rounding of the trip through a view's origin: a billionth
 * of its width, or a few of the last digits of numbers this large (times: ms since 1970). */
export function sameSpan(a: Span, b: Span): boolean {
  const width = Math.max(Math.abs(a[1] - a[0]), Math.abs(b[1] - b[0]));
  const size = Math.max(...a.map(Math.abs), ...b.map(Math.abs));
  const tol = Math.max(1e-9 * width, 8 * Number.EPSILON * size);
  return Math.abs(a[0] - b[0]) <= tol && Math.abs(a[1] - b[1]) <= tol;
}

/** A view's axis in a group of plots that zoom together. */
export class ZoomMember {
  private readonly hub: Hub;

  constructor(
    readonly key: string,
    private readonly follow: (at: Span) => void,
  ) {
    const hubs = registry();
    let hub = hubs.get(key);
    if (!hub) hubs.set(key, (hub = { members: new Set(), at: null }));
    this.hub = hub;
    hub.members.add(this);
  }

  /** Where the group is zoomed, or null: where it started. */
  get at(): Span | null {
    return this.hub.at;
  }

  /** Its axis shows `at`: the others follow, if that is news. */
  tell(at: Span): void {
    const was = this.hub.at;
    if (was && sameSpan(was, at)) return;
    const now: Span = [at[0], at[1]];
    this.hub.at = now;
    for (const m of this.hub.members) if (m !== this) m.follow(now);
  }

  leave(): void {
    this.hub.members.delete(this);
    if (!this.hub.members.size && registry().get(this.key) === this.hub) registry().delete(this.key);
  }
}
