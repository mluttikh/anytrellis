// WebGL2 backend: one program; per draw a scissor, the panel's mapping as uniforms, and the
// attribute pointers moved to the draw's first instance.

import type { RendererKind } from "../types";
import { type Frame, type InstanceSet, type Renderer, deviceClip } from "./renderer";
import { GLSL_FS, GLSL_VS } from "./shaders";

interface Cached {
  version: number;
  coords: WebGLBuffer;
  colors: WebGLBuffer;
}

export class WebGL2Renderer implements Renderer {
  readonly kind: RendererKind = "webgl2";
  readonly description: string;
  onFailure: ((reason: string) => void) | null = null;
  private readonly gl: WebGL2RenderingContext;
  private readonly program: WebGLProgram;
  private readonly vao: WebGLVertexArrayObject;
  private readonly loc: Record<string, WebGLUniformLocation | null>;
  private readonly aCoords: number;
  private readonly aColor: number;
  private readonly cache = new Map<string, Cached>();
  private dpr = 1;
  private cssW = 1;
  private cssH = 1;
  private lost = false;

  static create(canvas: HTMLCanvasElement, allowSoftware: boolean): WebGL2Renderer | null {
    const gl = canvas.getContext("webgl2", { premultipliedAlpha: true, antialias: false, alpha: true, preserveDrawingBuffer: true });
    if (!gl) return null;
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    const name = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "WebGL2";
    if (!allowSoftware && /swiftshader|llvmpipe|software/i.test(name)) return null;
    return new WebGL2Renderer(canvas, gl, name);
  }

  private constructor(
    readonly canvas: HTMLCanvasElement,
    gl: WebGL2RenderingContext,
    name: string,
  ) {
    this.gl = gl;
    this.description = `WebGL2 (${name})`;
    this.program = link(gl, GLSL_VS, GLSL_FS);
    this.vao = gl.createVertexArray()!;
    this.aCoords = gl.getAttribLocation(this.program, "a_coords");
    this.aColor = gl.getAttribLocation(this.program, "a_color");
    this.loc = {};
    for (const n of ["u_canvas", "u_map", "u_shape", "u_opacity", "u_dpr"]) this.loc[n] = gl.getUniformLocation(this.program, n);
    canvas.addEventListener("webglcontextlost", (e) => {
      e.preventDefault();
      this.lost = true;
      this.onFailure?.("WebGL context lost");
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
    const gl = this.gl;
    let c = this.cache.get(set.key);
    if (c && c.version === set.version) return c;
    if (!c) {
      c = { version: -1, coords: gl.createBuffer()!, colors: gl.createBuffer()! };
      this.cache.set(set.key, c);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, c.coords);
    gl.bufferData(gl.ARRAY_BUFFER, set.coords, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, c.colors);
    gl.bufferData(gl.ARRAY_BUFFER, set.colors, gl.STATIC_DRAW);
    c.version = set.version;
    return c;
  }

  render(frame: Frame): void {
    if (this.lost) return;
    const gl = this.gl;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.disable(gl.SCISSOR_TEST);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(this.program);
    gl.bindVertexArray(this.vao);
    gl.enable(gl.SCISSOR_TEST);
    gl.uniform2f(this.loc.u_canvas, this.cssW, this.cssH);
    gl.uniform1f(this.loc.u_dpr, this.dpr);
    for (const d of frame.draws) {
      if (d.count <= 0) continue;
      const clip = deviceClip(d.clip, this.dpr, this.canvas.width, this.canvas.height);
      if (!clip) continue;
      const c = this.upload(d.set);
      gl.scissor(clip[0], this.canvas.height - clip[1] - clip[3], clip[2], clip[3]);
      gl.uniform4f(this.loc.u_map, d.sx, d.ox, d.sy, d.oy);
      gl.uniform2f(this.loc.u_shape, d.halfWidth, d.kind);
      gl.uniform1f(this.loc.u_opacity, d.opacity);
      gl.bindBuffer(gl.ARRAY_BUFFER, c.coords);
      gl.enableVertexAttribArray(this.aCoords);
      gl.vertexAttribPointer(this.aCoords, 4, gl.FLOAT, false, 16, d.start * 16);
      gl.vertexAttribDivisor(this.aCoords, 1);
      gl.bindBuffer(gl.ARRAY_BUFFER, c.colors);
      gl.enableVertexAttribArray(this.aColor);
      gl.vertexAttribPointer(this.aColor, 4, gl.UNSIGNED_BYTE, true, 4, d.start * 4);
      gl.vertexAttribDivisor(this.aColor, 1);
      gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, d.count);
    }
    gl.disable(gl.SCISSOR_TEST);
    gl.bindVertexArray(null);
  }

  retain(keys: Set<string>): void {
    for (const [key, c] of this.cache) {
      if (keys.has(key)) continue;
      this.gl.deleteBuffer(c.coords);
      this.gl.deleteBuffer(c.colors);
      this.cache.delete(key);
    }
  }

  destroy(): void {
    this.retain(new Set());
    this.gl.getExtension("WEBGL_lose_context")?.loseContext();
  }
}

function link(gl: WebGL2RenderingContext, vs: string, fs: string): WebGLProgram {
  const compile = (type: number, src: string): WebGLShader => {
    const s = gl.createShader(type)!;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(`shader: ${gl.getShaderInfoLog(s)}`);
    return s;
  };
  const p = gl.createProgram()!;
  gl.attachShader(p, compile(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(`program: ${gl.getProgramInfoLog(p)}`);
  return p;
}
