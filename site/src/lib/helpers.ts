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

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Ongoing';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return 'Ongoing';
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
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
