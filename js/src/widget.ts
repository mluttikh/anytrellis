// anywidget entry: connects a Python Trellis model (TrellisWidget) to TrellisView.

import { bufferIds } from "./core/scene";
import type { Brush } from "./core/selection";
import { BufferStore, type PutMessage } from "./core/transport";
import type { RendererPreference, TrellisSpec } from "./core/types";
import { type Highlight, TrellisView } from "./core/view";

interface AnyModel {
  get(key: string): any;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on(event: string, cb: (...args: any[]) => void): void;
  off(event?: string, cb?: (...args: any[]) => void): void;
  send(content: unknown, callbacks?: unknown, buffers?: ArrayBuffer[]): void;
}

interface ModelState {
  store: BufferStore;
  views: Set<TrellisView>;
  pending: Map<number, (msg: any) => void>;
  nextRequest: number;
  tooltips: Map<string, Promise<string[][]>>;
  /** What a linked plot's selection highlights here (from Python), or null. */
  highlight: Highlight | null;
}

const states = new WeakMap<AnyModel, ModelState>();
const ASK_TIMEOUT_MS = 10_000;
const NO_DATA_HINT = "Waiting for data from Python. Is the kernel running? Run the cell again.";

function stateFor(model: AnyModel): ModelState {
  let s = states.get(model);
  if (s) return s;
  const state: ModelState = {
    store: new BufferStore((ids) => model.send({ type: "need", ids })),
    views: new Set(),
    pending: new Map(),
    nextRequest: 0,
    tooltips: new Map(),
    highlight: null,
  };
  model.on("msg:custom", (msg: any, buffers: (DataView | ArrayBuffer)[] = []) => {
    if (msg?.type === "put") state.store.receive(msg as PutMessage, buffers[0]);
    else if (msg?.type === "missing") state.store.missing(msg.id);
    else if (msg?.type === "answer") {
      state.pending.get(msg.request)?.(msg);
      state.pending.delete(msg.request);
    } else if (msg?.type === "highlight") {
      state.highlight = highlightOf(msg, buffers);
      state.views.forEach((v) => v.setHighlight(state.highlight));
    }
  });
  state.store.onStall = (stalled) => state.views.forEach((v) => v.setStatus(stalled ? NO_DATA_HINT : null));
  model.on("change:_spec", () => state.tooltips.clear());
  states.set(model, state);
  return state;
}

/** A highlight message's layers, read from its binary buffers. */
function highlightOf(msg: any, buffers: (DataView | ArrayBuffer)[]): Highlight | null {
  if (!Array.isArray(msg.layers)) return null;
  const bytes = (i: number): Uint8Array => {
    const b = buffers[i];
    if (!b) return new Uint8Array(0);
    return b instanceof ArrayBuffer ? new Uint8Array(b) : new Uint8Array(b.buffer, b.byteOffset, b.byteLength);
  };
  return {
    layers: msg.layers.map((l: any) => {
      if (l && typeof l.mask === "number") {
        // a bit per instance, the first in the lowest bit
        const bits = bytes(l.mask);
        const mask = new Uint8Array(l.count ?? bits.length * 8);
        for (let i = 0; i < mask.length; i++) mask[i] = (bits[i >> 3] >> (i & 7)) & 1;
        return { mask };
      }
      if (l && typeof l.fraction === "number") return { fraction: new Float32Array(bytes(l.fraction).slice().buffer) };
      return null;
    }),
  };
}

/** How often a linked plot sends its brush while it is dragged. */
const LIVE_MS = 50;

/** Ask Python and wait for its answer (a message with the same request number). */
function ask(model: AnyModel, s: ModelState, content: Record<string, unknown>, buffers?: ArrayBuffer[]): Promise<any> {
  const request = ++s.nextRequest;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      s.pending.delete(request);
      reject(new Error("no answer"));
    }, ASK_TIMEOUT_MS);
    s.pending.set(request, (msg) => {
      clearTimeout(timer);
      if (msg.error) reject(new Error(msg.error));
      else resolve(msg);
    });
    try {
      model.send({ ...content, request }, undefined, buffers);
    } catch (err) {
      clearTimeout(timer);
      s.pending.delete(request);
      reject(err);
    }
  });
}

function render({ model, el }: { model: AnyModel; el: HTMLElement }): () => void {
  const s = stateFor(model);
  let lastLive = 0; // when the brush last went to Python
  const view = new TrellisView(el, {
    source: s.store,
    renderer: (model.get("renderer") ?? "auto") as RendererPreference,
    tooltip: (layer, index) => {
      const key = `${layer}:${index}`;
      let p = s.tooltips.get(key);
      if (!p) {
        p = ask(model, s, { type: "tooltip", layer, index }).then((msg) => msg.rows as string[][]);
        p.catch(() => s.tooltips.delete(key));
        s.tooltips.set(key, p);
      }
      return p;
    },
    onFocus: (name) => {
      model.set("open_panel", name);
      model.save_changes();
    },
    onSelect: (brush) => {
      lastLive = performance.now();
      model.set("selection", brush);
      model.save_changes();
    },
    // a linked plot: the others follow the brush as it moves (Python relays it)
    onBrushing: (brush) => {
      const now = performance.now();
      if (!model.get("_live") || now - lastLive < LIVE_MS) return;
      lastLive = now;
      model.set("selection", brush);
      model.save_changes();
    },
    onClear: () => model.send({ type: "clear" }),
    // the Export menu's "Save ... next to the notebook": Python writes the file
    onSaveFile: async (name, data) => {
      const msg = await ask(model, s, { type: "save", name }, [await data.arrayBuffer()]);
      return String(msg.path);
    },
  });
  s.views.add(view);
  view.setHighlight(s.highlight);
  const load = (): void => {
    const spec = model.get("_spec") as TrellisSpec;
    if (spec?.version) {
      view.setSpec(spec).catch((err) => view.setStatus(`Cannot draw: ${String(err)}`));
      // keep only the buffers some view of this model still shows
      s.store.retain(new Set(bufferIds(spec)));
    }
  };
  // Trellis.open / close in Python (or another view of the same widget)
  const onFocus = (): void => view.setFocusName((model.get("open_panel") as string | null) ?? null);
  // Trellis.select in Python (or another view)
  const onSelection = (): void => view.setSelection((model.get("selection") as Brush | null) ?? null);
  model.on("change:_spec", load);
  model.on("change:open_panel", onFocus);
  model.on("change:selection", onSelection);
  onFocus();
  onSelection();
  load();
  model.send({ type: "ready" }); // what a link highlights here
  return () => {
    model.off("change:_spec", load);
    model.off("change:open_panel", onFocus);
    model.off("change:selection", onSelection);
    s.views.delete(view);
    view.destroy();
  };
}

export default { render };
