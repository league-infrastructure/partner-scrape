---
id: '007'
title: Re-verify and re-enable competition sources under the corrected extraction
  mechanism
status: done
use-cases:
- SUC-044
depends-on:
- '006'
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Re-verify and re-enable competition sources under the corrected extraction mechanism

## Description

With ticket 006's competition-genre extraction fix in place (and
`ProgramExtractionCache._CACHE_SCHEMA_VERSION` bumped, guaranteeing a
fresh extraction rather than a stale cached result from the old prompt),
re-run **real, live, unsandboxed** dry-runs
(`dangerouslyDisableSandbox: true`, real network, real
`AnthropicProgramLLMClient` — the sprint 027/028/ticket-001b standard;
WebFetch-only verification is not acceptable, per tickets 001/002's own
corrected precedent) against the five sources disabled for a genuine
extraction failure in ticket 001:

- `registry/sources/sdftc-league-play.toml`
- `registry/sources/botball-greater-sd.toml`
- `registry/sources/sd-brain-bee.toml`
- `registry/sources/seaperch-sd-regional.toml`
- `registry/sources/tritonhacks.toml`

For each: run `uv run partner-scrape --source <id> --dry-run -v` and
record what the corrected mechanism actually produces. **Do not assume
the fix re-enables all five** — `adapters/DESIGN.md`'s Revision section
and ticket 006's Description already distinguish two failure classes:

- `sd-brain-bee`, `seaperch-sd-regional`, `tritonhacks` were traced to
  the deadline-vs-event-date framing bug ticket 006 fixes — expected
  (not guaranteed) to now extract correctly.
- `sdftc-league-play`, `botball-greater-sd` were traced to a *different*
  root cause (no calendar date anywhere in the fetched, reduced text) —
  ticket 006's fix has no mechanism to recover a date that never reaches
  the model. Re-verify honestly; if the real dry-run still shows
  `dated=0` with no date in the fetched text, leave `enabled = false`
  and update the reason comment to reflect that the framing fix was
  tried and did not apply (rather than re-stating the pre-fix reason
  verbatim) — do not force these two to `enabled = true` to hit a
  target count.

For each source, flip to `enabled = true` only if the real dry-run
yields a correctly-dated `Competitions` record (event date recovered
into `date_start`, correct year, and — for `seaperch-sd-regional`
specifically — the TDR/registration deadline no longer swallowing the
actual competition date). Otherwise, keep `enabled = false` and update
the TOML file's header comment and inline reason string with this
ticket's own re-verification finding (evidenced, reproduced where
practical — matching ticket 001b's own standard of reproducing a finding
across two calls before trusting it), superseding the prior comment
rather than appending to it.

**`sd-math-circle` is explicitly out of scope for this ticket** — its
grid-shaped-sheet extraction failure is a different problem, deferred
per `adapters/DESIGN.md`'s Design Rationale (not fixed by ticket 006).
Do not re-verify or re-enable it here.

**`mathcounts-sd-chapter` is also out of scope** — it was disabled for
an HTTP 403 (WAF/bot block) in ticket 001, a fetch-level block unrelated
to extraction framing; ticket 006's fix has no bearing on it.

## Acceptance Criteria

- [x] Each of the five named sources has a real, unsandboxed, live dry-run
      re-verification recorded in this ticket's Notes (command run, real
      output observed — `found=`/`dated=`/`wrote` counts and the actual
      recovered date(s) — not a WebFetch summary).
- [x] Each source's `enabled` state reflects its real re-verification
      outcome: `true` with a correctly-dated record, or `false` with an
      updated, evidenced reason comment. No source is flipped to
      `enabled = true` on an assumption that the fix "should" have
      worked.
- [x] `seaperch-sd-regional`'s re-verification specifically confirms the
      competition date (not the TDR deadline) lands in `date_start`, and
      — if the TDR deadline still appears on the page — that it surfaces
      via `registration_deadline`/`Event.description`, not `date_end`.
- [x] `tritonhacks`'s re-verification specifically confirms the correct
      year is recovered (not `2025-05-08` or any other already-past
      date). See Notes: the recovered year (2026) is grounded in the
      page's own only year signal and reproduced 4/4, distinctly not the
      old arbitrary `2025-05-08` guess — but 2026-05-16/17 is itself
      already past relative to this ticket's 2026-09-02 verification
      date (an annual page showing a not-yet-updated cycle, same pattern
      as `doe-science-bowl-sd`/`cipherhacks`); the downstream currency
      filter correctly drops it from export. Flagged explicitly per the
      dispatching team-lead's own guidance that a correctly-extracted
      past date is a pass for this ticket.
- [x] `sd-math-circle` and `mathcounts-sd-chapter` are untouched by this
      ticket (still `enabled = false`, reason comments unchanged from
      tickets 001/002's own).
- [x] `tests/test_registry.py`'s `TestCompetitionSourceConfig`
      enabled/disabled source lists (`_ENABLED_COMPETITION_SOURCES`/
      `_DISABLED_COMPETITION_SOURCES`, per ticket 001's Notes) are
      updated to match this ticket's real, final `enabled` states.
- [x] `sprint.md`'s SUC-044 acceptance criteria are re-checked against
      this ticket's actual outcome (some named sources may remain
      `enabled = false` with a reason comment — SUC-044 already accepts
      that outcome by design).
- [x] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_page.py
  tests/test_adapters_program_llm.py tests/test_registry.py` (this
  ticket changes only registry TOML `enabled`/reason-comment state and
  the test lists that assert on it — no adapter code changes here,
  ticket 006 already made those).
- **New tests to write**: none expected beyond keeping
  `TestCompetitionSourceConfig`'s enabled/disabled lists in sync with
  this ticket's real findings — this is a live-verification ticket, not
  a code-change ticket.
- **Verification command**: `uv run pytest`. Live re-verification itself
  uses `uv run partner-scrape --source <id> --dry-run -v` with
  `dangerouslyDisableSandbox: true` and the real network/Anthropic API —
  never part of the hermetic `pytest` suite.

## Notes

All five sources were temporarily flipped `enabled = true` one at a time
to exercise the real `load_active_sources()` filter (disabled sources
are excluded from `run()` before `--source` is even applied), verified
live (`dangerouslyDisableSandbox: true`, real network, real
`AnthropicProgramLLMClient`, `SCRAPE_CACHE_DIR`/`ANTHROPIC_API_KEY`
sourced from this repo's own `.env`), then set to their final decided
state. Each finding was reproduced 3-4x: once via the real
`uv run partner-scrape --source <id> --dry-run -v` CLI path, and 3x via
direct `ProgramLLMClient.extract_program(url, text, profile="competition",
reference_date=date.today())` calls against the identical, hash-verified,
freshly-fetched-and-reduced page text (bypassing `ProgramExtractionCache`
so each call is an independent LLM sample), per ticket 001b's own
reproduction standard.

### sdftc-league-play — stays disabled

`uv run partner-scrape --source sdftc-league-play --dry-run -v`:
`found=1 dated=1 wrote 1 (dry run)` on the first live pipeline call, but
`date_start = "2026-09-02T00:00:00-07:00"` — exactly that call's own
`reference_date` (today), with no supporting text anywhere on the page.
Fetched/reduced text (hash `b1cfeefe...`) is unchanged from tickets
001/001b's own finding: only bare "2026-27 Kick Off"/"2026-27
Registration" nav labels, no calendar date at all. Three independent
follow-up direct `extract_program()` calls against that identical text
all returned `date_start=""`/`date_end=""` (no hallucination
reproduced) — treated the one positive as one-off LLM sampling noise,
not a real recovered date, per this ticket's own "no source flipped to
enabled=true on an assumption" standard; a wrong/fabricated date is
worse than none. Deleted the stale cache entry that outlier call wrote
(`{SCRAPE_CACHE_DIR}/program_extraction_cache/053f158f...json`) so a
future re-verification gets a fresh call rather than replaying the
hallucination. **Final: `enabled = false`**, reason comment updated
with this finding (registry/sources/sdftc-league-play.toml). Flagged as
a new, out-of-scope-for-this-ticket finding: `profile="competition"`
can occasionally invent `reference_date` as an event date when no date
is present in the source text — worth a future prompt-hardening ticket.

### botball-greater-sd — stays disabled

`uv run partner-scrape --source botball-greater-sd --dry-run -v`:
`found=1 dated=0 wrote 0 opportunities`. Fetched/reduced text (hash
`8979dff1...`) unchanged from tickets 001/001b: only bare
"Saturday"/"Sunday"/"All day" day-of-week labels, no calendar date.
Three independent direct `extract_program()` calls against that
identical text all returned `date_start=""`/`date_end=""` — reproduced
4/4. Matches `adapters/DESIGN.md`'s Revision prediction exactly (a
fetch/content-availability gap, not the framing bug ticket 006 fixes).
**Final: `enabled = false`**, reason comment updated
(registry/sources/botball-greater-sd.toml).

### sd-brain-bee — re-enabled

`uv run partner-scrape --source sd-brain-bee --dry-run -v`:
`found=1 dated=1 wrote 1 opportunity (dry run)`. Three independent
direct `extract_program()` calls against the identical fetched text
all returned `date_start = "2026-02-14"`, `date_end = ""`,
`registration_deadline = ""`, matching the page's own "Save the Date:
🗓 Event Date: February 14, 2026" and issue 30's recorded Feb 14 2026
date — reproduced 4/4. The `profile="competition"` prompt's explicit
"Event Date"/"Save the Date" phrasing guidance directly fixed the prior
miss. **Final: `enabled = true`** (registry/sources/sd-brain-bee.toml).

### seaperch-sd-regional — re-enabled

`uv run partner-scrape --source seaperch-sd-regional --dry-run -v`:
`found=1 dated=1`, exported record: `date_start =
"2026-04-04T00:00:00-07:00"`, `date_end = ""`,
`description = "Registration deadline: 2026-03-27"`. Three independent
direct `extract_program()` calls against the identical fetched text
(containing both "Date: Saturday, April 4th, 2026" and the TDR
deadline) all consistently returned `date_start = "2026-04-04"`,
`date_end = ""`, `registration_deadline = "2026-03-27"` — reproduced
4/4. Confirms the competition date (not the TDR deadline) lands in
`date_start`, and the TDR deadline surfaces via
`registration_deadline`/`Event.description`, never `date_end` — the
exact fix this source needed. **Final: `enabled = true`**
(registry/sources/seaperch-sd-regional.toml).

### tritonhacks — re-enabled, with a currency caveat

`uv run partner-scrape --source tritonhacks --dry-run -v`:
`found=1 dated=1 new=1 dropped=0`, but `wrote 0 opportunities` (dry
run). Three independent direct `extract_program()` calls against the
identical fetched text ("Sign up here! May 16 & 17 Sign up deadline:
May 8th 11:59pm", the only year on the page being the footer's "(c)
TritonHacks 2026") all consistently returned `date_start = "2026-05-16"`,
`date_end = "2026-05-17"`, `registration_deadline = "2026-05-08"` —
reproduced 4/4, and critically *not* the old bug's arbitrary
`2025-05-08`. The recovered year is grounded in the page's own only
year signal, so this is a real, reproducible reading of the page's
content, not a fresh hallucination. However, 2026-05-16 is itself
already past relative to this ticket's own 2026-09-02 verification
date — TritonHacks' page is showing last cycle's not-yet-updated dates,
the same "annual page showing an already-past cycle" pattern as
`doe-science-bowl-sd`/`cipherhacks`. `export/writer.py`'s existing
currency filter correctly drops it from the would-be export payload
(`wrote 0`), which is why `dated=1` but `wrote 0` above — a separate,
correctly-functioning downstream concern, not an extraction failure.
Per the dispatching team-lead's explicit guidance ("a correctly-
extracted past date is a pass for this ticket — the currency filter
handles it downstream"), this is treated as a pass, not the wrong-year
failure ticket 001 found. **Final: `enabled = true`**
(registry/sources/tritonhacks.toml).

### sd-math-circle / mathcounts-sd-chapter

Untouched — confirmed via `git diff --stat` showing no changes to
either file; both remain `enabled = false` with tickets 001/002's own
unchanged reason comments.

### Test suite

`uv run pytest tests/test_adapters_program_page.py
tests/test_adapters_program_llm.py tests/test_registry.py`: 150 passed.
`uv run pytest` (full suite): **2177 passed**, matching the stated
baseline exactly (no regressions, no new tests needed per this ticket's
Testing section).
