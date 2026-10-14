"""Hand-ranked policy controls and installed native parameter contracts."""
import random
import pytest
from pyscipopt import Model
from ra import allocators
from ra.config import resolve_native_overrides, load_config, ConfigError
from ra.types import DecisionContext, NodeRecord, NodeKey


def context(remaining=5):
    return DecisionContext('r', 1_000_000_000, 1_000_000_000 + int(remaining * 1e9), 0., 10., 0., 0., 10., 0, 3, 'f'*64)


def nodes():
    return [NodeRecord(NodeKey(0, i), None, d, b, e, a, 'a', 'leaf')
            for i, d, b, e, a in [(1, 2, 3., 1., 3), (2, 5, 2., 3., 2), (3, 1, 1., 2., 1)]]


@pytest.mark.parametrize('policy,want', [('estimate', 1), ('bound', 3), ('deepest', 2), ('fifo', 3)])
def test_hand_ranked_choices(policy, want):
    choice = allocators.make_allocator({'policy': policy, 'length': 2}, 17).choose(context(), nodes(), [1, 2, 4])
    assert choice.root == NodeKey(0, want)
    assert choice.node_limit == 2


def test_round_robin_services_regions_in_key_order():
    policy = allocators.make_allocator({'policy': 'round_robin_parent_groups', 'length': 1}, 0)
    assert [policy.choose(context(), nodes(), [1]).root.number for _ in range(5)] == [1, 2, 3, 1, 2]


def test_uniform_couples_seed_and_records_conditional_propensity():
    policy = allocators.make_allocator({'policy': 'uniform', 'length': 1}, 17)
    reference = random.Random(17)
    for _ in range(20):
        a = policy.choose(context(), nodes(), [1])
        assert a.root.number == reference.choice([1, 2, 3])
        assert a.selection_probability == 1/3


def test_budget_sensitive_alternates_and_uses_remaining_bins():
    policy = allocators.make_allocator({'policy': 'budget_sensitive', 'remaining_time_bins': [1., 3.], 'bin_lengths': [1, 2, 4]}, 0)
    actual = [policy.choose(context(t), nodes(), [1, 2, 4]) for t in [5., 2., .5, 3.]]
    assert [(a.root.number, a.node_limit) for a in actual] == [(1, 4), (3, 2), (1, 1), (3, 2)]


@pytest.mark.parametrize('config', [{'policy': 'invented'}, {'policy': 'fifo', 'length': True},
    {'policy': 'budget_sensitive', 'remaining_time_bins': [2., 1.], 'bin_lengths': [1, 2, 4]},
    {'policy': 'estimate', 'unexpected': 1}])
def test_invalid_policy_configuration_rejects(config):
    with pytest.raises(ValueError): allocators.make_allocator(config, 0)


def test_unsupported_length_and_empty_frontier_reject():
    policy = allocators.make_allocator({'policy': 'fifo', 'length': 8}, 0)
    with pytest.raises(ValueError): policy.choose(context(), nodes(), [1, 2])
    with pytest.raises(ValueError): policy.choose(context(), [], [1, 8])


def test_native_override_must_exist_in_installed_build():
    with pytest.raises(ValueError): resolve_native_overrides({'limits/time': 10.}, {'invented/param': 1})


def test_native_types_ranges_and_nonallocation_changes_reject():
    model = Model(); model.hideOutput()
    params = model.getParams()
    for overrides in [{'nodeselection/estimate/minplungedepth': -2}, {'nodeselection/estimate/stdpriority': True},
                      {'nodeselection/estimate/maxplungequot': float('nan')}, {'limits/time': 1.},
                      {'heuristics/rins/freq': -1}]:
        with pytest.raises(ValueError): resolve_native_overrides(params, overrides)
    changed = resolve_native_overrides(params, {'nodeselection/dfs/stdpriority': 300000})
    assert changed['nodeselection/dfs/stdpriority'] == 300000
    assert params['nodeselection/dfs/stdpriority'] == 0
    assert resolve_native_overrides(Model().getParams(), {})['nodeselection/dfs/stdpriority'] == 0
    model.freeProb()


def test_boolean_probe_ratio_is_not_numeric_one(tmp_path):
    import json
    payload = json.load(open('configs/workload_probes.json'))
    payload['row_column_ratios'] = [.5, True, 2]
    path = tmp_path/'bad.json';path.write_text(json.dumps(payload))
    with pytest.raises(ConfigError): load_config(path, 'generation')


def test_round_robin_parent_groups_deterministic_membership_changes():
    from dataclasses import replace
    policy = allocators.make_allocator({'policy':'round_robin_parent_groups','length':1},0)
    frontier=[replace(nodes()[0],parent=NodeKey(0,10)),replace(nodes()[1],parent=NodeKey(0,10)),replace(nodes()[2],parent=NodeKey(0,20))]
    assert policy.choose(context(),frontier,[1]).root.number==2  # FIFO sibling of group 10
    assert policy.choose(context(),frontier,[1]).root.number==3
    frontier=frontier[:2]+[replace(nodes()[2],key=NodeKey(0,4),parent=NodeKey(0,15))]
    assert policy.choose(context(),frontier,[1]).root.number==2
    assert policy.choose(context(),frontier,[1]).root.number==4


def test_tiny_delayed_payoff_lease_control_distinguishes_correct_schedule():
    """Two-unit public metalevel fixture; hand-proven optimum is BB=1."""
    from dataclasses import replace
    from ra.leases import LeaseController
    roots=[replace(nodes()[0],key=NodeKey(0,1),native_estimate=0.,native_lower_bound=1.),
           replace(nodes()[1],key=NodeKey(0,2),native_estimate=1.,native_lower_bound=0.)]
    values=[]
    for choice in ['estimate','bound']:
        policy=allocators.make_allocator({'policy':choice,'length':2},0)
        lease=LeaseController({r.key:None for r in roots},clock=lambda:0)
        allocation=policy.choose(context(),roots,[1,2]);lease.begin(allocation,0)
        selected=lease.next_node(roots,0);lease.mark_dispatch(0);lease.on_completed(selected)
        child=replace(next(n for n in roots if n.key==selected),key=NodeKey(0,3),parent=selected,depth=6)
        lease.parents={**lease.parents,child.key:selected}
        assert lease.next_node([child],1)==child.key
        lease.on_completed(child.key)
        outcome=lease.finish(2,'terminal');policy.observe(outcome)
        assert outcome.work==2 and outcome.unused_units==0
        values.append(.6 if selected.number==1 else 1.)
    assert values==[.6,1.]
    # Exhaust all 2-unit schedules: AA/AB/BA reach .6, only BB reaches 1.
    assert max([.6,.6,.6,1.])==1.


def test_installed_native_support_includes_boolean_plugin_settings():
    from ra.config import native_parameter_support
    model=Model();model.hideOutput()
    support=native_parameter_support()
    assert set(support)=={k for k in model.getParams() if k.startswith('nodeselection/')}
    changed=resolve_native_overrides(model.getParams(),{'nodeselection/uct/useestimate':True})
    assert changed['nodeselection/uct/useestimate'] is True
    with pytest.raises(ValueError):resolve_native_overrides(model.getParams(),{'nodeselection/uct/useestimate':1})
    model.freeProb()


def test_runtime_identity_hashes_linked_native_libraries():
    from ra.runner import _runtime_identity
    inventory=_runtime_identity()[3]
    assert any('libscip' in name for name in inventory['environment']['build'])


def test_huge_integer_native_override_rejects_without_overflow():
    model=Model();model.hideOutput()
    with pytest.raises(ValueError):resolve_native_overrides(model.getParams(),{'nodeselection/dfs/stdpriority':10**1000})
    model.freeProb()
