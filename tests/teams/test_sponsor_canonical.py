"""Tests for partner_scrape.teams.sponsor_canonical: sprint 013 ticket
005's reopening -- corpus-wide sponsor-name canonicalization, on top of
(never inside) ``normalize.partners.normalize_org_name``.

Every merge pair and drop case below is a **real string pulled directly
from the live-regenerated ``site/src/data/teams.json``** that motivated
this ticket's reopening -- not a hypothetical. See
``sponsor_canonical.py``'s own module docstring for the full story of
each defect class.
"""

from __future__ import annotations

import ast
from pathlib import Path

import partner_scrape.teams.sponsor_canonical as sponsor_canonical_module
from partner_scrape.teams.model import Team
from partner_scrape.teams.sponsor_canonical import (
    canonical_key,
    canonicalize_sponsors,
    expand_local,
    is_slug_like,
    reconstruct_slug,
)


def _team(**overrides) -> Team:
    defaults: dict = dict(
        team_id="ftc-1",
        league="FTC",
        program="FIRST Tech Challenge",
        number=1,
        name="Test Team",
        sources=["ftcscout"],
    )
    defaults.update(overrides)
    return Team(**defaults)


class TestCanonicalKey:
    """canonical_key = normalize_org_name + a trailing corporate-suffix
    strip -- the shared match key every merge decision in this module
    (and, via re-use in sponsor_extract.py, the pre-existing per-team
    merge too) compares."""

    def test_case_only_variants_share_a_key(self):
        assert canonical_key("QualComm") == canonical_key("Qualcomm")
        assert canonical_key("goBILDA") == canonical_key("GoBilda")

    def test_corporate_suffix_is_stripped_from_the_key(self):
        assert canonical_key("Qualcomm Inc") == canonical_key("Qualcomm")
        assert canonical_key("Qualcomm, Inc.") == canonical_key("Qualcomm")
        assert canonical_key("Nordson Corporation") == canonical_key("Nordson")
        assert canonical_key("Stella Maris LLC") == canonical_key("Stella Maris")
        assert canonical_key("The Best Dog for Me, LLC") == canonical_key("Best Dog for Me")

    def test_a_suffix_word_used_mid_name_is_not_stripped(self):
        # "Cohen, Schwarz & Co." -- "Co." is part of the real legal name
        # here, not a bare trailing suffix on an otherwise-different
        # base name; canonical_key still strips the trailing "co" token
        # (harmless -- it only matters if this collides with an
        # unrelated same-keyed name, which it does not in this corpus),
        # but the point of this test is that mid-name text survives.
        assert "schwarz" in canonical_key("Cohen, Schwarz & Co.")

    def test_normalize_org_name_itself_is_not_modified(self):
        # Scope boundary: canonical_key must be a strict addition on
        # top of normalize_org_name, never a replacement that changes
        # its own standalone behavior.
        from partner_scrape.normalize.partners import normalize_org_name

        assert normalize_org_name("Qualcomm Inc.") == "qualcomm inc"


class TestTrademarkArtifactCorruption:
    """Root cause (sponsor_canonical.py's own module docstring, verified
    directly against tests/fixtures/teams/ftcscout_search.json): the
    "&R" suffix is not a decode bug in this project's own code -- it
    appears byte-for-byte in FTCScout's raw API response, and
    sources/ftcscout.py does nothing to a sponsor string beyond
    ``list(sponsors_raw)``. There is no html.unescape or any other
    decode step anywhere between the API response and Team.sponsors to
    fix. expand_local()'s trailing-"&R"-strip is a narrow, evidence-
    based defensive cleanup against this exact observed shape."""

    def test_real_ftcscout_corruption_examples_are_stripped(self):
        assert expand_local("Solar Turbines, Inc&R") == ["Solar Turbines, Inc"]
        assert expand_local("Francis Parker School&R") == ["Francis Parker School"]
        assert expand_local("Caterpillar&R") == ["Caterpillar"]

    def test_a_genuine_ampersand_abbreviation_is_untouched(self):
        # "R&D" -- the "&" is mid-string, not a trailing "&R" artifact.
        assert expand_local("R&D Robotics Education") == ["R&D Robotics Education"]

    def test_genuine_spaced_ampersand_company_names_are_untouched(self):
        for name in [
            "William A. Steen & Associates",
            "Delta Fire & Safety",
            "Cohen, Schwarz & Co.",
            "Ken & Jean Dugas",
            "Southwind Healthcare & Rehabilitation",
        ]:
            assert expand_local(name) == [name]


class TestJoinedNameCorruption:
    """The one real compound-corruption instance found: two unrelated
    sponsor names joined by a bare, unspaced "&" (FTCScout's raw data,
    team 14338) -- split into two names rather than published as one
    mangled compound string or dropped outright (both real company/
    school names are informative and worth keeping)."""

    def test_the_real_general_atomics_classical_academy_compound_splits_in_two(self):
        raw = "General Atomics Aeronautical Inc.&Classical Academy High School"
        assert expand_local(raw) == [
            "General Atomics Aeronautical Inc.",
            "Classical Academy High School",
        ]

    def test_a_period_immediately_before_the_ampersand_is_required(self):
        # No "." directly before "&" -- e.g. a genuine "X & Y" spaced
        # name, or "R&D" -- never splits.
        assert expand_local("R&D Robotics Education") == ["R&D Robotics Education"]
        assert expand_local("William A. Steen & Associates") == ["William A. Steen & Associates"]


class TestTrailingBoilerplateWord:
    """A common ``<img alt="X logo">``-style artifact, observed
    repeatedly in one team's own scraped footer -- stripped from
    already-legible (whitespace-separated) candidates."""

    def test_real_logo_suffixed_examples_are_cleaned(self):
        assert expand_local("California Protons logo") == ["California Protons"]
        assert expand_local("PCH Litho logo") == ["PCH Litho"]
        assert expand_local("Pluribus Digital logo") == ["Pluribus Digital"]
        assert expand_local("General Atomics Sciences Education Foundation logo") == [
            "General Atomics Sciences Education Foundation"
        ]

    def test_a_name_with_no_trailing_boilerplate_word_is_unchanged(self):
        assert expand_local("Bourns, Inc.") == ["Bourns, Inc."]


class TestIsSlugLike:
    def test_hostnames_and_hyphen_underscore_slugs_are_slug_like(self):
        assert is_slug_like("nordson.com") is True
        assert is_slug_like("Nordson-Corporation-Logo-web") is True
        assert is_slug_like("1280px-Thermo_Fisher_Scientific_logo") is True
        assert is_slug_like("millipore-sigma") is True

    def test_ordinary_display_text_is_not_slug_like(self):
        assert is_slug_like("Nordson") is False
        assert is_slug_like("Solar Turbines") is False
        assert is_slug_like("General Atomics Sciences Education Foundation") is False

    def test_a_single_plain_word_is_not_slug_like(self):
        # No internal "-"/"_" and not a bare hostname -- e.g. "Qualcomm".
        assert is_slug_like("Qualcomm") is False


class TestReconstructSlug:
    """Corpus-wide hostname/filename recovery: matched against a
    reference of already-clean names observed elsewhere in the same
    run. Every case here is a real raw string from the live-regenerated
    teams.json."""

    def _reference(self, *clean_names: str):
        token_reference: dict[tuple, str] = {}
        compact_reference: dict[str, str] = {}
        for name in clean_names:
            tokens = tuple(canonical_key(name).split())
            token_reference.setdefault(tokens, name)
            compact_reference.setdefault("".join(tokens), name)
        return token_reference, compact_reference

    def test_hostname_recovers_the_known_clean_name(self):
        token_ref, compact_ref = self._reference("Nordson")
        assert reconstruct_slug("nordson.com", token_ref, compact_ref) == "Nordson"

    def test_hostname_with_no_internal_word_boundary_still_recovers_via_compact_match(self):
        # "solarturbines.com" has no delimiter telling us where "Solar"
        # ends and "Turbines" begins -- only the reference (a separately
        # known-clean "Solar Turbines") can supply that word break.
        token_ref, compact_ref = self._reference("Solar Turbines")
        assert reconstruct_slug("solarturbines.com", token_ref, compact_ref) == "Solar Turbines"

    def test_saic_hostname_recovers_the_acronym_as_is(self):
        token_ref, compact_ref = self._reference("SAIC")
        assert reconstruct_slug("saic.com", token_ref, compact_ref) == "SAIC"

    def test_filename_slug_with_extra_trailing_junk_recovers_via_token_prefix(self):
        # "Viasat-cef-science-olympiad" -- only "Viasat" is a real
        # company name; "cef-science-olympiad" is an unrelated
        # descriptor with no deterministic boundary of its own, dropped.
        token_ref, compact_ref = self._reference("Viasat")
        assert reconstruct_slug("Viasat-cef-science-olympiad", token_ref, compact_ref) == "Viasat"

    def test_decorated_filename_blind_joins_when_no_reference_matches(self):
        # "1280px-Thermo_Fisher_Scientific_logo" -- no "Thermo Fisher"
        # anywhere else in this corpus, but the leading size-prefix and
        # trailing "logo" are positive markers this is a genuinely
        # decorated filename, allowing the 3-token blind join.
        token_ref, compact_ref = self._reference()
        assert (
            reconstruct_slug("1280px-Thermo_Fisher_Scientific_logo", token_ref, compact_ref)
            == "Thermo Fisher Scientific"
        )

    def test_two_token_slug_blind_joins_even_with_no_boilerplate_marker(self):
        token_ref, compact_ref = self._reference()
        assert reconstruct_slug("millipore-sigma", token_ref, compact_ref) == "Millipore Sigma"

    def test_nordson_corporation_logo_web_recovers_via_reference_not_blind_join(self):
        token_ref, compact_ref = self._reference("Nordson")
        assert (
            reconstruct_slug("Nordson-Corporation-Logo-web", token_ref, compact_ref) == "Nordson"
        )

    def test_short_ambiguous_hostnames_with_no_reference_match_are_dropped(self):
        # Real examples with nothing recoverable anywhere else in the
        # live corpus: never publish a bare, still-fused hostname label.
        token_ref, compact_ref = self._reference("Gene Haas Foundation")
        for hostname in ["te.com", "haascnc.com", "fabworks.com", "hyperkelp.com"]:
            assert reconstruct_slug(hostname, token_ref, compact_ref) is None

    def test_a_four_token_slug_with_no_reference_match_is_dropped_not_blind_joined(self):
        # Without a "Viasat" reference to recover from, this must never
        # publish "Viasat Cef Science Olympiad" as if it were a real
        # company name.
        token_ref, compact_ref = self._reference()
        assert reconstruct_slug("Viasat-cef-science-olympiad", token_ref, compact_ref) is None

    def test_a_short_reference_key_never_matches_as_a_prefix(self):
        # Defense-in-depth: a short reference key (e.g. a hypothetical
        # 3-letter company) must never falsely prefix-match an unrelated
        # longer hostname label that merely starts with the same
        # letters.
        token_ref, compact_ref = self._reference("CAT")
        assert reconstruct_slug("caterpillarparts.com", token_ref, compact_ref) is None


class TestCanonicalizeSponsorsRealMergePairs:
    """End-to-end coverage of every merge pair the reopened ticket
    listed explicitly, each built from the real display strings/team
    IDs/provenance observed in the live-regenerated teams.json."""

    def test_qualcomm_variants_merge_across_different_teams(self):
        # Real proportions matter here: "Qualcomm" is by far the most
        # common spelling in the live corpus (~18 teams) against one
        # "QualComm" and one "Qualcomm Inc" -- reflected below with
        # three plain "Qualcomm" teams so the merge is decided by
        # frequency, not an artificial 1-vs-1-vs-1 tie-break.
        teams = [
            _team(team_id="ftc-19937", sponsors=["QualComm"], sponsor_provenance={"QualComm": "structured"}),
            _team(team_id="ftc-1622", sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "structured"}),
            _team(team_id="ftc-6565", sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "structured"}),
            _team(team_id="ftc-8742", sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "structured"}),
            _team(
                team_id="ftc-11288",
                sponsors=["Qualcomm Inc"],
                sponsor_provenance={"Qualcomm Inc": "structured"},
            ),
        ]
        canonicalize_sponsors(teams)
        displays = {t.team_id: t.sponsors for t in teams}
        assert displays == {
            "ftc-19937": ["Qualcomm"],
            "ftc-1622": ["Qualcomm"],
            "ftc-6565": ["Qualcomm"],
            "ftc-8742": ["Qualcomm"],
            "ftc-11288": ["Qualcomm"],
        }
        for team in teams:
            assert team.sponsor_provenance == {"Qualcomm": "structured"}

    def test_dod_stem_variants_merge_and_prefer_the_most_common_spelling(self):
        teams = [
            _team(team_id="ftc-a", sponsors=["DOD STEM"], sponsor_provenance={"DOD STEM": "structured"}),
            _team(team_id="ftc-b", sponsors=["DoD STEM"], sponsor_provenance={"DoD STEM": "structured"}),
            _team(team_id="ftc-c", sponsors=["DoD STEM"], sponsor_provenance={"DoD STEM": "structured"}),
            _team(team_id="ftc-d", sponsors=["DoD STEM"], sponsor_provenance={"DoD STEM": "structured"}),
            _team(team_id="ftc-e", sponsors=["Dod stem"], sponsor_provenance={"Dod stem": "structured"}),
        ]
        canonicalize_sponsors(teams)
        assert all(t.sponsors == ["DoD STEM"] for t in teams)

    def test_dodea_and_dod_stem_are_never_merged_together(self):
        # "DoD STEM" and "DoDEA" are different real DoD programs --
        # must never collapse despite sharing a "DoD" prefix.
        teams = [
            _team(team_id="ftc-a", sponsors=["DoD STEM"], sponsor_provenance={"DoD STEM": "structured"}),
            _team(team_id="ftc-b", sponsors=["DoDEA"], sponsor_provenance={"DoDEA": "structured"}),
        ]
        canonicalize_sponsors(teams)
        assert teams[0].sponsors == ["DoD STEM"]
        assert teams[1].sponsors == ["DoDEA"]

    def test_rev_robotics_case_variants_merge(self):
        teams = [
            _team(team_id="ftc-11212", sponsors=["REV Robotics"], sponsor_provenance={"REV Robotics": "structured"}),
            _team(team_id="ftc-19937", sponsors=["Rev Robotics"], sponsor_provenance={"Rev Robotics": "structured"}),
        ]
        canonicalize_sponsors(teams)
        assert teams[0].sponsors == teams[1].sponsors == ["REV Robotics"]

    def test_gobilda_case_variants_merge_preferring_structured(self):
        teams = [
            _team(team_id="ftc-12823", sponsors=["GoBilda"], sponsor_provenance={"GoBilda": "structured"}),
            _team(team_id="ftc-12499", sponsors=["goBILDA"], sponsor_provenance={"goBILDA": "scraped"}),
        ]
        canonicalize_sponsors(teams)
        assert teams[0].sponsors == teams[1].sponsors == ["GoBilda"]

    def test_nordson_hostname_and_filename_forms_merge_with_the_clean_name(self):
        teams = [
            _team(
                team_id="ftc-9049",
                sponsors=["Nordson-Corporation-Logo-web"],
                sponsor_provenance={"Nordson-Corporation-Logo-web": "scraped"},
            ),
            _team(team_id="frc-812", sponsors=["Nordson"], sponsor_provenance={"Nordson": "scraped"}),
            _team(
                team_id="frc-2102",
                sponsors=["nordson.com"],
                sponsor_provenance={"nordson.com": "scraped"},
            ),
        ]
        canonicalize_sponsors(teams)
        assert all(t.sponsors == ["Nordson"] for t in teams)

    def test_solar_turbines_forms_merge_preferring_the_suffix_free_display(self):
        teams = [
            _team(
                team_id="ftc-14195",
                sponsors=["Solar Turbines"],
                sponsor_provenance={"Solar Turbines": "structured"},
            ),
            _team(
                team_id="ftc-6565",
                sponsors=["Solar Turbines, Inc&R"],
                sponsor_provenance={"Solar Turbines, Inc&R": "structured"},
            ),
            _team(
                team_id="frc-2102",
                sponsors=["solarturbines.com"],
                sponsor_provenance={"solarturbines.com": "scraped"},
            ),
        ]
        canonicalize_sponsors(teams)
        assert all(t.sponsors == ["Solar Turbines"] for t in teams)

    def test_francis_parker_specificity_variants_merge(self):
        # "Francis Parker" (bare) and "Francis Parker School" are not
        # corporate-suffix variants of each other -- this is the
        # token-prefix clustering case, not a plain canonical_key match.
        teams = [
            _team(team_id="ftc-25993", sponsors=["Francis Parker"], sponsor_provenance={"Francis Parker": "structured"}),
            _team(
                team_id="ftc-6565",
                sponsors=["Francis Parker School"],
                sponsor_provenance={"Francis Parker School": "structured"},
            ),
            _team(
                team_id="ftc-10092",
                sponsors=["Francis Parker School&R"],
                sponsor_provenance={"Francis Parker School&R": "structured"},
            ),
        ]
        canonicalize_sponsors(teams)
        assert all(t.sponsors == ["Francis Parker School"] for t in teams)

    def test_general_atomics_compound_and_logo_variants_are_cleaned_but_not_force_merged(self):
        # Deliberately NOT collapsed into one company: "General Atomic",
        # "General Atomics Aeronautical" (a subsidiary), and "General
        # Atomics Sciences Education Foundation" (a nonprofit arm) are
        # legally distinct entities with no deterministic string
        # transformation connecting them -- see sponsor_canonical.py's
        # own module docstring, "Deliberately not attempted". Each
        # becomes clean and readable; none stays mangled.
        teams = [
            _team(team_id="ftc-11212", sponsors=["General Atomic"], sponsor_provenance={"General Atomic": "structured"}),
            _team(
                team_id="frc-2102",
                sponsors=["General Atomics Sciences Education Foundation logo"],
                sponsor_provenance={"General Atomics Sciences Education Foundation logo": "scraped"},
            ),
            _team(
                team_id="ftc-14338",
                sponsors=["General Atomics Aeronautical Inc.&Classical Academy High School"],
                sponsor_provenance={
                    "General Atomics Aeronautical Inc.&Classical Academy High School": "structured"
                },
            ),
        ]
        canonicalize_sponsors(teams)
        assert teams[0].sponsors == ["General Atomic"]
        assert teams[1].sponsors == ["General Atomics Sciences Education Foundation"]
        assert teams[2].sponsors == [
            "General Atomics Aeronautical Inc.",
            "Classical Academy High School",
        ]

    def test_thermo_fisher_and_millipore_sigma_filenames_recover_clean_names(self):
        team = _team(
            team_id="ftc-9049",
            sponsors=["1280px-Thermo_Fisher_Scientific_logo", "millipore-sigma"],
            sponsor_provenance={
                "1280px-Thermo_Fisher_Scientific_logo": "scraped",
                "millipore-sigma": "scraped",
            },
        )
        canonicalize_sponsors([team])
        assert team.sponsors == ["Thermo Fisher Scientific", "Millipore Sigma"]

    def test_viasat_filename_recovers_the_clean_name_from_a_different_team(self):
        teams = [
            _team(team_id="ftc-11212", sponsors=["Viasat"], sponsor_provenance={"Viasat": "structured"}),
            _team(
                team_id="ftc-9049",
                sponsors=["Viasat-cef-science-olympiad"],
                sponsor_provenance={"Viasat-cef-science-olympiad": "scraped"},
            ),
        ]
        canonicalize_sponsors(teams)
        assert teams[0].sponsors == ["Viasat"]
        assert teams[1].sponsors == ["Viasat"]

    def test_saic_hostname_recovers_the_clean_acronym_from_a_different_team(self):
        teams = [
            _team(team_id="ftc-6016", sponsors=["SAIC"], sponsor_provenance={"SAIC": "structured"}),
            _team(team_id="frc-2102", sponsors=["saic.com"], sponsor_provenance={"saic.com": "scraped"}),
        ]
        canonicalize_sponsors(teams)
        assert teams[0].sponsors == teams[1].sponsors == ["SAIC"]

    def test_ambiguous_hostnames_with_nothing_to_recover_from_are_dropped(self):
        team = _team(
            team_id="frc-2102",
            sponsors=["te.com", "haascnc.com", "fabworks.com", "hyperkelp.com"],
            sponsor_provenance={
                "te.com": "scraped",
                "haascnc.com": "scraped",
                "fabworks.com": "scraped",
                "hyperkelp.com": "scraped",
            },
        )
        canonicalize_sponsors([team])
        assert team.sponsors == []
        assert team.sponsor_provenance == {}


class TestCanonicalizeSponsorsMechanics:
    def test_a_teams_own_provenance_perspective_is_never_altered_by_display_rewriting(self):
        teams = [
            _team(team_id="ftc-a", sponsors=["QualComm"], sponsor_provenance={"QualComm": "structured"}),
            _team(team_id="ftc-b", sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "scraped"}),
            _team(team_id="ftc-c", sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "structured"}),
            _team(team_id="ftc-d", sponsors=["Qualcomm"], sponsor_provenance={"Qualcomm": "structured"}),
        ]
        canonicalize_sponsors(teams)
        # All four now display "Qualcomm" (the mode across the corpus --
        # 3 of 4 raw spellings already agree), but each team's OWN
        # provenance claim for its own entry is untouched.
        assert teams[0].sponsor_provenance == {"Qualcomm": "structured"}
        assert teams[1].sponsor_provenance == {"Qualcomm": "scraped"}
        assert teams[2].sponsor_provenance == {"Qualcomm": "structured"}
        assert teams[3].sponsor_provenance == {"Qualcomm": "structured"}

    def test_an_upstream_within_team_duplicate_is_deduplicated_as_a_side_effect(self):
        # Real upstream FTCScout data quality issue found while
        # investigating this ticket (team 9261): the same sponsor name
        # appears twice in one team's own raw sponsors list.
        team = _team(
            sponsors=["Carlsbad Educational Foundation", "Carlsbad Educational Foundation"],
            sponsor_provenance={"Carlsbad Educational Foundation": "structured"},
        )
        canonicalize_sponsors([team])
        assert team.sponsors == ["Carlsbad Educational Foundation"]

    def test_a_team_with_no_sponsors_is_left_alone(self):
        team = _team()
        canonicalize_sponsors([team])
        assert team.sponsors == []
        assert team.sponsor_provenance == {}

    def test_unrelated_short_generic_words_are_never_prefix_merged(self):
        # "Boys"/"Family"/"Community" are real (truncated-upstream, out
        # of this ticket's scope to repair) FTCScout sponsor strings --
        # must never become a prefix-cluster root that swallows an
        # unrelated longer name.
        teams = [
            _team(team_id="ftc-a", sponsors=["Boys"], sponsor_provenance={"Boys": "structured"}),
            _team(
                team_id="ftc-b",
                sponsors=["Boys State Program"],
                sponsor_provenance={"Boys State Program": "structured"},
            ),
        ]
        canonicalize_sponsors(teams)
        assert teams[0].sponsors == ["Boys"]
        assert teams[1].sponsors == ["Boys State Program"]


class TestNoForbiddenImports:
    def test_module_imports_nothing_from_enrich_adapters_or_pipeline_run(self):
        # Matches sponsor_extract.py's/sponsor_llm.py's/sponsor_cache.py's/
        # sponsor_candidates.py's own forbidden-import-scan precedent.
        path = Path(sponsor_canonical_module.__file__)
        tree = ast.parse(path.read_text(), filename=str(path))
        forbidden_prefixes = (
            "partner_scrape.enrich",
            "partner_scrape.adapters",
            "partner_scrape.pipeline",
        )
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        offenders.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(forbidden_prefixes):
                    offenders.append(node.module)
        assert offenders == []
