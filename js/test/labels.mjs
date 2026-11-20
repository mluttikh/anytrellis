// Text by the data on save_html pages: names at the lines' ends (each once, no legend;
// hovering one shows its line, a click selects it; they follow a zoom), text labels kept
// apart (`repel`), notes (`annotate()`), and exported SVGs that keep them.
//   node test/labels.mjs <pages dir> [screenshot dir] [renderer]
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
  const path = join(out, `labels-${tag}-${name}.svg`);
  await d.saveAs(path);
  return readFileSync(path, "utf8");
}
/** The line-end labels, in page coordinates. */
const ends = () =>
  page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const r = v.stage.getBoundingClientRect();
    const at = (e) => v.views.find((w) => w.panel === e.panel);
    return v.front_.ends.map((e) => ({ text: e.text, panel: e.panel, series: e.series, legend: e.legend, x: r.left + e.x + e.w / 2, y: r.top + e.y, ux: (e.ax - at(e).map.ox) / at(e).map.sx, inside: e.ax <= at(e).rect.x + at(e).rect.w + 0.5 }));
  });

// ---- names at the lines' ends --------------------------------------------------------------
await open("ends.html");
const legendShown = await page.evaluate(() => getComputedStyle(document.querySelector(".atr-legend")).display !== "none");
check(!legendShown, "no legend: the names label the lines");
let labels = await ends();
check(labels.length === 4 && labels.every((e) => e.panel === 1), `each name once, in the right panel (${labels.map((e) => `${e.text}@${e.panel}`).join(", ")})`);
const ys = labels.map((e) => e.y).sort((a, b) => a - b);
check(ys.every((y, i) => !i || y - ys[i - 1] >= 12), "the names apart from each other");
const japan = labels.find((e) => e.text === "Japan");
await page.mouse.move(japan.x, japan.y);
await page.waitForTimeout(150);
const preview = await page.evaluate(() => window.anytrellisViews[0].preview);
check(preview?.index === japan.legend && preview.levels[0] === japan.series, `hovering a name shows its line (${JSON.stringify(preview)})`);
await page.mouse.click(japan.x, japan.y);
await page.waitForTimeout(150);
const chosen = await page.evaluate(() => window.anytrellisViews[0].brush?.legend ?? null);
check(chosen?.levels?.length === 1 && chosen.levels[0] === japan.series, `a click selects its line (${JSON.stringify(chosen)})`);
await page.mouse.move(5, 5);
await page.waitForTimeout(100);
const svg = await exportSvg("ends");
check(["Japan", "Brazil", "India", "Nigeria"].every((n) => svg.includes(`>${n}<`)), "the exported SVG keeps the names");
await page.screenshot({ path: join(out, `labels-${tag}-ends.png`) });
// zoomed in on the middle half of x: the names at the last points in view
const before = labels.find((e) => e.text === "India").ux;
await page.evaluate(() => {
  const v = window.anytrellisViews[0];
  const w = v.views[1];
  const p = v.spec.panels[w.panel];
  const q = (w.x[1] - w.x[0]) / 4;
  v.setX(p.xg, [w.x[0] + q, w.x[1] - q]);
  v.request();
});
await page.waitForTimeout(200);
labels = await ends();
const india = labels.find((e) => e.text === "India");
check(labels.length === 4 && india?.ux < before && labels.every((e) => e.inside), `zoomed: the names at the last points in view (x ${before.toFixed(0)} → ${india?.ux.toFixed(0)})`);

// ---- labels kept apart, notes --------------------------------------------------------------
await open("notes.html");
const notes = await exportSvg("notes");
// each text twice: its halo, then itself
check((notes.match(/>Replacement</g) ?? []).length === 12, "a note in every panel");
check((notes.match(/>Long lives</g) ?? []).length === 2, "a note in one panel");
check(notes.includes(">Japan<") && notes.includes(">Haiti<"), "the kept-apart labels in the exported SVG");
await page.screenshot({ path: join(out, `labels-${tag}-notes.png`) });

check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
await browser.close();
if (failures.length) process.exit(1);
