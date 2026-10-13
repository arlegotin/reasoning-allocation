"""Leases charge observed distinct completions, never selector invocations."""
from dataclasses import FrozenInstanceError
from dataclasses import asdict
import time

import pytest

from ra.leases import LeaseController
from ra.types import Allocation, NodeKey, NodeRecord


def record(number, parent=None, depth=0, estimate=0., bound=0., epoch=0):
    return NodeRecord(NodeKey(epoch, number), parent, depth, bound, estimate, 0, '', 'leaf')


def allocation(root=NodeKey(0, 1), length=2):
    return Allocation(root, length, 0., 0., None, None, '')


def test_root_first_descendant_order_and_distinct_completed_work():
    root, child, deep, unrelated = record(1), record(2, NodeKey(0, 1), 1), record(3, NodeKey(0, 2), 2), record(4)
    parents = {n.key: n.parent for n in (root, child, deep, unrelated)}
    lease = LeaseController(parents)
    lease.begin(allocation(), 10)
    assert lease.next_node([deep, unrelated, root, child], 11) == root.key
    assert lease.next_node([deep, root, child], 12) == root.key
    assert lease.ledger.snapshot() == {'available': 0, 'reserved': 2, 'spent': 0}
    lease.on_completed(root.key)
    lease.on_completed(root.key)
    assert lease.next_node([child, unrelated, deep], 13) == deep.key
    lease.on_completed(deep.key)
    assert lease.next_node([child, unrelated], 14) is None
    outcome = lease.finish(15, 'terminal')
    assert (outcome.root, outcome.node_limit, outcome.work, outcome.end_reason) == (root.key, 2, 2, 'node_limit')
    assert lease.ledger.snapshot() == {'available': 0, 'reserved': 0, 'spent': 2}
    assert lease.finish(20, 'ignored') == outcome
    with pytest.raises(FrozenInstanceError):
        outcome.work = 9


def test_continuation_uses_estimate_bound_number_ties():
    parents = {NodeKey(0, 1): None}
    nodes = [record(5, NodeKey(0, 1), 1, 2., 1.), record(4, NodeKey(0, 1), 1, 1., 2.),
             record(3, NodeKey(0, 1), 1, 1., 1.), record(2, NodeKey(0, 1), 1, 1., 1.)]
    parents.update({n.key: n.parent for n in nodes})
    lease = LeaseController(parents)
    lease.begin(allocation(length=8), 10)
    lease.next_node([record(1)], 11)
    lease.on_completed(NodeKey(0, 1))
    assert lease.next_node(nodes, 12) == NodeKey(0, 2)


@pytest.mark.parametrize('frontier', [[], [record(9)]])
def test_exhaustion_returns_unused_once_and_never_selects_unrelated(frontier):
    lease = LeaseController({NodeKey(0, 1): None, NodeKey(0, 9): None})
    lease.begin(allocation(), 10)
    lease.next_node([record(1)], 11)
    lease.on_completed(NodeKey(0, 1))
    assert lease.next_node(frontier, 12) is None
    lease.cancel('again')
    assert lease.ledger.snapshot() == {'available': 1, 'reserved': 0, 'spent': 1}
    assert lease.finish(13, 'terminal').natural_completion is True


@pytest.mark.parametrize('reason', ['restart', 'ancestor_deleted', 'cancelled'])
def test_cancel_lineage_cannot_spend(reason):
    lease = LeaseController({NodeKey(0, 1): None})
    lease.begin(allocation(), 10)
    lease.cancel(reason)
    lease.on_completed(NodeKey(0, 1))
    assert lease.ledger.snapshot() == {'available': 2, 'reserved': 0, 'spent': 0}
    assert lease.finish(20, 'terminal').end_reason == reason


def test_deadline_closes_credit_and_retains_post_deadline_work():
    stop = []
    lease = LeaseController({NodeKey(0, 1): None}, deadline_ns=12, request_stop=lambda: stop.append('stop'), clock=lambda: 13)
    lease.begin(allocation(), 10)
    lease.next_node([record(1)], 11)
    assert lease.next_node([record(1)], 12) is None
    lease.on_completed(NodeKey(0, 1))
    lease.on_completed(NodeKey(0, 1))
    outcome = lease.finish(20, 'terminal')
    assert stop == ['stop']
    assert outcome.censored is True
    assert outcome.post_deadline_work == 1
    assert outcome.work == 0
    assert lease.ledger.snapshot() == {'available': 2, 'reserved': 0, 'spent': 0}


def test_missing_ancestry_errors_and_epoch_invalidates():
    lease = LeaseController({NodeKey(0, 1): None})
    lease.begin(allocation(), 10)
    lease.next_node([record(1)], 11)
    lease.on_completed(NodeKey(0, 1))
    with pytest.raises(ValueError, match='ancestor'):
        lease.next_node([record(2, NodeKey(0, 9), 2)], 12)
    assert lease.next_node([record(1, epoch=1)], 13) is None
    assert lease.finish(20, 'terminal').end_reason == 'restart'


@pytest.mark.parametrize('length', [0, -1, True, 2.5])
def test_nonpositive_or_noninteger_lengths_rejected(length):
    lease = LeaseController({})
    with pytest.raises(ValueError):
        lease.begin(allocation(length=length), 10)


def test_active_lease_requires_finish_before_rebid():
    lease = LeaseController({NodeKey(0, 1): None})
    lease.begin(allocation(), 10)
    with pytest.raises(RuntimeError):
        lease.begin(allocation(), 11)


def test_entry_dispatch_and_continuation_body_boundaries():
    ticks = iter([20, 25, 30, 37])
    lease = LeaseController({NodeKey(0, 1): None, NodeKey(0, 2): NodeKey(0, 1)}, clock=lambda: next(ticks))
    lease.begin(allocation(), 10)
    lease.next_node([record(1)], 11)
    lease.mark_dispatch(27)
    lease.on_completed(NodeKey(0, 1))
    lease.next_node([record(2, NodeKey(0, 1), 1)], 28)
    outcome = lease.finish(40, 'terminal')
    assert (outcome.entry_ns, outcome.dispatch_ns, outcome.end_ns) == (10, 27, 40)
    assert outcome.body_ns == 13
    assert outcome.continuation_ns == 7


def test_dispatch_crossing_deadline_requests_stop_before_native_return():
    stop = []
    lease = LeaseController({NodeKey(0, 1): None}, deadline_ns=12,
                            request_stop=lambda: stop.append('stop'))
    lease.begin(allocation(), 10)
    lease.next_node([record(1)], 11)
    lease.mark_dispatch(13)
    outcome = lease.finish(20, 'terminal')
    assert stop == ['stop']
    assert (outcome.dispatch_ns, outcome.end_reason, outcome.work) == (13, 'deadline', 0)


def test_unrelated_deletion_preserves_descendant_ancestry():
    parents = {NodeKey(0, 1): None, NodeKey(0, 2): NodeKey(0, 1), NodeKey(0, 9): None}
    lease = LeaseController(parents)
    lease.begin(allocation(), 10)
    lease.next_node([record(1)], 11)
    lease.on_completed(NodeKey(0, 1))
    lease._on_deleted(NodeKey(0, 9))
    assert lease.active
    assert lease.next_node([record(2, NodeKey(0, 1), 1)], 12) == NodeKey(0, 2)


def test_ancestor_deletion_cancels_deep_root():
    parents = {NodeKey(0, 1): None, NodeKey(0, 2): NodeKey(0, 1)}
    lease = LeaseController(parents)
    lease.begin(allocation(NodeKey(0, 2)), 10)
    lease.next_node([record(2, NodeKey(0, 1), 1)], 11)
    lease._on_deleted(NodeKey(0, 1))
    assert lease.next_node([record(2, NodeKey(0, 1), 1)], 12) is None
    assert lease.finish(15, 'terminal').end_reason == 'ancestor_deleted'


def run_native_lease_fixture(length=2, *, timeout=False, dispatch_timeout=False, restart=False,
                             normal=False, constructor_attachment=False):
    """Tiny public diagnostic covers only; no protected populations or learning."""
    from pyscipopt import Model, SCIP_EVENTTYPE as E, SCIP_PARAMSETTING as P, quicksum
    from ra.scip_backend import ScipBackend, _case_definition

    fixture = _case_definition('normal' if normal else 'branching')
    model = Model()
    model.hideOutput()
    defaults = model.getParams()
    model.setIntParam('parallel/maxnthreads', 1)
    model.setIntParam('lp/threads', 1)
    model.setRealParam('limits/time', 5.)
    if not normal:
        model.setPresolve(P.OFF)
        model.setHeuristics(P.OFF)
        model.setSeparating(P.OFF)
        model.setIntParam('presolving/maxrestarts', -1)
    x = [model.addVar(name=f'x{i}', vtype='B', obj=c) for i, c in enumerate(fixture['costs'])]
    for row in fixture['rows']:
        model.addCons(quicksum(x[i] for i in row) >= 1)
    del x
    trace, outcomes, ledgers, live_returns, event_order, incumbent_observations, deletion_observations = [], [], [], [], [], [], []

    class ObservedBackend(ScipBackend):
        def _on_event(self, event):
            kind = int(event.getType())
            event_order.append({'kind': kind, 'epoch': self.epoch, 'run': self.native_run,
                                'node_number': int(event.getNode().getNumber())
                                if kind & (E.NODESOLVED | E.NODEDELETE | E.NODEFOCUSED) else None})
            before = lease.active
            if timeout and kind in (E.NODEFEASIBLE, E.NODEINFEASIBLE, E.NODEBRANCHED):
                lease.deadline_ns = time.perf_counter_ns()
            super()._on_event(event)
            if kind == E.BESTSOLFOUND:
                incumbent_observations.append({'active_before': before, 'active_after': lease.active})
            if kind == E.NODEDELETE:
                deletion_observations.append({'number': int(event.getNode().getNumber()),
                    'active_before': before, 'active_after': lease.active})
            if restart and int(event.getType()) == E.NODEBRANCHED and not self.run_transitions and not getattr(self, '_restart_requested', False):
                self._restart_requested = True
                self.model.restartSolve()

        def resolve_live(self, key):
            node = super().resolve_live(key)
            trace.append([key.epoch, key.number])
            live_returns.append({'key': [key.epoch, key.number], 'stop': self.stop_requested})
            if dispatch_timeout and not self.stop_requested:
                lease.deadline_ns = time.perf_counter_ns()
            return node

    def collect(end_ns):
        if lease.pending:
            outcomes.append(asdict(lease.finish(end_ns, 'terminal')))
            ledgers.append(lease.ledger.snapshot())

    def choose(records):
        collect(backend.last_callback_entry_ns)
        root = min(records, key=lambda n: (-n.depth, n.key.number)).key
        lease.begin(allocation(root, length), backend.last_callback_entry_ns)
        return root

    if constructor_attachment:
        lease = LeaseController({})
        backend = ObservedBackend(model, costs=fixture['costs'], rows=fixture['rows'], choose=choose,
                                  lease_controller=lease)
    else:
        backend = ObservedBackend(model, costs=fixture['costs'], rows=fixture['rows'], choose=choose)
        lease = LeaseController(backend.parents, request_stop=backend.request_stop)
        backend.lease_controller = lease
    params = model.getParams()
    started = time.perf_counter_ns()
    backend.optimize()
    collect(backend.safe_return_ns)
    result = {'trace': trace, 'outcomes': outcomes, 'ledgers': ledgers,
              'live_returns': live_returns, 'status': str(model.getStatus()),
              'events': dict(backend.events), 'run_transitions': backend.run_transitions,
              'event_order': event_order, 'incumbent_observations': incumbent_observations,
              'deletion_observations': deletion_observations,
              'completions': [asdict(c) for c in backend.completions],
              'native_total_nodes': int(model.getNTotalNodes()),
              'native_last_run_nodes': int(model.getNNodes()),
              'completion_count': backend.processed_nodes,
              'focused_count': backend.events['NODEFOCUSED'],
              'non_search_events': dict(backend.non_search_events),
              'elapsed_ns': time.perf_counter_ns() - started,
              'last_callback_entry_ns': backend.last_callback_entry_ns,
              'last_callback_end_ns': backend.last_callback_end_ns,
              'last_dispatch_ns': backend.last_dispatch_ns,
              'stop_request_ns': backend.stop_request_ns, 'safe_return_ns': backend.safe_return_ns,
              'altered_enhancements': not normal,
              'diagnostic_fixture': 'normal' if normal else 'branching',
              'deadline_mode': 'dispatch' if dispatch_timeout else 'completed_event' if timeout else None,
              'parameter_changes': {k: v for k, v in params.items() if defaults.get(k) != v},
              'progress': backend.validated_progress()}
    model.freeProb()
    backend.raise_if_failed()
    result['subscriptions_after_free'] = backend.subscriptions
    return result


@pytest.mark.parametrize('length', [1, 2, 8])
def test_native_repeated_logical_leases_have_identical_live_traces(length):
    first, second = run_native_lease_fixture(length), run_native_lease_fixture(length)
    assert first['trace'] == second['trace']
    assert len(first['trace']) > 2
    assert first['events']['BESTSOLFOUND'] > 0
    if length > 1:
        assert any(o['active_before'] and o['active_after'] for o in first['incumbent_observations'])
        assert any(o['active_before'] and o['active_after'] for o in first['deletion_observations'])
    assert first['completion_count'] == first['native_total_nodes']
    assert first['progress'] == second['progress']
    assert sum(o['work'] for o in first['outcomes']) == len(first['trace'])
    for outcome, ledger in zip(first['outcomes'], first['ledgers']):
        assert outcome['work'] <= length
        assert ledger == {'available': length-outcome['work'], 'reserved': 0, 'spent': outcome['work']}
        assert outcome['entry_ns'] <= outcome['dispatch_ns'] <= outcome['end_ns']
        assert outcome['body_ns'] == outcome['end_ns']-outcome['dispatch_ns']
        assert 0 <= outcome['body_ns'] <= first['elapsed_ns']
        assert 0 <= outcome['continuation_ns'] <= outcome['body_ns']
    for previous, following in zip(first['outcomes'], first['outcomes'][1:]):
        assert previous['end_ns'] == following['entry_ns']
    assert any(o['end_reason'] == 'node_limit' for o in first['outcomes'])
    if length > 1:
        assert any(o['end_reason'] in ('exhaustion', 'ancestor_deleted', 'terminal') for o in first['outcomes'])


def test_native_deadline_returns_legal_live_node_and_keeps_debt():
    result = run_native_lease_fixture(timeout=True)
    assert result['status'] == 'userinterrupt'
    assert result['live_returns']
    assert any(row['stop'] for row in result['live_returns'])
    assert result['outcomes'][-1]['end_reason'] == 'deadline'
    assert result['outcomes'][-1]['censored'] is True
    assert result['outcomes'][-1]['post_deadline_work'] == 1
    assert result['outcomes'][-1]['work'] == 0
    assert result['ledgers'][-1] == {'available': 2, 'reserved': 0, 'spent': 0}
    assert result['stop_request_ns'] <= result['safe_return_ns']
    assert result['last_callback_entry_ns'] <= result['last_dispatch_ns'] <= result['last_callback_end_ns']


def test_native_dispatch_deadline_stops_before_return_with_legal_root():
    result = run_native_lease_fixture(dispatch_timeout=True)
    assert result['status'] == 'userinterrupt'
    assert result['trace'] == [[0, 1]]
    assert result['outcomes'][-1]['end_reason'] == 'deadline'
    assert result['last_dispatch_ns'] <= result['stop_request_ns'] <= result['last_callback_end_ns']


def test_native_actual_restart_cancels_lease_and_rebids_new_epoch():
    result = run_native_lease_fixture(length=8, restart=True)
    assert result['run_transitions'][0]['before'] == 1
    assert result['run_transitions'][0]['after'] == 2
    # Native old-root deletion is observed before getNRuns exposes run 2.
    assert result['outcomes'][0]['end_reason'] == 'ancestor_deleted'
    assert result['outcomes'][0]['work'] == 1
    assert result['ledgers'][0] == {'available': 7, 'reserved': 0, 'spent': 1}
    assert {key[0] for key in result['trace']} == {0, 1}
    assert all(l['reserved'] == 0 for l in result['ledgers'])


def test_native_normal_enhancements_remain_enabled():
    result = run_native_lease_fixture(normal=True)
    assert result['altered_enhancements'] is False
    assert set(result['parameter_changes']) <= {'parallel/maxnthreads', 'lp/threads', 'limits/time',
        'nodeselection/ra-live/stdpriority', 'nodeselection/ra-live/memsavepriority'}
    assert result['status'] == 'optimal'
    assert result['progress'] == (2., 2., 1.)


def test_native_constructor_attachment_binds_ancestry_and_native_stop():
    attached = run_native_lease_fixture(constructor_attachment=True)
    ordinary = run_native_lease_fixture()
    assert attached['trace'] == ordinary['trace']
    stopped = run_native_lease_fixture(constructor_attachment=True, timeout=True)
    assert stopped['status'] == 'userinterrupt'
    assert stopped['outcomes'][-1]['post_deadline_work'] == 1
