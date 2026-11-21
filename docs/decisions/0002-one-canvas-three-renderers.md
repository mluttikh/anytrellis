# 0002: One canvas of viewports, three renderers, and 2D canvases around it

- Status: **implemented**, 6 November 2026 (0.1).
- Changes: `js/src/core/renderers/` (WebGPU, WebGL2, Canvas 2D), `js/src/core/view.ts`
  (`markDraws`, the back and front canvases), `js/src/core/drawing.ts`,
  `js/src/core/layout.ts`; `docs/user/explanation/drawing.md` explains it to users.
- Written after the fact, from the code and the pull requests.

## Decision

- **All panels draw into one canvas**, each a viewport with its own transform from data to
  pixels. Marks are uploaded once as instances (a point, a segment, a bar); a zoom or pan
  changes a few numbers per panel and redraws. Nothing is sent again or recomputed in
  Python.
- **Three renderers, tried in order**: WebGPU, then WebGL2, then Canvas 2D, which always
  works. `renderer=` (and `?renderer=` in a page's URL) picks one. A lost GPU context falls
  back to Canvas 2D, and the plot keeps working. Every feature works in all three; a mark
  or effect added to one is added to the others in the same change.
- **Two 2D canvases surround the marks**: behind them the panels' backgrounds, grid and
  axes; in front the strips, labels, brush, crosshair, pins, focus ring and highlights.
  These hold a few hundred shapes, which Canvas 2D draws fast, and text, which the GPU
  draws badly.
- **The same drawing code paints the exports.** The browser's PNG and SVG come from the
  plot's own paint calls on a canvas or an SVG context (`export.ts`), so an image is the
  plot as shown.
- **A page of many plots starts each one only when it comes near the screen**, so the
  browser's limit on GPU contexts (16 in Chrome) is spent only on plots a reader reaches.

## Known limits

- Canvas 2D is slow beyond a few hundred thousand marks; the level of detail (0004) keeps
  what it draws near the pixels shown.
- WebGPU is checked headless on macOS only; CI runs WebGL2 and Canvas 2D.
