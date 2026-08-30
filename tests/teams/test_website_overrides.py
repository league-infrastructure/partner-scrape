"""Tests for partner_scrape.teams.website_overrides: cleanup of the
existing 53 TBA-sourced `Team.website` values plus ingestion of the
sprint 013 discovered-website/social overlay.

Fixtures are derived from real data, never hand-authored -- matching
sprint.md's Test Strategy lesson from sprint 011 ticket 003 (a
hand-authored fixture using the wrong `state_prov` value silently
passed every unit test while the real pipeline dropped 59 of 78 FRC
teams). `tests/fixtures/teams/discovered_websites_sample.toml` is
copied verbatim from a subset of this sprint's own committed research
artifact, `clasi/sprints/013-team-website-surfacing-and-sponsor-
extraction/research/discovered-websites.json`; the malformed/junk
website values below are the 11 real values measured live against
`site/src/data/teams.json` at ticket-write time (sprint.md's
Description), not invented strings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape.teams.model import Team
from partner_scrape.teams.website_overrides import DEFAULT_DATA_DIR, apply_website_overrides

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"

#: The committed sample overlay, copied verbatim from a subset of
#: research/discovered-websites.json. Deliberately named differently
#: from the real production file (`discovered-websites.toml`) so it is
#: never confused with it; `apply_website_overrides()` always reads a
#: fixed filename from whatever `data_dir` it's given (matching
#: `teams/geo.py`'s `SchoolIndex(data_dir=...)` convention), so tests
#: copy this sample's content into a tmp_path under that fixed name via
#: the `overlay_dir` fixture below.
_SAMPLE_OVERLAY_PATH = FIXTURES_DIR / "discovered_websites_sample.toml"


@pytest.fixture
def overlay_dir(tmp_path: Path) -> Path:
    """A tmp_path directory containing a `discovered-websites.toml`
    file whose content is the committed sample fixture, copied
    verbatim under the filename `apply_website_overrides()` actually
    reads."""
    dest_dir = tmp_path / "overlay-data"
    dest_dir.mkdir()
    (dest_dir / "discovered-websites.toml").write_text(_SAMPLE_OVERLAY_PATH.read_text())
    return dest_dir

# The real malformed triple-slash values, measured live against
# site/src/data/teams.json (sprint.md's Description) -- 4 recoverable,
# 3 dead (dead-ness is not this module's concern; ticket 001's live
# fetch decides that. This module only proves the string repair is
# correct for all 7, generically).
_REAL_TRIPLE_SLASH = {
    "frc-2029": ("http:///www.neotechrobotics.org", "http://www.neotechrobotics.org"),
    "frc-2658": ("http:///www.team2658.org", "http://www.team2658.org"),
    "frc-3341": ("http:///westviewrobotics.com", "http://westviewrobotics.com"),
    "frc-3965": ("http:///TEAM3965.org", "http://TEAM3965.org"),
    "frc-5025": ("http:///team5025.com", "http://team5025.com"),
    "frc-5477": ("http:///www.nubotx.com", "http://www.nubotx.com"),
    "frc-6695": ("http:///www.alphaknights.net", "http://www.alphaknights.net"),
}

# The real firstinspires.org junk value, measured live -- shared by all
# 4 affected teams.
_REAL_FIRSTINSPIRES_URL = "http://www.firstinspires.org/"


def _team(team_id: str, website: str = "") -> Team:
    return Team(team_id=team_id, league=team_id.split("-")[0].upper(), website=website)


class TestFirstInspiresCleanup:
    @pytest.mark.parametrize(
        "team_id", ["frc-3486", "frc-4139", "frc-4919", "frc-5884"]
    )
    def test_firstinspires_junk_value_is_cleared(self, team_id, overlay_dir):
        team = _team(team_id, website=_REAL_FIRSTINSPIRES_URL)

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == ""

    def test_www_less_form_is_also_cleared(self, overlay_dir):
        team = _team("frc-9999", website="http://firstinspires.org/")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == ""

    def test_a_real_domain_merely_containing_the_substring_is_not_misfired_on(self, overlay_dir):
        # urlsplit-based host comparison, never a substring match --
        # this host is not firstinspires.org even though it contains
        # "firstinspires" as a substring.
        team = _team("frc-9998", website="http://notfirstinspires.org/team")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == "http://notfirstinspires.org/team"


class TestTripleSlashRepair:
    @pytest.mark.parametrize("team_id", list(_REAL_TRIPLE_SLASH))
    def test_real_malformed_value_is_repaired(self, team_id, overlay_dir):
        malformed, repaired = _REAL_TRIPLE_SLASH[team_id]
        team = _team(team_id, website=malformed)

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == repaired

    def test_https_variant_is_also_repaired(self, overlay_dir):
        team = _team("frc-9997", website="https:///example.org")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == "https://example.org"

    def test_a_well_formed_url_is_left_untouched(self, overlay_dir):
        team = _team("frc-9996", website="http://www.team2658.org")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == "http://www.team2658.org"


class TestOverlayAppliedOnlyWhenWebsiteEmpty:
    def test_empty_website_gets_the_overlay_value(self, overlay_dir):
        team = _team("ftc-1622", website="")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == "https://teamspyder.org"

    def test_existing_non_empty_website_is_never_overwritten_by_the_overlay(self, overlay_dir):
        team = _team("ftc-1622", website="http://team-owned-site.example.org")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == "http://team-owned-site.example.org"

    def test_a_post_cleanup_empty_website_still_gets_the_overlay_value(self, overlay_dir):
        # firstinspires cleanup empties the website first; the overlay
        # then fills it, in the same call.
        team = Team(team_id="ftc-1622", league="FTC", website=_REAL_FIRSTINSPIRES_URL)

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == "https://teamspyder.org"


class TestSocialIngestion:
    def test_social_only_team_gets_social_populated_website_unchanged(self, overlay_dir):
        team = _team("frc-6659", website="")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == ""
        assert team.social == [
            "https://www.instagram.com/ehs.robotics",
            "https://twitter.com/team6659",
            "https://www.facebook.com/ehs-robotics-1606671419628388",
        ]

    def test_website_entry_also_sets_social(self, overlay_dir):
        team = _team("ftc-1622")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.social == [
            "https://www.instagram.com/spyder1622",
            "https://www.youtube.com/@spyder1622",
            "https://twitter.com/team1622",
            "https://twitter.com/frc1622",
        ]

    def test_team_absent_from_overlay_stays_at_defaults(self, overlay_dir):
        team = _team("ftc-99999999")

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == ""
        assert team.social == []


class TestWebsiteStatusNeverTouched:
    """AC: `website_status` is left exactly at its dataclass default for
    every team this stage touches, `strong`- and `weak`-confidence
    overlay entries alike -- proven directly, not just by the absence
    of code that would set it."""

    def test_strong_confidence_entry_leaves_website_status_untouched(self, overlay_dir):
        team = _team("ftc-1622")
        assert team.website_status == ""

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website_status == ""

    @pytest.mark.parametrize("team_id", ["ftc-6226", "ftc-14968", "ftc-18755"])
    def test_weak_confidence_entries_land_as_unverified_never_confirmed(self, team_id, overlay_dir):
        # "Unverified" here means "this stage never marks it anything" --
        # ticket 001's live fetch is what actually assigns
        # website_status; this module must never pre-confirm it.
        team = _team(team_id)
        assert team.website_status == ""

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website_status == ""
        assert team.website != ""  # the overlay did fill website...
        # ...but never website_status: the field this stage owns never
        # implies confirmation by itself.


class TestHostPathUniquenessGuard:
    def test_two_team_ids_claiming_the_identical_host_and_path_raises(self, tmp_path):
        bad_toml = tmp_path / "discovered-websites.toml"
        bad_toml.write_text(
            '["ftc-1111"]\n'
            'website = "https://carlsbaded.org/robopuffs-2/"\n'
            "social = []\n"
            "\n"
            '["ftc-2222"]\n'
            'website = "https://carlsbaded.org/robopuffs-2/"\n'
            "social = []\n"
        )

        with pytest.raises(RuntimeError):
            apply_website_overrides([_team("ftc-1111")], data_dir=tmp_path)

    def test_the_real_carlsbaded_org_and_sites_google_com_cases_never_raise(self, overlay_dir):
        # ftc-9049 and ftc-10809 both live under carlsbaded.org, at
        # distinct paths -- must not raise, and both teams must keep
        # their own website (never collapsed/dropped).
        team_a = _team("ftc-9049")
        team_b = _team("ftc-10809")

        apply_website_overrides([team_a, team_b], data_dir=overlay_dir)

        assert team_a.website == "https://carlsbaded.org/robopuffs-2/"
        assert team_b.website == "https://carlsbaded.org/crow-force/"

    def test_real_committed_overlay_file_loads_with_no_collision(self):
        # The full, real 52-entry overlay this sprint ships must itself
        # pass the uniqueness guard -- including the real
        # sites.google.com host-sharing entries the research file's
        # caveats call out.
        apply_website_overrides([_team("ftc-1622")], data_dir=DEFAULT_DATA_DIR)


class TestMissingOrMalformedDataFile:
    def test_missing_data_file_raises_loudly(self, tmp_path):
        with pytest.raises(RuntimeError):
            apply_website_overrides([_team("ftc-1622")], data_dir=tmp_path)

    def test_malformed_toml_raises_loudly(self, tmp_path):
        bad_toml = tmp_path / "discovered-websites.toml"
        bad_toml.write_text("this is not [ valid toml")

        with pytest.raises(RuntimeError):
            apply_website_overrides([_team("ftc-1622")], data_dir=tmp_path)

    def test_malformed_entry_raises_loudly(self, tmp_path):
        bad_toml = tmp_path / "discovered-websites.toml"
        # `social` must be an array of strings, not a bare string --
        # str(non-list) still "succeeds" via str() coercion above the
        # list comprehension only if iterable; a table with `social`
        # as a table (not array/string) triggers the AttributeError
        # path in _load_overlay.
        bad_toml.write_text(
            '["ftc-1111"]\n'
            "social = 12345\n"
        )

        with pytest.raises(RuntimeError):
            apply_website_overrides([_team("ftc-1111")], data_dir=tmp_path)


class TestIdempotence:
    def test_calling_twice_produces_the_same_result(self, overlay_dir):
        team = Team(team_id="ftc-1622", league="FTC", website=_REAL_FIRSTINSPIRES_URL)

        apply_website_overrides([team], data_dir=overlay_dir)
        first_website, first_social = team.website, list(team.social)

        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == first_website
        assert team.social == first_social

    def test_triple_slash_repair_is_idempotent(self, overlay_dir):
        team = _team("frc-2658", website="http:///www.team2658.org")

        apply_website_overrides([team], data_dir=overlay_dir)
        apply_website_overrides([team], data_dir=overlay_dir)

        assert team.website == "http://www.team2658.org"


class TestMutatesAndReturnsSameList:
    def test_returns_the_same_list_object_it_was_given(self, overlay_dir):
        teams = [_team("ftc-1622")]

        result = apply_website_overrides(teams, data_dir=overlay_dir)

        assert result is teams
