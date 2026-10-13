"""Lifecycle regressions: real native search plus primitive completion replay."""
from dataclasses import FrozenInstanceError
from itertools import product
import json

import pytest
from pyscipopt import Model

from ra.scip_backend import ScipBackend, StaleNodeError, capture_capabilities, compare_nodes
from ra.types import NodeKey, NodeRecord


@pytest.fixture(scope='module')
def capabilities(tmp_path_factory):
    return capture_capabilities(tmp_path_factory.mktemp('capabilities') / 'capabilities.json')


def test_live_resolution_rejects_deleted_key(capabilities):
    evidence = capabilities['cases']['branching']
    assert evidence['deleted_key_rejections'] > 0
    assert evidence['stale_exception'] == 'StaleNodeError'


def test_restart_advances_epoch_and_rejects_old_key(capabilities):
    evidence = capabilities['cases']['restart']
    assert evidence['native_runs'] >= 2
    assert evidence['run_transitions'][0]['before'] == 1
    assert evidence['run_transitions'][0]['after'] == 2
    assert evidence['reused_numbers']
    assert evidence['old_epoch_rejections'] > 0
    assert evidence['init_calls'] >= 2
    assert evidence['exit_calls'] >= 2


def test_repeated_completion_is_counted_once():
    model = Model()
    backend = ScipBackend(model, costs=(1,), rows=((0,),))
    key = NodeKey(0, 1)
    backend.record_completion(key, 'NODEFEASIBLE', main_tree=True)
    backend.record_completion(key, 'NODEFEASIBLE', main_tree=True)
    assert backend.processed_nodes == 1
    assert backend.completions[0].key == key
    assert backend.completions[0].main_tree is True
    assert backend.completions[0].event_kind == 'NODEFEASIBLE'
    model.freeProb()


def test_deleted_unprocessed_node_costs_no_credit(capabilities):
    evidence = capabilities['cases']['branching']
    assert evidence['unprocessed_deletions'] > 0
    assert evidence['credit_from_unprocessed_deletions'] == 0


def test_subsolver_completion_is_not_main_tree_credit():
    model = Model()
    backend = ScipBackend(model, costs=(1,), rows=((0,),))
    backend.record_completion(NodeKey(0, 1), 'NODEFEASIBLE', main_tree=False)
    assert backend.processed_nodes == 0
    model.freeProb()


def test_comparator_is_immutable_total_order():
    class Node:
        def __init__(self, depth, number): self.depth, self.number = depth, number
        def getDepth(self): return self.depth
        def getNumber(self): return self.number
        def getEstimate(self): raise AssertionError('mutable estimate read')
        def getLowerbound(self): raise AssertionError('mutable bound read')
    nodes = [Node(3, 2), Node(3, 8), Node(1, 1)]
    for i, j in product(range(3), repeat=2):
        assert compare_nodes(nodes[i], nodes[j]) == (i > j) - (i < j)
        assert compare_nodes(nodes[i], nodes[j]) == -compare_nodes(nodes[j], nodes[i])
    assert compare_nodes(nodes[0], nodes[2]) < 0
    record = NodeRecord(NodeKey(0, 2), NodeKey(0, 1), 1, 0., 1., 0, 'digest', 'child')
    with pytest.raises(FrozenInstanceError): record.depth = 9


def test_native_selection_returns_live_mapping_and_primitive_history(capabilities):
    evidence = capabilities['cases']['branching']
    assert evidence['legal_selections'] > 1
    assert evidence['selection_contract'] == 'selnode'
    assert evidence['history_contains_only_primitives'] is True
    assert evidence['max_ancestor_references'] > 0
    assert evidence['completion_count'] == evidence['native_total_nodes']
    assert evidence['root_completions'] == 1


def test_native_events_cleanup_and_stop(capabilities):
    assert capabilities['cases']['branching']['events']['NODEBRANCHED'] > 0
    assert capabilities['cases']['branching']['events']['NODEDELETE'] > 0
    assert capabilities['cases']['branching']['events']['BESTSOLFOUND'] > 0
    assert capabilities['cases']['branching']['events']['DUALBOUNDIMPROVED'] > 0
    assert capabilities['cases']['branching']['subscriptions_after_free'] == 0
    stop = capabilities['cases']['interrupt']
    assert stop['status'] == 'userinterrupt'
    assert stop['stop_requested'] is True
    assert stop['legal_selections_after_stop'] > 0


def test_objective_channels_and_normal_enhancements(capabilities):
    normal = capabilities['cases']['normal']
    assert normal['altered_enhancements'] is False
    assert normal['primal_original'] == 2
    assert normal['dual_original'] == 2
    assert normal['utility_local'] == 1
    affine = capabilities['cases']['affine']
    assert affine['primal_original'] == 11
    assert affine['dual_original'] == 11
    assert affine['transformed_objective'] != affine['primal_original']
    assert affine['utility_local'] == 1


def test_gate_requires_exercised_operations_and_clock_alignment(capabilities):
    assert capabilities['success'] is True, capabilities
    assert all(op['status'] == 'exercised' for op in capabilities['operations'].values())
    clock = capabilities['clock']
    assert clock['comparable'] is True
    assert len(clock['samples']) >= 3
    for sample in clock['samples']:
        assert sample['parent_send_ns'] <= sample['child_ns'] <= sample['parent_receive_ns']


def test_resolution_outside_callback_is_forbidden():
    model = Model()
    backend = ScipBackend(model, costs=(1,), rows=((0,),))
    with pytest.raises(RuntimeError, match='callback'):
        backend.resolve_live(NodeKey(0, 1))
    model.freeProb()


def test_presolve_temporary_root_deletion_does_not_poison_main_root(capabilities):
    evidence = capabilities['cases']['branching']
    assert evidence['non_search_events'].get('NODEDELETE', 0) >= 1
    assert evidence['root_completions'] == 1
    assert evidence['status'] == 'optimal'


def test_native_lifecycle_trace_identifies_temporary_presolve_root(capabilities):
    evidence = capabilities['cases']['branching']
    temporary = next(e for e in evidence['node_events'] if not e['main_tree'])
    assert temporary['kind'] == 'NODEDELETE'
    assert temporary['number'] == 1
    assert temporary['native_processed'] == 0
    assert temporary['ever_in_frontier'] is False
    assert temporary['stage'] < 9  # SCIP_STAGE.SOLVING
    assert temporary['node_type'] == 5  # SCIP_NODETYPE.DEADEND


def test_original_verification_rejects_wrong_objective():
    from ra.scip_backend import AdapterError
    model = Model()
    model.hideOutput()
    x = model.addVar(name='x0', vtype='B', obj=2)
    model.addCons(x >= 1)
    backend = ScipBackend(model, costs=(1,), rows=((0,),))
    model.optimize()
    with pytest.raises(AdapterError, match='objective mismatch'):
        backend.validated_progress()
    model.freeProb()


def test_capture_failure_preserves_blocked_and_missing_evidence(tmp_path, monkeypatch):
    from ra import scip_backend
    def broken(name):
        raise RuntimeError('injected discovery failure')
    monkeypatch.setattr(scip_backend, '_run_case', broken)
    out = tmp_path / 'blocked.json'
    report = capture_capabilities(out)
    assert report['success'] is False
    assert report['operations']['native_discovery']['status'] == 'blocked'
    assert report['operations']['restart']['status'] == 'missing'
    assert json.loads(out.read_text()) == report


def test_missing_primitive_ancestry_is_an_adapter_error():
    from ra.scip_backend import AdapterError
    model = Model()
    backend = ScipBackend(model, costs=(1,), rows=((0,),))
    with pytest.raises(AdapterError, match='missing primitive ancestor'):
        backend._path(NodeKey(0, 99))
    model.freeProb()


def test_reinitialization_rejects_prior_transformation_keys():
    model = Model()
    model.hideOutput()
    model.setIntParam('presolving/maxrounds', 0)
    x = model.addVar(name='x0', vtype='B', obj=1)
    model.addCons(x >= 1)
    epochs = []
    old_keys = []
    def choose(records):
        key = records[0].key
        epochs.append(key.epoch)
        if old_keys:
            with pytest.raises(StaleNodeError):
                backend.resolve_live(old_keys[0])
        old_keys.append(key)
        return key
    backend = ScipBackend(model, costs=(1,), rows=((0,),), choose=choose)
    model.optimize()
    model.freeTransform()
    model.optimize()
    assert len(epochs) >= 2
    assert epochs[0] != epochs[-1]
    model.freeProb()


def test_native_diagnostics_emit_no_stage_errors(capfd):
    from ra.scip_backend import _run_case
    _run_case('normal')
    assert 'ERROR' not in capfd.readouterr().err


def test_propagation_root_native_count_without_completion_is_not_credited(capabilities):
    case = capabilities['cases']['propagation']
    assert case['native_total_nodes'] == 1
    assert case['completion_count'] == 0
    assert case['native_lps'] == 0
    assert case['counter_difference'] == 1
    assert case['uncompleted_focused_deletions'] == 1


def test_normal_fixture_records_unchanged_native_enhancements(capabilities):
    assert capabilities['cases']['normal']['enhancement_parameter_changes'] == {}


def test_versioned_fixture_inputs_match_exercised_cases(capabilities):
    import hashlib
    from pathlib import Path
    fixtures = json.loads((Path(__file__).parent / 'fixtures' / 'capability_cases.json').read_text())
    assert set(fixtures['cases']) == set(capabilities['cases'])
    for name, fixture in fixtures['cases'].items():
        digest = hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest()
        assert capabilities['cases'][name]['fixture_sha256'] == digest


def test_selected_descendant_without_lp_emits_completed_work(capabilities):
    case = capabilities['cases']['descendant_propagation']
    assert case['native_total_nodes'] == case['completion_count'] == 5
    focused = {}
    no_lp_descendants = []
    for event in case['node_events']:
        key = (event['epoch'], event['number'])
        if event['kind'] == 'NODEFOCUSED':
            focused[key] = event
        elif event['kind'] in ('NODEFEASIBLE', 'NODEINFEASIBLE', 'NODEBRANCHED'):
            start = focused.pop(key)
            if event['depth'] > 0 and event['native_lp_count'] == start['native_lp_count']:
                no_lp_descendants.append(event['number'])
    assert no_lp_descendants == [2, 4]
    assert focused == {}
    assert case['uncompleted_focused_deletions'] == 0


def test_capability_cases_release_native_resources(capabilities):
    for case in capabilities['cases'].values():
        assert case['native_release_ns'] >= case['safe_return_ns']
        assert case['plugin_models_released'] is True


def _triangle_backend(*, backend_class=ScipBackend, choose=None):
    from pyscipopt import SCIP_PARAMSETTING as P
    model = Model()
    model.hideOutput()
    model.setPresolve(P.OFF)
    model.setHeuristics(P.OFF)
    model.setSeparating(P.OFF)
    model.setIntParam('presolving/maxrestarts', -1)
    model.setIntParam('branching/mostinf/priority', 1000000)
    x = [model.addVar(name=f'x{i}', vtype='B', obj=1) for i in range(3)]
    rows = ((0, 1), (0, 2), (1, 2))
    for a, b in rows:
        model.addCons(x[a] + x[b] >= 1)
    backend = backend_class(model, costs=(1, 1, 1), rows=rows, choose=choose)
    return model, backend


def test_interruption_is_reset_for_new_transformation():
    def choose(records):
        backend.request_stop()
        return records[0].key
    model, backend = _triangle_backend(choose=choose)
    try:
        model.optimize()
        first_request_ns = backend.stop_request_ns
        assert str(model.getStatus()) == 'userinterrupt'
        model.freeTransform()
        model.optimize()
        assert str(model.getStatus()) == 'userinterrupt'
        assert backend.stop_request_ns > first_request_ns
    finally:
        model.free()


@pytest.mark.parametrize('fault_site', ['selection', 'event_exitpresolve', 'event_solving'])
def test_native_callback_fault_is_preserved_and_released(fault_site, capfd, recwarn):
    from pyscipopt import SCIP_STAGE as S, SCIP_EVENTTYPE as E
    from ra.scip_backend import AdapterError, _primitive_history
    class FaultyEvents(ScipBackend):
        def _on_event(self, event):
            stage = self.model.getStage()
            if ((fault_site == 'event_exitpresolve' and stage == S.EXITPRESOLVE)
                    or (fault_site == 'event_solving' and event.getType() == E.NODEFOCUSED)):
                raise AdapterError(f'injected {fault_site} correctness alarm')
            super()._on_event(event)
    def choose(records):
        return NodeKey(-1, 1) if fault_site == 'selection' else records[0].key
    model, backend = _triangle_backend(backend_class=FaultyEvents, choose=choose)
    expected = StaleNodeError if fault_site == 'selection' else AdapterError
    try:
        with pytest.raises(expected) as caught:
            backend.optimize()
        fault = backend.callback_fault
        assert fault['exception_type'] == expected.__name__
        assert fault['callback'] == ('nodeselect' if fault_site == 'selection' else 'eventexec')
        assert fault['stage'] == (int(S.EXITPRESOLVE) if fault_site == 'event_exitpresolve' else int(S.SOLVING))
        assert fault['message'] in str(caught.value)
        assert fault['frames']
        assert _primitive_history(backend)
        json.dumps(fault, allow_nan=False)
        with pytest.raises(expected):
            backend.validated_progress()
        assert model.getStage() in (S.PRESOLVED, S.SOLVING, S.SOLVED)
    finally:
        model.free()
    assert backend.selector.model is None
    assert backend.handler.model is None
    assert backend.subscriptions == 0
    assert 'ERROR' not in capfd.readouterr().err
    assert not recwarn.list


def test_capability_fault_report_keeps_original_error_and_failed_status(tmp_path, monkeypatch, capfd, recwarn):
    from pyscipopt import SCIP_STAGE as S
    from ra import scip_backend
    original = scip_backend._CapabilityProbe._on_event
    def fault_at_exitpresolve(self, event):
        if self.model.getStage() == S.EXITPRESOLVE:
            raise scip_backend.AdapterError('capability original correctness alarm')
        original(self, event)
    monkeypatch.setattr(scip_backend._CapabilityProbe, '_on_event', fault_at_exitpresolve)
    report = capture_capabilities(tmp_path / 'fault.json')
    assert report['success'] is False
    assert 'AdapterError: capability original correctness alarm' in report['errors'][0]
    assert report['callback_fault']['stage'] == int(S.EXITPRESOLVE)
    assert report['callback_fault']['exception_type'] == 'AdapterError'
    assert report['failed_case']['plugin_models_released'] is True
    assert report['failed_case']['native_release_ns'] >= report['failed_case']['safe_return_ns']
    assert report['operations']['native_discovery']['status'] == 'blocked'
    assert 'ERROR' not in capfd.readouterr().err
    assert not recwarn.list


@pytest.mark.parametrize('fault_during_restart', [False, True])
def test_pending_stop_survives_real_restart(fault_during_restart, capfd, recwarn):
    from pyscipopt import SCIP_EVENTTYPE as E
    from ra.scip_backend import AdapterError
    class StopDuringRestart(ScipBackend):
        def _on_event(self, event):
            super()._on_event(event)
            if self.native_run == 1 and event.getType() == E.NODEBRANCHED:
                self.model.restartSolve()
            elif self.native_run == 1 and self.processed_nodes and event.getType() == E.NODEDELETE:
                if fault_during_restart:
                    raise AdapterError('restart teardown alarm')
                self.request_stop()
    model, backend = _triangle_backend(backend_class=StopDuringRestart)
    try:
        if fault_during_restart:
            with pytest.raises(AdapterError, match='restart teardown alarm'):
                backend.optimize()
        else:
            backend.optimize()
        assert model.getNRuns() == 2
        assert backend.stop_requested is True
        assert str(model.getStatus()) == 'userinterrupt'
        assert backend.run_transitions[-1]['after'] == 2
        if fault_during_restart:
            assert backend.callback_fault['native_run'] == 1
    finally:
        model.free()
    assert 'ERROR' not in capfd.readouterr().err
    assert not recwarn.list


def test_selection_fault_cannot_pass_capability_gate(tmp_path, monkeypatch, capfd, recwarn):
    from ra import scip_backend
    monkeypatch.setattr(scip_backend._CapabilityProbe, '_choose_diagnostic', lambda self, records: NodeKey(-1, 1))
    report = capture_capabilities(tmp_path / 'selection-fault.json')
    assert report['success'] is False
    assert report['callback_fault']['exception_type'] == 'StaleNodeError'
    assert report['callback_fault']['status'] == 'implementation_error'
    assert report['failed_case']['status'] == 'implementation_error'
    assert report['failed_case']['plugin_models_released'] is True
    assert 'StaleNodeError:' in report['errors'][0]
    assert 'ERROR' not in capfd.readouterr().err
    assert not recwarn.list


def test_faulted_adapter_cannot_resume_as_success():
    def choose(records):
        raise ValueError('policy schema failure')
    model, backend = _triangle_backend(choose=choose)
    try:
        with pytest.raises(ValueError, match='policy schema failure'):
            backend.optimize()
        first_fault = dict(backend.callback_fault)
        backend.choose = lambda records: records[0].key
        model.freeTransform()
        with pytest.raises(ValueError, match='policy schema failure'):
            backend.optimize()
        assert backend.callback_fault == first_fault
    finally:
        model.free()


def test_callback_setup_failure_still_returns_a_live_node(monkeypatch, capfd, recwarn):
    from pyscipopt import SCIP_STAGE as S
    from ra import scip_backend
    class FaultyRunIdentity(ScipBackend):
        def _sync_run(self):
            if self.model.getStage() == S.SOLVING:
                raise scip_backend.AdapterError('run identity unavailable')
            super()._sync_run()
    returned = []
    original_select = scip_backend._Selector.nodeselect
    def inspect_return(selector):
        open_numbers = {node.getNumber() for nodes in selector.model.getOpenNodes() for node in nodes}
        result = original_select(selector)
        number = result['selnode'].getNumber() if result['selnode'] is not None else None
        returned.append((open_numbers, number))
        return result
    monkeypatch.setattr(scip_backend._Selector, 'nodeselect', inspect_return)
    model, backend = _triangle_backend(backend_class=FaultyRunIdentity)
    try:
        with pytest.raises(scip_backend.AdapterError, match='run identity unavailable'):
            backend.optimize()
        assert returned
        assert all(number in frontier for frontier, number in returned if frontier)
    finally:
        model.free()
    assert 'ERROR' not in capfd.readouterr().err
    assert not recwarn.list
