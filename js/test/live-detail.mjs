// In a live JupyterLab: level of detail. A long line comes thinned and, zoomed in, in
// detail (two columns a pixel), then as it started again on reset; dense points come as
// cells, which tell their points, then as finer cells and as points again zoomed in; a
// brush over cells selects the rows under it in Python. The notebook's cells:
//
//   import numpy as np, polars as pl
//   from anytrellis import Trellis
//   rng = np.random.default_rng(7)
//   n = 1_000_000
//   walk = pl.DataFrame({"t": np.tile(np.arange(n, dtype=float), 4),
//                        "v": np.cumsum(rng.normal(size=4 * n)),
//                        "s": np.repeat(["a", "b", "c", "d"], n)})
//   p = Trellis(walk, wrap="s", title="walks").line(x="t", y="v", width=1)
//   p
//   ---
//   pts = pl.DataFrame({"x": rng.normal(size=n), "y": rng.normal(size=n),
//                       "c": rng.choice(["u", "v", "w"], n, p=[0.6, 0.3, 0.1])})
//   q = Trellis(pts, title="cloud").points(x="x", y="y", color="c", size=3)
//   q
//   ---
//   (an empty cell, where the test runs Python)
//
//   node test/live-detail.mjs <notebook url> [screenshot prefix] [chromium]
import { chromium } from "@playwright/test";

const [, , url, prefix, exe] = process.argv;
const browser = await chromium.launch({ executablePath: exe, args: ["--enable-unsafe-webgpu", ...(process.platform === "darwin" ? ["--use-angle=metal"] : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])] });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "warning" && m.text().includes("anytrellis") && errors.push(m.text()));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const shot = (name) => (prefix ? page.screenshot({ path: `${prefix}-${name}.png` }) : null);
const settle = () => page.waitForTimeout(2500); // the view reported, the detail sent and drawn

await page.goto(url);
await page.waitForSelector(".jp-Notebook", { timeout: 60000 });
await page.waitForTimeout(2000);
await page.click("text=Run", { timeout: 10000 });
await page.click("text=Run All Cells");
await page.waitForFunction(() => (window.anytrellisViews ?? []).filter((v) => v.scene).length === 2, null, { timeout: 120000 });
await settle();
const layers = (i) => page.evaluate((i) => window.anytrellisViews[i].scene.layers.map((l) => ({ type: l.spec.type, count: l.set.count })), i);
const inDetail = (i) => page.evaluate((i) => window.anytrellisViews[i].detail.size, i);
const counts = (ls) => ls.map((l) => `${l.type} ${l.count}`).join(", ");
const roots = await page.$$(".atr-root");

async function boxZoom(root, view, x0, y0, x1, y1) {
  const box = await (await root.$(".atr-stage")).boundingBox();
  const r = await page.evaluate((i) => window.anytrellisViews[i].views[0].rect, view);
  const at = (fx, fy) => [box.x + r.x + r.w * fx, box.y + r.y + r.h * fy];
  await page.keyboard.down("Shift");
  await page.mouse.move(...at(x0, y0));
  await page.mouse.down();
  await page.mouse.move(...at(x1, y1), { steps: 5 });
  await page.mouse.up();
  await page.keyboard.up("Shift");
  await settle();
}

// a line of 4 million points
let L = await layers(0);
check(L[0].count < 40000, `the 4M-point line arrives thinned (${L[0].count} segments)`);
await roots[0].scrollIntoViewIfNeeded();
await shot("line");
await boxZoom(roots[0], 0, 0.4, 0.5, 0.46, 0.505);
L = await layers(0);
const inView = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const l = v.scene.layers[0];
  const [a, b] = v.views[0].x;
  let n = 0;
  for (let i = l.starts[0]; i < l.starts[1]; i++) if (l.coords[i * 4] >= a && l.coords[i * 4] <= b) n++;
  return { n, px: v.views[0].rect.w };
});
check((await inDetail(0)) === 1 && inView.n > 3 * inView.px, `zoomed in, the line comes in detail (${inView.n} segments over ${Math.round(inView.px)} px)`);
await shot("line-zoomed");
await page.keyboard.press("r");
await settle();
L = await layers(0);
check(L[0].count < 40000, `reset: as it started (${L[0].count})`);

// a million points
let Q = await layers(1);
check(Q[0].count === 0 && Q[1].type === "rect" && Q[1].count > 0, `the 1M points arrive as cells (${counts(Q)})`);
await roots[1].scrollIntoViewIfNeeded();
await page.waitForTimeout(500);
const box = await (await roots[1].$(".atr-stage")).boundingBox();
const r1 = await page.evaluate(() => window.anytrellisViews[1].views[0].rect);
const cx = box.x + r1.x + r1.w / 2;
const cy = box.y + r1.y + r1.h / 2;
await page.mouse.move(cx - 3, cy - 3);
await page.mouse.move(cx, cy);
await page.waitForTimeout(800);
const tip = await page.$$eval(".atr-tip tr", (rows) => Object.fromEntries(rows.map((r) => [...r.children].map((c) => c.textContent.trim()))));
const levels = ["c u", "c v", "c w"].reduce((s, k) => s + Number(tip[k] ?? 0), 0);
check(Number(tip.points) > 0 && levels === Number(tip.points), `a cell tells its points, of each colour (${JSON.stringify(tip)})`);
await shot("points");
// a square box a few pixels across: points again
const fx = 12 / r1.w;
const fy = 12 / r1.h;
await boxZoom(roots[1], 1, 0.5, 0.5, 0.5 + fx, 0.5 + fy);
Q = await layers(1);
check(Q[0].count > 0 && Q[1].count === 0, `zoomed in a lot, points again (${counts(Q)})`);
await shot("points-zoomed");
await page.keyboard.press("r");
await page.waitForTimeout(300);
await boxZoom(roots[1], 1, 0.5 - 60 / r1.w, 0.5 - 60 / r1.h, 0.5 + 60 / r1.w, 0.5 + 60 / r1.h);
Q = await layers(1);
check(Q[0].count === 0 && Q[1].count > 0 && (await inDetail(1)) === 2, `zoomed in a little, finer cells (${counts(Q)})`);

// a brush over the cells; Python selects the rows under it
await page.keyboard.press("s");
await page.mouse.move(cx - 40, cy - 40);
await page.mouse.down();
await page.mouse.move(cx + 40, cy + 40, { steps: 5 });
await page.mouse.up();
await page.waitForTimeout(1000);
const sel = await page.evaluate(() => window.anytrellisViews[1].selected);
check(sel && sel.selected > 0 && sel.selected < sel.total, `a brush selects cells (${sel?.selected} of ${sel?.total})`);
async function run(code) {
  const cells = await page.$$(".jp-Cell .cm-content");
  await cells[cells.length - 1].click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(code);
  await page.keyboard.press("Shift+Enter");
  await page.waitForTimeout(3000);
  const outs = await page.$$eval(".jp-OutputArea-output", (o) => o.map((e) => e.textContent.trim()));
  return outs[outs.length - 1];
}
const rows = await run("print(len(q.selected()['x']))");
check(Number(rows) > 100, `Python selects the rows under it (${rows})`);
const shown = await run("print([lr['count'] for lr in q._shown_layers])");
check(shown === `[0, ${Q[1].count}]`, `Python knows what the browser draws (${shown})`);
await shot("points-brushed");
check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
