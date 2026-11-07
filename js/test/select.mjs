// Selecting on a save_html page: s, a brush that holds in every panel (linked: in its own,
// the link spreading it), moving it, a click
// and Esc clearing it, Shift+drag still zooming; with ?renderer= each backend.
//   node test/select.mjs <page.html> [screenshot dir] [renderer]
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const file = resolve(process.argv[2]);
const out = resolve(process.argv[3] ?? ".");
const renderer = process.argv[4] ?? "";
function executable() {
  if (process.env.CHROMIUM) return process.env.CHROMIUM;
  if (existsSync(chromium.executablePath())) return undefined;
  const cache = join(homedir(), "Library/Caches/ms-playwright");
  for (const d of readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse()) {
    const app = join(cache, d, "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
    if (existsSync(app)) return app;
  }
}
const browser = await chromium.launch({ executablePath: executable(), args: ["--enable-unsafe-webgpu", ...(process.platform === "darwin" ? ["--use-angle=metal"] : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])] });
const page = await browser.newPage({ viewport: { width: 1000, height: 800 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(`file://${file}${renderer ? `?renderer=${renderer}` : ""}`);
await page.waitForSelector(".anytrellis-embed[data-state='ready']");
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const tag = renderer || (await page.$eval(".anytrellis-embed", (e) => e.dataset.renderer));
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    return {
      brush: v.brush,
      sel: v.selected,
      brushes: v.front_.brushes.length,
      panels: v.views.length,
      x: v.views.map((w) => [...w.x]),
      mode: v.mode,
      linked: v.scene.layers.some((l) => l.link),
    };
  });
const layout = await page.evaluate(() => window.anytrellisViews[0].lay.panels);
const stage = await (await page.$(".atr-stage")).boundingBox();
const at = (rect, fx, fy) => [stage.x + rect.x + rect.w * fx, stage.y + rect.y + rect.h * fy];
const p0 = layout[0].rect;
const drag = async (from, to, shift = false) => {
  if (shift) await page.keyboard.down("Shift");
  await page.mouse.move(...from);
  await page.mouse.down();
  await page.mouse.move(...to, { steps: 6 });
  await page.mouse.up();
  if (shift) await page.keyboard.up("Shift");
  await page.waitForTimeout(150);
};

await page.mouse.click(...at(p0, 0.5, 0.5));
await page.keyboard.press("Escape"); // a selection saved with the page: gone
await page.keyboard.press("s");
let s = await state();
check(s.mode === "select" && (await page.$eval(".atr-toolbar [aria-pressed='true']", (b) => b.title)).startsWith("Select"), "s: select mode, and its button shows it");

// a sideways brush: an x range, in every panel
await drag(at(p0, 0.2, 0.5), at(p0, 0.5, 0.52));
s = await state();
check(s.brush && s.brush.x && s.brush.y === null, "a sideways drag brushes an x range");
check(s.sel && s.sel.selected > 0 && s.sel.selected < s.sel.total, `some marks are selected (${s.sel?.selected} of ${s.sel?.total})`);
if (s.linked) check(s.brushes === 1 && s.brush.panel === 0, "linked: the brush selects in its own panel (the link spreads it)");
else check(s.brushes === s.panels, `the brush shows in every panel (${s.brushes} of ${s.panels})`);
await page.screenshot({ path: join(out, `select-${tag}.png`) });
const first = s;

// drag inside the brush: it moves
await drag(at(p0, 0.35, 0.5), at(p0, 0.55, 0.5));
s = await state();
const moved = s.brush.x[0] - first.brush.x[0];
const width = first.x[0][1] - first.x[0][0];
check(Math.abs(moved - 0.2 * width) < 0.02 * width, "dragging the brush moves it");
const kept = s.brush.x[1] - s.brush.x[0];
const was = first.brush.x[1] - first.brush.x[0];
check(Math.abs(kept - was) <= 1e-9 * Math.abs(was), `and keeps its size (${kept} of ${was})`);

// a diagonal brush: x and y
await drag(at(p0, 0.05, 0.05), at(p0, 0.15, 0.95));
s = await state();
check(s.brush.x && s.brush.y, "a diagonal drag brushes x and y");

// Shift+drag still zooms; the brush stays
const before = s;
await drag(at(p0, 0.3, 0.5), at(p0, 0.7, 0.52), true);
s = await state();
check(s.x[0][1] - s.x[0][0] < before.x[0][1] - before.x[0][0] && s.brush, "Shift+drag zooms, and the selection stays");
await page.keyboard.press("r");

// a click clears; so does Esc
await page.mouse.click(...at(p0, 0.9, 0.9));
await page.waitForTimeout(100);
s = await state();
check(s.brush === null && s.sel === null, "a click clears the selection");
await drag(at(p0, 0.2, 0.5), at(p0, 0.5, 0.52));
await page.keyboard.press("Escape");
await page.waitForTimeout(100);
s = await state();
check(s.brush === null, "Esc clears the selection");
await page.keyboard.press("s");
s = await state();
check(s.mode === "pan", "s again: drag pans");
check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
