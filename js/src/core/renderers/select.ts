// Picks a backend: WebGPU, then WebGL2, then Canvas 2D. "auto" refuses software GPU
// implementations (Canvas 2D is faster and always available); forcing a backend accepts its
// software implementation.

import type { RendererKind, RendererPreference } from "../types";
import { Canvas2DRenderer } from "./canvas2d";
import type { Renderer } from "./renderer";
import { WebGL2Renderer } from "./webgl2";
import { WebGPURenderer } from "./webgpu";

export const CHAIN: RendererKind[] = ["webgpu", "webgl2", "canvas2d"];

export async function createRenderer(
  preference: RendererPreference,
  makeCanvas: () => HTMLCanvasElement,
  skip: RendererKind[] = [],
): Promise<{ renderer: Renderer; skipped: string[] }> {
  const start = preference === "auto" ? 0 : CHAIN.indexOf(preference);
  const skipped: string[] = [];
  for (const kind of CHAIN.slice(Math.max(0, start))) {
    if (skip.includes(kind)) continue;
    const canvas = makeCanvas();
    const allowSoftware = kind === preference;
    try {
      const renderer =
        kind === "webgpu"
          ? await WebGPURenderer.create(canvas, allowSoftware)
          : kind === "webgl2"
            ? WebGL2Renderer.create(canvas, allowSoftware)
            : Canvas2DRenderer.create(canvas);
      if (renderer) return { renderer, skipped };
      skipped.push(`${kind}: unavailable`);
    } catch (err) {
      skipped.push(`${kind}: ${err instanceof Error ? err.message : String(err)}`);
    }
    canvas.remove();
  }
  throw new Error(`no renderer available (${skipped.join("; ")})`);
}
