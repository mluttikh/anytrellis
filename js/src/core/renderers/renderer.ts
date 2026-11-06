// What every backend draws: instances of one primitive, in panels of one canvas.
//
// An instance is two points (a, b) and a colour. Drawn as a rectangle (KIND_RECT) it fills
// the box between a and b (bars); drawn as a capsule (KIND_CAPSULE) it is the segment a-b
// with round ends, `halfWidth` px either side (a line segment; a point when a == b).
// Coordinates are float32 relative to each panel's base; a draw maps them to CSS pixels with
// screen = offset + value * scale per axis, and clips to its panel.

import type { RendererKind } from "../types";

export const KIND_RECT = 0;
export const KIND_CAPSULE = 1;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** The instances of a layer, cached on the GPU by key and version. */
export interface InstanceSet {
  key: string;
  version: number;
  count: number;
  /** ax, ay, bx, by per instance. */
  coords: Float32Array;
  /** RGBA bytes per instance. */
  colors: Uint8Array;
}

export interface Draw {
  set: InstanceSet;
  start: number;
  count: number;
  /** The panel (CSS px): drawn clipped to it. */
  clip: Rect;
  /** screen x = ox + x * sx, screen y = oy + y * sy (CSS px). */
  sx: number;
  ox: number;
  sy: number;
  oy: number;
  kind: number;
  halfWidth: number;
  opacity: number;
}

export interface Frame {
  draws: Draw[];
}

export interface Renderer {
  readonly kind: RendererKind;
  readonly description: string;
  readonly canvas: HTMLCanvasElement;
  resize(cssWidth: number, cssHeight: number, dpr: number): void;
  render(frame: Frame): void;
  /** Forget cached sets whose key is not in `keys`. */
  retain(keys: Set<string>): void;
  destroy(): void;
  /** Called when the backend fails at run time (device lost, context lost). */
  onFailure: ((reason: string) => void) | null;
}

/** A draw's clip in device pixels, inside the canvas (null: nothing to draw). */
export function deviceClip(clip: Rect, dpr: number, width: number, height: number): [number, number, number, number] | null {
  const x0 = Math.max(0, Math.floor(clip.x * dpr));
  const y0 = Math.max(0, Math.floor(clip.y * dpr));
  const x1 = Math.min(width, Math.ceil((clip.x + clip.w) * dpr));
  const y1 = Math.min(height, Math.ceil((clip.y + clip.h) * dpr));
  if (x1 <= x0 || y1 <= y0) return null;
  return [x0, y0, x1 - x0, y1 - y0];
}
