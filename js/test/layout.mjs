// Layout on save_html pages: panels placed by a layout table (a map's shape, empty cells
// kept), panels sized by their range (space=), columns repeated as rows, a paged wrap filled
// down its columns, and each laid out as figure.py lays it out (<name>.boxes.json).
//   node test/layout.mjs <pages dir> [screenshot dir] [renderer]
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
const page = await browser.newPage({ viewport: { width: 1000, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const tag = renderer || "default";
const open = async (name) => {
  await page.goto(`file://${join(dir, `${name}.html`)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  await page.waitForTimeout(200);
};
/** The panels laid out: their spec index, label, row, column and box. */
const shown = () => page.evaluate(() => {
  const v = window.anytrellisViews[0];
  return {
    width: v.lay.width,
    strips: v.lay.strips.map((s) => s.label),
    panels: v.lay.panels.map((b) => {
      const p = v.spec.panels[b.index];
      return { index: b.index, label: p.label, row: p.row, col: p.col, x: b.rect.x, y: b.rect.y, w: b.rect.w, h: b.rect.h };
    }),
  };
});
/** The boxes as figure.py lays them out at the browser's width: each as high and as far
 * down, as wide as the others, in the same order left to right (the gutters and strips hold
 * text, which figure.py measures by its own metrics, a few px off the browser's). */
function sameAsPython(name, lay) {
  const all = JSON.parse(readFileSync(join(dir, `${name}.boxes.json`), "utf8"));
  const want = all[String(Math.round(lay.width))];
  if (!want) return check(false, `${name}: figure.py's boxes at width ${lay.width}`);
  const got = lay.panels.map((b) => [b.index, b.x, b.y, b.w, b.h]);
  const same = got.length === want.length && got.every((g, i) => g[0] === want[i][0]);
  check(same, `${name}: the same panels as figure.py (${got.length}, ${want.length})`);
  if (!same) return;
  const apart = Math.max(...got.map((g, i) => Math.max(Math.abs(g[2] - want[i][2]), Math.abs(g[4] - want[i][4]))));
  check(apart <= 3, `${name}: each as far down and as high as figure.py's (${apart.toFixed(1)} px apart at most)`);
  const share = (rows) => rows.map((r) => r[3] / rows[0][3]);
  const off = Math.max(...share(got).map((v, i) => Math.abs(v - share(want)[i])));
  check(off < 0.02, `${name}: as wide as each other as figure.py's (${(off * 100).toFixed(1)}% apart at most)`);
  const rank = (rows) => rows.map((r) => rows.filter((q) => q[1] < r[1] - 2).length);
  check(JSON.stringify(rank(got)) === JSON.stringify(rank(want)), `${name}: in figure.py's order left to right`);
}
const near = (a, b, tol = 1.5) => Math.abs(a - b) <= tol;

// ---- a layout table: Europe as a map -------------------------------------------------------
await open("geo");
let lay = await shown();
const at = (label) => lay.panels.find((p) => p.label === label);
const [iceland, norway, ireland, uk, georgia, turkey] = ["Iceland", "Norway", "Ireland", "United Kingdom", "Georgia", "Turkey"].map(at);
check(lay.panels.length === 19, `every country a panel (${lay.panels.length})`);
check(iceland.row === 0 && iceland.col === 0 && norway.col === 3 && georgia.col === 6 && turkey.row === 4, "each in its row and column of the table");
const step = uk.x - ireland.x;
check(step > 0 && near(norway.x - iceland.x, 3 * step) && near(iceland.y, norway.y), `empty cells kept: Norway three columns right of Iceland (${(norway.x - iceland.x).toFixed(1)}, a column ${step.toFixed(1)})`);
check(turkey.y > georgia.y && near(turkey.x + step, georgia.x), "Turkey a row below, a column left of Georgia");
sameAsPython("geo", lay);
await page.screenshot({ path: join(out, `layout-geo-${tag}.png`) });

// ---- space="free_x": a category as wide in every panel -------------------------------------
await open("space");
lay = await shown();
const bands = await page.evaluate(() => window.anytrellisViews[0].spec.panels.map((p) => p.x[1] - p.x[0]));
const perBand = lay.panels.map((p, i) => p.w / bands[i]);
check(lay.panels.length === 3 && Math.max(...perBand) - Math.min(...perBand) < 1.5, `each band as wide (${perBand.map((v) => v.toFixed(1))} px)`);
check(lay.panels[0].w < lay.panels[2].w, "a panel of fewer categories narrower");
sameAsPython("space", lay);
await page.screenshot({ path: join(out, `layout-space-${tag}.png`) });

// ---- repeat: a row a column, sized by its range --------------------------------------------
await open("repeat");
lay = await shown();
check(lay.panels.length === 3 && lay.panels.every((p, i) => p.row === i), "a row of panels per column");
check(["High (°C)", "precipitation", "wind"].every((s) => lay.strips.includes(s)), `the strips name the columns by their labels (${lay.strips})`);
const ys = await page.evaluate(() => window.anytrellisViews[0].spec.panels.map((p) => p.y[1] - p.y[0]));
const perUnit = lay.panels.map((p, i) => p.h / ys[i]);
check(Math.max(...perUnit) / Math.min(...perUnit) < 1.05, `space="free_y": a unit as high in every row (${perUnit.map((v) => v.toFixed(2))} px)`);
sameAsPython("repeat", lay);
await page.screenshot({ path: join(out, `layout-repeat-${tag}.png`) });

// ---- a paged wrap filled down its columns --------------------------------------------------
await open("downwards");
lay = await shown();
const order = [...lay.panels].sort((a, b) => a.x - b.x || a.y - b.y).map((p) => p.index);
check(JSON.stringify(order) === JSON.stringify([0, 1, 2, 3, 4, 5]), `the first page down its columns (${order})`);
sameAsPython("downwards", lay);
await page.click(".atr-pager .atr-button[aria-label='Next page']");
await page.waitForTimeout(200);
lay = await shown();
const second = [...lay.panels].sort((a, b) => a.x - b.x || a.y - b.y).map((p) => p.index);
check(JSON.stringify(second) === JSON.stringify([6, 7, 8, 9, 10, 11]), `and the next page (${second})`);
check(near(lay.panels.find((p) => p.index === 7).x, lay.panels.find((p) => p.index === 6).x), "panel 8 below panel 7");

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
