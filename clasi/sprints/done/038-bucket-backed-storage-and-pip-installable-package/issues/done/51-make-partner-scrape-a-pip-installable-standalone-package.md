---
status: done
sprint: 038
tickets:
- 038-006
- 038-012
- 038-013
---

# Make partner-scrape a pip-installable standalone package

## Description

Goal: `pip install partner-scrape` (or `pipx install partner-scrape`) on
any machine gives a working `partner-scrape` command, with no repo
checkout required.

### Where it stands (assessed 2026-10-02)

Already in place:

- `pyproject.toml` has a complete `[project]` table, a hatchling build
  backend, the `partner-scrape = "partner_scrape.cli:main"` console
  script, and a `headless` extra for Playwright.
- `uv build --wheel` succeeds. The wheel contains `partner_scrape/` along
  with its in-package data (`directory/data/*`, `directory/registry/*`,
  `teams/registry/*`), which are located via `Path(__file__)` and so work
  once installed.
- The `partner-scrape` name is unclaimed on PyPI (404 as of today).
- Nothing in `partner_scrape/` imports the legacy `scraper/` tree.

What breaks when it runs from an installed wheel:

1. **Repo-root data paths.** `partner_scrape/config.py` defines
   `REPO_ROOT = Path(__file__).parent.parent`. After install, that resolves
   to `site-packages/`. These defaults depend on it:
   - `registry/loader.py`: `DEFAULT_SOURCES_DIR = REPO_ROOT/registry/sources`
   - `registry/hub_schema.py`: `DEFAULT_HUBS_DIR = REPO_ROOT/registry/hubs`
   - `registry/candidates.py`: `DEFAULT_CANDIDATES_DIR = REPO_ROOT/registry/candidates`
   - `export/ads.py`: `DEFAULT_ADS_DIR = REPO_ROOT/registry/ads`
   - `config.py`: `DEFAULT_OWN_DATA_DIR = REPO_ROOT/data`, which per its
     comment is "not overridable via environment variable"
   - `config.py`: `DEFAULT_SITE_DIR = REPO_ROOT.parent/stem-ecosystem`
2. **The source registry is outside the package.** The root-level
   `registry/` directory (sources, hubs, candidates, ads) isn't in the
   wheel, so an installed copy has no sources to scrape.
3. **Python floor.** `requires-python = ">=3.13"` rules out many systems'
   default Python. Check whether 3.13 is actually needed.
4. **No release pipeline.** No workflow builds and publishes to PyPI, and
   the date-based version (`0.YYYYMMDD.N`) is bumped by hand.

### Proposed work

- Decide how registry data relates to the code:
  (a) ship `registry/` inside the package as default data (e.g. move it to
  `partner_scrape/registry_data/` or use hatch `force-include`), or
  (b) keep it external and require a `--registry-dir` / `PARTNER_SCRAPE_REGISTRY`
  setting with no default, or
  (c) do both: bundled defaults that a setting can override.
  Option (c) is probably best: the package works out of the box and the
  registry can still be edited without a release.
- Replace every `REPO_ROOT`-relative default with either a package-relative
  path (bundled data) or an env/CLI setting that defaults to the current
  working directory or a user data dir (`platformdirs`). That includes
  making the own-data output dir configurable (`PARTNER_SCRAPE_DATA_DIR`).
- Make `SITE_DIR` required, or default it to the CWD, instead of
  `../stem-ecosystem`.
- Make sure `partner-scrape --help` and a dry run work from a clean venv
  outside the repo, and add a CI smoke test that builds the wheel,
  installs it into a fresh venv in a temp directory, and runs
  `partner-scrape --help` plus one dry-run command.
- Consider dropping the `DESIGN.md` files from the wheel (about 200 KB),
  or keep them on purpose.
- Re-check `requires-python`.
- Add a GitHub Actions publish workflow using PyPI trusted publishing,
  triggered on tag or release. Claim the name on PyPI.
- Update the README with `pip install partner-scrape` / `pipx install
  "partner-scrape[headless]"` instructions, including the
  `playwright install chromium` step for the headless extra.
- Optionally, have the scheduled-run workflow install the published or
  built wheel instead of running `uv sync` from source.

### Acceptance

- From an empty directory, with no repo checkout:
  `pipx install partner-scrape && partner-scrape --help` works, and a
  dry run against the bundled registry produces output given only
  `SCRAPE_CACHE_DIR`.
- No module resolves a default path through `REPO_ROOT`.
- A tagged release publishes to PyPI automatically.
