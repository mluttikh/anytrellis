// The settings panel in a saved page: no Python to change the plot, so it says so and
// offers "Copy as Python" (the code the plot was saved with), opened by its toolbar button
// or `,`, closed by Esc; controls=False leaves it out. (Its changes, which need Python, are
// checked in tests/test_settings.py and in a live notebook.)
//   node test/settings.mjs <pages dir> [screenshot dir] [renderer]
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
const context = await browser.newContext({ viewport: { width: 1000, height: 800 } });
await context.grantPermissions(["clipboard-read", "clipboard-write"]);
const page = await context.newPage();
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

await open("years.html");
const button = page.locator(".atr-button[aria-label^='Settings']");
check(await button.count() === 1 && !(await button.evaluate((b) => b.hidden)), "a saved page has the settings button");
await page.click(".atr-stage");
await page.keyboard.press(",");
const panel = await page.evaluate(() => {
  const p = document.querySelector(".atr-settings");
  return { open: !p.hidden, selects: p.querySelectorAll("select").length, note: p.querySelector(".atr-settings-note")?.textContent ?? "", code: p.querySelector(".atr-code")?.textContent ?? "", expanded: document.querySelector(".atr-button[aria-label^='Settings']").getAttribute("aria-expanded") };
});
check(panel.open && panel.expanded === "true", ", opens the panel");
check(panel.selects === 0 && panel.note.includes("notebook"), "without Python: no controls, a note why");
check(panel.code.startsWith("(\n    Trellis(data, wrap=\"year\", cols=4, panel_height=150"), `it shows the plot's Python (${JSON.stringify(panel.code.slice(0, 60))}…)`);
await page.screenshot({ path: join(out, `settings-${tag}.png`) });
await page.click(".atr-settings-copy");
await page.waitForTimeout(200);
const copied = await page.evaluate(() => navigator.clipboard.readText().catch(() => ""));
check(copied === panel.code, "Copy as Python puts it on the clipboard");
const notice = await page.evaluate(() => window.anytrellisViews[0].notice.textContent);
check(notice.includes("Copied"), `and says so (${notice})`);
await page.keyboard.press("Escape");
check(await page.evaluate(() => document.querySelector(".atr-settings").hidden), "Esc closes it");
await page.click(".atr-button[aria-label^='Settings']");
await page.click(".atr-stage", { position: { x: 30, y: 300 } });
check(await page.evaluate(() => document.querySelector(".atr-settings").hidden), "a click outside closes it");

await open("nocontrols.html");
check(await page.evaluate(() => document.querySelector(".atr-button[aria-label^='Settings']").hidden), "controls=False: no settings button");
await page.click(".atr-stage");
await page.keyboard.press(",");
check(await page.evaluate(() => document.querySelector(".atr-settings").hidden), "and , opens nothing");

check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join("; ")}` : ""}`);
await browser.close();
if (failures.length) process.exit(1);
