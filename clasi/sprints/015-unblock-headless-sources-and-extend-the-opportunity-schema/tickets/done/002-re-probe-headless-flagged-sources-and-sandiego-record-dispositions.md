---
id: '002'
title: Re-probe headless-flagged sources and sandiego; record dispositions
status: done
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
issue: 37-headless-xml-fetch-and-sitemap-namespace-bugs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Re-probe headless-flagged sources and sandiego; record dispositions

## Description

With ticket 001's two fixes merged, re-probe live every source whose
zero-yield disposition was blocked by either bug and record a current,
evidence-backed disposition for each:

- The 9 headless-flagged sources from sprint 014 ticket 002:
  `climate-science-alliance`, `escondido-creek-conservancy`, `gsdsef`,
  `lajollalibrary`, `sandiego-cv-aopsacademy`, `sdrvc`,
  `techadventurecamp`, `titanbot`, `xplorstem`.
- `sandiego` (`sandiego.edu`), currently disabled with the sitemap
  namespace bug as its recorded reason.

This is a live-diagnosis ticket, matching sprint 014 ticket 003's own
methodology: probe first, then update the registry to match reality,
not the other way around.

## Acceptance Criteria

- [x] Each of the 10 sources is individually re-probed live
      (`partner-scrape --source <id> --dry-run -v`) after ticket 001's
      fixes, not lumped into a generic note.
- [x] A source that now yields real, dated records is re-enabled
      (`enabled = true`) with its new live yield count recorded in the
      TOML's addendum comment or this ticket's Notes.
- [x] A source that still yields nothing keeps `enabled = false`; if
      the root cause has changed (no longer the fetch/sitemap bug),
      the disabled-reason comment is updated to the new, accurate
      cause.
- [x] `sandiego` specifically is re-probed and its disposition
      resolved (re-enabled, or disabled with an updated, non-stale
      reason).
- [x] No source is deleted — `enabled = false` with an inline reason
      comment remains the only mechanism used, preserving history
      (matching `jointheleague.toml`/`olivewood-gardens.toml`'s
      existing convention).
- [x] Full test suite stays green; live probing is a diagnosis step,
      not a committed test.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`); registry
  loader tests to confirm every edited TOML still parses.
- **New tests to write**: none expected purely from TOML disposition
  edits — the existing registry loader tests already cover generic
  parsing. If live probing surfaces a genuine adapter-level bug
  distinct from the two ticket 001 already fixed, flag it for a
  follow-up rather than silently expanding this ticket's scope
  (matching sprint 014 ticket 003's own precedent).
- **Verification command**: `uv run pytest`. Live probing uses
  `partner-scrape --source <id> --dry-run -v` — not committed as a
  test.

## Implementation Plan

**Approach**: Per-source, live-probe-then-record, identical in shape
to sprint 014 ticket 003. Run each of the 10 sources through the real
pipeline post-fix, compare the result against its current TOML
disposition, and update only what changed.

**Files to modify**:
- `partner_scrape/registry/sources/climate-science-alliance.toml`,
  `escondido-creek-conservancy.toml`, `gsdsef.toml`,
  `lajollalibrary.toml`, `sandiego-cv-aopsacademy.toml`, `sdrvc.toml`,
  `techadventurecamp.toml`, `titanbot.toml`, `xplorstem.toml`,
  `sandiego.toml` — disposition updates only.

**Testing plan**: see Testing above.

**Documentation updates**: none expected beyond this ticket's own
Notes recording each source's new disposition and yield.

## Notes (2026-08-30 live re-probe results)

All 10 sources re-probed via `--dry-run --no-enrich --source <id> -v`
against a live network, post ticket-001. Two full batches were run: an
initial batch against the shared production `SCRAPE_CACHE_DIR`, then a
second, clean-cache batch (`SCRAPE_CACHE_DIR` pointed at a scratch
directory) per-source to rule out any cache contamination — see
Deviations below for why. Numbers below are from the clean-cache
batch, the authoritative one.

| Source | Before (sprint 014-003 disposition) | After (live re-probe) | found / dated | Disposition |
|---|---|---|---|---|
| climate-science-alliance | headless XML bug: "did not parse" | fixed; real sitemap XML parses | 1 / 0 | `enabled = true` (unchanged) |
| escondido-creek-conservancy | headless XML bug: `net::ERR_ABORTED` | fixed; real events discovered | 7 / 6 | `enabled = true` (unchanged) |
| gsdsef | headless XML bug: "did not parse" | fixed | 3 / 2 | `enabled = true` (unchanged) |
| lajollalibrary | headless XML bug: `net::ERR_ABORTED` | fetch fixed; site has no event-shaped URLs | 0 / 0 | `enabled = true` → **`false`** (reachable, no matching content) |
| sandiego-cv-aopsacademy | headless XML bug: "did not parse" | fixed; full course catalog discovered | 50 / 0 | `enabled = true` (unchanged) |
| sdrvc | headless XML bug: "did not parse" | fixed; all 3 events dated | 3 / 3 | `enabled = true` (unchanged) |
| techadventurecamp | headless XML bug: "did not parse" | fixed; strongest yield of the batch | 72 / 43 | `enabled = true` (unchanged) |
| titanbot | headless XML bug: `net::ERR_ABORTED` | fetch fixed; site has no event-shaped URLs | 0 / 0 | `enabled = true` → **`false`** (reachable, no matching content) |
| xplorstem | headless XML bug: `net::ERR_ABORTED` | fixed | 1 / 0 | `enabled = true` (unchanged) |
| sandiego | sitemap namespace bug: 0 URLs from a 0.84-namespaced sitemap | fixed; namespace-agnostic fallback recovers real content | 60 / 0 | `enabled = false` → **`true`** |

Net effect: 8 of 10 sources now enabled (was 9 headless enabled +
`sandiego` disabled = 9 of 10); `lajollalibrary` and `titanbot` newly
disabled (fetch bug fixed, but genuinely no event/program content on
either site); `sandiego` newly enabled (namespace bug fixed, 60 real
URLs recovered, including the exact `alumni/events/...` pages the
sprint 014 root-cause writeup already named live).

`dated=0` on several enabled sources (climate-science-alliance,
sandiego-cv-aopsacademy, xplorstem, sandiego) reflects `--no-enrich`
skipping LLM date extraction, or the discovered URL being a listing/
index page rather than an individual dated event page — an
extraction-quality question, not a discovery/fetch failure, and out
of this ticket's scope.

## Deviations / Findings for Follow-up (2026-08-30)

- **Live network flakiness on the first probe batch, not a code
  regression.** The first full batch (10 sources, shared production
  cache) showed `climate-science-alliance`, `gsdsef`, and `sdrvc` as
  still zero-yield with the exact pre-fix symptom (Chromium
  XML-viewer-wrapped body for `climate-science-alliance`'s
  `sitemap.xml`, confirmed by inspecting the on-disk cache entry
  directly). Root-caused via a targeted reproduction script
  (`PlaywrightFetcher().get(url)` called directly, then again
  interleaving a `robots.txt` navigation before each raw `.xml`
  fetch exactly as the real `PoliteFetcher` → `robots.py` call
  sequence does): both reproductions returned the correct, real raw
  XML every time — the fix code path (`_looks_like_raw_resource` →
  `_get_raw_response` via `page.request.get()`) is correct. A second
  live probe of the same three sources (production cache, after
  deleting the one corrupted cache entry) and a third, fully
  independent probe of all 10 sources against a clean scratch
  `SCRAPE_CACHE_DIR` both returned real, non-zero yields for all
  three. Conclusion: this was live network/CDN flakiness on the very
  first hit against those specific Wix-hosted sites (not reproducible
  on demand, not tied to any specific code path), not a bug in
  ticket 001's fix. Recorded here rather than silently discarded,
  per this ticket's own "flag genuine findings" testing guidance —
  no code change made, out of scope by the ticket's own boundary.
- **`sandiego` required a temporary `enabled = true` flip to probe.**
  `--source <id> --dry-run` silently no-ops for a disabled source
  (`load_active_sources()` filters `enabled: false` before the
  `--source` match), so there is no way to live-probe a currently-
  disabled source without enabling it first. Flipped `enabled = true`
  temporarily, probed, then finalized the TOML with the real
  evidence-backed comment (see the file's own re-probe addendum) —
  the temporary flip and the final disposition are the same value
  here since the probe confirmed real yield, so no separate revert
  was needed.
- **`xplorstem`'s `store-products-sitemap.xml` child sitemap fails
  XML parsing** (`undefined entity`, confirmed via a direct raw fetch:
  a genuine unescaped `&` in the live document, live-verified via
  `curl` too) — this is pre-existing, site-side malformed XML on
  xplorstem's own Wix product feed, unrelated to either bug this
  sprint fixed. `discovery/sitemap.py`'s existing per-child
  `ET.ParseError` handling already logs a warning and skips it
  gracefully (`_parse_sitemap_index()`), so no code behavior needs to
  change; noted in `xplorstem.toml`'s addendum for the record.
