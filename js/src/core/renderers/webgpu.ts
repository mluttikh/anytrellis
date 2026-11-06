// WebGPU backend: one pipeline; the draws' mappings go into one uniform buffer read at a
// dynamic offset per draw, and each draw starts at its first instance. One GPU device is
// shared by every plot on the page (WebGPU, unlike WebGL, lets one device draw into any
// number of canvases), so many plots cost no extra contexts.

import type { RendererKind } from "../types";
import { type Frame, type InstanceSet, type Renderer, deviceClip } from "./renderer";
import { WGSL } from "./shaders";

const STRIDE = 256; // minUniformBufferOffsetAlignment
const UNIFORM_FLOATS = 12;

interface Shared {
  device: GPUDevice;
  adapterName: string;
  pipelines: Map<GPUTextureFormat, { pipeline: GPURenderPipeline; layout: GPUBindGroupLayout }>;
}

let shared: Promise<Shared | null> | null = null;

async function device(allowSoftware: boolean): Promise<Shared | null> {
  if (!("gpu" in navigator) || !navigator.gpu) return null;
  if (!shared) {
    shared = (async () => {
      const adapter = await navigator.gpu.requestAdapter({ powerPreference: "high-performance" });
      if (!adapter) return null;
      const info = (adapter as GPUAdapter & { info?: GPUAdapterInfo }).info;
      const name = [info?.vendor, info?.architecture, info?.description].filter(Boolean).join(" ") || "WebGPU";
      const fallback = (adapter as GPUAdapter & { isFallbackAdapter?: boolean }).isFallbackAdapter ?? info?.isFallbackAdapter ?? false;
      if (fallback && !allowSoftware) return null;
      const dev = await adapter.requestDevice();
      dev.lost.then(() => {
        shared = null;
      });
      return { device: dev, adapterName: name, pipelines: new Map() };
    })().catch(() => null);
  }
  return shared;
}

function pipelineFor(s: Shared, format: GPUTextureFormat): { pipeline: GPURenderPipeline; layout: GPUBindGroupLayout } {
  let p = s.pipelines.get(format);
  if (p) return p;
  const module = s.device.createShaderModule({ code: WGSL });
  const layout = s.device.createBindGroupLayout({
    entries: [{ binding: 0, visibility: GPUShaderStage.VERTEX | GPUShaderStage.FRAGMENT, buffer: { type: "uniform", hasDynamicOffset: true } }],
  });
  const pipeline = s.device.createRenderPipeline({
    layout: s.device.createPipelineLayout({ bindGroupLayouts: [layout] }),
    vertex: {
      module,
      entryPoint: "vs",
      buffers: [
        { arrayStride: 16, stepMode: "instance", attributes: [{ shaderLocation: 0, offset: 0, format: "float32x4" }] },
        { arrayStride: 4, stepMode: "instance", attributes: [{ shaderLocation: 1, offset: 0, format: "unorm8x4" }] },
      ],
    },
    fragment: {
      module,
      entryPoint: "fs",
      targets: [
        {
          format,
          blend: {
            color: { srcFactor: "one", dstFactor: "one-minus-src-alpha", operation: "add" },
            alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha", operation: "add" },
          },
        },
      ],
    },
    primitive: { topology: "triangle-list" },
  });
  p = { pipeline, layout };
  s.pipelines.set(format, p);
  return p;
}

interface Cached {
  version: number;
  coords: GPUBuffer;
  colors: GPUBuffer;
  /** The coordinates uploaded: a new version with the same array only re-sends colours. */
  source: Float32Array;
}

export class WebGPURenderer implements Renderer {
  readonly kind: RendererKind = "webgpu";
  readonly description: string;
  onFailure: ((reason: string) => void) | null = null;
  private readonly cache = new Map<string, Cached>();
  private uniforms: GPUBuffer | null = null;
  private bindGroup: GPUBindGroup | null = null;
  private capacity = 0;
  private dpr = 1;
  private cssW = 1;
  private cssH = 1;
  private failed = false;

  static async create(canvas: HTMLCanvasElement, allowSoftware: boolean): Promise<WebGPURenderer | null> {
    const s = await device(allowSoftware);
    if (!s) return null;
    const context = canvas.getContext("webgpu");
    if (!context) return null;
    const format = navigator.gpu.getPreferredCanvasFormat();
    context.configure({ device: s.device, format, alphaMode: "premultiplied" });
    return new WebGPURenderer(canvas, s, context, format);
  }

  private constructor(
    readonly canvas: HTMLCanvasElement,
    private readonly s: Shared,
    private readonly context: GPUCanvasContext,
    private readonly format: GPUTextureFormat,
  ) {
    this.description = `WebGPU (${s.adapterName})`;
    s.device.lost.then((info) => {
      this.failed = true;
      this.onFailure?.(`WebGPU device lost: ${info.message}`);
    });
  }

  resize(cssWidth: number, cssHeight: number, dpr: number): void {
    this.dpr = dpr;
    this.cssW = cssWidth;
    this.cssH = cssHeight;
    const w = Math.max(1, Math.round(cssWidth * dpr));
    const h = Math.max(1, Math.round(cssHeight * dpr));
    if (this.canvas.width !== w) this.canvas.width = w;
    if (this.canvas.height !== h) this.canvas.height = h;
  }

  private upload(set: InstanceSet): Cached {
    const dev = this.s.device;
    let c = this.cache.get(set.key);
    if (c && c.version === set.version) return c;
    const colors = set.colors.byteLength % 4 === 0 ? set.colors : padded(set.colors);
    if (c && c.source === set.coords && c.colors.size >= Math.max(16, colors.byteLength)) {
      // only the colours changed (a selection): the coordinates stay on the GPU
      if (colors.byteLength) dev.queue.writeBuffer(c.colors, 0, colors.buffer, colors.byteOffset, colors.byteLength);
      c.version = set.version;
      return c;
    }
    if (c) {
      c.coords.destroy();
      c.colors.destroy();
    }
    const make = (data: ArrayBufferView): GPUBuffer => {
      const size = Math.max(16, Math.ceil(data.byteLength / 4) * 4);
      const b = dev.createBuffer({ size, usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST });
      if (data.byteLength) dev.queue.writeBuffer(b, 0, data.buffer, data.byteOffset, Math.floor(data.byteLength / 4) * 4);
      return b;
    };
    c = { version: set.version, coords: make(set.coords), colors: make(colors), source: set.coords };
    this.cache.set(set.key, c);
    return c;
  }

  private ensureUniforms(draws: number): void {
    if (draws <= this.capacity && this.uniforms) return;
    this.uniforms?.destroy();
    this.capacity = Math.max(64, 2 ** Math.ceil(Math.log2(draws)));
    const { layout } = pipelineFor(this.s, this.format);
    this.uniforms = this.s.device.createBuffer({ size: this.capacity * STRIDE, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    this.bindGroup = this.s.device.createBindGroup({ layout, entries: [{ binding: 0, resource: { buffer: this.uniforms, size: UNIFORM_FLOATS * 4 } }] });
  }

  render(frame: Frame): void {
    if (this.failed) return;
    const dev = this.s.device;
    const draws = frame.draws.filter((d) => d.count > 0);
    this.ensureUniforms(Math.max(1, draws.length));
    const data = new Float32Array((draws.length * STRIDE) / 4);
    draws.forEach((d, i) => {
      data.set([this.cssW, this.cssH, this.dpr, d.opacity, d.sx, d.ox, d.sy, d.oy, d.halfWidth, d.kind, 0, 0], (i * STRIDE) / 4);
    });
    if (draws.length) dev.queue.writeBuffer(this.uniforms!, 0, data);
    const encoder = dev.createCommandEncoder();
    const pass = encoder.beginRenderPass({
      colorAttachments: [{ view: this.context.getCurrentTexture().createView(), loadOp: "clear", storeOp: "store", clearValue: { r: 0, g: 0, b: 0, a: 0 } }],
    });
    const { pipeline } = pipelineFor(this.s, this.format);
    pass.setPipeline(pipeline);
    draws.forEach((d, i) => {
      const clip = deviceClip(d.clip, this.dpr, this.canvas.width, this.canvas.height);
      if (!clip) return;
      const c = this.upload(d.set);
      pass.setScissorRect(clip[0], clip[1], clip[2], clip[3]);
      pass.setBindGroup(0, this.bindGroup!, [i * STRIDE]);
      pass.setVertexBuffer(0, c.coords);
      pass.setVertexBuffer(1, c.colors);
      pass.draw(6, d.count, 0, d.start);
    });
    pass.end();
    dev.queue.submit([encoder.finish()]);
  }

  retain(keys: Set<string>): void {
    for (const [key, c] of this.cache) {
      if (keys.has(key)) continue;
      c.coords.destroy();
      c.colors.destroy();
      this.cache.delete(key);
    }
  }

  destroy(): void {
    this.retain(new Set());
    this.uniforms?.destroy();
    this.context.unconfigure();
  }
}

function padded(bytes: Uint8Array): Uint8Array {
  const out = new Uint8Array(Math.ceil(bytes.length / 4) * 4);
  out.set(bytes);
  return out;
}
