// Pages of a page column (page=) in save_html pages: a wrap of each region's stations
// (regions.html: 2 × 4 a page, a region of more on several pages) and a grid per site
// (sites.html: sensor by metric, each site's y scale its own). The pager names the pages by
// their level and picks one from a list; turning, sorting and opening keep a level's panels
// together; a grid's page keeps each cell in its place, unsorted.
//   node test/levels.mjs <dir with regions.html and sites.html> [dir for screenshots] [renderer]
import { existsSync, readdirSync } from "node:fs";
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
const page = await browser.newPage({ viewport: { width: 1000, height: 800 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const settle = () => page.waitForTimeout(150);
async function open(name) {
  await page.goto(`file://${join(dir, name)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
}
// what the plot shows: the panels drawn (spec indices), their cells and strips, the pager
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const select = document.querySelector(".atr-page-select");
    const shown = (e) => !!e && !e.hidden && !e.closest("[hidden]");
    return {
      shown: v.lay.panels.map((b) => b.index),
      cells: v.lay.panels.map((b) => [v.spec.panels[b.index].row, v.spec.panels[b.index].col, Math.round(b.rect.x), Math.round(b.rect.y)]),
      strips: v.lay.strips.map((s) => s.label),
      labels: v.lay.panels.map((b) => (b.strip ? v.spec.panels[b.index].label : null)),
      picked: select ? select.selectedOptions[0]?.textContent : null,
      options: select ? [...select.options].map((o) => o.textContent) : [],
      named: shown(select),
      number: shown(document.querySelector(".atr-page")),
      sorting: shown(document.querySelector(".atr-pager .atr-select")),
      filtering: shown(document.querySelector(".atr-pager .atr-search")),
      focused: v.focused,
      height: v.lay.height,
      y: v.lay.panels.map((b) => v.spec.panels[b.index].y),
    };
  });

// ---- a wrap of each region's stations -------------------------------------------------------
await open("regions.html");
const spec = await page.evaluate(() => window.anytrellisViews[0].spec);
const { groups, levels } = spec.pages;
const level = (i) => levels[groups[i]];
let s = await state();
check(s.named && !s.number, "the pager names the pages, in a list");
check(s.options.length === 6 && s.options[0] === "coast (1 of 2)" && s.options[5] === "south (2 of 2)", `a region of more stations than a page holds goes on two (${s.options.join(", ")})`);
check(s.shown.length === 8 && s.shown.every((i) => level(i) === "coast"), "the first page: the first region's first 8 stations");
check(s.labels.length === 8 && s.labels.every((t) => t?.startsWith("station")), `the strips name the stations, not the region (${s.labels[0]})`);
const fullHeight = s.height;
await page.screenshot({ path: join(out, `levels-${renderer || "auto"}-first.png`) });

await page.focus(".atr-root");
await page.keyboard.press("PageDown");
await settle();
s = await state();
check(s.picked === "coast (2 of 2)" && s.shown.every((i) => level(i) === "coast") && s.height === fullHeight, `Page Down: the rest of the region, the page as tall (${s.shown.length} panels)`);
await page.keyboard.press("PageDown");
await settle();
s = await state();
check(s.picked === "north (1 of 2)" && s.shown.every((i) => level(i) === "north"), "then the next region, on a page of its own");

await page.selectOption(".atr-page-select", { label: "south (1 of 2)" });
await settle();
s = await state();
check(s.picked === "south (1 of 2)" && s.shown.length === 8 && s.shown.every((i) => level(i) === "south"), "picking a page from the list shows it");

// sorted: each region's stations in turn, as sorted
await page.selectOption(".atr-pager .atr-select", "mean temp");
await settle();
s = await state();
const mean = spec.pages.stats.find((t) => t.name === "mean temp").values;
const coast = spec.panels.map((_, i) => i).filter((i) => level(i) === "coast").sort((a, b) => mean[a] - mean[b]);
check(s.picked === "coast (1 of 2)" && JSON.stringify(s.shown) === JSON.stringify(coast.slice(0, 8)), "sorting sorts each region's stations, the first region first");

// opened, then back: the page of its region
await page.selectOption(".atr-page-select", { label: "north (2 of 2)" });
await settle();
s = await state();
const opened = s.shown[0];
await page.evaluate((i) => window.anytrellisViews[0].setFocus(i, true), opened);
await settle();
await page.evaluate(() => window.anytrellisViews[0].setFocus(null, true));
await settle();
s = await state();
check(s.focused === null && s.picked === "north (2 of 2)", `back from an opened panel: its region's page (${s.picked})`);

// filtered: a region with none kept has no page
await page.fill(".atr-pager .atr-search", "station 1");
await settle();
s = await state();
const kept = spec.panels.map((p, i) => i).filter((i) => spec.panels[i].label.includes("1"));
const regionsKept = new Set(kept.map(level));
check(s.options.length >= regionsKept.size && s.options.every((o) => regionsKept.has(o.split(" (")[0])), `filtering keeps the pages of the regions with panels left (${s.options.join(", ")})`);

// ---- a grid per site ------------------------------------------------------------------------
await open("sites.html");
const grid = await page.evaluate(() => window.anytrellisViews[0].spec);
s = await state();
check(s.named && !s.sorting && !s.filtering, "a grid's pages: picked by site, not sorted or filtered");
check(JSON.stringify(s.options) === JSON.stringify(["A", "B", "C"]), `a page per site (${s.options.join(", ")})`);
check(s.shown.length === 6 && s.shown.every((i) => grid.pages.groups[i] === 0), "the first page: site A's six cells");
// (in the same cells: the y labels' width may move them a pixel or two)
const samePlaces = (a, b) => a.length === b.length && a.every(([r, c, x, y], k) => r === b[k][0] && c === b[k][1] && Math.abs(x - b[k][2]) <= 4 && y === b[k][3]);
const first = s.cells;
check(new Set(first.map(([r]) => r)).size === 2 && new Set(first.map(([, c]) => c)).size === 3, "on two rows of sensors and three columns of metrics");
check(s.strips.includes("temp") && s.strips.includes("a") && s.strips.includes("b"), `with the grid's strips (${s.strips.join(", ")})`);
const yA = s.y[0];
check(s.y.every((y) => y[0] === yA[0] && y[1] === yA[1]), "the cells of a page share their y scale");
await page.screenshot({ path: join(out, `levels-${renderer || "auto"}-grid.png`) });

await page.selectOption(".atr-page-select", { label: "C" });
await settle();
s = await state();
check(s.shown.every((i) => grid.pages.groups[i] === 2) && samePlaces(s.cells, first), "site C: each cell in the same place as site A's");
check(s.y[0][0] > yA[1] - 1, `site C's y scale is its own (${s.y[0].map((v) => v.toFixed(1))} after ${yA.map((v) => v.toFixed(1))})`);
const empty = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  return v.lay.panels.filter((b) => v.spec.panels[b.index].row === 1).map((b) => v.scene.layers[0].starts[b.index + 1] - v.scene.layers[0].starts[b.index]);
});
check(empty.every((n) => n === 0), "site C has no sensor b: its row is there, empty");

check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
await browser.close();
if (failures.length) {
  console.error(`${failures.length} failed`);
  process.exit(1);
}
