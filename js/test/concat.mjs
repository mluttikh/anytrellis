// Different plots in one figure on a save_html page (compose.py): each plot where Python's
// image puts it (concat.json: across the grid, at 824 px), the figure's title over them, a
// narrow plot's toolbar on a line under its title, and a brush in one plot lighting up its
// rows in the plot linked with it; legends collected; plots that share ranges zooming
// together.
//   node test/concat.mjs <pages dir> [screenshot dir] [renderer]
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
// 856 px: the page's 16 px margins leave the figure 824
const page = await browser.newPage({ viewport: { width: 856, height: 1100 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const tag = renderer || "default";
const want = JSON.parse(readFileSync(join(dir, "concat.json"), "utf8"));

await page.goto(`file://${join(dir, "concat.html")}${renderer ? `?renderer=${renderer}` : ""}`);
await page.waitForFunction(() => {
  const hosts = [...document.querySelectorAll(".anytrellis-embed")];
  return hosts.length === 3 && hosts.every((h) => h.dataset.state === "ready");
});
await page.waitForTimeout(300);

const placed = await page.evaluate(() => {
  const fig = document.querySelector(".anytrellis-concat");
  const grid = fig.querySelector(":scope > div:last-child").getBoundingClientRect();
  const title = fig.querySelector(".anytrellis-concat-title");
  return {
    title: title?.textContent,
    titleBottom: title?.getBoundingClientRect().bottom,
    gridTop: grid.top,
    plots: [...fig.querySelectorAll(".anytrellis-embed")].map((h) => {
      const r = h.getBoundingClientRect();
      return { x: r.left - grid.left, w: r.width, y: r.top - grid.top };
    }),
  };
});
check(placed.title === "Cars" && placed.titleBottom <= placed.gridTop + 0.5, "the figure's title, over its plots");
const near = (a, b) => Math.abs(a - b) <= 1;
check(placed.plots.length === want.length && placed.plots.every((p, i) => near(p.x, want[i][0]) && near(p.w, want[i][1])),
  `each plot where Python's image puts it (${placed.plots.map((p) => `${Math.round(p.x)}+${Math.round(p.w)}`).join(", ")})`);
check(placed.plots[0].y === placed.plots[1].y && placed.plots[2].y > placed.plots[0].y, "two in the first row, at its top; the third under them");

// lined up (align): the panels' edges in a column and their tops in a row; the scatter and
// the histogram, their heights free, as high as each other
const boxes = await page.evaluate(() =>
  [...document.querySelectorAll(".anytrellis-embed")].map((h) => {
    const v = window.anytrellisViews.find((x) => h.contains(x.root));
    const s = v.stage.getBoundingClientRect();
    const rects = v.lay.panels.map((b) => b.rect);
    const x0 = Math.min(...rects.map((r) => r.x));
    const y0 = Math.min(...rects.map((r) => r.y));
    const x1 = Math.max(...rects.map((r) => r.x + r.w));
    const y1 = Math.max(...rects.map((r) => r.y + r.h));
    return { left: s.left + x0, top: s.top + y0, right: s.left + x1, bottom: s.top + y1 };
  }),
);
const [sa, sb, sc] = boxes;
const show = (b) => `${Math.round(b.left)},${Math.round(b.top)}–${Math.round(b.right)},${Math.round(b.bottom)}`;
check(near(sa.top, sb.top) && near(sa.bottom, sb.bottom), `a row's panels start and end together (${show(sa)}; ${show(sb)})`);
check(near(sa.left, sc.left) && near(sa.right, sc.right), `a column's panels have the same left and right edges (${show(sa)}; ${show(sc)})`);

// the narrow plot: its title shown, its toolbar under it
const narrow = await page.evaluate(() => {
  const h = document.querySelectorAll(".anytrellis-embed")[1];
  const t = h.querySelector(".atr-title").getBoundingClientRect();
  const bar = h.querySelector(".atr-toolbar").getBoundingClientRect();
  return { title: t.width, titleBottom: t.bottom, barTop: bar.top, text: h.querySelector(".atr-title").textContent };
});
check(narrow.text === "Horsepower" && narrow.title > 60 && narrow.barTop >= narrow.titleBottom - 2, `a narrow plot: its title shown (${Math.round(narrow.title)} px), the toolbar under it`);
const wide = await page.evaluate(() => {
  const h = document.querySelectorAll(".anytrellis-embed")[0];
  const t = h.querySelector(".atr-title").getBoundingClientRect();
  const bar = h.querySelector(".atr-toolbar").getBoundingClientRect();
  return Math.abs(t.top + t.height / 2 - (bar.top + bar.height / 2));
});
check(wide < 4, "a wide one: its toolbar beside its title");
await page.screenshot({ path: join(out, `concat-${tag}.png`), fullPage: true });

// a brush in the scatter: the histogram, linked, lights its bars (and shows a chip, its
// header no taller: the plots don't move under a brush)
const headerH = () => page.evaluate(() => document.querySelectorAll(".anytrellis-embed")[1].querySelector(".atr-header").getBoundingClientRect().height);
const before = await headerH();
const lit = () =>
  page.evaluate(() => {
    const h = document.querySelectorAll(".anytrellis-embed")[1];
    const v = window.anytrellisViews.find((x) => h.contains(x.root));
    const l = v.highlight?.layers?.[0];
    return l ? ("fraction" in l ? [...l.fraction].filter((s) => s > 0).length : l.mask.reduce((a, b) => a + b, 0)) : 0;
  });
const box = await page.evaluate(() => {
  const h = document.querySelectorAll(".anytrellis-embed")[0];
  const v = window.anytrellisViews.find((x) => h.contains(x.root));
  const r = v.stage.getBoundingClientRect();
  const w = v.views[2].rect; // USA
  return { x: r.left + w.x, y: r.top + w.y, w: w.w, h: w.h };
});
await page.mouse.click(box.x + box.w * 0.9, box.y + 4);
await page.keyboard.press("s");
await page.mouse.move(box.x + box.w * 0.5, box.y + 2);
await page.mouse.down();
await page.mouse.move(box.x + box.w * 0.98, box.y + box.h - 2, { steps: 6 });
await page.mouse.up();
await page.waitForTimeout(300);
const bars = await lit();
check(bars > 0, `a brush in the scatter lights the histogram's bars (${bars})`);
const chips = await page.evaluate(() => document.querySelectorAll(".anytrellis-embed")[1].querySelectorAll(".atr-chip").length);
const after = await headerH();
check(chips > 0 && after === before, `its chip shows (${chips}), the narrow header as high as before (${before} → ${after} px)`);

// legends collected: the figure shows one legend under its plots, none of them their own;
// its clicks choose in each plot that has the legend
await page.goto(`file://${join(dir, "concat-legend.html")}${renderer ? `?renderer=${renderer}` : ""}`);
await page.waitForFunction(() => {
  const hosts = [...document.querySelectorAll(".anytrellis-embed")];
  return hosts.length === 3 && hosts.every((h) => h.dataset.state === "ready");
});
await page.waitForTimeout(300);
const shown = await page.evaluate(() => ({
  own: [...document.querySelectorAll(".anytrellis-embed .atr-legend")].filter((l) => getComputedStyle(l).display !== "none").length,
  groups: [...document.querySelectorAll(".anytrellis-figure-legend .atr-legend-group")].map((g) => g.textContent),
  below: document.querySelector(".anytrellis-figure-legend").getBoundingClientRect().top >= Math.max(...[...document.querySelectorAll(".anytrellis-embed")].map((h) => h.getBoundingClientRect().bottom)) - 1,
}));
check(shown.own === 0 && shown.groups.length === 1 && shown.groups[0] === "originEuropeJapanUSA" && shown.below, `one legend for the figure, under its plots (${JSON.stringify(shown)})`);
const chosen = () =>
  page.evaluate(() =>
    window.anytrellisViews.map((v) => ({ levels: v.brush?.legend?.levels ?? [], isolated: v.isolated?.level ?? null })),
  );
const entry = (label) => page.locator(".anytrellis-figure-legend .atr-legend-pick", { hasText: label });
await entry("Japan").click();
await page.waitForTimeout(200);
let now = await chosen();
check(JSON.stringify(now.slice(0, 2).map((c) => c.levels)) === "[[1],[1]]" && now[2].levels.length === 0, `a click chooses Japan in both plots that have the legend (${JSON.stringify(now)})`);
await entry("USA").click({ modifiers: ["Shift"] });
await page.waitForTimeout(200);
now = await chosen();
check(JSON.stringify(now.slice(0, 2).map((c) => c.levels)) === "[[1,2],[1,2]]", `Shift adds USA in both (${JSON.stringify(now)})`);
const on = await page.evaluate(() => [...document.querySelectorAll(".anytrellis-figure-legend .atr-legend-on")].map((e) => e.textContent));
check(JSON.stringify(on) === '["Japan","USA"]', `the figure's legend shows them chosen (${on})`);
await entry("Europe").dblclick();
await page.waitForTimeout(200);
now = await chosen();
check(now[0].isolated === 0 && now[1].isolated === 0 && JSON.stringify(now[0].levels) === "[1,2]", `a double-click shows Europe alone in both, the choice as before it (${JSON.stringify(now)})`);
// Escape in a plot: shown alone no more, there, in the legend and in the other plot
await page.evaluate(() => window.anytrellisViews[0].root.focus());
await page.keyboard.press("Escape");
await page.waitForTimeout(200);
const struck = await page.evaluate(() => document.querySelectorAll(".anytrellis-figure-legend .atr-legend-hidden").length);
now = await chosen();
check(struck === 0 && now.every((c) => c.isolated === null), `Escape in a plot: no entry alone, in the legend nor in the other plot (${struck} struck; ${JSON.stringify(now)})`);
const legendBoxes = await page.evaluate(() =>
  window.anytrellisViews.map((v) => {
    const s = v.stage.getBoundingClientRect();
    const rects = v.lay.panels.map((b) => b.rect);
    return Math.round(s.top + Math.max(...rects.map((r) => r.y + r.h)));
  }),
);
check(new Set(legendBoxes).size === 1, `without their legends, the row's panels still end together (${legendBoxes})`);
await page.screenshot({ path: join(out, `concat-legend-${tag}.png`), fullPage: true });

// ranges shared: a drag in one plot pans the other with it (x and y), not the third; Reset
// in the other brings both back
await page.goto(`file://${join(dir, "concat-shared.html")}${renderer ? `?renderer=${renderer}` : ""}`);
await page.waitForFunction(() => {
  const hosts = [...document.querySelectorAll(".anytrellis-embed")];
  return hosts.length === 3 && hosts.every((h) => h.dataset.state === "ready");
});
await page.waitForTimeout(300);
const ranges = () =>
  page.evaluate(() =>
    window.anytrellisViews.map((v) => {
      const p = v.spec.panels[0];
      const at = (axis, views) => (views.get(axis === "x" ? p.xg : p.yg) ?? p[axis]).map((n) => +(n + v.spec[axis].origin).toFixed(6));
      return { title: v.spec.title, x: at("x", v.xView), y: at("y", v.yView), joined: [v.spec.x.joined ?? null, v.spec.y.joined ?? null] };
    }),
  );
const byTitle = (rs) => Object.fromEntries(rs.map((r) => [r.title, r]));
let rs = byTitle(await ranges());
check(JSON.stringify(rs.Light.x) === JSON.stringify(rs.Heavy.x) && JSON.stringify(rs.Light.y) === JSON.stringify(rs.Heavy.y) && rs.All.joined.every((j) => j === null) && rs.Light.joined.every(Boolean),
  `two plots start with one range, the third its own (${JSON.stringify(rs)})`);
const start = rs;
const lightBox = await page.evaluate(() => {
  const v = window.anytrellisViews.find((x) => x.spec.title === "Light");
  const s = v.stage.getBoundingClientRect();
  const r = v.lay.panels[0].rect;
  return { x: s.left + r.x, y: s.top + r.y, w: r.w, h: r.h };
});
await page.mouse.move(lightBox.x + lightBox.w * 0.5, lightBox.y + lightBox.h * 0.5);
await page.mouse.down();
await page.mouse.move(lightBox.x + lightBox.w * 0.3, lightBox.y + lightBox.h * 0.6, { steps: 6 });
await page.mouse.up();
await page.waitForFunction(() => {
  const [a, b] = ["Light", "Heavy"].map((t) => window.anytrellisViews.find((v) => v.spec.title === t));
  return JSON.stringify([...a.xView]) !== "[]" && JSON.stringify([...a.xView.values()]) === JSON.stringify([...b.xView.values()]);
}, null, { timeout: 5000 }).catch(() => {});
rs = byTitle(await ranges());
const moved = rs.Light.x[0] > start.Light.x[0] && rs.Light.y[0] > start.Light.y[0];
check(moved && JSON.stringify(rs.Heavy.x) === JSON.stringify(rs.Light.x) && JSON.stringify(rs.Heavy.y) === JSON.stringify(rs.Light.y),
  `a drag in one plot pans the plot that shares its ranges (${JSON.stringify([rs.Light, rs.Heavy])})`);
check(JSON.stringify(rs.All.x) === JSON.stringify(start.All.x) && JSON.stringify(rs.All.y) === JSON.stringify(start.All.y), "the plot that shares nothing stays where it was");
await page.evaluate(() => window.anytrellisViews.find((v) => v.spec.title === "Heavy").root.querySelector("button[aria-label='Reset zoom']").click());
await page.waitForTimeout(200);
rs = byTitle(await ranges());
check(JSON.stringify(rs.Light.x) === JSON.stringify(start.Light.x) && JSON.stringify(rs.Light.y) === JSON.stringify(start.Light.y),
  `Reset in the other plot brings both back (${JSON.stringify(rs.Light)})`);
await page.screenshot({ path: join(out, `concat-shared-${tag}.png`), fullPage: true });

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
