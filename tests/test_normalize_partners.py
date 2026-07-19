"""Tests for partner_scrape.normalize.partners: the normalized-name partner join.

Uses tests/fixtures/partners.json -- a small synthetic fixture, not the
real stem-ecosystem repo's file, per the ticket's Files to Create/Modify
note (these tests must not depend on a sibling checkout existing).
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.normalize.partners import find_partner, load_partners, normalize_org_name

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PARTNERS_PATH = FIXTURES_DIR / "partners.json"


class TestNormalizeOrgName:
    def test_lowercases(self):
        assert normalize_org_name("Ocean Connectors") == "ocean connectors"

    def test_strips_leading_the(self):
        assert normalize_org_name("The Living Coast Discovery Center") == "living coast discovery center"

    def test_matches_with_and_without_leading_the(self):
        assert normalize_org_name("The Living Coast Discovery Center") == normalize_org_name(
            "Living Coast Discovery Center"
        )

    def test_strips_punctuation_and_collapses_whitespace(self):
        assert normalize_org_name("  I Love A Clean, San Diego!  ") == "i love a clean san diego"


class TestLoadPartners:
    def test_loads_all_fixture_partners_keyed_by_normalized_name(self):
        by_norm = load_partners(PARTNERS_PATH)

        assert by_norm["coastal roots farm"]["id"] == 101
        assert by_norm["living coast discovery center"]["id"] == 102
        assert by_norm["ocean connectors"]["id"] == 103

    def test_accepts_a_string_path_as_well_as_a_path_object(self):
        by_norm = load_partners(str(PARTNERS_PATH))
        assert "ocean connectors" in by_norm

    def test_first_record_wins_a_normalized_name_collision(self, tmp_path):
        dup_path = tmp_path / "partners.json"
        dup_path.write_text(
            '[{"id": 1, "name": "Ocean Connectors"}, {"id": 2, "name": "ocean connectors"}]'
        )

        by_norm = load_partners(dup_path)

        assert by_norm["ocean connectors"]["id"] == 1


class TestFindPartner:
    def test_matching_org_name_returns_the_partner_record(self):
        by_norm = load_partners(PARTNERS_PATH)

        partner = find_partner("Ocean Connectors", by_norm)

        assert partner is not None
        assert partner["id"] == 103

    def test_match_is_normalized_on_both_sides(self):
        by_norm = load_partners(PARTNERS_PATH)

        partner = find_partner("living coast discovery center", by_norm)

        assert partner is not None
        assert partner["id"] == 102

    def test_unmatched_org_name_returns_none(self):
        by_norm = load_partners(PARTNERS_PATH)

        assert find_partner("Some Org Not In The Fixture", by_norm) is None
