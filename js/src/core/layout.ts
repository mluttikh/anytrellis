// Where everything sits: panels on a grid, with gutters only where an axis is drawn.
//
// A panel draws its x axis when the cell below it is empty or in another x scale group, and
// its y axis when the cell to its left is empty or in another y group; so shared scales
// label only the outer panels, and free scales label every panel. An axis next to an empty
// cell (a wrap's last row, a grid's missing combination) draws into that cell, so it takes no
// gutter: the rows and columns stay evenly spaced. A wrap puts a strip over
// every panel; a grid puts its column labels over the top row and its row labels to the
// right of the last column.

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
  const { grid, panels } = spec;
  const fs = opts.fontSize;
  const rows = Math.max(1, grid.rows);
  const cols = Math.max(1, grid.cols);
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

  const stripH = Math.round(fs * 1.5 + 4);
  const wrapStrip = grid.kind === "wrap" ? stripH : 0;
  const topStrip = grid.kind === "grid" && grid.col_labels.length ? stripH : 0;
  const rightStrip = grid.kind === "grid" && grid.row_labels.length ? stripH : 0;
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
      index: i,
      rect,
      showX: showX[i],
      showY: showY[i],
      strip: wrapStrip ? { x: rect.x, y: rect.y - wrapStrip, w: pw, h: wrapStrip - 1 } : null,
      label: p.label,
      xAxis: showX[i] ? { x: rect.x, y: rect.y + ph, w: pw, h: xAxisHeight } : null,
      yAxis: showY[i] ? { x: rect.x - yLabelWidth[i], y: rect.y, w: yLabelWidth[i], h: ph } : null,
    };
  });

  const strips: Strip[] = [];
  if (topStrip) {
    grid.col_labels.forEach((label, c) => {
      strips.push({ rect: { x: colX[c], y: top, w: pw, h: topStrip - 1 }, label, vertical: false });
    });
  }
  if (rightStrip) {
    grid.row_labels.forEach((label, r) => {
      strips.push({ rect: { x: plotRight + GAP, y: rowY[r], w: rightStrip - 1, h: ph }, label, vertical: true });
    });
  }

  // the empty cells after a wrap's last panel, below the axes of the panels above them
  let spare: Rect | null = null;
  if (grid.kind === "wrap" && panels.length) {
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
        label: panelName(spec, index),
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
