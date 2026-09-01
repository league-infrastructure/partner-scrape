"""Tests for partner_scrape.registry.validate_roster: the roster
content-validation and join-integrity primitives (issue 48).

Every fixture here is a small, hand-built in-memory dict/dataclass --
no TOML files, no JSON fixture files, no disk I/O -- matching this
project's flat `tests/test_registry_*.py` naming for the `registry/`
package (see `test_registry.py`, `test_registry_candidates.py`).
"""

from __future__ import annotations

import pytest

from partner_scrape.normalize.partners import find_partner, normalize_org_name
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.registry.validate_roster import (
    BARE_CALIFORNIA_CENTROID,
    HIJACKED_DOMAINS,
    SD_BOUNDS,
    RosterValidationError,
    check_partner_references,
    find_unresolved_active_sources,
    validate_roster,
)


def _partner(
    id: int = 1,
    name: str = "Example Org",
    latitude: object = 32.8,
    longitude: object = -117.1,
    website: str | None = "https://example.org",
) -> dict:
    """A clean, valid partner row by default -- individual tests
    override only the field(s) relevant to the check under test."""
    return {
        "id": id,
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "website": website,
    }


def _source(org_name: str, source_id: str | None = None) -> SourceConfig:
    return SourceConfig(
        source_id=source_id or org_name,
        org_name=org_name,
        adapter_type="tec_rest",
        config={},
    )


class TestBareCaliforniaCentroid:
    def test_fires_on_the_exact_centroid(self):
        partners = [
            _partner(
                id=1,
                latitude=BARE_CALIFORNIA_CENTROID[0],
                longitude=BARE_CALIFORNIA_CENTROID[1],
            )
        ]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        assert "id=1" in str(exc_info.value)

    def test_fires_when_coordinate_rounds_to_the_centroid_at_six_decimal_places(self):
        # Off by less than half of the 6th decimal place -- must still
        # be caught, matching the deleted test's own round(x, 6) convention.
        partners = [
            _partner(
                id=2,
                latitude=BARE_CALIFORNIA_CENTROID[0] + 0.0000001,
                longitude=BARE_CALIFORNIA_CENTROID[1] - 0.0000001,
            )
        ]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        assert "id=2" in str(exc_info.value)

    def test_passes_on_a_clean_in_bounds_coordinate(self):
        partners = [_partner(id=3, latitude=32.8, longitude=-117.1)]

        validate_roster(partners)  # must not raise


class TestOutOfBoundsOrMalformedCoordinate:
    def test_fires_on_out_of_bounds_coordinate(self):
        partners = [
            _partner(id=4, latitude=SD_BOUNDS["latMax"] + 1.0, longitude=-117.1)
        ]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        assert "id=4" in str(exc_info.value)

    def test_fires_on_partial_coordinate_one_of_lat_lng_set(self):
        partners = [_partner(id=5, latitude=32.8, longitude=None)]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        assert "id=5" in str(exc_info.value)

    def test_fires_on_non_numeric_coordinate(self):
        partners = [_partner(id=6, latitude="not-a-number", longitude=-117.1)]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        assert "id=6" in str(exc_info.value)

    def test_passes_on_a_clean_in_bounds_coordinate(self):
        partners = [_partner(id=7, latitude=32.8, longitude=-117.1)]

        validate_roster(partners)  # must not raise

    def test_both_coordinates_absent_is_not_an_offender(self):
        # The documented "no coordinate yet" state -- not bad data.
        partners = [_partner(id=8, latitude=None, longitude=None)]

        validate_roster(partners)  # must not raise


class TestHijackedDomain:
    def test_fires_on_known_hijacked_domain(self):
        [domain] = HIJACKED_DOMAINS
        partners = [_partner(id=9, website=f"https://{domain}/events")]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        message = str(exc_info.value)
        assert "id=9" in message
        assert domain in message

    def test_passes_on_a_clean_website(self):
        partners = [_partner(id=10, website="https://example.org")]

        validate_roster(partners)  # must not raise


class TestDuplicateSlug:
    def test_fires_on_a_colliding_pair(self):
        partners = [
            _partner(id=11, name="Same Org!"),
            _partner(id=12, name="Same Org"),
        ]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        message = str(exc_info.value)
        assert "id=11" in message
        assert "id=12" in message

    def test_passes_on_distinct_slugs(self):
        partners = [
            _partner(id=13, name="Org One"),
            _partner(id=14, name="Org Two"),
        ]

        validate_roster(partners)  # must not raise

    def test_three_rows_two_colliding_one_distinct_reports_both_offenders_together(self):
        partners = [
            _partner(id=15, name="Same Org!"),
            _partner(id=16, name="Same Org"),
            _partner(id=17, name="Totally Different Org"),
        ]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        message = str(exc_info.value)
        assert "id=15" in message
        assert "id=16" in message
        assert "id=17" not in message  # the distinct row is not an offender


class TestValidatesRawListNotDeduplicatedView:
    """The dedicated proof (ticket 002's own Testing section) that
    `validate_roster()` operates on the *raw* partner list, never a
    name-deduplicated view like `normalize.partners.load_partners()`'s
    own `partners_by_norm` -- see sprint.md's Design Rationale:
    `load_partners()`'s `setdefault()` means a colliding second row
    never even enters that dict, so a check built on it would be
    structurally blind to issue 46's exact failure mode.
    """

    def test_load_partners_style_dedup_hides_the_second_row_but_validate_roster_still_catches_it(
        self,
    ):
        # Two rows that collide under BOTH model.slugify() (the check
        # this ticket adds) AND normalize_org_name() (the join key
        # load_partners()/find_partner() use) -- i.e. exactly the shape
        # that would collapse under either function.
        first = _partner(id=20, name="Coastal Roots Farm!")
        second = _partner(id=21, name="Coastal Roots Farm")

        assert normalize_org_name(first["name"]) == normalize_org_name(second["name"])

        # Reproduce load_partners()'s own documented setdefault-based
        # dedup in-memory -- load_partners() itself only reads from a
        # file path, and this test file is hermetic (no disk I/O), so
        # this replicates its exact behavior (first row wins a
        # normalized-name collision) rather than calling it directly.
        partners_by_norm: dict[str, dict] = {}
        for partner in (first, second):
            partners_by_norm.setdefault(normalize_org_name(partner["name"]), partner)

        assert len(partners_by_norm) == 1  # the second row never entered the dict

        # find_partner() -- the real, unmodified production function --
        # confirms the second row is genuinely invisible to a
        # load_partners()-based check: looking it up resolves to the
        # first row instead.
        resolved = find_partner(second["name"], partners_by_norm)
        assert resolved is not None
        assert resolved["id"] == first["id"]

        # validate_roster() operates on the raw list, not this
        # deduplicated view -- it still catches the collision.
        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster([first, second])

        message = str(exc_info.value)
        assert "id=20" in message
        assert "id=21" in message


class TestRaisesOneCombinedExceptionForMultipleOffenders:
    def test_offenders_from_different_checks_are_named_in_one_raised_exception(self):
        [domain] = HIJACKED_DOMAINS
        partners = [
            _partner(
                id=30,
                latitude=BARE_CALIFORNIA_CENTROID[0],
                longitude=BARE_CALIFORNIA_CENTROID[1],
            ),
            _partner(id=31, website=f"https://{domain}/"),
            _partner(id=32, name="Dup Org!"),
            _partner(id=33, name="Dup Org"),
        ]

        with pytest.raises(RosterValidationError) as exc_info:
            validate_roster(partners)

        message = str(exc_info.value)
        assert "id=30" in message
        assert "id=31" in message
        assert "id=32" in message
        assert "id=33" in message


class TestFindUnresolvedActiveSources:
    def test_returns_exactly_the_non_resolving_org_names(self):
        partners_by_norm = {
            normalize_org_name("Coastal Roots Farm"): {"id": 1, "name": "Coastal Roots Farm"},
        }
        sources = [
            _source("Coastal Roots Farm", source_id="crf"),
            _source("Totally Unknown Org", source_id="unknown"),
        ]

        result = find_unresolved_active_sources(sources, partners_by_norm)

        assert result == ["Totally Unknown Org"]

    def test_returns_empty_list_when_every_source_resolves(self):
        partners_by_norm = {
            normalize_org_name("Coastal Roots Farm"): {"id": 1, "name": "Coastal Roots Farm"},
        }
        sources = [_source("Coastal Roots Farm", source_id="crf")]

        assert find_unresolved_active_sources(sources, partners_by_norm) == []

    def test_never_raises_even_when_nothing_resolves(self):
        partners_by_norm: dict = {}
        sources = [_source("Nothing Matches", source_id="x")]

        # Deliberately non-raising -- the caller decides what to do
        # with the result (ticket 003 logs it as a warning).
        result = find_unresolved_active_sources(sources, partners_by_norm)

        assert result == ["Nothing Matches"]


class TestCheckPartnerReferences:
    def test_raises_naming_every_dangling_pair(self):
        partners = [_partner(id=1), _partner(id=2, name="Other Org")]
        references: list[tuple[str, int]] = [
            ("place-a", 1),  # resolves -- not an offender
            ("place-b", 99),
            ("place-c", 100),
        ]

        with pytest.raises(RosterValidationError) as exc_info:
            check_partner_references(references, partners)

        message = str(exc_info.value)
        assert "place-b" in message
        assert "99" in message
        assert "place-c" in message
        assert "100" in message
        assert "place-a" not in message

    def test_does_not_raise_when_every_reference_resolves(self):
        partners = [_partner(id=1), _partner(id=2, name="Other Org")]
        references: list[tuple[str, int]] = [("place-a", 1), ("place-b", 2)]

        check_partner_references(references, partners)  # must not raise
