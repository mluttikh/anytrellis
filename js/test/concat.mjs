// Different plots in one figure on a save_html page (compose.py): each plot where Python's
// image puts it (concat.json: across the grid, at 824 px), the figure's title over them, a
// narrow plot's toolbar on a line under its title, and a brush in one plot lighting up its
// rows in the plot linked with it.
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

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
