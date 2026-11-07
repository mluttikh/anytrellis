// Pictures of save_html pages for the documentation (scripts/docs_gallery.py writes the
// pages and the manifest):
//   node scripts/shots.mjs <manifest.json>
// The manifest lists {page, out, width, height, scale?, labels?}. A label puts a numbered badge on a
// part of the plot: "title", "toolbar", "legend", "badge" (the renderer), or "strip:i",
// "panel:i", "yaxis:i", "xaxis:i" for the i-th panel's.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { chromium } from "@playwright/test";

function executable() {
  if (process.env.CHROMIUM) return process.env.CHROMIUM;
  if (existsSync(chromium.executablePath())) return undefined;
  const cache = join(homedir(), "Library/Caches/ms-playwright");
  if (!existsSync(cache)) return undefined;
  for (const d of readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse()) {
    const app = join(cache, d, "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
    if (existsSync(app)) return app;
  }
}

const shots = JSON.parse(readFileSync(process.argv[2], "utf8"));
const args = process.platform === "darwin" ? ["--use-angle=metal"] : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"];
const browser = await chromium.launch({ executablePath: executable(), args });
let failed = 0;
for (const shot of shots) {
  const page = await browser.newPage({ viewport: { width: shot.width, height: shot.height }, deviceScaleFactor: shot.scale ?? 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  // Canvas 2D: the same picture on every machine, GPU or not
  await page.goto(`file://${shot.page}?renderer=canvas2d`);
  await page.waitForSelector(".anytrellis-embed[data-state='ready']", { timeout: 30000 });
  await page.waitForTimeout(300);
  if (shot.labels?.length) {
    await page.evaluate((labels) => {
      const root = document.querySelector(".atr-root");
      const box = root.getBoundingClientRect();
      const stage = root.querySelector(".atr-stage").getBoundingClientRect();
      const lay = window.anytrellisViews[0].lay;
      // each badge beside its part, not on it
      const at = (target) => {
        const [kind, i] = target.split(":");
        const p = lay.panels[Number(i ?? 0)];
        const [sx, sy] = [stage.left, stage.top];
        if (kind === "strip") return [sx + p.strip.x + 16, sy + p.strip.y + p.strip.h / 2];
        if (kind === "panel") return [sx + p.rect.x + p.rect.w * 0.8, sy + p.rect.y + p.rect.h * 0.25];
        if (kind === "yaxis") return [sx + p.yAxis.x - 12, sy + p.yAxis.y + p.yAxis.h * 0.2];
        if (kind === "xaxis") return [sx + p.xAxis.x + p.xAxis.w * 0.5, sy + p.xAxis.y + p.xAxis.h + 8];
        const sel = { title: ".atr-title", toolbar: ".atr-toolbar", legend: ".atr-legend", badge: ".atr-badge" }[kind];
        const el = root.querySelector(sel);
        if (kind === "badge") el.style.opacity = "0.9";
        const r = el.getBoundingClientRect();
        if (kind === "legend") {
          const first = el.firstElementChild?.getBoundingClientRect() ?? r;
          return [first.left - 16, first.top + first.height / 2];
        }
        if (kind === "title") {
          const text = document.createRange();
          text.selectNodeContents(el);
          const t = text.getBoundingClientRect();
          return [t.right + 18, t.top + t.height / 2];
        }
        return [r.left - 16, r.top + r.height / 2];
      };
      for (const { n, target, dx = 0, dy = 0 } of labels) {
        const [x, y] = at(target);
        const b = document.createElement("div");
        b.textContent = String(n);
        Object.assign(b.style, {
          position: "absolute", left: `${x + dx - box.left - 11}px`, top: `${y + dy - box.top - 11}px`,
          width: "22px", height: "22px", borderRadius: "11px", background: "#d6336c", color: "#fff",
          font: "600 12px/22px system-ui, sans-serif", textAlign: "center", zIndex: 10,
          boxShadow: "0 0 0 2px #fff",
        });
        root.append(b);
      }
    }, shot.labels);
  }
  await page.locator(".atr-root").screenshot({ path: shot.out });
  if (errors.length) {
    failed++;
    console.error(`${shot.page}: ${errors.join("; ")}`);
  }
  await page.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
