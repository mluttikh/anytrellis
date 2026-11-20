// Reversed axes on a save_html page (pages.py: reversed.html, x high to low, y a sqrt
// scale high at the bottom): the marks, a box zoom, panning, a brush and an exported image
// all run the reversed way; with ?renderer= each backend.
//   node test/reverse.mjs <page.html> [screenshot dir] [renderer]
import { existsSync, readFileSync, readdirSync } from "node:fs";
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
    const w = v.views[0];
    return { x: [...w.x], y: [...w.y], map: { ...w.map }, brush: v.brush, mode: v.mode, spec: { x: v.spec.x, y: v.spec.y } };
  });
const near = (a, b, tol) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(b));
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

const start = await state();
check(start.spec.x.reverse === true && start.spec.y.reverse === true && start.spec.y.kind === "sqrt", "the spec says x and y are reversed, y on a sqrt scale");
check(start.map.sx < 0 && start.map.sy > 0, "x runs right to left, y top to bottom");
const pxOf = (m, x, y) => [m.ox + x * m.sx, m.oy + y * m.sy];
const [left, top] = pxOf(start.map, start.x[1], start.y[1]);
check(Math.abs(left - p0.x) < 0.5 && Math.abs(top - (p0.y + p0.h)) < 0.5, "the high ends are at the left and at the bottom");
await page.screenshot({ path: join(out, `reverse-${tag}.png`) });

// a sideways Shift+drag over 20% to 50% of the panel's width: the values there, reversed
const span = start.x[1] - start.x[0];
await drag(at(p0, 0.2, 0.5), at(p0, 0.5, 0.52), true);
let s = await state();
const want = [start.x[1] - 0.5 * span, start.x[1] - 0.2 * span];
check(near(s.x[0], want[0], 0.01) && near(s.x[1], want[1], 0.01), `a box zooms x to the values under it (${s.x.map((v) => v.toFixed(2))} vs ${want.map((v) => v.toFixed(2))})`);
await page.keyboard.press("r");
await page.waitForTimeout(100);

// a drag to the right moves the content right: the higher values at the left come in
await drag(at(p0, 0.4, 0.5), at(p0, 0.6, 0.5));
s = await state();
check(s.x[0] > start.x[0] + 0.1 * span && near(s.x[1] - s.x[0], span, 1e-6), `dragging right pans x to higher values (${s.x.map((v) => v.toFixed(2))} from ${start.x.map((v) => v.toFixed(2))})`);
await page.keyboard.press("r");
await page.waitForTimeout(100);

// a brush: its x range low to high, the values under it
await page.keyboard.press("s");
await drag(at(p0, 0.2, 0.5), at(p0, 0.5, 0.52));
s = await state();
check(s.brush && s.brush.x && s.brush.x[0] < s.brush.x[1] && near(s.brush.x[0], want[0], 0.01) && near(s.brush.x[1], want[1], 0.01), "a brush holds the values under it, low to high");
// up and down on the reversed y: low values at the top
await page.keyboard.press("Escape");
await drag(at(p0, 0.5, 0.1), at(p0, 0.52, 0.4));
s = await state();
const ySpan = start.y[1] - start.y[0];
const wantY = [start.y[0] + 0.1 * ySpan, start.y[0] + 0.4 * ySpan];
check(s.brush && s.brush.y && near(s.brush.y[0], wantY[0], 0.02) && near(s.brush.y[1], wantY[1], 0.02), "a brush on the reversed y holds the low values at the top");
await page.keyboard.press("Escape");

// the image saved from the page: the tick labels run the reversed way too
await page.click(".atr-toolbar button[aria-haspopup='menu']");
const downloading = page.waitForEvent("download");
await page.click(".atr-export-item[data-export='svg']");
const saved = join(out, `reverse-${tag}.svg`);
await (await downloading).saveAs(saved);
const labels = await page.evaluate((text) => {
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  return [...doc.querySelectorAll("text")].map((t) => [t.textContent, Number(t.getAttribute("x")), Number(t.getAttribute("y"))]);
}, readFileSync(saved, "utf8"));
const xOf = (label) => labels.find((l) => l[0] === label)?.[1];
check(xOf("2") > xOf("6"), `the saved image puts fertility 2 right of 6 (${xOf("2")}, ${xOf("6")})`);
const yOf = (label) => labels.find((l) => l[0] === label)?.[2];
check(labels.filter((l) => l[0] === "0").length >= 3 && yOf("0") < yOf("1.0G"), `and population 0 above 1.0G, every row of panels labelled (${yOf("0")}, ${yOf("1.0G")})`);
check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
