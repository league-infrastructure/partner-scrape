# Store

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** in-flux

---

## 1. Purpose

`store/` is a durable, cross-run SQLite table of canonical `Event`s, keyed by acquisition
identity. It exists to be the foundation for incremental, self-updating scraping: a
future run should be able to ask "what do we already know?" before deciding what to
re-crawl. It is a subsystem because persistence of the canonical record is a distinct
concern from every stage that produces or consumes one, and because the store's opinions
— about identity and about row lifecycle — must be stated in exactly one place.

**Status note, stated up front: this subsystem is built and tested but is not wired into
the pipeline.** Nothing in `pipeline.py` or `cli.py` imports `EventStore`; no production
run reads from or writes to it. Everything below describes a working, unused component.

## 2. Orientation

One class, `EventStore(db_path=None)`, wrapping a single SQLite table:

```
events(identity TEXT PRIMARY KEY, source_id TEXT, data TEXT,
       content_hash TEXT, first_seen TEXT, last_seen TEXT)
```

`identity` is `sha256` of `Event.identity_key()`'s parts joined by `|`. `data` is the
whole `Event` serialized to JSON. `content_hash` is `enrich.cache.content_hash(event)` —
reused verbatim, not reimplemented.

**Sprint 009 note.** `_event_to_dict`/`_event_from_dict`'s stated intent is to cover
*every* `Event` field (see Design below); this sprint adds `opportunity_type` to that
serialization the same run it adds the field to `Event` itself (`model.py`), so the new
field does not become a second instance of the pre-existing `Event.trusted` gap (see Open
Questions) the moment it's introduced. Fixing the *existing* `trusted` gap is explicitly
out of this sprint's scope — see Open Questions.

Methods: `upsert(events, *, seen_at)`, `all_events()`, `prune_past(today)`,
`prune_unseen(cutoff)`, `count()`, `close()`, and context-manager support. `":memory:"`
is accepted for tests.

## 3. Constraints and Invariants

- **The store keeps *records*, not *the dataset*.** It performs no cross-source dedup, no
  recurrence collapsing, and no upcoming-only filtering. That is `normalize/`'s job,
  applied to whatever `all_events()` returns. Building any of it in here would give the
  system two disagreeing answers to "what is the current opportunity set".
- **Identity mirrors `model.Event.identity_key()` exactly** — the same "have we already
  seen this exact record from this source" question, hashed the same way `enrich/cache.py`
  hashes it. If the two drift, a run's enrichment cache and its event store would
  disagree about which rows are the same record.
- **`content_hash` is imported from `enrich.cache`, never reimplemented.** Same reason:
  two notions of "did the meaningful content change" must not drift apart.
- **`first_seen` never changes on upsert; `last_seen` always does.** They track a row's
  acquisition lifecycle independently of its content, which is what makes `prune_unseen`
  meaningful. Overwriting `first_seen` would erase the only record of how long the system
  has known about an event.
- **`prune_past` always keeps undated rows.** An `Event` with no `start` and no `end`
  cannot be judged stale by date, and it may acquire one on a later run when a source
  fills in its calendar. Treating undated as expired would silently discard exactly the
  records most likely to be repaired later.
- **`prune_past` judges by `end`, falling back to `start`** — the same precedence
  `export/writer.py` uses for its current-or-upcoming filter, so the two cannot disagree
  about which events are in the past.
- **The two prune operations are separate and answer different questions.**
  `prune_past(today)` removes events whose *date* has passed; `prune_unseen(cutoff)`
  removes rows *no run has observed* since a cutoff timestamp — i.e. records a source
  stopped listing. Merging them would conflate "the event happened" with "the source
  dropped it".
- **Deliberate non-goal — no schema migration machinery.** `CREATE TABLE IF NOT EXISTS`
  is the whole story. Adding a column to a populated database is currently an unhandled
  case; solve it when the store is actually wired in and has data worth preserving.

## 4. Design

**Why SQLite.** Standard library, single file, no server, transactional, and directly
inspectable with `sqlite3` on the command line. The alternative already in use elsewhere
— one JSON file per record, as `fetch/cache.py` and `enrich/cache.py` do — is fine for
lookup-by-key but cannot answer the queries this store exists for (prune by date, prune
by staleness, count, enumerate all).

**Why the `Event` is stored as a JSON blob rather than exploded into columns.** The
promoted columns are exactly the ones the store's own opinions need: `identity` (primary
key), `source_id` (attribution), `content_hash` (change detection), and the two
timestamps (lifecycle). Everything else is opaque payload. Exploding the full ~25-field
`Event` into columns would tie the schema to a record shape that other subsystems own and
change, and would require a migration for every field addition — for no query benefit,
since nothing filters on those fields.

**Serialization is explicit, not `dataclasses.asdict`.** `_event_to_dict` /
`_event_from_dict` are a hand-written, symmetric pair: datetimes become ISO strings,
`field_provenance`'s `Provenance` values become plain dicts. Explicitness is what makes
the round-trip testable field by field.

**Relationship to `enrich/cache.py`.** They are keyed identically and both track content
hashes, but they answer different questions. The enrichment cache remembers *"did we
already pay to enrich this content?"* and stores only the `EnrichmentResult`. The event
store remembers *the canonical Event itself*, accumulated across every run. Sharing the
identity and hash functions is deliberate; sharing storage would not work, because their
lifecycles differ.

**Relationship to the new `export/partner_log.py` (sprint 009) — not the same store under
a different name.** Both are "durable, cross-run" persistence, which invites the question
of why sprint 009 built a second one instead of finally wiring this one in. They persist
different *layers* of the pipeline for different *reasons*: this store keeps raw,
pre-normalization `Event`s keyed by acquisition identity, so a future run could skip
re-crawling. `export/partner_log.py` keeps finished, post-dedup `Opportunity`s keyed by
publish identity, so a published event is never lost. Using this store to also serve the
publish-persistence need would put `Opportunity`-shaped concerns (partner slugs, published
content hashing) into a module whose whole reason to exist is being agnostic about what
`normalize/` will later do with its rows — and would still leave this store unwired for
its own stated purpose. See `export/DESIGN.md`'s matching entry for the full comparison.

**How it would be wired.** The intended shape is: `pipeline.run()` upserts each source's
events after adapter collection, prunes, and hands `all_events()` (rather than only this
run's events) to `normalize.run()` — so a source that failed or was skipped this run still
contributes what it contributed last time. That change has not been made, and the
decision it implies (a failed source's stale data continuing to publish) has not been
taken.

## 5. Interfaces

### Exposes
- **`EventStore(db_path=None)`** — opens or creates the database (default
  `events.db`; `":memory:"` supported). Usable as a context manager; `close()` otherwise.
- **`.upsert(events, *, seen_at)`** — inserts or updates one row per event by identity.
  Sets `first_seen` on insert only; always updates `last_seen`, `data`, and
  `content_hash`.
- **`.all_events() -> list[Event]`** — every stored row, deserialized. No filtering, no
  ordering guarantee.
- **`.prune_past(today)`** — deletes rows whose effective date (`end`, else `start`) is
  before `today`. Undated rows are kept.
- **`.prune_unseen(cutoff)`** — deletes rows whose `last_seen` predates `cutoff`.
- **`.count() -> int`** — row count.

### Consumes
- **`Event`, `Provenance`, `IdentityKey` (from `model.py`)** — the record stored and its
  identity derivation. See the root `partner_scrape/DESIGN.md`.
- **`enrich.cache.content_hash`** — reused verbatim for change detection. See
  `enrich/DESIGN.md`.

Nothing consumes this subsystem today.

## 6. Open Questions / Known Limitations

- **Not wired into the pipeline.** This is the headline limitation. The component works
  and is covered by tests, but no production code path constructs it.
- `_event_to_dict` does not serialize `Event.trusted`, so a round-tripped event loses its
  trusted flag and would become subject to the relevance gate it is supposed to bypass.
  This must be fixed before the store is wired in. **(Still true after sprint 009.)** This
  sprint added parity for the *new* `opportunity_type` field so it doesn't create a second
  instance of this same gap, but deliberately did not retroactively fix the pre-existing
  `trusted` gap — that is unrelated to this sprint's two issues and is better filed as its
  own follow-up.
- No schema migration path. Adding a field to the persisted shape currently means
  rebuilding the database.
- No concurrency story. A single SQLite connection is held per `EventStore`; the pipeline
  runs eight source workers concurrently, so wiring this in requires deciding whether
  upserts happen per-worker (needing connection handling) or once on the main thread.
- The default database location (`events.db`, relative) is not routed through
  `config.py`, unlike every other on-disk artifact in the system.
- The central unresolved design question is policy, not mechanism: if a source fails this
  run, should its previously stored events still be published? Answering yes makes the
  site resilient to transient breakage; it also means a permanently dead source keeps
  publishing until someone notices. The store enables either answer and takes neither.
