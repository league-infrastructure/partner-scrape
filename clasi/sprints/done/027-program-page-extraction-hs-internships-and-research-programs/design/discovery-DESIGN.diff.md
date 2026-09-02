---
source_file: discovery-DESIGN.md
source_hash: db5b3314c3981fb1999daf98f7e70ce38b639c7a818b219ce30d27ac378ee936
---
# Diff: discovery-DESIGN.md

Comparison of the sprint overlay copy of `discovery-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- discovery-DESIGN.md (pristine)
+++ discovery-DESIGN.md (current)
@@ -3,6 +3,17 @@
 **Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** in-flux
 
 ---
+
+## Revision (2026-09-02 — sprint 027 ticket 006 exception cycle)
+
+This doc was not originally part of sprint 027's overlay (only `adapters/DESIGN.md`
+was, since sprint 027's own architecture framed the two new adapter types as reusing
+`discover_via_listing` unchanged). Ticket 006's live verification found that reuse
+insufficient for either of its two real listing sources — see `adapters-DESIGN.md`'s
+own Revision note for the full finding — so this sprint now also adds one new function
+here: `listing.py` gains `discover_via_selector(source, fetcher)`, a CSS-selector-driven
+sibling to the existing `discover_via_listing(source, fetcher)`, seeded into this
+overlay for that reason. See §2/§4/§5 below.
 
 ## 1. Purpose
 
@@ -31,6 +42,13 @@
   crawls the configured listing page(s), pattern-matches anchor hrefs against
   `sitemap.EVENT_PATH_RE`, and returns every match. No diffing, no snapshot, no cache
   write.
+- `listing.py` · `discover_via_selector(source, fetcher)` **(sprint 027 ticket 006
+  exception revision)**. A sibling to `discover_via_listing`, used only when
+  `source.config["link_selector"]` is set: crawls the same configured listing page(s),
+  but picks links via `tree.cssselect(link_selector)` instead of `EVENT_PATH_RE`, for a
+  listing whose card links are identified by markup structure/attributes rather than by
+  URL path shape. Same no-diffing, no-snapshot, no-cache-write posture as its sibling.
+  See §4.
 
 **Organization discovery (lead generation)** — feeds a human review queue, never the
 pipeline:
@@ -66,7 +84,15 @@
 - **`listing.py` deliberately does not diff.** A listing page carries no
   `lastmod`-equivalent signal, so there is nothing trustworthy to diff against. Adding a
   snapshot here would silently drop pages whose content changed without any observable
-  marker.
+  marker. **(Sprint 027 ticket 006 exception revision)** applies identically to
+  `discover_via_selector` — same reasoning, same no-snapshot posture.
+- **(Sprint 027 ticket 006 exception revision) Neither listing strategy restricts by
+  domain.** `EVENT_PATH_RE` matching never checked the matched link's domain against the
+  source's own; `discover_via_selector` inherits that same absence rather than adding a
+  new restriction — a CSS selector is already an explicit, operator-authored statement
+  of intent, so an extra domain gate would add a config knob with no evidenced need
+  (UCSD's own real cards are legitimately cross-domain — see `adapters-DESIGN.md`'s
+  Revision note).
 - **A sitemap candidate is accepted only if it is both HTTP 200 *and* parses with a
   `<urlset>` or `<sitemapindex>` root.** Several static-site generators serve a catch-all
   HTML page with status 200 for any path; accepting on status alone would treat that page
@@ -141,6 +167,22 @@
 becomes `evidence_text` for the human reviewer and the relevance gate. Links with no
 usable text and no `title` attribute are dropped — an unnamed link is not a usable lead.
 
+**(Sprint 027 ticket 006 exception revision) `discover_via_selector`: markup-shape
+discovery, not URL-shape discovery.** `discover_via_listing`'s `EVENT_PATH_RE` approach
+assumes a card's *target URL* is itself program-shaped (`/programs/…`); ticket 006's
+live verification found this false for both of this sprint's real listing sources (see
+`adapters-DESIGN.md`'s Revision note). `discover_via_selector` instead assumes the
+*source page's markup* around each card is what reliably identifies it — a `data-*`
+attribute, a class name — regardless of where the link then points. The two functions
+share their per-listing-page fetch loop (resolve `listing_urls` against `site_url`, GET,
+skip a non-200 page) and diverge only at the link-extraction step: `EVENT_PATH_RE.
+search()` over every `<a href>` versus `lxml`'s `cssselect(link_selector)` over the
+parsed tree, reading each matched element's own `href`. Because the selector can target
+an attribute anywhere in a card's markup (e.g. `li[data-grade*="High School"]
+a.learnmore`), one operator-authored string does discovery *and* the eligibility filter
+together — no second config key, no code change, matching `registry/DESIGN.md`'s
+"onboarding is a data edit" convention this doc's siblings already follow.
+
 ## 5. Interfaces
 
 ### Exposes
@@ -150,6 +192,10 @@
   does not raise for an unreachable or unparseable sitemap.
 - **`discover_via_listing(source, fetcher) -> list[EventRef]`** — listing-page event-URL
   discovery. Stateless; no cache interaction. Per-page failures are logged and skipped.
+- **`discover_via_selector(source, fetcher) -> list[EventRef]`** (sprint 027 ticket 006
+  exception revision) — the CSS-selector-driven sibling, used when `source.config`
+  carries `link_selector`. Same statelessness and per-page-failure handling as
+  `discover_via_listing`. See §4.
 - **`scan_hub(hub, fetcher, *, sources_dir=None, user_agent=...) -> list[OrgCandidate]`**
   — lead generation over one hub. Returns candidates not already covered by the Source
   Registry. Never constructs an `Event`; never persists anything.
@@ -177,7 +223,18 @@
   papered over by import ordering in `cli.py`. It needs a proper fix.
 - Listing discovery does not paginate. It was scoped to Fleet Science Center's single
   non-paginating Drupal view; a paginating listing page would silently yield only its
-  first page.
+  first page. **(Sprint 027 ticket 006 exception revision)** `discover_via_selector`
+  inherits this exact limitation — it crawls each configured `listing_urls` entry once,
+  with no pagination-follow logic; both of this revision's registered sources
+  (UCSD, SIO) are single, non-paginating pages, live-confirmed.
+- **(Sprint 027 ticket 006 exception revision, formerly speculative in
+  `adapters-DESIGN.md`)** A `link_selector` that stops matching after a target site's
+  markup changes (a redesign, a class rename) silently returns to zero cards — caught
+  now by `adapters/base.py`'s generic zero-refs warning (see `adapters-DESIGN.md`'s §4)
+  and by `observability/`'s yield-report alert below, but nothing here re-validates the
+  selector itself or distinguishes a total-zero drift from a partial one (24 cards
+  quietly becoming 3, say). Not solved speculatively; revisit if a registered
+  `link_selector` source is ever observed to drift.
 - Hub scanning's "every outbound link is a candidate" heuristic is deliberately broad and
   produces a lot of noise (footer links, social media, sponsors). The relevance gate and
   the human review queue absorb it, but precision has never been measured.
```
