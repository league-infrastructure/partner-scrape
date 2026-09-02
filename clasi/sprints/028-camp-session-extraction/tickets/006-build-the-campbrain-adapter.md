---
id: '006'
title: Build the campbrain adapter
status: done
use-cases:
- SUC-043
depends-on:
- '004'
- '005'
github-issue: ''
issue: 29-camp-session-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build the campbrain adapter

## Description

Builds the second of issue 29's two in-scope platform adapters:
`campbrain`, for organizations whose camps are hosted on CampBrain. New
module, `adapters/campbrain.py`, defining `CampBrainAdapter`, structurally
identical to ticket 005's `ActiveNetCampsAdapter` (same `discover()`/
`fetch()` single-configured-endpoint shape, same deterministic-parse-then-
LLM-fallback `extract()` shape, same constructor-injection signature, same
`_map_result_to_event` reuse, same `config.opportunity_type = "Camps"`
convention). Register in `adapters/__init__.py`'s `ADAPTERS` dispatch table
as `"campbrain"`.

**Registration scope**: issue 29 names Coastal Roots Farm and Watersports
Camp as CampBrain-hosted. Coastal Roots Farm is already registered via its
marketing page in ticket 004 (`program_page_multi`, full session table
already available there) — do **not** also register it via `campbrain`;
that would repeat the exact dual-registration risk this sprint's
`adapters/DESIGN.md` documents for Air & Space Museum/Helen Woodward.
Register **Watersports Camp** (or whichever CampBrain-hosted organization
in scope has no marketing-page equivalent) via this adapter, live-verified.

If live verification finds Coastal Roots Farm's marketing-page coverage is
in fact incomplete or unreliable compared to its CampBrain data, that is a
judgment call this ticket may resolve by switching Coastal Roots Farm's
registration from `program_page_multi` to `campbrain` (not by adding a
second registration) — document the reasoning in this ticket's Notes if
so.

## Acceptance Criteria

- [x] `adapters/campbrain.py` defines `CampBrainAdapter`
      (`discover`/`fetch`/`extract`), registered as `"campbrain"` in
      `adapters/__init__.py`.
- [x] A fixture-based test proves the adapter maps a saved CampBrain
      response/page into correctly-dated, correctly-priced `Event`s, with
      no live network or LLM call.
- [x] At least one CampBrain-hosted organization not already covered by a
      marketing page (e.g. Watersports Camp) is registered and
      live-verified.
- [x] Coastal Roots Farm is registered via at most one path total across
      this sprint (its ticket-004 marketing-page registration, unless this
      ticket's live verification finds cause to switch it — never both).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite).
- **New tests to write**: `tests/adapters/test_campbrain.py` — fixture-based,
  mirroring `test_activenet_camps.py`'s coverage shape (deterministic-parse
  path if confirmed live, LLM-fallback path, sold-out session, non-200
  fetch).
- **Verification command**: `uv run pytest`, plus a live dry-run for each
  newly-registered source.

## Notes

**Implementation.** `partner_scrape/adapters/campbrain.py` (new) defines
`CampBrainAdapter`, structurally identical to ticket 005's
`ActiveNetCampsAdapter`: `discover()`/`fetch()` share `ProgramPageAdapter`'s
single-configured-`url` shape; `extract()` first attempts a deterministic
JSON-sessions parse (`_try_parse_campbrain_sessions_json`,
`CONFIDENCE_STRUCTURED_PLATFORM = 1.0`), falling back to
`extract.reduce_html_to_text()` + `program_page._extract_many_programs()`
(the same call `program_page_multi`/`activenet_camps` already make) when
the body doesn't parse as that JSON shape. Every mapped field goes
through the existing `program_page._map_result_to_event` unmodified — no
new mapping code. Registered as `"campbrain"` in
`adapters/__init__.py`'s `ADAPTERS` table. Test file is
`tests/test_adapters_campbrain.py` (flat, not `tests/adapters/`) —
matching this repo's actual convention (`test_adapters_activenet_camps.py`
et al.), not this ticket's own draft path above, which predates that
convention being confirmed.

**Live verification (2026-09-02).** Investigated both issue-29-named
CampBrain orgs' real registration portals with a headless browser
(`wait_until="networkidle"` + settle wait, matching ticket 005's own
method): `https://coastalrootsfarm.campbrainregistration.com/` and
`https://watersportscamp.campbrainregistration.com/` (confirmed via a
live fetch of watersportscamp.com's own "Register Now!" link). Both are
CampBrain (BrainRunner Inc.) Vue/Vite SPAs whose *every* route probed
(default, `/programs`, `/catalog`, `/sessions`, `/camps`, `/register`,
`/session-select`, `/select-camper`) renders to an identical family
account **login form** — no session name, date, price, or availability
field anywhere in the rendered DOM or in any JSON response captured
during the render. This is a stricter gate than ActiveNet's JS-
fingerprint challenge: it's server-side authentication, not a bot check,
so no headless-rendering fix (unlike `fetch/headless.py`'s known gap for
ActiveNet) would recover data here. No institutional credential
equivalent exists for this consumer/family-account product. Full
write-up in `campbrain.py`'s module docstring.

**Registration.** `registry/sources/watersports-camp-campbrain.toml`
(new): The Watersports Camp, `adapter_type = "campbrain"`,
`enabled = false` with a reason comment recording the live-verification
finding above — same "design against the best evidence, disable with a
documented reason" precedent ticket 005 set for both its own ActiveNet
registrations.

**Coastal Roots Farm reconciliation.** Per this ticket's own instruction,
checked whether CampBrain is a better path than ticket 004's disabled
`program_page_multi` marketing-page registration
(`coastal-roots-farm-camp.toml`, disabled for an unrelated
extraction-quality reason — the LLM blends its 3 sessions into 1 dateless
record). It is not: `coastalrootsfarm.campbrainregistration.com` is
identically login-gated (checked live, same finding as Watersports Camp
above) — CampBrain yields *zero* accessible fields for this org, strictly
worse than the marketing page's human-legible (if currently
mis-extracted) prose. No `campbrain` entry was added for Coastal Roots
Farm; its existing ticket-004 registration is left unchanged. This
satisfies the "at most one path" acceptance criterion by construction —
only one registration exists for this org across the sprint, and it was
never a close call in practice once CampBrain's own login wall was
confirmed.

**Test result.** `uv run pytest` (full suite): 2140 passed (baseline 2124
+ 16 new `tests/test_adapters_campbrain.py` tests). No live network or
live Anthropic API call in any test — the deterministic-JSON path uses a
fixture-based speculative JSON payload (documented in `campbrain.py`'s
docstring as unconfirmed against any real CampBrain response, since none
was reachable); the LLM-fallback path uses a fixture reproducing the
real, live-captured login-page DOM
(`tests/fixtures/program_pages/campbrain_login_page.html`) plus
`FixtureProgramLLMClient`.
