# 0009: How a change is checked before it is merged

- Status: **implemented**, 7 November 2026 (CI), extended with every feature since.
- Changes: `.github/workflows/ci.yml`, `js/test/` (browser checks), `js/test/pages.py` (the
  pages they run on), `scripts/build_docs.py`, `scripts/check_dist.py`.
- Written after the fact, from CI and the way pull requests have been checked.

## Decision

A pull request runs, and passes, all of these locally before it is opened:

- **Python**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check` (the
  whole project, tests included, as CI does), `uv run pytest`.
- **TypeScript**: `npm run typecheck`, `npx vitest run`, `npm run build` (the bundle in
  `src/anytrellis/static` is what Python ships).
- **The browser checks** in headless Chromium, on pages written by `js/test/pages.py`, in
  WebGL2 and Canvas 2D (WebGPU too, locally). A new interaction gets a check, added to CI
  in the same change.
- **The documentation**: `uv run python scripts/build_docs.py --gallery`. It runs every
  example, fails on warnings, on a page over 3 MB gzipped, and on a public method or
  parameter that no guide uses or the cheat sheet lacks.
- **In a live notebook** (JupyterLab), when a change touches the widget protocol or adds a
  spec buffer (0001): some faults show only there.
- **With a database**: a feature that reads data gets a test with a DuckDB relation and
  `load="pages"` (0004).

And:

- **One branch and one pull request per change**, merged by the maintainer.
- **The changelog** gets an entry under Unreleased for every change a user can see.
- **Commits and pull requests carry no tool attribution.**
- **A test file is checked to be new before it is written**, so an existing one is not
  overwritten.
