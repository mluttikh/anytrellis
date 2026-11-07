// A page of many plots, as the documentation makes them: a plot starts only when it comes near
// the screen (each holds a GPU context, and browsers keep only so many), and every plot is
// drawn once scrolled to:
//   node test/many.mjs <many.html> [screenshot dir] [renderer]
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const file = resolve(process.argv[2]);
const out = resolve(process.argv[3] ?? ".");
const renderer = process.argv[4] ?? "auto";
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
await page.goto(`file://${file}?renderer=${renderer}`);
await page.waitForSelector(".anytrellis-embed[data-state='ready']");
await page.waitForTimeout(300);
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures.push(what);
};
const states = () => page.$$eval(".anytrellis-embed", (els) => els.map((e) => e.dataset.state ?? "waiting"));

let s = await states();
const started = s.filter((x) => x !== "waiting").length;
check(s.length === 20, `the page has 20 plots (${s.length})`);
check(started >= 1 && started <= 4, `only the plots near the screen start (${started} of ${s.length})`);

// scroll to the end: each plot starts as it comes near, and draws
for (let y = 0; y < 30; y++) {
  await page.mouse.wheel(0, 700);
  await page.waitForTimeout(150);
}
await page.waitForTimeout(800);
s = await states();
check(s.every((x) => x === "ready"), `every plot is drawn once scrolled to (${s.filter((x) => x === "ready").length} ready)`);
const last = page.locator(".anytrellis-embed").last();
const shot = await last.screenshot({ path: join(out, `many-last-${renderer}.png`) });
check(shot.length > 5000, "the last plot has a picture");
check(errors.length === 0, `no page errors ${errors.join("; ")}`);
await browser.close();
process.exit(failures.length ? 1 : 0);
