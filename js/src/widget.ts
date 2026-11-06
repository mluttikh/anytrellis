// anywidget entry: connects a Python Trellis model (TrellisWidget) to TrellisView.

import type { Brush } from "./core/selection";
import { BufferStore, type PutMessage } from "./core/transport";
import type { RendererPreference, TrellisSpec } from "./core/types";
import { TrellisView } from "./core/view";

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
  };
  model.on("msg:custom", (msg: any, buffers: (DataView | ArrayBuffer)[] = []) => {
    if (msg?.type === "put") state.store.receive(msg as PutMessage, buffers[0]);
    else if (msg?.type === "missing") state.store.missing(msg.id);
    else if (msg?.type === "answer") {
      state.pending.get(msg.request)?.(msg);
      state.pending.delete(msg.request);
    }
  });
  state.store.onStall = (stalled) => state.views.forEach((v) => v.setStatus(stalled ? NO_DATA_HINT : null));
  model.on("change:_spec", () => state.tooltips.clear());
  states.set(model, state);
  return state;
}

/** Ask Python and wait for its answer (a message with the same request number). */
function ask(model: AnyModel, s: ModelState, content: Record<string, unknown>): Promise<any> {
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
      model.send({ ...content, request });
    } catch (err) {
      clearTimeout(timer);
      s.pending.delete(request);
      reject(err);
    }
  });
}

function render({ model, el }: { model: AnyModel; el: HTMLElement }): () => void {
  const s = stateFor(model);
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
      model.set("selection", brush);
      model.save_changes();
    },
  });
  s.views.add(view);
  const load = (): void => {
    const spec = model.get("_spec") as TrellisSpec;
    if (spec?.version) {
      view.setSpec(spec).catch((err) => view.setStatus(`Cannot draw: ${String(err)}`));
      // keep only the buffers some view of this model still shows
      s.store.retain(new Set(bufferIdsOf(spec)));
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
  return () => {
    model.off("change:_spec", load);
    model.off("change:open_panel", onFocus);
    model.off("change:selection", onSelection);
    s.views.delete(view);
    view.destroy();
  };
}

function bufferIdsOf(spec: TrellisSpec): string[] {
  const ids: string[] = [];
  for (const l of spec.layers) {
    if (l.type === "rule") continue;
    ids.push(l.coords.id, l.starts.id);
    if (l.color.rgba) ids.push(l.color.rgba.id);
    if (l.color.codes) ids.push(l.color.codes.id);
  }
  return ids;
}

export default { render };
