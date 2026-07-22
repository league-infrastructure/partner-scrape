export function getLogoPath(logoSrc: string | null | undefined): string {
  // BASE_URL may or may not carry a trailing slash depending on how `base` is set
  // (--base /partner-scrape -> "/partner-scrape"; a config value with a trailing
  // slash -> "/partner-scrape/"; default -> "/"). Strip any trailing slash and add
  // one explicitly so the path resolves correctly under any base.
  const base = import.meta.env.BASE_URL.replace(/\/+$/, '');
  if (!logoSrc) return `${base}/images/logos/default-partner.svg`;
  // logo_src is now just the filename (e.g., "agua_hedionda_lagoon_foundation.jpg")
  return `${base}/images/logos/${logoSrc}`;
}

// Single shared image-fallback decision for both `OpportunityCard.astro` and
// `[slug].astro` (sprint 008, issue 19 site half / SUC-009), so the two
// callers can't drift on fallback order: an opportunity's own event photo
// (`image_src`, self-hosted by the scraper's Event Image Downloader under
// `public/images/opportunities/`) -> its partner's logo (`logo_src`, tier 2
// -- delegated to `getLogoPath()`, which already also owns tier 3, the
// generic placeholder) -> the placeholder. Mirrors `getLogoPath()`'s own
// filename-not-URL convention: `image_src` is a resolved local filename,
// never fetched at build time (see sprint.md Design Rationale).
export function resolveImage(
  imageSrc: string | null | undefined,
  logoSrc: string | null | undefined
): string {
  if (imageSrc) {
    const base = import.meta.env.BASE_URL.replace(/\/+$/, '');
    return `${base}/images/opportunities/${imageSrc}`;
  }
  return getLogoPath(logoSrc);
}

// Extract the intended local (San Diego) calendar day embedded in an ISO
// date string, ignoring any timezone offset suffix. `_iso()`
// (`partner_scrape/normalize/run.py`) always writes the scraper's
// already-resolved local Y-M-D plus a fixed `-07:00` suffix, so matching
// the string's own digits directly -- not asking a `Date` object for them
// -- gives the correct calendar day regardless of the build machine's own
// timezone. Mirrors CalendarView's `hasNoRealTime()` convention (see there
// for the full rationale) and its `dayKey()` day-bucketing.
const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})/;

function localDateOnly(dateStr: string): Date | null {
  const m = DATE_ONLY_RE.exec(dateStr);
  if (!m) return null;
  // Local-component constructor: this Date's own getters (and any
  // `toLocaleDateString` call with no explicit `timeZone`) reflect exactly
  // this Y-M-D, independent of the source string's own offset.
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

export function isWeekend(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  const d = localDateOnly(dateStr);
  if (!d) return false;
  const day = d.getDay();
  return day === 0 || day === 6;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Ongoing';
  const parsed = new Date(dateStr);
  if (isNaN(parsed.getTime())) return 'Ongoing';
  // Format from the locally-extracted Y-M-D (falling back to the parsed
  // Date for any string that doesn't match the expected ISO-date prefix)
  // so the weekday shown always matches the intended local calendar day,
  // not one shifted by the build machine's own timezone.
  const local = localDateOnly(dateStr) ?? parsed;
  return local.toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export function formatDateRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return 'Ongoing';
  const startStr = formatDate(start);
  if (!end) return startStr;
  const endStr = formatDate(end);
  if (startStr === endStr) return startStr;
  return `${startStr} – ${endStr}`;
}

export function truncate(text: string, maxLen: number = 150): string {
  if (!text || text.length <= maxLen) return text || '';
  return text.slice(0, maxLen).replace(/\s+\S*$/, '') + '…';
}

export function parseCity(location: string | null | undefined): string {
  if (!location) return '';
  const parts = location.split(',');
  return parts[0]?.trim() || '';
}

export function slugify(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

// Single shared "is this opportunity mappable" predicate, used by both the
// detail page's map section and the Map view's marker loop, so the two
// checks can't independently drift (see sprint 008 Design Rationale). A
// coordinate pair is mappable only if both values parse as finite numbers
// and are not the (0, 0) null-island placeholder that upstream sources use
// for "no real coordinate" — a bare falsy/NaN check alone misses this
// because `parseFloat("0")` is `0`, not `NaN`.
export function isMappable(
  lat: string | number | null | undefined,
  lng: string | number | null | undefined
): boolean {
  if (lat === null || lat === undefined || lng === null || lng === undefined) return false;
  const latNum = typeof lat === 'number' ? lat : parseFloat(lat);
  const lngNum = typeof lng === 'number' ? lng : parseFloat(lng);
  if (isNaN(latNum) || isNaN(lngNum)) return false;
  if (latNum === 0 && lngNum === 0) return false;
  return true;
}
