---
source_file: registry-DESIGN.md
source_hash: 509fad29a483529711ab48f0723e59135cbea2e758107d6bc74ae87701a65eb6
---
# Diff: registry-DESIGN.md

Comparison of the sprint overlay copy of `registry-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- registry-DESIGN.md (pristine)
+++ registry-DESIGN.md (current)
@@ -3,6 +3,37 @@
 **Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — sprint 029 competition-genre extraction fix)
+
+Tickets 001/002's real (not WebFetch-only) live-verification found that
+most of this sprint's registered competition sources' extraction was
+wrong, not merely site-blocked — traced to `adapters/program_llm.py`'s
+prompt being written for sprint 027's application-window program genre,
+not for single-dated-event competition pages. The full finding, the
+corrected extraction mechanism, and the Design Rationale for why it
+needed no registry-level change are documented in
+`adapters/DESIGN.md`'s own "Revision (2026-09-02 — sprint 029
+competition-genre extraction fix)" section — this file is cross-
+referenced from there rather than duplicated here.
+
+**No change to this document's own content below.** The mechanism
+decision this file's §4 Sprint 029 Design Rationale describes — every
+competition source registers through the existing `program_page`/
+`program_page_multi`/`program_listing` `adapter_type` family, with
+`config.opportunity_type = "Competitions"` where applicable — is
+unchanged and still accurate; the correction lives entirely inside how
+`adapters/` interprets that already-existing `config.opportunity_type`
+value (a new prompt profile, selected by data the registry already
+carries), not in any new registry schema, loader, or conventional
+`config` key. The sources this sprint's ticket 001 registered are
+exactly the files named in this document's existing Sprint 029
+paragraph below; their `enabled` states (3 enabled, 9 disabled as of
+tickets 001/002's correction) are tracked in each TOML file's own header
+comment and in `sprint.md`'s Tickets table, not restated here — this
+document describes the registration *mechanism*, not a live census of
+which sources currently pass verification, and re-verification is
+ticket 007's job (below), not a re-edit of this file.
 
 ## 1. Purpose
 
@@ -87,6 +118,43 @@
 roughly 15-20 new `program_page_multi` camp-marketing-page sources — see §5b's own sprint
 028 addendum for the full data-shape write-up. Same "no registry code change" story as
 sprint 027's addition above: every new value is dispatched entirely inside `adapters/`.
+
+**(Sprint 029)** San Diego's static-page competition/tournament calendar (issue 30) is
+registered using the exact three `adapter_type` values sprint 027/028 already shipped —
+zero new values, zero new conventional `config` keys. This sprint is the first real
+exercise of `adapters/DESIGN.md`'s own "reuse surface for sprints 029/030" note: roughly
+12 single-event pages (San Diego Regional Science Olympiad, SDFTC league play, SeaPerch,
+MATHCOUNTS SD chapter, DOE National Science Bowl SD regionals, Garibaldi Bowl, San Diego
+Brain Bee, Botball Greater SD, Congressional App Challenge, TritonHacks, CipherHacks, and
+SDCEC's Engineers Week awards where folded into its own multi-record entry) as
+`program_page` with `config.opportunity_type = "Competitions"`; San Diego Math Circle's
+public Google Sheet as one `program_page_multi` source (its several annual dated
+items — AMC, AIME, ARML, Math Kangaroo — read as N inline records off one fetched page,
+exactly the shape `program_page_multi` already handles); the SD Festival of Science &
+Engineering's `lovestemsd.org` (~35 DB-driven per-event pages) as one `program_listing`
+source, reusing the `config.link_selector` discovery escape hatch the ticket 006
+exception revision built if `EVENT_PATH_RE` doesn't match its card markup; and SDCEC's
+`/stem` curated list as its own `program_page_multi` source, with **no**
+`opportunity_type` override (its list mixes competitions with other STEM opportunity
+types, so each item keeps the LLM's own per-record classification — the same "no
+override, let the LLM decide" default `program_page`/`program_listing` already use when
+`config` sets none). CyberPatriot SD / SoCal Mayor's Cyber Cup is registered
+`enabled = false`, referencing issue 38 (`ndia-sd.org` needs the headless fetcher's
+still-missing settle wait), following the exact "disabled with a reason comment" triage
+convention sprint 014 established. GSDSEF and the SD Festival are this sprint's two
+"already a partner" checks: GSDSEF already has a `registry/sources/gsdsef.toml`
+registration (this sprint may edit its `config` in place to surface two specific dates
+it's missing, but adds no second file for it), while the SD Festival has **no** existing
+entry under any name — `usasciencefestival.toml` is a distinct, unrelated, already-
+disabled national organization, confirmed by a registry-wide grep before registering
+`lovestemsd.org` fresh — so no dual-registration risk applies to either, by construction
+rather than by luck. SDCEC additionally already has a `registry/hubs/sdcec-stem.toml`
+discovery-only hub (sprint 024); this sprint's new `registry/sources/sdcec.toml` entry
+does not touch it — a hub and a source for the same org are two different, already-
+separate catalogs (§3's physical-separation invariant), not the same
+same-org-registered-twice-*within*-`sources/` risk the GSDSEF/SD-Festival check above
+guards against. No schema, loader, or catalog-separation change for any of it — every
+new file is dispatched entirely inside `adapters/`, unchanged.
 
 ## 2. Orientation
 
@@ -173,6 +241,65 @@
 
 **`tomllib`, not a dependency.** Standard library since Python 3.11; the package requires
 3.13.
+
+**(Sprint 029) Design Rationale: reuse the sprint 027/028 LLM-extraction mechanism for
+competitions, rather than either of issue 30's own proposed mechanisms.**
+- *Decision*: every static-page competition/tournament source registers through the
+  existing `program_page`/`program_page_multi`/`program_listing` `adapter_type` family,
+  with `config.opportunity_type = "Competitions"` where the page is single-purpose (left
+  unset, for LLM classification, where a page's items span more than one type — SDCEC,
+  the SD Festival).
+- *Context*: issue 30 itself proposed two candidate mechanisms — (a) plain
+  `registry/sources/` entries using `listing_html` with "generous extraction," or (b) a
+  small standalone curated-source file (org, URL, expected month, last-verified) with its
+  own LLM date-extraction pass — written before sprint 027/028 had shipped.
+- *Alternatives considered*: (a) and (b) above.
+- *Why this choice*: (a) is a non-fit — `listing_html`'s deterministic `extract/` ladder
+  recovers generic markup-structured fields (title, date, location); it has no notion of
+  the deadline-first {audience, eligibility, open/closed} shape these annual competition
+  pages need, and approximating one would mean adding real code to `extract/`'s ladder.
+  (b) describes, feature for feature, a parallel hand-rolled reimplementation of what
+  `registry/sources/*.toml` plus `program_page`'s LLM extraction call already does —
+  building a second, competition-specific curated-source mechanism when a generalized one
+  already exists (and was explicitly designed for this reuse — `adapters/DESIGN.md`'s own
+  "Reuse surface for sprints 029/030" note) would be needless duplication of a solved
+  problem, the mirror image of the "speculative generality" this codebase's architecture
+  principles already warn against. The chosen mechanism already carries deadline-first
+  fields, `is_open`'s closed/full/sold-out semantics (sprint 028's generalization covers
+  exactly the "registration opens ~Sept" disposition these pages describe), the
+  `opportunity_type` override precedent, and the collapse/dedup bypass these annual,
+  non-recurring records need — for zero new code.
+- *Consequences*: this sprint adds registry data only. The one residual judgment call it
+  carries forward is the same one sprint 027 named and never fully closed for
+  COSMOS/OPTIMUS/ENLACE: `kind in PROGRAM_EXTRACTION_KINDS` records bypass cross-source
+  dedup by design, so a competition registered by accident under two different source
+  files would publish twice with no automatic catch — mitigated here by the GSDSEF/SD
+  Festival dual-registration check and the SDCEC cross-check (see `sprint.md`'s SUC-047),
+  not eliminated as a general risk.
+
+**(Sprint 029) Design Rationale: no new annual-review/recheck mechanism.**
+- *Decision*: a registered competition source is checked for freshness exactly the same
+  way every other source is — the existing weekly scheduled run re-fetches it
+  unconditionally — plus the registry's existing convention of a live-verification-date
+  comment in the TOML file header (already used throughout `sources/`, e.g. `gsdsef.toml`,
+  `sdcec-stem.toml`).
+- *Context*: issue 30 and the roadmap `sprint.md` both raise "annual review" as something
+  these slow-changing, once-a-year pages need.
+- *Alternatives considered*: a per-source `last_verified`/`next_check_date` field read by
+  `pipeline.run()` to skip or flag a source outside its expected window.
+- *Why this choice*: this is the identical problem sprint 028 already solved for Fleet's
+  seasonal camp page, and the identical reasoning applies unchanged — the pipeline already
+  re-checks every enabled source on every scheduled run, so there was never a technical gap
+  in *re-checking*; a competition page whose organizer hasn't yet posted next year's dates
+  is handled the same way an off-season camp page is (an empty or stale extraction, not an
+  error), and a page whose dates have simply gone stale is filtered at export time by the
+  existing `DEADLINE_FIRST_TYPES` currency rule. Building registry-level scheduling
+  machinery for a problem the existing cron already covers would repeat the exact
+  speculative-generality judgment sprint 028's own Design Rationale already rejected for
+  the same shape of ask.
+- *Consequences*: identical to sprint 028's accepted gap — an annual page that hasn't yet
+  updated to the new cycle's dates is indistinguishable in `observability/`'s yield report
+  from a broken source. Not solved here.
 
 ## 5. Interfaces
 
@@ -286,3 +413,8 @@
   "the same organization registered under two source files." Not solved here; caught only
   by author discipline and code review, same as the sprint 027 COSMOS/OPTIMUS/ENLACE risk
   this mirrors.
+- **(Sprint 029)** Same unenforced-by-tooling risk as the sprint 028 entry immediately
+  above, applied to this sprint's own dual-registration checks (GSDSEF, the SD Festival,
+  SDCEC's hub-plus-source pair) — all verified by a manual registry-wide grep during
+  planning, not an automated check; nothing in `registry/` itself would catch a *future*
+  edit re-introducing any of them.
```
