"""Independent original verification and shared native observation."""
import time

import pytest
from scipy.sparse import csr_matrix
from pyscipopt import Model, SCIP_PARAMSETTING

from ra.observer import Observer, NumericalAlarm
from ra.scip_backend import ScipBackend
from ra.types import CoverInstance


@pytest.fixture
def cover():
    return CoverInstance('tiny', 'public-tiny', 'tiny', csr_matrix([[1, 1, 0], [0, 1, 1]]), (1, 2, 1), {})


def test_original_feasibility_and_fractionality_reject_false_incumbents(cover):
    observer = Observer(cover, request_id='r')
    for values in ((0, 0, 0), (1, .3, 1)):
        with pytest.raises(NumericalAlarm):
            observer.validate_incumbent(values, 10)
    assert observer.available_local() == (float('inf'), 0., 0.)


def test_verified_cache_local_progress_and_dual_alarm(cover):
    sent = []
    observer = Observer(cover, request_id='r', publish=sent.append)
    anchor = observer.validate_incumbent((1, 1, 1), 10)
    assert observer.assignments[anchor.incumbent_hash].objective == 4
    observer.validate_incumbent((0, 1, 0), 11)
    observer.observe_dual(1, 12)
    assert observer.available_local() == (2., 1., .75)
    assert [r.sequence for r in sent] == [1, 2, 3]
    with pytest.raises(NumericalAlarm, match='dual'):
        observer.observe_dual(3, 13)
    assert observer.available_local() == (2., 1., .75)


def test_original_affine_observer_preserves_utility_and_raw_deviation(cover):
    observer = Observer(cover, request_id='r', objective_scale=3, objective_offset=5)
    observer.validate_incumbent((0, 1, 0), 10)
    observer.observe_dual(8, 11)
    assert observer.available_local() == (11., 8., .75)
    record = observer.observe_dual(11 + 1e-7, 12)
    assert record.dual_original > 11
    assert observer.available_local()[2] > 1


def make_model(cover, diagnostic=False):
    model = Model()
    model.hideOutput()
    variables = [model.addVar(name=f'x{i}', vtype='B', obj=c) for i, c in enumerate(cover.costs)]
    for row in range(cover.incidence.shape[0]):
        model.addCons(sum(variables[j] for j in cover.incidence[row].indices) >= 1)
    model.setIntParam('parallel/maxnthreads', 1)
    model.setIntParam('lp/threads', 1)
    if diagnostic:
        model.setPresolve(SCIP_PARAMSETTING.OFF)
        model.setHeuristics(SCIP_PARAMSETTING.OFF)
        model.setSeparating(SCIP_PARAMSETTING.OFF)
    return model


@pytest.mark.parametrize('native', [False, True])
def test_common_observer_terminal_fallback_and_cleanup(cover, native):
    observer = Observer(cover, request_id='r')
    model = make_model(cover)
    backend = ScipBackend(model, costs=cover.costs, rows=((0, 1), (1, 2)),
                          observer=observer, install_selector=not native)
    backend.optimize()
    assert backend.validated_progress() == (2., 2., 1.)
    assert observer.records[-1].primal_original == 2
    assert backend.safe_return_ns is not None
    if native:
        assert backend.selector is None
        assert backend.selection_count == 0
        assert not backend.parents and not backend.selection_boundaries
    model.freeProb()
    assert backend.progress_subscriptions == 0


def test_native_observer_preserves_compiled_selection_without_frontier_scans(monkeypatch):
    cover = CoverInstance('tri', 'public-tri', 'tiny', csr_matrix([[1, 1, 0], [0, 1, 1], [1, 0, 1]]), (1, 1, 1), {})
    def forbidden(*args):
        raise AssertionError('native route scanned Python frontier/ancestry')
    monkeypatch.setattr(ScipBackend, 'live_frontier', forbidden)
    monkeypatch.setattr(ScipBackend, '_capture_ancestry', forbidden)
    results = []
    for observed in (False, True):
        model = make_model(cover, diagnostic=True)
        before = {k: v for k, v in model.getParams().items() if k.startswith('nodeselection/')}
        if observed:
            backend = ScipBackend(model, costs=cover.costs, rows=((0, 1), (1, 2), (0, 2)),
                                  observer=Observer(cover, request_id='r'), install_selector=False)
            backend.optimize()
            assert before == {k: v for k, v in model.getParams().items() if k.startswith('nodeselection/')}
        else:
            model.optimize()
        results.append((str(model.getStatus()), model.getObjVal(), model.getNTotalNodes(), model.getNLPs()))
        model.freeProb()
    assert results[0] == results[1]
    assert results[0][1] == 2


def test_observer_callback_fault_survives_safe_native_return(cover):
    def failed(record):
        raise RuntimeError('transport failed')
    model = make_model(cover, diagnostic=True)
    backend = ScipBackend(model, costs=cover.costs, rows=((0, 1), (1, 2)),
                          observer=Observer(cover, request_id='r', publish=failed), install_selector=False)
    with pytest.raises(RuntimeError, match='transport failed'):
        backend.optimize()
    assert backend.safe_return_ns is not None
    assert backend.callback_fault is not None
    with pytest.raises(RuntimeError):
        backend.validated_progress()
    model.freeProb()


def test_deadline_interrupt_common_observer_keeps_native_selection_legal(cover):
    model = make_model(cover, diagnostic=True)
    backend = ScipBackend(model, costs=cover.costs, rows=((0, 1), (1, 2)),
                          observer=Observer(cover, request_id='r'), install_selector=False,
                          deadline_ns=time.perf_counter_ns() - 1)
    backend.optimize()
    assert backend.stop_requested
    assert backend.stop_request_ns <= backend.safe_return_ns
    model.freeProb()


def test_terminal_poll_recovers_missed_events(cover, monkeypatch):
    from ra.scip_backend import _ProgressEvents
    monkeypatch.setattr(_ProgressEvents, 'eventexec', lambda self, event: None)
    model = make_model(cover)
    observer = Observer(cover, request_id='r')
    backend = ScipBackend(model, costs=cover.costs, rows=((0, 1), (1, 2)), observer=observer, install_selector=False)
    backend.optimize()
    assert observer.available_local() == (2., 2., 1.)
    assert observer.records
    model.freeProb()


def test_native_focused_trajectory_parity_on_branched_public_fixture(tmp_path):
    """Test instrumentation copies nodes locally; production observer never scans."""
    import json
    from pyscipopt import Eventhdlr, SCIP_EVENTTYPE
    from ra.scip_backend import _case_definition
    fixture = _case_definition('branching')
    dense = [[int(j in row) for j in range(len(fixture['costs']))] for row in fixture['rows']]
    cover = CoverInstance('branch', 'public-diagnostic-71', 'tiny', csr_matrix(dense), tuple(fixture['costs']), {})
    class Focus(Eventhdlr):
        def __init__(self): self.nodes = []
        def eventinit(self): self.model.catchEvent(SCIP_EVENTTYPE.NODEFOCUSED, self)
        def eventexit(self): self.model.dropEvent(SCIP_EVENTTYPE.NODEFOCUSED, self)
        def eventexec(self, event):
            node = event.getNode()
            self.nodes.append((int(self.model.getNRuns()), int(node.getNumber()), int(node.getDepth())))
    results = []
    for observed in (False, True):
        model = make_model(cover, diagnostic=True)
        model.setIntParam('branching/mostinf/priority', 1000000)
        probe = Focus()
        model.includeEventhdlr(probe, 'test-focus', 'diagnostic parity only')
        if observed:
            backend = ScipBackend(model, costs=cover.costs, rows=fixture['rows'],
                                  observer=Observer(cover, request_id='r'), install_selector=False)
            backend.optimize()
            assert backend.selector is None and not backend.parents
        else:
            model.optimize()
        results.append({'focused': probe.nodes, 'objective': model.getObjVal(), 'nodes': model.getNTotalNodes(),
                        'lps': model.getNLPs(), 'status': str(model.getStatus())})
        model.freeProb()
    assert len(results[0]['focused']) > 1
    assert results[0] == results[1]
    (tmp_path / 'native-parity.json').write_text(json.dumps(results, indent=2))
