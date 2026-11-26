// A figure's plots lined up (compose.py: Concat, align): each plot is its own view (a
// widget in a notebook's grid, an embed in a saved page's), so they meet here, by the
// figure's id, on the page's global object (a notebook's widgets may each load the code).
//
// Each view lays itself out three times, each from the step before alone, so the views
// settle where compose.py puts the plots in an image:
//   1. as it is: where its panels would be (`natural`);
//   2. framed: its panels' left and right edges at its column's (the furthest in), their
//      top at its row's (the lowest), and how high its panels are then (`framed`);
//   3. stretched: a plot whose height is free as high as the highest free one in its row.
// A view says what it found (`publish`); when that changes the others lay themselves out
// again. Positions are in the plot's cell, CSS px from its top left (right: from its right).
//
// A view lines up only with those beside it on the page: in its row, those whose cells start
// at the same height; in its column, those whose cells start as far left and are as wide.
// A plot shown alone before it was put in a figure has one widget, so its view there is told
// the same place in the figure: it is lined up with nothing, as no cell is beside it.
import type { Frame } from "./layout";

/** A plot's place in a figure (Concat._cell). */
export interface FigureCell {
  group: string;
  row: number;
  col: number;
}

/** A plot's place in a figure, as Python tells it (Concat._places): its cell to line up in
 * (none: not lined up), and the figure that shows its legends (none: its own). */
export interface FigurePlace {
  group?: string;
  row?: number;
  col?: number;
  legend?: string;
  order?: number;
}

/** Where a plot's panels are in its cell, as it is alone; `free`: its height may grow. */
export interface Natural {
  left: number;
  top: number;
  right: number;
  height: number;
  free: boolean;
}

/** Where a plot's cell is on the page (getBoundingClientRect: left, top and width). */
export interface CellBox {
  x: number;
  y: number;
  w: number;
}

interface Member {
  cell: FigureCell;
  box: CellBox | null;
  natural: Natural | null;
  /** Its panels' height when framed, or null: not yet laid out. */
  framed: number | null;
  redo: () => void;
}

interface Group {
  members: Set<Member>;
  pending: boolean;
  /** Relayouts asked for in a row without settling: a guard against going round forever. */
  rounds: number;
}

const near = (a: number, b: number): boolean => Math.abs(a - b) < 1;

function same<T extends object>(a: T | null, b: T | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return (Object.keys(a) as (keyof T)[]).every((k) => a[k] === b[k]);
}

/** How many times a figure's views lay out again in a row before they stop trying. */
const MAX_ROUNDS = 12;

type Registry = Map<string, Group>;

function registry(): Registry {
  const g = globalThis as { anytrellisFigures?: Registry };
  return (g.anytrellisFigures ??= new Map());
}

/** A view's part in a figure. */
export class FigureMember {
  private readonly member: Member;
  private readonly group: Group;

  constructor(cell: FigureCell, redo: () => void) {
    const groups = registry();
    let group = groups.get(cell.group);
    if (!group) groups.set(cell.group, (group = { members: new Set(), pending: false, rounds: 0 }));
    this.group = group;
    this.member = { cell, box: null, natural: null, framed: null, redo };
    group.members.add(this.member);
  }

  get cell(): FigureCell {
    return this.member.cell;
  }

  /** Step 1: where its panels are as it is, its cell at `box` (null: it isn't lined up now,
   * a panel opened). */
  setNatural(natural: Natural | null, box: CellBox | null = null): void {
    const own = this.member;
    if (same(own.natural, natural) && same(own.box, box)) return;
    own.natural = natural;
    own.box = natural && box;
    if (!natural) own.framed = null;
    this.changed();
  }

  /** The members lined up with it: beside it in its row (`"row"`) or its column. */
  private peers(along: "row" | "col"): Member[] {
    const own = this.member;
    const a = own.box;
    if (!a || !own.natural) return [];
    return [...this.group.members].filter((m) => {
      const b = m.box;
      if (!b || !m.natural || m.cell[along] !== own.cell[along]) return false;
      return along === "row" ? near(a.y, b.y) : near(a.x, b.x) && near(a.w, b.w);
    });
  }

  /** Its frame: its column's edges and its row's top (in its cell), or null: none known. */
  frame(): Frame | null {
    const own = this.member.natural;
    if (!own) return null;
    let { left, top, right } = own;
    for (const m of this.peers("col")) {
      left = Math.max(left, m.natural!.left);
      right = Math.max(right, m.natural!.right);
    }
    for (const m of this.peers("row")) top = Math.max(top, m.natural!.top);
    return { left, top, right };
  }

  /** Step 2: its panels' height, framed. */
  setFramed(height: number): void {
    if (this.member.framed === height) return;
    this.member.framed = height;
    this.changed();
  }

  /** Step 3: how high its panels go (the highest free plot's of its row), or null: as framed. */
  target(): number | null {
    const own = this.member;
    if (!own.natural?.free || own.framed === null) return null;
    let most = own.framed;
    for (const m of this.peers("row")) if (m.natural!.free && m.framed !== null) most = Math.max(most, m.framed);
    return most;
  }

  leave(): void {
    this.group.members.delete(this.member);
    if (!this.group.members.size) registry().delete(this.member.cell.group);
    else this.changed();
  }

  /** The others lay out again, once for every change made in this task. */
  private changed(): void {
    const group = this.group;
    if (group.pending) return;
    group.pending = true;
    setTimeout(() => {
      group.pending = false;
      if (++group.rounds > MAX_ROUNDS) return;
      for (const m of group.members) m.redo();
      // settled: the relayouts (done at once) changed nothing
      if (!group.pending) group.rounds = 0;
    }, 0);
  }
}
