# Discovery

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** in-flux

---

## Revision (2026-09-02 — sprint 027 ticket 006 exception cycle)

This doc was not originally part of sprint 027's overlay (only `adapters/DESIGN.md`
was, since sprint 027's own architecture framed the two new adapter types as reusing
`discover_via_listing` unchanged). Ticket 006's live verification found that reuse
insufficient for either of its two real listing sources — see `adapters-DESIGN.md`'s
own Revision note for the full finding — so this sprint now also adds one new function
here: `listing.py` gains `discover_via_selector(source, fetcher)`, a CSS-selector-driven
sibling to the existing `discover_via_listing(source, fetcher)`, seeded into this
overlay for that reason. See §2/§4/§5 below.

## 1. Purpose

`discovery/` answers "which URLs are worth fetching?" — the step before any extraction
happens. It exists as a separate subsystem because URL resolution is a genuinely
different problem from record extraction: it is site-topology work (sitemaps, listing
pages, hub directories) rather than record-shape work, it is reusable across adapters,
and one of its strategies (hub scanning) must be *structurally* prevented from producing
records at all. Nothing else owns "find the addresses"; `adapters/` owns "turn an address
into an `Event`", and `extract/` owns "turn one page's HTML into fields".

## 2. Orientation

Two independent concerns live here, and they do not talk to each other.

**Event-URL discovery** — feeds the HTML adapters. Two sibling strategies:

- `sitemap.py` · `discover_changed_urls(source, fetcher, changed_only=False)`. Resolves a
  site's root sitemap (explicit `config["sitemap_url"]`, or probing
  `sitemap_index.xml` / `sitemap.xml` / `sitemap-index.xml` in order), recurses into a
  `<sitemapindex>`, classifies child sitemaps and URLs as event/program-related by
  filename and path pattern, then diffs the resulting `{url: lastmod}` map against a
  persisted per-source snapshot under `SCRAPE_CACHE_DIR`. Returns `EventRef`s for new or
  `lastmod`-changed URLs and rewrites the snapshot.
- `listing.py` · `discover_via_listing(source, fetcher)`. For sites with no sitemap:
  crawls the configured listing page(s), pattern-matches anchor hrefs against
  `sitemap.EVENT_PATH_RE`, and returns every match. No diffing, no snapshot, no cache
  write.
- `listing.py` · `discover_via_selector(source, fetcher)` **(sprint 027 ticket 006
  exception revision)**. A sibling to `discover_via_listing`, used only when
  `source.config["link_selector"]` is set: crawls the same configured listing page(s),
  but picks links via `tree.cssselect(link_selector)` instead of `EVENT_PATH_RE`, for a
  listing whose card links are identified by markup structure/attributes rather than by
  URL path shape. Same no-diffing, no-snapshot, no-cache-write posture as its sibling.
  See §4.

**Organization discovery (lead generation)** — feeds a human review queue, never the
pipeline:

- `hub_scan.py` · `scan_hub(hub, fetcher, ...)`. Fetches one curated external hub's
  pages, extracts every outbound (different-domain) link with its surrounding text as an
  `OrgCandidate`, and drops any candidate whose domain or normalized org name already
  matches a `SourceConfig`.
- `candidate_pipeline.py` · `discover_candidates(hubs, fetcher, enricher=None, ...)`.
  Sequences `scan_hub` over every hub, optionally passes each surviving candidate through
  a `RelevanceGate` (satisfied structurally by `LLMEnricher`) using a throwaway synthetic
  `Event`, and writes the survivors as review-marked TOML stubs via
  `registry.candidates.write_candidate`.

## 3. Constraints and Invariants

- **Hub scanning must never produce an `Event` that reaches the pipeline.** `hub_scan.py`
  never constructs a `model.Event` and imports nothing from `normalize/` or `export/`.
  The stakeholder position is explicit: *we* are the aggregator, and republishing another
  aggregator's listings as our own data is the failure mode this structure prevents. If a
  future edit gives this module a path to `normalize.run()` or `export_opportunities()`,
  that guarantee is gone regardless of intent.
- **`candidate_pipeline.py` may not import `pipeline.Enricher`.** It defines its own
  structurally-typed `RelevanceGate` Protocol instead. Importing from `pipeline.py` would
  create a `discovery → pipeline` edge running backwards against the codebase's one-way
  dependency direction. Python Protocols are structural, so a real `LLMEnricher`
  satisfies `RelevanceGate` with zero adaptation — there is no benefit to the import and
  a real architectural cost.
- **`candidate_pipeline.py`'s synthetic `Event` is never persisted and never returned.**
  It exists only to give the relevance classifier something Event-shaped. Leaking it into
  a return value would reintroduce exactly the hub-republication risk the structure
  forbids.
- **`listing.py` deliberately does not diff.** A listing page carries no
  `lastmod`-equivalent signal, so there is nothing trustworthy to diff against. Adding a
  snapshot here would silently drop pages whose content changed without any observable
  marker. **(Sprint 027 ticket 006 exception revision)** applies identically to
  `discover_via_selector` — same reasoning, same no-snapshot posture.
- **(Sprint 027 ticket 006 exception revision) Neither listing strategy restricts by
  domain.** `EVENT_PATH_RE` matching never checked the matched link's domain against the
  source's own; `discover_via_selector` inherits that same absence rather than adding a
  new restriction — a CSS selector is already an explicit, operator-authored statement
  of intent, so an extra domain gate would add a config knob with no evidenced need
  (UCSD's own real cards are legitimately cross-domain — see `adapters-DESIGN.md`'s
  Revision note).
- **A sitemap candidate is accepted only if it is both HTTP 200 *and* parses with a
  `<urlset>` or `<sitemapindex>` root.** Several static-site generators serve a catch-all
  HTML page with status 200 for any path; accepting on status alone would treat that page
  as an empty sitemap and silently yield zero URLs for the source forever.
- **(Sprint 015) `_parse_urlset()`'s namespace-agnostic fallback only fires when the
  namespace-qualified query finds zero `<url>` elements — never based on the final,
  filtered result being empty.** A urlset whose `<url>` elements all fail
  `EVENT_PATH_RE`'s `path_filter` legitimately returns `{}` without the fallback
  redoing the same (filtered-out) work under a different name; only a sitemap
  declaring a namespace other than the hardcoded `_NS` (or none) should ever reach the
  fallback branch.
- **This subsystem imports `adapters.base.EventRef` directly, never the `adapters`
  package.** Importing the package would pull in the dispatch table and every concrete
  adapter, inverting the dependency direction (adapters call discovery, never the
  reverse) and creating an import cycle.
- **`scan_hub` checks robots.txt per page.** Hub pages are third-party sites being
  crawled for their link graph; skipping the check would be the least defensible fetch in
  the codebase.
- **Per-page isolation in both listing crawl and hub scan.** A non-200 or unparseable
  page is logged and skipped, never fatal to the remaining pages.

## 4. Design

**The snapshot as incremental state.** `sitemap.py` is the only part of the system that
keeps discovery-time state across runs: `{SCRAPE_CACHE_DIR}/sitemap_snapshots/{source_id}`
holds the last observed `{url: lastmod}` map. It is rewritten to the full current state
on every successful resolution, not merged — so a source whose sitemap shrinks converges
rather than accumulating ghosts. `changed_only=False` (the default) still returns
everything; the diff narrows the result only when the caller asks for it.

**Two-level classification.** Sitemap URL selection happens twice: once over child
sitemap *filenames* inside a `<sitemapindex>` (`EVENT_PATTERNS`, `PROGRAM_PATTERNS` —
catching WordPress/TEC conventions like `tribe_events`), and once over individual URL
*paths* (`EVENT_PATH_RE`) for sites that have no dedicated event sitemap. The patterns
were ported from the pre-existing `dev/` exploration scripts as a starting point; `dev/`
is not a dependency.

**(Sprint 015) `_parse_urlset()` falls back to namespace-agnostic matching, tried only
after the qualified query.** *Context:* `_parse_urlset()` queried only
`root.findall("sm:url", _NS)` against the hardcoded sitemaps.org 0.9 namespace, while
root-tag acceptance (`_parse_sitemap_root()`) was already namespace-agnostic via
`_local_name()` — so a sitemap validating in a *different* namespace (or none) parsed
successfully but silently yielded zero `<url>` matches. Live-confirmed on
`sandiego.edu`'s legacy `xmlns="http://www.google.com/schemas/sitemap/0.84"` sitemap
(issue 37); `sandiego` was disabled with this exact reason. *Alternatives considered:*
replace the qualified query with a namespace-agnostic one everywhere — rejected: the
qualified query is marginally more precise for the 0.9 namespace every
currently-registered sitemap already validates against, and a query-first,
fallback-second design is additive by construction (see the invariant below) where a
query-only-agnostic rewrite is a strict behavior change to every existing sitemap, not
just the broken ones. *Why this choice:* if `root.findall("sm:url", _NS)` returns zero
elements, `_parse_urlset()` retries by iterating `root`'s direct children and matching
`_local_name(child.tag) == "url"`, then reads each child's `<loc>`/`<lastmod>` the same
way (`_find_local_child_text`, new). *Consequences:* a real, well-formed sitemap in any
namespace (or none) now contributes its URLs; no currently-working sitemap can regress,
since the fallback only fires on today's silent zero-URL failure mode.

**Why hub scanning lives here rather than in `registry/`.** It is discovery — the same
"resolve a starting point into addresses" shape as the other two strategies — even
though its output is org candidates rather than event URLs. What differs is the
*destination*: `registry/candidates/` and a human, rather than an adapter. Keeping it
here alongside its siblings, with an enforced structural firewall, was preferred to
inventing a fourth top-level directory for one 220-line module.

**Candidate dedup is name-and-domain based.** `scan_hub` reuses
`normalize.partners.normalize_org_name` for the name comparison. That is the single
permitted import from `normalize/` — a pure string function with no I/O and no
Event/Opportunity concept, so it does not weaken the firewall.

**Anchor heuristics.** A link's visible text is the best-effort org name (hub pages
conventionally name the org right in the anchor); the containing block's full text
becomes `evidence_text` for the human reviewer and the relevance gate. Links with no
usable text and no `title` attribute are dropped — an unnamed link is not a usable lead.

**(Sprint 027 ticket 006 exception revision) `discover_via_selector`: markup-shape
discovery, not URL-shape discovery.** `discover_via_listing`'s `EVENT_PATH_RE` approach
assumes a card's *target URL* is itself program-shaped (`/programs/…`); ticket 006's
live verification found this false for both of this sprint's real listing sources (see
`adapters-DESIGN.md`'s Revision note). `discover_via_selector` instead assumes the
*source page's markup* around each card is what reliably identifies it — a `data-*`
attribute, a class name — regardless of where the link then points. The two functions
share their per-listing-page fetch loop (resolve `listing_urls` against `site_url`, GET,
skip a non-200 page) and diverge only at the link-extraction step: `EVENT_PATH_RE.
search()` over every `<a href>` versus `lxml`'s `cssselect(link_selector)` over the
parsed tree, reading each matched element's own `href`. Because the selector can target
an attribute anywhere in a card's markup (e.g. `li[data-grade*="High School"]
a.learnmore`), one operator-authored string does discovery *and* the eligibility filter
together — no second config key, no code change, matching `registry/DESIGN.md`'s
"onboarding is a data edit" convention this doc's siblings already follow.

## 5. Interfaces

### Exposes
- **`discover_changed_urls(source, fetcher, *, changed_only=False) -> list[EventRef]`** —
  sitemap-based event-URL discovery. Reads and writes a per-source snapshot under
  `SCRAPE_CACHE_DIR`. Returns an empty list (logged) when no sitemap can be resolved;
  does not raise for an unreachable or unparseable sitemap.
- **`discover_via_listing(source, fetcher) -> list[EventRef]`** — listing-page event-URL
  discovery. Stateless; no cache interaction. Per-page failures are logged and skipped.
- **`discover_via_selector(source, fetcher) -> list[EventRef]`** (sprint 027 ticket 006
  exception revision) — the CSS-selector-driven sibling, used when `source.config`
  carries `link_selector`. Same statelessness and per-page-failure handling as
  `discover_via_listing`. See §4.
- **`scan_hub(hub, fetcher, *, sources_dir=None, user_agent=...) -> list[OrgCandidate]`**
  — lead generation over one hub. Returns candidates not already covered by the Source
  Registry. Never constructs an `Event`; never persists anything.
- **`discover_candidates(hubs, fetcher, enricher=None, *, sources_dir=None,
  candidates_dir=None)`** — full candidate flow, ending in TOML stubs written to the
  candidate review queue.
- **`OrgCandidate`** — `org_name`, `candidate_url`, `evidence_text`, `hub_id`.
- **`RelevanceGate` Protocol** — one method, `enrich(events) -> events`.

### Consumes
- **`Fetcher` and `fetch.robots.is_allowed` (from `fetch/`)** — all remote reads and the
  hub-scan robots check. See `fetch/DESIGN.md`.
- **`SourceConfig` / `HubConfig` / `load_sources` / `write_candidate` (from `registry/`)**
  — source and hub configuration, registry dedup lookup, and candidate persistence. See
  `registry/DESIGN.md`.
- **`adapters.base.EventRef`** — the output shape for the two event-URL strategies; a
  logic-free dataclass. See `adapters/DESIGN.md`.
- **`config.get_scrape_cache_dir` (from `config.py`)** — sitemap snapshot location.
- **`normalize.partners.normalize_org_name`** — string normalization for candidate
  dedup only. See the constraint above.

## 6. Open Questions / Known Limitations

- The `adapters.listing_html` ↔ `discovery.listing` import cycle is real and is currently
  papered over by import ordering in `cli.py`. It needs a proper fix.
- Listing discovery does not paginate. It was scoped to Fleet Science Center's single
  non-paginating Drupal view; a paginating listing page would silently yield only its
  first page. **(Sprint 027 ticket 006 exception revision)** `discover_via_selector`
  inherits this exact limitation — it crawls each configured `listing_urls` entry once,
  with no pagination-follow logic; both of this revision's registered sources
  (UCSD, SIO) are single, non-paginating pages, live-confirmed.
- **(Sprint 027 ticket 006 exception revision, formerly speculative in
  `adapters-DESIGN.md`)** A `link_selector` that stops matching after a target site's
  markup changes (a redesign, a class rename) silently returns to zero cards — caught
  now by `adapters/base.py`'s generic zero-refs warning (see `adapters-DESIGN.md`'s §4)
  and by `observability/`'s yield-report alert below, but nothing here re-validates the
  selector itself or distinguishes a total-zero drift from a partial one (24 cards
  quietly becoming 3, say). Not solved speculatively; revisit if a registered
  `link_selector` source is ever observed to drift.
- Hub scanning's "every outbound link is a candidate" heuristic is deliberately broad and
  produces a lot of noise (footer links, social media, sponsors). The relevance gate and
  the human review queue absorb it, but precision has never been measured.
- `registry/candidates/` does not exist on disk yet — no candidate run has been promoted.
  The flow is built and tested but has not been exercised end-to-end against real hubs at
  any volume.
- Sitemap classification is regex-based and tuned to WordPress/TEC/Drupal conventions. A
  site using an unusual sitemap layout falls back to path patterns, and if those miss
  too, the source yields nothing — visible only as a zero-yield alert from
  `observability/`.
