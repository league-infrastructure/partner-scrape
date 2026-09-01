---
status: in-progress
sprint: '025'
tickets:
- 025-001
---

# Move registry data (sources/hubs/candidates/ads) to a root-level `registry/` directory

## Description

Stakeholder directive (Eric, 2026-08-31 conversation): `partner_scrape/registry/`
today mixes CODE (`loader.py`, `schema.py`, `hub_schema.py`, `candidates.py`,
`validate_roster.py`, `__init__.py`, `DESIGN.md`, `DO_NOT_SCRAPE.md`) and DATA
(`sources/` — 122 TOML files, `hubs/` — 2 TOML files, `candidates/` — 241 TOML
files, `ads/` — 1 TOML file; 366 data files total) in the same directory tree,
buried inside the Python package.

Eric's stated principle, repeated twice in the same conversation: "well-known
data lives in an easily discoverable root-level place, code lives in the
package." `data/` (this repo's own pipeline-output directory, sprint 020) is
the existing precedent for a root-level, easily-discoverable data directory.

## Requested change

Move the four TOML-bearing directories (`sources/`, `hubs/`, `candidates/`,
`ads/`) from `partner_scrape/registry/` to a new root-level `registry/`
directory (`<repo_root>/registry/sources/`, `.../hubs/`, `.../candidates/`,
`.../ads/`), sibling to `data/` and `partner_scrape/`. The Python code that
reads and writes this data (`loader.py`, `hub_schema.py`, `candidates.py`,
`export/ads.py`) stays in `partner_scrape/registry/` (and `partner_scrape/
export/`) — it's code, not data — but each module's default-path constant
(`DEFAULT_SOURCES_DIR`, `DEFAULT_HUBS_DIR`, `DEFAULT_CANDIDATES_DIR`,
`DEFAULT_ADS_DIR`) needs to point at the new root-level location, mirroring
`config.py`'s existing `_REPO_ROOT`-relative pattern already established for
`DEFAULT_OWN_DATA_DIR` (sprint 020).

`teams/registry/` and `directory/registry/` are separate, much smaller
registries (4 and 2 TOML files respectively) not named in Eric's directive —
out of scope for this issue; a candidate follow-up if the same principle is
ever extended to them.
