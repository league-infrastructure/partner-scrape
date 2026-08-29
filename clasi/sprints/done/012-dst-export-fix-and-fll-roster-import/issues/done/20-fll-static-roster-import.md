---
status: done
sprint: '012'
tickets:
- 012-002
---

# Import the 48 FLL teams as a static roster into the teams directory

## Description

Sprint 011 shipped a working `/teams` section covering **230 San Diego robotics teams** — 152 FTC
from FTCScout and 78 FRC from The Blue Alliance, both live and refreshable. It deliberately left out
the third league: **FIRST LEGO League, 48 teams.**

This is increment 5 of the original robot-teams issue, split out at detail-planning time because it is
structurally different work from the rest of that sprint rather than more of the same.

## Cause

**There is no public FLL API.** Probed and confirmed: `firstinspires.org/team-event-search` exposes no
usable JSON endpoint (404/405), and unlike FTC (FTCScout) and FRC (TBA) there is no third-party
aggregator carrying FLL rosters. The existing 48-team list came from a *manual browser export* of the
FIRST team search, hand-enriched by an analyst on 2026-08-13, living in the sibling repo at
`../robot-team-analysis/fll/sd-fll-teams-contact-list.md`.

So FLL cannot be a live source. It can only be a static, dated import — which is why it did not belong
alongside sprint 011's live-pipeline work.

**It also has a hard expiry.** LEGO declined to renew its 28-year FIRST partnership on 2026-03-19,
making **2026-27 the last FIRST LEGO League season ever**. The successor program has no name, no
hardware, and no vendor. This data will stop being refreshable, and the `league` field needs to stay
open enough to absorb whatever replaces it.

## Proposed fix

A `static_roster` team source, alongside the existing `ftcscout` and `tba` sources in
`partner_scrape/teams/sources/`:

- Reads a committed CSV/markdown roster from `partner_scrape/teams/data/`; never touches the
  `Fetcher` (document that in the docstring, and test it).
- Carries `sunset_season = "2026-27"` in its registry TOML; `run_teams()` logs a WARNING once the
  current date passes it, so the staleness is loud rather than silent.
- Marks every record's provenance as static, so a consumer can tell live data from a dated snapshot.
- Location: FLL records have no school in most cases, and 28 of the 48 are family/home teams whose
  area was *inferred by an analyst from a corridor pattern, not sourced*. They should resolve at
  city precision at best, and the existing rung-7 "never guess" rule applies.

**Handle the contact data carefully.** The upstream `data/robot-teams.json` merge carries 40 email
addresses, 6 of them volunteer coaches' personal Gmail accounts, and its own `meta.warning` says not
to publish it. `partner_scrape/teams/model.py::Team` deliberately has **no email field** so leaking
one is structurally impossible — keep it that way, and strip contact fields at import rather than
carrying them into the module and filtering later.

## Verification

- Fixture-based, no network; a test asserting the source never calls the fetcher.
- A test asserting the sunset warning fires past `2026-27`.
- The export's privacy test (no key or value in `teams.json` matching an email pattern) must still
  pass with FLL records present.
- `/teams` rebuilds with 278 teams (230 + 48) and the page count matches.
- Full suite green.

## Related

- `clasi/sprints/done/011-robot-teams/issues/robot-teams-scrape-locate-and-publish-san-diego-first-teams.md`
  — the parent issue; this is its increment 5.
- `partner_scrape/teams/DESIGN.md` — the subsystem this extends.
- `../robot-team-analysis/fll/sd-fll-teams-contact-list.md` — the source roster.
- `../robot-team-analysis/fll/fll-disruption-2026.md` — the end-of-program brief.
- `data/robot-teams.json` — the merged seed carrying the emails; do not read it from the pipeline.
