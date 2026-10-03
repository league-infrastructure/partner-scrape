"""Schema doc publication (sprint 038, ticket 009)."""

from __future__ import annotations

from pathlib import Path

import tomllib

from partner_scrape.export import schema_doc
from partner_scrape.export.schema_doc import SCHEMA_DOC_KEY, publish_schema_doc
from partner_scrape.storage import LocalStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DOC = REPO_ROOT / "docs" / "data-schema.md"


def test_source_doc_lives_in_docs_and_data_is_untracked():
    assert SOURCE_DOC.is_file()
    assert "and it is committed to git" not in SOURCE_DOC.read_text(encoding="utf-8")
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    # Anchored: an unanchored "data/" also ignores partner_scrape/*/data/, and
    # hatchling honours .gitignore, silently dropping those from the wheel.
    assert "/data/" in ignore
    assert "data/" not in ignore


def test_wheel_force_includes_the_schema_doc():
    cfg = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    force = cfg["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force == {"docs/data-schema.md": "partner_scrape/data-schema.md"}


def test_publish_writes_schema_md_through_the_store(tmp_path):
    store = LocalStore(tmp_path)
    assert publish_schema_doc(store) == SCHEMA_DOC_KEY == "SCHEMA.md"
    assert (tmp_path / "SCHEMA.md").read_bytes() == SOURCE_DOC.read_bytes()


def test_bundled_copy_is_preferred_when_present(tmp_path, monkeypatch):
    bundled = tmp_path / "data-schema.md"
    bundled.write_text("bundled", encoding="utf-8")
    monkeypatch.setattr(schema_doc, "_BUNDLED", bundled)
    out = tmp_path / "out"
    publish_schema_doc(LocalStore(out))
    assert (out / "SCHEMA.md").read_text(encoding="utf-8") == "bundled"
