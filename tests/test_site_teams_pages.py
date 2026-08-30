"""Structural guard tests for the `/teams` site section (sprint 011
ticket 005), matching `test_site_data_access_page.py`'s convention of
asserting against the Astro source text rather than driving a real
`astro build` (no such precedent exists in this suite -- see
`tests/test_site_data_access_page.py`'s module docstring for the
pattern this mirrors).

Two defects these tests exist specifically to catch:

1. **The `PartnerCard` map-popup bug reintroduced in `TeamCard`.**
   `PartnerCard.astro` wraps its whole card body in one outer `<a>`, so
   its `<h3>` has no nested `<a>` and the map's own
   `card.querySelector('h3 a')` silently returns `null` (a live bug on
   the Partners map today -- sprint 011 Design Rationale).
   `TeamCard.astro` must model `OpportunityCard.astro` instead: the
   title anchor nested inside `<h3>`.
2. **City-precision teams plotted as individual pins.** ~70 teams sit
   at `location_precision: "city"` and mostly collapse onto a handful
   of shared city centroids; plotting each as its own pin would stack
   dozens of markers on one point and read as a single team. The map
   script must group them into one labelled badge per city instead.
"""

from __future__ import annotations

import re
from pathlib import Path

SITE_SRC = Path(__file__).resolve().parent.parent / "site" / "src"

TEAM_CARD = SITE_SRC / "components" / "TeamCard.astro"
TEAM_FILTERS = SITE_SRC / "components" / "TeamFilters.astro"
TEAMS_INDEX = SITE_SRC / "pages" / "teams" / "index.astro"
TEAMS_DETAIL = SITE_SRC / "pages" / "teams" / "[slug].astro"
HEADER = SITE_SRC / "components" / "Header.astro"
FOOTER = SITE_SRC / "components" / "Footer.astro"


def test_all_teams_site_files_exist():
    for path in (TEAM_CARD, TEAM_FILTERS, TEAMS_INDEX, TEAMS_DETAIL):
        assert path.is_file(), f"expected {path} to exist"


# === TeamCard: h3>a nesting, not the PartnerCard whole-card-anchor defect ===


def test_team_card_title_anchor_nested_inside_h3():
    source = TEAM_CARD.read_text(encoding="utf-8")
    assert re.search(r"<h3>\s*<a[\s>]", source), (
        "TeamCard.astro's title anchor must be nested inside <h3> "
        "(matching OpportunityCard.astro), not wrapping the whole card "
        "(the PartnerCard.astro pattern) -- the map's "
        "card.querySelector('h3 a') depends on this exact nesting."
    )


def test_team_card_does_not_wrap_whole_body_in_one_anchor():
    source = TEAM_CARD.read_text(encoding="utf-8")
    # The PartnerCard defect: <a class="partner-card-link"> opens right
    # after the <article>, wrapping the image/h3/etc. Guard against the
    # same shape reappearing in TeamCard.
    assert not re.search(r"<article[^>]*>\s*<a\b", source), (
        "TeamCard.astro must not wrap its entire card body in one outer "
        "<a> immediately after <article> -- that is the PartnerCard "
        "structure this ticket explicitly avoids."
    )


def test_team_card_has_data_type_attribute():
    source = TEAM_CARD.read_text(encoding="utf-8")
    assert "data-type=" in source, (
        "Every card needs a data-type attribute or scripts/filters.js "
        "cannot see it (excluded from the '#results-grid [data-type]' "
        "selector and the 'Showing X of Y' count)."
    )


# === TeamCard: website badge (013-002) -- confirmed only, via SocialIcon ===


def test_team_card_imports_social_icon_website_platform():
    source = TEAM_CARD.read_text(encoding="utf-8")
    assert "import SocialIcon from './SocialIcon.astro'" in source, (
        "the website badge must reuse SocialIcon.astro's 'website' "
        "platform icon, not a new asset."
    )
    assert re.search(r"<SocialIcon\s+platform=\"website\"", source), (
        "TeamCard.astro must render SocialIcon with platform=\"website\""
    )


def test_team_card_website_badge_gated_on_confirmed_status():
    source = TEAM_CARD.read_text(encoding="utf-8")
    # The badge must be gated on website_status === 'confirmed', not raw
    # website truthiness -- an 'unverified' website (a URL that failed a
    # live fetch) must never render the same badge as a working link.
    assert re.search(
        r"hasConfirmedWebsite\s*=\s*team\.website_status\s*===\s*['\"]confirmed['\"]",
        source,
    ), (
        "the website badge must be derived from "
        "team.website_status === 'confirmed', not team.website truthiness"
    )
    assert re.search(r"\{hasConfirmedWebsite\s*&&", source), (
        "the SocialIcon badge must be conditionally rendered on "
        "hasConfirmedWebsite"
    )


def test_team_card_has_data_website_attribute_for_filter_matching():
    source = TEAM_CARD.read_text(encoding="utf-8")
    assert re.search(
        r"data-website=\{hasConfirmedWebsite\s*\?\s*['\"]true['\"]\s*:\s*['\"]false['\"]\}",
        source,
    ), (
        "TeamCard must carry a data-website attribute reflecting "
        "confirmed-status so TeamFilters' 'Has a Website' facet "
        "(scripts/filters.js's dataset-attribute convention) can match "
        "against it."
    )


# === TeamFilters: build-time facet-count pattern, not PartnerFilters' plain list ===


def test_team_filters_uses_build_time_tally_pattern():
    source = TEAM_FILTERS.read_text(encoding="utf-8")
    assert "import teamsData from" in source
    assert re.search(r"function tally", source), (
        "TeamFilters.astro should clone OpportunityFilters.astro's "
        "build-time facet-count tally() pattern, not PartnerFilters.astro's "
        "uncounted checkbox list."
    )


def test_team_filters_has_website_facet_derived_not_tallied():
    source = TEAM_FILTERS.read_text(encoding="utf-8")
    # Modeled on inRegionCount, not tally(): website_status === 'confirmed'
    # is a derived condition, not a raw field value to count directly.
    assert re.search(
        r"hasWebsiteCount\s*=\s*teams\.filter\(\s*t\s*=>\s*t\.website_status\s*===\s*['\"]confirmed['\"]\s*\)\.length",
        source,
    ), (
        "TeamFilters.astro must derive a hasWebsiteCount the same way "
        "inRegionCount is derived (teams.filter(...).length), not via "
        "the generic tally() helper, since 'confirmed' is a derived "
        "condition, not a raw field value."
    )
    assert re.search(r'data-filter="website"\s+value="true"', source), (
        "the 'Has a Website' checkbox must use data-filter=\"website\" "
        "value=\"true\" so it matches TeamCard's data-website attribute"
    )
    assert "Has a Website" in source


def test_team_filters_website_facet_disabled_when_zero():
    source = TEAM_FILTERS.read_text(encoding="utf-8")
    assert re.search(
        r"is-empty['\"]:\s*hasWebsiteCount\s*===\s*0",
        source,
    ), (
        "the 'Has a Website' facet option must follow the same "
        "is-empty/disabled pattern as every other facet when its count "
        "is zero"
    )


# === teams/index.astro: required element IDs/classes filters.js finds by convention ===


def test_teams_index_has_required_filter_engine_hooks():
    source = TEAMS_INDEX.read_text(encoding="utf-8")
    for needle in (
        'id="results-grid"',
        'id="map-container"',
        'class="results-count"',
        'class="view-toggle"',
        "scripts/filters.js",
    ):
        assert needle in source, f"teams/index.astro is missing {needle!r}"


def test_team_card_uses_base_url_for_every_emitted_url():
    # teams/index.astro itself emits no raw hrefs -- it delegates every URL
    # to TeamCard (matching partners/index.astro, which likewise defines no
    # `base` of its own and relies on PartnerCard). TeamCard and the detail
    # page are where URLs are actually built.
    source = TEAM_CARD.read_text(encoding="utf-8")
    assert "import.meta.env.BASE_URL.replace(/\\/+$/, '')" in source


# === Map treatment: city-precision teams are badged, not pinned individually ===


def test_map_script_groups_city_precision_into_badges_not_pins():
    source = TEAMS_INDEX.read_text(encoding="utf-8")

    # Extract just the client <script> block containing the map logic
    # (there are two <script> tags on this page: filters.js and the
    # inline map-toggle script).
    script_match = re.search(r"<script>(.*?)</script>", source, re.S)
    assert script_match, "expected an inline <script> block on teams/index.astro"
    script = script_match.group(1)

    assert "location_precision" not in script or "precision" in script
    assert re.search(r"precision\s*===\s*['\"]city['\"]", script), (
        "map script must branch on location_precision === 'city' to "
        "group city-precision teams separately from individually-pinned "
        "school/zip teams."
    )

    # The circleMarker (individual pin) call must be reachable only via a
    # path that has already returned/continued out of the 'city' branch:
    # there must be exactly one circleMarker call site, and a `return`
    # must sit textually between the city-precision check and that call,
    # so a city-precision card can never reach it.
    city_check = re.search(r"precision\s*===\s*['\"]city['\"]", script)
    assert city_check, "expected a `precision === 'city'` check"

    circle_marker_calls = list(re.finditer(r"circleMarker\(", script))
    assert len(circle_marker_calls) == 1, (
        f"expected exactly one circleMarker() call site (for school/zip "
        f"precision only), found {len(circle_marker_calls)}"
    )

    between = script[city_check.end() : circle_marker_calls[0].start()]
    assert "return" in between, (
        "the city-precision branch must return before falling through to "
        "the individual-pin (circleMarker) code path"
    )

    # City badges must be labelled (city name + count) via a real DOM
    # marker, never a jittered coordinate and never Leaflet's built-in
    # marker-cluster plugin (a plain, unlabeled cluster implies the
    # centroid itself means something).
    assert "divIcon" in script, (
        "city-precision teams must render as a labelled divIcon badge, "
        "not a plain marker"
    )
    assert "MarkerCluster" not in script and "markerClusterGroup" not in script, (
        "must not use a generic clustering plugin for city-precision "
        "teams -- a labelled per-city badge is required instead"
    )
    # Jitter would add a random offset to a shared city centroid -- guard
    # against that reappearing.
    assert "Math.random" not in script, (
        "city-precision markers must never be jittered -- that fabricates "
        "precision and would shift on every regeneration"
    )

    # Clicking a badge must open a list of that city's teams (a <ul> of
    # per-team links), never a single-team popup.
    assert "<ul" in script and "bindPopup" in script


def test_map_script_excludes_out_of_region_teams():
    source = TEAMS_INDEX.read_text(encoding="utf-8")
    script_match = re.search(r"<script>(.*?)</script>", source, re.S)
    script = script_match.group(1)
    assert re.search(r"dataset\.region\s*!==\s*['\"]true['\"]", script), (
        "in_region=false teams must be excluded from the map -- at least "
        "one out-of-region team's city centroid (San Clemente) falls "
        "inside the San Diego bounding box, so the bounding-box check "
        "alone is not sufficient"
    )


def test_map_script_reuses_sd_bounds_and_marker_colour():
    source = TEAMS_INDEX.read_text(encoding="utf-8")
    assert "32.4" in source and "33.5" in source, "SD_BOUNDS latitude range missing"
    assert "-117.7" in source and "-116.0" in source, "SD_BOUNDS longitude range missing"
    assert "#c83e8e" in source, "expected the site's shared marker colour"


# === Detail page: getStaticPaths over teams.json, slug not bare number ===


def test_teams_detail_page_uses_get_static_paths_over_teams_json():
    source = TEAMS_DETAIL.read_text(encoding="utf-8")
    assert "export function getStaticPaths()" in source
    assert "teamsData" in source and "teams.json" in source
    assert "params: { slug:" in source


def test_teams_detail_page_uses_base_url():
    source = TEAMS_DETAIL.read_text(encoding="utf-8")
    assert "import.meta.env.BASE_URL.replace(/\\/+$/, '')" in source


# === Detail page: Team Website field gated on website_status (013-002) ===
# Issue 21 is explicit: "a broken link published on a public directory is
# worse than no link" -- a clickable <a> must never appear for a website
# this project already knows failed a live fetch.


def test_teams_detail_page_website_link_gated_on_confirmed():
    source = TEAMS_DETAIL.read_text(encoding="utf-8")
    assert re.search(
        r"team\.website\s*&&\s*team\.website_status\s*===\s*['\"]confirmed['\"]",
        source,
    ), (
        "the clickable Team Website <a> must be gated on "
        "team.website_status === 'confirmed', not on team.website alone"
    )


def test_teams_detail_page_unverified_website_renders_plain_text_not_link():
    source = TEAMS_DETAIL.read_text(encoding="utf-8")
    assert re.search(
        r"team\.website\s*&&\s*team\.website_status\s*===\s*['\"]unverified['\"]",
        source,
    ), "expected a branch gated on website_status === 'unverified'"

    # Extract just the unverified branch's JSX block and confirm it emits
    # no <a> element -- a bare URL as text with a note, per issue 21.
    match = re.search(
        r"\{team\.website\s*&&\s*team\.website_status\s*===\s*['\"]unverified['\"][\s\S]*?</dd>[\s\S]*?\)\}",
        source,
    )
    assert match, "could not isolate the unverified-website JSX block"
    unverified_block = match.group(0)
    assert "<a " not in unverified_block and "<a>" not in unverified_block, (
        "an 'unverified' website must render as plain unlinked text, "
        "never a clickable <a>"
    )
    assert "not yet verified" in unverified_block.lower(), (
        "the unverified website note must explain the link is unverified"
    )


def test_teams_detail_page_website_status_none_renders_nothing():
    # No explicit 'none' branch is required or expected: team.website is
    # empty for a 'none'-status team (no known URL), so both the
    # 'confirmed' and 'unverified' branches' `team.website &&` guard
    # already short-circuits -- this is existing, unchanged behavior.
    # Guard that no unconditional third branch was added that would
    # break this.
    source = TEAMS_DETAIL.read_text(encoding="utf-8")
    website_status_branches = re.findall(r"team\.website_status\s*===\s*['\"](\w+)['\"]", source)
    assert set(website_status_branches) == {"confirmed", "unverified"}, (
        f"expected exactly the 'confirmed'/'unverified' website_status "
        f"branches, found {website_status_branches}"
    )


# === Nav: Teams added to both Header.astro and Footer.astro (separate lists) ===


def test_teams_nav_item_in_header():
    source = HEADER.read_text(encoding="utf-8")
    assert re.search(r"label:\s*['\"]Teams['\"]", source), (
        "Header.astro's navItems must include a Teams entry"
    )
    assert "href: '/teams'" in source or 'href: "/teams"' in source


def test_teams_nav_item_in_footer():
    source = FOOTER.read_text(encoding="utf-8")
    assert re.search(r">Teams<", source), "Footer.astro must link to Teams"
    assert "${base}/teams" in source
