// Visual check: open save_html pages in Chromium with each backend and screenshot them.
//   node test/visual.mjs <dir with .html files> [out dir]
// Prints, per page and backend, the renderer actually used and any console errors.
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const dir = resolve(process.argv[2] ?? ".");
const out = resolve(process.argv[3] ?? dir);
const pages = readdirSync(dir).filter((f) => f.endsWith(".html")).sort();
const backends = (process.env.BACKENDS ?? "webgpu,webgl2,canvas2d").split(",");

// CHROMIUM=<path> picks the browser; else Playwright's own, else a cached Chrome for Testing
function executable() {
  if (process.env.CHROMIUM) return process.env.CHROMIUM;
  if (existsSync(chromium.executablePath())) return undefined;
  const cache = join(homedir(), "Library/Caches/ms-playwright");
  if (!existsSync(cache)) return undefined;
  for (const d of readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse()) {
    const app = join(cache, d, "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
    if (existsSync(app)) return app;
  }
  return undefined;
}

const browser = await chromium.launch({
  executablePath: executable(),
  headless: true,
  args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan,WebGPU", "--use-angle=metal", "--ignore-gpu-blocklist"],
});
let failures = 0;
for (const backend of backends) {
  const page = await browser.newPage({ viewport: { width: 1000, height: 800 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on("console", (m) => (m.type() === "error" || m.type() === "warning") && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  for (const f of pages) {
    errors.length = 0;
    await page.goto(`file://${join(dir, f)}?renderer=${backend}`);
    await page.waitForSelector(".anytrellis-embed[data-state='ready'], .anytrellis-embed[data-state='error']", { timeout: 20000 });
    const state = await page.$eval(".anytrellis-embed", (e) => [e.dataset.state, e.dataset.renderer]);
    const shot = join(out, `${f.replace(".html", "")}-${backend}.png`);
    await page.screenshot({ path: shot, fullPage: true });
    const ok = state[0] === "ready" && state[1] === backend && errors.length === 0;
    if (!ok) failures++;
    console.log(`${ok ? "ok  " : "FAIL"} ${f} ${backend}: ${state.join(" ")}${errors.length ? ` | ${errors.join(" | ")}` : ""}`);
  }
  await page.close();
}
await browser.close();
process.exit(failures ? 1 : 0);
