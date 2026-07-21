/**
 * Description Markdown Renderer (sprint 007, ticket 001, SUC-001).
 *
 * `opportunities.json`'s `description` field comes from several partner
 * sources (LeagueSync/Pike13 class copy, scraped HTML) and can contain
 * Markdown syntax (`**bold**`, blank-line-separated paragraphs) and/or
 * HTML entities (named, e.g. `&hellip;`/`&nbsp;`/`&lt;`/`&gt;`, and
 * numeric, e.g. `&#8211;`/`&#8217;` -- present in ~22 scraped
 * descriptions). Astro's default `{expr}` interpolation HTML-escapes its
 * output, so both show up as raw literal text instead of formatted
 * content -- see sprint.md's Architecture ("Description Markdown
 * Renderer") and Design Rationale ("Markdown rendering happens at build
 * time only, never client-side").
 *
 * Non-obvious wrinkle found in the real data: several of the ~22
 * entity-bearing descriptions are HTML entity-*encoded* HTML, e.g. a
 * literal `&lt;p&gt;...&lt;/p&gt;` in the source text -- an original
 * `<p>` element that some upstream sync step escaped rather than
 * stripped. Decoding entities before Markdown parsing turns that back
 * into a real `<p>` tag embedded in the string, which CommonMark treats
 * as a raw-HTML block. `remark-rehype` drops raw HTML nodes by default
 * (safe default, but it would silently blank out exactly this ticket's
 * target set of descriptions) -- `allowDangerousHtml` + `rehype-raw`
 * parses that raw HTML back into real nodes so `rehype-sanitize` can
 * inspect and sanitize it like any other markup, instead of the pair
 * being dropped or passed through unsanitized. This is the standard
 * unified/rehype pattern for "Markdown that may itself contain raw
 * HTML," not a bespoke workaround.
 *
 * This module exposes two pure, build-time-only entry points over one
 * shared sanitized-HAST pipeline (decode entities, parse Markdown,
 * resolve any embedded raw HTML, sanitize) so each caller gets the form
 * it needs from the *same* interpretation of the source text:
 *
 *   - `renderDescriptionHtml` -- sanitized HTML for the detail page's
 *     `set:html`.
 *   - `descriptionToPlainText` -- clean plain text for the card
 *     preview's `truncate()` (see `helpers.ts`).
 *
 * Deliberately reuses Astro's own built-in Markdown dependency chain
 * (`remark-parse`, `remark-gfm`, `remark-rehype`, `rehype-stringify`,
 * `rehype-raw` -- all already transitive dependencies of `astro` itself)
 * rather than a second markdown parser (e.g. `marked`); the only
 * genuinely new packages this ticket adds are the sanitizer
 * (`rehype-sanitize`), the plain-text extractor (`hast-util-to-text`),
 * and the entity decoder (`entities`). All of this runs in Node during
 * `astro build`; nothing here touches the DOM or performs network/CDN
 * access, matching the site's static build + strict CSP.
 */

import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkRehype from 'remark-rehype';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import rehypeStringify from 'rehype-stringify';
import { toText } from 'hast-util-to-text';
import { decode } from 'entities';
import type { Root as HastRoot } from 'hast';

// Shared parse+transform pipeline (no stringifier attached) so both
// entry points sanitize the exact same HAST tree instead of running two
// independently-behaving interpretations of the source text.
const treeProcessor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkRehype, { allowDangerousHtml: true })
  .use(rehypeRaw)
  .use(rehypeSanitize);

function toSanitizedHast(decodedText: string): HastRoot {
  return treeProcessor.runSync(treeProcessor.parse(decodedText)) as HastRoot;
}

/**
 * Renders one raw `description` string to sanitized HTML safe for
 * `set:html`. Decodes HTML entities first (so `&#8211;`/`&#8217;`/
 * `&hellip;` etc. become real characters), parses the result as
 * Markdown (CommonMark + GFM), resolves any embedded raw HTML, then
 * sanitizes the produced HTML tree (strips `<script>`, inline event
 * handlers, and anything else outside `rehype-sanitize`'s default
 * safe-element/attribute allowlist) before serializing.
 *
 * `null`/`undefined`/empty input returns `''` -- no crash, no visible
 * change from today's rendering (SUC-001 Alternate Flow).
 */
export function renderDescriptionHtml(text: string | null | undefined): string {
  if (!text) return '';
  const hast = toSanitizedHast(decode(text));
  return unified().use(rehypeStringify).stringify(hast);
}

/**
 * Reduces one raw `description` string to clean, readable plain text:
 * entities decoded, Markdown/HTML syntax stripped (no `**`, no literal
 * `\n\n`, no raw entity codes, no `<tag>` fragments), suitable for
 * `helpers.ts`'s `truncate()` in the card preview. Text is extracted
 * from the same sanitized HAST tree `renderDescriptionHtml` produces
 * (via `hast-util-to-text`, which -- like the DOM's `innerText` --
 * inserts sensible whitespace at block boundaries) so paragraph/list/
 * heading breaks become a single joining space instead of fusing
 * adjacent words together or leaking raw markup.
 *
 * `null`/`undefined`/empty input returns `''`, matching `truncate()`'s
 * existing null-safety.
 */
export function descriptionToPlainText(text: string | null | undefined): string {
  if (!text) return '';
  const hast = toSanitizedHast(decode(text));
  return toText(hast).replace(/\s+/g, ' ').trim();
}
