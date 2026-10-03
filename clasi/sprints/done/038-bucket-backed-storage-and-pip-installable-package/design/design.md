---
sprint: "038"
---
# Sprint 038 design overlay

Top-level doc changes (applied by tickets, not now):
- `docs/design/design.md`: add a "Storage" section (bucket layout, Store abstraction, where each key family lives, bucket versioning replaces git history for yield-history.json); update repository layout (data/ no longer in git, registry bundled in package).
- `partner_scrape/DESIGN.md`: document `storage.py` and the new `config.py` settings (no REPO_ROOT defaults).
- Per-module overlays: see `fetch-DESIGN.md`, `adapters-DESIGN.md`, `export-DESIGN.md`, `registry-DESIGN.md` here; tickets apply them to the real `partner_scrape/<module>/DESIGN.md`.
