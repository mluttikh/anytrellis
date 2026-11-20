// Shapes, sizes and dashes on save_html pages: legends that draw them, a hovered point's
// ring as big as the point, dashes with gaps on screen, and exported SVGs that keep them.
//   node test/channels.mjs <pages dir> [screenshot dir] [renderer]
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
/** The SVG the Export menu downloads. */
async function exportSvg(name) {
  await page.click(".atr-toolbar button[aria-haspopup='menu']");
  const downloading = page.waitForEvent("download");
  await page.click(".atr-export-item[data-export='svg']");
  const d = await downloading;
  const path = join(out, `channels-${tag}-${name}.svg`);
  await d.saveAs(path);
  return readFileSync(path, "utf8");
}

// ---- shapes and sizes ----------------------------------------------------------------------
await open("channels.html");
const legend = await page.evaluate(() => {
  const groups = [...document.querySelectorAll(".atr-legend-group")];
  return groups.map((g) => ({ title: g.querySelector(".atr-legend-title")?.textContent, glyphs: g.querySelectorAll("canvas.atr-glyph").length, items: g.querySelectorAll(".atr-legend-item").length }));
});
check(legend.length === 2 && legend[0].glyphs === 3 && legend[0].items === 3, `one legend for colour and shape, its entries drawn as shapes (${JSON.stringify(legend)})`);
check(legend[1]?.glyphs >= 3 && legend[1].glyphs === legend[1].items, "a size legend of points");
const big = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const layer = v.scene.layers[0];
  const w = v.views[0];
  // the largest point of the first panel, and its radius
  let best = -1;
  for (let i = layer.starts[w.panel]; i < layer.starts[w.panel + 1]; i++) if (best < 0 || layer.radii[i] > layer.radii[best]) best = i;
  const r = v.stage.getBoundingClientRect();
  const c = layer.coords;
  return { kind: layer.kind, r: layer.radii[best], half: layer.halfWidth, x: r.left + w.map.ox + c[best * 4] * w.map.sx, y: r.top + w.map.oy + c[best * 4 + 1] * w.map.sy, small: Math.min(...layer.radii.filter((x) => x > 0)) };
});
check(big.kind === 3, "points of shapes and sizes are drawn as shapes");
check(big.small < big.r && big.r <= big.half + 1e-6, `sizes from ${big.small.toFixed(1)} to ${big.r.toFixed(1)} px`);
await page.mouse.move(big.x, big.y);
await page.waitForTimeout(150);
const ring = await page.evaluate(() => window.anytrellisViews[0].front_.hovers[0]?.r ?? null);
check(ring !== null && Math.abs(ring - Math.max(3, big.r)) < 1e-6, `the hovered point's ring is as big as it (${ring})`);
await page.mouse.move(5, 5);
const shapes = await exportSvg("shapes");
check(shapes.includes("<svg") && (shapes.match(/<path/g) ?? []).length > 10, "the exported SVG draws the points as paths");
await page.screenshot({ path: join(out, `channels-${tag}.png`) });

// ---- dashes --------------------------------------------------------------------------------
await open("dashes.html");
// (a WebGPU canvas can't be read back once shown)
const readable = await page.evaluate(() => window.anytrellisViews[0].renderer.kind !== "webgpu");
const runs = await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const w = v.views[0];
  const marks = v.renderer.canvas;
  const copy = document.createElement("canvas");
  copy.width = marks.width;
  copy.height = marks.height;
  const ctx = copy.getContext("2d");
  ctx.drawImage(marks, 0, 0);
  const row = (y) => {
    const py = Math.round((w.map.oy + y * w.map.sy) * v.dpr);
    const x0 = Math.round((w.map.ox + 5 * w.map.sx) * v.dpr);
    const x1 = Math.round((w.map.ox + 95 * w.map.sx) * v.dpr);
    const d = ctx.getImageData(x0, py, x1 - x0, 1).data;
    let ink = 0;
    let changes = 0;
    let was = null;
    for (let i = 0; i < d.length; i += 4) {
      const on = d[i + 3] > 100;
      ink += on ? 1 : 0;
      if (was !== null && on !== was) changes++;
      was = on;
    }
    return { ink: ink / (d.length / 4), changes };
  };
  return { solid: row(1), dashed: row(2) };
});
if (readable) {
  check(runs.solid.ink > 0.98 && runs.solid.changes === 0, `the first level's line is solid (${JSON.stringify(runs.solid)})`);
  check(runs.dashed.changes > 20 && runs.dashed.ink > 0.3 && runs.dashed.ink < 0.8, `the second's has dashes and gaps (${JSON.stringify(runs.dashed)})`);
}
const glyphs = await page.$$eval("canvas.atr-glyph", (c) => c.length);
check(glyphs === 2, "its legend draws each line's dash");
const dashes = await exportSvg("dashes");
check(dashes.includes('stroke-dasharray="'), "the exported SVG's legend draws the dash");
check((dashes.match(/M/g) ?? []).length > 40, "and its line, a piece a dash");
await page.screenshot({ path: join(out, `channels-dashes-${tag}.png`) });

check(errors.length === 0, `no page errors (${errors.join("; ")})`);
await browser.close();
if (failures.length) process.exit(1);
