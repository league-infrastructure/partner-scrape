---
id: '001'
title: Offering standing-entity model, registry dispatch, and offerings.json export
status: open
use-cases: [SUC-052]
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

- [ ] `partner_scrape/directory/model.py` gains `OfferingType = Literal["volunteer", "free_program"]`,
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
- [ ] `partner_scrape/directory/sources/base.py` gains `OfferingRef`,
      `RawOfferingResponse`, an `OfferingSource` Protocol
      (discover/fetch/extract), and `run_offering_source()`, structurally
      identical to `PlaceSource`/`ClubSource`'s own trio.
- [ ] `partner_scrape/directory/sources/offering_static_roster.py`:
      `OfferingStaticRosterSource` reads `config.roster_path` (resolved
      relative to `directory/data/` when not absolute) straight off
      disk via `Path.read_text()`/`tomllib`, never touches the injected
      `Fetcher` (a runtime-call assertion test, matching
      `TestNeverTouchesFetcher`'s existing pattern, is required — see
      Testing below). Per-entry validation failures are logged and
      skipped, never raised (per-record failure isolation, matching
      `static_roster.py`'s convention).
- [ ] `partner_scrape/directory/pipeline.py`: `run_directory()`'s
      dispatch extends to a three-way check — `_PLACE_SOURCES` then
      `_CLUB_SOURCES` then `_OFFERING_SOURCES` per `source_config`,
      still one combined loop (never a third separate loop — this
      doc's own existing "why one combined loop" rationale applies
      identically to a third table). **No geocoding stage is added for
      `Offering`** — no `_apply_offering_geocoding()` function exists.
- [ ] `partner_scrape/directory/export.py`: `export_directory()` gains
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
- [ ] `partner_scrape/directory/registry/offerings-sd.toml`: new
      Directory Registry entry, `adapter_type =
      "offering_static_roster"`, `org_name = "San Diego STEM Offerings
      (curated static roster)"`, `enabled = true`, `[config]
      roster_path = "offerings.toml"`. No `[acquisition_policy]`
      section, matching `places-sd.toml`'s precedent.
- [ ] `partner_scrape/directory/data/offerings.toml`: created with a
      short header comment (matching `places.toml`'s own) and 1-2
      fixture rows sufficient for the tests below — real curation is
      tickets 002/003's job, not this ticket's.
- [ ] `cli.py`'s `directory` subcommand's printed summary gains an
      offerings count alongside the places/clubs counts — no new flag,
      no new subcommand (matching ticket 018-008's precedent exactly).
      `export/mirror.py`'s `MIRRORED_DATA_FILES` gains `"offerings.json"`.
- [ ] `_check_related_partner_references()` (or a sibling check) is
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
