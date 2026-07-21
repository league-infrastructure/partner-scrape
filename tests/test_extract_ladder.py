"""Tests for partner_scrape.extract.ladder: the Generic HTML Extractor.

Each test isolates one ladder rung using a synthesized fixture HTML page
that carries only the signal for that rung (tests/fixtures/html/),
matching sprint.md's Test Strategy for SUC-010. ``extract_fields`` takes
HTML/URL strings directly -- no ``Fetcher``, no socket, ever.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from partner_scrape.extract.ladder import (
    CONFIDENCE_BODY_REGEX,
    CONFIDENCE_JSON_LD,
    CONFIDENCE_OPENGRAPH,
    CONFIDENCE_TIME_TAG,
    CONFIDENCE_TITLE_FALLBACK,
    CONFIDENCE_URL_DATE,
    extract_fields,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "html"

#: Confidence must strictly decrease down the ladder -- the ordering
#: itself is a fact worth asserting, not just each tier's individual
#: value (sprint.md: "structured/high -> regex/low").
CONFIDENCE_ORDER = [
    CONFIDENCE_JSON_LD,
    CONFIDENCE_TIME_TAG,
    CONFIDENCE_OPENGRAPH,
    CONFIDENCE_TITLE_FALLBACK,
    CONFIDENCE_URL_DATE,
    CONFIDENCE_BODY_REGEX,
]


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


class TestConfidenceOrdering:
    def test_confidence_tiers_strictly_decrease_down_the_ladder(self):
        assert CONFIDENCE_ORDER == sorted(CONFIDENCE_ORDER, reverse=True)
        assert len(set(CONFIDENCE_ORDER)) == len(CONFIDENCE_ORDER)


class TestJsonLdRung:
    def test_json_ld_event_yields_every_field_at_highest_confidence(self):
        html = _read_fixture("json_ld_event.html")

        fields = extract_fields(html, "https://example.org/events/tide-pool-exploration/")

        assert fields["title"] == ("Tide Pool Exploration", CONFIDENCE_JSON_LD)
        assert fields["description"] == (
            "Explore local tide pools with a marine biologist.",
            CONFIDENCE_JSON_LD,
        )
        assert fields["start"] == (
            datetime.fromisoformat("2026-08-15T09:00:00-07:00"),
            CONFIDENCE_JSON_LD,
        )
        assert fields["end"] == (
            datetime.fromisoformat("2026-08-15T11:00:00-07:00"),
            CONFIDENCE_JSON_LD,
        )
        assert fields["location"] == (
            "Cabrillo Tide Pools, 1800 Cabrillo Memorial Dr, San Diego",
            CONFIDENCE_JSON_LD,
        )
        assert fields["cost"] == ("5", CONFIDENCE_JSON_LD)
        assert fields["image_url"] == (
            "https://example.org/images/tide-pool.jpg",
            CONFIDENCE_JSON_LD,
        )


class TestTimeTagRung:
    def test_time_tag_only_page_yields_dated_event_below_json_ld_confidence(self):
        html = _read_fixture("time_tag_only.html")

        fields = extract_fields(html, "https://example.org/events/beach-cleanup/")

        assert fields["start"] == (datetime(2026, 9, 1, 10, 0, 0), CONFIDENCE_TIME_TAG)
        assert fields["end"] == (datetime(2026, 9, 1, 12, 0, 0), CONFIDENCE_TIME_TAG)
        assert fields["start"][1] < CONFIDENCE_JSON_LD
        assert fields["title"] == ("Beach Cleanup", CONFIDENCE_TITLE_FALLBACK)


class TestOpenGraphRung:
    def test_opengraph_only_page_yields_title_and_description_but_no_date(self):
        html = _read_fixture("opengraph_only.html")

        fields = extract_fields(html, "https://example.org/events/star-party/")

        assert fields["title"] == ("Star Party Night", CONFIDENCE_OPENGRAPH)
        assert fields["description"] == (
            "Telescopes, snacks, and a clear sky.",
            CONFIDENCE_OPENGRAPH,
        )
        assert fields["image_url"] == (
            "https://example.org/images/star-party.jpg",
            CONFIDENCE_OPENGRAPH,
        )
        assert "start" not in fields
        assert "end" not in fields


class TestUrlDateRung:
    def test_url_embedded_date_with_no_structured_signal_yields_dated_event(self):
        html = _read_fixture("url_date_only.html")

        fields = extract_fields(html, "https://example.org/events/star-gazing-2026-04-22/")

        assert fields["start"] == (datetime(2026, 4, 22), CONFIDENCE_URL_DATE)
        assert fields["title"] == ("Star Gazing Night", CONFIDENCE_TITLE_FALLBACK)

    def test_no_url_date_pattern_yields_no_start_field(self):
        html = _read_fixture("url_date_only.html")

        fields = extract_fields(html, "https://example.org/events/star-gazing/")

        assert "start" not in fields


class TestBodyRegexRung:
    def test_body_text_date_with_nothing_else_yields_dated_event_at_lowest_confidence(self):
        html = _read_fixture("body_regex_only.html")

        fields = extract_fields(html, "https://example.org/events/astronomy-talk/")

        assert fields["start"] == (datetime(2026, 5, 13), CONFIDENCE_BODY_REGEX)
        assert fields["start"][1] == min(CONFIDENCE_ORDER)
        assert fields["title"] == ("Astronomy Talk", CONFIDENCE_TITLE_FALLBACK)


class TestBodyRegexScriptStyleExcluded:
    """Sprint 007 ticket 004: ``_extract_body_regex`` must not treat
    ``<script>``/``<style>`` element text as visible page content --
    ticket 003's investigation found ``lxml``'s ``text_content()``
    includes it by default, which can surface a stale/irrelevant
    "date" (e.g. a JS comment) ahead of the genuine one in scan order.
    """

    def test_date_inside_script_tag_is_ignored_in_favor_of_the_real_body_date(self):
        html = _read_fixture("body_regex_script_excluded.html")

        fields = extract_fields(html, "https://example.org/events/planetarium-night/")

        # "January 1, 2020" lives inside a <script> comment ahead of the
        # real date in document order; the old raw text_content()-based
        # scan would have matched it first. It must never win.
        assert fields["start"] == (datetime(2026, 8, 29), CONFIDENCE_BODY_REGEX)


class TestBodyRegexCommentExcluded:
    """Sprint 007 ticket 004: a date living inside an HTML *comment*
    (``<!--...-->``) must never be treated as page content.

    This is the exact real-world failure caught during this ticket's
    live verification against SDNHM: a dead "From the blog" sidebar
    widget, wrapped in an HTML comment (a stale/placeholder "March 9,
    2015" post), appears -- commented out -- on genuinely undated,
    evergreen program pages across the site. lxml's tree iteration
    yields ``Comment`` nodes as ordinary children, and a comment node's
    ``.text`` holds its *entire* raw body -- an early version of
    :func:`_visible_text_parts` that only checked element *tags*
    (``script``/``style``) missed this and surfaced the buried 2015
    date as if it were the real event date on nearly every SDNHM page.
    """

    def test_date_inside_html_comment_is_ignored_leaving_page_undated(self):
        html = _read_fixture("body_regex_comment_excluded.html")

        fields = extract_fields(html, "https://example.org/calendar/camp-o-saurus/")

        # The only "Month DD, YYYY"-shaped text anywhere on this page is
        # the commented-out widget's stale date -- correctly finding
        # nothing (not the stale 2015 date) matches ticket 003's own
        # finding that genuinely evergreen program pages have no
        # instance date and must stay undated, not get a fabricated one.
        assert "start" not in fields
        assert fields["title"] == ("Camp-o-Saurus", CONFIDENCE_TITLE_FALLBACK)


class TestBodyRegexWidenedWindow:
    """Sprint 007 ticket 004: the fix for SDNHM/Air & Space/Fleet's
    missed dates -- ticket 003 found genuine dates at *visible*-text
    offsets of 3274-9357 characters, past the original unconditional
    3000-character raw-text cutoff. This reproduces that shape: an
    inline ``<style>`` block plus a large repeated nav menu ahead of a
    real event date, pushing it past 3000 characters of *visible* text
    too -- proving script/style exclusion alone would not have been
    enough; the widened scan window is what recovers it.
    """

    def test_date_past_the_old_3000_char_window_behind_style_and_nav_noise_is_found(self):
        html = _read_fixture("body_regex_past_old_window.html")

        fields = extract_fields(
            html,
            "https://example.org/calendar/event/kit-model-aviation-collectible-swap-meet-2026",
        )

        assert fields["start"] == (datetime(2026, 6, 13), CONFIDENCE_BODY_REGEX)
        assert fields["title"] == (
            "Kit Model Aviation Collectible Swap Meet",
            CONFIDENCE_TITLE_FALLBACK,
        )


class TestNoTitleAnywhere:
    def test_no_title_page_yields_no_title_field(self):
        html = _read_fixture("no_title.html")

        fields = extract_fields(html, "https://example.org/events/mystery/")

        assert "title" not in fields
