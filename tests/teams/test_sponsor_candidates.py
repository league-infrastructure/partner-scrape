"""Tests for partner_scrape.teams.sponsor_candidates: deterministic,
offline sponsor-name candidate gathering (sprint 013 ticket 003).

``tests/fixtures/teams/sponsor_page_*.html`` are **real, live-captured**
team pages -- fetched directly on 2026-08-30 from teams whose website
this project's own research already confirmed
(``teams/data/discovered-websites.toml``: "All 31 URLs re-fetched
independently ... all returned HTTP 200"), not hand-authored. Each raw
capture was mechanically trimmed with ``lxml`` (``<script>``/``<style>``/
``<meta>``/``<link>``/``<svg>``/``<iframe>``/comment nodes removed
outright) to keep the committed fixture a reasonable size; no surviving
tag, attribute, or text value was rewritten. This matches
``tests/fixtures/teams/tba_teams_page0.json``'s own precedent of a
real-but-curated fixture, not a hand-approximated one -- sprint 011
ticket 003's own lesson (a hand-authored fixture used a ``state_prov``
value the real TBA API never returns, silently undercounting 59 of 78
FRC teams past every unit test) is exactly the failure mode a
hand-authored HTML shape would risk repeating here, with a worse cost
(a fabricated sponsor, not just an undercount).

- ``sponsor_page_gearup12499_heading.html`` -- ftc-12499's real site, a
  plain ``<h2>Sponsors</h2>`` followed by a logo grid. Recovers
  "Qualcomm" among its real sponsors -- the same company already the
  single most common structured sponsor in this project's existing
  49-FTC-team corpus (18 of 49, per the ticket's own grounding note),
  now recovered live from an unrelated page by the same mechanism.
- ``sponsor_page_teamspyder_partners.html`` -- frc-1622/ftc-1622's real
  site, a plain ``<h2>Partners</h2>`` heading.
- ``sponsor_page_ftc3650_thankyou.html`` -- ftc-3650's real site. Its
  sponsor section's label is ``<p class="kicker">Sponsors</p>`` (no
  semantic heading tag at all -- see ``sponsor_candidates.py``'s module
  docstring for why heading detection had to broaden past ``<h1>``-
  ``<h6>`` to recover this real page), immediately followed by a
  sibling paragraph reading "Thank you to our current sponsors." --
  this is this ticket's real "Thank You to Our Sponsors"-style fixture.
- ``sponsor_page_carlsbaded_footer.html`` -- ftc-10809's real site (a
  team-specific page on its sponsoring foundation's shared site). A
  genuine ``<footer>`` logo wall ("Proudly Supported By:") with no
  sponsor/partner/thank-matching heading anywhere nearby -- the
  footer-independent-of-heading fixture. Its ``alt``/``title``
  attributes are messy, filename-derived strings on this particular
  page; the outbound link hostnames (``nordson.com``, ``viasat.com``,
  ...) are the real, reliably recovered signal here, which is itself
  the point: this module is deliberately generous across multiple
  signal types because real pages don't consistently populate all of
  them.
- ``sponsor_page_segfault_none.html`` -- ftc-31862's real site, a small
  page with no sponsor-shaped section at all.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import partner_scrape.teams.sponsor_candidates as sponsor_candidates_module
from partner_scrape.teams.sponsor_candidates import MAX_CANDIDATES, gather_sponsor_candidates

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestHeadingFollowedByBlock:
    def test_plain_sponsors_heading_recovers_real_grounding_sponsor(self):
        html = _fixture("sponsor_page_gearup12499_heading.html")
        candidates = gather_sponsor_candidates(html, "https://www.gearup12499.com/")

        # Qualcomm is the single most common structured sponsor in this
        # project's existing 49-FTC-team corpus (18 of 49) -- recovering
        # it live from a real, unrelated team's <h2>Sponsors</h2> grid
        # is the ticket's own grounding check ("Existing sponsor data
        # for grounding").
        assert "Qualcomm" in candidates
        assert "Apple" in candidates
        assert "qualcomm.com" in candidates

    def test_our_partners_heading_recovers_real_sponsor_name(self):
        html = _fixture("sponsor_page_teamspyder_partners.html")
        candidates = gather_sponsor_candidates(html, "https://www.teamspyder.org/")
        assert "Robot Planet Ecuador" in candidates

    def test_thank_you_to_our_sponsors_heading_recovers_real_sponsor_names(self):
        # This fixture's actual heading-like label is a non-semantic
        # <p class="kicker">Sponsors</p>, immediately followed by a
        # sibling paragraph reading "Thank you to our current
        # sponsors." -- both match /sponsor|partner|thank/i, proving
        # the ticket's "Thank You to Our Sponsors"-style phrasing is
        # recognized by the same regex as the plain "Sponsors"/
        # "Partners" cases above.
        html = _fixture("sponsor_page_ftc3650_thankyou.html")
        # Sanity: confirm the real page actually carries this phrasing
        # (not a stand-in for it) before trusting what gets recovered.
        assert "Thank you to our current sponsors." in html

        candidates = gather_sponsor_candidates(html, "https://www.ftc3650.org/")
        assert "LJCDS logo" in candidates
        assert "ljcds.org" in candidates
        assert "Sibe logo" in candidates
        assert "sibe.io" in candidates


class TestFooterLogoWall:
    def test_real_footer_logo_wall_recovers_outbound_sponsor_hostnames(self):
        html = _fixture("sponsor_page_carlsbaded_footer.html")
        candidates = gather_sponsor_candidates(html, "https://carlsbaded.org/crow-force/")

        assert "nordson.com" in candidates
        assert "viasat.com" in candidates
        assert "thermofisher.com" in candidates
        assert "sigmaaldrich.com" in candidates

    def test_footer_scanned_independently_of_any_heading(self):
        # This fixture's own footer heading, "Proudly Supported By:",
        # matches none of /sponsor|partner|thank/i -- so recovering its
        # sponsor names at all proves the footer scan does not depend
        # on a nearby heading match, per SUC-003's Main Flow step 2
        # ("Independently scans any <footer> element ... whether or not
        # a matching heading exists nearby").
        assert sponsor_candidates_module._SPONSOR_HEADING_RE.search("Proudly Supported By:") is None

        html = _fixture("sponsor_page_carlsbaded_footer.html")
        candidates = gather_sponsor_candidates(html, "https://carlsbaded.org/crow-force/")
        assert "nordson.com" in candidates


class TestNoSponsorSignal:
    def test_real_page_with_no_sponsor_section_returns_empty(self):
        html = _fixture("sponsor_page_segfault_none.html")
        assert gather_sponsor_candidates(html, "https://seg-fault.org/") == []

    def test_synthetic_page_with_neither_heading_nor_footer_returns_empty(self):
        html = "<html><body><h1>Welcome</h1><p>We build robots.</p></body></html>"
        assert gather_sponsor_candidates(html, "https://example.org/") == []


class TestDenylist:
    def test_page_whose_only_candidates_are_denylisted_returns_empty(self):
        # Synthetic/hand-authored: this exercises a fixed, deterministic
        # set-membership check against known non-sponsor categories
        # (CMS vendor, program/aggregator, social platform, nav
        # boilerplate), not an approximation of any one real page's
        # structure -- the same category of "fine to hand-author" the
        # ticket grants the malformed-HTML case below.
        html = """
        <html><body>
        <h2>Our Sponsors</h2>
        <div>
          <a href="https://www.wix.com">Wix</a>
          <a href="https://www.facebook.com/exampleteam">Facebook</a>
          <img alt="FIRST Inspires">
        </div>
        <footer>
          <a href="https://www.squarespace.com">Squarespace</a>
          <img alt="Donate">
        </footer>
        </body></html>
        """
        assert gather_sponsor_candidates(html, "https://exampleteam.org/") == []

    def test_own_hostname_is_never_a_candidate(self):
        html = """
        <html><body>
        <footer>
          <a href="https://www.exampleteam.org/about">About</a>
          <a href="https://sponsor.example.com">Real Sponsor Co</a>
        </footer>
        </body></html>
        """
        candidates = gather_sponsor_candidates(html, "https://www.exampleteam.org/")
        assert "exampleteam.org" not in candidates
        assert "Real Sponsor Co" in candidates


class TestMalformedHtml:
    def test_empty_string_returns_empty_list_and_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = gather_sponsor_candidates("", "https://example.org/")
        assert result == []
        assert "example.org" in caplog.text

    def test_whitespace_only_html_returns_empty_list(self):
        assert gather_sponsor_candidates("   \n\t  ", "https://example.org/") == []


class TestDeduplicationAndCap:
    def test_same_name_from_alt_and_link_text_is_not_duplicated(self):
        html = """
        <html><body>
        <h2>Sponsors</h2>
        <div>
          <a href="https://acme-robotics.example.com">
            <img alt="Acme Robotics">
          </a>
        </div>
        </body></html>
        """
        candidates = gather_sponsor_candidates(html, "https://example.org/")
        assert candidates.count("Acme Robotics") == 1

    def test_synthetic_page_over_the_cap_is_capped_at_the_documented_size(self):
        # Synthetic/hand-authored: tests a fixed structural property
        # (the cap itself), not real page shape -- see TestDenylist's
        # docstring note for why this is an accepted exception.
        assert MAX_CANDIDATES == 40
        imgs = "".join(f'<img alt="Sponsor {i}">' for i in range(60))
        html = f"<html><body><footer>{imgs}</footer></body></html>"
        candidates = gather_sponsor_candidates(html, "https://example.org/")
        assert len(candidates) == MAX_CANDIDATES


class TestNoForbiddenImports:
    def test_module_imports_nothing_from_fetch_enrich_adapters_or_anthropic(self):
        # AST-level check, matching tests/teams/test_sources_base.py's
        # own forbidden-import-scan precedent -- a source-level
        # guarantee, not just "the module as currently written happens
        # not to import it."
        path = Path(sponsor_candidates_module.__file__)
        tree = ast.parse(path.read_text(), filename=str(path))
        forbidden_prefixes = (
            "partner_scrape.fetch",
            "partner_scrape.enrich",
            "partner_scrape.adapters",
            "anthropic",
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
