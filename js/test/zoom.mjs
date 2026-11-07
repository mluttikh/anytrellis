// Zooming one axis, box zoom, fitting y and undo, on a save_html page of a wrap with shared
// scales:
//   node test/zoom.mjs <page.html> [screenshot dir]
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const file = resolve(process.argv[2]);
const out = resolve(process.argv[3] ?? ".");
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
await page.goto(`file://${file}`);
await page.waitForSelector(".anytrellis-embed[data-state='ready']");
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    return { x: v.views.map((w) => [...w.x]), y: v.views.map((w) => [...w.y]), fit: v.fitY, box: v.mode === "zoom", ghosts: v.front_.ghosts.length };
  });
const layout = await page.evaluate(() => window.anytrellisViews[0].lay.panels);
const stage = await (await page.$(".atr-stage")).boundingBox();
const at = (rect, fx, fy) => [stage.x + rect.x + rect.w * fx, stage.y + rect.y + rect.h * fy];
const span = (r) => r[1] - r[0];
const near = (a, b, tol = 1e-6) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(a), Math.abs(b));
const same = (a, b) => a.every((r, i) => near(r[0], b[i][0]) && near(r[1], b[i][1]));
const wait = () => page.waitForTimeout(120);

const p0 = layout[0].rect;
const yAxis = layout[0].yAxis;
const xAxis = layout.find((b) => b.xAxis).xAxis;
await page.mouse.click(...at(p0, 0.5, 0.5)); // focus: the wheel zooms
const start = await state();

// Shift+wheel zooms y, also as macOS sends it (a sideways scroll)
await page.keyboard.down("Shift");
await page.mouse.wheel(-300, 0);
await page.keyboard.up("Shift");
await wait();
let s = await state();
check(span(s.y[0]) < span(start.y[0]) && same(s.x, start.x), "Shift+wheel sent sideways (macOS) zooms y, not x");
check(s.y.every((r) => near(r[0], s.y[0][0])), "y zooms in every panel that shares it");
await page.keyboard.press("r");

// a trackpad's sideways swipe pans x
await page.mouse.wheel(200, 0);
await wait();
s = await state();
check(s.x[0][0] > start.x[0][0] && near(span(s.x[0]), span(start.x[0])), "a sideways swipe pans x");
await page.keyboard.press("r");

// the wheel over the y axis zooms y; over the x axis, x
await page.mouse.move(stage.x + yAxis.x + yAxis.w / 2, stage.y + yAxis.y + yAxis.h / 2);
await page.mouse.wheel(0, -300);
await wait();
s = await state();
check(span(s.y[0]) < span(start.y[0]) && same(s.x, start.x), "the wheel over the y axis zooms y alone");
await page.keyboard.press("r");
await page.mouse.move(stage.x + xAxis.x + xAxis.w / 2, stage.y + xAxis.y + xAxis.h / 2);
await page.mouse.wheel(0, -300);
await wait();
s = await state();
check(span(s.x[0]) < span(start.x[0]) && same(s.y, start.y), "the wheel over the x axis zooms x alone");
await page.keyboard.press("r");

// dragging the y axis pans y alone; double-clicking it resets y (and opens no panel)
const ay = [stage.x + yAxis.x + yAxis.w / 2, stage.y + yAxis.y + yAxis.h / 2];
await page.mouse.move(...ay);
const cursor = await page.$eval(".atr-front", (e) => e.style.cursor);
check(cursor === "ns-resize", `the y axis shows it drags up and down (${cursor})`);
await page.mouse.down();
await page.mouse.move(ay[0], ay[1] + 40, { steps: 4 });
await page.mouse.up();
s = await state();
check(s.y[0][0] > start.y[0][0] && same(s.x, start.x), "dragging the y axis pans y alone");
await page.mouse.dblclick(...ay);
await wait();
s = await state();
const opened = await page.evaluate(() => window.anytrellisViews[0].focusName);
check(same(s.y, start.y) && opened === null, "double-clicking the y axis resets y, and opens no panel");

// Shift+drag: a mostly sideways box zooms x alone, to the box
const drag = async (from, to, shift = true) => {
  if (shift) await page.keyboard.down("Shift");
  await page.mouse.move(...from);
  await page.mouse.down();
  await page.mouse.move(...to, { steps: 6 });
  const during = await state();
  if (shift) await page.screenshot({ path: join(out, "zoom-box.png") });
  await page.mouse.up();
  if (shift) await page.keyboard.up("Shift");
  await wait();
  return during;
};
let during = await drag(at(p0, 0.2, 0.5), at(p0, 0.6, 0.53));
s = await state();
const want = [start.x[0][0] + 0.2 * span(start.x[0]), start.x[0][0] + 0.6 * span(start.x[0])];
check(near(s.x[0][0], want[0], 0.01) && near(s.x[0][1], want[1], 0.01) && same(s.y, start.y), "a sideways Shift+drag zooms x alone, to the box");
check(during.ghosts === layout.length - 1, `while it is drawn, the other panels of its x group show it (${during.ghosts})`);
const afterX = s;
// mostly up or down: y alone
await drag(at(p0, 0.5, 0.2), at(p0, 0.52, 0.7));
s = await state();
check(same(s.x, afterX.x) && span(s.y[0]) < span(start.y[0]) * 0.6, "an up-or-down Shift+drag zooms y alone");
// both
const beforeBoth = s;
await drag(at(p0, 0.2, 0.2), at(p0, 0.7, 0.8));
s = await state();
check(span(s.x[0]) < span(beforeBoth.x[0]) && span(s.y[0]) < span(beforeBoth.y[0]), "a diagonal Shift+drag zooms both");

// undo, step by step: u and Cmd/Ctrl+Z
await page.keyboard.press("u");
await wait();
check(same((await state()).x, beforeBoth.x), "u undoes the last zoom");
await page.keyboard.press("Meta+z");
await page.keyboard.press("Control+z");
await wait();
s = await state();
check(same(s.x, start.x) && same(s.y, start.y), "Cmd/Ctrl+Z undoes the ones before");

// z: plain drag draws a box; Shift+drag pans then
await page.keyboard.press("z");
s = await state();
check(s.box, "z: box zoom mode");
await drag(at(p0, 0.3, 0.5), at(p0, 0.6, 0.52), false);
s = await state();
check(span(s.x[0]) < span(start.x[0]) * 0.5, "in box zoom mode, plain drag draws a box");
await page.keyboard.press("z");
await page.keyboard.press("r");

// y fits the data in view: zoom x, y follows; zooming y by hand stops it
await page.keyboard.press("y");
s = await state();
check(s.fit && (await page.$eval(".atr-toolbar [aria-pressed='true']", (b) => b.title)).startsWith("Fit y"), "y: fitting y, and its button shows it");
await drag(at(p0, 0.45, 0.5), at(p0, 0.5, 0.52));
s = await state();
check(span(s.y[0]) < span(start.y[0]), `y fits the data in the zoomed x (${span(s.y[0]).toFixed(2)} of ${span(start.y[0]).toFixed(2)})`);
check(s.y.every((r) => near(r[0], s.y[0][0]) && near(r[1], s.y[0][1])), "a shared y fits all its panels together");
const fitted = s;
await page.mouse.move(...at(p0, 0.5, 0.5));
await page.mouse.down();
await page.mouse.move(...at(p0, 0.4, 0.7), { steps: 4 });
await page.mouse.up();
s = await state();
check(near(s.y[0][0], fitted.y[0][0], 0.05) && s.x[0][0] > fitted.x[0][0], "with y fitted, dragging pans x (y follows)");
await page.screenshot({ path: join(out, "zoom-fit.png") });
await page.keyboard.down("Shift");
await page.mouse.wheel(0, -200);
await page.keyboard.up("Shift");
await wait();
s = await state();
check(!s.fit, "zooming y by hand stops fitting it");
await page.keyboard.press("r");

// the keys stay in the plot
await page.evaluate(() => {
  window.leaked = [];
  document.addEventListener("keydown", (e) => window.leaked.push(e.key));
});
for (const k of ["y", "z", "u", "Meta+z"]) await page.keyboard.press(k);
const leaked = (await page.evaluate(() => window.leaked)).filter((k) => !["Meta", "Control", "Shift"].includes(k)); // a modifier's own press is no shortcut
check(leaked.length === 0, `y, z, u and Cmd+Z stay in the plot (reached the page: ${leaked})`);
check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
