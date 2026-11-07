// Open a notebook in a live JupyterLab or marimo, run it, and screenshot every plot.
//   jupyter lab --no-browser --port 8899 --IdentityProvider.token=test   (in examples/jupyter)
//   node test/notebooks.mjs jupyter "http://localhost:8899/lab/tree/01_getting_started.ipynb?reset&token=test" out/jl01 <chromium>
//   marimo run --headless --port 2718 --no-token *.py                     (in examples/marimo)
//   node test/notebooks.mjs marimo "http://localhost:2718/?file=01_getting_started.py" out/mo01 <chromium>
// Prints, per plot, the backend that draws it and any status it shows; then page errors.
import { chromium } from "@playwright/test";
const [, , mode, url, prefix, exe] = process.argv;
const browser = await chromium.launch({ executablePath: exe, args: ["--enable-unsafe-webgpu", ...(process.platform === "darwin" ? ["--use-angle=metal"] : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => /anytrellis|atr|Error/i.test(m.text()) && m.type() !== "log" && errors.push(m.text().slice(0, 200)));
await page.goto(url);
if (mode === "jupyter") {
  await page.waitForSelector(".jp-Notebook", { timeout: 60000 });
  await page.waitForTimeout(2500);
  await page.click("text=Run", { timeout: 10000 });
  await page.click("text=Run All Cells");
}
// wait for plots to be drawn (status hidden, renderer chosen)
const deadline = Date.now() + 90000;
let n = 0;
while (Date.now() < deadline) {
  await page.waitForTimeout(1500);
  n = await page.$$eval(".atr-root[data-renderer]", (e) => e.length);
  const total = await page.$$eval(".atr-root", (e) => e.length);
  const busy = mode === "jupyter" ? await page.$$eval(".jp-InputPrompt", (p) => p.some((x) => x.textContent.includes("*"))) : false;
  if (n > 0 && n === total && !busy) break;
}
await page.waitForTimeout(2500);
const roots = await page.$$(".atr-root");
console.log(`${prefix}: ${roots.length} plots, ${n} with a renderer`);
for (let i = 0; i < roots.length; i++) {
  await roots[i].scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  const info = await roots[i].evaluate((e) => ({
    renderer: e.dataset.renderer,
    status: e.querySelector(".atr-status")?.textContent || "",
    h: e.getBoundingClientRect().height,
  }));
  console.log(`  ${i}: ${info.renderer} h=${Math.round(info.h)} ${info.status}`);
  await roots[i].screenshot({ path: `${prefix}-${i}.png` });
}
console.log("  errors:", errors.length ? errors.slice(0, 5) : "none");
await browser.close();
