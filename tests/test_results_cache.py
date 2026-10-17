"""Tests for odatix.lib.results_cache (write-back cache in front of the results files)."""

import os

import pytest

import odatix.lib.results_cache as cache
import odatix.lib.results_schema as schema


@pytest.fixture(autouse=True)
def clean_cache():
    cache.invalidate()
    yield
    cache.invalidate()


@pytest.fixture
def results_path(tmp_path):
    return str(tmp_path / "results_dummy.yml")


def record(configuration, step="synth", fmax=100):
    return schema.make_record(
        {
            "type": "fmax_synthesis",
            "tool": "dummy",
            "flow": "standard",
            "step": step,
            "target": "target",
            "architecture": "arch",
            "configuration": configuration,
        },
        {"Fmax": fmax},
    )


def on_disk(path):
    return schema.load_results_file(path).records


######################################
# Write-through (the default)
######################################

class TestWriteThrough:
    def test_a_missing_file_loads_empty(self, results_path):
        assert cache.load(results_path) == ({}, [])

    def test_a_store_hits_the_disk_right_away(self, results_path):
        cache.store(results_path, {"Fmax": "MHz"}, [record("c0")])
        assert len(on_disk(results_path)) == 1

    def test_a_reload_gives_back_what_was_stored(self, results_path):
        cache.store(results_path, {"Fmax": "MHz"}, [record("c0")])
        units, records = cache.load(results_path)
        assert units == {"Fmax": "MHz"}
        assert len(records) == 1

    def test_an_unparsable_file_starts_over(self, results_path):
        with open(results_path, "w") as file:
            file.write("results: [oops\n")
        assert cache.load(results_path) == ({}, [])


######################################
# Staleness
######################################

class TestStaleness:
    def test_a_write_behind_the_cache_back_is_picked_up(self, results_path):
        cache.store(results_path, {}, [record("c0")])
        schema.dump_results_file(results_path, {}, [record("cX"), record("cY")])
        _, records = cache.load(results_path)
        assert len(records) == 2

    def test_a_deleted_file_is_picked_up(self, results_path):
        cache.store(results_path, {}, [record("c0")])
        os.remove(results_path)
        assert cache.load(results_path) == ({}, [])

    def test_invalidate_drops_pending_content(self, results_path):
        cache.store(results_path, {}, [record("c0")])
        with cache.deferred_writes(interval=1000.0):
            cache.store(results_path, {}, [record("c0"), record("c1")])
            cache.invalidate(results_path)
        assert len(on_disk(results_path)) == 1


######################################
# Deferred writes
######################################

class TestDeferredWrites:
    def test_a_burst_is_coalesced(self, results_path):
        with cache.deferred_writes(interval=1000.0):
            for i in range(10):
                units, records = cache.load(results_path)
                cache.store(results_path, units, schema.upsert_records(records, [record("c%d" % i)]))
            # The first store of the burst has nothing to coalesce with, the
            # nine others are still only in memory.
            assert len(on_disk(results_path)) == 1
            cache.flush()
            assert len(on_disk(results_path)) == 10

    def test_leaving_the_block_flushes(self, results_path):
        with cache.deferred_writes(interval=1000.0):
            cache.store(results_path, {}, [record("c0")])
            cache.store(results_path, {}, [record("c0"), record("c1")])
            assert len(on_disk(results_path)) == 1
        assert len(on_disk(results_path)) == 2

    def test_an_elapsed_interval_lets_the_next_store_through(self, results_path):
        with cache.deferred_writes(interval=0.0):
            cache.store(results_path, {}, [record("c0")])
            cache.store(results_path, {}, [record("c0"), record("c1")])
            assert len(on_disk(results_path)) == 2

    def test_flush_due_keeps_a_fresh_write_pending(self, results_path):
        with cache.deferred_writes(interval=1000.0):
            cache.store(results_path, {}, [record("c0")])
            cache.store(results_path, {}, [record("c0"), record("c1")])
            cache.flush_due()
            assert len(on_disk(results_path)) == 1

    def test_deferral_does_not_leak_out_of_the_block(self, results_path):
        with cache.deferred_writes(interval=1000.0):
            pass
        cache.store(results_path, {}, [record("c0")])
        cache.store(results_path, {}, [record("c0"), record("c1")])
        assert len(on_disk(results_path)) == 2

    def test_no_temporary_file_is_left_behind(self, tmp_path, results_path):
        with cache.deferred_writes(interval=0.0):
            for i in range(5):
                cache.store(results_path, {}, [record("c%d" % i)])
        assert [name for name in os.listdir(str(tmp_path)) if ".tmp." in name] == []
