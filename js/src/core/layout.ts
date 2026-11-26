// Where everything sits: panels on a grid, with gutters only where an axis is drawn.
//
// A panel draws its x axis when the cell below it is empty or in another x scale group, and
// its y axis when the cell to its left is empty or in another y group; so shared scales
// label only the outer panels, and free scales label every panel. An axis next to an empty
// cell (a wrap's last row, a grid's missing combination) draws into that cell, so it takes no
// gutter: the rows and columns stay evenly spaced. A wrap puts a strip over
// every panel; a grid puts its column labels over the top row and its row labels to the
// right of the last column. With several facet columns, strips nest: a strip per column,
// the first outermost, each spanning the panels (rows, columns) next to each other that
// share its level and those outside it. With strip_label, every panel (a grid's too) has a
// strip of its own naming it, and there are no others.
//
// The look (look.ts) sets the gap between panels, whether the y title sits over the plot at
// its left or on its side, where the x title goes, and whether a grid's row labels are level
// (as wide as they need) or on their side.

import { lookOf } from "./look";
import { pageList } from "./pages";
import { ticks, yTickCount } from "./ticks";
import type { TrellisSpec } from "./types";

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PanelBox {
  /** The panel's index in spec.panels. */
  index: number;
  rect: Rect;
  showX: boolean;
  showY: boolean;
  /** A strip over the panel (a wrap's, or an opened panel's), and its label. */
  strip: Rect | null;
  label: string;
  /** A paged wrap's value of the statistic sorted by, at the strip's right end. */
  note?: string;
  /** Pinned first on every page: a pin at its strip's left. */
  pinned?: boolean;
  /** Where its x and y axes are drawn (tick labels included), or null: the pointer zooms
   * and pans one axis there. */
  xAxis: Rect | null;
  yAxis: Rect | null;
}

export interface Strip {
  rect: Rect;
  label: string;
  /** Its text turned on its side (the classic theme's row strips). */
  vertical: boolean;
  /** Over the columns (`top`: a grid's columns, a wrap's outer levels) or right of the rows. */
  side: "top" | "right";
  /** It spans several panels (a nested strip's outer level). */
  span: boolean;
  /** A pinned panel's: a pin before its label. */
  pin?: boolean;
}

export interface Layout {
  width: number;
  height: number;
  panels: PanelBox[];
  /** A grid's column and row strips. */
  strips: Strip[];
  title: { x: number; y: number } | null;
  xTitle: { x: number; y: number } | null;
  yTitle: { x: number; y: number } | null;
  /** A wrap's empty cells after its last panel, less the axes drawn into them: the legend's
   * place, or null. */
  spare: Rect | null;
  /** Tick labels' height (x) and the y labels' width per column. */
  xAxisHeight: number;
  /** How a band x axis sets its labels (others: flat). */
  xLabels: XLabels;
  yAxisWidth: number[];
  /** The panels' text size (px): the look's, or stepped with the panels' width. */
  fontSize: number;
}

export interface LayoutOptions {
  width: number;
  /** The text's size (px), as `measure` measures it. */
  fontSize: number;
  measure: (text: string) => number;
  /** The plot's height (px), overriding the spec's (full screen, an opened panel). */
  height?: number | null;
  /** The panel opened (index in spec.panels): it alone, on the whole width. */
  focused?: number | null;
  /** Draw the title in the canvas (false: the page shows it). */
  title?: boolean;
  /** A paged wrap's panels on the page shown (indices in spec.panels, in order; default:
   * the first page's). */
  page?: number[] | null;
  /** Where the panels' box goes, lined up with other plots' in a figure (align.ts). */
  frame?: Frame | null;
}

/** The panels' box (not their strips or axes) lined up with other plots' in a figure: its
 * left edge at least at `left`, its top at least at `top`, and its right edge `right` px
 * from the plot's right, or further if it must (figure.py: Frame). */
export interface Frame {
  left: number;
  top: number;
  right: number;
}

/** The box of a layout's panels (not their strips or axes): what a figure lines up. */
export function panelsBox(lay: Layout): Rect {
  const rects = lay.panels.map((b) => b.rect);
  if (!rects.length) return { x: 0, y: 0, w: 0, h: 0 };
  const x0 = Math.min(...rects.map((r) => r.x));
  const y0 = Math.min(...rects.map((r) => r.y));
  const x1 = Math.max(...rects.map((r) => r.x + r.w));
  const y1 = Math.max(...rects.map((r) => r.y + r.h));
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** The cell (row, column) of a wrap's `k`-th panel, filled as `dir` says (facets.py: place). */
export function place(k: number, rows: number, cols: number, dir = "lt"): [number, number] {
  const [first, then] = dir;
  if (first === "l" || first === "r") {
    const run = Math.floor(k / cols);
    const at = k % cols;
    return [then === "t" ? run : rows - 1 - run, first === "l" ? at : cols - 1 - at];
  }
  const run = Math.floor(k / rows);
  const at = k % rows;
  return [first === "t" ? at : rows - 1 - at, then === "l" ? run : cols - 1 - run];
}

/** A panel's name: its level of each facet column. */
export function panelName(spec: TrellisSpec, index: number): string {
  const p = spec.panels[index];
  return p.keys.join(" · ") || p.label || `panel ${index + 1}`;
}

const TICK = 4;
const MIN_PANEL = 24;
/** A strip's room at either end, and between a name and its value. */
export const STRIP_PAD = 4;
/** The widest a minimal theme's row label gets (px); a longer one is cut. */
const ROW_LABEL_MAX = 120;
/** Strip text is semibold: about this much wider than measured. */
export const BOLD = 1.06;

/** How x labels are set: side by side (`flat`, thinned when they don't fit), on two lines
 * (`wrap`), or at 45 degrees (`angle`). Categories too long to sit side by side take the
 * first of wrap and angle that shows every one of them. */
export type XLabels = "flat" | "wrap" | "angle";

/** The longest an angled label gets (px); a longer one is cut. */
export const ANGLE_MAX = 90;

/** A label on two lines, split at the space nearest its middle (one line: no space). */
export function wrapLabel(label: string): string[] {
  let best = -1;
  for (let i = label.indexOf(" "); i >= 0; i = label.indexOf(" ", i + 1)) {
    if (best < 0 || Math.abs(i - label.length / 2) < Math.abs(best - label.length / 2)) best = i;
  }
  return best < 0 ? [label] : [label.slice(0, best), label.slice(best + 1)];
}

/** How a band x axis `panelW` px wide sets its labels, and the axis's height. Side by side
 * when the longest fits its band (estimated as the ticks thin them: 0.6 em a character);
 * else on two lines when each fits its band, measured; else at 45 degrees. */
export function xLabelMode(spec: TrellisSpec, panelW: number, opts: Pick<LayoutOptions, "fontSize" | "measure">): { mode: XLabels; height: number } {
  const fs = opts.fontSize;
  const flat = fs + TICK + 6;
  const levels = spec.x.kind === "band" ? spec.x.levels : null;
  if (!levels?.length) return { mode: "flat", height: flat };
  const per = panelW / levels.length;
  const longest = Math.max(...levels.map((l) => l.length));
  if (longest * 0.6 * fs + 10 <= per) return { mode: "flat", height: flat };
  const fits = (t: string): boolean => opts.measure(t) + 4 <= per;
  if (levels.every((l) => fits(l) || wrapLabel(l).every(fits))) return { mode: "wrap", height: flat + Math.round(fs * 1.2) };
  const widest = Math.min(ANGLE_MAX, Math.max(...levels.map((l) => opts.measure(l))));
  return { mode: "angle", height: Math.ceil((widest + fs) * Math.SQRT1_2) + TICK + 6 };
}

/** The width of the column left of the plot holding the y title on its side, or the height
 * of the line over the plot holding it level. */
function yTitleRoom(spec: TrellisSpec, fs: number): { w: number; h: number } {
  if (!spec.y.title) return { w: 0, h: 0 };
  return lookOf(spec).y_title === "side" ? { w: Math.round(fs * 1.4 + 4), h: 0 } : { w: 0, h: Math.round(fs * 1.4 + 2) };
}

/** The panels' shape, height over width, that full screen and an opened panel keep: the
 * spec's aspect, unless its height or panel_height sets their height instead. */
export function panelShape(spec: TrellisSpec): number | null {
  return spec.aspect && !spec.height && !spec.panel_height ? spec.aspect : null;
}

/** Under this width (px, at 12 px text) panels step their text down a pixel. */
export const NARROW = 160;

/** The plot's layout. With the look's `font_step` ("auto" text), the panels' text steps
 * from the page's size (12 px, the context applied): to 11/12 of it when panels would be
 * under `NARROW` px wide (a paged wrap's: those of its first page, so every page, even an
 * empty one, has the same), to 13/12 in an opened panel. */
export function layout(spec: TrellisSpec, opts: LayoutOptions): Layout {
  const focused = opts.focused !== null && opts.focused !== undefined && !!spec.panels[opts.focused];
  const at = (fs: number, page = opts.page): Layout => {
    const measure = fs === opts.fontSize ? opts.measure : (t: string) => (opts.measure(t) * fs) / opts.fontSize;
    const o = { ...opts, fontSize: fs, measure, page };
    return { ...(focused ? focusLayout(spec, o, opts.focused!) : layoutAt(spec, o)), fontSize: fs };
  };
  const base = opts.fontSize;
  if (!lookOf(spec).font_step) return at(base);
  if (focused) return at((base * 13) / 12);
  const lay = at(base);
  const probe = opts.page ? at(base, null) : lay;
  const narrowest = Math.min(...probe.panels.map((b) => b.rect.w));
  return narrowest < (NARROW * base) / 12 ? at((base * 11) / 12) : lay;
}

function layoutAt(spec: TrellisSpec, opts: LayoutOptions): Omit<Layout, "fontSize"> {
  const { grid } = spec;
  // a paged wrap: the page's panels, placed in turn on a grid of the page's size (the same
  // on every page, so turning pages does not move the plot)
  const pages = spec.pages ?? null;
  const shown = pages ? (opts.page ?? pageList(spec.panels.map((_, i) => i), pages)[0]) : null;
  // (a grid's page: each panel in its cell)
  const panels = shown
    ? shown.map((index, k) => {
        if (pages!.grid) return spec.panels[index];
        const [row, col] = place(k, pages!.rows, pages!.cols, grid.dir);
        return { ...spec.panels[index], row, col };
      })
    : spec.panels;
  const fs = opts.fontSize;
  const look = lookOf(spec);
  const GAP = look.panel_gap;
  const rows = Math.max(1, pages ? pages.rows : grid.rows);
  const cols = Math.max(1, pages ? pages.cols : grid.cols);
  const at = new Map<string, number>();
  panels.forEach((p, i) => at.set(`${p.row},${p.col}`, i));
  const cell = (r: number, c: number): number | undefined => at.get(`${r},${c}`);

  const showX = panels.map((p) => {
    const below = cell(p.row + 1, p.col);
    return below === undefined || panels[below].xg !== p.xg;
  });
  const showY = panels.map((p) => {
    const left = cell(p.row, p.col - 1);
    return left === undefined || panels[left].yg !== p.yg;
  });

  // y labels' width per column, from the ticks of the panels that draw a y axis; not those
  // with an empty cell on their left, whose labels go in that cell
  const yLabelWidth = panels.map((p, i) => (showY[i] ? yLabelsWidth(spec, p.y, opts, null) : 0));
  const yAxisWidth = new Array<number>(cols).fill(0);
  const yGutters = () => {
    yAxisWidth.fill(0);
    panels.forEach((p, i) => {
      if (!showY[i] || (p.col > 0 && cell(p.row, p.col - 1) === undefined)) return;
      yAxisWidth[p.col] = Math.max(yAxisWidth[p.col], yLabelWidth[i]);
    });
  };
  yGutters();
  let xAxisHeight = fs + TICK + 6;
  let xLabels: XLabels = "flat";
  const rowHasX = new Array<boolean>(rows).fill(false);
  panels.forEach((p, i) => {
    if (showX[i] && (p.row === rows - 1 || cell(p.row + 1, p.col) !== undefined)) rowHasX[p.row] = true;
  });
  if (pages) rowHasX[rows - 1] = true; // a short last page keeps the full pages' height

  const stripH = Math.round(fs * 1.5 + 4);
  const nested = grid.strips !== "joined";
  const own = !!grid.strip_label; // each panel's own strip, and no others
  const from = grid.strip_from ?? 0;
  const depth = (keys: string[][] | undefined): number => (nested ? Math.max(1, keys?.[0]?.length ?? 1) : 1);
  const wrapDepth = own ? 1 : grid.kind === "wrap" ? depth(panels.length ? [panels[0].keys.slice(from)] : undefined) : 0;
  const colDepth = !own && grid.kind === "grid" && grid.col_labels.length ? depth(grid.col_keys) : 0;
  const rowDepth = !own && grid.kind === "grid" && grid.row_labels.length ? depth(grid.row_keys) : 0;
  const wrapStrip = wrapDepth * stripH;
  const topStrip = colDepth * stripH;
  // the row strips' widths, outermost level first: on their side, a strip's height; level,
  // as wide as their longest label
  const rowW: number[] = [];
  for (let k = 0; k < rowDepth; k++) {
    if (look.row_labels === "side") rowW.push(stripH);
    else {
      const labels = rowDepth === 1 ? grid.row_labels : (grid.row_keys ?? []).map((keys) => keys[k]);
      const widest = Math.max(0, ...labels.map((l) => opts.measure(l)));
      rowW.push(Math.min(ROW_LABEL_MAX, Math.ceil(widest * (look.strip_bold ? BOLD : 1)) + 2 * STRIP_PAD + 4));
    }
  }
  const rightStrip = rowW.reduce((a, b) => a + b, 0);
  const titleH = spec.title && opts.title !== false ? Math.round(fs * 1.6 + 6) : 0;
  const xTitleH = spec.x.title ? Math.round(fs * 1.4 + 4) : 0;
  const yTitle = yTitleRoom(spec, fs);
  // in a figure (frame): the panels' box moved right and down, and its right edge in, to
  // line up with the other plots'
  const frame = opts.frame ?? null;
  const leftMost = 4 + yTitle.w;
  let left = leftMost;
  const right = frame ? Math.max(10, frame.right - rightStrip - (rightStrip ? GAP : 0)) : 10;
  const top = Math.max(6 + titleH + yTitle.h, frame ? frame.top - topStrip - wrapStrip : 0);
  const bottom = 4 + xTitleH;
  const lineUp = (): void => {
    if (frame) left = Math.max(leftMost, frame.left - yAxisWidth[0]);
  };
  lineUp();

  let axisRows = rowHasX.reduce((a, b) => a + (b ? xAxisHeight : 0), 0);
  const shape = panelShape(spec);
  // the width the panels share
  const freeWidth = (): number => {
    const gutters = yAxisWidth.reduce((a, b) => a + b, 0);
    return opts.width - left - right - gutters - (cols - 1) * GAP - rightStrip - (rightStrip ? GAP : 0);
  };
  const panelSize = (): [number, number] => {
    let w = Math.max(MIN_PANEL, Math.floor(freeWidth() / cols));
    let h: number;
    if (opts.height) {
      h = (opts.height - top - bottom - topStrip - axisRows - rows * wrapStrip - (rows - 1) * GAP) / rows;
      // the panels' shape kept, as large as fits: narrower when the height is too low for it
      if (shape && w * shape <= h) h = w * shape;
      else if (shape) w = Math.max(MIN_PANEL, Math.floor(h / shape));
    } else if (spec.panel_height) h = spec.panel_height;
    else if (spec.height) h = (spec.height - top - bottom - topStrip - axisRows - rows * wrapStrip - (rows - 1) * GAP) / rows;
    else if (spec.aspect) h = w * spec.aspect;
    else h = Math.min(300, Math.max(90, w * 0.62));
    return [w, Math.max(MIN_PANEL, Math.floor(h))];
  };
  // space=: each column's share of the width by its x range, each row's of the height by
  // its y range (the widest panel's of a column, the highest's of a row)
  const span = (d: [number, number]): number => Math.max(1e-12, Math.abs(d[1] - d[0]));
  const colSpan = new Array<number>(cols).fill(0);
  const rowSpan = new Array<number>(rows).fill(0);
  panels.forEach((p) => {
    colSpan[p.col] = Math.max(colSpan[p.col], span(p.x));
    rowSpan[p.row] = Math.max(rowSpan[p.row], span(p.y));
  });
  const shares = (spans: number[], on: boolean | undefined): number[] => {
    const known = spans.filter((s) => s > 0);
    const mean = known.length ? known.reduce((a, b) => a + b, 0) / known.length : 1;
    const of = spans.map((s) => (on ? s || mean : 1));
    const sum = of.reduce((a, b) => a + b, 0);
    return of.map((s) => (s * of.length) / sum);
  };
  const colShare = shares(colSpan, spec.space?.x);
  const rowShare = shares(rowSpan, spec.space?.y);
  const sizes = (w: number, h: number): [number[], number[]] => [colShare.map((s) => Math.max(MIN_PANEL, Math.floor(w * s))), rowShare.map((s) => Math.max(MIN_PANEL, Math.floor(h * s)))];
  // the panels' height sets how many y ticks they draw (finer steps, longer labels: 500M
  // between 0 and 1.0G), and it can follow their width, which follows the labels: so size
  // them, measure the labels drawn at that height, keep the wider, and size them again
  let [pw, ph] = panelSize();
  let [colW, rowH] = sizes(pw, ph);
  panels.forEach((p, i) => {
    if (showY[i]) yLabelWidth[i] = Math.max(yLabelWidth[i], yLabelsWidth(spec, p.y, opts, rowH[p.row]));
  });
  yGutters();
  lineUp();
  [pw, ph] = panelSize();
  [colW, rowH] = sizes(pw, ph);
  // categories that don't fit side by side: on two lines or angled, the axis as high as that
  // (space="free_x": every band as wide, the narrowest of them all otherwise)
  const bandsW = spec.space?.x && spec.x.levels ? (pw * cols * spec.x.levels.length) / colSpan.reduce((a, b) => a + b, 0) : pw;
  ({ mode: xLabels, height: xAxisHeight } = xLabelMode(spec, bandsW, opts));
  if (xLabels !== "flat") {
    axisRows = rowHasX.reduce((a, b) => a + (b ? xAxisHeight : 0), 0);
    [pw, ph] = panelSize();
    [colW, rowH] = sizes(pw, ph);
  }
  // in a figure: the pixels the panels' widths rounded off, a pixel more to the first
  // columns, so the right edge lines up to the pixel
  if (frame && !shape) {
    const spare = Math.floor(freeWidth() - colW.reduce((a, b) => a + b, 0));
    for (let c = 0; c < Math.min(spare, cols); c++) colW[c] += 1;
  }
  // panels narrowed to keep their shape: the grid centred
  const shift = Math.max(0, Math.floor((freeWidth() - colW.reduce((a, b) => a + b, 0)) / 2));

  const colX: number[] = [];
  let x = left + shift;
  for (let c = 0; c < cols; c++) {
    x += yAxisWidth[c];
    colX.push(x);
    x += colW[c] + GAP;
  }
  const rowY: number[] = [];
  let y = top + topStrip;
  for (let r = 0; r < rows; r++) {
    y += wrapStrip;
    rowY.push(y);
    y += rowH[r] + (rowHasX[r] ? xAxisHeight : 0) + GAP;
  }
  const plotBottom = y - GAP;
  const plotRight = colX[cols - 1] + colW[cols - 1];

  const boxes: PanelBox[] = panels.map((p, i) => {
    const pw = colW[p.col];
    const ph = rowH[p.row];
    const rect = { x: colX[p.col], y: rowY[p.row], w: pw, h: ph };
    return {
      index: shown ? shown[i] : i,
      rect,
      showX: showX[i],
      showY: showY[i],
      // a wrap's own strip: its innermost level's (the outer levels': strips over it)
      strip: wrapStrip ? { x: rect.x, y: rect.y - stripH, w: pw, h: stripH - 1 } : null,
      label: own ? (p.strip ?? p.label) : wrapDepth > 1 ? p.keys[p.keys.length - 1] : p.label,
      xAxis: showX[i] ? { x: rect.x, y: rect.y + ph, w: pw, h: xAxisHeight } : null,
      yAxis: showY[i] ? { x: rect.x - yLabelWidth[i], y: rect.y, w: yLabelWidth[i], h: ph } : null,
    };
  });

  const strips: Strip[] = [];
  if (colDepth === 1) {
    grid.col_labels.forEach((label, c) => {
      strips.push({ rect: { x: colX[c], y: top, w: colW[c], h: stripH - 1 }, label, vertical: false, side: "top", span: false });
    });
  } else if (colDepth > 1) {
    for (const [k, a, b] of nest(grid.col_keys ?? [], colDepth)) {
      const x0 = colX[a];
      strips.push({ rect: { x: x0, y: top + k * stripH, w: colX[b] + colW[b] - x0, h: stripH - 1 }, label: grid.col_keys![a][k], vertical: false, side: "top", span: b > a });
    }
  }
  const vertical = look.row_labels === "side";
  // a row level's strips: right of the inner levels' (the first column's outermost)
  const rowX = (k: number): number => plotRight + GAP + rowW.slice(k + 1).reduce((a, b) => a + b, 0);
  if (rowDepth === 1) {
    grid.row_labels.forEach((label, r) => {
      strips.push({ rect: { x: rowX(0), y: rowY[r], w: rowW[0] - 1, h: rowH[r] }, label, vertical, side: "right", span: false });
    });
  } else if (rowDepth > 1) {
    for (const [k, a, b] of nest(grid.row_keys ?? [], rowDepth)) {
      strips.push({ rect: { x: rowX(k), y: rowY[a], w: rowW[k] - 1, h: rowY[b] + rowH[b] - rowY[a] }, label: grid.row_keys![a][k], vertical, side: "right", span: b > a });
    }
  }
  if (wrapDepth > 1) {
    // each row's panels side by side, by column: the outer levels' strips over those sharing them
    for (let r = 0; r < rows; r++) {
      const inRow = panels.filter((p) => p.row === r).sort((p, q) => p.col - q.col);
      const runs: number[][] = [];
      inRow.forEach((p, i) => {
        if (i && p.col === inRow[i - 1].col + 1) runs[runs.length - 1].push(i);
        else runs.push([i]);
      });
      for (const run of runs) {
        const keys = run.map((i) => inRow[i].keys.slice(from));
        for (const [k, a, b] of nest(keys, wrapDepth - 1)) {
          const x0 = colX[inRow[run[a]].col];
          const x1 = colX[inRow[run[b]].col] + colW[inRow[run[b]].col];
          strips.push({ rect: { x: x0, y: rowY[r] - wrapStrip + k * stripH, w: x1 - x0, h: stripH - 1 }, label: keys[a][k], vertical: false, side: "top", span: b > a });
        }
      }
    }
  }

  // the empty cells after a wrap's last panel, below the axes of the panels above them
  let spare: Rect | null = null;
  if (grid.kind === "wrap" && panels.length && !pages) {
    const last = rows - 1;
    const used = panels.filter((p) => p.row === last).reduce((a, p) => Math.max(a, p.col + 1), 0);
    if (used > 0 && used < cols) {
      const sx = colX[used] - yAxisWidth[used] + 8;
      const sy = last > 0 ? rowY[last - 1] + rowH[last - 1] + xAxisHeight + GAP : rowY[last] - wrapStrip;
      const sb = rowY[last] + rowH[last];
      if (plotRight - sx >= 60 && sb - sy >= 30) spare = { x: sx, y: sy, w: plotRight - sx, h: sb - sy };
    }
  }

  const centreX = (colX[0] + plotRight) / 2;
  const centreY = (top + topStrip + plotBottom) / 2;
  const height = Math.ceil(plotBottom + bottom + 2);
  return {
    width: opts.width,
    height,
    panels: boxes,
    strips,
    title: titleH ? { x: left, y: 6 + fs * 1.2 } : null,
    xTitle: xTitleH ? { x: look.x_title === "end" ? plotRight : centreX, y: plotBottom + xTitleH - 2 } : null,
    yTitle: yTitle.w ? { x: left - leftMost + shift + 4 + fs, y: centreY } : yTitle.h ? { x: left + shift, y: top - yTitle.h / 2 } : null,
    spare,
    xAxisHeight,
    xLabels,
    yAxisWidth,
  };
}

/** Nested strips: for each of the first `depth` levels, the runs of items in turn whose
 * levels up to it are the same, as [level, first, last]. */
export function nest(keys: string[][], depth: number): [number, number, number][] {
  const out: [number, number, number][] = [];
  for (let k = 0; k < depth; k++) {
    let a = 0;
    for (let i = 1; i <= keys.length; i++) {
      const same = i < keys.length && keys[i].slice(0, k + 1).every((v, j) => v === keys[a][j]);
      if (same) continue;
      out.push([k, a, i - 1]);
      a = i;
    }
  }
  return out;
}

/** The width of a y axis (labels and ticks) over `domain`, with the ticks a panel `h` px high
 * draws (null: about 5); bands: every label measured. */
function yLabelsWidth(spec: TrellisSpec, domain: [number, number], opts: LayoutOptions, h: number | null): number {
  const count = spec.y.kind === "band" ? 1000 : h === null ? 5 : yTickCount(spec.y.kind, domain[0], domain[1], h);
  const labels = ticks(spec.y.kind, domain[0], domain[1], spec.y.origin, count, spec.y.levels, spec.y.format);
  return Math.ceil(Math.max(0, ...labels.map((t) => opts.measure(t.label)))) + TICK + 4;
}

/** One panel on the whole width, with both its axes and a strip naming it. */
function focusLayout(spec: TrellisSpec, opts: LayoutOptions, index: number): Omit<Layout, "fontSize"> {
  const fs = opts.fontSize;
  const p = spec.panels[index];
  const stripH = Math.round(fs * 1.5 + 4);
  const titleH = spec.title && opts.title !== false ? Math.round(fs * 1.6 + 6) : 0;
  const xTitleH = spec.x.title ? Math.round(fs * 1.4 + 4) : 0;
  const yTitle = yTitleRoom(spec, fs);
  const left = 4 + yTitle.w;
  const right = 10;
  const top = 6 + titleH + yTitle.h;
  const bottom = 4 + xTitleH;
  const total = opts.height ?? 360;
  const { mode: xLabels, height: xAxisHeight } = xLabelMode(spec, opts.width - left - right - yLabelsWidth(spec, p.y, opts, null), opts);
  const most = Math.max(MIN_PANEL, Math.floor(total - top - stripH - xAxisHeight - bottom - 2));
  let h = most;
  let yW = yLabelsWidth(spec, p.y, opts, h);
  let w = Math.max(MIN_PANEL, opts.width - left - yW - right);
  let shift = 0;
  const shape = panelShape(spec);
  if (shape) {
    // the panel's shape, as large as fits the height given: on the whole width, or
    // narrower and centred
    const fit = (): void => {
      const room = Math.max(MIN_PANEL, opts.width - left - yW - right);
      [w, h] = room * shape <= most ? [room, Math.max(MIN_PANEL, Math.floor(room * shape))] : [Math.max(MIN_PANEL, Math.floor(most / shape)), most];
      shift = Math.max(0, Math.floor((room - w) / 2));
    };
    fit();
    yW = yLabelsWidth(spec, p.y, opts, h); // the ticks the panel's height draws
    fit();
  }
  const rect = { x: left + shift + yW, y: top + stripH, w, h };
  const plotBottom = rect.y + h + xAxisHeight;
  return {
    width: opts.width,
    height: Math.ceil(plotBottom + bottom + 2),
    panels: [
      {
        index,
        rect,
        showX: true,
        showY: true,
        strip: { x: rect.x, y: top, w, h: stripH - 1 },
        label: p.strip ?? panelName(spec, index),
        xAxis: { x: rect.x, y: rect.y + h, w, h: xAxisHeight },
        yAxis: { x: rect.x - yW, y: rect.y, w: yW, h },
      },
    ],
    strips: [],
    title: titleH ? { x: left, y: 6 + fs * 1.2 } : null,
    xTitle: xTitleH ? { x: lookOf(spec).x_title === "end" ? rect.x + w : rect.x + w / 2, y: plotBottom + xTitleH - 2 } : null,
    yTitle: yTitle.w ? { x: shift + 4 + fs, y: rect.y + h / 2 } : yTitle.h ? { x: left + shift, y: 6 + titleH + yTitle.h / 2 } : null,
    spare: null,
    xAxisHeight,
    xLabels,
    yAxisWidth: [yW],
  };
}
