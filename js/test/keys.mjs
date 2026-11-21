// The arrow keys among marks and the table view on save_html pages. In a panel opened (or a
// plot of one panel), ← → step through its marks along x, ↑ ↓ to the mark above or below,
// Home and End to the ends: each shows its tooltip and is said in the live region ("k of
// n", n as many as Python draws, keys.json), the view following a mark off it; Esc lets go.
// t shows the table view: the panels' statistics and the rows as Python gives them, a
// panel's name opening it; a plot of many rows says why it lists none.
//   node test/keys.mjs <pages dir> [screenshot dir] [renderer]
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
const want = JSON.parse(readFileSync(join(dir, "keys.json"), "utf8"));
const open = async (name) => {
  await page.goto(`file://${join(dir, name)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  await page.waitForTimeout(200);
  await page.click(".atr-stage", { position: { x: 5, y: 5 } }); // the keys to the plot
};
const press = async (...keys) => {
  for (const k of keys) await page.keyboard.press(k);
  await page.waitForTimeout(400); // the live region: once the keys rest
  // a slow machine: until the panels are in place and a mark held is said
  await page
    .waitForFunction(() => {
      const v = window.anytrellisViews[0];
      return !v.motion && (!v.markAt || document.querySelector(".atr-sr").textContent !== "");
    }, null, { timeout: 3000 })
    .catch(() => {});
};
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const w = v.views[0];
    return {
      said: document.querySelector(".atr-sr").textContent,
      tip: getComputedStyle(document.querySelector(".atr-tip")).display !== "none",
      hovers: v.front_.hovers.length,
      at: v.markAt && { x: v.markAt.stop.x, y: v.markAt.stop.y },
      focused: v.focused,
      name: v.focused === null ? null : v.spec.panels[v.focused].keys.join(" · "),
      view: w && w.x,
    };
  });

// ---- among marks --------------------------------------------------------------------------
await open("keys.html");
await press("ArrowRight", "Enter");
let s = await state();
check(s.focused !== null, `→ then Enter: a panel opened (${s.name})`);
const n = want.points[s.name];
await press("ArrowRight");
s = await state();
check(s.said.endsWith(`1 of ${n}.`) && s.said.startsWith(s.name), `→: the first mark, said with its panel (${s.said})`);
check(s.tip && s.hovers === 1, "its tooltip shows, and the ring on it");
const first = s.at;
await press("ArrowRight");
s = await state();
check(s.said.endsWith(`2 of ${n}.`) && s.at.x >= first.x, "→ again: the next along x");
await press("End");
s = await state();
check(s.said.endsWith(`${n} of ${n}.`), `End: the last (${n}, as many as Python draws)`);
await press("ArrowRight");
s = await state();
check(s.said === "The last mark", `→ past it: says so (${s.said})`);
await press("Home");
s = await state();
check(s.said.endsWith(`1 of ${n}.`), "Home: the first");
// zoomed in on the first marks: End takes the view to the last
const before = s.view;
await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const p = v.spec.panels[v.focused];
  const [a, b] = p.x;
  v.setX(p.xg, [a, a + (b - a) / 10]);
});
await press("End");
s = await state();
check(s.at.x >= s.view[0] && s.at.x <= s.view[1] && s.view[1] - s.view[0] < (before[1] - before[0]) / 2, "zoomed in, End: the view goes to the last mark, still zoomed");
await press("Escape");
s = await state();
check(s.at === null && !s.tip && s.focused !== null, "Esc: lets go of the mark, the panel still open");
await press("Escape");
check((await state()).focused === null, "Esc again: back to all panels");

// one panel, two lines: ↑ ↓ between them at the same x
await open("keys-line.html");
await press("ArrowRight", "ArrowRight", "ArrowRight");
s = await state();
const low = s.at; // a's second point (by x, then y)
await press("ArrowUp");
s = await state();
check(s.at && s.at.x === low.x && s.at.y > low.y, `one panel: the arrows step at once; ↑ the line above at the same x (${JSON.stringify(low)} → ${JSON.stringify(s.at)})`);
await press("ArrowDown");
check(JSON.stringify((await state()).at) === JSON.stringify(low), "↓ back down");
await press("ArrowUp", "ArrowUp", "ArrowUp");
s = await state();
check(s.said === "No mark above", `↑ from the top: says so (${s.said}; at ${JSON.stringify(s.at)})`);
await press("End");
s = await state();
check(s.said.endsWith("6 of 6."), `each line's points, its last too (${s.said})`);
await page.screenshot({ path: join(out, `keys-${tag}.png`) });

// ---- the table view --------------------------------------------------------------------------
await open("keys.html");
await press("t");
const table = await page.evaluate(() => {
  const view = document.querySelector(".atr-table-view");
  const tables = [...view.querySelectorAll("table")];
  const cells = (t) => [...t.querySelectorAll("tbody tr")].map((tr) => [...tr.children].map((c) => c.textContent));
  return {
    shown: !view.hidden,
    focus: view.contains(document.activeElement),
    captions: tables.map((t) => t.querySelector("caption").textContent),
    heads: tables.map((t) => [...t.querySelectorAll("thead th")].map((th) => [th.textContent, th.getAttribute("scope")])),
    panels: cells(tables[0]),
    rows: tables[1] ? cells(tables[1]) : null,
  };
});
check(table.shown && table.focus, "t: the table view, the focus in it");
check(JSON.stringify(table.panels) === JSON.stringify(want.table.panels.rows), `each panel's statistics as Python gives them (${table.panels.length} panels)`);
check(table.heads[0].every(([, scope]) => scope === "col") && table.heads[0][0][0] === "panel", "a header row (scope col)");
check(table.rows?.length === want.table.rows.rows.length && JSON.stringify(table.rows[10]) === JSON.stringify(want.table.rows.rows[10]), `and the rows (${table.rows?.length}; a missing value blank)`);
await page.screenshot({ path: join(out, `keys-table-${tag}.png`) });
await page.click(`.atr-table-view th button:text-is("${want.table.panels.rows[1][0]}")`);
await page.waitForTimeout(150);
s = await state();
check(s.name === want.table.panels.rows[1][0] && (await page.$eval(".atr-table-view", (v) => v.hidden)), `a panel's name opens it (${s.name})`);
await press("t");
await press("Escape");
check(await page.$eval(".atr-table-view", (v) => v.hidden), "Esc closes the table");

await open("paged.html");
await press("t");
const paged = await page.evaluate(() => {
  const view = document.querySelector(".atr-table-view");
  return { panels: view.querySelectorAll("tbody")[0]?.children.length, tables: view.querySelectorAll("table").length, note: view.querySelector(".atr-help-about")?.textContent ?? "" };
});
check(paged.panels === 150 && paged.tables === 1 && /too many/.test(paged.note), `many rows: the panels (${paged.panels}) and why no rows (${paged.note})`);

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
