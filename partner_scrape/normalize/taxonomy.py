"""Controlled-vocabulary taxonomy derivation: text/value -> site-schema tags.

Ports `dev/export_site.py`'s `AREA_KEYWORDS` / `AGE_KEYWORDS` /
`map_cost` / `map_time_of_day` keyword-rule sets (ticket 006's
Description) into pure functions, reimplemented against the canonical
`Event` shape rather than that script's flat dict -- see
`derive_time_of_day`'s docstring for the one behavioral reimplementation
(reading `Event.start`'s real `datetime` instead of re-parsing a text
time string). No LLM this sprint (issue 04, sprint 2+); see sprint.md's
Architecture > Normalize & Dedup.

Every function here takes plain text/values, not an `Event` -- building
the input blob from an `Event`'s fields is run.py's job (via
:func:`build_taxonomy_text`), keeping this module a pure "text/value in,
tags out" layer that's trivial to unit test standalone.

Behavior matches `dev/export_site.py`'s rules on the same inputs
(spot-checked, not required to be byte-identical) per the ticket's
acceptance criteria.
"""

from __future__ import annotations

import re
from datetime import datetime

#: (pattern, label) rules for `areas_of_interest`, matched against a
#: blob of title+description+categories+tags text. Ported verbatim from
#: `dev/export_site.py`'s `AREA_KEYWORDS`.
AREA_KEYWORDS: list[tuple[str, str]] = [
    (
        r"\b(marine|ocean|aquarium|shark|whale|dolphin|turtle|fish|tide\s*pool|bird|wildlife|animal|insect|bug|reptile|zoo)\b",
        "Biology / LifeSciences",
    ),
    (
        r"\b(ecolog|environment|conservation|climate|recycl|compost|watershed|garden|farm|nature|habitat|creek|lagoon|river)\b",
        "Earth Science/Ecology",
    ),
    (
        r"\b(coding|code|program(?:ming)?|computer|robot|scratch|python|minecraft|cyber|video game)\b",
        "Coding/Computer Science/Cyber Security",
    ),
    (
        r"\b(engineer|maker|build|lego|3d print|circuit|invention|design challenge)\b",
        "Engineering",
    ),
    (
        r"\b(astronomy|planetarium|telescope|space|rocket|star|planet)\b",
        "Physical Science",
    ),
    (r"\b(math|algebra|geometry)\b", "Mathematics"),
    (r"\b(chemistry|chemical)\b", "Chemistry"),
    (r"\b(physics)\b", "Physics"),
]

#: (pattern, label) rules for `age_grade_level`. Ported verbatim from
#: `dev/export_site.py`'s `AGE_KEYWORDS`.
AGE_KEYWORDS: list[tuple[str, str]] = [
    (r"\b(famil(?:y|ies)|all ages)\b", "Family"),
    (r"\b(toddler|preschool|pre-k|ages? [0-5]\b)\b", "Pre-K"),
    (r"\b(teen|high school|grades? 9)\b", "Grades 9-12"),
    (r"\b(middle school|tween|grades? 6)\b", "Grades 6-8"),
    (r"\b(adult)\b", "Adult"),
]

#: Fallback area tag when no `AREA_KEYWORDS` rule matches -- matches
#: `dev/export_site.py`'s `tag_by_keywords(text, AREA_KEYWORDS) or
#: ["General Science"]` default in `build_opportunity`.
DEFAULT_AREA = "General Science"

#: `opportunity_type` classification rules, checked in order (first match
#: wins), mapping to the site's controlled vocabulary.
#:
#: These are matched against the event TITLE ONLY, deliberately. Matching
#: descriptions produced badly wrong results in practice: "Bird Walk at
#: Grant Park" and half the Anza-Borrego hikes classified as "Funding
#: Opportunities" (the word "grant"), and any event whose blurb said
#: "led by volunteers" became "Volunteering". A title is a curated,
#: high-signal label; a description is prose full of incidental words.
#:
#: Only high-confidence signals are encoded -- anything unmatched keeps
#: the `DEFAULT_OPPORTUNITY_TYPE` rather than being force-fit into a
#: bucket. There is deliberately NO "Funding Opportunities" rule: an
#: events calendar carries events, not grant announcements, and every
#: keyword for it (grant/scholarship/fellowship) is a false-positive
#: magnet. Bare "school" is likewise avoided -- it matches the
#: "preschool"/"school-age" AUDIENCE terms -- so phrases are used.
#:
#: Internships are handled separately by kind in normalize/run.py (they
#: force "Work-based Learning") and never reach this function.
OPPORTUNITY_TYPE_KEYWORDS: list[tuple[str, str]] = [
    (r"\b(clean[\s-]?up|litter|street sweep|beach sweep|restoration|"
     r"stewardship|volunteer day|service learning|trail work)\b", "Volunteering"),
    (r"\b(virtual|webinar|online|livestream|live stream)\b", "Online"),
    (r"\b(professional development|conference|symposium|colloquium|"
     r"educator workshop|teacher (?:training|workshop))\b",
     "Professional Development / Conferences"),
    (r"\b(career fair|job fair|college fair|career day|internship fair)\b",
     "Career Connections"),
    (r"\b(field trip|school program|in-school|school group|for schools|"
     r"school assembly)\b", "School Programs"),
]

#: Default `opportunity_type` when no `OPPORTUNITY_TYPE_KEYWORDS` rule
#: matches -- the site's most general bucket, and what every event was
#: blindly stamped before this classifier existed.
DEFAULT_OPPORTUNITY_TYPE = "Out-of-school Programs"

_COST_AMOUNT_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")


def tag_by_keywords(text: str, rules: list[tuple[str, str]]) -> list[str]:
    """Return every rule label whose pattern matches ``text`` (case-insensitive).

    Preserves ``rules`` order and never repeats a label -- ported
    verbatim from `dev/export_site.py`'s `tag_by_keywords`.
    """
    found: list[str] = []
    for pattern, label in rules:
        if re.search(pattern, text, re.I) and label not in found:
            found.append(label)
    return found


def derive_areas_of_interest(text: str) -> list[str]:
    """Derive `areas_of_interest` tags from ``text``.

    Falls back to ``["General Science"]`` when nothing matches, matching
    `dev/export_site.py`'s `build_opportunity` default.
    """
    return tag_by_keywords(text, AREA_KEYWORDS) or [DEFAULT_AREA]


def classify_opportunity_type(title: str) -> str:
    """Classify an event's `opportunity_type` from its TITLE into the
    site's controlled vocabulary via `OPPORTUNITY_TYPE_KEYWORDS`.

    Title only, on purpose -- see `OPPORTUNITY_TYPE_KEYWORDS` for why
    matching descriptions produced badly wrong classifications. First
    matching rule wins; an unmatched title returns
    ``DEFAULT_OPPORTUNITY_TYPE`` ("Out-of-school Programs"), which is the
    honest answer for most of this corpus rather than a forced guess.

    Deterministic and free -- unlike the other classification fields
    there is no LLM path for this yet, so it always runs at normalize
    time. An LLM pass would classify the long tail better.
    """
    for pattern, label in OPPORTUNITY_TYPE_KEYWORDS:
        if re.search(pattern, title, re.I):
            return label
    return DEFAULT_OPPORTUNITY_TYPE


def derive_age_grade_level(text: str) -> list[str]:
    """Derive `age_grade_level` tags from ``text``.

    No fallback -- an empty list is a genuinely unknown age range,
    matching `dev/export_site.py` (which applies no default here).
    """
    return tag_by_keywords(text, AGE_KEYWORDS)


def map_cost(cost_text: str) -> str:
    """Map free-text ``cost`` to the site's `cost_range` taxonomy where possible.

    Ported unchanged from `dev/export_site.py`'s `map_cost`.
    """
    if not cost_text:
        return ""
    lowered = cost_text.strip().lower()
    if "free" in lowered or lowered in ("$0", "0", "$0.00"):
        return "Free"
    amounts = [float(a) for a in _COST_AMOUNT_RE.findall(cost_text)]
    if amounts:
        low = min(amounts)
        if low == 0:
            return "Free"
        for cap, label in [
            (25, "Less than $25"),
            (50, "Less than $50"),
            (100, "Less than $100"),
            (200, "Less than $200"),
        ]:
            if low < cap:
                return label
        return "Greater than $200"
    # Unparseable but short enough to display as-is ("Included with admission").
    return cost_text if len(cost_text) <= 40 else ""


def derive_time_of_day(start: datetime | None, all_day: bool) -> list[str]:
    """Derive `time_of_day` from a canonical Event's `start`/`all_day`.

    Reimplemented against the canonical Event shape:
    `dev/export_site.py`'s `map_time_of_day` parsed a free-text time
    string; the Event model already carries a real `datetime`, so this
    reads its hour directly instead of re-parsing text -- same
    Morning/Afternoon/Evening hour thresholds as the original
    (`hour < 12` / `hour < 17`).
    """
    if all_day:
        return ["All Day"]
    if start is None:
        return []
    hour = start.hour
    if hour < 12:
        return ["Morning"]
    if hour < 17:
        return ["Afternoon"]
    return ["Evening"]


def build_taxonomy_text(title: str, description: str, categories: list[str], tags: list[str]) -> str:
    """Concatenate the fields keyword rules are matched against.

    Matches `dev/export_site.py`'s `text = " ".join([title, description,
    categories, tags])` blob-building.
    """
    return " ".join([title, description, " ".join(categories), " ".join(tags)])
