// Exporting images on a save_html page: the Export menu (e) and its items, a PNG download at
// twice the plot's size, an SVG download that is valid and holds the plot's text and marks,
// copying a PNG and an SVG to the clipboard, the selection and an opened panel in the image,
// and the dark theme; with ?renderer= each backend.
//   node test/export.mjs <page.html> [dir for the images] [renderer]
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const file = resolve(process.argv[2]);
const out = resolve(process.argv[3] ?? ".");
const renderer = process.argv[4] ?? "";
mkdirSync(out, { recursive: true });
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

/** A page of the plot, in a light or dark colour scheme. */
async function open(scheme = "light") {
  const context = await browser.newContext({ viewport: { width: 1000, height: 800 }, acceptDownloads: true, colorScheme: scheme });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`file://${file}${renderer ? `?renderer=${renderer}` : ""}`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']");
  return { page, errors };
}

const menuOpen = (page) => page.$eval(".atr-export", (m) => !m.hidden);
const items = (page) => page.$$eval(".atr-export-item", (b) => b.map((x) => x.dataset.export));

/** Choose an item of the Export menu (opened by its button); a download's file, if any. */
async function choose(page, how, name) {
  await page.click(".atr-toolbar button[aria-haspopup='menu']");
  const downloading = how === "png" || how === "svg" ? page.waitForEvent("download") : null;
  await page.click(`.atr-export-item[data-export='${how}']`);
  if (!downloading) return null;
  const d = await downloading;
  const path = join(out, `export-${tag}-${name}.${how}`);
  await d.saveAs(path);
  return { path, name: d.suggestedFilename() };
}

/** A PNG's width and height, from its header. */
function pngSize(path) {
  const b = readFileSync(path);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}

/** What an SVG holds, parsed in the page: valid or not, its size, texts, paths, background. */
const svgFacts = (page, text) =>
  page.evaluate((t) => {
    const doc = new DOMParser().parseFromString(t, "image/svg+xml");
    const svg = doc.documentElement;
    return {
      valid: !doc.querySelector("parsererror") && svg.tagName === "svg",
      width: Number(svg.getAttribute("width")),
      height: Number(svg.getAttribute("height")),
      texts: Array.from(doc.querySelectorAll("text"), (e) => e.textContent),
      paths: doc.querySelectorAll("path").length,
      background: doc.querySelector("svg > rect")?.getAttribute("fill"),
    };
  }, text);

{
  const { page, errors } = await open();
  const size = await page.$eval(".atr-root", (r) => [Math.round(r.getBoundingClientRect().width), Math.round(r.getBoundingClientRect().height)]);
  const title = await page.$$eval(".atr-title", (e) => e[0]?.textContent ?? "");
  const legend = await page.$$eval(".atr-legend-item", (e) => e.map((x) => x.textContent));

  // the menu: e opens it, Esc and a click outside close it
  await page.locator(".atr-stage").click({ position: { x: 300, y: 200 } });
  await page.keyboard.press("e");
  check(await menuOpen(page), "e opens the Export menu");
  const offered = await items(page);
  check(["copy", "copy-svg", "png", "svg"].every((h) => offered.includes(h)), `it offers copying and downloading (${offered.join(", ")})`);
  check(!offered.includes("save-png"), "a page without Python offers no saving next to a notebook");
  await page.keyboard.press("Escape");
  check(!(await menuOpen(page)), "Esc closes it");
  await page.click(".atr-toolbar button[aria-haspopup='menu']");
  await page.mouse.click(5, 790);
  check(!(await menuOpen(page)), "a click outside closes it");

  // PNG: twice the plot's size
  const png = await choose(page, "png", "plain");
  const [pw, ph] = pngSize(png.path);
  check(pw === size[0] * 2 && ph === size[1] * 2, `a PNG twice the plot's size (${pw} × ${ph} for ${size.join(" × ")})`);
  const stem = title ? title.replace(/[^\w.-]+/g, "-").slice(0, 10) : "anytrellis";
  check(png.name.endsWith(".png") && png.name.startsWith(stem), `named after the title, or anytrellis (${png.name})`);

  // SVG: valid, the plot's size, its title, legend and tick labels as text, its marks as paths
  const svgFile = await choose(page, "svg", "plain");
  const svg = readFileSync(svgFile.path, "utf8");
  const facts = await svgFacts(page, svg);
  check(facts.valid, "the SVG is valid XML");
  check(facts.width === size[0] && facts.height === size[1], `the SVG has the plot's size (${facts.width} × ${facts.height})`);
  check(!title || facts.texts.includes(title), "the title is in it as text");
  check(legend.every((l) => facts.texts.includes(l)), `the legend's entries are in it (${legend.length})`);
  const panels = await page.$$eval(".anytrellis-embed", () => window.anytrellisViews[0].lay.panels.length);
  check(facts.paths > panels * 2, `marks, axes and strips are paths (${facts.paths})`);
  check(!/rgba\(|#[0-9a-f]{8}"/i.test(svg), "no rgba() or 8-digit colours (not every SVG reader takes them)");
  check(!/[Ss]elect|[Rr]eset|[Ff]ull screen/.test(facts.texts.join(" ")), "no toolbar in it");

  // the clipboard: a PNG, and an SVG with a PNG beside it (a browser without a clipboard,
  // as some headless ones: said, and skipped)
  const clipboard = () => page.evaluate(async () => (await navigator.clipboard.read()).flatMap((i) => i.types)).catch((err) => String(err));
  await choose(page, "copy", "");
  await page.waitForTimeout(300);
  let types = await clipboard();
  if (typeof types === "string") console.log(`skip the clipboard: ${types}`);
  else {
    check(types.includes("image/png"), `Copy image puts a PNG on the clipboard (${types.join(", ")})`);
    const notice = await page.$eval(".atr-notice", (n) => n.textContent);
    check(/Copied/.test(notice), `the plot says it was copied ("${notice}")`);
    if (offered.includes("copy-svg")) {
      await choose(page, "copy-svg", "");
      await page.waitForTimeout(300);
      types = await clipboard();
      check(Array.isArray(types) && types.includes("image/svg+xml") && types.includes("image/png"), `Copy as vector puts an SVG and a PNG on it (${types})`);
    }
  }

  // a selection is in the image: the other marks faded
  await page.evaluate(() => {
    const v = window.anytrellisViews[0];
    const p = v.spec.panels[0];
    v.setSelection({ x: [p.x[0], (p.x[0] + p.x[1]) / 2], y: null, panel: null, legend: null });
  });
  await page.waitForTimeout(300);
  const selected = readFileSync((await choose(page, "svg", "selected")).path, "utf8");
  const opacities = (t) => new Set(t.match(/stroke-opacity="[\d.]+"/g) ?? []).size;
  check(opacities(selected) > opacities(svg), `the selection is in it: faded marks (${opacities(svg)} → ${opacities(selected)} opacities)`);

  // an opened panel: its name in the file name and the image
  const name = await page.evaluate(() => {
    const v = window.anytrellisViews[0];
    v.setSelection(null);
    const n = v.spec.panels[1].keys.join(" · ");
    v.setFocusName(n);
    return n;
  });
  await page.waitForTimeout(400);
  const one = await choose(page, "svg", "opened");
  const oneFacts = await svgFacts(page, readFileSync(one.path, "utf8"));
  check(one.name.includes(name.replace(/[^\w.-]+/g, "-")), `an opened panel's name is in the file name (${one.name})`);
  check(oneFacts.texts.includes(name), "and in the image");
  check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
  await page.context().close();
}

{
  // the dark theme: the image's background and text are the plot's
  const { page, errors } = await open("dark");
  const bg = await page.$eval(".atr-root", (r) => getComputedStyle(r).getPropertyValue("--atr-bg").trim());
  const facts = await svgFacts(page, readFileSync((await choose(page, "svg", "dark")).path, "utf8"));
  check(bg === "#12171d" && facts.background === bg, `dark: the SVG's background is the plot's (${facts.background})`);
  const png = await choose(page, "png", "dark");
  const corner = await page.evaluate(async (data) => {
    const img = await createImageBitmap(await (await fetch(`data:image/png;base64,${data}`)).blob());
    const c = new OffscreenCanvas(img.width, img.height).getContext("2d");
    c.drawImage(img, 0, 0);
    return Array.from(c.getImageData(2, img.height - 3, 1, 1).data);
  }, readFileSync(png.path).toString("base64"));
  check(corner[0] < 40 && corner[1] < 40 && corner[2] < 50, `dark: the PNG's background is dark (${corner.join(",")})`);
  check(errors.length === 0, `no page errors (dark)${errors.length ? `: ${errors.join("; ")}` : ""}`);
}

await browser.close();
if (failures.length) {
  console.error(`${failures.length} failed`);
  process.exit(1);
}
