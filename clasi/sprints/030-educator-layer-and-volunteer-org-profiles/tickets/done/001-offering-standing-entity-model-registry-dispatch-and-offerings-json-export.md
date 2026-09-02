---
id: '001'
title: Offering standing-entity model, registry dispatch, and offerings.json export
status: done
use-cases:
- SUC-052
depends-on: []
github-issue: ''
issue:
- 33-educator-programs-layer.md
- 14-improve-volunteer-opportunity-discovery.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Offering standing-entity model, registry dispatch, and offerings.json export

## Description

Foundation ticket for both linked issues (33 part 2 and 14 Strategy B):
add a third standing-entity type, `Offering`, to `partner_scrape/
directory/`, following the exact `Place`/`Club` package shape ticket
018-007/018-008 established. This ticket ships the mechanism only —
model, source, registry entry, pipeline dispatch, export — with a small
fixture-sized roster sufficient to prove the mechanism end to end.
Tickets 002/003 populate the real curated data afterward.

Full design rationale lives in this sprint's `design/directory-
DESIGN.md` (see its "Revision (2026-09-02 — sprint 030 Offerings
standing-entity type)" section) — read that before starting; this
ticket does not re-derive the design.

**Key decisions this ticket implements** (see the design doc for the
full "why"):
- One `Offering` dataclass serves both issues via an `offering_type`
  discriminator (`"volunteer"` | `"free_program"`), not two models.
- `age_minimum: int | None` is a first-class typed field (never folded
  into free-text `eligibility`) — `None` means "no individual-volunteer
  age minimum applies," never a guessed `0`.
- `Offering` has **no location/geocoding fields at all** — no
  `latitude`/`longitude`/`location_precision`, no `GeoLadder`
  dependency, no geocoding pipeline stage. This is a deliberate scope
  narrowing versus both `Place` and `Club`, not an oversight.
- `related_partner_id: int | None` reuses `Place`'s existing
  hand-verified-join convention (never auto-derived).
- Data file is TOML (`directory/data/offerings.toml`, `[[offering]]`
  array of tables), matching `places.toml`'s "too many fields for a
  flat table" rationale, not `hack-club-sd.tsv`'s narrower shape.

## Acceptance Criteria

- [x] `partner_scrape/directory/model.py` gains `OfferingType = Literal["volunteer", "free_program"]`,
      `OfferingStatus = Literal["active", "seasonal", "closed"]` (mirroring
      `Place`'s/`Club`'s `VALID_*` frozenset-derivation pattern), and an
      `Offering` dataclass with fields: `offering_id`, `org_name`,
      `title`, `offering_type`, `description`, `eligibility`,
      `age_minimum: int | None`, `how_to_book`, `link_url`,
      `last_verified`, `status`, `status_note`,
      `related_partner_id: int | None`, `sources: list[str]`. Every
      field defaults to an empty/neutral value (bare `Offering()` is
      constructible), matching `Place`/`Club`'s convention. Validation:
      `status_note` required whenever `status != "active"`, mirroring
      `Place.status_note`'s existing rule exactly.
- [x] `partner_scrape/directory/sources/base.py` gains `OfferingRef`,
      `RawOfferingResponse`, an `OfferingSource` Protocol
      (discover/fetch/extract), and `run_offering_source()`, structurally
      identical to `PlaceSource`/`ClubSource`'s own trio.
- [x] `partner_scrape/directory/sources/offering_static_roster.py`:
      `OfferingStaticRosterSource` reads `config.roster_path` (resolved
      relative to `directory/data/` when not absolute) straight off
      disk via `Path.read_text()`/`tomllib`, never touches the injected
      `Fetcher` (a runtime-call assertion test, matching
      `TestNeverTouchesFetcher`'s existing pattern, is required — see
      Testing below). Per-entry validation failures are logged and
      skipped, never raised (per-record failure isolation, matching
      `static_roster.py`'s convention).
- [x] `partner_scrape/directory/pipeline.py`: `run_directory()`'s
      dispatch extends to a three-way check — `_PLACE_SOURCES` then
      `_CLUB_SOURCES` then `_OFFERING_SOURCES` per `source_config`,
      still one combined loop (never a third separate loop — this
      doc's own existing "why one combined loop" rationale applies
      identically to a third table). **No geocoding stage is added for
      `Offering`** — no `_apply_offering_geocoding()` function exists.
- [x] `partner_scrape/directory/export.py`: `export_directory()` gains
      a third optional `offerings: list[Offering] | None = None`
      keyword argument. `None` means "do not touch `offerings.json`
      at all"; a list (possibly empty) writes it as an independent
      `{"meta": {...}, "offerings": [...]}` document to
      `own_data_dir / "offerings.json"` only (sprint 025's "one
      publish, one path" convention — no `site_dir` write). `meta`
      carries `generated`/`total`/`by_offering_type`, mirroring
      `clubs.json`'s `by_club_type` shape. Sorted by
      `(offering_type, name)`. The existing "places before clubs"
      ordering/failure-isolation guarantee extends to
      "places before clubs before offerings."
- [x] `partner_scrape/directory/registry/offerings-sd.toml`: new
      Directory Registry entry, `adapter_type =
      "offering_static_roster"`, `org_name = "San Diego STEM Offerings
      (curated static roster)"`, `enabled = true`, `[config]
      roster_path = "offerings.toml"`. No `[acquisition_policy]`
      section, matching `places-sd.toml`'s precedent.
- [x] `partner_scrape/directory/data/offerings.toml`: created with a
      short header comment (matching `places.toml`'s own) and 1-2
      fixture rows sufficient for the tests below — real curation is
      tickets 002/003's job, not this ticket's.
- [x] `cli.py`'s `directory` subcommand's printed summary gains an
      offerings count alongside the places/clubs counts — no new flag,
      no new subcommand (matching ticket 018-008's precedent exactly).
      `export/mirror.py`'s `MIRRORED_DATA_FILES` gains `"offerings.json"`.
      **Note (see Notes below): `export/mirror.py` no longer exists —
      sprint 019 removed it and its `MIRRORED_DATA_FILES` allowlist
      outright, along with `config.get_mirror_site_dirs()` and the
      `--mirror-site-dir`/`--no-mirror` CLI flags (see `export/
      DESIGN.md`'s own "Sprint 019" note). This clause is stale
      boilerplate inherited from ticket 018-008's template and predates
      that removal — there is nothing left to add `"offerings.json"`
      to. Treated as satisfied-as-inapplicable; the CLI summary half of
      this criterion is implemented and tested
      (`tests/test_cli_directory.py::TestArgumentWiring::
      test_prints_a_summary_including_the_written_offerings_count`).
- [x] `_check_related_partner_references()` (or a sibling check) is
      extended to also validate `Offering.related_partner_id` values
      against `site/src/data/partners.json`'s own `id` field, matching
      `Place`'s existing join-integrity discipline.

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/` (full
  suite — must stay green; `tests/directory/test_export.py`'s
  `TestHardInvariants` must still pass unmodified, extended to also
  assert `offerings.json` is untouched when `offerings=None`).
- **New tests to write**:
  - `tests/directory/test_model.py` (or extend the existing model test
    file): `Offering` construction, `status_note` validation rule.
  - `tests/directory/test_sources_offering_static_roster.py`: mirrors
    `test_sources_static_roster.py`'s structure, including a
    `TestNeverTouchesFetcher` case.
  - `tests/directory/test_pipeline.py`: extend for the three-way
    dispatch (a real `Offering` registry entry must not trigger a
    spurious Place/Club "unregistered" warning, mirroring the existing
    combined-dispatch test), and a test proving no `GeoLadder` is ever
    constructed for `Offering` records (matching the existing
    `test_geo_ladder_is_never_constructed_*` pattern's spirit — for
    `Offering` there is no fallback function to call at all).
  - `tests/directory/test_export.py`: `offerings=None` vs.
    `offerings=[]` vs. a real list, matching `clubs`'s existing test
    coverage shape.
  - **Every test that reaches `export_directory()`/`run_directory()`
    with a real `own_data_dir`/`offerings` argument MUST pin
    `own_data_dir=tmp_path`** — `config.get_own_data_dir()` resolves to
    a real repo path with no env override; an unpinned test silently
    writes into this repo's actual `data/` directory.
- **Verification command**: `uv run pytest`

## Notes

- **`offerings.json` sort key.** SUC-052's Main Flow and this ticket's
  own export.py acceptance criterion both describe sorting "matching
  `places.json`'s/`clubs.json`'s own `(type, name)` convention:
  `(offering_type, name)`." `Offering` has no single `name` field — it
  splits `org_name` (the operating org, e.g. "Fleet Science Center")
  and `title` (the offering's own name within that org, e.g.
  "Volunteer Program"), a deliberate two-field split this ticket's own
  model design calls for (see `directory/model.py`'s `Offering`
  docstring). Resolved as `(offering_type, org_name, title)`:
  `org_name` is the closer analog to `Place.name`/`Club.name` (the
  "who is this" field a reader scans first), with `title` as a stable
  tiebreaker for the rare case of two offerings from the same org.
  Documented in `export.py`'s own inline comment at the sort call site.
- **`export/mirror.py`'s `MIRRORED_DATA_FILES` criterion is stale.**
  Sprint 019 removed `export/mirror.py` outright (along with
  `config.get_mirror_site_dirs()` and the `--mirror-site-dir`/
  `--no-mirror` CLI flags) — see `partner_scrape/export/DESIGN.md`'s
  own "Sprint 019" note. This ticket's acceptance-criteria text
  (inherited from ticket 018-008's template, written before sprint 019)
  still names that file; there is nothing left to add
  `"offerings.json"` to. Not an architectural conflict requiring an
  exception — just an outdated line item, treated as
  satisfied-as-inapplicable. The rest of that same criterion (the CLI
  summary's offerings count) is implemented and tested normally.
- **Fixture data, not real curation.** `directory/data/offerings.toml`
  carries two clearly-marked `PLACEHOLDER` rows (one `volunteer`, one
  `free_program`) — enough to prove discover → fetch → extract →
  pipeline dispatch → export end to end, per this ticket's own scope
  ("Tickets 002/003 populate the real curated data afterward"). Tickets
  002 and 003 are expected to *replace* these rows, not merely append
  to them.
- **`_check_related_partner_references()` generalized, not
  duplicated.** `directory/pipeline.py`'s existing join-integrity guard
  now takes both `places` and `offerings` and builds one combined
  `(referencer_id, partner_id)` list before calling the already-generic
  `registry.validate_roster.check_partner_references()` once — no
  second, `Offering`-specific validation function.
- Full suite: `uv run pytest` → 2268 passed (baseline 2192; +76 from
  this ticket's new tests). No test writes into this repo's real
  `data/` directory (verified via `git status --short data/` after the
  run).
