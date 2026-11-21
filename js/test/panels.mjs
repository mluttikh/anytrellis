// Moving between panels: the arrow keys' ring (Enter opens), pinning panels first on every
// page (p, or a panel's pin button), comparing every panel with one (c: its marks in grey
// in the others), and Esc letting each go.
//   node test/panels.mjs <pages dir> [screenshot dir] [renderer]
import { existsSync, readFileSync, readdirSync } from "node:fs";
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
const page = await browser.newPage({ viewport: { width: 1000, height: 800 }, acceptDownloads: true });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const tag = renderer || "default";
const open = async (name) => {
  await page.goto(`file://${join(dir, name)}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  await page.waitForTimeout(200);
};
const state = async () => {
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  return page.evaluate(() => {
    const v = window.anytrellisViews[0];
    return {
      ring: v.ring,
      ringRect: v.front_.ring,
      page: v.pagePanels(),
      pinned: v.paging.pinned ?? [],
      compare: v.compareName,
      focused: v.focused,
      notice: v.notice.hidden ? "" : v.notice.textContent,
      chips: [...v.chips.querySelectorAll(".atr-chip")].map((c) => c.dataset.chip),
      boxes: v.lay.panels.filter((b) => b.pinned).map((b) => b.index),
      ghosts: v.markDraws(v.views).filter((d) => d.set.key.endsWith(":ghost")).length,
      tools: v.tools.hidden ? null : [...v.tools.querySelectorAll("button")].filter((b) => !b.hidden).length,
    };
  });
};
const name = (i) => page.evaluate((i) => {
  const v = window.anytrellisViews[0];
  return v.spec.panels[i] && v.lay.panels.find((b) => b.index === i)?.label;
}, i);

await open("pins.html");
await page.evaluate(() => window.anytrellisViews[0].root.focus());
let s = await state();
const first = s.page;
await page.keyboard.press("ArrowRight");
s = await state();
check(s.ring === first[0] && s.ringRect !== null, `the arrow keys reach the first panel (${s.ring})`);
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowDown");
s = await state();
check(s.ring === first[5], `right, then down: the panel below the second (${s.ring}, want ${first[5]})`);
check(s.notice.includes(await name(first[5])), `its name said (${s.notice})`);
check(s.tools !== null, "its buttons shown");
const target = s.ring;
await page.keyboard.press("p");
s = await state();
check(s.page[0] === target && s.pinned.length === 1, `p pins it: first on the page (${s.page.slice(0, 3)})`);
check(s.boxes.includes(target), "a pin in its strip");
check(s.chips.includes("pin"), "a chip says so");
await page.keyboard.press("PageDown");
s = await state();
check(s.page[0] === target && !first.slice(1).some((i) => s.page.includes(i) && i !== target), `on the next page too, first (${s.page.slice(0, 3)})`);
// compare with the ringed panel (still on the page: pinned)
await page.keyboard.press("c");
s = await state();
check(s.compare !== null && s.ghosts > 0, `c compares every panel with it: its marks in the others (${s.ghosts} draws)`);
check(s.chips.includes("compare"), "a chip says which");
await page.screenshot({ path: join(out, `panels-${tag}-compare.png`) });
const svg = await page.evaluate(() => window.anytrellisViews[0].svgImage?.() ?? "");
if (svg) check(svg.includes("rgb(184,190,198)") || svg.includes("#b8bec6"), "the export draws the compared marks");
await page.keyboard.press("Escape");
s = await state();
check(s.ring === null && s.compare !== null, "Esc lets the ring go first");
await page.keyboard.press("Escape");
s = await state();
check(s.compare === null && s.ghosts === 0, "then the comparison");
// a panel's buttons, under the pointer: pin another
const box = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const b = v.lay.panels[2];
  const r = v.stage.getBoundingClientRect();
  return { index: b.index, x: r.left + b.rect.x + b.rect.w / 2, y: r.top + b.rect.y + b.rect.h / 2 };
});
await page.mouse.move(box.x, box.y);
await page.waitForTimeout(100);
s = await state();
check(s.tools === 3, `hovering a panel shows open, pin and compare (${s.tools})`);
await page.click(".atr-panel-tools button:nth-child(2)");
s = await state();
check(s.pinned.length === 2 && s.page[1] === box.index, `its pin button pins it (${s.page.slice(0, 3)})`);
await page.click(".atr-panel-tools button:nth-child(2)");
s = await state();
check(s.pinned.length === 1, "again: unpinned");
// Enter opens the ringed panel
await page.evaluate(() => window.anytrellisViews[0].root.focus());
await page.keyboard.press("ArrowRight");
const ringed = (await state()).ring;
await page.keyboard.press("Enter");
s = await state();
check(s.focused === ringed, `Enter opens the panel reached (${s.focused})`);
await page.keyboard.press("Escape");
s = await state();
check(s.focused === null, "Esc goes back");

check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
await browser.close();
if (failures.length) process.exit(1);
