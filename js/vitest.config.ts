import { defineConfig } from "vitest/config";

// unit tests only; the visual check (test/visual.mjs) runs with Playwright
export default defineConfig({ test: { include: ["test/*.test.ts"] } });
