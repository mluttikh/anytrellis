// In a live JupyterLab or marimo: box zoom (Shift+drag), y fit, undo, and that the plot's
// keys and Shift+drag stay out of the notebook (JupyterLab's command mode: y makes a cell
// code, z undoes a cell operation, Shift+click selects cells).
//   node test/live-zoom.mjs jupyter|marimo <url> [chromium]
import { chromium } from "@playwright/test";

const [, , mode, url, exe] = process.argv;
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
const b = await (await root.$(".atr-stage")).boundingBox();
const notebook = () =>
  mode === "jupyter"
    ? page.evaluate(() => ({
        markdown: document.querySelectorAll(".jp-MarkdownCell").length,
        selected: document.querySelectorAll(".jp-Cell.jp-mod-selected").length,
        dialog: !!document.querySelector(".jp-Dialog"),
      }))
    : Promise.resolve({ markdown: 0, selected: 0, dialog: false });
await page.mouse.click(b.x + b.width * 0.2, b.y + b.height * 0.3);
const before = await notebook();
const shotA = await root.screenshot();
// Shift+drag: a box zoom
await page.keyboard.down("Shift");
await page.mouse.move(b.x + b.width * 0.1, b.y + b.height * 0.25);
await page.mouse.down();
await page.mouse.move(b.x + b.width * 0.22, b.y + b.height * 0.27, { steps: 6 });
const boxShown = !(await root.screenshot()).equals(shotA); // the box, drawn
await page.mouse.up();
await page.keyboard.up("Shift");
await page.waitForTimeout(400);
const shotB = await root.screenshot();
check(boxShown && !shotA.equals(shotB), "Shift+drag zooms to a box");
let nb = await notebook();
check(nb.selected === before.selected, `Shift+drag selects no cells (${nb.selected} selected, was ${before.selected})`);
// y, z, u and Cmd+Z: the plot's, not the notebook's
for (const k of ["y", "z", "z", "u", "Meta+z"]) {
  await page.keyboard.press(k);
  await page.waitForTimeout(150);
}
nb = await notebook();
check(nb.markdown === before.markdown, `y and z leave the cells alone (markdown cells ${nb.markdown}, were ${before.markdown})`);
check(!nb.dialog, "no notebook dialog opened");
const shotC = await root.screenshot();
check(!shotC.equals(shotB), "u and Cmd+Z undid the zoom");
check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
