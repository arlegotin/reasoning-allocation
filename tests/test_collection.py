import json
import random
from pathlib import Path

import numpy as np
import pytest

from ra.collect import RandomizedBehavior, TraceWriter, collect_traces, mixture_probability
from ra.candidates import build_pool
from ra.config import load_feature_schema
from ra.types import DecisionContext, NodeKey, NodeRecord


def nodes():
    return [NodeRecord(NodeKey(1, i), None, i, float(i), float(i), 0, 'x', 'leaf') for i in range(1, 160)]


def context():
    return DecisionContext('r', 10, 100, 0., 100., 0., 0., 100., 0, 159, 'x')


def test_uniform_mass_also_counts_for_heuristic_action():
    h = (NodeKey(1, 7), 1)
    assert mixture_probability(h, h, 2, 2, .2) == pytest.approx(.85)
    actions = [(NodeKey(1, n), length) for n in (7, 8) for length in (1, 2)]
    assert sum(mixture_probability(a, h, 2, 2, .2) for a in actions) == pytest.approx(1)
    assert mixture_probability(actions[-1], h, 2, 2, .2) == pytest.approx(.05)


def test_rng_replay_and_support():
    def run():
        pool_rng = random.Random(42)
        behavior = RandomizedBehavior({'policy': 'estimate', 'length': 1}, .2, 43)
        result = []
        for _ in range(30):
            pool = build_pool(nodes(), 128, pool_rng)
            a = behavior.choose(context(), pool.records, [1, 2])
            assert a.root in pool.ids and a.node_limit in (1, 2)
            result.append((a, pool.pool_hash, behavior.last_rng_before, behavior.last_rng_after))
        return result
    assert run() == run()
    with pytest.raises(ValueError, match='support'):
        RandomizedBehavior({'policy': 'estimate', 'length': 64}, .2, 1).choose(context(), nodes(), [1, 2])


@pytest.mark.parametrize('split', ['discovery', 'validation', 'confirmatory', 'shift'])
def test_rejects_nontraining_collection_before_io(tmp_path, split):
    with pytest.raises(ValueError, match='train'):
        collect_traces(tmp_path / 'missing', split, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_trace_arrays_are_bounded_immutable_and_aligned(tmp_path):
    schema = load_feature_schema(Path('configs/features.json'))
    writer = TraceWriter(tmp_path, schema, max_decisions=2)
    row = np.zeros(len(schema.names))
    first = writer.decision(row, {'pool_hash': 'abc'})
    second = writer.decision(row + 1, {'pool_hash': 'def'})
    assert first != second
    assert np.load(tmp_path / first, allow_pickle=False).shape == (1, 192)
    with pytest.raises(ValueError, match='limit'):
        writer.decision(row, {})
    assert json.loads((tmp_path / 'decision-000000.json').read_text())['selected_features'] == first
    assert not any('NaN' in p.read_text() for p in tmp_path.glob('*.json'))
    with pytest.raises((FileExistsError, ValueError)):
        TraceWriter(tmp_path, schema, max_decisions=2)


def test_public_collection_dry_run_has_locked_training_forecast(tmp_path):
    result = collect_traces(Path('configs/exploratory.json'), 'train', tmp_path / 'traces', dry_run=True)
    assert result['independent_originals'] == 6
    assert result['requests'] == 18
    assert result['epsilon'] == .2
    assert result['support_lengths'] == [1, 2, 4, 8, 16, 32, 64]
    assert result['selected_row_bytes'] == 1536
    assert not (tmp_path / 'traces').exists()


def test_pooled_summaries_exclude_missing_and_action_fields():
    from ra.collect import pooled_features
    from ra.types import FeatureBatch
    schema = load_feature_schema(Path('configs/features.json'))
    values = np.zeros((4, 192))
    col = schema.names.index('node_depth')
    values[:, col] = [2, 2, 6, 6]
    values[2:, schema.names.index('node_bound__value_infinite')] = 1
    matrix, pooled_schema, duration = pooled_features(FeatureBatch(values, (), schema.hash, 0), schema, 2, 2, 8)
    assert matrix[0, :7].tolist() == [4, 2, 2, 6, 0, 2, 0]
    i = pooled_schema['fields'].index('node_bound') * 9
    assert matrix[0, i + 4:i + 7].tolist() == [.5, 1, 0]
    assert all(not f.startswith('action_') for f in pooled_schema['fields'])
    assert matrix[0, -1] == 8 and duration >= 0


def test_pool_summary_distinguishes_missing_from_infinity():
    from ra.collect import pooled_features
    from ra.types import FeatureBatch
    schema = load_feature_schema(Path('configs/features.json'))
    values = np.zeros((2, 192))
    values[0, schema.names.index('node_bound__missing')] = 1
    values[1, schema.names.index('node_bound__value_infinite')] = 1
    _, metadata, _ = pooled_features(FeatureBatch(values, (), schema.hash, 0), schema, 2, 1, 2)
    assert 'missing_fraction' in metadata['statistics']
    assert 'infinite_fraction' in metadata['statistics']


def test_collection_rejects_unlocked_training_input():
    from ra.collect import validate_training_instance
    from ra.data import GeneratorCell, generate_cover
    with pytest.raises(ValueError, match='locked'):
        validate_training_instance(generate_cover(GeneratorCell('uniform', 64, 32, 8), 17))


def test_trace_cap_is_explicit_fault_never_ordinary_deadline():
    from types import SimpleNamespace
    from ra.collect import CollectionRuntime
    runtime = CollectionRuntime.__new__(CollectionRuntime)
    runtime.writer = SimpleNamespace(count=128, maximum=128)
    runtime.backend = SimpleNamespace(selection_count=128)
    runtime.callbacks_limit = 1000
    with pytest.raises(RuntimeError, match='trace resource limit'):
        runtime.full()


def test_infinite_metadata_serializes_explicitly_without_nonstandard_json(tmp_path):
    schema = load_feature_schema(Path('configs/features.json'))
    writer = TraceWriter(tmp_path, schema, max_decisions=1)
    writer.decision(np.zeros(192), {'context': {'native_reference': float('inf')}})
    metadata = json.loads((tmp_path / 'decision-000000.json').read_text(),
                          parse_constant=lambda x: pytest.fail('nonstandard JSON'))
    assert metadata['context']['native_reference'] == {'nonfinite': '+infinity'}


def test_real_collection_guard_is_contained_and_costed(tmp_path):
    from ra.collect import _collection_plan
    from ra.data import GeneratorCell, generate_cover
    from ra.provenance import derive_seed
    from ra.exact import canonical_cover
    from ra.runner import run_request
    from ra.types import Request
    import hashlib
    forecast, protocol, generation, run = _collection_plan(Path('configs/exploratory.json'))
    cover = generate_cover(GeneratorCell(**generation['cells'][1]), derive_seed(generation['master_seed'], 'train', 2))
    path = tmp_path / 'original.json'
    path.write_text(json.dumps({**canonical_cover(cover), 'instance_id': cover.instance_id,
        'template_id': cover.template_id, 'cell_id': cover.cell_id, 'lineage': cover.lineage}))
    method = run['methods'][0]
    method['collection']['max_decisions'] = 1
    request = Request('guard', str(path), hashlib.sha256(path.read_bytes()).hexdigest(), cover.instance_id,
        'a'*64, 'b'*64, 'c'*64, method['name'], 'train', 17, 4_213_657_916, 2_000_000_000,
        sum(cover.costs), method_config={**method, 'lease_lengths': run['lease_lengths']})
    result = run_request(request, tmp_path / 'attempt')
    assert result.status == 'implementation_error', result.error
    assert 'trace resource limit' in result.error
    assert result.resources['native_released'] and result.resources['resource_release_confirmed']
    assert result.resources['end_to_end_ns'] > 0 and result.resources['worker_cpu_ns'] > 0
    assert result.resources['collection']['decisions'] == 1
    assert result.resources['fallback_count'] == 0
    wire_bytes = sum((tmp_path / 'attempt' / name).stat().st_size for name in
                     ('wire.jsonl', 'progress.jsonl', 'stdout.log', 'stderr.log'))
    assert result.resources['trace_bytes'] == wire_bytes + result.resources['collection']['trace_bytes']
    decisions = list((tmp_path / 'attempt/trace').glob('decision-*.json'))
    decision = json.loads(decisions[0].read_text())
    assert decision['context']['original_columns'] == 256
    assert decision['context']['original_rows'] == 512
    assert decision['context']['solver_infinity'] == 1e20
    assert decision['prediction_status'] == 'unavailable-no-model'
    assert decision['allocation']['seconds_prediction'] is None
    assert result.resources['solver_threads'] == result.resources['lp_threads'] == 1
    assert (tmp_path / 'attempt/stderr.log').read_text() == ''


def test_selected_original_weights_preserve_locked_cell_mass():
    from ra.collect import selected_training_manifest
    generated = {'instances': [{'template_index': i, 'cell_id': str(i//2), 'population_weight': 1/12}
                              for i in range(12)], 'instance_count': 12}
    selected = selected_training_manifest(generated, [0, 2, 4, 6, 8, 10])
    assert selected['instance_count'] == 6
    assert sum(r['population_weight'] for r in selected['instances']) == pytest.approx(1)
    assert all(r['population_weight'] == pytest.approx(1/6) for r in selected['instances'])
    assert generated['instances'][0]['population_weight'] == 1/12
    with pytest.raises(ValueError, match='cell'):
        selected_training_manifest(generated, [0, 2])
