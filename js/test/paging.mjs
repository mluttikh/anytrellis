// A paged wrap (150 panels) in a save_html page: the pager turns pages (buttons, Page Down),
// sorts by a statistic (the strips show its value), filters by name and by a statistic's
// range, and an opened panel steps through the panels as sorted, back to its page after;
// with a renderer (?renderer=) each backend.
//   node test/paging.mjs <page.html> [dir for screenshots] [renderer]
import { existsSync, readdirSync } from "node:fs";
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
const settle = () => page.waitForTimeout(150);
// what the plot shows: the panels drawn (spec indices), their strips, the pager's texts
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const text = (s) => document.querySelector(s)?.textContent ?? "";
    return {
      shown: v.lay.panels.map((b) => b.index),
      notes: v.lay.panels.map((b) => b.note),
      height: v.lay.height,
      where: text(".atr-page"),
      count: text(".atr-count"),
      pager: !document.querySelector(".atr-pager").hidden,
      focused: v.focused,
      paging: v.paging,
    };
  });
const stats = await page.evaluate(() => window.anytrellisViews[0].spec.pages.stats);
const stat = (name) => stats.find((s) => s.name === name);
const range = (a, b) => Array.from({ length: b - a }, (_, i) => a + i);

let s = await state();
check(s.pager && s.where === "Page 1 of 7" && s.count === "150 panels", `the pager shows the first of 7 pages (${s.where}, ${s.count})`);
check(JSON.stringify(s.shown) === JSON.stringify(range(0, 24)), "the first page draws the first 24 panels");
const fullHeight = s.height;

await page.click(".atr-pager .atr-button[aria-label='Next page']");
await settle();
s = await state();
check(s.where === "Page 2 of 7" && s.shown[0] === 24, `the next page button turns the page (${s.where}, from ${s.shown[0]})`);
await page.focus(".atr-root");
await page.keyboard.press("PageDown");
await settle();
s = await state();
check(s.where === "Page 3 of 7" && s.shown[0] === 48, `Page Down turns it too (${s.where})`);
for (let i = 0; i < 6; i++) await page.keyboard.press("PageDown");
await settle();
s = await state();
check(s.where === "Page 7 of 7" && s.shown.length === 6, `the last page has the last 6 panels (${s.shown.length})`);
check(s.height === fullHeight, `and the height of a full page (${s.height} px)`);

// sort by the trend, descending: the strips show it
await page.selectOption(".atr-pager .atr-select", "trend temp");
await page.click(".atr-pager .atr-button[aria-label='Ascending']");
await settle();
s = await state();
const trend = stat("trend temp");
const byTrend = range(0, 150).sort((a, b) => trend.values[b] - trend.values[a]);
check(s.where === "Page 1 of 7", "sorting turns back to the first page");
check(JSON.stringify(s.shown) === JSON.stringify(byTrend.slice(0, 24)), "sorted by trend, steepest rise first");
check(s.notes[0] === trend.text[byTrend[0]], `the strips show the trend (${s.notes[0]})`);
await page.screenshot({ path: join(out, `paging-${tag}-sorted.png`) });

// filter by name: every word
await page.fill(".atr-pager .atr-search", "station 1");
await settle();
s = await state();
const names = await page.evaluate(() => window.anytrellisViews[0].spec.panels.map((p) => p.label));
const withOne = names.filter((n) => n.includes("1")).length;
check(s.count === `${withOne} of 150 panels`, `filtering by name keeps those with every word (${s.count})`);
await page.fill(".atr-pager .atr-search", "");

// filter by a statistic's range
await page.click(".atr-pager .atr-button[aria-label='Filter by statistics']");
const means = stat("mean temp").values;
const cut = [...means].sort((a, b) => a - b)[120];
const low = page.locator(".atr-filters input[aria-label='mean temp: at least']");
await low.fill(String(cut));
await settle();
s = await state();
const kept = means.filter((m) => m >= cut).length;
check(s.count === `${kept} of 150 panels` && s.where === "Page 1 of 2", `a statistic's range filters too (${s.count}, ${s.where})`);
check(s.shown.every((i) => means[i] >= cut), "every panel shown is in the range");
await page.screenshot({ path: join(out, `paging-${tag}-filtered.png`) });
await page.keyboard.press("Escape");
await settle();
check(await page.$eval(".atr-filters", (e) => e.hidden), "Escape closes the filters");
check((await page.$eval(".atr-pager .atr-button[aria-label='Filter by statistics']", (e) => e.dataset.count)) === "1", "the filter button counts the filters set");

// open a panel: it steps through the panels as sorted and filtered, back on its page
s = await state();
const order = s.shown;
await page.focus(".atr-root");
await page.keyboard.press("PageDown"); // to page 2 of 2
await settle();
s = await state();
const second = s.shown;
const box = await (await page.$(".atr-stage")).boundingBox();
const r = await page.evaluate(() => window.anytrellisViews[0].lay.panels[0].rect);
await page.mouse.dblclick(box.x + r.x + r.w / 2, box.y + r.y + r.h / 2);
await settle();
s = await state();
check(s.focused === second[0] && !s.pager, `a double-click opens the panel and hides the pager (${s.focused})`);
await page.keyboard.press("PageUp");
await settle();
s = await state();
check(s.focused === order[order.length - 1], `Page Up opens the panel before it, as sorted (${s.focused})`);
await page.keyboard.press("Backspace");
await settle();
s = await state();
check(s.focused === null && s.pager && s.where === "Page 1 of 2", `back to all panels: the page that has it (${s.where})`);

check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
await browser.close();
if (failures.length) {
  console.error(`${failures.length} failed`);
  process.exit(1);
}
