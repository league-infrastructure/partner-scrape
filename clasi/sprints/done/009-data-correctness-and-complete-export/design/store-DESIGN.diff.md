---
source_file: store-DESIGN.md
source_hash: 11f1994d28b23d6f69ce2d3ad6ccdec94e79973476aa4edb0263e7f80f343059
---
# Diff: store-DESIGN.md

Comparison of the sprint overlay copy of `store-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- store-DESIGN.md (pristine)
+++ store-DESIGN.md (current)
@@ -29,6 +29,13 @@
 `identity` is `sha256` of `Event.identity_key()`'s parts joined by `|`. `data` is the
 whole `Event` serialized to JSON. `content_hash` is `enrich.cache.content_hash(event)` —
 reused verbatim, not reimplemented.
+
+**Sprint 009 note.** `_event_to_dict`/`_event_from_dict`'s stated intent is to cover
+*every* `Event` field (see Design below); this sprint adds `opportunity_type` to that
+serialization the same run it adds the field to `Event` itself (`model.py`), so the new
+field does not become a second instance of the pre-existing `Event.trusted` gap (see Open
+Questions) the moment it's introduced. Fixing the *existing* `trusted` gap is explicitly
+out of this sprint's scope — see Open Questions.
 
 Methods: `upsert(events, *, seen_at)`, `all_events()`, `prune_past(today)`,
 `prune_unseen(cutoff)`, `count()`, `close()`, and context-manager support. `":memory:"`
@@ -94,6 +101,18 @@
 identity and hash functions is deliberate; sharing storage would not work, because their
 lifecycles differ.
 
+**Relationship to the new `export/partner_log.py` (sprint 009) — not the same store under
+a different name.** Both are "durable, cross-run" persistence, which invites the question
+of why sprint 009 built a second one instead of finally wiring this one in. They persist
+different *layers* of the pipeline for different *reasons*: this store keeps raw,
+pre-normalization `Event`s keyed by acquisition identity, so a future run could skip
+re-crawling. `export/partner_log.py` keeps finished, post-dedup `Opportunity`s keyed by
+publish identity, so a published event is never lost. Using this store to also serve the
+publish-persistence need would put `Opportunity`-shaped concerns (partner slugs, published
+content hashing) into a module whose whole reason to exist is being agnostic about what
+`normalize/` will later do with its rows — and would still leave this store unwired for
+its own stated purpose. See `export/DESIGN.md`'s matching entry for the full comparison.
+
 **How it would be wired.** The intended shape is: `pipeline.run()` upserts each source's
 events after adapter collection, prunes, and hands `all_events()` (rather than only this
 run's events) to `normalize.run()` — so a source that failed or was skipped this run still
@@ -130,7 +149,11 @@
   and is covered by tests, but no production code path constructs it.
 - `_event_to_dict` does not serialize `Event.trusted`, so a round-tripped event loses its
   trusted flag and would become subject to the relevance gate it is supposed to bypass.
-  This must be fixed before the store is wired in.
+  This must be fixed before the store is wired in. **(Still true after sprint 009.)** This
+  sprint added parity for the *new* `opportunity_type` field so it doesn't create a second
+  instance of this same gap, but deliberately did not retroactively fix the pre-existing
+  `trusted` gap — that is unrelated to this sprint's two issues and is better filed as its
+  own follow-up.
 - No schema migration path. Adding a field to the persisted shape currently means
   rebuilding the database.
 - No concurrency story. A single SQLite connection is held per `EventStore`; the pipeline
```
