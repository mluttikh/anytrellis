// How a plot looks: a dozen settings, of which the named themes are presets. Python sends
// them resolved (theme.py: Theme.spec); a name or a partial look is filled in from the
// presets here, so a spec written by hand (tests, an old saved page) still draws.

import type { TrellisSpec } from "./types";

export interface Look {
  /** Fill each panel with the panel colour. */
  panel_fill: boolean;
  /** A line around each panel, in the axis colour. */
  frame: boolean;
  /** Which way grid lines run: `auto` across y, and across x too for points or when y is a band. */
  grid: "auto" | "x" | "y" | "both" | "none";
  /** The grid: the text colour at this opacity. */
  grid_opacity: number;
  /** Which axes draw a line along the panel's edge. */
  axis_lines: "x" | "y" | "both" | "none";
  /** Strips filled with the strip colour (else: the label alone, as a title). */
  strip_fill: boolean;
  strip_align: "left" | "center";
  strip_bold: boolean;
  /** The y title: level over the plot (`↑ temp`) or on its side at the left. */
  y_title: "top" | "side";
  /** The x title: centred under the plot, or at its right end (`weight →`). */
  x_title: "center" | "end";
  /** A grid's row labels: level, as wide as they need, or on their side in a strip. */
  row_labels: "level" | "side";
  /** Pixels between panels. */
  panel_gap: number;
}

export type LookName = "minimal" | "framed" | "classic";

export const LOOKS: Record<LookName, Look> = {
  minimal: {
    panel_fill: false,
    frame: false,
    grid: "auto",
    grid_opacity: 0.1,
    axis_lines: "x",
    strip_fill: false,
    strip_align: "left",
    strip_bold: true,
    y_title: "top",
    x_title: "center",
    row_labels: "level",
    panel_gap: 6,
  },
  framed: {
    panel_fill: false,
    frame: true,
    grid: "auto",
    grid_opacity: 0.1,
    axis_lines: "none",
    strip_fill: false,
    strip_align: "center",
    strip_bold: false,
    y_title: "top",
    x_title: "end",
    row_labels: "level",
    panel_gap: 10,
  },
  classic: {
    panel_fill: true,
    frame: false,
    grid: "both",
    grid_opacity: 0.12,
    axis_lines: "both",
    strip_fill: true,
    strip_align: "center",
    strip_bold: false,
    y_title: "side",
    x_title: "center",
    row_labels: "side",
    panel_gap: 6,
  },
};

/** The spec's look: a preset's, with what the spec sets over it (default: minimal). */
export function lookOf(spec: TrellisSpec): Look {
  const t = spec.theme;
  if (!t) return LOOKS.minimal;
  if (typeof t === "string") return LOOKS[t] ?? LOOKS.minimal;
  return { ...LOOKS[t.base ?? "minimal"], ...t } as Look;
}
