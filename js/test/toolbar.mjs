// The toolbar on a save_html page: the drag mode as one of three (pan, box zoom, select),
// by click, by arrow keys and by z / s; chips that say what differs from the start (zoomed,
// selected) and undo it; the keys and mouse on ?, with the renderer and the version, closed
// by Esc or a click outside; with ?renderer= each backend.
//   node test/toolbar.mjs <page.html> [screenshot dir] [renderer]
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
const mode = () => page.evaluate(() => window.anytrellisViews[0].mode);
const checked = () => page.$$eval(".atr-segmented [role='radio']", (bs) => bs.filter((b) => b.getAttribute("aria-checked") === "true").map((b) => b.getAttribute("aria-label")));
const chips = () => page.$$eval(".atr-chip", (cs) => cs.map((c) => c.dataset.chip + ": " + c.firstChild.textContent));
const settle = () => page.waitForTimeout(150);
const layout = await page.evaluate(() => window.anytrellisViews[0].lay.panels);
const stage = await (await page.$(".atr-stage")).boundingBox();
const at = (rect, fx, fy) => [stage.x + rect.x + rect.w * fx, stage.y + rect.y + rect.h * fy];
const p0 = layout[0].rect;

// ---- the drag mode ---------------------------------------------------------------------
check((await mode()) === "pan" && JSON.stringify(await checked()) === '["Pan: drag moves the view"]', "pan is on at the start, and the only one checked");
await page.click(".atr-segmented [aria-label^='Box zoom']");
check((await mode()) === "zoom" && (await checked()).length === 1, "a click on box zoom: zoom mode, one checked");
await page.click(".atr-segmented [aria-label^='Box zoom']");
check((await mode()) === "zoom", "a second click keeps it (a radio, not a toggle)");
await page.focus(".atr-segmented [aria-checked='true']");
await page.keyboard.press("ArrowRight");
check((await mode()) === "select", "→ in the group: the next mode");
check(await page.evaluate(() => document.activeElement?.getAttribute("aria-checked") === "true"), "and the focus moves with it");
await page.keyboard.press("ArrowRight");
check((await mode()) === "lasso", "→ again: the lasso");
await page.keyboard.press("ArrowRight");
check((await mode()) === "pan", "→ from the last: back to the first");
await page.mouse.click(...at(p0, 0.5, 0.5));
await page.keyboard.press("s");
check((await mode()) === "select" && (await checked())[0].startsWith("Select"), "s: select, and its button is checked");
await page.keyboard.press("s");
check((await mode()) === "pan", "s again: pan");

// ---- chips ------------------------------------------------------------------------------
check((await chips()).length === 0, "no chips at the start");
await page.mouse.move(...at(p0, 0.5, 0.5));
await page.mouse.wheel(0, -400);
await settle();
let c = await chips();
check(c.length === 1 && c[0] === "zoom: Zoomed in x", `a scroll zooms x: a chip says so (${c})`);
const header = await (await page.$(".atr-header")).boundingBox();
const stageAfter = await (await page.$(".atr-stage")).boundingBox();
check(Math.abs(stageAfter.y - stage.y) < 0.5, "the chip sits in the header: the plot does not move");
check(header.height < 40, "the header stays one row");
await page.click(".atr-chip[data-chip='zoom'] button");
await settle();
check((await chips()).length === 0, "Reset on the chip: zoom gone, and the chip");

await page.keyboard.press("s");
await page.mouse.move(...at(p0, 0.2, 0.2));
await page.mouse.down();
await page.mouse.move(...at(p0, 0.6, 0.8), { steps: 6 });
await page.mouse.up();
await settle();
c = await chips();
const sel = await page.evaluate(() => window.anytrellisViews[0].selected);
check(c.length === 1 && c[0] === `select: ${sel.selected.toLocaleString("en-US")} of ${sel.total.toLocaleString("en-US")} marks selected`, `a brush: a chip counts it (${c})`);
await page.click(".atr-chip[data-chip='select'] button");
await settle();
check((await page.evaluate(() => window.anytrellisViews[0].brush)) === null && (await chips()).length === 0, "Clear on the chip: the selection gone");
await page.keyboard.press("s");

// ---- help -------------------------------------------------------------------------------
const helpShown = () => page.$eval(".atr-help", (h) => !h.hidden);
check(!(await helpShown()), "the help is hidden at the start");
await page.mouse.click(...at(p0, 0.5, 0.5));
await page.keyboard.press("?");
check(await helpShown(), "?: the keys and mouse");
const text = await page.$eval(".atr-help", (h) => h.innerText);
const desc = await page.evaluate(() => window.anytrellisViews[0].rendererName);
check(text.includes(`Drawn with ${desc}`) && desc.length > 0, `it names the renderer (${desc})`);
check(/anytrellis \d+\.\d+/.test(text), "and the version");
check(text.includes("Page Up") && text.includes("Shift+drag"), "and the keys and mouse");
writeFileSync(join(out, `toolbar-help-${tag}.png`), await page.screenshot());
await page.keyboard.press("Escape");
check(!(await helpShown()), "Esc closes it");
await page.click(".atr-toolbar [aria-label='Keys and mouse']");
check(await helpShown(), "its button opens it");
await page.mouse.click(5, 790);
check(!(await helpShown()), "a click outside closes it");
check(!(await page.$(".atr-badge")), "no renderer badge in the corner");

// the toolbar at rest: icons in the muted colour, fully opaque
const rest = await page.$eval(".atr-toolbar", (t) => getComputedStyle(t).opacity);
check(rest === "1", `the toolbar is fully opaque at rest (${rest})`);

check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
await browser.close();
console.log(failures.length ? `${failures.length} failed` : "all passed");
process.exit(failures.length ? 1 : 0);
