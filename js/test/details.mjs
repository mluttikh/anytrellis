// Details the eye catches, on save_html pages: a page's own styles (a documentation
// theme's tables, its letter spacing) leave the plot and its tooltip as they are, and a
// linked plot's highlight of part of a histogram's bars draws the faded bars whole, the
// selected share solid from their base; with a renderer (?renderer=) each backend.
//   node test/details.mjs <dir of the pages> [dir for screenshots] [renderer]
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const pages = resolve(process.argv[2]);
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
const tag = renderer || "auto";

async function open(name) {
  const page = await browser.newPage({ viewport: { width: 1000, height: 800 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`file://${join(pages, name)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  return { page, errors };
}

{
  // a documentation theme's styles, as Material's and Zensical's: every plain table roomy,
  // bordered and bold-headed, the text's letter spacing tightened
  const { page, errors } = await open("years.html");
  await page.addStyleTag({
    content: `body { letter-spacing: -0.15px; }
      table:not([class]) { display: inline-block; font-size: 0.8rem; border: 1px solid #ccc; }
      table:not([class]) th { min-width: 5rem; padding: 0.9375em 1.25em; font-weight: 700; }
      table:not([class]) td { padding: 0.9375em 1.25em; border-top: 1px solid #ccc; }
      th, td { padding: 9px; } table { margin: 2em 0; }`,
  });
  const rects = await page.evaluate(() => window.anytrellisViews[0].views.map((v) => v.rect));
  const box = await (await page.$(".atr-stage")).boundingBox();
  const r = rects[0];
  let shown = false;
  for (let fy = 0.1; fy < 0.95 && !shown; fy += 0.03) {
    for (let fx = 0.1; fx < 0.9 && !shown; fx += 0.1) {
      await page.mouse.move(box.x + r.x + r.w * fx, box.y + r.y + r.h * fy);
      shown = await page.$eval(".atr-tip", (e) => getComputedStyle(e).display === "block");
    }
  }
  check(shown, "hover shows a tooltip");
  if (shown) {
    const tip = await page.$eval(".atr-tip", (t) => {
      const c = (e) => getComputedStyle(e);
      const th = t.querySelector("th");
      const td = t.querySelector("td");
      const table = t.querySelector("table");
      return {
        cell: [c(th).paddingTop, c(th).paddingLeft, c(td).paddingTop, c(td).paddingLeft, c(th).minWidth],
        weight: c(th).fontWeight,
        size: [c(th).fontSize, c(td).fontSize],
        border: [c(table).borderTopWidth, c(td).borderTopWidth],
        margin: c(table).marginTop,
        rowHeight: t.querySelector("tr").getBoundingClientRect().height,
      };
    });
    check(tip.cell.every((v) => v === "0px"), `its cells keep no padding of the page's (${tip.cell.join(" ")})`);
    check(tip.weight === "400" && tip.size.every((s) => s === "12px"), `its labels are the plot's text (${tip.weight}, ${tip.size.join(" ")})`);
    check(tip.border.every((b) => b === "0px") && tip.margin === "0px", "and no borders or margins of the page's");
    check(tip.rowHeight < 20, `a compact line a row (${tip.rowHeight.toFixed(1)} px)`);
    await page.locator(".atr-tip").screenshot({ path: join(out, `details-${tag}-tooltip.png`) });
  }
  const spacing = await page.$eval(".atr-root", (e) => getComputedStyle(e).letterSpacing);
  check(spacing === "normal", `the plot keeps its letter spacing (${spacing})`);
  check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
  await page.close();
}

{
  // a linked plot selects half the rows of each bar: the bars faded whole, half of each solid
  const { page, errors } = await open("hist.html");
  const colours = await page.evaluate(async () => {
    const v = window.anytrellisViews[0];
    const n = v.spec.layers[0].count;
    v.setHighlight({ layers: [{ fraction: new Float32Array(n).fill(0.5) }] });
    await new Promise((r) => setTimeout(r, 300));
    // the tallest bar, at 90% and at 25% of its height: in the faded part and the solid one
    const view = v.views[0];
    const c = v.scene.layers[0].coords;
    let best = 0;
    for (let i = 0; i < n; i++) if (c[i * 4 + 3] > c[best * 4 + 3]) best = i;
    const x = view.map.ox + ((c[best * 4] + c[best * 4 + 2]) / 2) * view.map.sx;
    const at = (f) => view.map.oy + (c[best * 4 + 1] + f * (c[best * 4 + 3] - c[best * 4 + 1])) * view.map.sy;
    const img = await createImageBitmap(await v.pngImage(1));
    const ctx = new OffscreenCanvas(img.width, img.height).getContext("2d");
    ctx.drawImage(img, 0, 0);
    const stage = document.querySelector(".atr-stage").getBoundingClientRect();
    const root = document.querySelector(".atr-root").getBoundingClientRect();
    const px = (y) => Array.from(ctx.getImageData(Math.round(x + stage.left - root.left), Math.round(y + stage.top - root.top), 1, 1).data);
    const panel = px(view.rect.y + 2);
    return { faded: px(at(0.9)), solid: px(at(0.25)), panel };
  });
  const same = (a, b) => a.slice(0, 3).every((v, i) => Math.abs(v - b[i]) <= 3);
  check(!same(colours.faded, colours.panel), `a bar's unselected part is drawn faded (${colours.faded} vs the panel's ${colours.panel})`);
  check(!same(colours.faded, colours.solid), `and its selected part solid (${colours.solid})`);
  await page.screenshot({ path: join(out, `details-${tag}-hist.png`) });
  check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
  await page.close();
}

await browser.close();
if (failures.length) {
  console.error(`${failures.length} failed`);
  process.exit(1);
}
