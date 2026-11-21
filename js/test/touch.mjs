// Touch: one finger scrolls the page past the plot (with box zoom or select on, it draws),
// two fingers pinch to zoom (side by side: x alone) and pan, a long press pins the values
// there and a tap lets them go. Touches come through Chrome's input pipeline (CDP), so the
// page scrolls as on a phone.
//   node test/touch.mjs <years.html> [screenshot dir] [renderer]
import { existsSync, readdirSync } from "node:fs";
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
// a phone-sized window: the page scrolls past the plot
const context = await browser.newContext({ viewport: { width: 700, height: 500 }, hasTouch: true, isMobile: true });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const tag = renderer || "default";
await page.goto(`file://${file}${renderer ? `?renderer=${renderer}` : ""}`);
await page.waitForSelector(".anytrellis-embed[data-state='ready']");
await page.waitForTimeout(200);
const cdp = await context.newCDPSession(page);
const touch = (type, points) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: points.map(([x, y], id) => ({ x, y, id })) });
/** Fingers moved from `from` to `to` (each [[x, y], ...]) in steps. */
async function gesture(from, to, steps = 10) {
  await touch("touchStart", from);
  for (let k = 1; k <= steps; k++) await touch("touchMove", from.map(([x, y], i) => [x + ((to[i][0] - x) * k) / steps, y + ((to[i][1] - y) * k) / steps]));
  await touch("touchEnd", []);
  await page.waitForTimeout(150);
}
const frame = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
/** The second panel's box in the window, and what it shows. */
const panel = async () => {
  await frame();
  return page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const w = v.views[1];
    const r = v.stage.getBoundingClientRect();
    return { x: r.left + w.rect.x, y: r.top + w.rect.y, w: w.rect.w, h: w.rect.h, xr: [...w.x], yr: [...w.y], scroll: window.scrollY };
  });
};
const width = (r) => r[1] - r[0];

// one finger: the page scrolls, the plot stays
let p = await panel();
await gesture([[p.x + p.w / 2, p.y + p.h / 2]], [[p.x + p.w / 2, p.y + p.h / 2 - 120]]);
await page.waitForTimeout(1200); // the page coasts to a stop
let q = await panel();
check(q.scroll > p.scroll + 50, `one finger scrolls the page (${p.scroll} → ${q.scroll})`);
check(q.xr[0] === p.xr[0] && q.yr[0] === p.yr[0], "and leaves the plot as it was");
const told = await page.evaluate(() => window.anytrellisViews[0].notice.textContent);
check(told.includes("Two fingers"), `it says how to pan and zoom (${told})`);
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(200);

// two fingers side by side, apart: x zoomed in about them, y as it was, the page still
p = await panel();
const cy = p.y + p.h / 2;
await gesture([[p.x + p.w * 0.4, cy], [p.x + p.w * 0.6, cy]], [[p.x + p.w * 0.3, cy], [p.x + p.w * 0.7, cy]]);
q = await panel();
check(Math.abs(width(q.xr) / width(p.xr) - 0.5) < 0.05, `a pinch apart zooms x in (×${(width(p.xr) / width(q.xr)).toFixed(2)})`);
check(Math.abs(width(q.yr) - width(p.yr)) < 1e-9, "fingers side by side: y as it was");
check(Math.abs((q.xr[0] + q.xr[1]) / 2 - (p.xr[0] + p.xr[1]) / 2) < width(p.xr) * 0.02, "about the fingers' midpoint");
check(q.scroll === p.scroll, "the page does not scroll under two fingers");

// one above the other, together: y zoomed out, x as it was
p = q;
const cx = p.x + p.w / 2;
await gesture([[cx, p.y + p.h * 0.2], [cx, p.y + p.h * 0.8]], [[cx, p.y + p.h * 0.35], [cx, p.y + p.h * 0.65]]);
q = await panel();
check(Math.abs(width(q.yr) / width(p.yr) - 2) < 0.1 && Math.abs(width(q.xr) - width(p.xr)) < 1e-9, `a pinch together, one finger above the other, zooms y out (×${(width(q.yr) / width(p.yr)).toFixed(2)})`);
await page.keyboard.press("u");

// two fingers moved together: a pan
p = q;
await gesture([[p.x + p.w * 0.4, cy - 20], [p.x + p.w * 0.6, cy + 20]], [[p.x + p.w * 0.2, cy - 20], [p.x + p.w * 0.4, cy + 20]]);
q = await panel();
check(Math.abs(width(q.xr) - width(p.xr)) < width(p.xr) * 0.01 && q.xr[0] > p.xr[0] + width(p.xr) * 0.15, `two fingers moved left pan right (${p.xr[0].toFixed(2)} → ${q.xr[0].toFixed(2)})`);
await page.keyboard.press("u");
await page.keyboard.press("u");
q = await panel();
check(Math.abs(width(q.xr) - width(p.xr) * 2) < width(p.xr) * 0.05, "u undoes a pinch, as a zoom");

// a long press on a point: its values, pinned; a tap lets them go
const point = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const layer = v.scene.layers[0];
  const w = v.views[1];
  const i = layer.starts[w.panel] + 3;
  const r = v.stage.getBoundingClientRect();
  return { x: r.left + w.map.ox + layer.coords[i * 4] * w.map.sx, y: r.top + w.map.oy + layer.coords[i * 4 + 1] * w.map.sy };
});
await touch("touchStart", [[point.x, point.y]]);
await page.waitForTimeout(700);
await touch("touchEnd", []);
await page.waitForTimeout(150);
let pinned = await page.evaluate(() => !!window.anytrellisViews[0].pinned);
check(pinned, "a long press pins the values there");
await page.screenshot({ path: join(out, `touch-${tag}-press.png`) });
await touch("touchStart", [[point.x + 60, point.y + 30]]);
await touch("touchEnd", []);
await page.waitForTimeout(150);
pinned = await page.evaluate(() => !!window.anytrellisViews[0].pinned);
check(!pinned, "a tap lets them go");

// select on: one finger draws a brush, the page stays
await page.evaluate(() => window.anytrellisViews[0].setMode("select"));
p = await panel();
await gesture([[p.x + 20, p.y + 20]], [[p.x + p.w / 2, p.y + p.h / 2]]);
q = await panel();
const brush = await page.evaluate(() => window.anytrellisViews[0].brush);
check(brush !== null && q.scroll === p.scroll, `with select on, one finger brushes (${JSON.stringify(brush?.x)})`);

check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
await browser.close();
if (failures.length) process.exit(1);
