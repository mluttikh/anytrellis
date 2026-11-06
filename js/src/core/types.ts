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

export type AxisKind = "number" | "time" | "band";
export type Share = "all" | "row" | "col" | "none";

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
  type: "line" | "points" | "bars";
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
  /** Per instance, its row's key of the link columns (uint32): a selection grows to every
   * mark sharing a key. Absent: not linked. */
  link?: BufferRef | null;
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

export type LayerSpec = MarkLayerSpec | RuleLayerSpec;

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
  /** auto: in a wrap's empty cells when it fits, else under the plot; bottom: under it. */
  legend_position?: "auto" | "bottom";
  /** Start with y fitted to the data in view (it follows x zooms). */
  fit_y?: boolean;
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
  return layer.type !== "rule";
}
