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


class TestNoTitleAnywhere:
    def test_no_title_page_yields_no_title_field(self):
        html = _read_fixture("no_title.html")

        fields = extract_fields(html, "https://example.org/events/mystery/")

        assert "title" not in fields
