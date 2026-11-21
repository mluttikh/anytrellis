// Views and the filters' histograms on a save_html page (views.html, views kept in Python):
// the Views menu lists them and shows each as Python does (views.json: the panels shown, the
// zoom), names the one shown in the bar; the reader keeps one and deletes it; a link ending
// #view=<name> opens on it; a drag across a statistic's histogram filters the panels by
// it, the number boxes following, and a click on it clears.
//   node test/views.mjs <pages dir> [screenshot dir] [renderer]
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
const page = await browser.newPage({ viewport: { width: 1000, height: 760 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const tag = renderer || "default";
const want = JSON.parse(readFileSync(join(dir, "views.json"), "utf8"));
const open = async (hash = "") => {
  await page.goto(`file://${join(dir, "views.html")}${renderer ? `?renderer=${renderer}` : ""}${hash}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  await page.waitForTimeout(200);
};
/** The panels shown (names, in order), the paging, the x zoom of group 0 and the bar's view. */
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    return {
      paging: v.paging,
      x: v.xView.get(0),
      start: v.spec.panels[0].x,
      label: document.querySelector(".atr-views-label")?.textContent,
      kept: Object.keys(v.keptViews),
    };
  });
/** The panels shown (indices, in order), as Python's shown_panels gives them. */
const names = () => page.evaluate(() => window.anytrellisViews[0].views.map((w) => w.panel));
const showView = async (name) => {
  await page.click(".atr-views-button");
  await page.click(`.atr-view-name:text-is("${name}")`);
  await page.waitForTimeout(250);
};

await open();
let s = await state();
check(s.label === "Views" && s.kept.join() === "warm,zoomed,pinned", `the views kept in Python, none shown (${s.kept})`);
for (const name of ["warm", "zoomed", "pinned"]) {
  await showView(name);
  s = await state();
  const shown = await names();
  check(JSON.stringify(shown) === JSON.stringify(want[name].panels), `${name}: the panels Python shows (${shown.slice(0, 3)}...)`);
  check(s.label === name, `the bar names it (${s.label})`);
  const z = want[name].zoom?.x?.[0]?.[1];
  const zoomed = z ? Math.abs(s.x[0] - z[0]) < 1e-6 && Math.abs(s.x[1] - z[1]) < 1e-6 : Math.abs(s.x[0] - s.start[0]) < 1e-6 && Math.abs(s.x[1] - s.start[1]) < 1e-6;
  check(zoomed, `and its zoom (${z ? "the first half" : "as it starts"})`);
  if (z) {
    await page.click(".atr-stage", { position: { x: 5, y: 5 } });
    await page.keyboard.press("r");
    await page.waitForTimeout(150);
    s = await state();
    check(s.label === "Views", `zoomed out again: no longer the view (${s.label})`);
  }
}
await page.screenshot({ path: join(out, `views-${tag}.png`) });

// ---- kept by the reader, and deleted ------------------------------------------------------
await page.click(".atr-views-button");
await page.fill(".atr-view-save input", "mine");
await page.press(".atr-view-save input", "Enter");
await page.waitForTimeout(100);
s = await state();
check(s.kept.includes("mine") && s.label !== "Views", `the reader keeps one ("mine"; the bar: ${s.label})`);
await page.click(".atr-view-drop[aria-label='Delete the view mine']");
s = await state();
check(!s.kept.includes("mine"), "and deletes it");
await page.keyboard.press("Escape");
check(await page.$eval(".atr-views", (m) => m.hidden), "Esc closes the menu");

// ---- #view=<name> ----------------------------------------------------------------------------
await open("#view=warm");
check(JSON.stringify(await names()) === JSON.stringify(want.warm.panels), "a link ending #view=warm opens on it");
await page.evaluate(() => (location.hash = "view=pinned"));
await page.waitForTimeout(250);
check(JSON.stringify(await names()) === JSON.stringify(want.pinned.panels), "and #view= changed: that view");

// ---- the histograms --------------------------------------------------------------------------
await open();
await page.click(".atr-pager [aria-label='Filter by statistics']");
const rows = await page.$$eval(".atr-filter-row", (rs) => rs.map((r) => [r.querySelector(".atr-filter-name").textContent, !!r.querySelector(".atr-hist")]));
check(rows.filter(([, h]) => h).length >= 5, `a histogram for each number statistic with a range (${rows.filter(([, h]) => h).map(([n]) => n)})`);
const hist = await page.$(".atr-filter-row:has(.atr-filter-name:text-is('mean temp')) .atr-hist");
const box = await hist.boundingBox();
await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2);
await page.mouse.down();
await page.mouse.move(box.x + box.width + 20, box.y + box.height / 2, { steps: 5 });
await page.mouse.up();
await page.waitForTimeout(150);
const after = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const stat = v.spec.pages.stats.find((x) => x.name === "mean temp");
  const nums = stat.values.filter((x) => typeof x === "number");
  const [lo, hi] = [Math.min(...nums), Math.max(...nums)];
  const cond = v.paging.where?.["mean temp"];
  const kept = cond ? nums.filter((x) => x >= cond[0]).length : null;
  const inputs = [...document.querySelectorAll(".atr-filter-row")].find((r) => r.querySelector(".atr-filter-name").textContent === "mean temp").querySelectorAll("input");
  return { cond, mid: (lo + hi) / 2, span: hi - lo, kept, count: document.querySelector(".atr-count").textContent, low: inputs[0].value, high: inputs[1].value, band: !!document.querySelector(".atr-hist-range") };
});
check(after.cond && after.cond[1] === null && Math.abs(after.cond[0] - after.mid) < after.span * 0.05, `a drag from the middle to past the end: at least about the middle, open above (${JSON.stringify(after.cond)})`);
check(after.count.startsWith(`${after.kept} of`), `the panels it keeps counted (${after.count})`);
check(after.low === String(after.cond[0]) && after.high === "" && after.band, "the boxes follow, and the range shows as a band");
await page.screenshot({ path: join(out, `views-hist-${tag}.png`) });
await page.mouse.click(box.x + box.width * 0.3, box.y + box.height / 2);
await page.waitForTimeout(100);
check(await page.evaluate(() => !window.anytrellisViews[0].paging.where?.["mean temp"]), "a click on it clears the filter");

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
