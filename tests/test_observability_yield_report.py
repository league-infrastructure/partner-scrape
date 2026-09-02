"""Pure unit tests for `partner_scrape.observability.yield_report`
(ticket 004-002): found/dated/new/dropped computation against a known
previous snapshot, zero-yield/cliff alert firing (and not firing), a
source's error being distinguishable from a clean zero-yield source,
and a first-ever run producing no alerts. No file I/O anywhere in this
file -- `compute_yield_report` is pure data-in, data-out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from partner_scrape.model import Event
from partner_scrape.observability.yield_report import (
    CLIFF_DROP_THRESHOLD,
    REGIONS_SNAPSHOT_KEY,
    SourceRecord,
    compute_yield_report,
)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


@dataclass
class FakeOpportunity:
    """A minimal stand-in for `normalize.run.Opportunity` -- only
    ``.slug``/``.sources``/``.region`` matter to this module's
    comparison logic (duck-typed, matching
    `pipeline.Reporter.record_opportunities`'s own `list[Any]`
    signature), so a full `Opportunity` is unnecessary. ``region``
    defaults to ``""`` (unclassified), matching `Opportunity.region`'s
    own default (sprint 033, issue 34) -- every pre-sprint-033 test
    fixture that omits it is unaffected."""

    slug: str
    sources: frozenset[str]
    region: str = ""


def _event(start: datetime | None = None) -> Event:
    return Event(title="Some Event", start=start)


class TestFoundDatedComputation:
    def test_found_is_the_raw_event_count(self):
        record = SourceRecord("acme", "Acme Org", [_event(), _event(), _event()])

        report = compute_yield_report([record], [], {}, now=NOW)

        [source] = report.sources
        assert source.found == 3

    def test_dated_counts_only_events_with_a_start(self):
        events = [
            _event(start=datetime(2026, 8, 1)),
            _event(start=datetime(2026, 8, 2)),
            _event(start=None),
        ]
        record = SourceRecord("acme", "Acme Org", events)

        report = compute_yield_report([record], [], {}, now=NOW)

        [source] = report.sources
        assert source.dated == 2

    def test_a_source_with_zero_events_reports_zero_found_and_dated(self):
        record = SourceRecord("acme", "Acme Org", [])

        report = compute_yield_report([record], [], {}, now=NOW)

        [source] = report.sources
        assert source.found == 0
        assert source.dated == 0


class TestNewAndDroppedComputation:
    def test_new_and_dropped_computed_against_the_previous_slug_set(self):
        record = SourceRecord("acme", "Acme Org", [_event()])
        opportunities = [
            FakeOpportunity(slug="event-a", sources=frozenset({"acme"})),
            FakeOpportunity(slug="event-b", sources=frozenset({"acme"})),
        ]
        # Previously acme contributed event-a and event-c; this run it
        # contributes event-a and event-b -- event-b is new, event-c
        # dropped.
        previous_snapshot = {"acme": {"found": 2, "slugs": ["event-a", "event-c"]}}

        report = compute_yield_report([record], opportunities, previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.new == 1
        assert source.dropped == 1

    def test_only_opportunities_attributed_to_this_source_are_counted(self):
        record = SourceRecord("acme", "Acme Org", [_event()])
        opportunities = [
            FakeOpportunity(slug="event-a", sources=frozenset({"acme"})),
            FakeOpportunity(slug="other-org-event", sources=frozenset({"otherorg"})),
        ]

        report = compute_yield_report([record], opportunities, {}, now=NOW)

        [source] = report.sources
        assert source.new == 1
        assert source.slugs == frozenset({"event-a"})

    def test_first_ever_run_treats_every_current_slug_as_new_none_dropped(self):
        record = SourceRecord("acme", "Acme Org", [_event()])
        opportunities = [FakeOpportunity(slug="event-a", sources=frozenset({"acme"}))]

        report = compute_yield_report([record], opportunities, {}, now=NOW)

        [source] = report.sources
        assert source.new == 1
        assert source.dropped == 0


class TestDeltaComputation:
    def test_delta_is_this_run_found_minus_previous_found(self):
        record = SourceRecord("acme", "Acme Org", [_event(), _event()])
        previous_snapshot = {"acme": {"found": 5, "slugs": []}}

        report = compute_yield_report([record], [], previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.previous_found == 5
        assert source.delta == 2 - 5

    def test_delta_and_previous_found_are_none_with_no_prior_snapshot_entry(self):
        record = SourceRecord("acme", "Acme Org", [_event()])

        report = compute_yield_report([record], [], {}, now=NOW)

        [source] = report.sources
        assert source.previous_found is None
        assert source.delta is None


class TestZeroYieldAlert:
    def test_fires_when_a_previously_productive_source_returns_nothing(self):
        record = SourceRecord("fleet", "Fleet Science Center", [])
        previous_snapshot = {"fleet": {"found": 12, "slugs": ["a", "b"]}}

        report = compute_yield_report([record], [], previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.zero_yield is True

    def test_does_not_fire_without_a_previous_snapshot_entry_for_the_source(self):
        # First-ever run for this source_id -- an expected baseline,
        # never an alert.
        record = SourceRecord("newsource", "New Org", [])

        report = compute_yield_report([record], [], {}, now=NOW)

        [source] = report.sources
        assert source.zero_yield is False

    def test_does_not_fire_when_the_previous_run_was_already_zero(self):
        record = SourceRecord("alwaysempty", "Org", [])
        previous_snapshot = {"alwaysempty": {"found": 0, "slugs": []}}

        report = compute_yield_report([record], [], previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.zero_yield is False

    def test_does_not_fire_when_the_source_still_finds_events(self):
        record = SourceRecord("fleet", "Fleet Science Center", [_event()])
        previous_snapshot = {"fleet": {"found": 12, "slugs": []}}

        report = compute_yield_report([record], [], previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.zero_yield is False


class TestCliffAlert:
    def test_fires_on_a_drop_past_the_threshold(self):
        # previous 10, now 4 -> 60% drop, past the 50% threshold.
        record = SourceRecord("acme", "Acme", [_event() for _ in range(4)])
        previous_snapshot = {"acme": {"found": 10, "slugs": []}}

        report = compute_yield_report([record], [], previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.cliff is True

    def test_does_not_fire_exactly_at_the_threshold(self):
        # previous 10, now 5 -> exactly 50% drop, at (not past) threshold.
        record = SourceRecord("acme", "Acme", [_event() for _ in range(5)])
        previous_snapshot = {"acme": {"found": 10, "slugs": []}}

        report = compute_yield_report([record], [], previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.cliff is False

    def test_does_not_fire_on_a_small_drop(self):
        # previous 10, now 9 -> 10% drop.
        record = SourceRecord("acme", "Acme", [_event() for _ in range(9)])
        previous_snapshot = {"acme": {"found": 10, "slugs": []}}

        report = compute_yield_report([record], [], previous_snapshot, now=NOW)

        [source] = report.sources
        assert source.cliff is False

    def test_does_not_fire_without_a_previous_snapshot_entry(self):
        record = SourceRecord("acme", "Acme", [_event()])

        report = compute_yield_report([record], [], {}, now=NOW)

        [source] = report.sources
        assert source.cliff is False

    def test_threshold_is_a_named_constant_not_a_magic_number(self):
        assert CLIFF_DROP_THRESHOLD == 0.5


class TestFirstEverRun:
    def test_no_previous_snapshot_produces_no_alerts_for_any_source(self):
        records = [
            SourceRecord("acme", "Acme", []),
            SourceRecord("beta", "Beta", [_event(), _event()]),
        ]

        report = compute_yield_report(records, [], {}, now=NOW)

        assert all(not source.zero_yield and not source.cliff for source in report.sources)
        assert report.alerts == []


class TestRegionTallying:
    """Sprint 033, issue 34: `RegionYield` mirrors `SourceYield`'s
    first-run-baseline/delta/zero-flag shape, but tallies the final
    `Opportunity` list by `.region` rather than per-source raw events."""

    def test_counts_opportunities_by_region(self):
        opportunities = [
            FakeOpportunity(slug="a", sources=frozenset({"acme"}), region="South Bay"),
            FakeOpportunity(slug="b", sources=frozenset({"acme"}), region="South Bay"),
            FakeOpportunity(slug="c", sources=frozenset({"acme"}), region="East County"),
        ]

        report = compute_yield_report([], opportunities, {}, now=NOW)

        by_region = {r.region: r.count for r in report.regions}
        assert by_region["South Bay"] == 2
        assert by_region["East County"] == 1

    def test_empty_region_is_bucketed_as_unclassified_not_dropped(self):
        opportunities = [
            FakeOpportunity(slug="a", sources=frozenset({"acme"}), region=""),
        ]

        report = compute_yield_report([], opportunities, {}, now=NOW)

        by_region = {r.region: r.count for r in report.regions}
        assert by_region["unclassified"] == 1

    def test_unclassified_entry_always_present_even_with_zero_unclassified_records(self):
        opportunities = [
            FakeOpportunity(slug="a", sources=frozenset({"acme"}), region="South Bay"),
        ]

        report = compute_yield_report([], opportunities, {}, now=NOW)

        by_region = {r.region: r.count for r in report.regions}
        assert by_region["unclassified"] == 0

    def test_regions_from_opportunities_without_the_region_attribute_default_to_unclassified(
        self,
    ):
        # Duck-typed via getattr, mirroring .slug/.sources -- an object
        # with no .region attribute at all (e.g. a pre-sprint-033 fixture
        # in some other test module) reads as unclassified, not an error.
        @dataclass
        class LegacyFakeOpportunity:
            slug: str
            sources: frozenset[str]

        opportunities = [LegacyFakeOpportunity(slug="a", sources=frozenset({"acme"}))]

        report = compute_yield_report([], opportunities, {}, now=NOW)

        by_region = {r.region: r.count for r in report.regions}
        assert by_region["unclassified"] == 1

    def test_regions_appear_in_first_encountered_order_unclassified_last(self):
        opportunities = [
            FakeOpportunity(slug="a", sources=frozenset(), region=""),
            FakeOpportunity(slug="b", sources=frozenset(), region="East County"),
            FakeOpportunity(slug="c", sources=frozenset(), region="South Bay"),
            FakeOpportunity(slug="d", sources=frozenset(), region="East County"),
        ]

        report = compute_yield_report([], opportunities, {}, now=NOW)

        assert [r.region for r in report.regions] == [
            "East County",
            "South Bay",
            "unclassified",
        ]


class TestRegionDeltaComputation:
    def test_delta_is_this_run_count_minus_previous_count(self):
        opportunities = [
            FakeOpportunity(slug="a", sources=frozenset(), region="South Bay"),
            FakeOpportunity(slug="b", sources=frozenset(), region="South Bay"),
        ]
        previous_snapshot = {REGIONS_SNAPSHOT_KEY: {"South Bay": {"count": 8}}}

        report = compute_yield_report([], opportunities, previous_snapshot, now=NOW)

        south_bay = next(r for r in report.regions if r.region == "South Bay")
        assert south_bay.previous_count == 8
        assert south_bay.delta == 2 - 8

    def test_previous_count_and_delta_are_none_with_no_prior_snapshot_entry(self):
        opportunities = [FakeOpportunity(slug="a", sources=frozenset(), region="South Bay")]

        report = compute_yield_report([], opportunities, {}, now=NOW)

        south_bay = next(r for r in report.regions if r.region == "South Bay")
        assert south_bay.previous_count is None
        assert south_bay.delta is None

    def test_a_region_absent_from_this_run_but_present_in_the_previous_snapshot_still_gets_an_entry(
        self,
    ):
        # The exact regression signal this measurement exists to catch:
        # East County had 8 last run, 0 (i.e. no opportunities at all)
        # this run.
        previous_snapshot = {REGIONS_SNAPSHOT_KEY: {"East County": {"count": 8}}}

        report = compute_yield_report([], [], previous_snapshot, now=NOW)

        east_county = next(r for r in report.regions if r.region == "East County")
        assert east_county.count == 0
        assert east_county.previous_count == 8
        assert east_county.delta == -8


class TestRegionZeroFlag:
    def test_fires_when_a_previously_populated_region_has_zero_this_run(self):
        previous_snapshot = {REGIONS_SNAPSHOT_KEY: {"East County": {"count": 8}}}

        report = compute_yield_report([], [], previous_snapshot, now=NOW)

        east_county = next(r for r in report.regions if r.region == "East County")
        assert east_county.zero is True

    def test_does_not_fire_without_a_previous_snapshot_entry_for_the_region(self):
        opportunities = [FakeOpportunity(slug="a", sources=frozenset(), region="South Bay")]

        report = compute_yield_report([], [], {}, now=NOW)

        # South Bay never appears (no opportunities this run, no prior
        # baseline) -- first-ever run for every region is not itself an
        # alert.
        assert all(not r.zero for r in report.regions)

    def test_does_not_fire_when_the_previous_run_was_already_zero(self):
        previous_snapshot = {REGIONS_SNAPSHOT_KEY: {"East County": {"count": 0}}}

        report = compute_yield_report([], [], previous_snapshot, now=NOW)

        east_county = next(r for r in report.regions if r.region == "East County")
        assert east_county.zero is False

    def test_does_not_fire_when_the_region_still_has_records(self):
        opportunities = [
            FakeOpportunity(slug="a", sources=frozenset(), region="South Bay"),
        ]
        previous_snapshot = {REGIONS_SNAPSHOT_KEY: {"South Bay": {"count": 8}}}

        report = compute_yield_report([], opportunities, previous_snapshot, now=NOW)

        south_bay = next(r for r in report.regions if r.region == "South Bay")
        assert south_bay.zero is False


class TestErrorDistinguishability:
    def test_an_errored_source_is_distinguishable_from_a_clean_zero_yield_source(self):
        error = RuntimeError("adapter exploded")
        broken = SourceRecord("broken", "Broken Org", [], error=error)
        clean = SourceRecord("clean", "Clean Org", [])

        report = compute_yield_report([broken, clean], [], {}, now=NOW)

        by_id = {source.source_id: source for source in report.sources}
        assert by_id["broken"].error is error
        assert by_id["broken"].found == 0
        assert by_id["clean"].error is None
        assert by_id["clean"].found == 0
