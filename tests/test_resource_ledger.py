"""Exclusive elapsed accounting and independent overlapping resource costs."""
import pytest

from ra import ledger
from ra.runner import run_request
from test_worker import cold_request


def test_nested_diagnostics_do_not_add_to_exclusive_worker_elapsed():
    clock = ledger.TimeLedger(100)
    clock.enter('startup', 110)
    clock.enter('administration', 120)
    clock.enter('diagnostic:inference', 130)
    clock.leave(150)
    clock.leave(160)
    clock.leave(170)
    totals = clock.summary(200)
    assert totals == {'startup': 20, 'native': 0, 'administration': 40,
                      'observation': 0, 'finalization': 0, 'residual': 40}
    assert sum(totals.values()) == 100
    assert clock.diagnostics == {'inference': 20}


def test_nested_observation_is_excluded_from_native_and_administration():
    clock = ledger.TimeLedger(0)
    clock.enter('native', 0)
    clock.enter('administration', 10)
    clock.enter('observation', 20)
    clock.leave(30)
    clock.leave(40)
    clock.leave(50)
    assert clock.summary(60) == {'startup': 0, 'native': 20, 'administration': 20,
                                 'observation': 10, 'finalization': 0, 'residual': 10}
    with pytest.raises(ValueError):
        clock.enter('native', 49)
    with pytest.raises(ValueError):
        clock.enter('invented', 60)


def test_cold_resources_reconcile_without_adding_parent_overlap(cold_request, tmp_path):
    result = run_request(cold_request, tmp_path / 'attempt')
    r, t = result.resources, result.timestamps
    assert r['timing_partition_complete']
    assert sum(r['worker_exclusive_ns'].values()) == t['worker_release_ns'] - t['worker_entry_ns']
    assert sum(r['elapsed_partition_ns'].values()) == r['end_to_end_ns']
    assert r['end_to_end_ns'] == t['parent_finalize_ns'] - t['launch_ns']
    assert r['worker_exclusive_ns']['observation'] > 0
    assert r['worker_exclusive_ns']['native'] > 0
    assert r['parent_sampling_ns'] > 0
    assert r['parent_observation_ns_overlapping_worker'] > 0
    assert r['worker_sampled_peak_rss_bytes'] > 0
    assert r['worker_sampled_cpu_ns_lower_bound'] > 0
    assert r['resource_release_confirmed'] is True
    assert r['timer_resolution_ns'] >= 1


def test_progress_callback_cost_belongs_to_mandatory_observation():
    from ra.scip_backend import _contain_callback
    clock = ledger.TimeLedger(0)
    class Backend:
        time_ledger = clock
    class ProgressCallback:
        timing_category = 'observation'
        backend = Backend()
        @_contain_callback
        def eventexec(self):
            sum(range(100))
    ProgressCallback().eventexec()
    import time
    totals = clock.summary(time.perf_counter_ns())
    assert totals['observation'] > 0
    assert totals['administration'] == 0
