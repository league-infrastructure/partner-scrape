"""Shared ATS posting classifier: internship? STEM? San Diego-local?

See ``sprint.md``'s Architecture > Step 3 module table ("ATS Filters"
row) and Design Rationale ("deterministic ... not via the existing LLM
relevance gate"): this module holds the internship-title, STEM-job-
keyword, and San-Diego-location heuristics used by *both* the
Greenhouse adapter (ticket 003) and the Lever adapter (ticket 004), so
the rules live in exactly one place rather than being duplicated per
adapter.

Every function here is a pure function over plain strings -- no
``Event``, no ``Fetcher``, no I/O -- so it is independently unit-
testable without either adapter (ticket 002's acceptance criteria).
Turning a match into a canonical ``Event`` (field mapping, ``kind=
"internship"``, ``external_id``, ...) stays each adapter's own job; see
this module's docstring boundary in sprint.md's module table ("Outside:
fetching, JSON parsing, or ``Event`` construction").

Reuses ``normalize/taxonomy.py``'s ``tag_by_keywords()`` helper (pure,
already general-purpose) for the STEM check, but supplies a new,
job-title-oriented keyword list (:data:`STEM_KEYWORDS`), not
``taxonomy.AREA_KEYWORDS`` -- that list is tuned for K-12 event/program
titles ("marine|ocean|aquarium...") and does not reliably match company
job titles like "Bioinformatics Intern" or "Data Science Intern"
(confirmed gap during architecture planning: neither "biology" nor
"data science" appears in ``AREA_KEYWORDS`` at all).

**Remote-location handling** (ticket 002's constraint: "decide how to
treat 'Remote' and document"): :func:`is_local_posting` is a plain
case-insensitive substring check against ``location_keywords`` (default
``["San Diego"]``). A bare ``"Remote"`` location carries no geographic
signal that the role is San-Diego-based, so it does **not** match under
the default keywords -- this is a deliberate exclusion, not an
oversight, since "remote" alone could mean anywhere. A location string
that combines both, e.g. ``"Remote - San Diego, CA"`` or ``"Remote
(San Diego)"``, *does* match, because the substring "San Diego" is
still present -- no special-casing of the word "Remote" itself is
needed or done.

**Does not produce a ``cost_range`` value.** See sprint.md's Design
Rationale / this ticket's acceptance criteria: ``cost_range``'s enum
represents cost *to the applicant*, and defaulting it (e.g. to "Free")
would make the site's cost badge misleadingly imply "this internship
doesn't pay," which is neither true nor knowable from either ATS's
public API. The caller (adapters, tickets 003/004) must leave
``Event.cost``/``Event.cost_range`` unset for internship postings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from partner_scrape.normalize.taxonomy import tag_by_keywords

#: Internship/early-career title or commitment-field signal. Matched
#: with ``re.IGNORECASE`` against a title (and, when present, a
#: separate commitment/department string -- Lever's ``categories.
#: commitment`` field often says "Intern"/"Internship" directly, per
#: sprint.md's SUC-002 main flow).
#:
#: Word-boundary safe by construction: ``\bintern(?:s|ship|ships)?\b``
#: matches "intern", "interns", "internship", "internships" as whole
#: words, but not "international" or "internal" -- the character after
#: "intern" in both of those words is a word character ("a"), so no
#: ``\b`` boundary exists at that position and the optional
#: ``(?:s|ship|ships)`` group cannot consume it either (neither word
#: continues with "s" or "ship").
INTERNSHIP_PATTERNS: list[str] = [
    r"\bintern(?:s|ship|ships)?\b",
    r"\bco[- ]?op\b",
    r"\bapprentice(?:ship)?\b",
    r"\bearly[- ]career\b",
]

_INTERNSHIP_RE = re.compile("|".join(INTERNSHIP_PATTERNS), re.IGNORECASE)

#: Job-title-oriented STEM keyword rules, (pattern, label) pairs in the
#: same shape as ``normalize/taxonomy.AREA_KEYWORDS`` (reusing
#: ``tag_by_keywords`` below) but broader, since job titles and ATS
#: department strings don't reliably match that event-oriented list
#: (see module docstring). Covers: engineering, software, data,
#: biology/biomedical/bioinformatics/genomics, chemistry, physics,
#: hardware/firmware, robotics/ML/AI, mechanical/electrical/aerospace,
#: manufacturing/lab/R&D, semiconductor/wireless -- per ticket 002's
#: acceptance criteria.
STEM_KEYWORDS: list[tuple[str, str]] = [
    (r"\bengineer(?:ing|s)?\b", "Engineering"),
    (r"\bsoftware\b", "Software"),
    (r"\bdata\b", "Data"),
    (r"\b(biology|biomedical|bioinformatics|genomics|biotech)\b", "Biology/Biomedical"),
    (r"\b(chemistry|chemical)\b", "Chemistry"),
    (r"\bphysics\b", "Physics"),
    (r"\b(hardware|firmware)\b", "Hardware/Firmware"),
    (r"\b(robotics|robot|machine learning|\bml\b|\bai\b|artificial intelligence)\b", "Robotics/ML/AI"),
    (r"\b(mechanical|electrical|aerospace)\b", "Mechanical/Electrical/Aerospace"),
    (r"\b(manufacturing|laboratory|\blab\b|r&d|research)\b", "Manufacturing/Lab/R&D"),
    (r"\b(semiconductor|wireless)\b", "Semiconductor/Wireless"),
    (r"\bscientist\b", "Scientist"),
]

#: Default location-match keywords, per ticket 002's acceptance
#: criteria: ``is_local_posting``'s default. Mirrors ``SourceConfig.
#: config``'s existing per-source-tunable pattern (e.g. ``localist.py``'s
#: ``days``/``pp``) -- a source-level ``location_keywords`` override
#: changes the match set with no code change.
DEFAULT_LOCATION_KEYWORDS: list[str] = ["San Diego"]

#: PhD/graduate-level title signal -- when present, ``classify_posting``
#: adds ``"Graduate"`` to the default ``age_grade_level`` list. Deliberately
#: word-boundary safe: ``\bgraduate\b`` does not match inside
#: "undergraduate" (no boundary between "under" and "graduate").
_GRADUATE_RE = re.compile(r"\b(ph\.?d|doctoral|graduate|master'?s|msc|postdoc(?:toral)?)\b", re.IGNORECASE)

#: Default ``age_grade_level`` for a matching posting, per ticket 002's
#: acceptance criteria. ``"Graduate"`` is appended, not substituted,
#: when the title carries a PhD/graduate-level keyword (see
#: ``_GRADUATE_RE``).
DEFAULT_AGE_GRADE_LEVEL: list[str] = ["Grades 9-12", "Undergraduate"]

#: Default ``time_of_day`` for a matching posting -- a full workday
#: commitment, the closest fit in the existing enum (sprint.md SUC-003).
DEFAULT_TIME_OF_DAY: list[str] = ["All Day"]


@dataclass(frozen=True)
class PostingVerdict:
    """Default classification values for one posting that passed all three checks.

    Deliberately carries no ``cost_range`` field -- see module
    docstring and ticket 002's acceptance criteria: the caller must not
    set ``Event.cost``/``Event.cost_range`` from this module's output.
    """

    age_grade_level: list[str] = field(default_factory=list)
    time_of_day: list[str] = field(default_factory=list)


def is_internship_posting(title: str, commitment: str = "") -> bool:
    """Report whether ``title`` (or ``commitment``) signals an internship/early-career role.

    Matches "Software Engineering Intern", "Biology Research Intern",
    "Data Science Co-op", "Marketing Apprenticeship". Does not match
    "Senior Software Engineer", "VP of Sales", "International Sales
    Manager" -- see :data:`INTERNSHIP_PATTERNS`'s word-boundary-safety
    note.
    """
    return bool(_INTERNSHIP_RE.search(title) or (commitment and _INTERNSHIP_RE.search(commitment)))


def is_stem_posting(title: str, department: str = "") -> bool:
    """Report whether ``title``/``department`` signal a STEM role.

    Matches "Bioinformatics Intern", "Data Science Intern", "Hardware
    Engineering Intern". Does not match "Marketing Intern", "HR
    Coordinator Intern". Uses :data:`STEM_KEYWORDS`, a job-title-
    oriented set broader than ``normalize.taxonomy.AREA_KEYWORDS`` (see
    module docstring).
    """
    text = f"{title} {department}" if department else title
    return bool(tag_by_keywords(text, STEM_KEYWORDS))


def is_local_posting(location: str, keywords: list[str] | None = None) -> bool:
    """Report whether ``location`` matches any of ``keywords`` (default ``["San Diego"]``).

    Case-insensitive substring match. "San Diego, CA" matches; "Remote"
    and "Austin, TX" do not, under the default keywords -- see module
    docstring's Remote-handling note. Passing ``keywords=["La Jolla",
    "San Diego"]`` (or any other list) overrides the match set entirely,
    with no code change, mirroring ``SourceConfig.config``'s existing
    per-source-tunable pattern.
    """
    active_keywords = keywords if keywords is not None else DEFAULT_LOCATION_KEYWORDS
    lowered = location.lower()
    return any(keyword.lower() in lowered for keyword in active_keywords)


def _is_graduate_level(title: str) -> bool:
    """Report whether ``title`` carries a PhD/graduate-level signal."""
    return bool(_GRADUATE_RE.search(title))


def classify_posting(
    title: str,
    commitment: str = "",
    department: str = "",
    location: str = "",
    location_keywords: list[str] | None = None,
) -> PostingVerdict | None:
    """Combine the three checks (AND) into one match/no-match verdict.

    Returns ``None`` when any of :func:`is_internship_posting`,
    :func:`is_stem_posting`, :func:`is_local_posting` fails. On a match,
    returns a :class:`PostingVerdict` with default ``age_grade_level``
    (``["Grades 9-12", "Undergraduate"]``, plus ``"Graduate"`` when
    ``title`` contains a PhD/graduate-level keyword) and ``time_of_day``
    (``["All Day"]``) -- per ticket 002's acceptance criteria. Deliberately
    produces no ``cost_range`` value (see module docstring).
    """
    if not is_internship_posting(title, commitment):
        return None
    if not is_stem_posting(title, department):
        return None
    if not is_local_posting(location, location_keywords):
        return None

    age_grade_level = list(DEFAULT_AGE_GRADE_LEVEL)
    if _is_graduate_level(title):
        age_grade_level.append("Graduate")

    return PostingVerdict(
        age_grade_level=age_grade_level,
        time_of_day=list(DEFAULT_TIME_OF_DAY),
    )
