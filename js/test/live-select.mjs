// In a live JupyterLab, notebook 02: a brush drawn in the browser reaches Python
// (Trellis.selected), Trellis.select reaches the browser, and s stays out of the notebook.
//   node test/live-select.mjs <url of 02_lattice_and_cleveland.ipynb> [chromium]
import { chromium } from "@playwright/test";

const [, , url, exe] = process.argv;
const browser = await chromium.launch({ executablePath: exe, args: ["--enable-unsafe-webgpu", "--use-angle=metal"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
await page.goto(url);
await page.waitForSelector(".jp-Notebook", { timeout: 60000 });
await page.waitForTimeout(2000);
await page.click("text=Run", { timeout: 10000 });
await page.click("text=Run All Cells");
await page.waitForSelector(".atr-root[data-renderer]", { timeout: 90000 });
await page.waitForFunction(() => [...document.querySelectorAll(".atr-title")].some((t) => t.textContent.startsWith("Fewer than three")), null, { timeout: 90000 });
await page.waitForTimeout(3000);
const root = await page.evaluateHandle(() =>
  [...document.querySelectorAll(".atr-root")].find((r) => r.querySelector(".atr-title")?.textContent.startsWith("Fewer than three")),
);
await root.scrollIntoViewIfNeeded();
await page.waitForTimeout(500);
let b = await (await root.$(".atr-stage")).boundingBox();

async function run(code) {
  const cells = await page.$$(".jp-Cell");
  await cells[cells.length - 1].click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("Escape");
  await page.keyboard.press("b");
  await page.keyboard.press("Enter");
  await page.keyboard.type(code);
  await page.keyboard.press("Shift+Enter");
  await page.waitForTimeout(2500);
  const outs = await page.$$eval(".jp-OutputArea-output", (o) => o.map((x) => x.textContent.trim()));
  return outs[outs.length - 1];
}

const markdown = () => page.$$eval(".jp-MarkdownCell", (c) => c.length);
const before = await markdown();
check((await run("print(len(followed.selected()))")) === "154", "Python's selection: 154 rows of 14 countries");

// in the browser: s, then a brush over the high fertility of 1955 (the first panel's right)
await root.scrollIntoViewIfNeeded();
await page.waitForTimeout(300);
b = await (await root.$(".atr-stage")).boundingBox(); // a new cell scrolled the page
const shotA = await root.screenshot();
await page.mouse.click(b.x + b.width * 0.15, b.y + b.height * 0.2);
await page.keyboard.press("s");
await page.waitForTimeout(1800); // the notice it shows fades: screenshots compare the plot
const shotS = await root.screenshot();
await page.mouse.move(b.x + b.width * 0.14, b.y + b.height * 0.07); // below the strip
await page.mouse.down();
await page.mouse.move(b.x + b.width * 0.245, b.y + b.height * 0.27, { steps: 8 });
await page.mouse.up();
await page.waitForTimeout(800);
const shotB = await root.screenshot();
check(!shotS.equals(shotB), "a brush drawn in the browser changes the plot");
check((await markdown()) === before && !(await page.$(".jp-Dialog")), "s and the drag leave the notebook alone");
const got = await run('s = followed.selection; print(s["panel"], s["x"] is not None, len(followed.selected()))');
const [panel, hasX, rows] = got.split(" ");
check(panel === "1955" && hasX === "True" && Number(rows) > 154, `Python sees the brush: panel ${panel}, ${rows} rows`);
// from Python: select() clears, in the browser too
await run('followed.select(); print("cleared")');
await root.scrollIntoViewIfNeeded();
await page.waitForTimeout(800);
const shotC = await root.screenshot();
check(!shotC.equals(shotB), "select() in Python clears the browser's brush");
check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
