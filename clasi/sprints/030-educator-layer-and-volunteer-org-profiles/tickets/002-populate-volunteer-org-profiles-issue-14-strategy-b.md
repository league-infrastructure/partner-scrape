---
id: '002'
title: Populate volunteer org profiles (issue 14 Strategy B)
status: open
use-cases: [SUC-050]
depends-on: ['001']
github-issue: ''
issue: 14-improve-volunteer-opportunity-discovery.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Populate volunteer org profiles (issue 14 Strategy B)

## Description

Add real, hand-curated `[[offering]]` rows (`offering_type =
"volunteer"`) to `directory/data/offerings.toml` for the six orgs issue
14's 2026-08-30 research update named as Strategy B's target list:
Fleet, SDZWA, Birch, the Nat, ILACSD, and San Diego River Park
Foundation. Data-only ticket — no code changes beyond what ticket 001
already shipped.

**Age minimums are the load-bearing fact of this ticket** (issue 14's
own instruction: "Note age minimums explicitly ... it matters for the
teen audience"): Fleet 18+ (`VolunteerMatters`, 6-month commitment —
capture the commitment in `how_to_book`'s free text, there is no
separate structured field for it this sprint, see `directory/DESIGN.md`
Open Questions), SDZWA 18+ (`Volgistics`), Birch 16+ (`Volgistics`).
For the Nat, ILACSD, and San Diego River Park Foundation, research each
org's own stated age policy directly (do not assume 18+ by default —
`age_minimum` stays `None` if the org states no minimum, never guessed).

## Acceptance Criteria

- [ ] `directory/data/offerings.toml` has exactly six new
      `offering_type = "volunteer"` rows: Fleet, SDZWA, Birch, the Nat,
      ILACSD, San Diego River Park Foundation.
- [ ] Fleet's `age_minimum = 18`, SDZWA's `age_minimum = 18`, Birch's
      `age_minimum = 16` — matching issue 14's research verbatim.
- [ ] The Nat's, ILACSD's, and San Diego River Park Foundation's
      `age_minimum` reflects each org's own actually-published policy
      (a real value or `None` if the org states none) — not a copied
      default.
- [ ] Every row's `link_url` points to that org's actual volunteer
      portal/application page (Volgistics/VolunteerMatters/Galaxy
      Digital or the org's own "get involved" page), verified live.
- [ ] Every row's `description` states what volunteers actually do at
      that org, in the org's own words where possible.
- [ ] Every row's `related_partner_id` is hand-checked against
      `site/src/data/partners.json`'s `id` field where a confident
      match exists; left `None` otherwise — never guessed.
- [ ] `uv run partner-scrape directory --source offerings-sd --dry-run -v`
      (real, not fixture, run against the static roster — this reads
      local TOML, not the network, so it is safe under this sprint's
      no-live-network-in-tests constraint) shows all six rows parsed
      with no validation warnings.

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/` (roster
  parsing/validation tests from ticket 001 must still pass against the
  now-larger real dataset).
- **New tests to write**: extend `tests/directory/
  test_sources_offering_static_roster.py`'s dataset-validity coverage
  (or a new `tests/directory/test_dataset_validity.py` case, mirroring
  `TestRelatedPartnerIdJoinIntegrity`) to spot-check the six volunteer
  rows' `age_minimum` values and `related_partner_id` joins.
- **Verification command**: `uv run pytest`
