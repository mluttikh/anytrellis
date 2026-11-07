// Images of the plot, for slides and reports: the view paints the plot as shown (its zoom,
// selection, opened panel and theme) on a 2D context. On a canvas at PNG_SCALE that is the
// PNG; on SvgContext, which records the same calls as SVG elements, it is the vector image.
// Both go to the clipboard, a download, or (in a notebook) a file Python saves.

/** PNG pixels per CSS pixel: sharp on slides and high-resolution screens. */
export const PNG_SCALE = 2;

type Matrix = [number, number, number, number, number, number];

interface State {
  fill: string | SvgGradient;
  stroke: string;
  lineWidth: number;
  alpha: number;
  font: string;
  align: CanvasTextAlign;
  baseline: CanvasTextBaseline;
  dash: number[];
  cap: CanvasLineCap;
  m: Matrix;
  /** Clips set in this state (clip path ids), opened as groups when something is drawn in
   * them; `opened` of them are, and its restore closes them. */
  clips: string[];
  opened: number;
}

/** A linear gradient on an SvgContext, as createLinearGradient makes on a canvas. */
export class SvgGradient {
  readonly stops: [number, string][] = [];
  constructor(
    readonly x0: number,
    readonly y0: number,
    readonly x1: number,
    readonly y1: number,
  ) {}

  addColorStop(offset: number, color: string): void {
    this.stops.push([offset, color]);
  }
}

/** Numbers in SVG: two decimals are a hundredth of a pixel. */
function n(v: number): string {
  return String(Math.round(v * 100) / 100);
}

function esc(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** A CSS colour as an SVG paint and its opacity: not every SVG reader (PowerPoint, Inkscape)
 * takes rgba() or #rrggbbaa, so the alpha goes in an opacity attribute. */
export function paint(color: string): [string, number] {
  const c = color.trim();
  const rgba = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+%?))?\s*\)$/i.exec(c);
  if (rgba) {
    const a = rgba[4] === undefined ? 1 : rgba[4].endsWith("%") ? parseFloat(rgba[4]) / 100 : parseFloat(rgba[4]);
    const [r, g, b] = [rgba[1], rgba[2], rgba[3]].map((v) => Math.round(parseFloat(v)));
    return [`rgb(${r},${g},${b})`, a];
  }
  const hex = /^#([0-9a-f]{6})([0-9a-f]{2})$/i.exec(c);
  if (hex) return [`#${hex[1]}`, parseInt(hex[2], 16) / 255];
  if (c === "transparent") return ["none", 0];
  return [c, 1];
}

/** A canvas `font` (e.g. "600 14px system-ui, sans-serif") as SVG font attributes. */
export function fontAttributes(font: string): string {
  const m = /^\s*((?:(?:normal|italic|oblique|bold|bolder|lighter|\d{3})\s+)*)([\d.]+)px\s+(.+)$/.exec(font);
  if (!m) return `font-size="12" font-family="sans-serif"`;
  const words = m[1].trim().split(/\s+/).filter(Boolean);
  const weight = words.find((w) => /^(bold|bolder|lighter|\d{3})$/.test(w));
  const style = words.find((w) => w === "italic" || w === "oblique");
  return `font-size="${n(parseFloat(m[2]))}" font-family="${esc(m[3].trim())}"${weight && weight !== "400" ? ` font-weight="${weight}"` : ""}${style ? ` font-style="${style}"` : ""}`;
}

/**
 * The part of CanvasRenderingContext2D the plot is drawn with, recording SVG: paths (filled or
 * stroked), rectangles, circles, text, clipping, transforms, dashes and gradients. Each fill
 * or stroke is one <path>, so a run of marks of one colour is one element.
 */
export class SvgContext {
  private readonly out: string[] = [];
  private readonly defs: string[] = [];
  private s: State;
  private readonly stack: State[] = [];
  private path: string[] = [];
  private nextId = 0;
  /** Clip path ids by their path, so panels clipped many times share one. */
  private readonly clipIds = new Map<string, string>();

  constructor(
    readonly width: number,
    readonly height: number,
    /** Width of `text` in px in `font` (a canvas measures it in the page). */
    private readonly measure: (text: string, font: string) => number,
  ) {
    this.s = { fill: "#000", stroke: "#000", lineWidth: 1, alpha: 1, font: "10px sans-serif", align: "start", baseline: "alphabetic", dash: [], cap: "butt", m: [1, 0, 0, 1, 0, 0], clips: [], opened: 0 };
  }

  /** The 2D context interface over this recorder, for code written for a canvas. */
  get context(): CanvasRenderingContext2D {
    return this as unknown as CanvasRenderingContext2D;
  }

  // ---- state
  get fillStyle(): string | SvgGradient {
    return this.s.fill;
  }
  set fillStyle(v: string | SvgGradient) {
    this.s.fill = v;
  }
  get strokeStyle(): string {
    return this.s.stroke;
  }
  set strokeStyle(v: string) {
    this.s.stroke = v;
  }
  get lineWidth(): number {
    return this.s.lineWidth;
  }
  set lineWidth(v: number) {
    this.s.lineWidth = v;
  }
  get globalAlpha(): number {
    return this.s.alpha;
  }
  set globalAlpha(v: number) {
    this.s.alpha = v;
  }
  get font(): string {
    return this.s.font;
  }
  set font(v: string) {
    this.s.font = v;
  }
  get textAlign(): CanvasTextAlign {
    return this.s.align;
  }
  set textAlign(v: CanvasTextAlign) {
    this.s.align = v;
  }
  get textBaseline(): CanvasTextBaseline {
    return this.s.baseline;
  }
  set textBaseline(v: CanvasTextBaseline) {
    this.s.baseline = v;
  }
  get lineCap(): CanvasLineCap {
    return this.s.cap;
  }
  set lineCap(v: CanvasLineCap) {
    this.s.cap = v;
  }
  setLineDash(dash: number[]): void {
    this.s.dash = [...dash];
  }
  getLineDash(): number[] {
    return [...this.s.dash];
  }

  save(): void {
    this.stack.push(this.s);
    this.s = { ...this.s, dash: [...this.s.dash], m: [...this.s.m], clips: [], opened: 0 };
  }

  restore(): void {
    for (let i = 0; i < this.s.opened; i++) this.out.push("</g>");
    const prev = this.stack.pop();
    if (prev) this.s = prev;
  }

  // ---- transforms
  setTransform(a: number, b: number, c: number, d: number, e: number, f: number): void {
    this.s.m = [a, b, c, d, e, f];
  }
  transform(a: number, b: number, c: number, d: number, e: number, f: number): void {
    const [ma, mb, mc, md, me, mf] = this.s.m;
    this.s.m = [ma * a + mc * b, mb * a + md * b, ma * c + mc * d, mb * c + md * d, ma * e + mc * f + me, mb * e + md * f + mf];
  }
  translate(x: number, y: number): void {
    this.transform(1, 0, 0, 1, x, y);
  }
  scale(x: number, y: number): void {
    this.transform(x, 0, 0, y, 0, 0);
  }
  rotate(angle: number): void {
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    this.transform(c, s, -s, c, 0, 0);
  }

  private pt(x: number, y: number): string {
    const [a, b, c, d, e, f] = this.s.m;
    return `${n(a * x + c * y + e)} ${n(b * x + d * y + f)}`;
  }

  /** How much the transform scales lengths (rotations and uniform scales only). */
  private get unit(): number {
    const [a, b, c, d] = this.s.m;
    return Math.sqrt(Math.abs(a * d - b * c));
  }

  // ---- paths
  beginPath(): void {
    this.path = [];
  }
  moveTo(x: number, y: number): void {
    this.path.push(`M${this.pt(x, y)}`);
  }
  lineTo(x: number, y: number): void {
    this.path.push(`L${this.pt(x, y)}`);
  }
  closePath(): void {
    this.path.push("Z");
  }
  rect(x: number, y: number, w: number, h: number): void {
    this.path.push(`M${this.pt(x, y)}L${this.pt(x + w, y)}L${this.pt(x + w, y + h)}L${this.pt(x, y + h)}Z`);
  }
  /** Full circles only (all the plot draws): two half arcs. */
  arc(x: number, y: number, r: number): void {
    const rr = n(r * this.unit);
    this.path.push(`M${this.pt(x + r, y)}A${rr} ${rr} 0 1 0 ${this.pt(x - r, y)}A${rr} ${rr} 0 1 0 ${this.pt(x + r, y)}Z`);
  }

  private fillPaint(): string {
    const f = this.s.fill;
    if (f instanceof SvgGradient) {
      const id = `g${this.nextId++}`;
      const stops = f.stops.map(([o, c]) => {
        const [col, a] = paint(c);
        return `<stop offset="${n(o)}" stop-color="${col}"${a < 1 ? ` stop-opacity="${n(a)}"` : ""}/>`;
      });
      this.defs.push(`<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${n(f.x0)}" y1="${n(f.y0)}" x2="${n(f.x1)}" y2="${n(f.y1)}">${stops.join("")}</linearGradient>`);
      return `fill="url(#${id})"${this.s.alpha < 1 ? ` fill-opacity="${n(this.s.alpha)}"` : ""}`;
    }
    const [col, a] = paint(f);
    const op = a * this.s.alpha;
    return `fill="${col}"${op < 1 ? ` fill-opacity="${n(op)}"` : ""}`;
  }

  private strokePaint(): string {
    const [col, a] = paint(this.s.stroke);
    const op = a * this.s.alpha;
    const dash = this.s.dash.length ? ` stroke-dasharray="${this.s.dash.map((v) => n(v * this.unit)).join(" ")}"` : "";
    const cap = this.s.cap !== "butt" ? ` stroke-linecap="${this.s.cap}"` : "";
    return `fill="none" stroke="${col}" stroke-width="${n(this.s.lineWidth * this.unit)}"${op < 1 ? ` stroke-opacity="${n(op)}"` : ""}${dash}${cap}`;
  }

  fill(): void {
    if (this.path.length) this.emit(`<path d="${this.path.join("")}" ${this.fillPaint()}/>`);
  }
  stroke(): void {
    if (this.path.length) this.emit(`<path d="${this.path.join("")}" ${this.strokePaint()}/>`);
  }
  fillRect(x: number, y: number, w: number, h: number): void {
    const keep = this.path;
    this.path = [];
    this.rect(x, y, w, h);
    this.fill();
    this.path = keep;
  }
  strokeRect(x: number, y: number, w: number, h: number): void {
    const keep = this.path;
    this.path = [];
    this.rect(x, y, w, h);
    this.stroke();
    this.path = keep;
  }
  clearRect(): void {}

  /** Clip what follows (until restore) to the current path. */
  clip(): void {
    const d = this.path.join("");
    let id = this.clipIds.get(d);
    if (!id) {
      id = `c${this.nextId++}`;
      this.clipIds.set(d, id);
      this.defs.push(`<clipPath id="${id}"><path d="${d}"/></clipPath>`);
    }
    this.s.clips.push(id);
  }

  /** An element, inside the clip groups not yet opened (outer states' first). */
  private emit(element: string): void {
    for (const state of [...this.stack, this.s]) {
      for (; state.opened < state.clips.length; state.opened++) this.out.push(`<g clip-path="url(#${state.clips[state.opened]})">`);
    }
    this.out.push(element);
  }

  createLinearGradient(x0: number, y0: number, x1: number, y1: number): SvgGradient {
    return new SvgGradient(x0, y0, x1, y1);
  }

  // ---- text
  measureText(text: string): TextMetrics {
    return { width: this.measure(text, this.s.font) } as TextMetrics;
  }

  fillText(text: string, x: number, y: number): void {
    if (!text) return;
    const size = parseFloat(/([\d.]+)px/.exec(this.s.font)?.[1] ?? "12");
    // baselines as offsets (dominant-baseline is not read everywhere): about where a canvas
    // puts them for a sans-serif font
    const shift = { middle: 0.35, top: 0.8, hanging: 0.8, bottom: -0.2, ideographic: -0.2, alphabetic: 0 }[this.s.baseline] ?? 0;
    const anchor = { center: "middle", right: "end", end: "end", left: "start", start: "start" }[this.s.align];
    const [a, b, c, d, e, f] = this.s.m;
    const place = b === 0 && c === 0 && a === 1 && d === 1 ? `x="${n(x + e)}" y="${n(y + f + shift * size)}"` : `transform="matrix(${[a, b, c, d, e, f].map(n).join(" ")})" x="${n(x)}" y="${n(y + shift * size)}"`;
    this.emit(`<text ${place} ${fontAttributes(this.s.font)}${anchor !== "start" ? ` text-anchor="${anchor}"` : ""} ${this.fillPaint()}>${esc(text)}</text>`);
  }

  /** The image: what was drawn, on `background` (none: transparent). */
  toString(background?: string): string {
    while (this.stack.length) this.restore();
    for (let i = 0; i < this.s.opened; i++) this.out.push("</g>");
    this.s.opened = 0;
    let bg = "";
    if (background) {
      const [col, a] = paint(background);
      bg = `<rect width="100%" height="100%" fill="${col}"${a < 1 ? ` fill-opacity="${n(a)}"` : ""}/>`;
    }
    const defs = this.defs.length ? `<defs>${this.defs.join("")}</defs>` : "";
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${n(this.width)}" height="${n(this.height)}" viewBox="0 0 ${n(this.width)} ${n(this.height)}">${defs}${bg}${this.out.join("")}</svg>`;
  }
}

/** A text measurer for SvgContext: a canvas of the page, in the font asked for. */
export function pageMeasure(): (text: string, font: string) => number {
  const ctx = document.createElement("canvas").getContext("2d")!;
  return (text, font) => {
    ctx.font = font;
    return ctx.measureText(text).width;
  };
}

/** Whether this page may put images on the clipboard (a secure context: https, localhost,
 * a file opened from disk). */
export function canCopyImages(): boolean {
  return window.isSecureContext && typeof ClipboardItem !== "undefined" && !!navigator.clipboard?.write;
}

/** Whether this browser takes an SVG on the clipboard (Chrome, Edge and VS Code do). */
export function canCopySvg(): boolean {
  return canCopyImages() && typeof ClipboardItem.supports === "function" && ClipboardItem.supports("image/svg+xml");
}

/** Put a PNG on the clipboard. It is a promise, so the clipboard is claimed during the click
 * (browsers require that) while the image is still being made. */
export async function copyPng(png: Promise<Blob>): Promise<void> {
  await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
}

/** Put an SVG on the clipboard with the PNG beside it: an app that reads SVG pastes the
 * vector image, any other the picture. */
export async function copySvg(svg: Promise<string>, png: Promise<Blob>): Promise<void> {
  const vector = svg.then((text) => new Blob([text], { type: "image/svg+xml" }));
  await navigator.clipboard.write([new ClipboardItem({ "image/svg+xml": vector, "image/png": png })]);
}

/** SVGs larger than this are slow in slides: the message says so. */
export const LARGE_SVG_BYTES = 1_000_000;

export function sizeText(bytes: number): string {
  return bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1e3))} kB`;
}

/** What a copied or saved SVG was: its size, and a hint when it is large. */
export function svgMessage(done: string, bytes: number): string {
  const size = sizeText(bytes);
  return bytes > LARGE_SVG_BYTES ? `${done} as SVG (${size}): large, so slow in slides; a PNG is lighter` : `${done} as SVG (${size})`;
}

/** Offer a file for download. */
export function download(data: Blob, name: string): void {
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** A file name from the plot's title and opened panel: letters, digits, dots and dashes. */
export function fileName(title: string, panel: string | null, ext: string): string {
  const base = [title, panel ?? ""].filter(Boolean).join("-");
  const safe = base.replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "") || "anytrellis";
  return `${safe}.${ext}`;
}

/**
 * Whether the page may download. A sandboxed page (JupyterLab's "Open in New Browser Tab"
 * serves HTML with "sandbox allow-scripts") has its downloads blocked without a word; it also
 * has an opaque origin and no storage, which tells it from a page opened from disk.
 */
export function canDownload(): boolean {
  if (window.origin !== "null") return true;
  try {
    void window.localStorage;
    return true;
  } catch {
    return false;
  }
}

/** What a sandboxed page says instead of downloading. */
export const NO_DOWNLOADS = "This tab can't download files (it is sandboxed): open the HTML file from disk, or copy the image";

/** The colours of a CSS linear-gradient (as computed: rgb() and rgba() values). */
function gradientColors(image: string): string[] {
  return image.match(/rgba?\([^)]*\)|#[0-9a-f]{3,8}\b/gi) ?? [];
}

/**
 * Paint HTML of the plot (its title, its legend) on `ctx` where it is shown: each element's
 * background colour or left-to-right gradient as a rectangle, each text as text in its font
 * and colour, faded as the element is (a legend entry not chosen). `origin` is the image's
 * top left on the page.
 */
export function paintHtml(ctx: CanvasRenderingContext2D, el: Element, origin: DOMRect, opacity = 1): void {
  const cs = getComputedStyle(el);
  if (cs.display === "none" || cs.visibility === "hidden") return;
  const alpha = opacity * (parseFloat(cs.opacity) || 0);
  if (alpha <= 0) return;
  const box = el.getBoundingClientRect();
  const [x, y] = [box.left - origin.left, box.top - origin.top];
  const colors = cs.backgroundImage.startsWith("linear-gradient") ? gradientColors(cs.backgroundImage) : [];
  if (colors.length > 1) {
    const g = ctx.createLinearGradient(x, 0, x + box.width, 0);
    colors.forEach((c, i) => g.addColorStop(i / (colors.length - 1), c));
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = g;
    ctx.fillRect(x, y, box.width, box.height);
    ctx.restore();
  } else if (box.width > 0 && box.height > 0 && el.parentElement && paint(cs.backgroundColor)[1] > 0) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = cs.backgroundColor;
    ctx.fillRect(x, y, box.width, box.height);
    ctx.restore();
  }
  for (const node of Array.from(el.childNodes)) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      paintHtml(ctx, node as Element, origin, alpha);
      continue;
    }
    const text = node.nodeType === Node.TEXT_NODE ? (node.textContent ?? "").trim() : "";
    if (!text) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const r = range.getBoundingClientRect();
    if (!r.width) continue;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = cs.color;
    ctx.font = `${cs.fontStyle === "normal" ? "" : `${cs.fontStyle} `}${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(text, r.left - origin.left, r.top - origin.top + r.height / 2);
    ctx.restore();
  }
}
