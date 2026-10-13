from dataclasses import replace
import json

import pytest

from ra.config import ConfigError, load_config
from ra.data import GeneratorCell, generate_cover
from ra.provenance import SplitOwnership, derive_seed, derive_cover, instance_hash


def test_split_seed_namespaces_are_deterministic_and_distinct():
    labels = ['discovery', 'train', 'validation', 'confirmatory', 'shift']
    seeds = [derive_seed('master', label, 3) for label in labels]
    assert len(set(seeds)) == 5
    assert seeds[1] == derive_seed('master', 'train', 3)
    with pytest.raises(ValueError):
        derive_seed('master', 'typo', 3)


def test_permutation_scaling_and_repeated_solver_seed_remain_in_template_split(tmp_path):
    instance = generate_cover(GeneratorCell('uniform', 6, 4, 2), 1)
    derivative = derive_cover(instance, row_order=(3, 2, 1, 0), column_order=(5, 4, 3, 2, 1, 0), cost_scale=2)
    assert derivative.template_id == instance.template_id
    assert derivative.lineage['root_template_id'] == instance.template_id
    assert instance_hash(instance) != instance_hash(derivative)
    owner = SplitOwnership()
    owner.register(instance, 'train')
    owner.register(derivative, 'train')
    owner.register(replace(derivative, lineage={**derivative.lineage, 'solver_seed': 123}), 'train')
    path = tmp_path / 'ownership.json'
    owner.save(path)
    with pytest.raises(ValueError, match='split'):
        SplitOwnership.load(path).register(derivative, 'confirmatory')


def test_structured_ancestor_ownership_cannot_hide_behind_new_matrix_or_template():
    original = generate_cover(GeneratorCell('uniform', 6, 4, 2), 2)
    other = generate_cover(GeneratorCell('uniform', 6, 4, 2), 3)
    linked = replace(other, lineage={**other.lineage, 'ancestor_template_ids': [original.template_id]})
    owner = SplitOwnership()
    owner.register(original, 'train')
    with pytest.raises(ValueError, match='split'):
        owner.register(linked, 'confirmatory')


def test_exact_content_duplicate_cannot_cross_split():
    original = generate_cover(GeneratorCell('uniform', 6, 4, 2), 4)
    alias = replace(original, template_id='different', lineage={'root_template_id': 'different'})
    owner = SplitOwnership()
    owner.register(original, 'train')
    with pytest.raises(ValueError, match='split'):
        owner.register(alias, 'validation')


@pytest.mark.parametrize('extra', [{'unknown': 0}, {'family_weights': {'uniform': -1}}, {'templates_per_cell': True}, {'purpose': 'frozen'}, {'schema_version': 2}])
def test_config_rejects_unknown_fields_negative_weights_and_invalid_types(tmp_path, extra):
    config = {'schema_version': 1, 'purpose': 'workload', 'master_seed': 'master', 'templates_per_cell': 1,
              'cells': [{'family': 'uniform', 'columns': 6, 'rows': 4, 'degree': 2}], **extra}
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ConfigError):
        load_config(path, 'workload')


def test_config_rejects_nested_unknowns_duplicate_keys_and_nonfinite(tmp_path):
    path = tmp_path / 'config.json'
    for raw in ['{"schema_version":1,"schema_version":1}', '{"family_weights":{"uniform":NaN}}',
                '{"schema_version":1,"purpose":"workload","master_seed":"x","templates_per_cell":1,"cells":[{"family":"uniform","columns":6,"rows":4,"degree":2,"extra":1}]}']:
        path.write_text(raw)
        with pytest.raises(ConfigError):
            load_config(path, 'workload')


def test_canonical_hash_ignores_sparse_storage_order_but_includes_lineage():
    original = generate_cover(GeneratorCell('uniform', 6, 4, 3), 9)
    a = original.incidence.copy()
    for r in range(4):
        start, end = a.indptr[r:r + 2]
        a.indices[start:end] = a.indices[start:end][::-1]
    assert instance_hash(replace(original, incidence=a)) == instance_hash(original)
    assert instance_hash(replace(original, lineage={**original.lineage, 'generator_version': 'changed'})) != instance_hash(original)


@pytest.mark.parametrize('weights', [{'uniform': 1e308, 'block': 1e308}, {'uniform': 1, 'block': True}, {'uniform': 1}])
def test_weights_require_complete_finite_positive_total(tmp_path, weights):
    config = {'schema_version': 1, 'purpose': 'workload', 'master_seed': 'm', 'templates_per_cell': 1,
              'cells': [{'family': 'uniform', 'columns': 6, 'rows': 4, 'degree': 2},
                        {'family': 'block', 'columns': 6, 'rows': 4, 'degree': 2, 'blocks': 2}],
              'family_weights': weights}
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ConfigError):
        load_config(path, 'workload')


def test_registry_rejects_missing_identity_and_unsupported_schema(tmp_path):
    path = tmp_path / 'ownership.json'
    for payload in [{'schema_version': 1, 'owners': {'template:': 'train'}},
                    {'schema_version': True, 'owners': {}},
                    {'schema_version': 1, 'owners': {'content:garbage': 'train'}}]:
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            SplitOwnership.load(path)


@pytest.mark.parametrize('arguments', [{'cost_scale': 0}, {'column_order': (0,)}, {'row_order': (0, 0, 0, 0)}])
def test_invalid_derivatives_are_rejected(arguments):
    instance = generate_cover(GeneratorCell('uniform', 6, 4, 2), 1)
    with pytest.raises(ValueError):
        derive_cover(instance, **arguments)


def test_conflicting_registration_leaves_registry_unchanged():
    original = generate_cover(GeneratorCell('uniform', 6, 4, 2), 1)
    other = generate_cover(GeneratorCell('uniform', 6, 4, 2), 2)
    owner = SplitOwnership()
    owner.register(original, 'train')
    before = dict(owner.owners)
    with pytest.raises(ValueError):
        owner.register(replace(other, lineage={**other.lineage, 'ancestor_template_ids': [original.template_id]}), 'validation')
    assert owner.owners == before


@pytest.mark.parametrize('parent', ['', 'not-a-hash', 'a' * 63, 'a' * 65, 'A' * 64, 'g' * 64, None, 7])
def test_invalid_derivative_parent_rejects_without_poisoning_registry(tmp_path, parent):
    instance = generate_cover(GeneratorCell('uniform', 6, 4, 2), 1)
    owner = SplitOwnership()
    owner.register(instance, 'train')
    before = dict(owner.owners)
    invalid = replace(instance, lineage={**instance.lineage, 'derivative': {'parent_instance_hash': parent}})
    with pytest.raises(ValueError):
        owner.register(invalid, 'train')
    assert owner.owners == before
    path = tmp_path / 'ownership.json'
    owner.save(path)
    assert SplitOwnership.load(path).owners == before


@pytest.mark.parametrize('parent', ['0' * 64, 'f' * 64, '0123456789abcdef' * 4])
def test_valid_derivative_parent_and_all_namespace_entries_round_trip(tmp_path, parent):
    instance = generate_cover(GeneratorCell('uniform', 6, 4, 2), 1)
    instance = replace(instance, template_id='arbitrary template:label', lineage={
        **instance.lineage, 'root_template_id': 'root template',
        'ancestor_template_ids': ['ancestor template'], 'derivative': {'parent_instance_hash': parent}})
    owner = SplitOwnership()
    owner.register(instance, 'validation')
    assert owner.owners['instance:' + parent] == 'validation'
    assert {key.split(':', 1)[0] for key in owner.owners} == {'template', 'content', 'instance'}
    path = tmp_path / 'ownership.json'
    owner.save(path)
    assert SplitOwnership.load(path).owners == owner.owners


@pytest.mark.parametrize('key,split', [('template:', 'train'), ('instance:', 'train'),
    ('content:' + 'A' * 64, 'train'), ('unknown:identity', 'train'),
    ('instance:' + '0' * 64, 'unsupported')])
def test_invalid_public_registry_entries_cannot_be_successfully_saved(tmp_path, key, split):
    owner = SplitOwnership()
    owner.owners[key] = split
    path = tmp_path / 'new' / 'ownership.json'
    with pytest.raises(ValueError):
        owner.save(path)
    assert not path.parent.exists()
