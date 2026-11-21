// Panels moving to their places on save_html pages: a sort slides each panel from where it
// was to where it goes, in about 250 ms (motion.ts), a frame at a time and ending exactly on
// the layout; a panel opened grows from its place in the grid, and back; a page of all-new
// panels is a cut; a reader asking for reduced motion sees every change at once.
//   node test/motion.mjs <pages dir> [screenshot dir] [renderer]
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
const page = await browser.newPage({ viewport: { width: 1000, height: 800 } });
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
  await page.waitForTimeout(300);
};
// each frame until a move begun has stopped (a slow machine: up to `ms`): whether the
// panels move, and panel `index`'s rect as drawn (`also`: another panel's, as `other`)
const watch = (index, ms = 2000, also = -1) =>
  page.evaluate(
    ([index, ms, also]) =>
      new Promise((done) => {
        const v = window.anytrellisViews[0];
        const t0 = performance.now();
        const frames = [];
        const frame = () => {
          const w = v.views.find((x) => x.panel === index);
          const o = v.views.find((x) => x.panel === also);
          frames.push({ t: performance.now() - t0, moving: !!v.motion, rect: w && { ...w.rect }, other: o && { ...o.rect } });
          const stopped = frames.some((f) => f.moving) && !frames.at(-1).moving;
          if (performance.now() - t0 < ms && !stopped) requestAnimationFrame(frame);
          else done(frames);
        };
        frame();
      }),
    [index, ms, also],
  );
const laidOut = (index) => page.evaluate((i) => window.anytrellisViews[0].lay.panels.find((b) => b.index === i)?.rect ?? null, index);
const same = (a, b) => a && b && ["x", "y", "w", "h"].every((k) => Math.abs(a[k] - b[k]) < 0.01);
const between = (r, a, b) => ["x", "y", "w", "h"].some((k) => a[k] !== b[k]) && ["x", "y", "w", "h"].every((k) => r[k] >= Math.min(a[k], b[k]) - 0.01 && r[k] <= Math.max(a[k], b[k]) + 0.01);

// ---- a sort --------------------------------------------------------------------------------
await open("paged.html");
const first = await page.evaluate(() => window.anytrellisViews[0].lay.panels[0]);
const watching = watch(first.index);
await page.selectOption(".atr-pager .atr-select", "trend temp");
let frames = await watching;
let end = await laidOut(first.index);
let moving = frames.filter((f) => f.moving && f.rect);
check(end !== null && !same(end, first.rect), `sorted: the first panel goes elsewhere on the page (${JSON.stringify(end)})`);
check(moving.length >= 3, `it moves over several frames (${moving.length})`);
check(moving.some((f) => between(f.rect, first.rect, end) && !same(f.rect, first.rect) && !same(f.rect, end)), "between where it was and where it goes");
const began = frames.findIndex((f) => f.moving);
const stopped = frames.findIndex((f, i) => i > began && !f.moving);
const took = began >= 0 && stopped > 0 ? frames[stopped].t - frames[began].t : -1;
check(took > 200 && took < 400 && same(frames.at(-1).rect, end), `and stops in its place in about 250 ms (${Math.round(took)} ms)`);
await page.screenshot({ path: join(out, `motion-${tag}-sorted.png`) });

// a page of all-new panels (none pinned): at once
const one = await page.evaluate(() => window.anytrellisViews[0].lay.panels[0].index);
const turning = watch(one, 200);
await page.click(".atr-pager .atr-button[aria-label='Next page']");
frames = await turning;
check(!frames.some((f) => f.moving), "the next page: a cut, no panel in both");

// ---- a panel opened, and back ----------------------------------------------------------------
await open("keys.html");
const grid = await page.evaluate(() => window.anytrellisViews[0].lay.panels.map((b) => ({ index: b.index, rect: b.rect })));
await page.focus(".atr-root");
await page.keyboard.press("ArrowRight");
const opening = watch(grid[0].index);
await page.keyboard.press("Enter");
frames = await opening;
end = await laidOut(grid[0].index);
moving = frames.filter((f) => f.moving && f.rect);
const widths = moving.map((f) => f.rect.w);
check(moving.length >= 3 && widths.every((w, i) => i === 0 || w >= widths[i - 1] - 0.01), `opened: it grows from its place in the grid (${Math.round(widths[0])} → ${Math.round(end.w)} px)`);
check(moving.some((f) => between(f.rect, grid[0].rect, end) && !same(f.rect, end) && f.rect.w > grid[0].rect.w + 1), "through the sizes between");
check(same(frames.at(-1).rect, end), "and ends on the layout");
const other = grid[1].index;
const closing = watch(grid[0].index, 2000, other);
await page.keyboard.press("Escape");
frames = await closing;
moving = frames.filter((f) => f.moving && f.rect);
check(moving.length >= 3 && moving[0].rect.w > grid[0].rect.w + 1 && same(frames.at(-1).rect, grid[0].rect), "back to all panels: it shrinks to its place");
const others = moving.map((f) => f.other).filter(Boolean);
const g = grid[1].rect;
check(others.length >= 3 && others[0].w < g.w - 1 && Math.abs(others[0].x + others[0].w / 2 - (g.x + g.w / 2)) < 0.5 && same(frames.at(-1).other, g), `the others grow in about their middles (${Math.round(others[0]?.w)} → ${Math.round(g.w)} px)`);

// ---- reduced motion --------------------------------------------------------------------------
await page.emulateMedia({ reducedMotion: "reduce" });
await open("paged.html");
const still = watch(first.index, 200);
await page.selectOption(".atr-pager .atr-select", "trend temp");
frames = await still;
check(!frames.some((f) => f.moving) && same(frames.at(-1).rect, await laidOut(first.index)), "reduced motion: sorted at once");
await page.focus(".atr-root");
await page.keyboard.press("ArrowRight");
const at = watch(other, 200);
await page.keyboard.press("Enter");
frames = await at;
check(!frames.some((f) => f.moving), "and a panel opened at once");

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
