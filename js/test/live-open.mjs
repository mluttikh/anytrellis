// In a live JupyterLab or marimo: open a panel, step, go back, full screen; and the keys
// stay out of the notebook (JupyterLab's command-mode shortcuts).
//   node test/live-open.mjs jupyter|marimo <url> <screenshot prefix> [chromium]
import { chromium } from "@playwright/test";

const [, , mode, url, prefix, exe] = process.argv;
const browser = await chromium.launch({ executablePath: exe, args: ["--enable-unsafe-webgpu", ...(process.platform === "darwin" ? ["--use-angle=metal"] : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
await page.goto(url);
if (mode === "jupyter") {
  await page.waitForSelector(".jp-Notebook", { timeout: 60000 });
  await page.waitForTimeout(2000);
  await page.click("text=Run", { timeout: 10000 });
  await page.click("text=Run All Cells");
}
await page.waitForSelector(".atr-root[data-renderer]", { timeout: 90000 });
await page.waitForTimeout(3000);
const root = (await page.$$(".atr-root"))[0];
await root.scrollIntoViewIfNeeded();
await page.waitForTimeout(500);
const stage = await root.$(".atr-stage");
const b = await stage.boundingBox();
const crumbs = () => root.evaluate((r) => r.querySelectorAll(".atr-crumb").length);
const panelName = () => root.evaluate((r) => r.querySelector(".atr-panel-name")?.textContent ?? null);

// double-click the first panel
await page.mouse.dblclick(b.x + b.width * 0.25, b.y + b.height * 0.3);
await page.waitForTimeout(400);
const name = await panelName();
check(name !== null, `double-click opens a panel (${name})`);
await root.screenshot({ path: `${prefix}-opened.png` });
const editBefore = mode === "jupyter" ? await page.$$eval(".jp-mod-editMode", (e) => e.length) : 0;
await page.keyboard.press("PageDown");
await page.waitForTimeout(300);
const name2 = await panelName();
check(name2 !== null && name2 !== name, `Page Down: the next panel (${name2})`);
await page.keyboard.press("r");
await page.keyboard.press("r"); // r r restarts the kernel in JupyterLab's command mode
await page.waitForTimeout(500);
if (mode === "jupyter") check(!(await page.$(".jp-Dialog")), "r r stays in the plot (no restart-kernel dialog)");
await page.keyboard.press("Backspace");
await page.waitForTimeout(400);
check((await crumbs()) === 0, "Backspace: all panels again");

// Enter over a panel opens it (and does not put JupyterLab's cell in edit mode)
await page.mouse.move(b.x + b.width * 0.25, b.y + b.height * 0.3);
await page.keyboard.press("Enter");
await page.waitForTimeout(400);
check((await crumbs()) === 1, "Enter opens the panel under the pointer");
if (mode === "jupyter") {
  const editAfter = await page.$$eval(".jp-mod-editMode", (e) => e.length);
  check(editAfter === editBefore, "Enter does not start editing a cell");
}
await page.keyboard.press("Escape");
await page.waitForTimeout(300);
check((await crumbs()) === 0, "Esc: all panels again");

// full screen with the toolbar button, then f to leave
await root.hover();
const full = await root.$(".atr-toolbar .atr-button:last-child");
await full.click();
await page.waitForTimeout(800);
check(await root.evaluate((r) => r.matches(":fullscreen")), "the toolbar button goes full screen");
const h = await root.evaluate((r) => r.querySelector(".atr-stage").getBoundingClientRect().height);
check(h > 700, `full screen: the plot fills the screen (stage ${Math.round(h)} px)`);
await page.screenshot({ path: `${prefix}-fullscreen.png` });
await page.keyboard.press("f");
await page.waitForTimeout(800);
check(!(await root.evaluate((r) => r.matches(":fullscreen"))), "f leaves full screen");
const h2 = await root.evaluate((r) => r.querySelector(".atr-stage").getBoundingClientRect().height);
check(h2 < h, `the plot is its own size again (${Math.round(h2)} px)`);
check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
