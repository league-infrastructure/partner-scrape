# Registry

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable

---

## 1. Purpose

`registry/` is the data-driven catalog of *what* the system scrapes and *how to reach it*:
one TOML file per organization, plus three parallel catalogs for hubs, ads, and
unpromoted candidates. It is a subsystem because it is the codebase's configuration
boundary — the deliberate seam that makes onboarding a new partner organization a data
edit rather than a code change. It owns the schemas those files must satisfy and the
loaders that turn them into typed objects, and it owns the *physical separation* between
catalogs that must never be confused with one another.

**(Sprint 025 ticket 001)** This document lives at `partner_scrape/registry/` alongside
the schema/loader code, but the four TOML data directories it describes (§2) do not: they
were relocated to a root-level `registry/` directory, sibling to `partner_scrape/` and
`data/`, so that config-as-data is not nested inside the Python package. Only the data
moved — the code (`schema.py`, `loader.py`, `hub_schema.py`, `candidates.py`,
`validate_roster.py`, this file) stays here. Each loader's `DEFAULT_*_DIR` constant now
resolves via `config.REPO_ROOT / "registry" / "<subdir>"` rather than a path relative to
this module's own `__file__`.

**(Sprint 014)** This sprint is squarely an exercise of that "onboarding is a data
edit" design point, at higher volume than any prior sprint: roughly 33 existing
`sources/` entries get a triage disposition (fixed / re-typed / flagged headless /
disabled-with-reason), two known mis-registrations are corrected
(`sd-river-park-foundation`'s `adapter_type`, `sandiego-gov`'s `org_name`/`site_url`
mismatch), and roughly 20 new entries are added against already-existing adapters. No
schema, loader, or catalog-separation change is needed for any of it — see §6.

**(Sprint 015 ticket 005)** Three of five feeds sprint 014 deferred solely on a
robots.txt policy gate (`county-parks`, `mission-trails`, `surfrider-sd`,
`sd-astronomy-association`, `swe-san-diego`) are registered with
`acquisition_policy.respect_robots = false`, following a stakeholder decision
(issue 38) that published ICS subscription URLs are feed-client traffic, and made
real by ticket 003's fetcher-threading fix; `county-parks` and
`sd-astronomy-association` were dropped after live dry-run exposed pre-existing
`ical.py` parsing bugs unrelated to robots policy (see the ticket's Notes).

**(Sprint 016 ticket 002)** Both feeds sprint 015 ticket 005 withheld are now
registered. Sprint 016 ticket 001's `ical.py` hardening (multi-RRULE
first-rule salvage, widened per-VEVENT exception isolation) fully unblocks
`sd-astronomy-association`, live-verified `found=795 dated=795 new=177` and
committed. `county-parks` (Tockify) needed one more fix: ticket 001's
`X-PUBLISHED-TTL` pre-parse strip was necessary but not sufficient — the same
Tockify feed also emits a second, distinct non-standard duration property,
`REFRESH-INTERVAL:P15M`, immediately after `X-PUBLISHED-TTL` in the
`VCALENDAR` header, which `icalendar`'s strict parser rejects identically
(`InvalidCalendar: Invalid iCalendar duration: P15M`). Per a team-lead ruling
that this was a second live-evidenced case of the exact pattern ticket 001
already fixed (not a new architectural boundary), ticket 002 widened
`ical.py`'s pre-parse strip to a small evidenced-property list covering both
properties (see `adapters/DESIGN.md`'s sprint-016 addendum). Re-verified live:
`county-parks` now returns `found=553 dated=553 new=36`, all 553 raw VEVENTs
parsing — this batch's single highest-yield feed. Both are committed with
`acquisition_policy.respect_robots = false`, completing the 5-of-5 robots-gated
batch from issue 38/40.

**(Sprint 016 ticket 004)** `sources/robotevents-vex-sd.toml` (new) registers the
first non-FIRST robotics league this project ingests — VEX Robotics Competition
(V5RC/VIQRC) and the Aerial Drone Competition, CA Region 4, via the new
`robotevents` adapter (`adapters/DESIGN.md`'s own sprint-016 addendum). Registered
`enabled = true` with no live verification — no `ROBOTEVENTS_KEY` was provisioned
during this ticket's execution — mirroring `frc-sd.toml`'s TBA precedent (§3's
"malformed or missing-required-field file is logged and skipped" isolation
covers a bad *file*; a missing *credential* is `pipeline.run()`'s existing
per-source isolation instead, unaffected by this file being present).

**(Sprint 027)** Two new `adapter_type` values, `program_page` and `program_listing`
(`adapters/DESIGN.md`), are registered exactly like any other source — a new
`sources/*.toml` file with `adapter_type = "program_page"` (or `"program_listing"`),
`config.url` (or `config.listing_urls`/`config.site_url`), and a new conventional
`config.program_kind` key (`"internship"` or `"program"`) the adapter reads to set
`Event.kind`. No registry code changes: `schema.py`/`loader.py` already accept any
string `adapter_type` value without validating it against a known set (§3's "no schema
validation for the contents of `config`" limitation, unchanged, extends to
`program_kind` the same way it already covers every other adapter-specific config key)
— dispatch to the right `Adapter` implementation happens entirely in `adapters/`, which
this module has no dependency on. This sprint is a pure exercise of "onboarding is a
data edit," at the granularity of ~18 new source files (roughly 15 individual program
pages, 2 listing sources, 1 scholarship).

**(Sprint 028)** Two more `adapter_type` values, `activenet_camps` and `campbrain`, plus
roughly 15-20 new `program_page_multi` camp-marketing-page sources — see §5b's own sprint
028 addendum for the full data-shape write-up. Same "no registry code change" story as
sprint 027's addition above: every new value is dispatched entirely inside `adapters/`.

## 2. Orientation

Four data directories, three schema/loader pairs. The directories below live at the
repo-root `registry/` (sibling to `partner_scrape/`), not inside this subsystem's own
`partner_scrape/registry/` — see §1's sprint 025 ticket 001 note.

| Directory | Schema | Loader | Contents |
|---|---|---|---|
| `sources/` | `schema.SourceConfig` | `loader.load_sources` / `load_active_sources` | ~101 organizations before sprint 014; ~120 after |
| `hubs/` | `hub_schema.HubConfig` | `hub_schema.load_hubs` | curated lead-generation hubs |
| `ads/` | `export.ads.AdConfig` | `export.ads.load_ad_configs` | hand-authored ad slots |
| `candidates/` | `candidates.CandidateStub` | `candidates.list_candidates` | discovered orgs awaiting human promotion |

See also [`DO_NOT_SCRAPE.md`](DO_NOT_SCRAPE.md) — a checked-in, non-loaded reference of sites this project has investigated and decided not to scrape (or deferred); check it before re-researching a candidate hub or source's ToS/robots.txt from scratch.

A `SourceConfig` is `source_id` (the TOML filename stem), `org_name`, `adapter_type`,
`config`, plus optional `taxonomy_defaults`, `acquisition_policy`, and `enabled`.
`config`, `taxonomy_defaults`, and `acquisition_policy` are plain dicts, not sub-schemas.
`acquisition_policy` is where `fetch_strategy` (`"static"` / `"headless"`) and `max_urls`
(default 300) live.

A `HubConfig` is much smaller — `hub_id`, `hub_name`, `page_urls`, `config` — with no
`adapter_type` and no `acquisition_policy`, because a hub is a place to look for
organizations, never a place to acquire events from.

`candidates.py` writes review-marked TOML stubs containing only `org_name`,
`candidate_url`, `discovered_via`, and `evidence_text`.

## 3. Constraints and Invariants

- **A malformed or missing-required-field file is logged and skipped, never fatal.** With
  ~100 source files, one bad edit must not take the whole run down. Both `load_sources`
  and `load_hubs` catch `InvalidSourceConfig`/`InvalidHubConfig` and `TOMLDecodeError`
  per file.
- **`hubs/`, `ads/`, and `candidates/` are physically separate from `sources/` and are
  never in `loader.DEFAULT_SOURCES_DIR`'s scan path.** This is the primary safety
  property preventing a hub — another aggregator's listing — from being treated as a live
  event source.
- **A candidate stub deliberately omits `adapter_type` and `config`,** so that even a
  misdirected `load_sources()` pointed at `candidates/` fails
  `SourceConfig.from_toml`'s required-field check rather than silently succeeding. This is
  belt-and-suspenders behind the directory separation, and it is why promotion is a
  deliberate human edit: a stub is *not* a valid source until someone fills in how to
  reach it.
- **`load_sources` returns disabled entries; `load_active_sources` filters them.**
  Disabling a source must be a one-line `enabled = false` edit, not a file deletion, so
  the entry still round-trips through the loader and its history is preserved. The
  Pipeline uses `load_active_sources`; anything auditing the catalog uses `load_sources`.
- **`source_id` is the TOML filename stem.** It is the join key for the enrichment cache,
  the sitemap snapshot, the yield-history snapshot, and the export's source attribution.
  Renaming a file orphans all four.
- **`config` / `taxonomy_defaults` / `acquisition_policy` stay untyped dicts.** Different
  `adapter_type`s need genuinely different shapes (`api_base` for `tec_rest`, `feed_url`
  for `ical`, a board token for `greenhouse`). Over-typing them would need revisiting on
  every new adapter, and the validation that matters — "does this adapter understand this
  config?" — can only happen in the adapter anyway.
- **Deliberate non-goal — no fetching, no adapter knowledge.** This subsystem parses and
  validates files. It does not know what an adapter does with the config it hands over,
  and it must not grow adapter-specific validation.

## 4. Design

**One file per organization.** The alternative — one large catalog file — was rejected
because the registry is edited by humans, reviewed in pull requests, and grows by one
entry at a time. Per-file granularity makes a diff show exactly which organization
changed, and makes the "skip the bad file, keep the other hundred" isolation natural
rather than something a parser has to reconstruct.

**Why `hub_schema.py` is one module while sources are split across `schema.py` and
`loader.py`.** A hub definition is a much smaller shape, so a schema/loader split adds no
real separation of concerns. The asymmetry is deliberate, not an oversight.

**`from_toml` classmethods do the validation.** Each schema owns its own required-field
check and raises its own exception type (`InvalidSourceConfig`, `InvalidHubConfig`,
`InvalidAdConfig`), which the directory loader catches. Validation lives next to the shape
it validates.

**Where the ads catalog lives.** `registry/ads/` holds the data but
`export/ads.py` holds its schema and loader — the one place the four catalogs are not
symmetric. The ad contract is an output-side concern (it exists to write `ads.json`) and
was built with the export it feeds; only its *data* belongs alongside the other
hand-curated catalogs.

**`tomllib`, not a dependency.** Standard library since Python 3.11; the package requires
3.13.

## 5. Interfaces

### Exposes
- **`load_active_sources(directory=None) -> list[SourceConfig]`** — the enabled subset;
  what `pipeline.run()` calls. Defaults to `DEFAULT_SOURCES_DIR`.
- **`load_sources(directory=None) -> list[SourceConfig]`** — the full parseable set,
  including disabled entries. Never raises for a bad file; logs and skips.
- **`SourceConfig`**, **`SourceConfig.from_toml(path)`**, **`InvalidSourceConfig`**,
  **`DEFAULT_SOURCES_DIR`**, **`DEFAULT_MAX_URLS_PER_SOURCE`** (300).
- **`HubConfig`**, **`HubConfig.from_toml(path)`**, **`load_hubs(directory=None)`**,
  **`InvalidHubConfig`**, **`DEFAULT_HUBS_DIR`**.
- **`write_candidate(candidate, directory=None) -> CandidateStub`** — persists one
  `OrgCandidate` as a review stub, skipping near-duplicates of existing stubs.
  **`list_candidates(directory=None)`**, **`CandidateStub`**, **`DEFAULT_CANDIDATES_DIR`**.

### Consumes
- **`discovery.hub_scan.OrgCandidate`** — the input to `write_candidate`. The only
  inbound type dependency this subsystem has, and it is data-only.

Otherwise nothing: `registry/` sits near the bottom of the dependency graph, consumed by
`adapters/`, `discovery/`, and `pipeline.py`.

## 5b. Data conventions

`acquisition_policy` keys in use today:
- `fetch_strategy` — `"static"` (default) or `"headless"`; read only by `pipeline.run()`.
- `max_urls` — per-source discovery cap, default 300; enforced by `adapters.base.run`.
- `rate_limit_seconds` and other politeness knobs are passed through to `PoliteFetcher`.

`taxonomy_defaults` supplies `Opportunity` fields that cannot be derived from event text
(contact details, `financial_support`, `ngss_aligned`, and similar), applied during
`normalize/`'s mapping stage. **(Sprint 015 ticket 008)** `eligibility` is now the one key
actually consumed — threaded through `normalize.run()`'s `source_taxonomy_defaults`
parameter into `Opportunity.eligibility`; the other conventional keys named above remain
unread hardcoded stubs in `normalize/run.py`, an explicit Out of Scope decision (see
`normalize/DESIGN.md`'s own sprint 015 addendum). §6's "no schema validation for the
contents of `config`" limitation applies identically to `taxonomy_defaults`: a typo'd key
(e.g. `elegibility`) is silently ignored, not an error.

**(Sprint 027)** `config.program_kind` (`"internship"` | `"program"`) and, for
`program_listing` sources, `config.listing_urls`/`config.site_url` (the identical shape
`listing_html` already uses) are new conventional `config` keys, read only by the two
new adapters — same untyped-dict status as every other adapter-specific `config` key.
`config.opportunity_type` is an additional, optional override for a `program_kind =
"program"` source whose type is known a priori (e.g. the SD Foundation Scholarship's
`"Funding Opportunities"`) rather than left to the LLM extraction call's own
classification.

**(Ticket 006 exception revision)** A third `adapter_type` value, `program_page_multi`
(same `config.url`/`config.program_kind` shape as `program_page`, for a page whose body
holds N inline program records rather than one — see `adapters/DESIGN.md`'s Revision
note), and one new conventional `config` key for `program_listing` sources,
`config.link_selector` (a CSS selector string, e.g.
`li[data-grade*="High School"] a.learnmore`) — both are ordinary registry data, same as
every key above: no `schema.py`/`loader.py` change, dispatch and interpretation happen
entirely inside `adapters/`/`discovery/`, which this module still has no dependency on.

**(Sprint 028)** Two more `adapter_type` values, `activenet_camps` and `campbrain`
(`adapters/DESIGN.md`'s own sprint 028 section) — the two camp-registration platform
adapters. Both reuse `program_page`'s existing `config.url`/`config.program_kind`/
`config.opportunity_type` shape verbatim (one registered per-organization listing
endpoint, `program_kind = "program"`, `opportunity_type = "Camps"`); no new conventional
`config` key was needed for either, since a camp-platform source is, from this module's
point of view, indistinguishable in shape from a `program_page`/`program_page_multi`
source — same untyped `config` dict, same "no schema validation for the contents of
`config`" limitation (§6) applying identically. Every marketing-page camp source
registered this sprint (San Diego Zoo's per-program pages, Living Coast, Coastal Roots
Farm, Elementary Institute of Science, SD Model Railroad Museum, Camp Invention, CMOD,
Southwestern College Y.E.S., Birch's newsroom page, Fleet) is a plain `program_page_multi`
entry with `config.opportunity_type = "Camps"` — zero registry code change, a pure
"onboarding is a data edit" exercise at the granularity of roughly 15-20 new source files
(San Diego Zoo and Camp Invention each contribute multiple individually-registered
per-program pages). Camp Galileo SD is deliberately not one of them (commercial-chain
scope exclusion — see `sprint.md`'s Scope and `adapters/DESIGN.md`'s Design Rationale);
Air & Space Museum and Helen Woodward are registered only as `activenet_camps` sources,
not also as `program_page_multi` marketing-page sources, for the same
dual-registration-avoidance reason.

## 6. Open Questions / Known Limitations

- There is no schema validation for the contents of `config`, so a typo in a key an
  adapter expects surfaces as a zero-yield run rather than a load error. The yield report
  in `observability/` is the only signal.
- `registry/candidates/` does not exist on disk yet; the discovery flow that populates it
  has not been run against real hubs at volume.
- Only one hub and one ad are configured today. Neither catalog has been exercised with
  multiple entries in production.
- Promotion from a candidate stub to a live source is entirely manual and undocumented
  beyond the stub's own fields — there is no checklist for choosing an `adapter_type`.
- Disabled sources accumulate. Nothing reports how many entries are `enabled = false` or
  why. **(Sprint 014, partial)** The "or why" half is now addressed by convention, not
  tooling: this sprint's triage ticket disables sources with an inline reason comment
  (`enabled = false  # disabled: <reason>`, e.g. `olivewood-gardens.toml`'s existing
  precedent), so a human reading the file always sees why. The "how many, in aggregate"
  half — a report or count across the catalog — is still unbuilt; this remains a real
  gap for a future sprint, not resolved here.
- **(Sprint 014)** `source_id` correctness (the constraint in §3: it's the join key for
  four separate subsystems) was violated in the wild before this sprint —
  `sandiego-gov.toml`'s `org_name` named an entirely different organization than its
  `site_url`. This sprint's triage ticket corrects it, but the registry itself still has
  no automated check that `org_name` and `site_url` (or any other field pair) are
  mutually consistent — the §3 "no schema validation for the contents of `config`"
  limitation extends to this kind of cross-field consistency too, and a similar
  mismatch could recur silently for any other source.
- **(Sprint 028)** Nothing in `registry/` itself prevents a future edit from
  re-introducing the exact dual-registration this sprint deliberately avoided by
  convention (Air & Space Museum/Helen Woodward registered only via `activenet_camps`,
  never also via a `program_page_multi` marketing-page entry) — the same "no cross-field/
  cross-file consistency check" gap the sprint 014 entry above already names, applied to
  "the same organization registered under two source files." Not solved here; caught only
  by author discipline and code review, same as the sprint 027 COSMOS/OPTIMUS/ENLACE risk
  this mirrors.
