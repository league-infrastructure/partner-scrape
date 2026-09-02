"""Dataset-validity regression tests for the curated Offerings roster
(`partner_scrape/directory/data/offerings.toml`)'s six volunteer org
profile rows (sprint 030, ticket 002, issue 14 Strategy B).

Data-only-ticket tests, matching sprint.md's Test Strategy precedent
for a curated dataset (`tests/directory/test_dataset_validity.py`'s
Places precedent, `tests/directory/test_club_dataset_validity.py`'s
Clubs precedent): these pin down properties of the *real* committed
data -- Fleet/SDZWA/Birch's issue-14-verbatim age minimums, the other
three orgs' honestly-researched age minimums, and every row's
hand-verified `related_partner_id` join -- rather than a synthetic
fixture, so a future edit to `offerings.toml` that regresses one of
these is caught directly.

`TestRelatedPartnerIdJoinIntegrity` drives the real, committed roster
through `directory.pipeline.run_directory()`'s own join-integrity guard
(`_check_related_partner_references()`) with `dry_run=True` (so no
export ever runs -- no `get_own_data_dir()` pinning needed, matching
this sprint's own test hazard warning) and a fixture `site_dir` whose
`partners.json` carries exactly the `related_partner_id` values the
real roster references, parsed straight out of `offerings.toml`'s own
text -- mirrors `test_club_dataset_validity.py`'s identical
`_write_real_partners_fixture` pattern so this can never drift from
the data it stands in for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from partner_scrape.directory.pipeline import run_directory
from partner_scrape.directory.sources.base import run_offering_source
from partner_scrape.directory.sources.offering_static_roster import (
    DEFAULT_ROSTER_PATH,
    OfferingStaticRosterSource,
)
from partner_scrape.registry.loader import load_active_sources

DIRECTORY_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "directory" / "registry"
)


class _NeverCalledFetcher:
    def get(self, url, headers=None):
        raise AssertionError("must never call the injected Fetcher")


def _real_source_config():
    sources = load_active_sources(DIRECTORY_REGISTRY_DIR)
    return next(s for s in sources if s.adapter_type == "offering_static_roster")


def _real_offerings():
    return run_offering_source(_real_source_config(), OfferingStaticRosterSource(), _NeverCalledFetcher())


def _real_volunteer_offerings():
    return {o.offering_id: o for o in _real_offerings() if o.offering_type == "volunteer"}


class TestSixVolunteerOrgsPresent:
    def test_all_six_named_volunteer_orgs_are_present(self):
        by_id = _real_volunteer_offerings()

        assert set(by_id) == {
            "fleet-science-center-volunteer",
            "sdzwa-volunteer",
            "birch-aquarium-volunteer",
            "sdnhm-volunteer",
            "ilacsd-volunteer",
            "san-diego-river-park-foundation-volunteer",
        }


class TestAgeMinimumsMatchIssue14Verbatim:
    """AC: Fleet and SDZWA's age_minimum is 18; Birch's is 16 --
    matching issue 14's own 2026-08-30 research verbatim."""

    def test_fleet_age_minimum_is_eighteen(self):
        assert _real_volunteer_offerings()["fleet-science-center-volunteer"].age_minimum == 18

    def test_sdzwa_age_minimum_is_eighteen(self):
        assert _real_volunteer_offerings()["sdzwa-volunteer"].age_minimum == 18

    def test_birch_age_minimum_is_sixteen(self):
        assert _real_volunteer_offerings()["birch-aquarium-volunteer"].age_minimum == 16


class TestAgeMinimumsAreHonestlyResearchedNotGuessed:
    """AC: the Nat's, ILACSD's, and San Diego River Park Foundation's
    age_minimum reflects each org's own actually-published policy (a
    real value or None if the org states none) -- never a copied
    default. As live-verified 2026-09-02, none of the three publishes a
    numeric minimum, so age_minimum is None for all three -- never a
    guessed 18 copied from the other three rows."""

    @pytest.mark.parametrize(
        "offering_id",
        ["sdnhm-volunteer", "ilacsd-volunteer", "san-diego-river-park-foundation-volunteer"],
    )
    def test_age_minimum_is_none_not_a_guessed_default(self, offering_id):
        assert _real_volunteer_offerings()[offering_id].age_minimum is None


class TestLinkUrlsAreLiveVerifiedAndWellFormed:
    def test_every_volunteer_rows_link_url_is_non_empty_and_well_formed(self):
        for offering in _real_volunteer_offerings().values():
            assert offering.link_url, offering.offering_id
            assert offering.link_url.startswith(("http://", "https://")), offering.offering_id


class TestDescriptionsAreNonEmpty:
    def test_every_volunteer_rows_description_is_non_empty(self):
        for offering in _real_volunteer_offerings().values():
            assert offering.description, offering.offering_id


class TestRelatedPartnerIdJoinIntegrity:
    """AC: every row's related_partner_id is hand-checked against the
    partner roster's own id field where a confident match exists --
    left None otherwise, never guessed. Spot-checks the six hand-copied
    ids directly, then re-verifies every non-None reference in the real
    roster resolves through directory.pipeline's own join-integrity
    guard (the same mechanism a real `directory` CLI run exercises)."""

    def test_hand_copied_partner_ids_match_the_expected_org(self):
        by_id = _real_volunteer_offerings()

        assert by_id["fleet-science-center-volunteer"].related_partner_id == 121
        assert by_id["sdzwa-volunteer"].related_partner_id == 241
        assert by_id["birch-aquarium-volunteer"].related_partner_id == 238
        assert by_id["sdnhm-volunteer"].related_partner_id == 24
        assert by_id["ilacsd-volunteer"].related_partner_id == 361
        assert by_id["san-diego-river-park-foundation-volunteer"].related_partner_id == 323

    def test_every_related_partner_id_resolves_via_run_directorys_join_guard(self, tmp_path):
        text = DEFAULT_ROSTER_PATH.read_text(encoding="utf-8")
        ids = sorted({int(m) for m in re.findall(r"related_partner_id\s*=\s*(\d+)", text)})
        assert ids, "expected at least one related_partner_id in the real roster"

        site_dir = tmp_path / "fixture-site"
        data_dir = site_dir / "src" / "data"
        data_dir.mkdir(parents=True)
        partners = [{"id": pid, "name": f"Fixture Partner {pid}"} for pid in ids]
        (data_dir / "partners.json").write_text(json.dumps(partners), encoding="utf-8")

        # dry_run=True: computes the would-be-written payload without
        # touching disk -- no get_own_data_dir() pinning needed, since
        # export_directory() is never reached. source= isolates the
        # offering source alone so Places'/Clubs' own related_partner_id
        # references (which this fixture partners.json does not carry)
        # never enter this check.
        payload = run_directory(
            registry_dir=DIRECTORY_REGISTRY_DIR,
            source="offering_static_roster",
            site_dir=site_dir,
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
        )

        assert len(payload["offerings"]) == 7
