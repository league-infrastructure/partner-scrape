---
source_file: registry-DESIGN.md
source_hash: 44a0dbf8e3a096e56e695f59e305c57574a333437011a387ef41fe473dd80bac
---
# Diff: registry-DESIGN.md

Comparison of the sprint overlay copy of `registry-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- registry-DESIGN.md (pristine)
+++ registry-DESIGN.md (current)
@@ -1,8 +1,66 @@
 # Registry
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 030 — Offering Registry catalog + educator-PD program-page registrations) · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 031 — four new ATS `adapter_type` values) · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — sprint 031 ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable)
+
+Four new `adapter_type` values register exactly like every prior
+adapter-family addition (sprint 016's `robotevents`, sprint 027's
+`program_page`/`program_listing`, sprint 028's `activenet_camps`/
+`campbrain`) — new `sources/*.toml` files, zero `schema.py`/`loader.py`
+change, since `config` stays an untyped dict and this module has no
+dependency on `adapters/`. See `adapters/DESIGN.md`'s own sprint 031
+section for what each adapter does with these keys.
+
+New conventional `config` keys, one set per adapter type:
+- **`workday`**: `tenant`, `site` (Workday's own path segments,
+  `POST /wday/cxs/{tenant}/{site}/jobs`), and `api_base` (Workday's
+  API host is sharded per tenant, e.g. `{tenant}.wd5.myworkdayjobs.com`
+  — unlike Greenhouse's single global default host, every Workday
+  source is expected to need its own `api_base`, confirmed live per
+  tenant rather than assumed from one shared default).
+- **`neogov`**: `agency` (which of the four `governmentjobs.com`
+  agencies a given registration targets) — pending this adapter type
+  actually existing; see `adapters/DESIGN.md`'s own sprint 031 note
+  that NEOGOV's real endpoint shape is unconfirmed and this sprint's
+  ticket may instead register the four agencies through the existing
+  `generic_html`/`listing_html` `adapter_type` if no structured
+  endpoint is found.
+- **`smartrecruiters`**: `company` (the SmartRecruiters company slug,
+  e.g. `ServiceNow`, matching the path segment in
+  `api.smartrecruiters.com/v1/companies/{company}/postings`).
+- **`workable`**: `account` (the Workable subdomain/account slug for
+  `apply.workable.com`).
+
+All four follow `greenhouse.py`'s/`lever.py`'s existing `board_token`/
+`company` precedent: one identifying config key (or two, for Workday's
+tenant/site pair) plus an optional `api_base` override, no schema
+change, `config` validated only implicitly by whether the adapter can
+use it.
+
+**Sony Interactive Entertainment** registers as a plain new
+`greenhouse` source (`config.board_token =
+"sonyinteractiveentertainmentglobal"`) — no new `adapter_type`, no new
+`config` key, the identical mechanism every existing Greenhouse-backed
+company source already uses (e.g. `gossamerbio.toml`'s own precedent,
+§1 above).
+
+**The six unconfirmed-ATS employers this sprint probes (Qualcomm,
+Solar Turbines, Teradata, BAE, General Atomics, Intuit) get no
+`sources/` entry from this sprint unless the probe finds one is
+already reachable through an *existing* adapter type** — see
+`adapters/DESIGN.md`'s own Design Rationale for why a probe ticket,
+not four speculative registrations against an assumed shape, is this
+sprint's scope for them. A probe finding that an employer is blocked or
+needs a credential is recorded in the ticket's own notes, not as a
+`registry/sources/` entry with `enabled = false` — there is nothing to
+disable that was never registered in the first place, unlike a
+previously-live source found broken (`DO_NOT_SCRAPE.md`'s own
+convention is for a site actively investigated and rejected, which
+does apply if a probe finds a real ToS/robots block worth recording
+there).
 
 ## Revision (2026-09-02 — sprint 030 educator layer and volunteer org profiles)
 
@@ -448,6 +506,14 @@
 Air & Space Museum and Helen Woodward are registered only as `activenet_camps` sources,
 not also as `program_page_multi` marketing-page sources, for the same
 dual-registration-avoidance reason.
+
+**(Sprint 031)** Four more `adapter_type` values, `workday`, `neogov`, `smartrecruiters`,
+and `workable` (`adapters/DESIGN.md`'s own sprint 031 section) — the second and third
+ATS-family additions after sprint 006's `greenhouse`/`lever`. New conventional `config`
+keys per type are listed in this document's sprint 031 Revision note above; same
+untyped-dict status, same "no schema validation for the contents of `config`" limitation
+(§6) applying identically. Sony Interactive Entertainment is a data-only addition to the
+existing `greenhouse` catalog, zero new mechanism.
 
 ## 6. Open Questions / Known Limitations
 
@@ -488,3 +554,16 @@
   SDCEC's hub-plus-source pair) — all verified by a manual registry-wide grep during
   planning, not an automated check; nothing in `registry/` itself would catch a *future*
   edit re-introducing any of them.
+- **(Sprint 031)** NEOGOV's four agency registrations may end up split across two
+  different `adapter_type` values (`neogov` for whichever agencies expose a structured
+  endpoint, `generic_html`/`listing_html` for whichever don't) if the ticket-level live
+  verification finds a mixed result — `adapters/DESIGN.md`'s own sprint 031 note already
+  flags this as a legitimate outcome, not a defect, but it is worth recording here too:
+  this document's own "one adapter, four agencies" framing (roadmap `sprint.md`) may not
+  hold exactly as stated once live evidence is in.
+- **(Sprint 031)** Workday's `api_base` is expected to differ per tenant (the API host is
+  sharded, e.g. `wd1`/`wd5`), unlike every other adapter type registered so far, where one
+  global default host (or none at all) covers every source. No cross-file consistency
+  check catches a copy-pasted wrong shard — same "no schema validation for the contents of
+  `config`" limitation (§6, above) as every other adapter-specific key, surfacing here as a
+  live 404/wrong-tenant response rather than a load error if gotten wrong.
```
