---
source_file: adapters-DESIGN.md
source_hash: 8a7155a6e0a8d8f6429e3dcf0e708f84a302046762c7583f0608beae83fc5c28
---
# Diff: adapters-DESIGN.md

Comparison of the sprint overlay copy of `adapters-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- adapters-DESIGN.md (pristine)
+++ adapters-DESIGN.md (current)
@@ -1,8 +1,123 @@
 # Adapters
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 030 — `pd` extraction profile added) · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — sprint 030 educator-PD extraction profile)
+
+Issue 33 part 1's curated educator-PD program pages (UCSD CREATE, SD
+Science Project, UCSD Math Project, Code.org regional partner,
+CSTA-SD, SDSU CRMSE, Fleet educator workshops, Salk STEM Educators
+Summit, Zoo teacher workshops) register through the existing
+`program_page`/`program_page_multi`/`program_listing` mechanism, typed
+`Professional Development / Conferences` — the reuse surface this
+module's own `ProgramPageMultiAdapter` docstring already named as
+expected ("sprints 029 (competitions) and 030 (educator pages) are
+expected to register against directly with zero further adapter
+code"). That claim holds exactly as written for `discover()`/`fetch()`/
+the dispatch structure — no new adapter class, no new discovery logic.
+**It does not hold for the LLM extraction prompt**, and this revision
+exists because sprint 029's own Revision (above) is the direct
+precedent for why: reusing an existing profile's *wording* for a
+structurally different genre produces systematic, silent extraction
+errors, not merely site-specific quirks (`sd-brain-bee`,
+`seaperch-sd-regional`, `tritonhacks` — all three traced to
+framing/vocabulary mismatches, not fetch or model failures). This
+revision does the same live-verification-informed judgment sprint 029
+was forced into, up front, rather than repeating its optimism.
+
+**Why an educator-PD workshop/conference page is its own third genre,
+neither `"program"` nor `"competition"`.** An educator-PD page (a
+summit, a workshop series, a CSTA-SD chapter meeting) shares one
+structural property with the competition genre — its primary date is
+the event's own date, not an application-window open/close pair, so
+`"program"`'s framing ("the application window's open date" /
+"the application deadline") is the wrong lens here exactly as it was
+for `sd-brain-bee`. But it shares none of the competition genre's own
+vocabulary assumptions: `_FIELD_EXTRACTION_RULES_COMPETITION`'s date
+guidance explicitly steers the model toward "Event Date," "Competition
+Date," "Tournament Date," "Save the Date" phrasing and a
+"competition/tournament" framing sentence — vocabulary a PD workshop
+page does not use ("Register for our fall workshop," "RSVP by," "Summit
+registration closes"), and telling the model "this is a competition or
+tournament" when it plainly is not risks exactly the kind of
+label-primed misreading 029's own root-cause analysis diagnosed for the
+*other* direction (a program-shaped prompt on event-shaped content).
+**Design decision: a third `profile="pd"`, with its own system prompt
+pair, following the exact mechanical shape `profile="competition"`
+already established** — no `ProgramExtractionResult` schema change (the
+existing `date_start`/`date_end`/`registration_deadline`/`cost`/
+`eligibility`/`is_open`/`opportunity_type` fields already cover a PD
+event's shape: `date_start`/`date_end` for the workshop's own date(s),
+`registration_deadline` for a stated RSVP/registration cutoff distinct
+from the event date, `eligibility` for "K-12 STEM educators," grade
+band, or district restriction, `audience_grades` reused to hold an
+educator-audience descriptor like "K-5 teachers" or "STEM
+coordinators" rather than a student grade band). No
+`ProgramExtractionCache._CACHE_SCHEMA_VERSION` bump either — the
+stored-entry *shape* is unchanged, only which of three prompt variants
+produced it (see this section's Open Question below for the one real,
+pre-existing risk this raises).
+
+`ProgramLLMClient.extract_program`/`extract_programs`'s `profile`
+parameter's accepted values become `"program"` (default) |
+`"competition"` (sprint 029) | `"pd"` (this sprint) — a plain string,
+not a typed enum (matching this module's existing "small, hand-curated
+set, not worth over-typing" convention for comparable fields).
+`program_page.py`'s `_resolve_extraction_profile()` extends its
+existing single-branch check to a three-way one, still driven entirely
+by data the registry already carries, still with **no new registry
+`config` key**:
+
+```python
+def _resolve_extraction_profile(source: SourceConfig) -> str:
+    opportunity_type = source.config.get("opportunity_type")
+    if opportunity_type == "Competitions":
+        return "competition"
+    if opportunity_type == "Professional Development / Conferences":
+        return "pd"
+    return "program"
+```
+
+This is the same "select the prompt variant from the config override
+value every affected source's TOML already carries" mechanism sprint
+029 established, extended by one more `elif`-shaped case — not a new
+mechanism. Every existing `"program"`- and `"competition"`-profile
+source's behavior is byte-for-byte unchanged (neither branch's
+condition can newly match a pre-existing registration).
+
+**Reused verbatim, no new code:** `_extract_one_program()`/
+`_extract_many_programs()` (the HTML-reduction, cache lookup, and
+per-ref exception-isolation logic), `ProgramExtractionCache` itself,
+`_map_result_to_event()`'s date/eligibility/cost/opportunity_type
+mapping, and `ProgramListingAdapter`'s `config.link_selector` discovery
+path (ticket 006 exception revision) for any educator-PD listing page
+whose cards aren't `EVENT_PATH_RE`-shaped (a real possibility for
+CSTA-SD's or Fleet's own event-listing pages — registered per-source as
+needed, decided at registration time, not a mechanism change).
+`program_page_multi` is available for any educator-PD source whose
+page holds several session dates inline on one page rather than links
+to N separate detail pages (e.g. a CSTA-SD chapter's own upcoming-
+meetings list), the identical SIO-shape reuse this module's own
+docstring already anticipated for "sprint 030 (educator pages)."
+
+**Open question — pre-existing, not new to this revision, flagged
+here because this sprint is the second consumer to make it matter.**
+`ProgramExtractionCache`'s key is `(url, content_hash(body))` —
+`profile` is not part of the key (`program_cache.py`, unchanged by
+either this revision or sprint 029's). This has been true since sprint
+027 and is harmless for every source registered so far, because a
+given URL is registered under exactly one `config.opportunity_type`
+value for its whole life. It would stop being harmless only if a
+source's `opportunity_type` override were ever *changed* after a cache
+entry already exists for that URL under the old profile — the cache
+would silently serve the stale, wrong-profile result until the page's
+own content changes. Not a risk this sprint introduces or needs to fix
+(no educator-PD URL has ever been cached under a different profile),
+but worth a follow-up issue given two sprints have now added a profile
+without ever revisiting this — see this sprint's sprint.md Open
+Questions for the recommended follow-up.
 
 ## Revision (2026-09-02 — sprint 029 competition-genre extraction fix)
 
```
