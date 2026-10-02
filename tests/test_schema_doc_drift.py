"""Drift guard for ``docs/data-schema.md`` (sprint 038 ticket 010, issue 46).

The doc's per-file field lists are transcribed from the exporters' schema
constants. This module parses each list out of the doc and asserts it equals
its constant exactly and in order, so adding/removing/reordering a field
without updating the doc fails the suite (same style as the
``TEAMS_SCHEMA_FIELDS`` pin in ``tests/teams/test_export.py``).

Deliberately NOT pinned: the four classifier-prompt vocabularies
(``areas_of_interest``, ``age_grade_level``, ``cost_range``, ``time_of_day``)
-- they are unvalidated prompt guidance, not enums -- and all prose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from partner_scrape.directory.export import (
    CLUBS_SCHEMA_FIELDS,
    OFFERINGS_SCHEMA_FIELDS,
    PLACES_SCHEMA_FIELDS,
)
from partner_scrape.export.writer import SITE_SCHEMA_FIELDS
from partner_scrape.teams.export import TEAMS_SCHEMA_FIELDS

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "data-schema.md"

# (doc file name in the section heading, constant name, constant value)
_CASES = [
    ("opportunities.json", "SITE_SCHEMA_FIELDS", SITE_SCHEMA_FIELDS),
    ("teams.json", "TEAMS_SCHEMA_FIELDS", TEAMS_SCHEMA_FIELDS),
    ("places.json", "PLACES_SCHEMA_FIELDS", PLACES_SCHEMA_FIELDS),
    ("clubs.json", "CLUBS_SCHEMA_FIELDS", CLUBS_SCHEMA_FIELDS),
    ("offerings.json", "OFFERINGS_SCHEMA_FIELDS", OFFERINGS_SCHEMA_FIELDS),
]


def _doc_section(filename: str) -> tuple[int, list[str]]:
    """Return (stated field count, field names) from the ``## `file` — N fields``
    section: the first paragraph after the heading made only of backticked
    names."""
    text = DOC_PATH.read_text(encoding="utf-8")
    heading = re.search(
        rf"^## `{re.escape(filename)}` — (\d+) fields\s*$", text, re.MULTILINE
    )
    assert heading, f"docs/data-schema.md has no '## `{filename}` — N fields' heading"
    body = text[heading.end():].lstrip("\n")
    paragraph = body.split("\n\n", 1)[0]
    fields = re.findall(r"`([^`]+)`", paragraph)
    assert fields, f"no field list found under the `{filename}` heading"
    return int(heading.group(1)), fields


@pytest.mark.parametrize(("filename", "const_name", "const"), _CASES)
def test_doc_field_list_matches_constant(filename, const_name, const):
    stated_count, doc_fields = _doc_section(filename)
    expected = list(const)

    missing = [f for f in expected if f not in doc_fields]
    extra = [f for f in doc_fields if f not in expected]
    assert not missing and not extra, (
        f"docs/data-schema.md `{filename}` field list is out of sync with "
        f"{const_name}: missing from doc {missing}, extra in doc {extra}"
    )
    assert doc_fields == expected, (
        f"docs/data-schema.md `{filename}` lists the same fields as "
        f"{const_name} but in a different order: doc {doc_fields} vs "
        f"constant {expected}"
    )
    assert stated_count == len(expected), (
        f"docs/data-schema.md `{filename}` heading says {stated_count} fields "
        f"but {const_name} has {len(expected)}"
    )
