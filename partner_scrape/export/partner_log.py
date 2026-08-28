"""`partner_log.record()`: the persistent, per-partner, append-only accumulation layer.

`export/writer.py`'s `opportunities.json` is overwritten every run --
today's snapshot only. This module is issue 15's answer to "publish a
complete, self-describing export": a durable, cross-run record of
*every* `Opportunity` ever seen, keyed by partner and never pruned, so a
future build-time projection (`export/publish.py`, ticket 004) can
reconstruct current *and* past events with no other data source.

## Why a new module, not a reuse of `store/event_store.py`

`EventStore` and this module both look like "durable, cross-run,
identity-keyed" persistence, which invites the question of why sprint
009 built a second one instead of finally wiring the first in. They are
not the same problem: `EventStore` persists raw, pre-normalization
`Event`s keyed by *acquisition* identity ("have we already seen this
exact record from this source"), for the purpose of skipping
re-crawling. This module persists finished, post-dedup `Opportunity`s
keyed by *publish* identity (the reworked `Opportunity.slug`, sprint
009 ticket 002), for the purpose of never losing a published event.
`normalize/DESIGN.md` already states these two identity concepts must
not be conflated -- forcing one store to serve both would do exactly
that, and would also force `EventStore` (currently unwired,
pre-normalization) to sit downstream of `normalize/`, an entirely
different position in the pipeline than its own design describes. See
`export/DESIGN.md`'s matching entry for the full comparison.

## Directory layout

Partner directories are keyed by the *already-resolved* partner
identity (`Opportunity.partner_name`, via `model.slugify`), never by
raw scraper `source_id` -- an `Opportunity` can carry several
contributing `source_id`s (`Opportunity.sources`, from cross-source
dedup) but always resolves to exactly one partner via `normalize/`'s
existing partner join, so keying by the resolved partner has no
"which source owns this copy" ambiguity to answer.

```
{log_dir}/<partner-slug>/partner.json          -- curated partner record,
                                                   refreshed every call
{log_dir}/<partner-slug>/opportunities.jsonl   -- append-only; one JSON
                                                   object per line
```

`log_dir` defaults to `{config.get_scrape_cache_dir()}/partner_log/` --
no new environment variable, matching `enrich/cache.py`'s and
`store/event_store.py`'s existing "subdirectory of `SCRAPE_CACHE_DIR`"
convention.

## Append/skip identity

Each line carries every `Opportunity` field (`sources` as a plain,
sorted list, not a `frozenset`) plus `content_hash`
(`published_content_hash()`, below). A line is appended only when its
`(slug, content_hash)` pair is not already present for that partner; an
existing line is never edited or removed -- this is what lets past
events survive across runs even though nothing in this module ever
decides "current" vs. "past" (that is `publish.py`'s job, applied at
read time).

## Crash safety

Both files are written with a temp-file-then-`os.replace` swap
(`_atomic_write_text`), never opened in-place for writing. A run that
crashes mid-write leaves the *previous* complete file untouched -- there
is no window where a reader (or the next `record()` call) can observe a
half-written `partner.json` or `opportunities.jsonl`. Because the
append/skip decision already requires reading a partner's full
`opportunities.jsonl` into memory, writing the (unchanged prefix + any
new lines) back out atomically costs the same order of I/O as the read
that was already required -- it does not add a second full-file pass.
Note for future maintainers: this means each touched partner's *whole*
`.jsonl` is rewritten on every run that appends to it, which is fine at
today's (empty) starting scale but means write cost, like
`publish.py`'s already-flagged read cost, grows with total accumulated
history rather than with a single run's yield -- worth re-measuring
once real history accumulates, not solved speculatively here (see
`export/DESIGN.md`'s Open Questions).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import defaultdict
from dataclasses import fields
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import get_scrape_cache_dir, get_site_dir
from partner_scrape.model import slugify
from partner_scrape.normalize.partners import find_partner, load_partners
from partner_scrape.normalize.run import Opportunity

#: Subdirectory of `SCRAPE_CACHE_DIR` the accumulation store lives
#: under. No new environment variable -- matches `enrich/cache.py`'s
#: `_CACHE_SUBDIR` and `store/event_store.py`'s default-under-cache-dir
#: convention.
_LOG_SUBDIR = "partner_log"

#: Filename of each partner's append-only opportunities log, relative
#: to its own `<partner-slug>/` directory. A module-level constant, not
#: a literal, so `export/publish.py` (ticket 004) can import it rather
#: than re-guessing the filename -- this module never imports
#: `publish.py` (the dependency is one-way), it only exposes this name
#: for `publish.py` to depend on. See `export/DESIGN.md`.
_JSONL_FILENAME = "opportunities.jsonl"

#: Filename of each partner's curated-record snapshot, relative to its
#: own `<partner-slug>/` directory.
_PARTNER_JSON_FILENAME = "partner.json"

#: The published-schema fields `published_content_hash` hashes over,
#: matching SUC-005's Main Flow step 2 exactly. Deliberately excludes
#: identity/bookkeeping fields (`slug`, `sources`, `partner_name`,
#: `partner_id`, `availability`, contact fields, `logo_src`/`image_src`,
#: ...) -- this hash answers "did the *published* content change", not
#: "did anything about the record change".
_HASHED_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "date_start",
    "date_end",
    "location",
    "cost_range",
    "opportunity_type",
    "age_grade_level",
    "areas_of_interest",
    "time_of_day",
    "link",
)


def published_content_hash(opportunity: Opportunity) -> str:
    """Compute a stable hash over `opportunity`'s *published* fields.

    A distinct function from `enrich.cache.content_hash` -- that hash
    answers "did the LLM's *input* change" (pre-enrichment Event
    fields); this one answers "did the *published* content change"
    (post-enrichment, post-taxonomy, post-dedup `Opportunity` fields).
    Reusing one function's name for two different questions is exactly
    the kind of drift `store/event_store.py` warns against for its own,
    correct reuse of `enrich.cache.content_hash` (there, the question
    is identical; here, it is not) -- see `export/DESIGN.md`'s Design
    section.
    """
    payload = {name: getattr(opportunity, name) for name in _HASHED_FIELDS}
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _default_log_dir() -> Path:
    return get_scrape_cache_dir() / _LOG_SUBDIR


def _default_partners_path() -> Path:
    """`{site_dir}/src/data/partners.json` -- the same location
    `pipeline.run()` resolves for `normalize.run()`'s own `partners_path`
    (see `normalize/DESIGN.md`). Production callers (`pipeline.run()`)
    always pass the exact value they already resolved rather than
    relying on this default, so the two modules' partner join can never
    disagree about which `partners.json` they read.
    """
    return get_site_dir() / "src" / "data" / "partners.json"


def _to_log_dict(opportunity: Opportunity, content_hash: str) -> dict[str, Any]:
    """Project every `Opportunity` field to a JSON-able dict, `sources`
    as a plain sorted list (not a `frozenset`, which `json.dumps` can't
    serialize), plus `content_hash`. Unlike `writer.py`'s
    `_to_json_dict`, `sources` is kept -- this is the persisted record,
    not the site-schema-filtered export."""
    record = {f.name: getattr(opportunity, f.name) for f in fields(Opportunity)}
    record["sources"] = sorted(record["sources"])
    record["content_hash"] = content_hash
    return record


def _read_existing_lines(jsonl_path: Path) -> list[str]:
    if not jsonl_path.exists():
        return []
    text = jsonl_path.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def _existing_keys(lines: list[str]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for line in lines:
        entry = json.loads(line)
        keys.add((entry["slug"], entry["content_hash"]))
    return keys


def _atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` so a crash mid-write can never leave a
    half-written file: the new content lands in a sibling temp file
    first, fsynced, and only then atomically swapped over the target
    via `os.replace` (atomic on POSIX and Windows within one
    filesystem). Raises `RuntimeError` on any `OSError` -- matches
    `writer.py`'s/`ads.py`'s loud-failure philosophy for an unwritable
    target rather than silently skipping the write.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write partner log entry to {path}: {exc}. Check that "
            f"its parent directory is writable."
        ) from exc


def record(
    opportunities: Iterable[Opportunity],
    *,
    log_dir: str | Path | None = None,
    partners_path: str | Path | None = None,
    dry_run: bool = False,
) -> None:
    """Accumulate `opportunities` into their partner's append-only log.

    For each `Opportunity`, resolves a partner slug from its
    already-resolved `partner_name` (`model.slugify`, reused from the
    same primitive `normalize/run.py` uses for event slugs) and computes
    `published_content_hash(opportunity)`. A `(slug, content_hash)` pair
    already present in that partner's `opportunities.jsonl` is skipped
    (no write); anything else is appended as a new line. No existing
    line is ever edited or removed. Each touched partner's `partner.json`
    is refreshed from `normalize.partners.load_partners(partners_path)`
    every call, whether or not any new opportunity line was appended --
    it is a snapshot, not an append-only log.

    Args:
        opportunities: this run's normalized `Opportunity` records
            (typically `normalize.run()`'s output).
        log_dir: root of the per-partner accumulation store. Defaults to
            `config.get_scrape_cache_dir() / "partner_log"` when `None`.
            Tests should always pass an explicit `tmp_path` here, never
            rely on the default.
        partners_path: path to the site's curated `partners.json`.
            Defaults to `{config.get_site_dir()}/src/data/partners.json`
            when `None`. Production callers (`pipeline.run()`) pass the
            exact value already resolved for `normalize.run()`.
        dry_run: when `True`, compute the append/skip decision for every
            opportunity without touching disk at all -- no directory is
            created, no `partner.json` or `opportunities.jsonl` is
            written.

    Raises:
        RuntimeError: a partner's directory under `log_dir` cannot be
            created or written to. Never silently skips accumulation.
    """
    resolved_log_dir = Path(log_dir) if log_dir is not None else _default_log_dir()
    resolved_partners_path = (
        Path(partners_path) if partners_path is not None else _default_partners_path()
    )
    partners_by_norm = load_partners(resolved_partners_path)

    by_slug: dict[str, list[Opportunity]] = defaultdict(list)
    for opportunity in opportunities:
        by_slug[slugify(opportunity.partner_name)].append(opportunity)

    for partner_slug, opps in by_slug.items():
        partner_dir = resolved_log_dir / partner_slug
        jsonl_path = partner_dir / _JSONL_FILENAME

        # No match in the curated roster -> keep the org name, leave
        # `id` unset (`find_partner`'s existing non-fatal convention,
        # SUC-005's documented error flow) -- the partner still
        # accumulates normally under its org-name slug.
        curated = find_partner(opps[0].partner_name, partners_by_norm)
        partner_record: dict[str, Any] = (
            dict(curated) if curated is not None else {"id": opps[0].partner_id, "name": opps[0].partner_name}
        )

        existing_lines = _read_existing_lines(jsonl_path)
        existing_keys = _existing_keys(existing_lines)

        new_lines = list(existing_lines)
        appended = False
        for opportunity in opps:
            content_hash = published_content_hash(opportunity)
            key = (opportunity.slug, content_hash)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_lines.append(
                json.dumps(
                    _to_log_dict(opportunity, content_hash), sort_keys=True, ensure_ascii=False
                )
            )
            appended = True

        if dry_run:
            continue

        _atomic_write_text(
            partner_dir / _PARTNER_JSON_FILENAME,
            json.dumps(partner_record, indent=1, ensure_ascii=False, sort_keys=True),
        )
        if appended:
            _atomic_write_text(jsonl_path, "\n".join(new_lines) + "\n")
