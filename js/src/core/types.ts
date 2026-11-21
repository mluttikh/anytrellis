// The spec Python sends (plot.py: Trellis._build). Bulk data travels as buffers, referred to
// by content id.

import type { Look, LookName } from "./look";

export type Dtype = "float64" | "float32" | "int32" | "uint32" | "uint16" | "uint8";

export interface BufferRef {
  id: string;
  dtype: Dtype;
  count: number;
  components: number;
  byteLength: number;
}

/** `log`, `sqrt`, `symlog`: numbers in a transformed scale's units (log10, √, symlog):
 * zoomed and panned like numbers, labelled as the values (ticks.ts: `untransform`). */
export type AxisKind = "number" | "time" | "band" | "log" | "sqrt" | "symlog";
/** `sliced`: each panel its own group, every domain as wide as the widest (lattice's
 * relation="sliced"); zooming one panel gives every panel its width, about its own centre. */
export type Share = "all" | "row" | "col" | "page" | "none" | "sliced";

export interface AxisSpec {
  kind: AxisKind;
  /** Categories of a band axis, by index. */
  levels: string[] | null;
  /** Added to every value of the axis to get the data's own value (times: ms since 1970). */
  origin: number;
  share: Share;
  title: string;
  /** How its values are written (`Trellis.format`): a d3-format string, or strftime for times. */
  format?: string | null;
  /** From high to low: x right to left, y top to bottom. */
  reverse?: boolean;
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
  /** How a wrap fills its cells (a paged wrap: each page): the side each run of panels
   * starts at ("l", "r": runs are rows; "t", "b": columns), then the side the first run is
   * at (facets.py: DIRECTIONS). Absent: "lt". */
  dir?: string;
}

export interface ColorSpec {
  /** RGBA bytes per instance, or null (one colour: `solid`). */
  rgba: BufferRef | null;
  solid: [number, number, number, number] | null;
  /** Per instance, the level of a category colour column (legend `legend`). */
  codes: BufferRef | null;
  legend: number | null;
  /** Per instance, the value of a number colour column (float64): a range of the legend
   * selects by it. */
  values?: BufferRef | null;
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
  /** Points of other shapes or sizes (channels.ts): one shape's code, or each point's
   * (uint8); each one's diameter as a share of `size` (float32). Absent: circles. */
  marker?: { shape: number; shapes: BufferRef | null; sizes: BufferRef | null } | null;
  /** A dashed line: dash and gap lengths in line widths, a pattern each, and each segment's
   * pattern (uint8; null: the first). Absent: solid. */
  dash?: { patterns: number[][]; codes: BufferRef | null } | null;
  /** Labels at the ends of the line's series (`label="end"`): each series' name, each
   * instance's series (uint16), and the colour legend the series are levels of (null:
   * none). */
  end_labels?: { names: string[]; series: BufferRef; legend: number | null } | null;
  /** An axis whose coordinates are pixels from the panel's edge, not data (a rug): "y",
   * up from its bottom; "x", right from its left. Absent: both in data. */
  pin?: "x" | "y" | null;
}

export interface RuleLayerSpec {
  type: "rule";
  name: string;
  axis: "x" | "y";
  /** Positions relative to the axis origin. */
  values: number[];
  /** From data: each value's panel (−1: every panel). Absent or null: every panel. */
  panels?: number[] | null;
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
  /** Labels placed so none covers another (labels.ts: repel); those with no room left out. */
  repel?: boolean;
}

/** A note (`annotate()`): text at a data position (axis units, relative to the origins;
 * null: x at the panel's left, y at its top), in some panels (null: every one), moved by
 * dx, dy px (a line goes back to the position). */
export interface NoteSpec {
  text: string;
  x: number | null;
  y: number | null;
  panels: number[] | null;
  dx: number;
  dy: number;
  align: "left" | "center" | "right";
  color: [number, number, number, number] | null;
  size: number | null;
}

export type LayerSpec = MarkLayerSpec | RuleLayerSpec | TextLayerSpec;

export interface LegendSpec {
  /** As shown (a column's label). */
  title: string;
  /** The colour column's name. */
  name?: string;
  /** category: an entry per level; number: a gradient; bins: a stepped number scale's
   * ranges as entries (labels written in Python); shape, dash: a shape or dash column's
   * levels; size: a size column's values, as points. */
  kind: "category" | "number" | "bins" | "shape" | "dash" | "size";
  labels?: string[];
  colors: string[];
  lo?: number;
  hi?: number;
  /** bins: the edges of the ranges (one more than the labels). */
  breaks?: number[];
  /** A number legend's ends: a d3-format string. */
  format?: string | null;
  /** Each entry's shape code (channels.ts: SHAPES), its dash (line widths), or its point's
   * diameter (px); `line_width`: the dashed lines'. */
  shapes?: number[];
  dashes?: number[][];
  line_width?: number;
  sizes?: number[];
  /** Its levels are labelled at the ends of the lines instead (not shown). */
  direct?: boolean;
}

export interface TrellisSpec {
  version: 1;
  /** The anytrellis that made the spec (shown in the help, ?). */
  package_version?: string;
  title: string;
  /** A line or two under the title. */
  subtitle?: string;
  /** A note under the plot (a source, a footnote). */
  caption?: string;
  grid: GridSpec;
  panels: PanelSpec[];
  x: AxisSpec;
  y: AxisSpec;
  layers: LayerSpec[];
  legends: LegendSpec[];
  /** Notes at data positions (`annotate()`). */
  notes?: NoteSpec[];
  height: number | null;
  panel_height: number | null;
  /** Each panel's height as a multiple of its width (unless height or panel_height). */
  aspect?: number | null;
  /** Panels sized by their range (`space=`): each column as wide as its x range takes of
   * them all (`x`), each row as high as its y range (`y`); a band axis's range is its
   * levels. Absent: every panel the same size. */
  space?: { x: boolean; y: boolean } | null;
  /** auto: in a wrap's empty cells when it fits, else under the plot; bottom: under it;
   * right: a column right of the plot (under it when too tall); none: no legend. */
  legend_position?: "auto" | "top" | "bottom" | "right" | "none";
  /** Start with y fitted to the data in view (it follows x zooms). */
  fit_y?: boolean;
  /** The plot's description for screen readers (Python's, or alt=): the figure's label. */
  description?: string;
  /** The settings panel's sections (null: no panel, controls=False). Each setting is the
   * property or method of the same name in Python. */
  settings?: SettingsSection[] | null;
  /** A panel's buttons (open, pin, compare) on the panel under the pointer (absent: yes). */
  panel_buttons?: boolean;
  /** The look (look.ts): a preset's name, or its settings (from Python: all of them). */
  theme?: LookName | (Partial<Look> & { base?: LookName });
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
  /** Its name as shown (its column's label; default: its name). */
  label?: string;
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
  /** Panels first on every page, whatever the sort and filters (their names). */
  pinned?: string[];
}

/** A view kept (Trellis.save_view, or the reader's Views menu): the paging, the panel
 * opened and the one compared (names), and the zoom (each scale group's range, in the
 * spec's units; null: as the plot starts). */
export interface SavedView extends Paging {
  open?: string | null;
  compare?: string | null;
  zoom?: Zoom | null;
}

export interface Zoom {
  x: [number, [number, number]][];
  y: [number, [number, number]][];
}

/** The table view (the toolbar's Table, t), from Python: each panel's statistics, and the
 * rows when they are few (`note`: why not); every value as text. */
export interface TableView {
  panels: { columns: string[]; rows: string[][] };
  rows: { caption: string; columns: string[]; rows: string[][] } | null;
  note?: string;
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

/** A section of the settings panel ("Layout", "Scales", "Data"). */
export interface SettingsSection {
  title: string;
  settings: Setting[];
}

/** One setting: a menu of choices (value, label), or a number stepped up and down. */
export interface Setting {
  name: string;
  label: string;
  kind: "select" | "stepper";
  value: unknown;
  options?: [unknown, string][];
  /** A stepper: the value shown (its own when the setting is None), and its range. */
  shown?: number;
  min?: number;
  max?: number;
}
