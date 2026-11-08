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
  /** Where its x and y axes are drawn (tick labels included), or null: the pointer zooms
   * and pans one axis there. */
  xAxis: Rect | null;
  yAxis: Rect | null;
}

export interface Strip {
  rect: Rect;
  label: string;
  vertical: boolean;
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
  yAxisWidth: number[];
}

export interface LayoutOptions {
  width: number;
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
}

/** A panel's name: its level of each facet column. */
export function panelName(spec: TrellisSpec, index: number): string {
  const p = spec.panels[index];
  return p.keys.join(" · ") || p.label || `panel ${index + 1}`;
}

const GAP = 6;
const TICK = 4;
const MIN_PANEL = 24;

export function layout(spec: TrellisSpec, opts: LayoutOptions): Layout {
  if (opts.focused !== null && opts.focused !== undefined && spec.panels[opts.focused]) return focusLayout(spec, opts, opts.focused);
  const { grid } = spec;
  // a paged wrap: the page's panels, placed in turn on a grid of the page's size (the same
  // on every page, so turning pages does not move the plot)
  const pages = spec.pages ?? null;
  const shown = pages ? (opts.page ?? pageList(spec.panels.map((_, i) => i), pages)[0]) : null;
  // (a grid's page: each panel in its cell)
  const panels = shown
    ? shown.map((index, k) => (pages!.grid ? spec.panels[index] : { ...spec.panels[index], row: Math.floor(k / pages!.cols), col: k % pages!.cols }))
    : spec.panels;
  const fs = opts.fontSize;
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
  const xAxisHeight = fs + TICK + 6;
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
  const rightStrip = rowDepth * stripH;
  const titleH = spec.title && opts.title !== false ? Math.round(fs * 1.6 + 6) : 0;
  const xTitleH = spec.x.title ? Math.round(fs * 1.4 + 4) : 0;
  const yTitleW = spec.y.title ? Math.round(fs * 1.4 + 4) : 0;
  const left = 4 + yTitleW;
  const right = 10;
  const top = 6 + titleH;
  const bottom = 4 + xTitleH;

  const axisRows = rowHasX.reduce((a, b) => a + (b ? xAxisHeight : 0), 0);
  const panelSize = (): [number, number] => {
    const gutters = yAxisWidth.reduce((a, b) => a + b, 0);
    const free = opts.width - left - right - gutters - (cols - 1) * GAP - rightStrip - (rightStrip ? GAP : 0);
    const w = Math.max(MIN_PANEL, Math.floor(free / cols));
    let h: number;
    if (opts.height) h = (opts.height - top - bottom - topStrip - axisRows - rows * wrapStrip - (rows - 1) * GAP) / rows;
    else if (spec.panel_height) h = spec.panel_height;
    else if (spec.height) h = (spec.height - top - bottom - topStrip - axisRows - rows * wrapStrip - (rows - 1) * GAP) / rows;
    else if (spec.aspect) h = w * spec.aspect;
    else h = Math.min(300, Math.max(90, w * 0.62));
    return [w, Math.max(MIN_PANEL, Math.floor(h))];
  };
  // the panels' height sets how many y ticks they draw (finer steps, longer labels: 500M
  // between 0 and 1.0G), and it can follow their width, which follows the labels: so size
  // them, measure the labels drawn at that height, keep the wider, and size them again
  let [pw, ph] = panelSize();
  panels.forEach((p, i) => {
    if (showY[i]) yLabelWidth[i] = Math.max(yLabelWidth[i], yLabelsWidth(spec, p.y, opts, ph));
  });
  yGutters();
  [pw, ph] = panelSize();

  const colX: number[] = [];
  let x = left;
  for (let c = 0; c < cols; c++) {
    x += yAxisWidth[c];
    colX.push(x);
    x += pw + GAP;
  }
  const rowY: number[] = [];
  let y = top + topStrip;
  for (let r = 0; r < rows; r++) {
    y += wrapStrip;
    rowY.push(y);
    y += ph + (rowHasX[r] ? xAxisHeight : 0) + GAP;
  }
  const plotBottom = y - GAP;
  const plotRight = colX[cols - 1] + pw;

  const boxes: PanelBox[] = panels.map((p, i) => {
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
      strips.push({ rect: { x: colX[c], y: top, w: pw, h: stripH - 1 }, label, vertical: false });
    });
  } else if (colDepth > 1) {
    for (const [k, a, b] of nest(grid.col_keys ?? [], colDepth)) {
      const x0 = colX[a];
      strips.push({ rect: { x: x0, y: top + k * stripH, w: colX[b] + pw - x0, h: stripH - 1 }, label: grid.col_keys![a][k], vertical: false });
    }
  }
  if (rowDepth === 1) {
    grid.row_labels.forEach((label, r) => {
      strips.push({ rect: { x: plotRight + GAP, y: rowY[r], w: stripH - 1, h: ph }, label, vertical: true });
    });
  } else if (rowDepth > 1) {
    for (const [k, a, b] of nest(grid.row_keys ?? [], rowDepth)) {
      const x0 = plotRight + GAP + (rowDepth - 1 - k) * stripH; // the first column's outermost
      strips.push({ rect: { x: x0, y: rowY[a], w: stripH - 1, h: rowY[b] + ph - rowY[a] }, label: grid.row_keys![a][k], vertical: true });
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
          const x1 = colX[inRow[run[b]].col] + pw;
          strips.push({ rect: { x: x0, y: rowY[r] - wrapStrip + k * stripH, w: x1 - x0, h: stripH - 1 }, label: keys[a][k], vertical: false });
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
      const sy = last > 0 ? rowY[last - 1] + ph + xAxisHeight + GAP : rowY[last] - wrapStrip;
      const sb = rowY[last] + ph;
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
    xTitle: xTitleH ? { x: centreX, y: plotBottom + xTitleH - 2 } : null,
    yTitle: yTitleW ? { x: 4 + fs, y: centreY } : null,
    spare,
    xAxisHeight,
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
  const labels = ticks(spec.y.kind, domain[0], domain[1], spec.y.origin, count, spec.y.levels);
  return Math.ceil(Math.max(0, ...labels.map((t) => opts.measure(t.label)))) + TICK + 4;
}

/** One panel on the whole width, with both its axes and a strip naming it. */
function focusLayout(spec: TrellisSpec, opts: LayoutOptions, index: number): Layout {
  const fs = opts.fontSize;
  const p = spec.panels[index];
  const stripH = Math.round(fs * 1.5 + 4);
  const xAxisHeight = fs + TICK + 6;
  const titleH = spec.title && opts.title !== false ? Math.round(fs * 1.6 + 6) : 0;
  const xTitleH = spec.x.title ? Math.round(fs * 1.4 + 4) : 0;
  const yTitleW = spec.y.title ? Math.round(fs * 1.4 + 4) : 0;
  const left = 4 + yTitleW;
  const right = 10;
  const top = 6 + titleH;
  const bottom = 4 + xTitleH;
  const total = opts.height ?? 360;
  const h = Math.max(MIN_PANEL, Math.floor(total - top - stripH - xAxisHeight - bottom - 2));
  const yW = yLabelsWidth(spec, p.y, opts, h);
  const w = Math.max(MIN_PANEL, opts.width - left - yW - right);
  const rect = { x: left + yW, y: top + stripH, w, h };
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
    xTitle: xTitleH ? { x: rect.x + w / 2, y: plotBottom + xTitleH - 2 } : null,
    yTitle: yTitleW ? { x: 4 + fs, y: rect.y + h / 2 } : null,
    spare: null,
    xAxisHeight,
    yAxisWidth: [yW],
  };
}
