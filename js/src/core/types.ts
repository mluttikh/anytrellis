// The spec Python sends (plot.py: Trellis._build). Bulk data travels as buffers, referred to
// by content id.

export type Dtype = "float64" | "float32" | "int32" | "uint32" | "uint16" | "uint8";

export interface BufferRef {
  id: string;
  dtype: Dtype;
  count: number;
  components: number;
  byteLength: number;
}

/** `log`: numbers in log10 units (a log scale): zoomed and panned like numbers, labelled
 * as the values. */
export type AxisKind = "number" | "time" | "band" | "log";
export type Share = "all" | "row" | "col" | "page" | "none";

export interface AxisSpec {
  kind: AxisKind;
  /** Categories of a band axis, by index. */
  levels: string[] | null;
  /** Added to every value of the axis to get the data's own value (times: ms since 1970). */
  origin: number;
  share: Share;
  title: string;
}

export interface PanelSpec {
  row: number;
  col: number;
  /** The strip of a wrap ("" in a grid). */
  label: string;
  /** The panel's level of each facet column. */
  keys: string[];
  /** With strip_label: the panel's own strip (the margins' and nested strips: none). */
  strip?: string;
  /** The domain, relative to the axis origin. */
  x: [number, number];
  y: [number, number];
  /** Scale groups: panels of a group share a domain and zoom together. */
  xg: number;
  yg: number;
}

export interface GridSpec {
  kind: "single" | "grid" | "wrap";
  rows: number;
  cols: number;
  row_labels: string[];
  col_labels: string[];
  row_title: string;
  col_title: string;
  /** A grid's rows' and columns' level of each of their facet columns (nested strips). */
  row_keys?: string[][];
  col_keys?: string[][];
  /** A wrap's strips name the panels' keys from this one on (those before: the page's). */
  strip_from?: number;
  /** With several facet columns, `nested`: a strip per column, spanning the panels of its
   * level; `joined`: one strip naming the levels together. */
  strips?: "nested" | "joined";
  /** Each panel names itself in a strip of its own (PanelSpec.strip). */
  strip_label?: boolean;
}

export interface ColorSpec {
  /** RGBA bytes per instance, or null (one colour: `solid`). */
  rgba: BufferRef | null;
  solid: [number, number, number, number] | null;
  /** Per instance, the level of a category colour column (legend `legend`). */
  codes: BufferRef | null;
  legend: number | null;
}

export interface MarkLayerSpec {
  /** `band`: an area between two lines (ymin, ymax): drawn as an area, its base not zero. */
  type: "line" | "points" | "bars" | "area" | "rect" | "band";
  name: string;
  count: number;
  /** x0, y0, x1, y1 per instance (float64, relative to the axis origins), sorted by panel. */
  coords: BufferRef;
  /** Panel p holds instances starts[p] .. starts[p + 1]. */
  starts: BufferRef;
  color: ColorSpec;
  /** Line width (px). */
  width: number;
  /** Point diameter (px). */
  size: number;
  opacity: number;
  /** Python has tooltip columns for this layer. */
  tooltip: boolean;
  /** Context (the other panels' data): not hovered, not selected. */
  context: boolean;
  /** A line drawn as steps ("pre", "post", "mid"): hovering it finds its levels, each
   * starting at its point, not its risers. */
  step?: string | null;
  /** Per instance, its row's key of the link columns (uint32): a selection grows to every
   * mark sharing a key. Absent: not linked. */
  link?: BufferRef | null;
  /** Areas: the base's y at each end of an instance (float64, 2 per instance). */
  base?: BufferRef | null;
  /** Axes the tooltip leaves out (a box: its numbers come from Python instead). */
  hide?: ("x" | "y")[];
  /** The parts of one summary mark drawing the same rows (a box's body and lines) share a
   * family: an instance selected selects every instance of its group (uint32 per
   * instance) in the family. */
  family?: number | null;
  groups?: BufferRef | null;
  /** Tooltip rows given with the spec (a summary's, which are few): per row of its table,
   * a value for each name; `tip_rows`: each instance's row. */
  tips?: { names: string[]; values: string[][] } | null;
  tip_rows?: BufferRef | null;
  /** A paged plot in a notebook: the panels whose instances it has (Python sends the
   * others' when they are shown). Absent: every panel's. */
  panels?: number[] | null;
}

export interface RuleLayerSpec {
  type: "rule";
  name: string;
  axis: "x" | "y";
  /** Positions relative to the axis origin. */
  values: number[];
  color: [number, number, number, number];
  width: number;
  dash: number[];
}

/** Labels at points, drawn on the front canvas. */
export interface TextLayerSpec {
  type: "text";
  name: string;
  count: number;
  /** x, y per label (float64, relative to the axis origins), sorted by panel. */
  coords: BufferRef;
  starts: BufferRef;
  /** The labels as UTF-8 bytes; label i is bytes offsets[i] .. offsets[i + 1]. */
  labels: BufferRef;
  offsets: BufferRef;
  /** RGBA per label (a colour column), else one colour, else the theme's text colour. */
  colors: BufferRef | null;
  color: [number, number, number, number] | null;
  size: number;
  align: "left" | "center" | "right";
  dx: number;
  dy: number;
  opacity: number;
  context: boolean;
  /** As a mark layer's: the panels whose labels it has (absent: every panel's). */
  panels?: number[] | null;
}

export type LayerSpec = MarkLayerSpec | RuleLayerSpec | TextLayerSpec;

export interface LegendSpec {
  title: string;
  kind: "category" | "number";
  labels?: string[];
  colors: string[];
  lo?: number;
  hi?: number;
}

export interface TrellisSpec {
  version: 1;
  title: string;
  grid: GridSpec;
  panels: PanelSpec[];
  x: AxisSpec;
  y: AxisSpec;
  layers: LayerSpec[];
  legends: LegendSpec[];
  height: number | null;
  panel_height: number | null;
  /** Each panel's height as a multiple of its width (unless height or panel_height). */
  aspect?: number | null;
  /** auto: in a wrap's empty cells when it fits, else under the plot; bottom: under it. */
  legend_position?: "auto" | "bottom";
  /** Start with y fitted to the data in view (it follows x zooms). */
  fit_y?: boolean;
  /** A wrap shown a page at a time (null: all its panels at once). */
  pages?: PagesSpec | null;
}

/** A paged wrap: a page's rows and columns, and each panel's statistics to sort and filter
 * the panels by. With page columns (page=): each panel's page level, a page per level. */
export interface PagesSpec {
  rows: number;
  cols: number;
  stats: PanelStat[];
  /** Each panel's page level (an index in `levels`): a level's panels on pages of their own. */
  groups?: number[] | null;
  /** The page levels' names. */
  levels?: string[] | null;
  /** The page columns' names. */
  title?: string;
  /** A grid on every page: each panel keeps its cell (not sorted or filtered). */
  grid?: boolean;
}

export interface PanelStat {
  name: string;
  kind: "number" | "text";
  /** A value per panel (null: none; "" for text). */
  values: (number | string | null)[];
  /** Each value as shown. */
  text: string[];
}

/** The page shown (from 0), the sort (a statistic's name; null: as given) and the filters:
 * words of the panels' names, and per statistic a [low, high] range (null: open) or text. */
export interface Paging {
  page?: number;
  sort?: string | null;
  descending?: boolean;
  name?: string;
  where?: Record<string, [number | null, number | null] | string | null>;
}

/** Where buffers come from: Python (BufferStore), or a page that embeds them. */
export interface DataSource {
  has(id: string): boolean;
  get(id: string): ArrayBuffer;
  ensure(ids: string[]): Promise<void>;
}

export type RendererKind = "webgpu" | "webgl2" | "canvas2d";
export type RendererPreference = RendererKind | "auto";

export function isMark(layer: LayerSpec): layer is MarkLayerSpec {
  return layer.type !== "rule" && layer.type !== "text";
}
