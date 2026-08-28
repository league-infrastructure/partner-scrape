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
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.export.writer import SITE_SCHEMA_FIELDS

PAGE_PATH = (
    Path(__file__).resolve().parent.parent
    / "site"
    / "src"
    / "pages"
    / "data-access.astro"
)


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
