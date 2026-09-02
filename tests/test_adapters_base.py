"""Tests for partner_scrape.adapters.base: the Adapter contract's
dispatch-by-adapter_type registry and the generic discover -> fetch ->
extract chaining logic in run().

These tests exercise the dispatch mechanism itself, independent of any
real adapter_type -- test_adapters_tec.py covers the concrete TEC
adapter's behavior. No test here opens a real network socket.
"""

from __future__ import annotations

import logging

import pytest

from partner_scrape.adapters.base import (
    ADAPTERS,
    DEFAULT_MAX_URLS_PER_SOURCE,
    EventRef,
    RawResponse,
    UnknownAdapterType,
    acquisition_kwargs,
    get_adapter,
    run,
)
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
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

    def fetch(self, ref, fetcher, source):
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


class _ConfigurableRefsFakeAdapter:
    """Adapter test double whose discover() returns ``REF_COUNT`` refs.

    ``REF_COUNT`` is a class attribute (matching ``_StaticFakeAdapter``'s
    own ``_REFS`` class-attribute convention above) so it can be set per
    test before registering this class in ``ADAPTERS`` -- ``get_adapter()``
    instantiates adapters with no constructor arguments, so per-instance
    configuration isn't available. One canned Event per ref, titled with
    the ref's own URL, so a test can also assert *which* refs survived a
    cap, not just how many.
    """

    REF_COUNT = 0

    def discover(self, source, fetcher):
        return [EventRef(url=f"https://example.org/page/{i}") for i in range(self.REF_COUNT)]

    def fetch(self, ref, fetcher, source):
        return RawResponse(ref=ref, status=200, body="")

    def extract(self, raw, source):
        return [Event(title=raw.ref.url)]


def _source_with_acquisition_policy(acquisition_policy: dict) -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="fake_test_type",
        config={},
        acquisition_policy=acquisition_policy,
    )


class TestMaxUrlsCap:
    """Per-source URL cap (registry/schema.py's ``max_urls`` default,
    consumed by ``run()`` above): one pathological source's ``discover()``
    output must never dominate a run's fetch count, and truncation must
    never be silent.
    """

    def test_source_with_more_refs_than_cap_fetches_only_the_cap(self, caplog):
        ADAPTERS["fake_test_type"] = _ConfigurableRefsFakeAdapter
        _ConfigurableRefsFakeAdapter.REF_COUNT = DEFAULT_MAX_URLS_PER_SOURCE + 50

        # No [acquisition_policy] override -- resolves to the package
        # default cap, same as a real TOML source with no [acquisition_
        # policy] section at all (registry/schema.py's own default-merge
        # behavior for max_urls).
        with caplog.at_level(logging.WARNING, logger="partner_scrape.adapters.base"):
            events = run(_source("fake_test_type"), _NullFetcher())

        assert len(events) == DEFAULT_MAX_URLS_PER_SOURCE
        # The cap keeps the *first* N refs, in discover()'s own order --
        # never an arbitrary subset.
        assert events[0].title == "https://example.org/page/0"
        assert events[-1].title == f"https://example.org/page/{DEFAULT_MAX_URLS_PER_SOURCE - 1}"

        # Truncation is never silent: the log names the source, how many
        # were discovered, the cap, and exactly how many were dropped.
        assert "fixture_org" in caplog.text
        assert str(DEFAULT_MAX_URLS_PER_SOURCE + 50) in caplog.text  # discovered
        assert f"cap of {DEFAULT_MAX_URLS_PER_SOURCE}" in caplog.text
        assert "dropping 50" in caplog.text

    def test_source_under_cap_is_unaffected_and_logs_nothing(self, caplog):
        ADAPTERS["fake_test_type"] = _ConfigurableRefsFakeAdapter
        _ConfigurableRefsFakeAdapter.REF_COUNT = 5

        with caplog.at_level(logging.WARNING, logger="partner_scrape.adapters.base"):
            events = run(_source("fake_test_type"), _NullFetcher())

        assert len(events) == 5
        assert caplog.text == ""

    def test_source_exactly_at_the_cap_is_not_truncated_or_logged(self, caplog):
        ADAPTERS["fake_test_type"] = _ConfigurableRefsFakeAdapter
        _ConfigurableRefsFakeAdapter.REF_COUNT = 7

        source = _source_with_acquisition_policy({"max_urls": 7})
        with caplog.at_level(logging.WARNING, logger="partner_scrape.adapters.base"):
            events = run(source, _NullFetcher())

        assert len(events) == 7
        assert caplog.text == ""

    def test_per_source_max_urls_override_is_respected(self):
        ADAPTERS["fake_test_type"] = _ConfigurableRefsFakeAdapter
        _ConfigurableRefsFakeAdapter.REF_COUNT = 10

        source = _source_with_acquisition_policy({"max_urls": 3})
        events = run(source, _NullFetcher())

        assert len(events) == 3
        assert [e.title for e in events] == [
            "https://example.org/page/0",
            "https://example.org/page/1",
            "https://example.org/page/2",
        ]

    def test_per_source_override_raising_the_cap_is_also_respected(self):
        # An override doesn't just lower the cap -- a source explicitly
        # configured with a *higher* max_urls than the package default
        # must be allowed to fetch more than DEFAULT_MAX_URLS_PER_SOURCE.
        ADAPTERS["fake_test_type"] = _ConfigurableRefsFakeAdapter
        _ConfigurableRefsFakeAdapter.REF_COUNT = DEFAULT_MAX_URLS_PER_SOURCE + 10

        source = _source_with_acquisition_policy(
            {"max_urls": DEFAULT_MAX_URLS_PER_SOURCE + 10}
        )
        events = run(source, _NullFetcher())

        assert len(events) == DEFAULT_MAX_URLS_PER_SOURCE + 10


class _ZeroRefsFakeAdapter:
    """Adapter test double whose ``discover()`` always returns zero refs --
    a generic (non-program-family) adapter type, used to prove
    ``run()``'s zero-discovered-refs warning (ticket 006 exception
    revision) fires for every adapter type, not only ``program_page``/
    ``program_listing``/``program_page_multi``.
    """

    def discover(self, source, fetcher):
        return []

    def fetch(self, ref, fetcher, source):
        raise AssertionError("fetch() should never be called when discover() found nothing")

    def extract(self, raw, source):
        raise AssertionError("extract() should never be called when discover() found nothing")


class TestZeroRefsWarning:
    """``run()`` logs a warning (never raises) when ``discover()`` returns
    zero refs for an enabled source -- sprint 027 ticket 006 exception
    revision, generic across every adapter type (§4 of
    ``adapters/DESIGN.md``'s Revision note).
    """

    def test_zero_refs_logs_a_warning_naming_source_and_adapter_type(self, caplog):
        ADAPTERS["fake_test_type"] = _ZeroRefsFakeAdapter

        with caplog.at_level(logging.WARNING, logger="partner_scrape.adapters.base"):
            events = run(_source("fake_test_type"), _NullFetcher())

        assert events == []
        assert "fixture_org" in caplog.text
        assert "fake_test_type" in caplog.text

    def test_zero_refs_does_not_raise(self):
        ADAPTERS["fake_test_type"] = _ZeroRefsFakeAdapter

        run(_source("fake_test_type"), _NullFetcher())  # must not raise

    def test_nonzero_refs_logs_no_zero_refs_warning(self, caplog):
        ADAPTERS["fake_test_type"] = _StaticFakeAdapter

        with caplog.at_level(logging.WARNING, logger="partner_scrape.adapters.base"):
            run(_source("fake_test_type"), _NullFetcher())

        assert "discovered 0 URL" not in caplog.text


class TestAcquisitionKwargs:
    """``acquisition_kwargs(source)`` -- sprint 015 ticket 003's helper
    that reads ``source.acquisition_policy`` into the two kwargs every
    ``fetcher.get()`` call site now spreads in. See this ticket for the
    ``PoliteFetcher.get()`` docstring precedent this helper finally
    implements.
    """

    def test_source_with_no_acquisition_policy_keys_resolves_to_polite_fetcher_defaults(self):
        # A directly-constructed SourceConfig (no from_toml merge) with
        # acquisition_policy={} -- the exact shape DEFAULT_MAX_URLS_PER_
        # SOURCE's own docstring calls out as this module's defensive
        # fallback case.
        source = _source_with_acquisition_policy({})

        kwargs = acquisition_kwargs(source)

        assert kwargs == {
            "rate_limit_seconds": DEFAULT_RATE_LIMIT_SECONDS,
            "respect_robots": True,
        }

    def test_explicit_override_of_both_keys_is_returned_verbatim(self):
        source = _source_with_acquisition_policy(
            {"rate_limit_seconds": 5.0, "respect_robots": False}
        )

        kwargs = acquisition_kwargs(source)

        assert kwargs == {"rate_limit_seconds": 5.0, "respect_robots": False}

    def test_leaguesync_toml_shaped_policy_yields_respect_robots_false(self):
        # Mirrors registry/sources/leaguesync.toml's real
        # [acquisition_policy] section verbatim -- this is the exact
        # shape that was previously dead config (see this ticket's
        # Description).
        source = _source_with_acquisition_policy(
            {
                "respect_robots": False,
                "rate_limit_seconds": 1.0,
                "discovered_via": "OOP build, 2026-07-20",
            }
        )

        kwargs = acquisition_kwargs(source)

        assert kwargs["respect_robots"] is False
        assert kwargs["rate_limit_seconds"] == 1.0


class TestRunThreadsSourceIntoFetch:
    """``run()`` passes ``source`` as ``fetch()``'s third positional
    argument (this ticket widened the ``Adapter.fetch()`` Protocol to
    match ``discover()``/``extract()``, which already received
    ``source`` -- see ``adapters/base.py``'s ``Adapter.fetch()``
    docstring) -- proven directly rather than only implied by every
    concrete adapter's own tests passing.
    """

    def test_fetch_receives_the_same_source_instance_run_was_called_with(self):
        received: list[SourceConfig] = []

        class _RecordingAdapter:
            def discover(self, source, fetcher):
                return [EventRef(url="https://example.org/only")]

            def fetch(self, ref, fetcher, source):
                received.append(source)
                return RawResponse(ref=ref, status=200, body="")

            def extract(self, raw, source):
                return []

        ADAPTERS["fake_test_type"] = _RecordingAdapter
        source = _source("fake_test_type")

        run(source, _NullFetcher())

        assert received == [source]
