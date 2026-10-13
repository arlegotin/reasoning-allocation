import pytest

from ra.data import GeneratorCell, generate_cover
from ra.exact import enumerate_cover, verify_cover
from test_objectives import cover


def test_two_row_optimum_by_exhaustive_original_integer_check():
    assert enumerate_cover(cover()).objective == 2
    assert enumerate_cover(cover(((0, 1),), (2**63, 2**63 + 1))).objective == 2**63


def solve_tiny(instance, selector, diagnostic):
    from pyscipopt import Model, SCIP_PARAMSETTING, quicksum
    from ra.leases import LeaseController
    from ra.scip_backend import ScipBackend
    from ra.types import Allocation
    model = Model('public-tiny-exact-audit')
    model.hideOutput()
    defaults = model.getParams()
    model.setIntParam('parallel/maxnthreads', 1)
    model.setIntParam('lp/threads', 1)
    if diagnostic:
        model.setPresolve(SCIP_PARAMSETTING.OFF)
        model.setHeuristics(SCIP_PARAMSETTING.OFF)
        model.setSeparating(SCIP_PARAMSETTING.OFF)
    rows = [tuple(int(j) for j in instance.incidence[r].indices) for r in range(instance.incidence.shape[0])]
    variables = [model.addVar(name=f'x{i}', vtype='B', obj=c) for i, c in enumerate(instance.costs)]
    for row in rows:
        model.addCons(quicksum(variables[i] for i in row) >= 1)
    anchor = model.createSol()
    for variable in variables:
        model.setSolVal(anchor, variable, 1)
    assert model.addSol(anchor, free=True)
    backend = None
    lease = None
    if selector != 'native-scip':
        if selector != 'ra-depth':
            length = int(selector.rsplit('-', 1)[1])
            lease = LeaseController({})
            def choose(records):
                key = min(records, key=lambda n: (-n.depth, n.key.number)).key
                lease.begin(Allocation(key, length, 0., 0., None, None, ''), backend.last_callback_entry_ns)
                return key
        else:
            choose = None
        backend = ScipBackend(model, costs=instance.costs, rows=rows, choose=choose, lease_controller=lease)
    try:
        backend.optimize() if backend else model.optimize()
        assert str(model.getStatus()) == 'optimal'
        checked = verify_cover(instance, tuple(model.getVal(v) for v in variables), model.getParam('numerics/feastol'))
        assert checked.objective == enumerate_cover(instance).objective
        assert model.getObjVal() == checked.objective
        assert model.getParam('limits/nodes') == defaults['limits/nodes'] == -1
        return {'objective': checked.objective, 'nodes': int(model.getNTotalNodes()),
                'selections': backend.selection_count if backend else None,
                'diagnostic': diagnostic, 'selector': selector,
                'parameters': {k: v for k, v in model.getParams().items() if defaults.get(k) != v},
                'lease_outcomes': len(lease.outcomes) if lease else 0}
    finally:
        model.freeProb()
        if backend:
            backend.raise_if_failed()


@pytest.mark.parametrize('selector', ['native-scip', 'ra-depth', 'ra-lease-1', 'ra-lease-2', 'ra-lease-8'])
@pytest.mark.parametrize('diagnostic', [False, True], ids=['normal', 'altered-diagnostic'])
@pytest.mark.parametrize('family', ['uniform', 'block', 'redundant'])
def test_all_current_complete_selectors_match_generated_enumerated_optimum(family, diagnostic, selector):
    instance = generate_cover(GeneratorCell(family, 10, 12, 4, blocks=2 if family == 'block' else None,
        clone_fraction=.2 if family == 'redundant' else 0, bridge_multiplier=3 if family == 'redundant' else 1), 19)
    solve_tiny(instance, selector, diagnostic)


@pytest.mark.parametrize('selector', ['ra-depth', 'ra-lease-1', 'ra-lease-2', 'ra-lease-8'])
def test_each_custom_selector_is_exercised_in_explicit_branching_diagnostic(selector):
    result = solve_tiny(cover(((0, 1), (1, 2), (0, 2)), (1, 1, 1)), selector, True)
    assert result['selections'] > 0
    assert result['objective'] == 2
    if selector != 'ra-depth':
        assert result['lease_outcomes'] > 0
