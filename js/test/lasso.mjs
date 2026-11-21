// Lasso and click selection on save_html pages: a lasso drawn selects the marks inside it (in
// every panel, as a brush does), moves when dragged and clears on Esc; a click selects the
// mark under it, Shift+click adds or takes one away, a click on no mark clears; with
// link=, a click follows the mark's key into every panel; and a lasso or a click made in
// Python selects as many marks as Python selects rows (<name>.selected.json).
//   node test/lasso.mjs <pages dir> [screenshot dir] [renderer]
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
  await page.waitForTimeout(200);
};
const state = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    return { brush: v.brush, sel: v.selected, mode: v.mode, lassos: v.front_.lassos.length, brushes: v.front_.brushes.length };
  });
/** The page coordinates of panel `i`'s point at fractions (fx, fy) of its box. */
const at = async (i, fx, fy) => {
  const b = await page.evaluate((i) => {
    const v = window.anytrellisViews[0];
    const r = v.stage.getBoundingClientRect();
    const w = v.views[i];
    return { x: r.left + w.rect.x, y: r.top + w.rect.y, w: w.rect.w, h: w.rect.h };
  }, i);
  return [b.x + b.w * fx, b.y + b.h * fy];
};
/** The marks (of the first layer) inside the brush's lasso, in any panel, counted here. */
const inside = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const poly = v.brush.lasso;
    const test = (x, y) => {
      let c = false;
      for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [xi, yi] = poly[i];
        const [xj, yj] = poly[j];
        if (yi !== yj && yi > y !== yj > y && x < ((y - yi) * (xj - xi)) / (yj - yi) + xi) c = !c;
      }
      return c;
    };
    const l = v.scene.layers[0];
    let n = 0;
    for (let i = 0; i < l.set.count; i++) n += test(l.coords[i * 4], l.coords[i * 4 + 1]) ? 1 : 0;
    return n;
  });

// ---- a lasso drawn -------------------------------------------------------------------------
await open("years.html");
await page.click(".atr-stage", { position: { x: 5, y: 5 } }); // the keys to the plot
await page.keyboard.press("l");
let s = await state();
check(s.mode === "lasso", "l: the lasso");
const ring = [];
for (let k = 0; k <= 40; k++) {
  const t = (k / 40) * Math.PI * 2;
  ring.push(await at(0, 0.45 + 0.3 * Math.cos(t), 0.5 + 0.35 * Math.sin(t)));
}
await page.mouse.move(...ring[0]);
await page.mouse.down();
for (const p of ring.slice(1)) await page.mouse.move(...p);
await page.mouse.up();
await page.waitForTimeout(150);
s = await state();
check(s.brush?.lasso?.length >= 3 && s.brush.lasso.length <= 64, `a lasso of ${s.brush?.lasso?.length} corners`);
check(s.lassos > 1 && s.brushes === 0, `drawn in every panel as its outline (${s.lassos}), not as a box`);
const want = await inside();
check(s.sel?.selected === want && want > 0, `the marks inside it selected (${s.sel?.selected} of ${want})`);
await page.mouse.move(5, 5);
await page.screenshot({ path: join(out, `lasso-${tag}.png`) });
// dragged from inside: it moves
const before = s.brush.lasso[0];
const mid = await at(0, 0.45, 0.5);
await page.mouse.move(...mid);
await page.mouse.down();
await page.mouse.move(mid[0] + 30, mid[1], { steps: 5 });
await page.mouse.up();
await page.waitForTimeout(150);
s = await state();
check(s.brush?.lasso && s.brush.lasso[0][0] > before[0] && Math.abs(s.brush.lasso[0][1] - before[1]) < 1e-6, "dragged from inside, it moves");
check(s.sel?.selected === (await inside()), "and selects what is inside it there");
await page.keyboard.press("Escape");
s = await state();
check(s.brush === null, "Esc clears it");

// ---- clicks ---------------------------------------------------------------------------------
await page.keyboard.press("s");
/** Page coordinates of the k-th mark of panel 0 alone at its place (no other within 12 px). */
const mark = (k) =>
  page.evaluate((k) => {
    const v = window.anytrellisViews[0];
    const w = v.views[0];
    const l = v.scene.layers[0];
    const r = v.stage.getBoundingClientRect();
    const px = (i) => [w.map.ox + l.coords[i * 4] * w.map.sx, w.map.oy + l.coords[i * 4 + 1] * w.map.sy];
    const lone = [];
    for (let i = l.starts[w.panel]; i < l.starts[w.panel + 1]; i++) {
      const [x, y] = px(i);
      let alone = true;
      for (let j = l.starts[w.panel]; j < l.starts[w.panel + 1] && alone; j++) if (j !== i && Math.hypot(px(j)[0] - x, px(j)[1] - y) < 12) alone = false;
      if (alone) lone.push([r.left + x, r.top + y]);
    }
    return lone[k] ?? null;
  }, k);
const a = await mark(0);
const b = await mark(1);
await page.mouse.click(...a);
await page.waitForTimeout(100);
s = await state();
check(s.brush?.at?.length === 1 && s.sel?.selected === 1, `a click selects the mark under it (${s.sel?.selected})`);
await page.keyboard.down("Shift");
await page.mouse.click(...b);
await page.keyboard.up("Shift");
await page.waitForTimeout(100);
s = await state();
check(s.brush?.at?.length === 2 && s.sel?.selected === 2, `Shift+click adds one (${s.sel?.selected})`);
await page.keyboard.down("Shift");
await page.mouse.click(...a);
await page.keyboard.up("Shift");
await page.waitForTimeout(100);
s = await state();
check(s.brush?.at?.length === 1 && s.sel?.selected === 1, "Shift+click on one selected takes it away");
await page.screenshot({ path: join(out, `clicked-${tag}.png`) });
await page.keyboard.press("Escape");

// ---- with link=: a click follows the mark's key ----------------------------------------------
await open("gap-link.html");
await page.click(".atr-stage", { position: { x: 5, y: 5 } });
await page.keyboard.press("s");
await page.mouse.click(...(await mark(0)));
await page.waitForTimeout(100);
const followed = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const l = v.scene.layers[0];
  const m = v.selection.masks[0];
  const keys = new Set();
  const panels = new Set();
  for (let p = 0; p < l.starts.length - 1; p++) for (let i = l.starts[p]; i < l.starts[p + 1]; i++) if (m[i]) [keys.add(l.link[i]), panels.add(p)];
  return { keys: keys.size, panels: panels.size, of: v.spec.panels.length };
});
check(followed.keys === 1 && followed.panels > 5, `linked: one country selected, in ${followed.panels} of ${followed.of} panels`);

// ---- made in Python: as many marks as Python's rows -------------------------------------------
for (const name of ["lasso", "clicked"]) {
  await open(`${name}.html`);
  s = await state();
  const rows = JSON.parse(readFileSync(join(dir, `${name}.selected.json`), "utf8"));
  check(s.sel?.selected === rows && rows > 0, `${name} from Python: ${s.sel?.selected} marks, Python ${rows} rows`);
}
check(s.lassos === 0 && s.brushes === 0, "marks clicked: no outline drawn");

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
