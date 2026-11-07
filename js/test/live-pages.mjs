// In a live JupyterLab: a paged plot sends the panels around the page shown, not all of
// them. It starts with the first two pages' data; the next page draws at once (its data is
// here) and the one after it comes; a page further away says it is loading until its data
// comes; Python's show_page and open bring their panels' data too, and a saved page has
// every panel's. The notebook's cells:
//
//   import numpy as np
//   from anytrellis import Trellis
//   from anytrellis.synthetic import sensors
//   d = sensors(stations=300, sensors=1, hours=24 * 7)
//   st = np.asarray(d["station"])
//   first = np.unique(st, return_index=True)[1]
//   tags = {k: np.asarray(d[k])[first] for k in ("station", "time", "temp")}
//   p = (Trellis(d, wrap="station", title="stations")
//        .line(x="time", y="temp", width=1)
//        .text(tags, x="time", y="temp", text="station", size=10))
//   p
//   ---
//   (an empty cell, where the test runs Python)
//
//   node test/live-pages.mjs <notebook url> [screenshot prefix] [chromium]
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
const settle = () => page.waitForTimeout(1500); // the paging reported, the panels' data sent and drawn

await page.goto(url);
await page.waitForSelector(".jp-Notebook", { timeout: 60000 });
await page.waitForTimeout(2000);
await page.click("text=Run", { timeout: 10000 });
await page.click("text=Run All Cells");
await page.waitForFunction(() => (window.anytrellisViews ?? []).some((v) => v.scene), null, { timeout: 120000 });
await settle();

/** What the view draws: the page's panels, and per layer the panels it has data of and the
 * instances each page panel holds. */
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const shown = v.focused !== null ? [v.focused] : v.pagePanels();
    return {
      page: v.paging.page ?? 0,
      shown,
      loading: !v.notice.hidden && v.notice.textContent.startsWith("Loading"),
      layers: v.scene.layers.map((l) => ({ type: l.spec.type, has: l.spec.panels?.length ?? null, counts: shown.map((p) => l.starts[p + 1] - l.starts[p]) })),
      texts: v.scene.texts.map((t) => ({ has: t.spec.panels?.length ?? null, counts: shown.map((p) => t.starts[p + 1] - t.starts[p]) })),
      total: v.spec.panels.length,
    };
  });
const drawn = (s) => s.layers[0].counts.every((n) => n > 0) && s.texts[0].counts.every((n) => n === 1);
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

let s = await state();
check(s.total === 300 && s.layers[0].has === 48 && s.texts[0].has === 48, `it starts with the first two pages' data (${s.layers[0].has} of ${s.total} panels; labels ${s.texts[0].has})`);
check(drawn(s) && !s.loading, "the first page is drawn");
await (await page.$(".atr-root")).scrollIntoViewIfNeeded();
await shot("page-1");

// the next page: its data is here already
await page.evaluate(() => window.anytrellisViews[0].setPaging({ ...window.anytrellisViews[0].paging, page: 1 }, true));
s = await state();
check(s.page === 1 && drawn(s) && !s.loading, "the next page draws at once");
await settle();
s = await state();
check(s.layers[0].has === 72 && s.texts[0].has === 72, `then the pages either side of it come (${s.layers[0].has} panels)`);

// a page further away: loading, then drawn
await page.evaluate(() => window.anytrellisViews[0].setPaging({ ...window.anytrellisViews[0].paging, page: 9 }, true));
s = await state();
check(s.page === 9 && s.loading && !drawn(s), "a page further away says it is loading");
await settle();
s = await state();
check(drawn(s) && !s.loading, `then its panels are drawn (page ${s.page + 1}, ${s.layers[0].counts[0]} segments in its first panel)`);
await shot("page-10");

// Python turns the page
await run("p.show_page(4)");
s = await state();
check(s.page === 3 && drawn(s) && !s.loading, "show_page in Python: the page and its panels' data");

// Python opens a panel of another page
const name = await run("print(p.panels()[250])");
await run(`p.open("${name}")`);
s = await state();
check(s.shown.length === 1 && s.shown[0] === 250 && drawn(s), `open in Python: a panel of another page, with its data (${name})`);
await run("p.close()");

// hovering a line on the page shown asks Python for its row: as sent
const tip = await run("print(p._tooltip(0, 0, p._shown_ids()[0]) == p._tooltip(0, 0))");
check(tip === "True", "Python answers tooltips for the data sent");

// a saved page has every panel's data
const full = await run("f, _ = p._full_scene(); print([lr['count'] for lr in f['layers']], [e[2].count for e in p._full], ['panels' in lr for lr in f['layers']])");
const [counts, all, marked] = full.split("] [").map((t) => t.replace(/[[\]]/g, ""));
check(counts === all && !marked.includes("True"), `a saved page has every panel's data (${counts})`);

check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
