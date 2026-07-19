"""Tests for partner_scrape.adapters.base: the Adapter contract's
dispatch-by-adapter_type registry and the generic discover -> fetch ->
extract chaining logic in run().

These tests exercise the dispatch mechanism itself, independent of any
real adapter_type -- test_adapters_tec.py covers the concrete TEC
adapter's behavior. No test here opens a real network socket.
"""

from __future__ import annotations

import pytest

from partner_scrape.adapters.base import (
    ADAPTERS,
    EventRef,
    RawResponse,
    UnknownAdapterType,
    get_adapter,
    run,
)
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig


@pytest.fixture(autouse=True)
def _restore_adapters_registry():
    """Snapshot/restore ADAPTERS around every test.

    Several tests register a throwaway ``fake_test_type`` entry to
    exercise dispatch without depending on a real adapter -- this keeps
    that registration from leaking into other test modules (e.g. one
    that asserts the exact set of known adapter types).
    """
    original = dict(ADAPTERS)
    yield
    ADAPTERS.clear()
    ADAPTERS.update(original)


class _NullFetcher:
    """A Fetcher that fails the test if anything actually calls it.

    _StaticFakeAdapter below never delegates to the fetcher it's given
    (its fetch() returns a canned RawResponse), so any call here would
    indicate run() is doing something other than passing the fetcher
    through unused.
    """

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        raise AssertionError(f"fetcher.get() should not be called directly: {url}")


class _StaticFakeAdapter:
    """Adapter test double with hard-coded discover/fetch/extract behavior.

    Used to test run()'s generic chaining across multiple EventRefs
    without depending on any real adapter_type's fetch/parse logic.
    """

    _REFS = [EventRef(url="https://example.org/page/1"), EventRef(url="https://example.org/page/2")]
    _EVENTS_BY_URL = {
        "https://example.org/page/1": [Event(title="Event A")],
        "https://example.org/page/2": [Event(title="Event B"), Event(title="Event C")],
    }

    def discover(self, source, fetcher):
        return self._REFS

    def fetch(self, ref, fetcher):
        return RawResponse(ref=ref, status=200, body="")

    def extract(self, raw, source):
        return self._EVENTS_BY_URL[raw.ref.url]


def _source(adapter_type: str) -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org", org_name="Fixture Org", adapter_type=adapter_type, config={}
    )


class TestDispatchRegistry:
    def test_unknown_adapter_type_raises_clear_error(self):
        with pytest.raises(UnknownAdapterType, match="nope_not_a_type"):
            get_adapter("nope_not_a_type")

    def test_registering_a_new_adapter_type_is_a_one_line_dict_entry(self):
        ADAPTERS["fake_test_type"] = _StaticFakeAdapter

        adapter = get_adapter("fake_test_type")

        assert isinstance(adapter, _StaticFakeAdapter)

    def test_get_adapter_returns_a_fresh_instance_each_call(self):
        ADAPTERS["fake_test_type"] = _StaticFakeAdapter

        first = get_adapter("fake_test_type")
        second = get_adapter("fake_test_type")

        assert first is not second


class TestRunChaining:
    def test_run_chains_discover_fetch_extract_and_concatenates_events_in_order(self):
        ADAPTERS["fake_test_type"] = _StaticFakeAdapter

        events = run(_source("fake_test_type"), _NullFetcher())

        assert [e.title for e in events] == ["Event A", "Event B", "Event C"]

    def test_run_raises_for_an_unregistered_adapter_type(self):
        with pytest.raises(UnknownAdapterType):
            run(_source("totally_unregistered_type"), _NullFetcher())


class TestTecRestIsRegistered:
    def test_importing_the_adapters_package_registers_tec_rest(self):
        import partner_scrape.adapters as adapters_pkg

        assert adapters_pkg.ADAPTERS["tec_rest"] is adapters_pkg.TecRestAdapter
