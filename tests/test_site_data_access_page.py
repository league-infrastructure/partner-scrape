"""Schema-drift guard for `site/src/pages/data-access.astro` (sprint 010
ticket 001, issue 16).

`data-access.astro`'s event field reference is hand-authored, not
generated from `export.writer.SITE_SCHEMA_FIELDS` at build time (sprint
010 Design Rationale D3 -- the page is static documentation, not a data
viewer). That means the two can drift silently if `Opportunity` ever
gains, loses, or renames a field. This is the one guard sprint 010 adds:
it does not verify prose accuracy or the worked example's values, only
that every current field *name* still appears somewhere in the page's
source text -- exactly the failure mode (a renamed/added/removed field)
a hand-authored doc page is prone to.

Sprint 017 ticket 002 (issue 42) extends this file with the identical
guard for `teams.json`'s field set (`teams.export.TEAMS_SCHEMA_FIELDS`,
File 3 on the same page) plus lightweight substring checks that
`site/public/llms.txt` and `site/src/pages/for-agents.astro` mention
`teams.json` -- the same per-page, hand-authored-doc precedent this
file already establishes for `data-access.astro`, per issue 42's own
verification note ("content assertions if the existing test suite
covers those pages").
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.export.writer import SITE_SCHEMA_FIELDS
from partner_scrape.teams.export import TEAMS_SCHEMA_FIELDS

SITE_DIR = Path(__file__).resolve().parent.parent / "site"

PAGE_PATH = SITE_DIR / "src" / "pages" / "data-access.astro"
FOR_AGENTS_PAGE_PATH = SITE_DIR / "src" / "pages" / "for-agents.astro"
LLMS_TXT_PATH = SITE_DIR / "public" / "llms.txt"

#: The absolute, publicly-served `teams.json` URL -- matches `DATA_ORIGIN`
#: in `for-agents.astro` and the existing `partners.json` bullet's URL
#: convention (issue 42).
TEAMS_JSON_URL = "https://league-infrastructure.github.io/partner-scrape/data/teams.json"


def test_page_exists():
    assert PAGE_PATH.is_file(), f"expected {PAGE_PATH} to exist"


def test_every_site_schema_field_documented():
    source = PAGE_PATH.read_text(encoding="utf-8")
    missing = [name for name in SITE_SCHEMA_FIELDS if name not in source]
    assert not missing, (
        f"data-access.astro is missing these SITE_SCHEMA_FIELDS names: {missing} "
        "-- update the page's event field reference to match "
        "export.writer.SITE_SCHEMA_FIELDS."
    )


def test_at_least_one_field_present_sanity_check():
    # Guards against a vacuous pass if SITE_SCHEMA_FIELDS were ever empty.
    assert len(SITE_SCHEMA_FIELDS) > 0


# === Sprint 017 ticket 002 (issue 42): teams.json discovery surfaces ===


def test_every_teams_schema_field_documented():
    source = PAGE_PATH.read_text(encoding="utf-8")
    missing = [name for name in TEAMS_SCHEMA_FIELDS if name not in source]
    assert not missing, (
        f"data-access.astro is missing these TEAMS_SCHEMA_FIELDS names: {missing} "
        "-- update the page's teams.json field reference to match "
        "partner_scrape.teams.export.TEAMS_SCHEMA_FIELDS."
    )


def test_at_least_one_teams_field_present_sanity_check():
    # Guards against a vacuous pass if TEAMS_SCHEMA_FIELDS were ever empty.
    assert len(TEAMS_SCHEMA_FIELDS) > 0


def test_data_access_page_documents_teams_json_envelope():
    source = PAGE_PATH.read_text(encoding="utf-8")
    for envelope_field in (
        "meta.generated",
        "meta.total",
        "meta.by_league",
        "meta.by_location_precision",
        "meta.out_of_region",
    ):
        assert envelope_field in source, (
            f"data-access.astro is missing envelope field {envelope_field!r} "
            "from its teams.json documentation."
        )


def test_llms_txt_mentions_teams_json_with_absolute_url():
    source = LLMS_TXT_PATH.read_text(encoding="utf-8")
    assert "teams.json" in source
    assert TEAMS_JSON_URL in source


def test_for_agents_page_mentions_teams_json():
    source = FOR_AGENTS_PAGE_PATH.read_text(encoding="utf-8")
    assert "teams.json" in source
