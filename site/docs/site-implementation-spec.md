# SD STEM Ecosystem — Site Implementation Spec

## Context for the Implementing Agent

You are building an Astro static site that replaces the existing Drupal site at sdstemecosystem.org. You have access to the full CSS from the original site — replicate the visual design as closely as possible. This document describes the **structure, data model, pages, components, and behavior** you need to implement.

The site's primary purpose is an **event/opportunity finder** for STEM activities in San Diego County, backed by a **partner directory**. Everything else is a thin static shell.

---

## Architecture

- **Framework**: Astro (static site generation)
- **Data sources**: JSON files in `src/data/` (partners, opportunities) and Markdown files in `src/content/pages/` for editorial content
- **Filtering**: Client-side JavaScript. The live dataset is small — typically 30-80 current opportunities and ~195 partners. The scraper only feeds current/upcoming events into the build; historical data is retained in the scraper's archive but never ships to the site. Ship the full JSON inline and filter in the browser.
- **Deployment**: GitHub Pages or similar static host. A separate scraper process (not part of this spec) commits updated JSON files, which triggers a rebuild via GitHub Actions.
- **No server-side logic, no database, no CMS, no login system.**

### Repository Structure

```
/
├── src/
│   ├── layouts/
│   │   ├── BaseLayout.astro          # HTML shell, head, nav, footer
│   │   └── ContentPage.astro         # Layout for static Markdown pages
│   ├── components/
│   │   ├── Header.astro              # Site header + navigation
│   │   ├── Footer.astro              # Site footer
│   │   ├── Hero.astro                # Homepage hero section
│   │   ├── OpportunityCard.astro     # Card for opportunity list view
│   │   ├── OpportunityFilters.astro  # Filter sidebar/panel (renders static HTML, hydrated by JS)
│   │   ├── OpportunityGrid.astro     # The grid/list container
│   │   ├── PartnerCard.astro         # Card for partner list view
│   │   ├── PartnerFilters.astro      # Partner filter controls
│   │   ├── PartnerGrid.astro         # Partner grid container
│   │   ├── MapEmbed.astro            # Leaflet/Mapbox map for location views
│   │   └── FeaturedOpportunities.astro  # Homepage featured section
│   ├── pages/
│   │   ├── index.astro               # Homepage
│   │   ├── opportunities/
│   │   │   ├── index.astro           # Opportunity listing with filters
│   │   │   └── [slug].astro          # Opportunity detail page
│   │   ├── partners/
│   │   │   ├── index.astro           # Partner directory with filters
│   │   │   └── [id].astro            # Partner detail page
│   │   ├── about.astro               # About the Ecosystem
│   │   └── contact.astro             # Contact page
│   ├── data/
│   │   ├── opportunities.json        # Scraped event/opportunity data
│   │   ├── partners.json             # Partner organization data (converted from CSV)
│   │   └── scrape-meta.json          # Timestamp of last scrape (for display)
│   ├── scripts/
│   │   └── filters.js                # Client-side filter logic (shared by opportunities + partners)
│   └── styles/
│       └── global.css                # Ported CSS from original site
├── public/
│   ├── images/
│   │   └── logos/                    # Partner logos (downloaded from original site)
│   └── favicon.svg
└── astro.config.mjs
```

---

## Data Schemas

### Opportunities (`src/data/opportunities.json`)

Each opportunity object has the following fields. All are strings or arrays of strings unless noted.

| Field | Type | Notes |
|-------|------|-------|
| `slug` | string | URL-safe identifier, used for detail page routing |
| `title` | string | Display name of the opportunity |
| `partner_name` | string | Name of the offering organization |
| `partner_id` | number | Foreign key to partners.json (you'll need to join on name if this field is missing) |
| `description` | string | Full text description, may be long |
| `link` | string | External registration/info URL |
| `availability` | string | Free-text schedule info |
| `date_start` | ISO 8601 string | Start date. Many are in the past — filter logic should handle this. |
| `date_end` | ISO 8601 string | End date (optional, not always present) |
| `age_grade_level` | string[] | Values: `Pre-K`, `TK/K`, `Grades 1-2`, `Grades 3-5`, `Grades 6-8`, `Grades 9-12`, `Undergraduate`, `Graduate`, `Adult`, `Family` |
| `cost_range` | string | Values: `Free`, `Less than $25`, `Less than $50`, `Less than $100`, `Less than $200`, `Greater than $200` |
| `time_of_day` | string[] | Values: `Morning`, `Afternoon`, `Evening`, `All Day`, `Online/Hybrid`, `Overnight` |
| `opportunity_type` | string | Values: `Out-of-school Programs`, `Online`, `Professional Development / Conferences`, `School Programs`, `Career Connections`, `Work-based Learning`, `Volunteering`, `Funding Opportunities` |
| `areas_of_interest` | string[] | Values: `Biology / LifeSciences`, `General Science`, `Engineering`, `Technology`, `Earth Science/Ecology`, `Coding/Computer Science/Cyber Security`, `Mathematics`, `Social Science`, `Physical Science`, `Chemistry`, `Physics` |
| `specific_attention` | string[] | Optional. Values like `Programs for boys`, `Programs for girls`, `Programs for students with disabilities`, `Programs in Spanish`, etc. |
| `financial_support` | string | `Yes` or `No` |
| `ngss_aligned` | string | `Yes` or `No` |
| `location` | string | Free-text address |
| `latitude` | string | For map display |
| `longitude` | string | For map display |
| `contact_name` | string | |
| `contact_email` | string | |
| `contact_phone` | string | |
| `logo_src` | string | Partner logo path (may need remapping to local assets) |

### Partners (`src/data/partners.json`)

Convert from CSV. Each partner object:

| Field | Type | Notes |
|-------|------|-------|
| `id` | number | Unique identifier |
| `name` | string | Organization name |
| `organization_type` | string | Values: `Afterschool/Out-of-School Time`, `Business & Industry`, `Museums, Science Centers & Zoos`, `Colleges, Universities, and Certificate/Credential Programs`, `Advocacy/Philanthropy & Government`, `CBOs, Family/Parent Organizations, Youth Organizing & Advisory Groups`, `District/School`, `Professional, Trade & Student Associations`, `Libraries`, `Curriculum Provider` |
| `description` | string | About the organization |
| `location` | string | Free-text address |
| `latitude` | float | |
| `longitude` | float | |
| `website` | string | External URL |
| `phone` | string | |
| `email` | string | |
| `twitter` | string | Full URL |
| `facebook` | string | Full URL |
| `linkedin` | string | Full URL |
| `instagram` | string | Full URL |
| `logo_src` | string | Logo image path |

---

## Page Specifications

### 1. Homepage (`/`)

The homepage is a landing page that funnels visitors into the opportunity finder. It should feel active and current — the main value proposition is "find STEM events happening now."

**Sections, top to bottom:**

1. **Hero**: Full-width banner with the Ecosystem tagline and a prominent search/CTA. The hero should contain:
   - Headline: "San Diego STEM Ecosystem" (or similar from original)
   - Subhead: short value prop about connecting people with STEM opportunities
   - **Primary CTA button**: "Find Opportunities" → links to `/opportunities`
   - **Quick search bar** (optional but recommended): a text input + a few quick-filter buttons (e.g., "Free", "This Week", "For Families") that link to `/opportunities` with pre-set query params

2. **Featured Opportunities**: A curated row of 3-4 opportunity cards. Selection logic: soonest upcoming `date_start`, prioritizing `cost_range: "Free"`. Use the `OpportunityCard` component.

3. **How It Works / What We Do**: A short 3-column section (icon + short text) explaining the Ecosystem's purpose. Content can be pulled from the original site's About section. Keep it to 2-3 sentences per column. This is static Markdown-editable content.

4. **Partner Logos**: A scrolling or grid display of partner logos, linking to `/partners`. Show a representative sample (12-20 logos), not all 195. Prioritize partners that have active opportunities.

5. **Call to Action Strip**: A full-width colored band with "Are you a STEM organization? Join the Ecosystem" or similar, linking to `/contact`.

### 2. Opportunity Listing (`/opportunities`)

This is the core page of the site. It's a filterable, searchable listing of all opportunities.

**Layout**: Two-column on desktop (filter sidebar left, results right). Single column on mobile with filters in a collapsible panel.

**Filter Sidebar** (`OpportunityFilters` component):

The following filters should be available. Each is a group of checkboxes (multi-select) except where noted. Filters are AND across categories, OR within a category (e.g., selecting "Grades 3-5" AND "Grades 6-8" shows opportunities tagged with either).

| Filter Group | Type | Values |
|---|---|---|
| **Search** | Text input | Searches title and description |
| **Opportunity Type** | Checkbox group | All 8 `opportunity_type` values |
| **Age / Grade Level** | Checkbox group | All 10 `age_grade_level` values |
| **Areas of Interest** | Checkbox group | All 11 `areas_of_interest` values |
| **Cost** | Checkbox group | All 6 `cost_range` values |
| **Time of Day** | Checkbox group | All 6 `time_of_day` values |
| **Financial Support Available** | Toggle/checkbox | Filters to `financial_support: "Yes"` |
| **NGSS Aligned** | Toggle/checkbox | Filters to `ngss_aligned: "Yes"` |

Additional filter behaviors:
- Show the count of matching results next to the filter group header or in a results summary bar: "Showing 12 of 54 opportunities"
- A "Clear All Filters" button
- Filter state should be reflected in the URL query string so filtered views are shareable/bookmarkable
- On mobile, the filter panel should be a slide-out or accordion that starts collapsed, with a "Filter" button to open it

**Results Area** (`OpportunityGrid` component):

- Default sort: by `date_start` ascending (soonest first)
- Each result renders as an `OpportunityCard`
- No pagination needed at this scale (30-80 items). Show all results on one page. If the dataset unexpectedly grows past ~100, add simple pagination at that point.
- A **map/list toggle** at the top of the results area. List view is default. Map view shows results as pins on a Leaflet map (using `latitude`/`longitude`), with card popups on click.

**OpportunityCard** component:

Displays a single opportunity in the listing. Should show:
- Partner logo (small, left-aligned or top)
- Opportunity title (linked to detail page)
- Partner name
- `opportunity_type` as a tag/badge
- `date_start` formatted human-readable (or "Ongoing" if no date)
- `cost_range` — highlight "Free" visually
- `age_grade_level` as small tags
- Truncated description (2-3 lines)
- "Learn More" link to detail page

### 3. Opportunity Detail (`/opportunities/[slug]`)

A full page for a single opportunity. Generated statically from the JSON at build time (Astro dynamic routes with `getStaticPaths`).

**Content:**
- **Title** (large heading)
- **Partner attribution**: logo + name, linked to partner detail page
- **Key details sidebar or info box**:
  - Date/time: formatted `date_start` – `date_end`, plus `availability` text
  - Cost: `cost_range`
  - Age/Grade: `age_grade_level` as tags
  - Areas: `areas_of_interest` as tags
  - Location: `location` text + small map if lat/lng available
  - NGSS Aligned: badge if yes
  - Financial Support: badge if yes
- **Description**: full `description` text
- **Registration/Link**: prominent button linking to `link` (opens in new tab). Label: "Register" or "Learn More" depending on context.
- **Contact info**: name, email, phone
- **Back link**: "← Back to Opportunities"

### 4. Partner Directory (`/partners`)

A filterable directory of all partner organizations.

**Layout**: Same two-column pattern as opportunities. Filter sidebar left, results right.

**Filter Sidebar** (`PartnerFilters`):

| Filter Group | Type | Values |
|---|---|---|
| **Search** | Text input | Searches name and description |
| **Organization Type** | Checkbox group | All 10 `organization_type` values |

**Results Area** (`PartnerGrid`):

- Default sort: alphabetical by name
- Each result renders as a `PartnerCard`
- Map/list toggle, same as opportunities page

**PartnerCard** component:

- Logo
- Organization name (linked to detail page)
- `organization_type` as a tag
- Truncated description (2 lines)
- Location (city/area only — parse from the `location` string)

### 5. Partner Detail (`/partners/[id]`)

A full page for a single partner. Generated statically.

**Content:**
- **Name** (heading)
- **Logo** (large)
- **Organization type** as badge
- **Description**: full text
- **Contact info**: phone, email, website link
- **Social links**: Twitter, Facebook, LinkedIn, Instagram — show icons for any that have values
- **Location**: address + map if lat/lng available
- **Opportunities from this partner**: a list/grid of `OpportunityCard` components, filtered to where `partner_name` matches. If none, show "No current opportunities listed." This cross-link is important — it's how visitors discover what a partner offers.

### 6. About (`/about`)

Static content page using the `ContentPage` layout. Pull content from the original site's About/Mission pages. Describes what the STEM Ecosystem is, who's involved, what it does.

This page is authored in Markdown at `src/content/pages/about.md` with frontmatter for title and optional sections. Keep it simple — it's a single-scroll page, not tabbed.

### 7. Contact (`/contact`)

Static page with:
- Ecosystem contact info (email, phone)
- A brief section: "Want to add your organization?" with instructions or a link to a Google Form (external)
- Physical address / mailing address if available
- Embedded map of the Ecosystem office location (optional)

---

## Navigation

**Header nav** (persistent across all pages):

```
[Logo]  Home  |  Opportunities  |  Partners  |  About  |  Contact
```

Keep it flat. No dropdowns. On mobile, collapse to a hamburger menu.

The original site has more nav items (News, Get Involved, Programs, etc.) — do **not** include these. The site is intentionally smaller.

**Footer:**
- Ecosystem name + tagline
- Repeat nav links
- Social media links (if the Ecosystem has them)
- "Last updated: [date from scrape-meta.json]" — shows visitors the data is current
- Funder/sponsor logos (row of small logos, same as original site footer)

---

## Component Behavior Notes

### Client-Side Filtering (`src/scripts/filters.js`)

This is the most complex piece of JavaScript on the site. It powers both the Opportunities and Partners listing pages.

Implementation approach:
1. At build time, Astro renders all cards into the page as HTML with `data-*` attributes encoding their filterable values (e.g., `data-type="Online"`, `data-age="Grades 3-5,Grades 6-8"`, `data-cost="Free"`).
2. The filter JS reads checkbox states, compares against `data-*` attributes, and toggles card visibility with CSS classes.
3. URL query params are synced bidirectionally: changing filters updates the URL; loading a URL with params pre-checks the corresponding filters.

For multi-value fields (age, areas, time_of_day), store as comma-separated in the data attribute. The filter matches if **any** of the card's values match **any** of the checked filter values (OR within group).

Across groups, filters are AND: a card must match at least one value in **every** active filter group to be shown.

### Map Component

Use Leaflet with OpenStreetMap tiles (free, no API key). Both the opportunities and partners pages need map views.

The map should:
- Show pins for all currently-filtered results (not all results, just visible ones)
- Cluster pins when zoomed out (use Leaflet.markercluster)
- Show a popup on pin click with: name, type badge, and link to detail page
- Auto-fit bounds to show all visible pins

### Date Handling

The `opportunities.json` file that ships with the site contains **only current and upcoming events**. The scraper is responsible for filtering out past events before committing — the site itself does not need to deal with stale data.

- Display dates in a human-friendly format: "March 5, 2025" not "2025-03-05T12:00:00Z"
- For ongoing/undated opportunities (no `date_start`), display "Ongoing"
- If an opportunity has both `date_start` and `date_end`, show the range: "March 5 – March 9, 2025"
- The reference dataset (`opportunities.json` in the project files) contains ~330 historical records going back to 2019. This is the scraped archive. For development and testing, filter to records with `date_start` in the future (or use a small hand-curated test set). The production scraper will only produce current events.

### Logo Handling

The `logo_src` values in both datasets are relative paths from the old Drupal site. During the build pipeline (separate from this implementation), logos will be downloaded and placed in `public/images/logos/`. The filenames will be normalized. Use a helper function to resolve logo paths:

```javascript
function getLogoPath(logoSrc) {
  if (!logoSrc) return '/images/logos/default-partner.png';
  // Extract filename from the Drupal path
  const filename = logoSrc.split('/').pop().split('?')[0];
  return `/images/logos/${filename}`;
}
```

Provide a default/placeholder logo for partners without one.

---

## Responsive Behavior

Follow the original site's breakpoints and responsive patterns. Key behaviors:

- **Desktop** (>1024px): Two-column layout on listing pages (sidebar + results). Full nav in header.
- **Tablet** (768-1024px): Filter sidebar collapses to top of page or toggle panel. Cards in 2-column grid.
- **Mobile** (<768px): Single column. Hamburger nav. Filter panel behind a "Filter" button. Cards stack vertically. Map view works but is secondary to list view.

---

## SEO & Meta

Each page should have:
- Unique `<title>` tag (e.g., "Find STEM Opportunities | SD STEM Ecosystem")
- `<meta name="description">` — for detail pages, use the first 160 chars of the description field
- Open Graph tags (`og:title`, `og:description`, `og:image`) — use partner logo for detail pages, site logo for listing/static pages
- Canonical URLs

Generate a `sitemap.xml` at build time (Astro has a plugin for this).

---

## What's NOT In Scope

Do not implement:
- News/blog section
- "Get Involved" pages
- Working group pages (Role Model, Early Childhood, etc.)
- User login / registration
- Partner self-service event submission
- Newsletter signup
- Collab Lab archive
- FAQ page
- Any CMS or admin interface
- Comments or user-generated content

These may be added later. For now, the site is: Homepage → Opportunities → Partners → About → Contact.

---

## Build & Deploy

- `npm run build` produces a fully static site in `dist/`
- GitHub Actions workflow: on push to `main`, run build and deploy to hosting
- The scraper (separate repo/process) commits updated JSON files to this repo on a schedule, which triggers the build
- `scrape-meta.json` contains `{ "last_updated": "2025-04-09T12:00:00Z" }` — display this in the footer so visitors know the data is fresh
