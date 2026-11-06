// Interaction check on a save_html page: hover shows a tooltip, wheel zoom moves every panel
// of the scale group, double-click resets, and the dark theme applies.
//   node test/interact.mjs <page.html> [screenshot dir]
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const file = resolve(process.argv[2]);
const out = resolve(process.argv[3] ?? ".");
function executable() {
  if (process.env.CHROMIUM) return process.env.CHROMIUM;
  if (existsSync(chromium.executablePath())) return undefined;
  const cache = join(homedir(), "Library/Caches/ms-playwright");
  for (const d of readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse()) {
    const app = join(cache, d, "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
    if (existsSync(app)) return app;
  }
}
const browser = await chromium.launch({ executablePath: executable(), args: ["--enable-unsafe-webgpu", "--use-angle=metal"] });
const page = await browser.newPage({ viewport: { width: 1000, height: 800 }, colorScheme: "dark" });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(`file://${file}`);
await page.waitForSelector(".anytrellis-embed[data-state='ready']");
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const ranges = () => page.evaluate(() => window.anytrellisViews[0].views.map((v) => [...v.x]));
const rects = await page.evaluate(() => window.anytrellisViews[0].views.map((v) => v.rect));
const stage = await page.$(".atr-stage");
const box = await stage.boundingBox();

// hover: sweep across the first panel until a tooltip shows
const r = rects[0];
let shown = false;
for (let fy = 0.1; fy < 0.95 && !shown; fy += 0.04) {
  await page.mouse.move(box.x + r.x + r.w * 0.5, box.y + r.y + r.h * fy);
  shown = await page.$eval(".atr-tip", (e) => getComputedStyle(e).display === "block");
}
check(shown, "hover shows a tooltip");
if (shown) console.log("     tooltip:", (await page.$eval(".atr-tip", (e) => e.innerText)).replace(/\s+/g, " "));
await page.screenshot({ path: join(out, "interact-hover-dark.png") });

// wheel zoom (needs focus: click first)
const before = await ranges();
await page.mouse.click(box.x + r.x + r.w * 0.5, box.y + r.y + r.h * 0.5);
await page.mouse.wheel(0, -300);
await page.waitForTimeout(100);
const after = await ranges();
const groups = await page.evaluate(() => window.anytrellisViews[0].spec.panels.map((p) => p.xg));
const zoomed = after.map((a, i) => a[1] - a[0] < before[i][1] - before[i][0] - 1e-9);
check(zoomed[0], "wheel zooms the panel");
check(zoomed.every((z, i) => z === (groups[i] === groups[0])), "every panel of its x group zooms with it (and only those)");

// drag pans
const mid = await ranges();
await page.mouse.move(box.x + r.x + r.w * 0.5, box.y + r.y + r.h * 0.5);
await page.mouse.down();
await page.mouse.move(box.x + r.x + r.w * 0.3, box.y + r.y + r.h * 0.5, { steps: 5 });
await page.mouse.up();
const panned = await ranges();
check(panned[0][0] > mid[0][0], "drag pans");

// double-click opens the panel: it alone, on the whole width, with the way back
const name = await page.evaluate(() => window.anytrellisViews[0].focusName);
check(name === null, "no panel open at first");
const one = async () => page.evaluate(() => window.anytrellisViews[0].views.map((v) => v.panel));
await page.mouse.dblclick(box.x + r.x + r.w * 0.5, box.y + r.y + r.h * 0.5);
await page.waitForTimeout(150);
let shown2 = await one();
const rect0 = await page.evaluate(() => window.anytrellisViews[0].views[0].rect);
check(shown2.length === 1 && shown2[0] === 0, `double-click opens the panel (${shown2})`);
check(rect0.w > r.w * 1.5, `the opened panel is wider (${Math.round(rect0.w)} px, was ${Math.round(r.w)})`);
check(await page.isVisible(".atr-crumb"), "the breadcrumb shows the way back");
// zoom in the opened panel: back in the grid, its x group shows the same range
await page.mouse.move(box.x + rect0.x + rect0.w * 0.5, box.y + rect0.y + rect0.h * 0.5);
await page.mouse.wheel(0, -400);
await page.waitForTimeout(100);
const zoomedOpen = (await ranges())[0];
await page.keyboard.press("PageDown");
await page.waitForTimeout(100);
shown2 = await one();
check(shown2[0] === 1, `Page Down opens the next panel (${shown2})`);
await page.keyboard.press("Backspace");
await page.waitForTimeout(150);
const back = await ranges();
check(back.length === before.length, "Backspace goes back to all panels");
check(back.every((a, i) => groups[i] !== groups[0] || Math.abs(a[0] - zoomedOpen[0]) < 1e-6), "the zoom stays linked after going back");
// Enter opens the panel under the pointer; Esc goes back
await page.mouse.move(box.x + rects[1].x + rects[1].w * 0.5, box.y + rects[1].y + rects[1].h * 0.5);
await page.keyboard.press("Enter");
await page.waitForTimeout(100);
check((await one())[0] === 1, "Enter opens the panel under the pointer");
await page.keyboard.press("Escape");
await page.waitForTimeout(100);
check((await one()).length === before.length, "Esc goes back");
// keys the plot handles stay out of the page (JupyterLab's shortcuts)
await page.evaluate(() => {
  window.leaked = [];
  document.addEventListener("keydown", (e) => window.leaked.push(e.key));
});
await page.keyboard.press("r");
await page.waitForTimeout(50);
const reset = await ranges();
check(reset.every((a, i) => Math.abs(a[0] - before[i][0]) < 1e-6 && Math.abs(a[1] - before[i][1]) < 1e-6), "r resets the zoom");
await page.keyboard.press("x");
const leaked = await page.evaluate(() => window.leaked);
check(!leaked.includes("r") && leaked.includes("x"), `handled keys stay in the plot (reached the page: ${leaked})`);
// full screen
await page.keyboard.press("f");
await page.waitForTimeout(400);
const full = await page.evaluate(() => {
  const root = document.querySelector(".atr-root");
  return { on: root.matches(":fullscreen"), h: root.getBoundingClientRect().height, stage: document.querySelector(".atr-stage").getBoundingClientRect().height };
});
check(full.on, "f goes full screen");
check(full.stage > 600, `the plot fills the screen (stage ${Math.round(full.stage)} px of ${Math.round(full.h)})`);
await page.screenshot({ path: join(out, "interact-fullscreen.png") });
await page.keyboard.press("f");
await page.waitForTimeout(400);
check(!(await page.evaluate(() => document.querySelector(".atr-root").matches(":fullscreen"))), "f again leaves full screen");

const bg = await page.$eval(".atr-root", (e) => getComputedStyle(e).backgroundColor);
check(bg === "rgb(18, 23, 29)", `dark theme (background ${bg})`);
check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
