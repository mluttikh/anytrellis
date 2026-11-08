// In a live JupyterLab: summaries of a DuckDB table read a page at a time (load="pages").
// The database computes every panel's histogram (and loess fit) at once; the widget gets
// those of the panels around the page shown, and turning the page sends the next ones
// without asking the database again. A plot of lines and their fits reads the lines' rows a
// page at a time and takes the fits from the database. The notebook's cells:
//
//   import duckdb
//   import numpy as np
//   import pyarrow as pa
//   from anytrellis import Trellis
//   from anytrellis.synthetic import sensors
//   d = sensors(stations=300, sensors=1, hours=24 * 7)
//   rel = duckdb.from_arrow(pa.table({k: np.asarray(d[k]) for k in ("station", "time", "temp")}))
//   p = Trellis(rel, wrap="station", title="histograms", load="pages").hist(x="temp", bins=20)
//   q = (Trellis(rel, wrap="station", title="fits", load="pages")
//        .line(x="time", y="temp", width=1).smooth(x="time", y="temp"))
//   display(p, q)
//   ---
//   (an empty cell, where the test runs Python)
//
//   node test/live-page-summaries.mjs <notebook url> [screenshot prefix] [chromium]
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
const settle = () => page.waitForTimeout(1500); // the paging reported, the panels' data sent and drawn

await page.goto(url);
await page.waitForSelector(".jp-Notebook", { timeout: 60000 });
await page.waitForTimeout(2000);
await page.click("text=Run", { timeout: 10000 });
await page.click("text=Run All Cells");
await page.waitForFunction(() => (window.anytrellisViews ?? []).filter((v) => v.scene).length === 2, null, { timeout: 120000 });
await settle();

/** What view ``k`` draws: the page's panels, and per layer the panels it has data of, the
 * instances each page panel holds, and the panels' y ranges. */
const state = (k) =>
  page.evaluate((k) => {
    const v = window.anytrellisViews[k];
    const shown = v.pagePanels();
    return {
      page: v.paging.page ?? 0,
      loading: !v.notice.hidden && v.notice.textContent.startsWith("Loading"),
      layers: v.scene.layers.map((l) => ({ type: l.spec.type, has: l.spec.panels?.length ?? null, counts: shown.map((p) => l.starts[p + 1] - l.starts[p]) })),
      y: shown.map((p) => v.spec.panels[p].y.join(",")),
      total: v.spec.panels.length,
    };
  }, k);
const drawn = (s, layers) => layers.every((i) => s.layers[i].counts.every((n) => n > 0));
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

// ---- histograms: every panel's from the database, the widget's a few pages' -----------------
let s = await state(0);
check(s.total === 300 && s.layers[0].type === "bars" && s.layers[0].has === 48, `the histograms of the first two pages' panels (${s.layers[0].has} of ${s.total})`);
check(drawn(s, [0]) && !s.loading, "the first page is drawn");
const yFirst = s.y[0];
check(s.y.every((y) => y === yFirst), "the panels share their y range");
const plots = await page.$$(".atr-root");
await plots[0].scrollIntoViewIfNeeded();
if (prefix) await plots[0].screenshot({ path: `${prefix}-hist-1.png` });

await turn(0, 9);
s = await state(0);
check(s.page === 9 && s.loading, "a page further away says it is loading");
await settle();
s = await state(0);
check(drawn(s, [0]) && !s.loading, "then its histograms are drawn");
check(s.y[0] === yFirst, `with the same y range: every panel's counts, from the start (${s.y[0]})`);
if (prefix) await plots[0].screenshot({ path: `${prefix}-hist-10.png` });

const asked = await run("print(p._read is None, p._page_tables == {}, len(p._queried))");
check(asked === "True True 1", `Python read no rows: the database's summaries, once (${asked})`);
const tip = await run("print(p._tooltip(0, 0, p._shown_ids()[0]) == p._tooltip(0, 0), p._tooltip(0, 0)[0][0])");
check(tip === "True bin", `a bar's tooltip, for the data sent (${tip})`);
const chosen = await run(
  "import narwhals as nw; p.select(x=(10, 14)); r = p.selected(); a = Trellis(rel, wrap='station').hist(x='temp', bins=20).select(x=(10, 14)).selected(); print(type(r).__name__, len(r.fetchall()) == len(nw.from_native(a)))",
);
check(chosen === "DuckDBPyRelation True", `a brush over bars selects their rows, as a query (${chosen})`);
await run("p.select()");

// ---- lines and their fits: the lines' rows a page at a time, the fits every panel's -----------
s = await state(1);
const [lines, band, fit] = s.layers;
check(lines.type === "line" && lines.has === 48 && band.has === 48 && fit.has === 48, `lines and fits of the first two pages' panels (${lines.has}, ${band.has}, ${fit.has})`);
check(drawn(s, [0, 1, 2]), "the first page's lines, bands and fits are drawn");
await plots[1].scrollIntoViewIfNeeded();
await turn(1, 6);
await settle();
s = await state(1);
check(s.page === 6 && drawn(s, [0, 1, 2]) && !s.loading, "another page: its lines and fits");
if (prefix) await plots[1].screenshot({ path: `${prefix}-fits-7.png` });
const read = await run("print(sorted(q._read.names), q._table(q._layers[0]).n < len(d['station']) / 3)");
check(read === "['station', 'temp', 'time'] True", `Python read the lines' rows of a few pages (${read})`);

check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
