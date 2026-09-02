---
source_file: extract-DESIGN.md
source_hash: 40d7754bdf548d417fc7f13afa2515e16643fb9c064fe58514af0186840d7b7f
---
# Diff: extract-DESIGN.md

Comparison of the sprint overlay copy of `extract-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- extract-DESIGN.md (pristine)
+++ extract-DESIGN.md (current)
@@ -3,6 +3,26 @@
 **Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
 
 ---
+
+## Revision (2026-09-01 — sprint 028)
+
+Sprint 027's `program_page`/`program_listing`/`program_page_multi` adapter family
+(`adapters/DESIGN.md`) sends a fetched page's raw HTML body to the LLM verbatim, with no
+reduction step. Two verified failures came out of that (issue 36): the SD Foundation
+Community Scholarship's raw page HTML (840KB-965KB site-wide) raised
+`anthropic.BadRequestError: prompt is too long: 600199 tokens > 200000 maximum`, and a
+UCSD Summer Program Finder card (`www.rmtlacademy.org`, 612KB) hit the same limit. Sprint
+028 fixes this by adding one new public function here, `reduce_html_to_text()` (§2, §5),
+rather than adding a second HTML-reduction path inside `adapters/` — per this doc's own
+"read fields out of unstructured HTML... worth testing in isolation" purpose statement
+(§1), text reduction is the same kind of self-contained, purely computational, no-network/
+no-config/no-state problem `extract_fields()` already solves, just for a different
+consumer (an LLM prompt budget, not the confidence ladder). It reuses this module's
+existing visible-text-walking machinery (`_visible_text_parts`/`_visible_body_text`,
+already used by the body-regex rung) rather than duplicating an HTML-to-text pass — see
+§4's Revision note for why a shared helper, not two independent implementations, was the
+right call once a second caller needed "get me the visible text" with a different bound
+than the ladder's own 20,000-character rung limit.
 
 ## 1. Purpose
 
@@ -13,9 +33,20 @@
 corpus of real pages. It owns the confidence model for unstructured extraction:
 the ordering of which signals are trusted over which. Nothing else makes that judgment.
 
+**(Sprint 028)** It also now owns one more self-contained, purely computational problem
+of the same shape: reducing an arbitrary HTML page down to bounded, readable plain text,
+for a caller (the LLM-extraction adapter family) that needs the page's prose content but
+not its markup, script, or boilerplate, and cannot safely hand an LLM an unbounded page.
+This is a distinct output from `extract_fields()` — plain text, not
+`{field: (value, confidence)}` — but the same "parse once, walk the tree, return
+something total and pure" shape, so it lives here rather than becoming a second
+tree-walking implementation inside `adapters/`.
+
 ## 2. Orientation
 
-One public function: `extract_fields(html: str, url: str) -> dict[str, tuple[Any, float]]`.
+Two public functions.
+
+`extract_fields(html: str, url: str) -> dict[str, tuple[Any, float]]`.
 
 It parses the page once with `lxml.html` and then runs a fixed sequence of extraction
 strategies ("rungs") in descending order of trust. Each rung contributes only fields that
@@ -33,6 +64,15 @@
 The return value is a flat `{field_name: (value, confidence)}` map. A field no rung could
 recover — most often `start`/`end` on a page with no date signal at all — is simply
 *absent* from the map, not present with a placeholder.
+
+**(Sprint 028)** `reduce_html_to_text(html: str, max_chars: int = 100_000) -> str`. Parses
+the page once with `lxml.html` (same parser, same `fromstring`-then-tolerate-bad-markup
+behavior as `extract_fields`), strips `<script>`, `<style>`, `<nav>`, `<header>`, and
+`<footer>` elements before walking the remaining tree for visible text (reusing
+`_visible_text_parts`, the same helper the body-regex rung already calls), collapses
+whitespace, and truncates to the first `max_chars` characters. Returns `""` for
+unparseable/empty HTML, with a logged warning — never raises, matching
+`extract_fields()`'s own error-handling contract exactly.
 
 ## 3. Constraints and Invariants
 
@@ -62,6 +102,26 @@
 - **Body-text scanning is bounded** (`_BODY_SCAN_LIMIT`, 20 000 chars) and skips
   `<script>`/`<style>` content. Removing the bound makes the lowest-value, highest-noise
   rung the most expensive one on large pages.
+- **(Sprint 028) `reduce_html_to_text()`'s bound is deliberately separate from
+  `_BODY_SCAN_LIMIT`.** The two exist for different reasons and must not be unified: the
+  body-regex rung's 20,000-character cap bounds the cost of a low-value, high-noise date
+  regex scan; `reduce_html_to_text()`'s 100,000-character cap bounds an LLM's context
+  budget for a page it needs to read in full. Changing one must not silently change the
+  other.
+- **(Sprint 028) Truncation keeps the leading `max_chars` characters of reduced text,
+  never the whole page.** A program/camp page states its key facts (program name, dates,
+  price, eligibility) in prose near the top, not buried at the end — the same
+  publisher-authoring assumption the body-regex rung's own bound already accepts (see
+  that rung's docstring). This is a documented, deliberate strategy, not an arbitrary cut:
+  a page whose material facts live past the 100,000-character mark would need a different
+  strategy (e.g. a summary pass), which is not built here because no page examined during
+  sprint 027/028 exhibited that shape.
+- **(Sprint 028) `reduce_html_to_text()` strips `<script>`/`<style>`/`<nav>`/`<header>`/
+  `<footer>` before truncating, not after.** Stripping first is what makes the
+  100,000-character budget mostly page *content* rather than boilerplate — the SD
+  Foundation pages' own site-wide template bloat (a large repeated mega-menu/inline
+  script payload on every page, per this module's own live-measured finding) is exactly
+  the shape this ordering is designed to discard before the cap ever applies.
 
 ## 4. Design
 
@@ -97,6 +157,17 @@
 
 **Dependency.** `lxml`, already a base dependency of the package since the first sprint.
 No parser was added for this module.
+
+**(Sprint 028) Why a shared helper, not a second implementation.** `adapters/
+program_page.py` could have grown its own `lxml`-based strip-and-walk function instead.
+That was rejected the same way `extract/DESIGN.md`'s own non-goal already rejects
+per-site special cases living outside this module: "get the visible text out of an HTML
+page" is exactly the problem `_visible_text_parts`/`_visible_body_text` already solve for
+the body-regex rung, and a second implementation would drift from this one's tolerance
+for malformed markup (a bug fixed in one would not fix the other). Exporting
+`reduce_html_to_text()` from here, reusing the existing private helpers internally,
+keeps there being exactly one "how do we get readable text out of arbitrary HTML" answer
+in the codebase.
 
 ## 5. Interfaces
 
@@ -109,11 +180,19 @@
   `CONFIDENCE_TITLE_FALLBACK`, `CONFIDENCE_URL_DATE`, `CONFIDENCE_BODY_REGEX`** — the
   tier constants, exported so callers stamp provenance with the same numbers the ladder
   used rather than re-deriving them.
+- **(Sprint 028) `reduce_html_to_text(html: str, max_chars: int = 100_000) -> str`** —
+  script/style/nav/header/footer-stripped, whitespace-collapsed, leading-`max_chars`-
+  truncated visible text. Pure; total (returns `""` rather than raising on bad input).
+  Consumed by `adapters/program_page.py`'s `_extract_one_program`/
+  `_extract_many_programs` before every cache lookup and LLM call — see
+  `adapters/DESIGN.md`'s sprint 028 section.
 
 ### Consumes
 Nothing from any other subsystem. `extract/` imports only the standard library and
 `lxml`. It does not import `model`, `fetch`, `registry`, or `config` — which is what
-makes it trivially unit-testable against a directory of saved HTML fixtures.
+makes it trivially unit-testable against a directory of saved HTML fixtures. **(Sprint
+028)** `reduce_html_to_text()` preserves this exactly — same zero-dependency shape as
+`extract_fields()`.
 
 ## 6. Open Questions / Known Limitations
 
@@ -129,3 +208,14 @@
   tradeoff has never been measured against real export quality.
 - There is no microdata/RDFa rung. Some older event sites use those instead of JSON-LD
   and currently fall through to the weaker rungs.
+- **(Sprint 028)** `reduce_html_to_text()`'s 100,000-character truncation is a fixed
+  constant, not derived from the model's actual token budget (`adapters/program_llm.py`'s
+  `MODEL_ID` and its 200K-token context window). 100,000 characters is comfortably below
+  200K tokens for ordinary English prose (~4 chars/token), but a page whose reduced text
+  is unusually token-dense (e.g. heavy non-Latin script or numeric tables) is not
+  measured against the model's real tokenizer. Not built speculatively — revisit if a
+  reduced page is ever observed to still exceed the context window.
+- **(Sprint 028)** No page examined during sprint 027/028 needed anything past the
+  leading 100,000 characters to recover its program/session fields, so the "keep the
+  leading text" truncation strategy is unverified against a page whose material facts
+  are genuinely deep in the document. Revisit if one is found.
```
