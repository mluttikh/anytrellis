// The legend on save_html pages: hovering an entry shows its marks, a double-click shows it
// alone, dragging on a gradient selects a range of a number colour, a stepped scale's bin
// selects its range, and a long legend (over the panels) shows its first entries and a search.
//   node test/legends.mjs <pages dir> [screenshot dir] [renderer]
import { existsSync, readdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const dir = resolve(process.argv[2]);
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
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const open = async (name) => {
  await page.goto(`file://${join(dir, name)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
};
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    return { legend: v.brush?.legend ?? null, sel: v.selected, preview: v.preview, isolated: v.isolated };
  });
const plot = page.locator(".atr-stage");
const settle = () => page.waitForTimeout(250);
const tag = renderer || "default";

// ---- a category legend: hover, double-click ------------------------------------------------
await open("years.html");
const items = page.locator(".atr-legend-pick");
await page.mouse.move(1, 1);
await settle();
const plain = await plot.screenshot();
await items.nth(1).hover();
await settle();
let s = await state();
check(JSON.stringify(s.preview?.levels) === "[1]" && s.sel === null, "hovering an entry shows its marks, not a selection");
const hovered = await plot.screenshot();
check(!hovered.equals(plain), "the other colours fade while it is hovered");
await plot.screenshot({ path: join(out, `legend-hover-${tag}.png`) });
await page.mouse.move(1, 1);
await settle();
s = await state();
check(s.preview === null && (await plot.screenshot()).equals(plain), "leaving it: the plot as it was");

await items.nth(1).dblclick();
await settle();
s = await state();
check(s.isolated?.level === 1 && s.legend === null, "a double-click shows the entry alone (no selection left by its clicks)");
const struck = await page.$$eval(".atr-legend-pick", (els) => els.map((e) => e.classList.contains("atr-legend-hidden")));
check(struck.filter(Boolean).length === struck.length - 1 && !struck[1], "the other entries are struck through");
await page.mouse.move(1, 1);
await settle();
const alone = await plot.screenshot();
check(!alone.equals(plain), "the others' marks are hidden");
await plot.screenshot({ path: join(out, `legend-alone-${tag}.png`) });
// hidden marks have no tooltip: hover where another colour's point is
const hiddenTip = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const scene = v.scene;
  const layer = scene.layers[0];
  const i = layer.codes.findIndex((c) => c !== 1);
  const view = v.views.find((w) => w.panel === [...layer.starts].findIndex((st, p) => st <= i && i < layer.starts[p + 1]));
  if (!view) return null;
  const m = view.map;
  const x = m.ox + (scene.baseX[view.panel] + layer.set.coords[i * 4]) * m.sx;
  const y = m.oy + (scene.baseY[view.panel] + layer.set.coords[i * 4 + 1]) * m.sy;
  return { x, y };
});
if (hiddenTip) {
  const box = await plot.boundingBox();
  await page.mouse.move(box.x + hiddenTip.x, box.y + hiddenTip.y);
  await settle();
  const swatch = await page.$eval(".atr-tip", (t) => (getComputedStyle(t).display === "none" ? "" : t.textContent ?? ""));
  const level0 = await page.$eval(".atr-legend-pick", (e) => e.textContent);
  check(!swatch.includes(level0 ?? "\u0000") || swatch === "", "a hidden mark has no tooltip");
  await page.mouse.move(1, 1);
}
await items.nth(1).dblclick();
await settle();
s = await state();
check(s.isolated === null && s.legend === null, "a double-click again shows every entry");
await page.mouse.move(1, 1);
await page.evaluate(() => document.activeElement?.blur?.()); // no focus ring
await page.waitForTimeout(1800); // the notice of its clicks fades
const again = await plot.screenshot();
check(again.equals(plain), "the plot is as it was");
if (!again.equals(plain)) {
  writeFileSync(join(out, `legends-plain-${tag}.png`), plain);
  writeFileSync(join(out, `legends-again-${tag}.png`), again);
}
await items.nth(2).dblclick();
await page.focus(".atr-root");
await page.keyboard.press("Escape");
s = await state();
check(s.isolated === null, "Esc shows every entry");
// a selection made before survives a double-click
await items.nth(0).click();
await items.nth(2).dblclick();
s = await state();
check(JSON.stringify(s.legend?.levels) === "[0]" && s.isolated?.level === 2, "a double-click keeps the selection before it");
await page.keyboard.press("Escape");
await page.keyboard.press("Escape");

// ---- a number colour: drag on its gradient --------------------------------------------------
await open("legend-number.html");
const bar = page.locator(".atr-gradient");
check((await bar.getAttribute("class"))?.includes("atr-gradient-pick"), "a number colour's gradient can be dragged on");
const g = await bar.boundingBox();
await page.mouse.move(g.x + g.width * 0.6, g.y + g.height / 2);
await page.mouse.down();
await page.mouse.move(g.x + g.width * 0.9, g.y + g.height / 2, { steps: 5 });
await page.mouse.up();
await settle();
s = await state();
const lg = await page.evaluate(() => window.anytrellisViews[0].spec.legends[0]);
const span = lg.hi - lg.lo;
const want = [lg.lo + 0.6 * span, lg.lo + 0.9 * span];
const range = s.legend?.range;
check(!!range && Math.abs(range[0] - want[0]) < span * 0.03 && Math.abs(range[1] - want[1]) < span * 0.03, `a drag selects a range of the values: ${range?.map((v) => v.toFixed(1))}`);
check(s.sel && s.sel.selected > 0 && s.sel.selected < s.sel.total, `the marks of values in it: ${s.sel?.selected} of ${s.sel?.total}`);
const win = await page.$eval(".atr-gradient-window", (w) => getComputedStyle(w).display);
check(win === "block", "the range shows on the gradient");
await plot.screenshot({ path: join(out, `legend-range-${tag}.png`) });
await page.mouse.click(g.x + g.width * 0.2, g.y + g.height / 2);
s = await state();
check(s.legend === null && s.sel === null, "a click on the gradient clears it");

// ---- a stepped scale: a bin's range ---------------------------------------------------------
await open("legend-bins.html");
const binItems = page.locator(".atr-legend-pick");
check((await binItems.count()) >= 3, "a stepped scale's bins can be clicked");
const breaks = await page.evaluate(() => window.anytrellisViews[0].spec.legends[0].breaks);
await binItems.nth(1).click();
s = await state();
check(JSON.stringify(s.legend?.range) === JSON.stringify([breaks[1], breaks[2]]) && s.sel?.selected > 0, "a click on a bin selects its range");
let on = await page.$$eval(".atr-legend-pick", (els) => els.map((e) => e.classList.contains("atr-legend-on")));
check(on[1] && on.filter(Boolean).length === 1, "its entry is pressed");
await binItems.nth(2).click({ modifiers: ["Shift"] });
s = await state();
check(JSON.stringify(s.legend?.range) === JSON.stringify([breaks[1], breaks[3]]), "Shift+click widens the range");
on = await page.$$eval(".atr-legend-pick", (els) => els.map((e) => e.classList.contains("atr-legend-on")));
check(on[1] && on[2] && on.filter(Boolean).length === 2, "the bins in it are pressed");
await page.keyboard.press("Escape");

// ---- a long legend over the panels ----------------------------------------------------------
await open("legend-many.html");
const legendBox = await page.locator(".atr-legend").boundingBox();
const stageBox = await plot.boundingBox();
check(legendBox.y + legendBox.height <= stageBox.y + 1, "legend('top'): over the panels");
const shown = () => page.$$eval(".atr-legend-item", (els) => els.filter((e) => !e.hidden).map((e) => e.textContent));
check((await shown()).length === 20, "the first 20 of 30 entries");
check((await page.textContent(".atr-legend-more")) === "10 more", "and how many more");
const find = page.locator(".atr-legend-search");
const names = await page.evaluate(() => window.anytrellisViews[0].spec.legends[0].labels);
const last = names[names.length - 1];
await find.fill(last.slice(0, 4));
const found = await shown();
check(found.includes(last) && found.every((t) => t.toLowerCase().includes(last.slice(0, 4).toLowerCase())), `a search finds the rest: ${found.join(", ")}`);
await find.press("Escape");
check((await shown()).length === 20 && (await find.inputValue()) === "", "Esc empties the search");
await page.locator(".atr-root").screenshot({ path: join(out, `legend-many-${tag}.png`) });

check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
