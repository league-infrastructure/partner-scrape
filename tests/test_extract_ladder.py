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
    reduce_html_to_text,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "html"

#: Shared with tests/test_adapters_program_page.py -- the ~900KB bloated
#: fixture representative of the SD Foundation site's own live-measured
#: template bloat (issue 36) lives here, not under fixtures/html/, since
#: it is also fetched as a program page fixture body.
PROGRAM_PAGES_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "program_pages"

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


# ---------------------------------------------------------------------
# reduce_html_to_text (sprint 028, issue 36)
# ---------------------------------------------------------------------


class TestReduceHtmlToTextOversizedPage:
    """AC: a saved ~900KB fixture page (representative of the SD
    Foundation site's own live-measured template bloat -- a large
    repeated nav menu plus an inline script payload on every page)
    reduces to well under the 200K-token model context limit.
    """

    def test_bloated_page_reduces_well_under_the_token_limit(self):
        html = (PROGRAM_PAGES_FIXTURES_DIR / "sd_foundation_bloated_page.html").read_text()
        # The two live sprint-027 failures measured 840KB-965KB
        # (sdfoundation.org) and 612KB (rmtlacademy.org) raw HTML; this
        # fixture reproduces that shape.
        assert len(html) > 800_000

        reduced = reduce_html_to_text(html)

        # Comfortably under the default 100_000-char cap, and therefore
        # comfortably under the ~200K-token (≈800K-char) model limit that
        # motivated this function -- the nav/header/footer/script bloat
        # that made up nearly the entire raw page is gone, leaving only
        # the page's actual program content.
        assert len(reduced) < 100_000
        assert len(reduced) < len(html) / 100

    def test_bloated_page_still_contains_the_real_program_content(self):
        html = (PROGRAM_PAGES_FIXTURES_DIR / "sd_foundation_bloated_page.html").read_text()

        reduced = reduce_html_to_text(html)

        assert "Fixture SD Foundation Community Scholarship" in reduced
        assert "November 1, 2026" in reduced
        assert "$5,000 scholarship" in reduced

    def test_bloated_page_s_nav_header_footer_script_bloat_is_gone(self):
        html = (PROGRAM_PAGES_FIXTURES_DIR / "sd_foundation_bloated_page.html").read_text()

        reduced = reduce_html_to_text(html)

        assert "Program Category" not in reduced  # <nav> mega-menu
        assert "Footer Section" not in reduced  # <footer>
        assert "trackingConfig" not in reduced  # <script>


class TestReduceHtmlToTextOrdinaryPageIsANoOp:
    """AC: reducing an already-small page is a no-op on its extracted
    fields -- the ordinary program-page fixture's real content survives
    reduction unchanged in substance (only markup/whitespace differs).
    """

    def test_small_ordinary_page_keeps_its_content_and_stays_small(self):
        html = (PROGRAM_PAGES_FIXTURES_DIR / "prose_program_page.html").read_text()

        reduced = reduce_html_to_text(html)

        assert len(reduced) < len(html)
        assert len(reduced) < 1_000
        assert "Fixture Research Experience for High School Students" in reduced
        assert "$2,500 stipend" in reduced
        assert "February 15" in reduced


class TestReduceHtmlToTextTruncation:
    """AC/design: truncation keeps the *leading* max_chars characters of
    reduced text, never the whole page -- a program page states its key
    facts near the top (extract/DESIGN.md's sprint 028 invariant).
    """

    def test_truncates_to_the_leading_max_chars_characters(self):
        html = "<body><p>" + ("word " * 50) + "</p></body>"

        reduced = reduce_html_to_text(html, max_chars=20)

        assert reduced == ("word " * 50).strip()[:20]
        assert len(reduced) == 20

    def test_a_page_under_max_chars_is_not_padded_or_altered(self):
        html = "<body><p>short page content</p></body>"

        reduced = reduce_html_to_text(html, max_chars=100_000)

        assert reduced == "short page content"


class TestReduceHtmlToTextMalformedOrEmpty:
    """AC: returns "" for unparseable/empty HTML, with a logged warning,
    never raising -- matching extract_fields()'s own contract exactly.
    """

    def test_empty_string_returns_empty_string_without_raising(self, caplog):
        with caplog.at_level("WARNING"):
            result = reduce_html_to_text("")

        assert result == ""

    def test_whitespace_only_returns_empty_string_without_raising(self):
        assert reduce_html_to_text("   \n\t  ") == ""


class TestReduceHtmlToTextStripsBoilerplateBeforeTruncating:
    """Design: stripping nav/header/footer/script happens before the
    character cap applies -- otherwise a small max_chars budget would be
    entirely consumed by boilerplate that a real caller never wants.
    """

    def test_leading_nav_does_not_consume_the_truncation_budget(self):
        html = (
            "<body>"
            "<nav>" + ("nav link " * 50) + "</nav>"
            "<main>real program content</main>"
            "</body>"
        )

        reduced = reduce_html_to_text(html, max_chars=10)

        assert reduced == "real progr"
        assert "nav link" not in reduced
