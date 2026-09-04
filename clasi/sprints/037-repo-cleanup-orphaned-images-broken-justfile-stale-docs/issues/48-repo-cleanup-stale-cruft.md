---
status: in-progress
sprint: '037'
tickets:
- 037-001
- 037-002
- 037-003
---

# Repo cleanup: orphaned images, broken justfile, stale docs and ignores

Survey done 2026-09-03 at the stakeholder's request ("go through the
directory, and propose clean ups... I want you to get rid of any old
cruft and tidy up"), approved 2026-09-04. Seven items, each verified
against the real tree.

**Not cruft, explicitly out of scope:** `dev/` (two live hand-run
maintenance scripts — `refresh_school_directories.py`, which
`geo_ladder.py` depends on annually, and `backfill_missing_images.py`,
whose check-only mode is a reusable integrity gate); the 241 unreviewed
stubs in `registry/candidates/` (a stakeholder review backlog); and the
26 byte-identical files shared by `.agents/` and `.claude/` (CLASI's
dual-platform install).

## 1. Orphaned opportunity images (77 files, 35 MB)

`data/images/opportunities/` holds 562 files / 336 MB. Only 485 are
referenced by `data/opportunities.json` or any
`data/partners/*/{events,past-events}.json`. The other 77 are
referenced by nothing.

Filenames are content-hashed, so a deleted image whose event reappears
is simply re-downloaded — the cost of being wrong is one refetch, not
data loss.

Prefer adding a prune mode to `dev/backfill_missing_images.py` over a
throwaway command: that script already computes the referenced set for
its check mode, so the inverse is nearly free, and it makes this
repeatable instead of a one-time manual sweep. Re-run its existing
check afterward to prove nothing referenced was removed.

**Done (037-001, 2026-09-04)**: added `--prune`/`--dry-run` to
`dev/backfill_missing_images.py`. Ran against the real repo:
`data/images/opportunities/` went from 562 files / 322M to 485 files /
288M — exactly 77 files removed (~34M), matching the survey. Post-prune
check-only run reported 0 missing for both the partners-derived and
opportunities-derived checks.

## 2. `justfile` is actively broken and partly dangerous

- `dev`, `build`, `preview` all `cd site/`, which has not existed in
  this repo since sprint 019 moved the site to `stem-ecosystem`.
- **`pub` runs `git push origin master`** — this repo is under a
  deliberate push freeze — and then dispatches `pages.yml`, which was
  disabled on 2026-09-03 when the stakeholder turned off website
  publishing from this repo.

`pub` must not survive in any form that pushes master or dispatches a
Pages deploy. For the other three, either remove them or make it
unmistakable that they need a manual `stem-ecosystem` clone; removal is
the honest default now that this repo does not publish the site.

## 3. README documents publishing that is turned off

README's beta-preview section describes the GitHub Pages workflow and
tells the reader to clone `stem-ecosystem` into `site/` for `just
dev`/`just build`. Publishing was disabled 2026-09-03 (workflow
`disabled_manually`; the site stays live serving its last deploy).
Rewrite that section to match reality, and keep it consistent with
whatever ticket 2 does to the justfile.

## 4. Stale references to deleted files

`partner_scrape/discovery/sitemap.py` and
`partner_scrape/discovery/DESIGN.md` cite `dev/inventory_sitemaps.py`
and `dev/lib/sitemap_parser.py` as the origin of their regex patterns.
Both files were deleted long ago. The attribution is honest history but
points at nothing a reader can open — reword so it reads as historical
provenance rather than a live cross-reference.

## 5. `.gitignore` gaps

None of these are ignored, and the first two appeared in `git status`
during the 2026-09-02 session: `.clasi/.clasi.db-wal`,
`.clasi/.clasi.db-shm` (sqlite sidecars of the already-ignored
`.clasi/.clasi.db`), and `.pytest_cache/`.

## 6. Redundant `docs/design/.gitkeep`

`docs/design/` now holds `design.md`, `overview.md`, `specification.md`
and `usecases.md`. The `.gitkeep` no longer keeps anything.

## 7. Four empty config files

`config/dev/public.env`, `config/dev/secrets.env`,
`config/local/eric/public.env`, `config/local/eric/secrets.env` are all
0 bytes; only `config/prod/*` carries real (SOPS-encrypted) content.

**Verify before deleting**: these may be scaffolding `dotconfig`
expects for its deploy list. If removing them breaks `dotconfig`'s view
of available deploys, leave them and record why here instead.

## Verification

Full suite green; `dev/backfill_missing_images.py` reports 0 missing
after the prune; `just --list` runs clean with no recipe pointing at a
path that does not exist.
