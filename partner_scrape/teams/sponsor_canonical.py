"""Sponsor-name canonicalization (``teams.sponsor_canonical``).

Sprint 013 ticket 005, reopened. The first pass of this ticket wired
extraction/dedup together but only deduped a *single team's* structured
vs. scraped sponsor names against each other. Auditing the real,
regenerated ``teams.json`` after that pass shipped (57 teams with
sponsors, 130 "distinct" sponsor strings) showed the real defect: the
*same* company is reported under different spellings by *different*
teams' own structured records (``"QualComm"`` for one team,
``"Qualcomm"`` for eighteen others, ``"Qualcomm Inc"`` for one more) --
no per-team merge, however good, can ever see that, because each
team's ``sponsors`` list is independent. Counted naively, Qualcomm --
the single most important data point, sponsoring ~20 teams -- looked
like three different companies. This module is the fix: a
corpus-wide canonicalization pass, layered on top of (never inside)
``normalize.partners.normalize_org_name`` -- reused, per this ticket's
own "do not write a second normalizer" instruction, as the shared base
every match key here builds on. ``normalize_org_name`` itself is never
modified: it is the shared key for the curated partner-directory join,
and changing its behavior would silently alter which opportunities
match which partner (see this ticket's own scope boundary).

**Two problems, two fixes, one shared match key.**

1. **Corruption, not formatting.** A handful of FTCScout-sourced
   sponsor strings carry a literal, byte-for-byte-verbatim ``"&R"``
   suffix -- ``"Solar Turbines, Inc&R"``, ``"Francis Parker
   School&R"``, ``"Caterpillar&R"`` -- and one compound string joins
   two unrelated sponsor names with a bare, unspaced ``"&"``
   (``"General Atomics Aeronautical Inc.&Classical Academy High
   School"``). Investigated directly against
   ``tests/fixtures/teams/ftcscout_search.json`` (documented as "a
   real, live-captured response... unmodified beyond JSON
   pretty-printing"): every one of these strings already appears
   corrupted *verbatim in the raw JSON FTCScout's API returns*.
   ``sources/ftcscout.py::_extract_one`` does nothing to a sponsor
   string beyond ``list(sponsors_raw)`` -- no ``html.unescape``, no
   regex, no string manipulation of any kind sits between the API
   response and ``Team.sponsors``. **There is no decode step in this
   project's own code to fix**; the corruption is baked into the data
   FTCScout's API hands us. (Best reconstruction of *their* bug, for
   the record: ``"&R"`` sits exactly where a ``"®"`` registered-
   trademark mark would naturally appear -- immediately after "Inc",
   "School", "Caterpillar", with no separating space -- consistent
   with their own ingestion mis-decoding a ``&reg;``/``&REG;`` HTML
   entity and truncating it to its first two characters. Not
   reproducible or fixable from this side.) ``_strip_trademark_artifact``
   and ``_split_joined_names`` (used by :func:`expand_local`) are a
   narrow, evidence-based defensive cleanup against exactly these two
   observed shapes -- not a general HTML-entity decoder, since there
   is no decoding happening on our side to correct.

2. **No canonicalization across spelling variants.** Case
   (``"QualComm"``/``"Qualcomm"``), corporate suffixes
   (``"Qualcomm"``/``"Qualcomm Inc"``), hostname forms
   (``"nordson.com"`` -> ``"Nordson"``), and image-filename forms
   (``"1280px-Thermo_Fisher_Scientific_logo"`` -> ``"Thermo Fisher
   Scientific"``) all need to collapse to one company for the
   stakeholder's stated goal ("keep track of which companies are
   engaged in sponsoring teams") to mean anything. :func:`canonical_key`
   is the shared match key every merge decision in this module (and,
   via :func:`canonical_key` being imported into ``sponsor_extract.py``,
   the pre-existing per-team structured/scraped merge too) now uses --
   ``normalize_org_name`` plus corporate-suffix stripping.
   :func:`canonicalize_sponsors` is the corpus-wide pass:
   local per-name cleanup -> corpus-wide hostname/filename
   reconstruction (matched against every *other* clean name already
   observed in this run) -> a token-prefix clustering pass (folds
   ``"Francis Parker"`` into ``"Francis Parker School"``) -> one
   canonical display chosen per cluster, applied to every team that
   mentions it.

**Display vs. match key, kept separate throughout** (this ticket's own
design note): every function that decides whether two names are "the
same company" compares :func:`canonical_key` output, never a display
string. What gets *published* is always an actual observed spelling --
never a fabricated title-cased guess invented from nothing -- chosen by
:func:`_pick_canonical_display`'s "prefer structured provenance, then a
suffix-free form, then the most common spelling" rule. A name this
module cannot deterministically clean or match against anything already
known-clean (e.g. ``"te.com"``, ``"haascnc.com"`` -- no other mention of
either company anywhere in this run to recover a real name from) is
**dropped**, never published as a mangled hostname or filename
fragment -- this ticket's own explicit instruction ("prefer dropping
the junk variant over publishing a mangled string") over a fragile
guess.

**Deliberately not attempted**: fuzzy business-relationship clustering
of legally-distinct-but-affiliated entities (``"CAT"``/``"Caterpillar"``
-- a ticker vs. a name, no deterministic string transformation connects
them; ``"General Atomics Aeronautical Inc."`` vs. ``"General Atomics
Sciences Education Foundation"`` -- a subsidiary and a nonprofit arm of
the same parent, not spelling variants of the same legal name). Merging
those would require a hand-curated alias table, which is exactly the
kind of judgment call this module's deterministic, string-level
canonicalization is not -- see ``teams/DESIGN.md``'s Open Questions.

Same zero-edges invariant as every other ``teams/`` module: no import
from ``enrich/``, ``adapters/``, or ``normalize.run()``/``pipeline.run()``
-- only ``normalize.partners.normalize_org_name`` (the one sanctioned
exception, matching ``sponsor_extract.py``'s and ``teams.merge``'s own
precedent) plus sibling ``teams/`` modules.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Mapping

from partner_scrape.normalize.partners import normalize_org_name
from partner_scrape.teams.model import Team

# --------------------------------------------------------------------------
# canonical_key: the shared match key (normalize_org_name + corporate-suffix
# stripping). Used both by this module's own corpus-wide pass and by
# sponsor_extract.py's pre-existing per-team structured/scraped merge.
# --------------------------------------------------------------------------

#: Common corporate legal suffixes, checked as the *last* normalized token
#: only (never mid-name) -- "Qualcomm Inc" -> "qualcomm", "Solar Turbines,
#: Inc" -> "solar turbines", "Nordson Corporation" -> "nordson", "Stella
#: Maris LLC" -> "stella maris". Applied to an already normalize_org_name'd
#: string, so punctuation ("Inc.", "Bourns, Inc.") is already gone by the
#: time this set is checked.
_CORPORATE_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "corp",
        "corporation",
        "co",
        "company",
        "ltd",
        "limited",
        "plc",
    }
)


def _suffix_stripped_tokens(name: str) -> list[str]:
    tokens = normalize_org_name(name).split()
    while tokens and tokens[-1] in _CORPORATE_SUFFIXES:
        tokens.pop()
    return tokens


def canonical_key(name: str) -> str:
    """The shared match key for "is this the same company": ``normalize_org_name``
    (case/punctuation/leading-article/whitespace, reused verbatim) plus a
    trailing corporate-legal-suffix strip this module adds on top. Never
    used as a display value -- see the module docstring's "display vs.
    match key" note.
    """
    return " ".join(_suffix_stripped_tokens(name))


def _has_corporate_suffix(name: str) -> bool:
    """Whether ``name``'s own last normalized token is a corporate suffix --
    used only to prefer a suffix-free spelling as the *display* form when
    :func:`_pick_canonical_display` has a choice, never for matching."""
    tokens = normalize_org_name(name).split()
    return bool(tokens) and tokens[-1] in _CORPORATE_SUFFIXES


# --------------------------------------------------------------------------
# expand_local: self-contained per-name cleanup needing no corpus-wide
# data -- the FTCScout "&R" trademark-artifact corruption, the compound
# "X.&Y" joined-list-item corruption, and a trailing "<name> logo"-style
# alt-text artifact. See module docstring's "Corruption, not formatting"
# section for why these three (and only these three) are handled here as
# narrow, evidence-based fixes rather than a general decoder.
# --------------------------------------------------------------------------

#: Matches a literal trailing "&R" with no preceding whitespace -- the
#: exact, byte-for-byte shape confirmed present in FTCScout's own raw API
#: response for every real instance found in this project's live data
#: ("Solar Turbines, Inc&R", "Francis Parker School&R", "Caterpillar&R").
#: Anchored to the *end* of the string specifically so it never touches
#: "R&D Robotics Education" (a real company name, "&" mid-string, nothing
#: after the "D") or any other genuine "&"-containing name in this
#: project's data -- every one of those has whitespace on both sides of
#: its "&", never this exact "no-space, at end of string" shape.
_TRADEMARK_ARTIFACT_RE = re.compile(r"&R$")


def _strip_trademark_artifact(name: str) -> str:
    return _TRADEMARK_ARTIFACT_RE.sub("", name).rstrip()


#: Matches "<head ending in a literal '.'>&<tail starting with a capital
#: letter>" -- the shape of the one real compound-corruption instance
#: found ("General Atomics Aeronautical Inc.&Classical Academy High
#: School"). Requires the "." immediately before "&" (no space) so it
#: never matches a genuine spaced "X & Y" company name ("William A. Steen
#: & Associates", "Delta Fire & Safety" -- both have a space before their
#: "&") and never matches "R&D Robotics Education" (no "." before its
#: "&" at all).
_JOINED_NAMES_RE = re.compile(r"^(?P<head>.+\.)&(?P<tail>[A-Z].+)$")


def _split_joined_names(name: str) -> list[str]:
    match = _JOINED_NAMES_RE.match(name)
    if not match:
        return [name]
    return [match.group("head").strip(), match.group("tail").strip()]


#: A single trailing whitespace-separated word this common, real
#: ``<img alt="X logo">``-style pattern leaves behind -- observed
#: repeatedly in one team's own scraped footer ("California Protons
#: logo", "PCH Litho logo", "Pluribus Digital logo", "General Atomics
#: Sciences Education Foundation logo"). Stripped from the *end* of a
#: whitespace-separated (i.e. already-legible, non-slug) candidate only --
#: the slug/hostname reconstruction pipeline below has its own, richer
#: boilerplate-token handling for filename-shaped strings.
_BOILERPLATE_WORDS = frozenset({"logo", "logos", "icon", "icons", "banner", "image", "img", "photo"})


def _strip_trailing_boilerplate_word(name: str) -> str:
    tokens = name.split()
    while tokens and tokens[-1].casefold().strip(".:,") in _BOILERPLATE_WORDS:
        tokens.pop()
    return " ".join(tokens)


def expand_local(raw: str) -> list[str]:
    """Self-contained cleanup of one raw sponsor display string, needing no
    corpus-wide reference data: strip a trailing FTCScout "&R" artifact,
    split a "X.&Y" joined-list-item corruption into two names, then strip
    a trailing " logo"/" icon"/etc. alt-text artifact from each result.

    Returns 0, 1, or 2 cleaned display strings (2 only for the joined-name
    case; 0 if every step above left nothing).
    """
    result: list[str] = []
    for part in _split_joined_names(_strip_trademark_artifact(raw.strip())):
        cleaned = _strip_trailing_boilerplate_word(part.strip())
        if cleaned:
            result.append(cleaned)
    return result


# --------------------------------------------------------------------------
# Hostname/filename detection + corpus-wide reconstruction. Unlike
# expand_local above, this needs a reference set of already-clean names
# observed elsewhere in the same run -- "nordson.com" cannot recover the
# word break in "Nordson" from its own characters alone, but can if
# "Nordson" is independently known-clean somewhere else in this run.
# --------------------------------------------------------------------------

_HOSTNAME_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*\.(?:com|org|net|edu|us|io)$", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)+$", re.IGNORECASE)


def is_slug_like(name: str) -> bool:
    """Whether ``name`` is shaped like a bare hostname (``"nordson.com"``)
    or an underscore/hyphen-joined filename slug (``"Nordson-Corporation-
    Logo-web"``, ``"1280px-Thermo_Fisher_Scientific_logo"``) rather than
    ordinary, already-legible display text. A real display name in this
    project's data always either contains whitespace or is a single plain
    word with no ``-``/``_``/hostname-TLD shape -- so this check is a
    clean, non-overlapping partition, not a fuzzy heuristic.
    """
    stripped = name.strip()
    if not stripped or " " in stripped:
        return False
    return bool(_HOSTNAME_RE.match(stripped) or _SLUG_RE.match(stripped))


#: A leading "<digits>px" image-size prefix (e.g. "1280px-") -- a strong,
#: unambiguous signal this is a filename, not a name, and (combined with a
#: trailing boilerplate token) positive evidence :func:`reconstruct_slug`'s
#: 3-token blind-join fallback can rely on.
_LEADING_SIZE_PREFIX_RE = re.compile(r"^\d+px[-_]?", re.IGNORECASE)
_TLD_SUFFIX_RE = re.compile(r"\.(?:com|org|net|edu|us|io)$", re.IGNORECASE)
_SLUG_SPLIT_RE = re.compile(r"[-_]+")

#: Trailing tokens stripped repeatedly from a slug/hostname's tail --
#: image/asset boilerplate, never part of a real company name.
_SLUG_BOILERPLATE_TOKENS = frozenset(
    {
        "logo",
        "logos",
        "web",
        "icon",
        "icons",
        "image",
        "img",
        "png",
        "jpg",
        "jpeg",
        "svg",
        "gif",
        "banner",
        "header",
        "footer",
        "thumb",
        "thumbnail",
    }
)

#: The minimum length a reference compact key must have before it is
#: eligible to match as a *prefix* (not exact match) of a single-token
#: hostname/slug's compact form -- defense against a short, coincidental
#: reference key (e.g. a hypothetical 3-character "cat") falsely matching
#: an unrelated longer hostname label that merely happens to start with
#: the same letters. Exact matches are never subject to this floor.
_MIN_COMPACT_PREFIX_LEN = 4


def _slug_tokens(name: str) -> tuple[list[str], bool]:
    """Strip a leading size-prefix and TLD suffix, split the remainder on
    ``-``/``_``, then strip trailing boilerplate tokens (repeatedly).
    Returns the surviving tokens plus whether any marker (size-prefix or
    boilerplate token) was actually found -- positive evidence this really
    is a "decorated" filename, used to gate the 3-token blind-join
    fallback in :func:`reconstruct_slug`.
    """
    working = name.strip()
    had_marker = False

    size_match = _LEADING_SIZE_PREFIX_RE.match(working)
    if size_match:
        working = working[size_match.end() :]
        had_marker = True

    working = _TLD_SUFFIX_RE.sub("", working)
    tokens = [t for t in _SLUG_SPLIT_RE.split(working) if t]

    while tokens and tokens[-1].casefold() in _SLUG_BOILERPLATE_TOKENS:
        tokens.pop()
        had_marker = True

    return tokens, had_marker


def reconstruct_slug(
    name: str,
    token_reference: Mapping[tuple[str, ...], str],
    compact_reference: Mapping[str, str],
) -> str | None:
    """Recover a clean display name from a hostname/filename-shaped
    ``name`` (``is_slug_like(name)`` must be true), or return ``None`` to
    signal "drop this, never publish a mangled string."

    Two independent recovery paths, tried in order:

    1. **Cross-reference against ``token_reference``/``compact_reference``**
       -- names already known-clean elsewhere in this same run (see
       :func:`_build_reference`). A multi-token slug (``-``/``_``
       explicitly present, e.g. "Viasat-cef-science-olympiad") matches by
       its longest token-tuple prefix against ``token_reference`` --
       "Viasat" alone matches, the trailing "cef-science-olympiad"
       descriptor is dropped as unexplained junk. A single fused token
       (a bare hostname label with no internal delimiter, e.g.
       "solarturbines" from "solarturbines.com") matches by exact or
       (length-guarded) prefix compact-string comparison against
       ``compact_reference``, since there is no delimiter information to
       tokenize by -- word boundaries can only come from a known-clean
       reference, never guessed.
    2. **Blind title-case join**, only when (1) found nothing: a 2-token
       slug is always safe to join (its own explicit ``-``/``_``
       delimiters already encode real word boundaries -- "millipore-
       sigma" -> "Millipore Sigma"); a 3-token slug is joined only when a
       positive filename marker (leading size-prefix or a stripped
       trailing boilerplate token) was found, since that is the evidence
       distinguishing a "decorated" filename's real name (e.g. "1280px-
       Thermo_Fisher_Scientific_logo" -> "Thermo Fisher Scientific") from
       an arbitrary bare multi-word slug of unknown structure. A single
       fused token or an unmarked run of 4+ tokens is never blind-joined
       (a bare hostname label may not actually be one word plus
       punctuation stripped, and an unmarked long slug -- "viasat-cef-
       science-olympiad" -- is far more likely to be a name plus
       unrelated descriptive text than a company name in full).
    """
    tokens, had_marker = _slug_tokens(name)
    if not tokens:
        return None

    if len(tokens) > 1:
        key_tokens = tuple(t.casefold() for t in tokens)
        for prefix_len in range(len(key_tokens), 0, -1):
            prefix = key_tokens[:prefix_len]
            if prefix in token_reference:
                return token_reference[prefix]
        if len(tokens) == 2 or (len(tokens) == 3 and had_marker):
            return " ".join(t[:1].upper() + t[1:].lower() for t in tokens)
        return None

    compact = tokens[0].casefold()
    if compact in compact_reference:
        return compact_reference[compact]
    for ref_key, ref_display in compact_reference.items():
        if (
            len(ref_key) >= _MIN_COMPACT_PREFIX_LEN
            and ref_key != compact
            and compact.startswith(ref_key)
        ):
            return ref_display
    return None


def _build_reference(teams: list[Team]) -> tuple[dict[tuple[str, ...], str], dict[str, str]]:
    """Every already-clean (not :func:`is_slug_like`) sponsor display name
    across the whole ``teams`` list, indexed two ways for
    :func:`reconstruct_slug`: by its :func:`canonical_key`'s whitespace-
    split tokens (for multi-token slug matching) and by those tokens
    joined with no separator (for single-fused-token hostname matching).
    First-seen wins a collision (iteration order over ``teams`` is the
    only tie-break needed here -- a genuine collision between two
    differently-spelled-but-identically-keyed clean names is exactly what
    :func:`canonicalize_sponsors`'s own later grouping pass reconciles).
    """
    token_reference: dict[tuple[str, ...], str] = {}
    compact_reference: dict[str, str] = {}
    for team in teams:
        for name in team.sponsors:
            if is_slug_like(name):
                continue
            key_tokens = tuple(canonical_key(name).split())
            if not key_tokens:
                continue
            token_reference.setdefault(key_tokens, name)
            compact_reference.setdefault("".join(key_tokens), name)
    return token_reference, compact_reference


# --------------------------------------------------------------------------
# Corpus-wide clustering + display selection.
# --------------------------------------------------------------------------

#: A canonical_key is eligible to act as a *prefix* cluster root (folding
#: a longer name into a shorter one it starts with -- "Francis Parker"
#: absorbing "Francis Parker School") only if it is "specific enough" to
#: rule out coincidence: at least two words, or a single word of at least
#: this many characters. Blocks a short, generic single word ("Boys",
#: "CAT") from ever acting as a prefix root; confirmed empirically against
#: this project's real 130-string corpus to produce exactly the intended
#: merges ("Francis Parker"/"Francis Parker School", "AFCEA"/"AFCEA San
#: Diego") and no unintended ones.
_MIN_PREFIX_ROOT_SINGLE_TOKEN_LEN = 5


def _is_safe_prefix_root(key_tokens: tuple[str, ...]) -> bool:
    if len(key_tokens) >= 2:
        return True
    return len(key_tokens) == 1 and len(key_tokens[0]) >= _MIN_PREFIX_ROOT_SINGLE_TOKEN_LEN


def _cluster_keys(keys: list[str]) -> dict[str, str]:
    """Union-find clustering of distinct ``canonical_key`` strings: two
    keys cluster together when one's whitespace-split tokens are a proper
    prefix of the other's (and the shorter one is "safe" per
    :func:`_is_safe_prefix_root` above) -- the mechanism that folds
    "Francis Parker" into the same company as "Francis Parker School"
    despite "School" not being a corporate suffix ``canonical_key`` itself
    strips. Exact-equal keys are already the same dict key and need no
    union step. Returns ``{key: cluster_root}`` for every key in ``keys``.
    """
    parent = {key: key for key in keys}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    tokens_of = {key: tuple(key.split()) for key in keys}

    for shorter in keys:
        shorter_tokens = tokens_of[shorter]
        if not shorter_tokens or not _is_safe_prefix_root(shorter_tokens):
            continue
        for longer in keys:
            if shorter == longer:
                continue
            longer_tokens = tokens_of[longer]
            if len(longer_tokens) > len(shorter_tokens) and longer_tokens[: len(shorter_tokens)] == shorter_tokens:
                union(shorter, longer)

    return {key: find(key) for key in keys}


def _pick_canonical_display(
    names: list[str], counts: Counter, provenances: Mapping[str, set]
) -> str:
    """Choose one display string to publish for every name in ``names``
    (all sharing one cluster). Preference order: a display seen with
    ``"structured"`` provenance beats one only ever seen ``"scraped"``; a
    suffix-free spelling beats one carrying a corporate suffix
    (``"Solar Turbines"`` over ``"Solar Turbines, Inc"``, both structured);
    the most common raw spelling across the corpus wins ties (``"DoD
    STEM"``, seen on 3 teams, over ``"DOD STEM"``/``"Dod stem"``, one
    each); a final deterministic tie-break (shortest, then alphabetical)
    resolves any remainder (``"REV Robotics"`` over ``"Rev Robotics"`` --
    both structured, suffix-free, count 1). Never fabricates a spelling
    not actually observed somewhere in this run.
    """
    structured = [n for n in names if "structured" in provenances.get(n, set())]
    pool = structured if structured else names

    suffix_free = [n for n in pool if not _has_corporate_suffix(n)]
    pool = suffix_free if suffix_free else pool

    max_count = max(counts[n] for n in pool)
    top = [n for n in pool if counts[n] == max_count]
    return sorted(top, key=lambda n: (len(n), n))[0]


def _rebuild_team(team: Team, entries: list[tuple[str, str]]) -> None:
    """Rebuild ``team.sponsors``/``team.sponsor_provenance`` from
    ``entries`` (``(display_name, provenance)`` pairs, in the order they
    should appear), deduplicating by :func:`canonical_key` -- a
    ``"structured"`` provenance always wins a same-key conflict over
    ``"scraped"``, matching ``sponsor_extract.py::_merge_sponsors``'s own
    existing preference. Used by every rewrite step in this module (local
    expansion, slug reconstruction, final display normalization) so all
    three share one dedup rule.
    """
    new_sponsors: list[str] = []
    new_provenance: dict[str, str] = {}
    display_by_key: dict[str, str] = {}

    for name, provenance in entries:
        key = canonical_key(name)
        if not key:
            continue
        existing = display_by_key.get(key)
        if existing is not None:
            if provenance == "structured" and new_provenance.get(existing) != "structured":
                new_provenance[existing] = "structured"
            continue
        display_by_key[key] = name
        new_sponsors.append(name)
        new_provenance[name] = provenance

    team.sponsors = new_sponsors
    team.sponsor_provenance = new_provenance


def _apply_local_expansion(team: Team) -> None:
    entries: list[tuple[str, str]] = []
    for name in team.sponsors:
        provenance = team.sponsor_provenance.get(name, "")
        for expanded in expand_local(name):
            entries.append((expanded, provenance))
    _rebuild_team(team, entries)


def _apply_slug_reconstruction(
    team: Team,
    token_reference: Mapping[tuple[str, ...], str],
    compact_reference: Mapping[str, str],
) -> None:
    entries: list[tuple[str, str]] = []
    for name in team.sponsors:
        provenance = team.sponsor_provenance.get(name, "")
        if is_slug_like(name):
            resolved = reconstruct_slug(name, token_reference, compact_reference)
            if resolved is None:
                continue
            entries.append((resolved, provenance))
        else:
            entries.append((name, provenance))
    _rebuild_team(team, entries)


def canonicalize_sponsors(teams: list[Team]) -> None:
    """Corpus-wide sponsor-name canonicalization: mutates every ``Team``
    in ``teams`` in place so the same real company is published under one
    consistent display name everywhere it is mentioned, across every
    team, not just within one team's own list. Called once by
    ``teams.pipeline.run_teams()``, after ``extract_sponsors()`` (or
    ``--no-sponsors``) and before ``export_teams()`` -- see that module's
    own docstring for why this must run unconditionally, even when
    sponsor scraping itself is skipped.

    Four passes, in order (see the module docstring for the full
    rationale behind each):

    1. :func:`_apply_local_expansion` on every team -- corruption cleanup
       and joined-name splitting, needing no cross-team data.
    2. Build the corpus-wide clean-name reference (:func:`_build_reference`)
       from the now locally-cleaned corpus.
    3. :func:`_apply_slug_reconstruction` on every team -- resolve or drop
       every remaining hostname/filename-shaped name against that
       reference.
    4. Global clustering (:func:`_cluster_keys`) and display selection
       (:func:`_pick_canonical_display`) across every team's now-clean
       sponsor list, then one final rewrite pass so every team uses the
       same chosen display for the same company. A team's own
       ``sponsor_provenance`` value for its own claim is never altered by
       this step -- only the *display string* used as that claim's key
       changes; whether a name is that team's ``"structured"`` claim or
       ``"scraped"`` one is untouched.
    """
    for team in teams:
        _apply_local_expansion(team)

    token_reference, compact_reference = _build_reference(teams)

    for team in teams:
        _apply_slug_reconstruction(team, token_reference, compact_reference)

    key_of: dict[str, str] = {}
    counts: Counter[str] = Counter()
    provenances: dict[str, set[str]] = defaultdict(set)
    for team in teams:
        for name in team.sponsors:
            key_of[name] = canonical_key(name)
            counts[name] += 1
            provenance = team.sponsor_provenance.get(name, "")
            if provenance:
                provenances[name].add(provenance)

    keys = sorted({key for key in key_of.values() if key})
    root_of = _cluster_keys(keys)

    cluster_names: dict[str, list[str]] = defaultdict(list)
    for name, key in key_of.items():
        if not key:
            continue
        cluster_names[root_of[key]].append(name)

    canonical_display: dict[str, str] = {
        root: _pick_canonical_display(names, counts, provenances)
        for root, names in cluster_names.items()
    }

    for team in teams:
        entries: list[tuple[str, str]] = []
        for name in team.sponsors:
            key = key_of.get(name, "")
            if not key:
                continue
            display = canonical_display.get(root_of.get(key, key), name)
            entries.append((display, team.sponsor_provenance.get(name, "")))
        _rebuild_team(team, entries)
