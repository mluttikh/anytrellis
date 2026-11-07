// Clicking legend entries on a save_html page with a category colour: a click selects a
// colour, Shift+click adds one, a click on the only one chosen or Esc clears, a brush then
// keeps the colours; with ?renderer= each backend.
//   node test/legend.mjs <page.html> [screenshot dir] [renderer]
import { existsSync, readdirSync, writeFileSync } from "node:fs";
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
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    return { legend: v.brush?.legend ?? null, sel: v.selected, brushes: v.front_.brushes.length };
  });
const pressed = () => page.$$eval(".atr-legend-pick", (items) => items.map((i) => i.getAttribute("aria-pressed") === "true"));
const plot = page.locator(".atr-stage");
const shot = async () => {
  await page.mouse.move(1, 1); // the legend is in the picture: not hovered, not focused
  await page.evaluate(() => document.activeElement?.blur?.());
  await page.waitForTimeout(250);
  return plot.screenshot();
};

const items = page.locator(".atr-legend-pick");
const n = await items.count();
check(n >= 3, `the legend's entries can be clicked (${n})`);
const before = await shot();

await items.nth(1).click();
let s = await state();
const one = s.sel?.selected ?? 0;
check(JSON.stringify(s.legend?.levels) === "[1]" && one > 0 && one < s.sel.total, `a click selects one colour: ${one} of ${s.sel?.total}`);
check(JSON.stringify(await pressed()) === JSON.stringify([...Array(n)].map((_, i) => i === 1)), "its entry is pressed");
check(s.brushes === 0, "no brush rectangle is drawn for colours alone");
const shotOne = await shot();
check(!shotOne.equals(before), "the other colours fade");
await plot.screenshot({ path: join(out, `legend-one-${tag}.png`) });

await items.nth(2).click({ modifiers: ["Shift"] });
s = await state();
check(JSON.stringify(s.legend?.levels) === "[1,2]" && s.sel.selected > one, "Shift+click adds a colour");
await items.nth(2).click({ modifiers: ["Shift"] });
s = await state();
check(JSON.stringify(s.legend?.levels) === "[1]" && s.sel.selected === one, "Shift+click again takes it away");

await items.nth(1).click();
s = await state();
check(s.legend === null && s.sel === null, "a click on the only colour chosen clears");
await page.waitForTimeout(1800); // the notice fades
const after = await shot();
check(after.equals(before), "the plot is as it was");
if (!after.equals(before)) {
  writeFileSync(join(out, `legend-before-${tag}.png`), before);
  writeFileSync(join(out, `legend-after-${tag}.png`), after);
}

// a colour chosen after another was cleared shows itself, not the first one's marks (the
// renderers keep the selected marks' buffers by version: a new selection needs a new one)
// one colour, cleared, then another, each drawn; compared once the notice has gone
await items.nth(1).click();
await page.waitForTimeout(1800);
const shotFirst = await shot();
await items.nth(1).click();
await page.waitForTimeout(300);
await items.nth(2).click();
await page.waitForTimeout(1800);
const shotTwo = await shot();
check(!shotTwo.equals(shotFirst), "a colour chosen after clearing another shows its own marks");
await items.nth(2).click();

// a colour, then a brush over the left half: both hold
await items.nth(1).click();
// the left half of the first panel (in every panel: the same range)
const box = await plot.boundingBox();
const r = await page.evaluate(() => window.anytrellisViews[0].views[0].rect);
await page.mouse.click(box.x + r.x + r.w * 0.5, box.y + r.y + r.h * 0.5);
await page.keyboard.press("s");
await page.mouse.move(box.x + r.x + 2, box.y + r.y + 2);
await page.mouse.down();
await page.mouse.move(box.x + r.x + r.w * 0.4, box.y + r.y + r.h - 2, { steps: 8 });
await page.mouse.up();
s = await state();
check(JSON.stringify(s.legend?.levels) === "[1]" && s.sel.selected > 0 && s.sel.selected < one, `a brush keeps the colour: ${s.sel.selected} of ${one}`);
await plot.screenshot({ path: join(out, `legend-brush-${tag}.png`) });
await page.keyboard.press("Escape");
s = await state();
check(s.legend === null && s.sel === null && !(await pressed()).some(Boolean), "Esc clears both");

// the keyboard: Tab to an entry, Enter
await items.nth(0).focus();
await page.keyboard.press("Enter");
s = await state();
check(JSON.stringify(s.legend?.levels) === "[0]", "Enter on a focused entry selects it");
check(errors.length === 0, `no page errors ${errors.slice(0, 3).join(" | ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
