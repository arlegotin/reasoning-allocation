from dataclasses import replace

import pytest

from ra.collect import label_leases, residual_administration
from ra.types import LeaseOutcome, NodeKey, ProgressRecord, SelectionBoundary


def lease(**changes):
    value = LeaseOutcome(NodeKey(1, 1), 1, 1, 0, 5, 20, 'node_limit', True, False, 0, 15, 0, 0,
                         snapshot_ns=2)
    return replace(value, **changes)


def test_interval_partition_and_only_dispatched_labels():
    result = label_leases([lease(), lease(dispatch_ns=None, body_ns=0)], [], 100, 100)
    assert len(result) == 1
    assert result[0]['admin_ns'] == 5
    assert result[0]['body_ns'] == 15
    assert result[0]['full_ns'] == 20
    assert result[0]['endpoint_gain'] == 0


def test_receipt_after_deadline_excluded_despite_local_progress():
    progress = [ProgressRecord('r', 1, 1, 1, 100, 0., 'anchor', True),
                ProgressRecord('r', 2, 8, 11, 50, 0., 'better', True)]
    result = label_leases([lease(end_reason='deadline', censored=True, natural_completion=False,
                                local_utility_end=.5)], progress, 10, 100)[0]
    assert result['endpoint_gain'] == 0
    assert result['completion_outcome_known'] is False
    assert result['natural_completion'] is None
    assert result['last_observation_sequence'] == 1
    assert result['full_ns'] == 20


def test_watchdog_is_lower_bound_and_not_completed_body_target():
    result = label_leases([lease(end_reason='watchdog', censored=True, natural_completion=False)], [], 100, 100)[0]
    assert result['duration_lower_bound'] is True
    assert result['body_fit_eligible'] is False
    assert result['body_ns'] == 15


def test_residual_empty_or_expired_administration():
    boundaries = [SelectionBoundary(20, 22, None, 25, 'residual', 'known', 'empty_tree'),
                  SelectionBoundary(25, 26, None, 30, 'residual', 'known', 'deadline')]
    assert residual_administration(boundaries) == 10


def test_lease_callbacks_preserve_immutable_aligned_metadata():
    from ra.leases import LeaseController
    from ra.types import Allocation
    events = []
    controller = LeaseController({NodeKey(1, 1): None}, on_dispatch=lambda o: events.append(('dispatch', o)),
                                 on_finish=lambda o: events.append(('finish', o)), retain_outcomes=False)
    allocation = Allocation(NodeKey(1, 1), 1, None, None, None, .85, 'policy')
    controller.begin(allocation, 0, metadata={'snapshot_ns': 2, 'trace_index': 0, 'pool_hash': 'pool'})
    controller.mark_dispatch(5)
    outcome = controller.finish(20, 'terminal')
    assert outcome.trace_index == 0 and outcome.snapshot_ns == 2
    assert outcome.selection_probability == .85 and outcome.admin_ns == 5 and outcome.full_ns == 20
    assert [kind for kind, _ in events] == ['dispatch', 'finish']
    assert controller.outcomes == []


def test_finalizer_retains_missing_outcome_as_watchdog_lower_bound(tmp_path):
    import json
    from types import SimpleNamespace
    import numpy as np
    from ra.collect import TraceWriter, finalize_trace
    from ra.config import load_feature_schema
    from ra.runner import _atomic_json
    from pathlib import Path
    schema = load_feature_schema(Path('configs/features.json'))
    writer = TraceWriter(tmp_path / 'trace', schema, max_decisions=2)
    allocation = {'root': {'epoch': 1, 'number': 1}, 'node_limit': 1, 'selection_probability': 1.,
                  'policy_state_hash': 'p', 'gain_prediction': None, 'seconds_prediction': None, 'seconds_q90': None}
    metadata = {'allocation': allocation, 'pool_ids': [allocation['root']], 'pool_hash': 'pool',
                'support_lengths': [1], 'support_hash': 'support', 'heuristic': [allocation['root'], 1]}
    writer.decision(np.zeros(192), metadata)
    writer.decision(np.zeros(192), metadata)  # No dispatch for second selected row.
    _atomic_json(tmp_path / 'trace/dispatch-000000.json', {'allocation': allocation, 'pool_hash': 'pool',
        'entry_ns': 0, 'snapshot_ns': 2, 'dispatch_ns': 5, 'local_utility_entry': 0.}, immutable=True)
    summary = finalize_trace(tmp_path, [], SimpleNamespace(deadline_ns=10, p0=100), 20, True, [], 'deadline', True)
    assert summary['labels'] == 1 and summary['unknown_dispatches'] == 1
    label = json.loads((tmp_path / 'trace/label-000000.json').read_text())
    assert label['work'] is None
    assert label['duration_lower_bound'] and not label['body_fit_eligible'] and not label['gain_fit_eligible']
    assert label['natural_completion'] is None and label['full_ns'] == 20
    assert not (tmp_path / 'trace/label-000001.json').exists()


def test_failed_dispatch_journal_does_not_create_negative_body_or_label():
    from ra.leases import LeaseController
    from ra.types import Allocation
    def fail(_):
        raise OSError('journal failed')
    controller = LeaseController({NodeKey(1, 1): None}, on_dispatch=fail)
    controller.begin(Allocation(NodeKey(1, 1), 1, None, None, None, 1., 'p'), 0)
    with pytest.raises(OSError):
        controller.mark_dispatch(5)
    outcome = controller.finish(0, 'callback_error')
    assert outcome.dispatch_ns is None and outcome.body_ns == 0
    assert label_leases([outcome], [], 100, 100) == []


def test_partial_recovery_counts_retained_trace_shards_without_fabricating_labels(tmp_path):
    import json
    from ra.runner import _read_attempt
    (tmp_path / 'bootstrap.json').write_text(json.dumps({'resources': {}, 'clock_aligned': False}))
    (tmp_path / 'trace').mkdir()
    (tmp_path / 'trace/selected-000000.npy').write_bytes(b'incomplete array evidence')
    recovered, final = _read_attempt(tmp_path)
    assert not final and recovered['duration_censored']
    assert recovered['resources']['trace_bytes'] == len(b'incomplete array evidence')
    assert not list((tmp_path / 'trace').glob('label-*'))


def test_expired_scoring_rebid_without_dispatched_lease_is_residual():
    boundaries = [SelectionBoundary(0, 2, 5, 7, 'rebid', 'known', None),
                  SelectionBoundary(20, 22, 29, 30, 'rebid', 'known', None)]
    # Second callback returns a legal native node solely to unwind an expired
    # scoring decision. It has no actual lease dispatch, so all10ns is residual.
    assert residual_administration(boundaries, dispatched_entries={0}) == 10
