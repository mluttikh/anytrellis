// Tooltips on save_html pages (pages.py): a title line and rows with swatches, every series
// at the hovered x for lines coloured by category, the crosshair's values on the axes, and a
// tooltip pinned by a click; with ?renderer= each backend.
//   node test/tooltip.mjs <pages dir> [screenshot dir] [renderer]
import { existsSync, readdirSync } from "node:fs";
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
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
let tag = renderer;

async function open(name) {
  const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`file://${join(dir, name)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  tag ||= await page.$eval(".anytrellis-embed", (e) => e.dataset.renderer);
  const stage = await (await page.$(".atr-stage")).boundingBox();
  const panels = await page.evaluate(() => window.anytrellisViews[0].lay.panels.map((b) => b.rect));
  const at = (i, fx, fy) => [stage.x + panels[i].x + panels[i].w * fx, stage.y + panels[i].y + panels[i].h * fy];
  return { page, errors, at, stage };
}

/** The live tooltip: shown or not, its title line, and its rows. */
const tipOf = (page, sel = ".atr-tip:not(.atr-tip-pinned)") =>
  page.$eval(sel, (t) => ({
    shown: getComputedStyle(t).display === "block",
    panel: t.querySelector(".atr-tip-panel")?.textContent ?? "",
    x: t.querySelector(".atr-tip-x") ? [t.querySelector(".atr-tip-x").dataset.name, t.querySelector(".atr-tip-x").dataset.value] : null,
    rows: [...t.querySelectorAll("tr")].map((r) => ({
      label: r.querySelector("th").textContent.trim(),
      value: r.querySelector("td").textContent.trim(),
      swatch: !!r.querySelector(".atr-tip-swatch"),
      strong: r.classList.contains("atr-tip-strong"),
    })),
  }));
const front = (page) => page.evaluate(() => {
  const f = window.anytrellisViews[0].front_;
  return { hovers: f.hovers.length, pins: f.pins.length, readout: f.readout, crossX: f.crossX };
});
const hoverAt = async (page, [x, y]) => {
  await page.mouse.move(x - 3, y - 3);
  await page.mouse.move(x, y);
  await page.waitForTimeout(80);
};

{
  // one panel of six countries' lines, coloured by country, with labels=
  const { page, errors, at } = await open("series.html");
  await hoverAt(page, at(0, 0.43, 0.5));
  let tip = await tipOf(page);
  check(tip.shown && tip.rows.length === 6, `lines coloured by category: every series at the hovered x (${tip.rows.length} rows)`);
  check(tip.x && tip.x[0] === "Year" && /^(19|20)\d5$|^(19|20)\d0$/.test(tip.x[1]), `the title line holds x, labelled as labels= says, at a data point's x (${tip.x})`);
  check(tip.rows.every((r) => r.swatch && r.label && r.value), "each row: a swatch, the series, its value");
  const values = tip.rows.map((r) => Number(r.value));
  check(values.every((v, i) => i === 0 || v <= values[i - 1]), `sorted top to bottom (${values.join(", ")})`);
  check(tip.rows.filter((r) => r.strong).length === 1, "the series nearest the pointer stands out");
  let f = await front(page);
  check(f.hovers === 6, `a ring on each series at that x (${f.hovers})`);
  check(f.readout && f.readout.x !== null && f.readout.x === f.crossX && f.readout.y !== null, "the crosshair snaps to that x, and its values go on the axes");
  // the readout: drawn over the x axis below the crosshair, in the text's colour
  const ink = await page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const w = v.views[0];
    const x = w.map.ox + v.front_.readout.x * w.map.sx;
    const ctx = v.front.getContext("2d");
    const d = ctx.getImageData(Math.round(x * v.dpr), Math.round((w.rect.y + w.rect.h + 12) * v.dpr), 1, 1).data;
    return [...d];
  });
  check(ink[3] > 200 && ink[0] < 90, `the x readout is drawn on the axis (${ink})`);
  await page.screenshot({ path: join(out, `tooltip-${tag}-series.png`) });
  // pinning: a click keeps it; the pointer moves on and a second tooltip shows. The click
  // that gives the plot the keys pins nothing
  const pinnedFrom = tip;
  await page.mouse.click(...at(0, 0.43, 0.5));
  await page.waitForTimeout(80);
  check((await page.$$(".atr-tip-pinned")).length === 0, "the first click gives the plot the keys, and pins nothing");
  await page.mouse.click(...at(0, 0.43, 0.5));
  await page.waitForTimeout(80);
  check((await page.$$(".atr-tip-pinned")).length === 1, "then a click pins the tooltip");
  await hoverAt(page, at(0, 0.8, 0.5));
  const pinned = await tipOf(page, ".atr-tip-pinned");
  tip = await tipOf(page);
  f = await front(page);
  check(pinned.x[1] === pinnedFrom.x[1] && tip.shown && tip.x[1] !== pinned.x[1], `it stays as the pointer moves on, next to the live one (${pinned.x[1]}, ${tip.x[1]})`);
  check(f.pins === 6, "its rings stay too");
  const selectable = await page.$eval(".atr-tip-pinned", (t) => getComputedStyle(t).userSelect);
  check(selectable === "text", "its text can be selected and copied");
  await page.screenshot({ path: join(out, `tooltip-${tag}-pinned.png`) });
  await page.keyboard.press("Escape");
  check((await page.$$(".atr-tip-pinned")).length === 0, "Esc unpins it");
  await page.mouse.click(...at(0, 0.43, 0.5));
  await page.click(".atr-tip-pinned .atr-tip-close");
  check((await page.$$(".atr-tip-pinned")).length === 0, "and so does its ×");
  await page.mouse.click(...at(0, 0.43, 0.5));
  await page.mouse.move(...at(0, 0.5, 0.5));
  await page.mouse.wheel(0, -200);
  await page.waitForTimeout(150);
  check((await page.$$(".atr-tip-pinned")).length === 0, "zooming unpins it (the panels moved under it)");
  await page.mouse.move(5, 5);
  await page.waitForTimeout(80);
  f = await front(page);
  check(!(await tipOf(page)).shown && f.readout === null && f.hovers === 0, "off the panels: no tooltip, rings or readout");
  check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
  await page.close();
}

{
  // lines grouped within a colour (a country a line, coloured by region): the line hovered
  const { page, errors, at } = await open("grouped.html");
  let tip = null;
  for (let fy = 0.2; fy < 0.9 && !tip?.shown; fy += 0.05) {
    await hoverAt(page, at(0, 0.5, fy));
    tip = await tipOf(page);
  }
  check(tip.shown && tip.rows.some((r) => r.label === "region") && tip.rows.length <= 4, `a colour of many lines: the line hovered, not a list (${JSON.stringify(tip.rows.map((r) => r.label))})`);
  check(tip.panel !== "" && tip.x && tip.x[0] === "year", `the title line: the panel and x (${tip.panel}, ${tip.x})`);
  check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
  await page.close();
}

{
  // points (labelled.html: labels=): the panel and x on the title line, y with its swatch
  const { page, errors, at } = await open("labelled.html");
  let tip = null;
  for (let fy = 0.1; fy < 0.95 && !tip?.shown; fy += 0.03) {
    for (let fx = 0.1; fx < 0.9 && !tip?.shown; fx += 0.1) {
      await hoverAt(page, at(0, fx, fy));
      tip = await tipOf(page);
    }
  }
  check(tip.shown && tip.panel === "1955" && tip.x[0] === "Children per woman", `a point: its panel and x, labelled (${tip.panel}, ${tip.x})`);
  check(tip.rows[0].label === "Life expectancy" && tip.rows[0].swatch && tip.rows[1].label === "Region", `then y with its colour's swatch, then the colour column (${JSON.stringify(tip.rows)})`);
  await page.locator(".atr-tip").first().screenshot({ path: join(out, `tooltip-${tag}-point.png`) });
  check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
  await page.close();
}

await browser.close();
process.exit(failures.length ? 1 : 0);
