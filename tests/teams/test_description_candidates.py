"""Tests for partner_scrape.teams.description_candidates: deterministic,
offline description-content gathering (sprint 021 ticket 002).

**Fixture provenance.** Two of the four fixtures below are *not* new
captures -- they reuse, unmodified, two of
``tests/teams/test_sponsor_candidates.py``'s own real, live-captured
pages (that module's own docstring records provenance: fetched directly
2026-08-30 from teams whose website this project's own research already
confirmed):

- ``sponsor_page_teamspyder_partners.html`` -- teamspyder.org's real
  site. Its ``<head>`` carries no ``<meta name="description">`` tag (the
  sponsor-fixture curation pass strips ``<meta>`` outright, but a check
  of the raw file confirms none existed to strip), yet it has a real
  ``<title>Team Spyder 1622</title>``, a real ``<h3>Who Is Team
  Spyder?</h3>`` heading, and substantial real prose ("Team Spyder is
  the robotics team that represents Poway High in FRC or FIRST Robotics
  Competition ..."). This is the ticket's "no meta description but
  title/headings/body present" fixture.
- ``sponsor_page_ftc3650_thankyou.html`` -- ftc3650.org's real site.
  Its footer carries a real, unmodified contact paragraph, ``<p
  class="small">Email: <a href="mailto:limited_liability@ljcds.org">
  limited_liability@ljcds.org</a></p>`` -- a genuine email address in
  real body prose, not a synthesized stand-in. This is the ticket's
  email-in-prose fixture.

Reusing these two real fixtures here, unmodified, is a stronger realism
guarantee than a fresh, purpose-built copy would be -- the sprint 011
ticket-011-003 lesson already on record in this codebase (a
hand-authored fixture silently passed every unit test while the real
pipeline had a real defect).

**``description_page_meta_description.html`` is new to this ticket, and
is a representative reconstruction, not a live capture** -- documented
here rather than left implicit, per this ticket's own fixture-quality
bar. Every team site this ticket's author could check turned out to
carry no ``<meta name="description">`` tag at all: the five real domains
``test_sponsor_candidates.py``'s own fixtures were captured from
(gearup12499.com, teamspyder.org, ftc3650.org, carlsbaded.org,
seg-fault.org), plus two more drawn from
``teams/data/discovered-websites.toml`` (ftc14496robot.wixsite.com,
robogenesis.org) -- itself a genuine, useful finding (small team sites
overwhelmingly skip the tag), but it leaves no real captured example
anywhere in this project's corpus to reuse verbatim. This session's own
tooling could not close that gap either: direct network access
(``curl``) is blocked by this sandbox's policy, and the ``WebFetch``
tool's HTML-to-markdown conversion drops ``<head>``/``<meta>`` content
entirely (confirmed against a page known to have no ``<title>`` surface
in its markdown either), so even a page that *does* carry the tag could
not be verified through it. This fixture is therefore modeled on Wix's
real, well-documented generated-page shape (``data-testid``/``data-hook``
attributes, a ``<meta name="generator" content="Wix.com Website
Builder">`` tag) -- not an arbitrary invention, since two of this
project's own discovered team sites (``ftc14496robot.wixsite.com``,
``7159roboravens.wixsite.com``) are literally Wix-hosted -- per this
ticket's own stated fallback for when a live capture isn't feasible
("closely approximate real markup patterns you've seen in this
codebase's other test fixtures for team sites").

``description_page_pure_js_shell.html`` is hand-authored, matching
``test_sponsor_candidates.py``'s own precedent (``TestMalformedHtml``)
for a fixed structural property rather than any one real page's shape --
a client-only SPA mount point with no server-rendered text at all is a
structural case (the ticket's own "pure-JS shell" framing), not a
site-specific one.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

import partner_scrape.teams.description_candidates as description_candidates_module
from partner_scrape.teams.description_candidates import (
    MAX_CONTENT_CHARS,
    gather_description_content,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"

#: The same loose-but-sufficient email pattern
#: ``tests/teams/test_export.py`` uses for its own whole-payload privacy
#: regression -- reused here (not imported -- test modules stay
#: independent of one another) so this test checks the gathered content
#: against the same shape of string the export-layer backstop checks.
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestMetaDescriptionPresent:
    def test_meta_description_is_included_in_gathered_content(self):
        html = _fixture("description_page_meta_description.html")
        content = gather_description_content(html, "https://ftc14496robot.wixsite.com/roboctopi")

        assert (
            "Roboctopi is FTC Team 14496, a FIRST Tech Challenge robotics team "
            "based in San Diego, California" in content
        )

    def test_title_and_headings_still_present_alongside_meta_description(self):
        # SUC-022's own Acceptance Criteria wording is "returns content
        # that includes" the meta description "when present" -- not
        # "returns only" it. A page carrying all three signals should
        # surface all three, not have the meta description crowd out
        # the rest.
        html = _fixture("description_page_meta_description.html")
        content = gather_description_content(html, "https://ftc14496robot.wixsite.com/roboctopi")

        assert "Roboctopi" in content
        assert "About Our Team" in content
        assert "Our Mission" in content


class TestNoMetaDescriptionTitleAndHeadingsFallback:
    def test_real_page_with_no_meta_description_returns_title_heading_and_body_text(self):
        html = _fixture("sponsor_page_teamspyder_partners.html")
        # Sanity: confirm the real page actually carries no meta
        # description tag (not a stand-in for that absence) before
        # trusting what the fallback path recovers.
        assert "meta name=\"description\"" not in html

        content = gather_description_content(html, "https://www.teamspyder.org/")

        assert content != ""
        assert "Team Spyder 1622" in content  # <title>
        assert "Who Is Team Spyder?" in content  # <h3>
        assert "Poway High" in content  # real body prose
        assert len(content) <= MAX_CONTENT_CHARS

    def test_real_heavy_markup_page_picks_first_of_two_title_tags(self):
        # sponsor_page_gearup12499_heading.html's real <head> carries
        # *two* <title> tags ("12499 Gear Up" and "Home") -- a real
        # captured shape, not a contrived edge case. The first should
        # win, matching a real browser's own resolution of the
        # duplicate, and the result must still respect the cap despite
        # this being the largest fixture in the corpus.
        html = _fixture("sponsor_page_gearup12499_heading.html")
        content = gather_description_content(html, "https://www.gearup12499.com/")

        assert "12499 Gear Up" in content
        assert content != ""
        assert len(content) <= MAX_CONTENT_CHARS


class TestEmailStrippedFromBodyProse:
    def test_real_email_in_footer_prose_is_stripped(self):
        html = _fixture("sponsor_page_ftc3650_thankyou.html")
        # Sanity: confirm the real page actually carries this address
        # in body prose (not a stand-in for it) before trusting that
        # gathering strips it.
        assert "limited_liability@ljcds.org" in html

        content = gather_description_content(html, "https://www.ftc3650.org/")

        assert "limited_liability@ljcds.org" not in content
        assert not _EMAIL_PATTERN.search(content)
        # The rest of the page's real content should still be present --
        # stripping the address must not have emptied the whole result.
        assert "Limited Liability FTC 3650" in content

    def test_synthetic_email_in_a_single_paragraph_is_stripped(self):
        # Synthetic/hand-authored: exercises the regex's own boundary
        # behavior (an email mid-sentence) directly, the same category
        # of "fine to hand-author" test_sponsor_candidates.py's own
        # TestDenylist docstring grants for a fixed, deterministic
        # check -- the real-page case above is the ticket's dedicated,
        # non-incidental coverage this test only supplements.
        html = (
            "<html><head><title>Contact</title></head><body>"
            "<h1>Contact Us</h1>"
            "<p>Contact us at team1234@school.org for more info.</p>"
            "</body></html>"
        )
        content = gather_description_content(html, "https://example.org/")

        assert "team1234@school.org" not in content
        assert not _EMAIL_PATTERN.search(content)
        assert "Contact us at" in content
        assert "for more info" in content


class TestNoExtractableContent:
    def test_pure_js_shell_with_no_server_rendered_text_returns_empty(self):
        html = _fixture("description_page_pure_js_shell.html")
        assert gather_description_content(html, "https://example.org/") == ""

    def test_synthetic_page_with_no_meta_title_or_body_tags_returns_empty(self):
        html = "<html><body><div><img src=\"logo.png\"></div></body></html>"
        assert gather_description_content(html, "https://example.org/") == ""


class TestMalformedHtml:
    def test_empty_string_returns_empty_and_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = gather_description_content("", "https://example.org/")
        assert result == ""
        assert "example.org" in caplog.text

    def test_whitespace_only_html_returns_empty_string(self):
        assert gather_description_content("   \n\t  ", "https://example.org/") == ""


class TestCharacterCap:
    def test_synthetic_page_over_the_cap_is_truncated_to_the_documented_size(self):
        # Synthetic/hand-authored: tests a fixed structural property
        # (the cap itself), not real page shape -- matching
        # test_sponsor_candidates.py's own TestDeduplicationAndCap
        # precedent for the same kind of test.
        assert MAX_CONTENT_CHARS == 2000
        paragraphs = "".join(f"<p>Paragraph number {i} about our robotics team. </p>" for i in range(200))
        html = f"<html><body>{paragraphs}</body></html>"

        content = gather_description_content(html, "https://example.org/")

        assert len(content) == MAX_CONTENT_CHARS

    def test_cap_never_leaves_a_truncated_email_fragment_behind(self):
        # Stripping happens before truncation (module docstring), so a
        # hard cut can never land mid-email and leave an unstrippable
        # partial address behind. Construct a page whose email sits
        # exactly at the truncation boundary and confirm no '@' survives
        # in the returned content.
        padding = "x" * (MAX_CONTENT_CHARS - 10)
        html = f"<html><body><p>{padding} contact coach@school.edu now</p></body></html>"

        content = gather_description_content(html, "https://example.org/")

        assert "@" not in content


class TestNoForbiddenImports:
    def test_module_imports_nothing_from_fetch_enrich_adapters_or_anthropic(self):
        # AST-level check, matching test_sponsor_candidates.py's own
        # forbidden-import-scan precedent -- a source-level guarantee,
        # not just "the module as currently written happens not to
        # import it."
        path = Path(description_candidates_module.__file__)
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
