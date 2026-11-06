// Standalone plots (Trellis.save_html / to_html): the data embedded in the page, so they
// work without a kernel. Any number per page: <div class="anytrellis-embed"> holding a
// <script type="application/json"> with {spec, buffers (id → base64), renderer}.

import type { Brush } from "./core/selection";
import { embeddedSource } from "./core/transport";
import type { RendererPreference, TrellisSpec } from "./core/types";
import { TrellisView } from "./core/view";

interface Payload {
  spec: TrellisSpec;
  buffers: Record<string, string>;
  renderer: RendererPreference;
  /** The panel opened in Python (Trellis.open), or null. */
  focus?: string | null;
  selection?: Brush | null;
}

declare global {
  interface Window {
    /** The views of the page's plots (tests and debugging). */
    anytrellisViews?: TrellisView[];
  }
}

async function start(host: HTMLElement): Promise<void> {
  const data = host.querySelector<HTMLScriptElement>("script[type='application/json']");
  if (!data || host.dataset.state) return;
  host.dataset.state = "loading";
  try {
    const payload = JSON.parse(data.textContent!) as Payload;
    // ?renderer=webgl2 (etc.) in the page's URL forces a backend: tests and comparisons
    const forced = new URLSearchParams(location.search).get("renderer") as RendererPreference | null;
    const renderer = forced ?? payload.renderer ?? "auto";
    const view = new TrellisView(host, { source: embeddedSource(payload.buffers), renderer });
    (window.anytrellisViews ??= []).push(view);
    if (payload.focus) view.setFocusName(payload.focus);
    if (payload.selection) view.setSelection(payload.selection);
    await view.setSpec(payload.spec);
    // two frames: the first draw happens on the next animation frame
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    host.dataset.state = "ready";
    host.dataset.renderer = view.rendererKind ?? "none";
  } catch (err) {
    host.dataset.state = "error";
    console.error("[anytrellis]", err);
    host.append(`anytrellis could not draw this plot: ${String(err)}`);
  }
}

function startAll(): void {
  document.querySelectorAll<HTMLElement>(".anytrellis-embed").forEach((h) => void start(h));
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startAll);
else startAll();
