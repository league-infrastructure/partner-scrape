"""Publish the data schema doc next to the data it describes.

``docs/data-schema.md`` is the source of truth for the published output's
schema. It is bundled into the wheel (hatch ``force-include`` in
``pyproject.toml``) as ``partner_scrape/data-schema.md`` and written to
the data Store as ``SCHEMA.md`` -- ``data/SCHEMA.md`` in the bucket -- at
the end of a normal run, so consumers of the bucket find the schema
beside the files it describes.
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.config import resolve_data_store
from partner_scrape.storage import Store

#: Key of the published copy, relative to the data Store.
SCHEMA_DOC_KEY = "SCHEMA.md"

_BUNDLED = Path(__file__).resolve().parent.parent / "data-schema.md"
_SOURCE_CHECKOUT = Path(__file__).resolve().parent.parent.parent / "docs" / "data-schema.md"


def schema_doc_path() -> Path:
    """Locate the schema doc: the wheel-bundled copy, else the repo's
    ``docs/data-schema.md`` (source checkout / editable install)."""
    for candidate in (_BUNDLED, _SOURCE_CHECKOUT):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"data schema doc not found (looked in {_BUNDLED} and {_SOURCE_CHECKOUT})"
    )


def publish_schema_doc(store: Store | str | Path | None = None) -> str:
    """Write the schema doc to ``SCHEMA.md`` in the data Store; return the key."""
    resolve_data_store(store).write_bytes(
        SCHEMA_DOC_KEY, schema_doc_path().read_bytes(), "text/markdown; charset=utf-8"
    )
    return SCHEMA_DOC_KEY
