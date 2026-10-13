from dataclasses import replace
import json
import subprocess
import sys

import pytest

from ra.config import load_config
from ra.data import GeneratorCell, generate_cover, generate_workload
from ra.exact import verify_cover
from ra.provenance import instance_hash


@pytest.mark.parametrize('family', ['uniform', 'block', 'redundant'])
def test_recipe_invariants_and_repeat_hash(family):
    cell = GeneratorCell(family, 10, 20, 4, blocks=2 if family == 'block' else None,
                         clone_fraction=.25 if family == 'redundant' else 0,
                         bridge_multiplier=3 if family == 'redundant' else 1)
    a, b = generate_cover(cell, 7), generate_cover(cell, 7)
    assert a.incidence.shape == (20, 10)
    assert a.incidence.has_canonical_format
    assert set(a.incidence.data) == {1}
    assert all(a.incidence.indptr[i + 1] > a.incidence.indptr[i] for i in range(20))
    assert all(type(c) is int and c > 0 for c in a.costs)
    assert (a.incidence != b.incidence).nnz == 0
    assert a.costs == b.costs and a.lineage == b.lineage
    assert a.instance_id == b.instance_id == instance_hash(a)
    verify_cover(a, (1,) * 10, 1e-6)


@pytest.mark.parametrize('cell', [
    GeneratorCell('uniform', 3, 2, 4), GeneratorCell('uniform', 0, 2, 1),
    GeneratorCell('unknown', 10, 2, 2), GeneratorCell('block', 4, 2, 4, blocks=1),
    GeneratorCell('block', 5, 2, 4, blocks=6),
    GeneratorCell('redundant', 10, 2, 4, clone_fraction=.9),
    GeneratorCell('redundant', 10, 2, 4, clone_fraction=-.1),
    GeneratorCell('uniform', 10, 2, 2, clone_fraction=.2),
    GeneratorCell('uniform', 10, 2, 2, cost_distribution='mixture'),
    GeneratorCell('block', 10, 2, 2, blocks=2, cost_distribution='mixture', low_cost_probability=-.1),
])
def test_invalid_sampling_is_never_substituted(cell):
    with pytest.raises(ValueError):
        generate_cover(cell, 1)


def test_block_inside_reduction_recorded_and_mixture_declared():
    cell = GeneratorCell('block', 6, 9, 4, blocks=3, cost_distribution='mixture', low_cost_probability=1)
    instance = generate_cover(cell, 3)
    assert instance.lineage['inside_reductions'] == 9
    assert all(1 <= c <= 10 for c in instance.costs)
    assert all(instance.incidence.indptr[i + 1] - instance.incidence.indptr[i] == 4 for i in range(9))
    high = generate_cover(replace(cell, low_cost_probability=0), 3)
    assert all(50 <= c <= 100 for c in high.costs)


def test_floor_clones_bridge_before_clone_perturbation_and_rare_degrees():
    cell = GeneratorCell('redundant', 10, 100, 4, clone_fraction=.25, bridge_multiplier=10)
    instance = generate_cover(cell, 11)
    assert instance.lineage['clone_count'] == 2
    assert instance.lineage['base_count'] == 8
    assert instance.lineage['cost_order'] == ['bridge_base', 'clone', 'perturb_floor_one']
    rare = instance.lineage['rare_rows']
    assert len(rare) == 2
    base = instance.incidence[:, :8]
    assert all(base.indptr[r + 1] - base.indptr[r] == 1 for r in rare)
    assert all(base.indptr[r + 1] - base.indptr[r] == 4 for r in range(100) if r not in rare)
    bridge = {int(j) for r in rare for j in base[r].indices}
    assert all(instance.costs[j] % 10 == 0 for j in bridge)
    for j, source in enumerate(instance.lineage['clone_sources'], start=8):
        assert (instance.incidence[:, j] != instance.incidence[:, source]).nnz == 0
        assert abs(instance.costs[j] - instance.costs[source]) <= 1


def test_declared_decimal_clone_fraction_has_mathematical_floor_count():
    instance = generate_cover(GeneratorCell('redundant', 50, 10, 4, clone_fraction=.58), 11)
    assert instance.lineage['clone_count'] == 29
    assert instance.lineage['base_count'] == 21


def test_clone_minus_one_is_floored_and_unused_columns_are_preserved():
    # Seed 84 draws costs (63, 1), rare column 0 and clone perturbation -1.
    instance = generate_cover(GeneratorCell('redundant', 3, 1, 1, clone_fraction=.5), 84)
    assert instance.costs[instance.lineage['clone_sources'][0]] == instance.costs[2] == 1
    sparse = generate_cover(GeneratorCell('uniform', 8, 1, 1), 1)
    assert sparse.incidence.shape == (1, 8)
    assert sparse.incidence.nnz == 1


def test_A001_only_ordinary_base_parents_and_unchanged_final_rare_degree():
    cell = GeneratorCell('redundant', 10, 100, 4, clone_fraction=.25, bridge_multiplier=10)
    # Unrestricted v1 seed 8 cloned bridge column 6; corrected recipe must not.
    instance = generate_cover(cell, 8)
    rare = instance.lineage['rare_rows']
    bridge = {int(j) for r in rare for j in instance.incidence[r, :8].indices}
    expected = [j for j in range(8) if j not in bridge]
    assert not set(instance.lineage['clone_sources']) & bridge
    assert all(instance.incidence.indptr[r + 1] - instance.incidence.indptr[r] == 1 for r in rare)
    assert instance.lineage['clone_eligible_columns'] == expected
    assert instance.lineage['clone_parent_rule'] == 'ordinary-base-no-rare-incidence-v1'
    assert set(instance.lineage['clone_sources']) <= set(expected)


def test_A001_no_ordinary_parent_fails_with_original_seed_and_zero_clones_succeeds():
    from ra.data import GenerationError
    with pytest.raises(GenerationError, match='no eligible ordinary clone parent') as caught:
        generate_cover(GeneratorCell('redundant', 2, 1, 1, clone_fraction=.5), 188)
    assert caught.value.template_seed == 188
    assert caught.value.clone_count == 1
    assert caught.value.eligible_columns == ()
    instance = generate_cover(GeneratorCell('redundant', 1, 1, 1), 188)
    assert instance.lineage['clone_eligible_columns'] == []
    assert instance.lineage['clone_count'] == 0


def test_A001_ordinary_parents_are_sampled_with_replacement_never_from_clones():
    instance = generate_cover(GeneratorCell('redundant', 4, 1, 1, clone_fraction=.5), 8)
    assert len(instance.lineage['clone_eligible_columns']) == 1
    assert instance.lineage['clone_sources'] == instance.lineage['clone_eligible_columns'] * 2
    assert all(j < 2 for j in instance.lineage['clone_sources'])


def test_probe_grid_is_discovery_only_and_starts_at_64():
    config = load_config(__import__('pathlib').Path('configs/workload_probes.json'), 'workload_probes')
    report = generate_workload(config, 'discovery', None, dry_run=True)
    assert report['dry_run'] and report['purpose'] == 'discovery'
    assert min(c['columns'] for c in report['cells']) == 64
    assert {c['rows'] / c['columns'] for c in report['cells']} == {.5, 1, 2}
    assert {c['degree'] for c in report['cells']} == {4, 8, 16}
    assert {c['blocks'] for c in report['cells'] if c['family'] == 'block'} == {2, 4, 8}
    with pytest.raises(ValueError, match='discovery'):
        generate_workload(config, 'confirmatory', None, dry_run=True)


def test_cli_dry_run_writes_nothing_then_persists_manifest(tmp_path):
    config = {'schema_version': 1, 'purpose': 'workload', 'master_seed': 'test', 'templates_per_cell': 1,
              'cells': [{'family': 'uniform', 'columns': 6, 'rows': 3, 'degree': 2}]}
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    out = tmp_path / 'data' / 'train'
    command = [sys.executable, '-m', 'ra.cli', 'generate', '--config', str(path), '--split', 'train', '--out', str(out)]
    dry = subprocess.run(command + ['--dry-run'], capture_output=True, text=True)
    assert dry.returncode == 0, dry.stderr
    assert not out.parent.exists()
    real = subprocess.run(command, capture_output=True, text=True)
    assert real.returncode == 0, real.stderr
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['split'] == 'train' and len(manifest['instances']) == 1
    assert manifest['population_frozen'] is False
    assert (out.parent / 'split_ownership.json').exists()
    assert json.loads((out / (manifest['instances'][0]['instance_id'] + '.json')).read_text())['costs']


def test_lightweight_cli_and_types_do_not_import_numerical_libraries():
    run = subprocess.run([sys.executable, '-c',
        "import sys; import ra.cli, ra.types; assert not {'numpy','scipy','pyscipopt'} & sys.modules.keys()"],
        capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('raw', ['[]', 'null', '{', '{"purpose":"future"}'])
def test_cli_malformed_config_is_explicit_failure_without_traceback(tmp_path, raw):
    path = tmp_path / 'malformed.json'
    path.write_text(raw)
    run = subprocess.run([sys.executable, '-m', 'ra.cli', 'generate', '--config', str(path), '--split', 'train', '--dry-run'], capture_output=True, text=True)
    assert run.returncode == 1
    assert 'generate failed' in run.stderr
    assert 'Traceback' not in run.stderr


def test_manifest_equal_family_then_cell_weights_and_default_out(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {'schema_version': 1, 'purpose': 'workload', 'master_seed': 'test', 'templates_per_cell': 2,
              'cells': [{'family': 'uniform', 'columns': 6, 'rows': 3, 'degree': 2},
                        {'family': 'uniform', 'columns': 6, 'rows': 4, 'degree': 2},
                        {'family': 'block', 'columns': 6, 'rows': 4, 'degree': 2, 'blocks': 2}]}
    manifest = generate_workload(config, 'train', None)
    assert manifest['out'] == 'data/train'
    assert sum(r['population_weight'] for r in manifest['instances'] if r['family'] == 'uniform') == .5
    assert sum(r['population_weight'] for r in manifest['instances'] if r['family'] == 'block') == .5
    assert {r['population_weight'] for r in manifest['instances'] if r['family'] == 'uniform'} == {.125}
    with pytest.raises(ValueError):
        generate_workload(config, 'train', None)
