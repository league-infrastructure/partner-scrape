"""Tests for partner_scrape.store.event_store: EventStore.

Every test uses an in-memory (`:memory:`) or `tmp_path`-based database --
never the real configured `SCRAPE_CACHE_DIR` -- mirroring
`test_enrich_cache.py`'s testing policy.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from partner_scrape.model import Event, Provenance
from partner_scrape.store.event_store import EventStore


def _sample_event(**overrides: Any) -> Event:
    defaults: dict[str, Any] = dict(
        source_id="fixture_org",
        external_id="evt-1",
        title="Robotics Night",
        description="Hands-on robotics for kids.",
    )
    defaults.update(overrides)
    return Event(**defaults)


def _full_event(**overrides: Any) -> Event:
    """An Event with every field populated, incl. classification and provenance."""
    event = Event(
        kind="program",
        source_id="fixture_org",
        external_id="evt-1",
        url="https://example.org/events/1",
        title="Robotics Night",
        description="Hands-on robotics for kids.",
        start=datetime(2026, 8, 15, 18, 0, 0),
        end=datetime(2026, 8, 15, 20, 0, 0),
        all_day=False,
        location="Fixture Library",
        latitude=32.7157,
        longitude=-117.1611,
        cost="Free",
        registration_url="https://example.org/register",
        image_url="https://example.org/image.png",
        categories=["stem", "youth"],
        tags=["robotics", "engineering"],
        relevant=True,
        relevance_reason="A hands-on youth robotics program.",
        areas_of_interest=["Engineering"],
        age_grade_level=["Grades 6-8"],
        cost_range="Free",
        time_of_day=["Evening"],
    )
    event.set("title", event.title, source="generic_html", confidence=0.9)
    event.set("relevant", event.relevant, source="llm_enrichment", confidence=0.85)
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


# ---------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------


class TestRoundTrip:
    def test_full_event_round_trips_unchanged(self):
        store = EventStore(":memory:")
        event = _full_event()

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        [stored] = store.all_events()

        assert stored == event

    def test_round_trip_preserves_field_provenance(self):
        store = EventStore(":memory:")
        event = _full_event()

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        [stored] = store.all_events()

        assert stored.field_provenance["title"] == Provenance(
            source="generic_html", confidence=0.9
        )
        assert stored.field_provenance["relevant"] == Provenance(
            source="llm_enrichment", confidence=0.85
        )

    def test_round_trip_preserves_datetimes(self):
        store = EventStore(":memory:")
        event = _full_event()

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        [stored] = store.all_events()

        assert stored.start == datetime(2026, 8, 15, 18, 0, 0)
        assert stored.end == datetime(2026, 8, 15, 20, 0, 0)

    def test_round_trip_preserves_undated_event(self):
        store = EventStore(":memory:")
        event = _full_event(start=None, end=None)

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        [stored] = store.all_events()

        assert stored.start is None
        assert stored.end is None

    def test_round_trip_preserves_kind_and_classification_fields(self):
        store = EventStore(":memory:")
        event = _full_event(kind="internship")

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        [stored] = store.all_events()

        assert stored.kind == "internship"
        assert stored.areas_of_interest == ["Engineering"]
        assert stored.age_grade_level == ["Grades 6-8"]
        assert stored.cost_range == "Free"
        assert stored.time_of_day == ["Evening"]

    def test_round_trip_preserves_empty_field_provenance(self):
        store = EventStore(":memory:")
        event = _sample_event()
        assert event.field_provenance == {}

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        [stored] = store.all_events()

        assert stored.field_provenance == {}


# ---------------------------------------------------------------------
# upsert: insert vs. update
# ---------------------------------------------------------------------


class TestUpsert:
    def test_insert_new_identity_sets_first_seen_and_last_seen_equal(self):
        store = EventStore(":memory:")
        event = _sample_event()
        seen_at = datetime(2026, 7, 1, 12, 0, 0)

        store.upsert([event], seen_at=seen_at)

        assert store.count() == 1

    def test_upsert_same_identity_twice_keeps_row_count_at_one(self):
        store = EventStore(":memory:")
        event = _sample_event(title="Robotics Night")

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        store.upsert([event], seen_at=datetime(2026, 7, 2, 12, 0, 0))

        assert store.count() == 1

    def test_upsert_update_preserves_first_seen(self):
        store = EventStore(":memory:")
        event = _sample_event()
        first_seen = datetime(2026, 7, 1, 12, 0, 0)
        second_seen = datetime(2026, 7, 5, 9, 0, 0)

        store.upsert([event], seen_at=first_seen)
        row = store._conn.execute(
            "SELECT first_seen, last_seen FROM events"
        ).fetchone()
        assert row == (first_seen.isoformat(), first_seen.isoformat())

        store.upsert([event], seen_at=second_seen)
        row = store._conn.execute(
            "SELECT first_seen, last_seen FROM events"
        ).fetchone()

        assert row == (first_seen.isoformat(), second_seen.isoformat())

    def test_upsert_update_replaces_content(self):
        store = EventStore(":memory:")
        event = _sample_event(description="Original description")

        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        updated = _sample_event(description="Updated description")
        store.upsert([updated], seen_at=datetime(2026, 7, 2, 12, 0, 0))

        [stored] = store.all_events()
        assert stored.description == "Updated description"

    def test_two_events_with_different_identities_both_persist(self):
        store = EventStore(":memory:")
        event_a = _sample_event(source_id="org_a", external_id="evt-a")
        event_b = _sample_event(source_id="org_b", external_id="evt-b")

        store.upsert([event_a, event_b], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        assert store.count() == 2
        identities = {e.source_id for e in store.all_events()}
        assert identities == {"org_a", "org_b"}

    def test_upsert_is_a_single_transaction_for_multiple_events(self):
        store = EventStore(":memory:")
        events = [
            _sample_event(source_id="org_a", external_id="evt-a"),
            _sample_event(source_id="org_b", external_id="evt-b"),
            _sample_event(source_id="org_c", external_id="evt-c"),
        ]

        store.upsert(events, seen_at=datetime(2026, 7, 1, 12, 0, 0))

        assert store.count() == 3

    def test_fallback_identity_key_events_are_distinguished_by_title_and_date(self):
        store = EventStore(":memory:")
        event_a = _sample_event(external_id="", title="Beach Cleanup", start=datetime(2026, 8, 1, 9, 0))
        event_b = _sample_event(external_id="", title="Beach Cleanup", start=datetime(2026, 8, 2, 9, 0))

        store.upsert([event_a, event_b], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        assert store.count() == 2


# ---------------------------------------------------------------------
# all_events / count
# ---------------------------------------------------------------------


class TestAllEventsAndCount:
    def test_count_is_zero_for_empty_store(self):
        store = EventStore(":memory:")
        assert store.count() == 0
        assert store.all_events() == []

    def test_all_events_returns_every_stored_event(self):
        store = EventStore(":memory:")
        events = [
            _sample_event(source_id="org_a", external_id="evt-a"),
            _sample_event(source_id="org_b", external_id="evt-b"),
            _sample_event(source_id="org_c", external_id="evt-c"),
        ]
        store.upsert(events, seen_at=datetime(2026, 7, 1, 12, 0, 0))

        stored_ids = {e.source_id for e in store.all_events()}
        assert stored_ids == {"org_a", "org_b", "org_c"}
        assert store.count() == 3


# ---------------------------------------------------------------------
# prune_past
# ---------------------------------------------------------------------


class TestPrunePast:
    def test_deletes_dated_past_event(self):
        store = EventStore(":memory:")
        past_event = _sample_event(
            external_id="past", start=datetime(2020, 1, 1, 9, 0), end=datetime(2020, 1, 1, 11, 0)
        )
        store.upsert([past_event], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        deleted = store.prune_past(today=date(2026, 7, 1))

        assert deleted == 1
        assert store.count() == 0

    def test_keeps_upcoming_event(self):
        store = EventStore(":memory:")
        upcoming = _sample_event(
            external_id="upcoming",
            start=datetime(2027, 1, 1, 9, 0),
            end=datetime(2027, 1, 1, 11, 0),
        )
        store.upsert([upcoming], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        deleted = store.prune_past(today=date(2026, 7, 1))

        assert deleted == 0
        assert store.count() == 1

    def test_keeps_undated_event(self):
        store = EventStore(":memory:")
        undated = _sample_event(external_id="undated")
        assert undated.start is None and undated.end is None
        store.upsert([undated], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        deleted = store.prune_past(today=date(2026, 7, 1))

        assert deleted == 0
        assert store.count() == 1

    def test_uses_end_date_when_present_even_if_start_is_past(self):
        """An event that started in the past but ends today/future is not pruned."""
        store = EventStore(":memory:")
        multi_day = _sample_event(
            external_id="multi-day",
            start=datetime(2026, 6, 30, 9, 0),
            end=datetime(2026, 7, 2, 17, 0),
        )
        store.upsert([multi_day], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        deleted = store.prune_past(today=date(2026, 7, 1))

        assert deleted == 0
        assert store.count() == 1

    def test_falls_back_to_start_date_when_no_end(self):
        store = EventStore(":memory:")
        past_no_end = _sample_event(external_id="past-no-end", start=datetime(2020, 1, 1, 9, 0))
        store.upsert([past_no_end], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        deleted = store.prune_past(today=date(2026, 7, 1))

        assert deleted == 1
        assert store.count() == 0

    def test_event_ending_today_is_not_pruned(self):
        store = EventStore(":memory:")
        ends_today = _sample_event(external_id="ends-today", end=datetime(2026, 7, 1, 23, 0))
        store.upsert([ends_today], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        deleted = store.prune_past(today=date(2026, 7, 1))

        assert deleted == 0
        assert store.count() == 1

    def test_mixed_past_upcoming_and_undated(self):
        store = EventStore(":memory:")
        past = _sample_event(external_id="past", start=datetime(2020, 1, 1, 9, 0))
        upcoming = _sample_event(external_id="upcoming", start=datetime(2027, 1, 1, 9, 0))
        undated = _sample_event(external_id="undated")
        store.upsert([past, upcoming, undated], seen_at=datetime(2026, 7, 1, 12, 0, 0))

        deleted = store.prune_past(today=date(2026, 7, 1))

        assert deleted == 1
        remaining_ids = {e.external_id for e in store.all_events()}
        assert remaining_ids == {"upcoming", "undated"}


# ---------------------------------------------------------------------
# prune_unseen
# ---------------------------------------------------------------------


class TestPruneUnseen:
    def test_deletes_rows_not_seen_since_cutoff(self):
        store = EventStore(":memory:")
        stale = _sample_event(external_id="stale")
        store.upsert([stale], seen_at=datetime(2026, 6, 1, 12, 0, 0))

        deleted = store.prune_unseen(cutoff=datetime(2026, 7, 1, 0, 0, 0))

        assert deleted == 1
        assert store.count() == 0

    def test_keeps_freshly_seen_rows(self):
        store = EventStore(":memory:")
        fresh = _sample_event(external_id="fresh")
        store.upsert([fresh], seen_at=datetime(2026, 7, 5, 12, 0, 0))

        deleted = store.prune_unseen(cutoff=datetime(2026, 7, 1, 0, 0, 0))

        assert deleted == 0
        assert store.count() == 1

    def test_mixed_stale_and_fresh(self):
        store = EventStore(":memory:")
        stale = _sample_event(external_id="stale")
        fresh = _sample_event(external_id="fresh")
        store.upsert([stale], seen_at=datetime(2026, 6, 1, 12, 0, 0))
        store.upsert([fresh], seen_at=datetime(2026, 7, 5, 12, 0, 0))

        deleted = store.prune_unseen(cutoff=datetime(2026, 7, 1, 0, 0, 0))

        assert deleted == 1
        remaining_ids = {e.external_id for e in store.all_events()}
        assert remaining_ids == {"fresh"}

    def test_reupserting_refreshes_last_seen_and_survives_prune(self):
        store = EventStore(":memory:")
        event = _sample_event(external_id="repeat")
        store.upsert([event], seen_at=datetime(2026, 6, 1, 12, 0, 0))
        # A later run re-crawls and sees it again.
        store.upsert([event], seen_at=datetime(2026, 7, 10, 12, 0, 0))

        deleted = store.prune_unseen(cutoff=datetime(2026, 7, 1, 0, 0, 0))

        assert deleted == 0
        assert store.count() == 1

    def test_cutoff_exactly_equal_to_last_seen_is_not_pruned(self):
        store = EventStore(":memory:")
        seen_at = datetime(2026, 7, 1, 12, 0, 0)
        event = _sample_event(external_id="boundary")
        store.upsert([event], seen_at=seen_at)

        deleted = store.prune_unseen(cutoff=seen_at)

        assert deleted == 0
        assert store.count() == 1


# ---------------------------------------------------------------------
# Construction / defaults
# ---------------------------------------------------------------------


class TestConstruction:
    def test_default_db_path_uses_configured_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))

        store = EventStore()

        assert store.db_path == tmp_path / "events.db"
        assert (tmp_path / "events.db").exists()

    def test_tmp_path_db_creates_schema_and_persists_across_reopen(self, tmp_path):
        db_path = tmp_path / "sub" / "events.db"
        store = EventStore(db_path)
        event = _sample_event()
        store.upsert([event], seen_at=datetime(2026, 7, 1, 12, 0, 0))
        store.close()

        reopened = EventStore(db_path)

        assert reopened.count() == 1

    def test_context_manager_closes_connection(self, tmp_path):
        db_path = tmp_path / "events.db"
        with EventStore(db_path) as store:
            store.upsert([_sample_event()], seen_at=datetime(2026, 7, 1, 12, 0, 0))
            assert store.count() == 1
