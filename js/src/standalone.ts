// Standalone plots (Trellis.save_html / to_html): the data embedded in the page, so they
// work without a kernel. Any number per page: <div class="anytrellis-embed"> holding a
// <script type="application/json"> with {spec, buffers (id → base64), renderer}. Plots
// saved linked (Link.save_html) carry their marks' keys and are linked here (savedlink.ts).

import type { FigurePlace } from "./core/align";
import { FigureLegend } from "./core/figurelegend";
import { LinkGroup, type SavedLink, readLink } from "./core/savedlink";
import type { Brush } from "./core/selection";
import { embeddedSource } from "./core/transport";
import type { Paging, RendererPreference, SavedView, TableView, TrellisSpec, Zoom } from "./core/types";
import { TrellisView } from "./core/view";

interface Payload {
  spec: TrellisSpec;
  buffers: Record<string, string>;
  renderer: RendererPreference;
  /** The panel opened in Python (Trellis.open), or null. */
  focus?: string | null;
  /** The panel drawn faintly in every other (Trellis.compare), or null. */
  compare?: string | null;
  selection?: Brush | null;
  /** The page, sort and filters of a paged wrap. */
  paging?: Paging | null;
  /** The Python that made the plot as saved (Trellis.code), or null: controls=False. */
  code?: string | null;
  /** Its marks' keys in a link saved with it (Link.save_html), or null. */
  link?: SavedLink | null;
  /** The views kept (Trellis.save_view): the Views menu's, and #view=<name>'s. */
  views?: Record<string, SavedView> | null;
  /** The zoom it opens with (a view shown in Python), or null: as the plot starts. */
  zoom?: Zoom | null;
  /** The table view's data (Trellis._table_view). */
  table?: TableView | null;
  /** Its place in a figure that lines up its plots (Concat._cell), or null. */
  figure?: FigurePlace | null;
}

/** The view a link to the page names: #view=<name>. */
function viewInHash(): string | null {
  return new URLSearchParams(location.hash.slice(1)).get("view");
}

/** The page's links, by group. */
const groups = new Map<string, LinkGroup>();

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
    const code = payload.code ?? null;
    const link = payload.link ?? null;
    let group: LinkGroup | undefined;
    if (link) {
      group = groups.get(link.group);
      if (!group) groups.set(link.group, (group = new LinkGroup(link.size)));
    }
    // a link's other plots follow a brush as it moves: once a frame
    let pending = false;
    const changed = (): void => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => {
        pending = false;
        group?.changed(view);
      });
    };
    const view = new TrellisView(host, {
      source: embeddedSource(payload.buffers),
      renderer,
      code: () => code,
      table: payload.table ? async () => payload.table ?? null : undefined,
      onSelect: group ? changed : undefined,
      onBrushing: group ? changed : undefined,
      onClear: group ? () => group!.clear() : undefined,
    });
    (window.anytrellisViews ??= []).push(view);
    if (payload.focus) view.setFocusName(payload.focus);
    if (payload.compare) view.setCompareName(payload.compare);
    if (payload.selection) view.setSelection(payload.selection);
    if (payload.paging) view.setPaging(payload.paging);
    if (payload.views) view.setViews(payload.views);
    if (payload.zoom) view.setZoom(payload.zoom);
    if (payload.figure) view.setFigure(payload.figure);
    await view.setSpec(payload.spec);
    const named = viewInHash();
    if (named) view.showView(named);
    if (group && link) {
      group.add(view, readLink(link));
      if (payload.selection) group.changed(view); // a selection saved: it leads
    }
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

// A plot starts when it comes near the screen: each holds a GPU context, and browsers keep
// only so many (Chrome 16 WebGL contexts, fewer on phones; past that the oldest are lost),
// so a page of many plots (the documentation) starts only those read. One in view, or in a
// browser without IntersectionObserver, starts at once.
const NEAR = "600px";

function startAll(): void {
  // a figure's legend, collected from its plots: it fills in as they start
  for (const host of document.querySelectorAll<HTMLElement>(".anytrellis-figure-legend")) {
    if (host.dataset.legend && !host.dataset.state) {
      host.dataset.state = "ready";
      new FigureLegend(host, host.dataset.legend);
    }
  }
  const hosts = document.querySelectorAll<HTMLElement>(".anytrellis-embed");
  if (typeof IntersectionObserver === "undefined") {
    hosts.forEach((h) => void start(h));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        // a link's plots start together (a selection saved in one shows in the others), and
        // a figure's (lined up with each other)
        const link = e.target.closest(".anytrellis-link, .anytrellis-concat");
        const group = link ? [...link.querySelectorAll<HTMLElement>(".anytrellis-embed")] : [e.target as HTMLElement];
        for (const h of group) {
          observer.unobserve(h);
          void start(h);
        }
      }
    },
    { rootMargin: NEAR },
  );
  hosts.forEach((h) => observer.observe(h));
}

// a link to another view of the page (#view=<name>): each plot that has it shows it
window.addEventListener("hashchange", () => {
  const named = viewInHash();
  if (named) window.anytrellisViews?.forEach((v) => v.showView(named));
});

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startAll);
else startAll();
