// In a live JupyterLab, notebook 07: a brush in one linked plot highlights the others,
// while it is dragged and after; Python sees the rows; a click in another plot clears.
//   node test/linked.mjs <url of 07_linked_plots.ipynb> [chromium]
import { writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const [, , url, exe] = process.argv;
const browser = await chromium.launch({ executablePath: exe, args: ["--enable-unsafe-webgpu", "--use-angle=metal"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
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
const plot = async (title) => {
  await page.waitForFunction((t) => [...document.querySelectorAll(".atr-title")].some((x) => x.textContent.startsWith(t)), title, { timeout: 90000 });
  return page.evaluateHandle((t) => [...document.querySelectorAll(".atr-root")].find((r) => r.querySelector(".atr-title")?.textContent.startsWith(t)), title);
};
const scatter = await plot("Weight and mileage");
const power = await plot("Horsepower by origin");
const mileage = await plot("Mileage by cylinders");
const years = await plot("Fertility and life");
const lives = await plot("Life expectancy");
await page.waitForTimeout(3000);

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
const stage = async (root) => {
  await root.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  return (await root.$(".atr-stage")).boundingBox();
};
// a brush from (fx0, fy0) to (fx1, fy1), fractions of the stage; `during` runs mid-drag
async function brush(root, [fx0, fy0, fx1, fy1], during) {
  const b = await stage(root);
  await page.mouse.click(b.x + b.width * fx0, b.y + b.height * fy0);
  await page.keyboard.press("s");
  await page.waitForTimeout(1800); // the notice fades
  await page.mouse.move(b.x + b.width * fx0, b.y + b.height * fy0);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * ((fx0 + fx1) / 2), b.y + b.height * ((fy0 + fy1) / 2), { steps: 6 });
  await page.waitForTimeout(600);
  const mid = during ? await during() : null;
  await page.mouse.move(b.x + b.width * fx1, b.y + b.height * fy1, { steps: 6 });
  await page.mouse.up();
  await page.keyboard.press("s"); // back to panning
  await page.waitForTimeout(1500);
  return mid;
}
const shot = (root) => root.screenshot();

// the selection made in the notebook (scatter.select): the heaviest cars, shown in the others
check(Number(await run("print(len(power.selected()))")) > 0, "select() in Python highlights the linked plots");
await run("scatter.select(); print('cleared')");
await page.waitForTimeout(800);
const powerA = await shot(power);
const mileageA = await shot(mileage);
await page.waitForTimeout(400);
check(powerA.equals(await shot(power)), "a still plot screenshots the same");

// brush the light cars (the scatter's left half)
const powerMid = await brush(scatter, [0.08, 0.1, 0.4, 0.9], async () => {
  const p = await power.screenshot();
  return p;
});
check(!powerMid.equals(powerA), "the histogram follows the brush while it is dragged");
const powerB = await shot(power);
const mileageB = await shot(mileage);
check(!powerB.equals(powerA) && !powerB.equals(powerMid), "the histogram shows the final brush");
check(!mileageB.equals(mileageA), "the boxes light up");
const [a, c, none] = (await run("print(len(power.selected()), len(scatter.selected()), power.selection is None)")).split(" ");
check(Number(a) > 0 && a === c && none === "True", `Python: the linked plot selects the brushed rows (${a} of ${c})`);

// a click in the histogram (no brush of its own) clears the link's selection
const pb = await stage(power);
await page.mouse.click(pb.x + pb.width * 0.5, pb.y + pb.height * 0.5);
await page.keyboard.press("s");
await page.mouse.click(pb.x + pb.width * 0.5, pb.y + pb.height * 0.5);
await page.keyboard.press("s");
await page.waitForTimeout(1500);
await page.mouse.move(5, 5);
await page.waitForTimeout(500);
check((await run("print(scatter.selection is None, len(power.selected()))")) === "True 0", "a click in a linked plot clears the selection");
check((await shot(power)).equals(powerA), "the histogram is back as it was");

// on="country": brush high fertility in 1955, their lines light up
const livesA = await shot(lives);
await brush(years, [0.15, 0.2, 0.215, 0.4]); // 1955: high fertility, short lives
const livesB = await shot(lives);
check(!livesB.equals(livesA), "on=country: the brushed countries' lines light up");
const rows = (await run("print(len(lives.selected()) % 11 == 0 and len(lives.selected()) > 0)"));
check(rows === "True", "on=country: every year of the selected countries");
if (process.env.SHOTS) {
  writeFileSync(`${process.env.SHOTS}/linked-power.png`, powerB);
  writeFileSync(`${process.env.SHOTS}/linked-mileage.png`, mileageB);
  await lives.screenshot({ path: `${process.env.SHOTS}/linked-lives.png` });
  await years.screenshot({ path: `${process.env.SHOTS}/linked-years.png` });
}
check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
