// In a live JupyterLab: linking plots that read a DuckDB table a page at a time
// (load="pages"). A selection of batches in a scatter lights up the rows of those batches in
// the pages read, and fills each panel's histogram (counted by the database) to their share;
// a page turned to is lit up too. A brush in a page plot selects for the others, and a brush
// with link= selects the rows of the brushed rows' batches in every panel. The notebook's
// cells:
//
//   import duckdb
//   import numpy as np
//   import polars as pl
//   import anytrellis as at
//   from anytrellis import Trellis
//   from anytrellis.synthetic import sensors
//   d = sensors(stations=300, sensors=1, hours=24 * 7)
//   t = pl.DataFrame({k: np.asarray(d[k]) for k in ("station", "time", "temp")})
//   t = t.with_columns(batch=(pl.int_range(pl.len()) * 7919 % 211).cast(pl.String))
//   rel = duckdb.from_arrow(t.to_arrow())
//   by = t.group_by("batch").agg(pl.col("temp").mean().alias("mean"), pl.len().alias("n")).sort("batch")
//   q = Trellis(by, title="batches").points(x="mean", y="n")
//   p = Trellis(rel, wrap="station", title="readings", load="pages").points(x="time", y="temp", size=2)
//   h = Trellis(rel, wrap="station", title="histograms", load="pages").hist(x="temp", bins=20)
//   k = Trellis(rel, wrap="station", title="by batch", load="pages", link="batch").points(x="time", y="temp", size=2)
//   group = at.link(q, p, h, on="batch")
//   display(q, p, h, k)
//   ---
//   (an empty cell, where the test runs Python)
//
//   node test/live-page-link.mjs <notebook url> [screenshot prefix] [chromium]
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
const settle = () => page.waitForTimeout(1500);

await page.goto(url);
await page.waitForSelector(".jp-Notebook", { timeout: 60000 });
await page.waitForTimeout(2000);
await page.click("text=Run", { timeout: 10000 });
await page.click("text=Run All Cells");
await page.waitForFunction(() => (window.anytrellisViews ?? []).filter((v) => v.scene).length === 4, null, { timeout: 120000 });
await settle();

/** What view ``k`` highlights: per spec layer, its instances (of the panels of the page
 * shown) and how many are lit (a mask) or their mean share (a histogram's fractions). */
const lit = (k) =>
  page.evaluate((k) => {
    const v = window.anytrellisViews[k];
    const shown = v.pagePanels() ?? v.spec.panels.map((_, i) => i); // a plot that doesn't page: all
    return {
      page: v.paging?.page ?? 0,
      layers: v.scene.layers.map((l, i) => {
        const h = v.highlight?.layers?.[i] ?? null;
        const ids = shown.flatMap((p) => Array.from({ length: l.starts[p + 1] - l.starts[p] }, (_, j) => l.starts[p] + j));
        if (!h) return { n: ids.length, lit: null };
        if ("mask" in h) return { n: ids.length, lit: ids.filter((j) => h.mask[j]).length, size: h.mask.length };
        const shares = ids.map((j) => h.fraction[j]);
        return { n: ids.length, lit: shares.filter((x) => x > 0).length, share: shares.reduce((a, b) => a + b, 0) / Math.max(1, shares.length), size: h.fraction.length };
      }),
    };
  }, k);
const turn = (k, to) => page.evaluate(([k, to]) => window.anytrellisViews[k].setPaging({ ...window.anytrellisViews[k].paging, page: to }, true), [k, to]);
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
const roots = await page.$$(".atr-root");

// ---- a selection of batches elsewhere: the rows of the pages read, the histograms' shares ----
await run("q.select(x=(6.8, 7.2))");
await settle();
let s = await lit(1);
const points = s.layers[0];
check(points.lit > 0 && points.lit < points.n, `the readings of the batches chosen light up (${points.lit} of ${points.n})`);
let bars = (await lit(2)).layers[0];
check(bars.lit > 0 && bars.share > 0 && bars.share < 1, `the histograms fill to the batches' share (${bars.lit} of ${bars.n} bars, ${bars.share?.toFixed(3)})`);
const want = await run(
  "import numpy as np; c = q.selected()['batch'].to_list(); w = p._window; r = p._table(p._layers[0]); print(int(np.isin(r.values('batch'), c).sum()) > 0, len(c))",
);
check(want.startsWith("True"), `Python's rows of the pages read hold the batches chosen (${want})`);
await roots[1].scrollIntoViewIfNeeded();
if (prefix) await roots[1].screenshot({ path: `${prefix}-readings-1.png` });
await roots[2].scrollIntoViewIfNeeded();
if (prefix) await roots[2].screenshot({ path: `${prefix}-hist-1.png` });

await turn(1, 9); // a page further away: read, then lit up
await turn(2, 9);
await settle();
s = await lit(1);
check(s.page === 9 && s.layers[0].n > 0 && s.layers[0].lit > 0 && s.layers[0].lit < s.layers[0].n, `page 10's readings, read, light up (${s.layers[0].lit} of ${s.layers[0].n})`);
bars = (await lit(2)).layers[0];
check(bars.n > 0 && bars.share > 0 && bars.share < 1, `and page 10's histograms (${bars.share?.toFixed(3)})`);
await roots[1].scrollIntoViewIfNeeded();
if (prefix) await roots[1].screenshot({ path: `${prefix}-readings-10.png` });

// ---- a brush in a plot reading pages: its batches light up in the scatter -----------------
const out = await run("p.select(y=(10, 30), panel=p.panels()[9 * 24]); print(q._highlight is not None, int(q._highlight[id(q._layers[0])].sum()))");
const [has, n] = out.split(" ");
check(has === "True" && Number(n) > 0 && Number(n) < 211, `a brush in a page plot selects batches in the scatter (${n} of 211)`);
s = await lit(0);
check(s.layers[0].lit === Number(n), `the scatter lights them up (${s.layers[0].lit})`);
check((await lit(1)).layers.every((l) => l.lit === null), "the page plot brushed shows its own brush, not a highlight");

// ---- link=: a brush in one panel selects the rows of its batches in every panel -------------
await run("group.clear()");
await roots[3].scrollIntoViewIfNeeded();
await page.waitForTimeout(300);
const b = await roots[3].boundingBox(); // the first panel: about x 7-21%, y 15-30% of the plot
await page.mouse.click(b.x + b.width * 0.12, b.y + b.height * 0.22);
await page.keyboard.press("s");
await page.waitForTimeout(1800);
await page.mouse.move(b.x + b.width * 0.08, b.y + b.height * 0.17);
await page.mouse.down();
await page.mouse.move(b.x + b.width * 0.17, b.y + b.height * 0.27, { steps: 8 });
await page.mouse.up();
await page.waitForTimeout(1500);
const got = await run("s = k.selection; r = k.selected().pl(); print(s and s.get('panel'), r['station'].n_unique() > 1, r['batch'].n_unique() > 0)");
check(/^station \d+ True True$/.test(got), `Python sees the brush in one panel, its batches' rows in many (${got})`);
if (prefix) await roots[3].screenshot({ path: `${prefix}-link-1.png` });
await turn(3, 4);
await settle();
const kept = await run("print(k.panels().index(k.selection['panel']) in k._window, k.selection['panel'])");
check(kept.startsWith("True"), `the brushed panel is still read while page 5 is shown (${kept})`);
if (prefix) await roots[3].screenshot({ path: `${prefix}-link-5.png` });

check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
