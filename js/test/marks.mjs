// Hexagonal bins, density contours, rugs and segments on save_html pages: hexagons hovered
// inside, rugs that stay at the panels' edges as the panels zoom and that a brush selects by
// their values alone, segments drawn whole, and an exported SVG of them.
//   node test/marks.mjs <pages dir> [screenshot dir] [renderer]
import { existsSync, readFileSync, readdirSync } from "node:fs";
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
const page = await browser.newPage({ viewport: { width: 1000, height: 800 }, acceptDownloads: true });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const tag = renderer || "default";
const open = async (name) => {
  await page.goto(`file://${join(dir, name)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  await page.waitForTimeout(200);
};
const tip = () => page.$eval(".atr-tip:not(.atr-tip-pinned)", (t) => ({
  shown: getComputedStyle(t).display === "block",
  rows: [...t.querySelectorAll("tr")].map((r) => [r.querySelector("th").textContent.trim(), r.querySelector("td").textContent.trim()]),
}));
/** Ink on the marks' canvas in a box of CSS px (null: a WebGPU canvas, not read back). */
const ink = (x, y, w, h) => page.evaluate(([x, y, w, h]) => {
  const v = window.anytrellisViews[0];
  if (v.renderer.kind === "webgpu") return null;
  const marks = v.renderer.canvas;
  const copy = document.createElement("canvas");
  copy.width = marks.width;
  copy.height = marks.height;
  const ctx = copy.getContext("2d");
  ctx.drawImage(marks, 0, 0);
  const d = ctx.getImageData(Math.round(x * v.dpr), Math.round(y * v.dpr), Math.max(1, Math.round(w * v.dpr)), Math.max(1, Math.round(h * v.dpr))).data;
  let on = 0;
  for (let i = 3; i < d.length; i += 4) on += d[i] > 40 ? 1 : 0;
  return on;
}, [x, y, w, h]);
async function exportSvg(name) {
  await page.click(".atr-toolbar button[aria-haspopup='menu']");
  const downloading = page.waitForEvent("download");
  await page.click(".atr-export-item[data-export='svg']");
  const d = await downloading;
  const path = join(out, `marks-${tag}-${name}.svg`);
  await d.saveAs(path);
  return readFileSync(path, "utf8");
}

// ---- hexagonal bins ------------------------------------------------------------------------
await open("hexbin.html");
const hex = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const layer = v.scene.layers[0];
  const w = v.views[0];
  const i = layer.starts[w.panel]; // a left half: its right side is the hexagon's middle
  const c = layer.coords;
  const b = layer.base;
  const cy = (c[i * 4 + 3] + b[i * 2 + 1]) / 2;
  const r = v.stage.getBoundingClientRect();
  return { type: layer.spec.type, count: layer.spec.count, legend: v.spec.legends.map((l) => l.kind), x: r.left + w.map.ox + c[i * 4 + 2] * w.map.sx - 2, y: r.top + w.map.oy + cy * w.map.sy };
});
check(hex.type === "band" && hex.count > 20 && hex.count % 2 === 0, `hexagons, two halves each (${hex.count})`);
check(hex.legend.includes("number"), "coloured by their counts, with a colour bar");
await page.mouse.move(hex.x - 3, hex.y - 3);
await page.mouse.move(hex.x, hex.y);
await page.waitForTimeout(120);
const t = await tip();
check(t.shown && t.rows.some(([k, v]) => k === "count" && Number(v) >= 1), `hovering inside a hexagon tells its count (${JSON.stringify(t.rows)})`);
await page.mouse.move(5, 5);
await page.screenshot({ path: join(out, `marks-hexbin-${tag}.png`) });
const hexSvg = await exportSvg("hexbin");
check((hexSvg.match(/<path/g) ?? []).length > 3, "the exported SVG draws them");

// ---- contours and rugs ---------------------------------------------------------------------
await open("contours.html");
const layers = await page.evaluate(() => window.anytrellisViews[0].scene.layers.map((l) => ({ name: l.spec.name, type: l.spec.type, pin: l.spec.pin ?? null, count: l.spec.count })));
const contour = layers.find((l) => l.name === "contour");
check(contour?.type === "line" && contour.count > 50, `contours drawn as lines (${contour?.count})`);
const rugX = layers.findIndex((l) => l.name === "rug");
const rugY = layers.findIndex((l) => l.name === "rug_y");
check(layers[rugX]?.pin === "y" && layers[rugY]?.pin === "x", "a rug of x along the bottom edge, of y along the left");
/** Where the rug's first tick of the first panel is drawn, and the panel. */
const tick = () => page.evaluate((li) => {
  const v = window.anytrellisViews[0];
  const layer = v.scene.layers[li];
  const w = v.views[0];
  const i = layer.starts[w.panel];
  const draw = v.markDraws([w]).find((d) => d.set.key.startsWith(`${li}:`) || d.set === layer.set);
  return { x: w.map.ox + layer.coords[i * 4] * w.map.sx, top: w.rect.y + w.rect.h - layer.coords[i * 4 + 3], bottom: w.rect.y + w.rect.h, rect: w.rect, oy: draw?.oy, sy: draw?.sy, y: [...w.y] };
}, rugX);
const before = await tick();
check(before.sy === -1 && Math.abs(before.oy - before.bottom) < 1e-6, "its ticks measured up from the panel's bottom");
const inkBefore = await ink(before.x - 1, before.top + 1, 2, before.bottom - before.top - 2);
if (inkBefore !== null) check(inkBefore > 0, `a tick drawn there (${inkBefore} px)`);
// zoom y in on the first panel: the rug stays at the bottom edge
const stage = await (await page.$(".atr-stage")).boundingBox();
await page.mouse.click(stage.x + before.rect.x + before.rect.w / 2, stage.y + before.rect.y + before.rect.h / 2);
await page.keyboard.down("Shift");
await page.mouse.wheel(0, -400);
await page.keyboard.up("Shift");
await page.waitForTimeout(300);
const after = await tick();
check(after.y[1] - after.y[0] < before.y[1] - before.y[0], `y zoomed in (${before.y.map((v) => v.toFixed(1))} to ${after.y.map((v) => v.toFixed(1))})`);
check(Math.abs(after.oy - after.bottom) < 1e-6 && Math.abs(after.top - before.top) < 1e-6, "the rug still at the bottom edge, as long");
const inkAfter = await ink(after.x - 1, after.top + 1, 2, after.bottom - after.top - 2);
if (inkAfter !== null) check(inkAfter > 0, `and drawn there (${inkAfter} px)`);
await page.keyboard.press("r");
// a brush over the middle of x and the top of y: the x rug's ticks of that x are selected
const chosen = await page.evaluate(([rx, ry]) => {
  const v = window.anytrellisViews[0];
  const p = v.spec.panels[0];
  const x = [p.x[0] + (p.x[1] - p.x[0]) * 0.4, p.x[0] + (p.x[1] - p.x[0]) * 0.6];
  const y = [p.y[0] + (p.y[1] - p.y[0]) * 0.8, p.y[1]];
  v.setSelection({ x, y, panel: 0, legend: null });
  void v.selected; // (settled lazily, once a frame)
  const sel = v.selection;
  const count = (li) => sel.masks[li].reduce((a, b) => a + b, 0);
  const layer = v.scene.layers[rx];
  let inside = 0;
  for (let i = layer.starts[0]; i < layer.starts[1]; i++) inside += layer.coords[i * 4] >= x[0] && layer.coords[i * 4] <= x[1] ? 1 : 0;
  return { x: count(rx), inside, y: count(ry) };
}, [rugX, rugY]);
check(chosen.x === chosen.inside && chosen.x > 0, `a brush selects the x rug's ticks by x alone (${chosen.x} of ${chosen.inside})`);
await page.screenshot({ path: join(out, `marks-contours-${tag}.png`) });
await page.evaluate(() => window.anytrellisViews[0].setSelection(null));
// hovering a rug's tick: no tooltip of it
await page.mouse.move(stage.x + before.x, stage.y + before.bottom - 3);
await page.waitForTimeout(120);
const overRug = await page.evaluate(() => window.anytrellisViews[0].front_.hovers.map((h) => h.layer ?? null));
check(!overRug.some((l) => l === rugX || l === rugY), "a rug is not hovered");
const rugSvg = await exportSvg("contours");
check((rugSvg.match(/<path/g) ?? []).length > 10, "the exported SVG draws contours and rugs");

// ---- segments ------------------------------------------------------------------------------
await open("segments.html");
const seg = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const layer = v.scene.layers[0];
  const w = v.views[0];
  const i = layer.starts[w.panel];
  const c = layer.coords;
  const r = v.stage.getBoundingClientRect();
  return { type: layer.spec.type, count: layer.spec.count, x: r.left + w.map.ox + c[i * 4 + 2] * w.map.sx, y: r.top + w.map.oy + c[i * 4 + 3] * w.map.sy, len: Math.hypot((c[i * 4 + 2] - c[i * 4]) * w.map.sx, (c[i * 4 + 3] - c[i * 4 + 1]) * w.map.sy) };
});
check(seg.type === "line" && seg.count > 50, `a segment a country (${seg.count})`);
await page.mouse.move(seg.x - 3, seg.y - 3);
await page.mouse.move(seg.x, seg.y);
await page.waitForTimeout(120);
const st = await tip();
// (a saved page has no Python for the tooltip's columns: the hovered values only)
check(st.shown && st.rows.some(([k]) => k.startsWith("life_expect")), `hovering a segment's end tells its values (${JSON.stringify(st.rows)})`);
await page.mouse.move(5, 5);
await page.screenshot({ path: join(out, `marks-segments-${tag}.png`) });

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
