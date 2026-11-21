// Plots linked in a saved page (Link.save_html), with no kernel: a brush saved from Python
// fills the histogram's bars to the shares Python's link sends (link-saved.json); a brush in
// the histogram takes over (the scatter's brush goes, its points light up) and the other
// follows as it moves; Esc clears both; a lasso and a click in the scatter light the bars of
// the cars chosen; a link on= of two plots reading DuckDB lights the countries' marks
// (link-db.json).
//   node test/savedlink.mjs <pages dir> [screenshot dir] [renderer]
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
const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
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
  await page.waitForFunction(() => {
    const hosts = [...document.querySelectorAll(".anytrellis-embed")];
    return hosts.length > 1 && hosts.every((h) => h.dataset.state === "ready");
  });
  await page.waitForTimeout(200);
};
/** Per plot, in page order: its brush, its highlight's lit marks and bars' shares. */
const state = () =>
  page.evaluate(() => {
    const hosts = [...document.querySelectorAll(".anytrellis-embed")];
    return hosts.map((h) => {
      const v = window.anytrellisViews.find((x) => h.contains(x.root));
      const hl = v.highlight;
      const layers = hl ? hl.layers.map((l) => (!l ? null : "mask" in l ? { lit: l.mask.reduce((a, b) => a + b, 0), of: l.mask.length } : { shares: [...l.fraction] })) : null;
      return { brush: v.brush, layers, selected: v.selected };
    });
  });
const viewIndex = (k) => page.evaluate((k) => {
  const h = document.querySelectorAll(".anytrellis-embed")[k];
  return window.anytrellisViews.findIndex((x) => h.contains(x.root));
}, k);
/** Page coordinates of plot k's panel i at fractions (fx, fy) of its box. */
const at = async (k, i, fx, fy) => {
  const vi = await viewIndex(k);
  const b = await page.evaluate(([vi, i]) => {
    const v = window.anytrellisViews[vi];
    const r = v.stage.getBoundingClientRect();
    const w = v.views[i];
    return { x: r.left + w.rect.x, y: r.top + w.rect.y, w: w.rect.w, h: w.rect.h };
  }, [vi, i]);
  return [b.x + b.w * fx, b.y + b.h * fy];
};
const drag = async (from, to, during) => {
  await page.mouse.move(...from);
  await page.mouse.down();
  await page.mouse.move((from[0] + to[0]) / 2, (from[1] + to[1]) / 2, { steps: 4 });
  await page.waitForTimeout(100);
  if (during) await during();
  await page.mouse.move(...to, { steps: 4 });
  await page.mouse.up();
  await page.waitForTimeout(150);
};

// ---- saved with a brush: the other plot shows it, as Python's link would ---------------------
await open("link-saved.html");
const want = JSON.parse(readFileSync(join(dir, "link-saved.json"), "utf8"));
let [scatter, hist] = await state();
check(scatter.brush !== null && scatter.layers === null, "the scatter keeps the brush saved");
const shares = hist.layers?.[0]?.shares;
check(shares && shares.length === want[0].length && shares.every((s, i) => Math.abs(s - want[0][i]) < 1e-6),
  `the bars fill to the shares Python's link sends (${shares?.filter((s) => s > 0).length} of ${want[0].length} bars)`);
await page.screenshot({ path: join(out, `savedlink-${tag}.png`) });

// ---- a brush in the histogram takes over ----------------------------------------------------
await page.mouse.click(...(await at(1, 0, 0.95, 0.05)));
await page.keyboard.press("s");
let mid = null;
await drag(await at(1, 0, 0.02, 0.02), await at(1, 0, 0.4, 0.98), async () => {
  mid = (await state())[0];
});
check(mid?.brush === null && mid?.layers?.[0]?.lit > 0, `mid-drag: the scatter's brush gone, its points lit (${mid?.layers?.[0]?.lit})`);
[scatter, hist] = await state();
check(hist.brush !== null && hist.layers === null, "the histogram has the brush, and no highlight");
check(scatter.layers?.[0]?.lit > 0 && scatter.layers[0].lit < scatter.layers[0].of && scatter.selected?.selected === scatter.layers[0].lit,
  `the scatter lights the cars of the bars brushed (${scatter.layers?.[0]?.lit} of ${scatter.layers?.[0]?.of}), counted in its chip`);
const litBefore = scatter.layers[0].lit;
await page.keyboard.press("Escape"); // (a drag from inside the brush would move it)
await drag(await at(1, 0, 0.02, 0.02), await at(1, 0, 0.8, 0.98));
check((await state())[0].layers[0].lit > litBefore, "a wider brush lights more");
await page.keyboard.press("Escape");
await page.waitForTimeout(150);
[scatter, hist] = await state();
check(scatter.brush === null && hist.brush === null && scatter.layers === null && hist.layers === null, "Esc clears both");

// ---- a lasso and a click in the scatter ------------------------------------------------------
await page.mouse.click(...(await at(0, 0, 0.98, 0.02)));
await page.keyboard.press("l");
const ring = [];
for (let k = 0; k <= 30; k++) {
  const t = (k / 30) * Math.PI * 2;
  ring.push(await at(0, 0, 0.3 + 0.2 * Math.cos(t), 0.4 + 0.3 * Math.sin(t)));
}
await page.mouse.move(...ring[0]);
await page.mouse.down();
for (const p of ring.slice(1)) await page.mouse.move(...p);
await page.mouse.up();
await page.waitForTimeout(150);
[scatter, hist] = await state();
check(scatter.brush?.lasso && hist.layers?.[0]?.shares.some((s) => s > 0), "a lasso in the scatter fills the bars");
const point = await page.evaluate((vi) => {
  const v = window.anytrellisViews[vi];
  const w = v.views[0];
  const l = v.scene.layers[0];
  const r = v.stage.getBoundingClientRect();
  const px = (i) => [w.map.ox + l.coords[i * 4] * w.map.sx, w.map.oy + l.coords[i * 4 + 1] * w.map.sy];
  for (let i = 0; i < l.set.count; i++) {
    const [x, y] = px(i);
    let alone = true;
    for (let j = 0; j < l.set.count && alone; j++) if (j !== i && Math.hypot(px(j)[0] - x, px(j)[1] - y) < 12) alone = false;
    if (alone) return [r.left + x, r.top + y];
  }
  return null;
}, await viewIndex(0));
await page.mouse.click(...point);
await page.waitForTimeout(150);
[scatter, hist] = await state();
const filledBars = hist.layers?.[0]?.shares.filter((s) => s > 0).length;
check(scatter.selected?.selected === 1 && filledBars === 1, `a click on one car fills its bar alone (${filledBars})`);
await page.keyboard.press("Escape");

// ---- on= of two plots reading DuckDB ---------------------------------------------------------
await open("link-db.html");
const db = JSON.parse(readFileSync(join(dir, "link-db.json"), "utf8"));
const [years, growth] = await state();
const lit = growth.layers?.reduce((a, l) => a + (l?.lit ?? 0), 0);
check(years.brush !== null && lit > 0, `a link on country from DuckDB: lit in the other plot (${lit} marks)`);
// a line's pieces: each lit if either end's row is chosen, so a country of n rows lights n - 1
check(lit === db.rows - db.countries, `as many as Python's rows of the countries chosen give (${db.rows} rows of ${db.countries} countries)`);

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
