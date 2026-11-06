// Content-addressed buffer store fed by chunked "put" messages from Python.
// Transport-agnostic: the caller supplies how "need" requests are sent.

import type { DataSource } from "./types";

export interface PutMessage {
  type: "put";
  id: string;
  chunk: number;
  chunks: number;
  /** Byte offset of this chunk in the full buffer. */
  offset: number;
  byteLength: number;
}

interface Partial {
  target: Uint8Array;
  received: number;
  chunks: number;
}

/** Quiet time (ms) with requests open after which the store counts as stalled. */
export const STALL_MS = 4000;

export class BufferStore implements DataSource {
  private readonly buffers = new Map<string, ArrayBuffer>();
  private readonly partial = new Map<string, Partial>();
  private readonly waiters = new Map<string, Array<() => void>>();
  private readonly requested = new Set<string>();
  /** A request got no answer for STALL_MS: Python is gone (e.g. its kernel restarted). */
  stalled = false;
  onStall: ((stalled: boolean) => void) | null = null;
  private lastActivity = 0;
  private stallTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(private readonly request: (ids: string[]) => void) {}

  has(id: string): boolean {
    return this.buffers.has(id);
  }

  get(id: string): ArrayBuffer {
    const b = this.buffers.get(id);
    if (!b) throw new Error(`buffer ${id} not loaded`);
    return b;
  }

  /** Resolve once every id is present, requesting the missing ones once. */
  async ensure(ids: string[]): Promise<void> {
    const missing = ids.filter((id) => !this.buffers.has(id));
    const toRequest = missing.filter((id) => !this.requested.has(id));
    toRequest.forEach((id) => this.requested.add(id));
    const done = Promise.all(missing.map((id) => new Promise<void>((resolve) => this.wait(id, resolve))));
    if (toRequest.length) {
      this.lastActivity = Date.now();
      try {
        this.request(toRequest);
      } catch (err) {
        console.warn("[anytrellis] cannot ask Python for data:", err);
        toRequest.forEach((id) => this.requested.delete(id));
        this.setStalled(true);
      }
      this.watch();
    }
    await done;
  }

  private watch(): void {
    clearTimeout(this.stallTimer);
    if (!this.requested.size) return;
    const quiet = Date.now() - this.lastActivity;
    if (quiet >= STALL_MS) {
      this.setStalled(true);
      return;
    }
    this.stallTimer = setTimeout(() => this.watch(), STALL_MS - quiet);
  }

  private setStalled(stalled: boolean): void {
    if (stalled === this.stalled) return;
    this.stalled = stalled;
    this.onStall?.(stalled);
  }

  /** Keep only these buffers (those of the spec shown). */
  retain(ids: Set<string>): void {
    for (const id of [...this.buffers.keys()]) if (!ids.has(id)) this.buffers.delete(id);
    for (const id of [...this.partial.keys()]) if (!ids.has(id)) this.partial.delete(id);
    for (const id of [...this.requested]) if (!ids.has(id)) this.requested.delete(id);
    for (const id of [...this.waiters.keys()]) if (!ids.has(id)) this.release(id);
    this.watch();
  }

  /** Python has no buffer `id`: stop waiting. */
  missing(id: string): void {
    this.requested.delete(id);
    this.partial.delete(id);
    this.release(id);
    this.watch();
  }

  private release(id: string): void {
    const ws = this.waiters.get(id) ?? [];
    this.waiters.delete(id);
    ws.forEach((resolve) => resolve());
  }

  receive(msg: PutMessage, chunk: DataView | ArrayBuffer | Uint8Array): void {
    const bytes =
      chunk instanceof Uint8Array
        ? chunk
        : chunk instanceof ArrayBuffer
          ? new Uint8Array(chunk)
          : new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength);
    this.lastActivity = Date.now();
    this.setStalled(false);
    let p = this.partial.get(msg.id);
    if (!p) {
      p = { target: new Uint8Array(msg.byteLength), received: 0, chunks: msg.chunks };
      this.partial.set(msg.id, p);
    }
    p.target.set(bytes, msg.offset);
    p.received += 1;
    if (p.received < p.chunks) return;
    this.partial.delete(msg.id);
    this.requested.delete(msg.id);
    this.buffers.set(msg.id, p.target.buffer as ArrayBuffer);
    this.release(msg.id);
    this.watch();
  }

  private wait(id: string, resolve: () => void): void {
    const list = this.waiters.get(id) ?? [];
    list.push(resolve);
    this.waiters.set(id, list);
  }
}

/** Buffers embedded in a page (base64), for standalone plots. */
export function embeddedSource(buffers: Record<string, string>): DataSource {
  const decoded = new Map<string, ArrayBuffer>();
  for (const [id, b64] of Object.entries(buffers)) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    decoded.set(id, out.buffer);
  }
  return {
    has: (id) => decoded.has(id),
    get: (id) => decoded.get(id)!,
    ensure: (ids) => (ids.every((id) => decoded.has(id)) ? Promise.resolve() : Promise.reject(new Error("missing data"))),
  };
}
