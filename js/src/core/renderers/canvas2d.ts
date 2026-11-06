// Canvas 2D backend: the same draws without a GPU. Runs of instances of one colour are
// filled or stroked as one path.

import type { RendererKind } from "../types";
import { type Frame, KIND_RECT, KIND_TRAP, type Renderer } from "./renderer";

export class Canvas2DRenderer implements Renderer {
  readonly kind: RendererKind = "canvas2d";
  readonly description = "Canvas 2D";
  onFailure: ((reason: string) => void) | null = null;
  private readonly ctx: CanvasRenderingContext2D;
  private dpr = 1;

  static create(canvas: HTMLCanvasElement): Canvas2DRenderer | null {
    const ctx = canvas.getContext("2d");
    return ctx ? new Canvas2DRenderer(canvas, ctx) : null;
  }

  private constructor(
    readonly canvas: HTMLCanvasElement,
    ctx: CanvasRenderingContext2D,
  ) {
    this.ctx = ctx;
  }

  resize(cssWidth: number, cssHeight: number, dpr: number): void {
    this.dpr = dpr;
    const w = Math.max(1, Math.round(cssWidth * dpr));
    const h = Math.max(1, Math.round(cssHeight * dpr));
    if (this.canvas.width !== w) this.canvas.width = w;
    if (this.canvas.height !== h) this.canvas.height = h;
  }

  render(frame: Frame): void {
    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    for (const d of frame.draws) {
      if (d.count <= 0) continue;
      ctx.save();
      ctx.beginPath();
      ctx.rect(d.clip.x, d.clip.y, d.clip.w, d.clip.h);
      ctx.clip();
      ctx.globalAlpha = d.opacity;
      ctx.lineCap = "round";
      ctx.lineWidth = Math.max(0.5, d.halfWidth * 2);
      const { coords, colors, base } = d.set;
      let style = -1;
      let open = false;
      const flush = (): void => {
        if (!open) return;
        if (d.kind === KIND_RECT || d.kind === KIND_TRAP) ctx.fill();
        else ctx.stroke();
        open = false;
      };
      for (let i = d.start; i < d.start + d.count; i++) {
        const rgba = (colors[i * 4] << 24) | (colors[i * 4 + 1] << 16) | (colors[i * 4 + 2] << 8) | colors[i * 4 + 3];
        if (rgba !== style) {
          flush();
          style = rgba;
          const css = `rgba(${colors[i * 4]},${colors[i * 4 + 1]},${colors[i * 4 + 2]},${colors[i * 4 + 3] / 255})`;
          ctx.fillStyle = css;
          ctx.strokeStyle = css;
          ctx.beginPath();
          open = true;
        }
        const ax = d.ox + coords[i * 4] * d.sx;
        const ay = d.oy + coords[i * 4 + 1] * d.sy;
        const bx = d.ox + coords[i * 4 + 2] * d.sx;
        const by = d.oy + coords[i * 4 + 3] * d.sy;
        if (!Number.isFinite(ax + ay + bx + by)) continue;
        if (d.kind === KIND_TRAP && base) {
          const ba = d.oy + base[i * 2] * d.sy;
          const bb = d.oy + base[i * 2 + 1] * d.sy;
          if (!Number.isFinite(ba + bb)) continue;
          ctx.moveTo(ax, ay);
          ctx.lineTo(bx, by);
          ctx.lineTo(bx, bb);
          ctx.lineTo(ax, ba);
          ctx.closePath();
        } else if (d.kind === KIND_RECT) {
          const x = Math.min(ax, bx);
          const y = Math.min(ay, by);
          ctx.rect(x, y, Math.max(1, Math.abs(bx - ax)), Math.max(1, Math.abs(by - ay)));
        } else {
          ctx.moveTo(ax, ay);
          // a zero-length segment draws nothing in some browsers: nudge it
          ctx.lineTo(bx === ax && by === ay ? bx + 0.01 : bx, by);
        }
      }
      flush();
      ctx.restore();
    }
  }

  retain(): void {}

  destroy(): void {}
}
