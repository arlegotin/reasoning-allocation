"""Pre-allocation behavior: normalization, leakage rejection and bounded buffers."""
from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from ra.config import ConfigError, load_feature_schema
from ra.features import build_features, normalize_transformed
from ra.types import AncestrySummary, DecisionContext, LineageService, NodeKey, NodeRecord

SCHEMA = Path('configs/features.json')


def context(**changes):
    base = DecisionContext('r', 2_000_000_000, 10_000_000_000, .6, 6., 2., -10., 10., 20, 2, '',
                           start_ns=0, selection_count=10, original_columns=3, original_rows=2,
                           original_density=2/3, initial_primal_original=10., initial_dual_original=0.,
                           last_verified_improvement_ns=1_000_000_000, native_incumbent_count=2,
                           past_throughput_per_second=5., solver_infinity=1e20)
    return replace(base, **changes)


def node(number=2, **changes):
    return replace(NodeRecord(NodeKey(0, number), NodeKey(0, 1), 1, -5., 5., 3, 'digest', 'child'), **changes)


def column(batch, schema, name):
    return batch.matrix[:, schema.names.index(name)]


def test_solver_infinity_is_not_ieee_finiteness():
    value, masks = normalize_transformed(1e20, 0., 1e20, lambda x: abs(x) >= 1e20)
    assert masks['value_infinite'] is True
    assert masks['cutoff_infinite'] is True
    assert masks['lower_infinite'] is False
    assert value == 0. and math.isfinite(value)


@pytest.mark.parametrize('value,lower,cutoff,want', [
    (-5., -10., 10., .25), (0., -10., 10., .5), (5., 0., 0., 5.),
    (25., 10., 70., .25), (5., -1e20, 1e20, 5.), (5., -1e20, 10., .5),
    (5., 0., 1e20, 5.),
])
def test_normalization_references_and_positive_affine_semantics(value, lower, cutoff, want):
    got, _ = normalize_transformed(value, lower, cutoff, lambda x: abs(x) >= 1e20)
    assert got == pytest.approx(want)


def test_float64_exact_action_support_and_distinct_original_progress():
    schema = load_feature_schema(SCHEMA)
    batch = build_features(context(), [node(), node(3)], [1, 4], {}, schema)
    assert batch.matrix.dtype == np.float64
    assert batch.matrix.shape == (4, len(schema.names))
    assert batch.action_rows == ((NodeKey(0, 2), 1), (NodeKey(0, 2), 4), (NodeKey(0, 3), 1), (NodeKey(0, 3), 4))
    assert batch.schema_hash == schema.hash
    assert batch.matrix_bytes == batch.matrix.nbytes == 4 * len(schema.names) * 8
    assert batch.extraction_ns > 0
    assert np.isfinite(batch.matrix).all()
    assert column(batch, schema, 'node_bound') == pytest.approx([.25] * 4)
    assert column(batch, schema, 'node_estimate_minus_bound') == pytest.approx([.5] * 4)
    assert column(batch, schema, 'child_local_utility_original') == pytest.approx([.6] * 4)
    assert column(batch, schema, 'primal_progress_original') == pytest.approx([.4] * 4)
    assert column(batch, schema, 'dual_progress_original') == pytest.approx([.2] * 4)
    assert column(batch, schema, 'available_work') == pytest.approx([40.] * 4)
    assert column(batch, schema, 'action_remaining_work_ratio') == pytest.approx([.025, .1, .025, .1])


def test_optional_ancestry_missing_is_not_native_path_missing():
    schema = load_feature_schema(SCHEMA)
    batch = build_features(context(), [node()], [1], {}, schema)
    assert column(batch, schema, 'parent_bound__missing')[0] == 1.
    assert column(batch, schema, 'node_bound__missing')[0] == 0.
    assert column(batch, schema, 'root_to_node_depth')[0] == 1.
    from pyscipopt import Model
    from ra.scip_backend import AdapterError, ScipBackend
    model = Model()
    try:
        backend = ScipBackend(model, costs=(1,), rows=((0,),))
        with pytest.raises(AdapterError, match='missing primitive ancestor'):
            backend._path(NodeKey(0, 999))
    finally:
        model.freeProb()


def test_lineage_is_bounded_and_uses_only_preallocation_history():
    schema = load_feature_schema(SCHEMA)
    events = tuple(LineageService(i, i/10, i*100_000_000) for i in range(1, 9))
    summary = AncestrySummary(-10., 0., events)
    schema = replace(schema, lineage_limit=2)
    batch = build_features(context(), [node()], [1], {node().key: summary}, schema)
    assert column(batch, schema, 'lineage_completed_work')[0] == 15.
    assert column(batch, schema, 'lineage_gain_original')[0] == pytest.approx(1.5)
    assert column(batch, schema, 'seconds_since_service')[0] == pytest.approx(1.2)
    assert column(batch, schema, 'parent_bound')[0] == 0.
    assert column(batch, schema, 'node_minus_parent_bound')[0] == .25
    with pytest.raises(ValueError, match='bounded'):
        AncestrySummary(-10., 0., events + events)
    with pytest.raises(ValueError, match='future'):
        build_features(context(), [node()], [1], {node().key: AncestrySummary(history=(LineageService(1, .1, 3_000_000_000),))}, schema)


def test_clipping_and_solver_masks_never_mutate_native_records():
    schema = load_feature_schema(SCHEMA)
    record = node(native_estimate=1e19, native_lower_bound=1e20)
    batch = build_features(context(), [record], [1], {}, schema)
    assert column(batch, schema, 'node_estimate__out_of_range')[0] == 1.
    assert column(batch, schema, 'node_bound__value_infinite')[0] == 1.
    assert column(batch, schema, 'node_estimate_minus_bound__value_infinite')[0] == 1.
    assert record.native_estimate == 1e19 and record.native_lower_bound == 1e20


def test_schema_order_caps_hash_and_privileged_fields(tmp_path):
    schema = load_feature_schema(SCHEMA)
    assert schema.hash == load_feature_schema(SCHEMA).hash
    payload = json.loads(SCHEMA.read_text())
    payload['features'].reverse()
    path = tmp_path/'schema.json'
    path.write_text(json.dumps(payload))
    reversed_schema = load_feature_schema(path)
    assert schema.hash != reversed_schema.hash
    assert schema.names != reversed_schema.names
    for name in ('teacher_optimum', 'future_gain', 'selection_probability', 'post_selection_cost'):
        payload['features'][0]['name'] = name
        path.write_text(json.dumps(payload))
        with pytest.raises(ConfigError, match='whitelist'):
            load_feature_schema(path)
    with pytest.raises(ValueError, match='schema hash'):
        build_features(context(feature_schema_hash='wrong'), [node()], [1], {}, schema)
    with pytest.raises(TypeError, match='primitive'):
        build_features(context(), [object()], [1], {}, schema)
    with pytest.raises(TypeError, match='primitive'):
        build_features(context(), [node()], [1], {node().key: {'teacher_optimum': 1}}, schema)


@pytest.mark.parametrize('lengths', [[], [0], [True], [1, 1]])
def test_action_support_rejects_invalid_lengths(lengths):
    with pytest.raises(ValueError, match='length'):
        build_features(context(), [node()], lengths, {}, load_feature_schema(SCHEMA))


def test_buffer_limit_is_explicit_and_empty_pool_is_well_shaped():
    schema = replace(load_feature_schema(SCHEMA), max_action_rows=2)
    with pytest.raises(ValueError, match='buffer'):
        build_features(context(), [node(), node(3)], [1, 2], {}, schema)
    batch = build_features(context(), [], [1], {}, schema)
    assert batch.matrix.shape == (0, len(schema.names))
    with pytest.raises(ValueError, match='duplicate'):
        build_features(context(), [node(), node()], [1], {}, schema)


def test_primitive_types_remain_numerically_cold():
    result = subprocess.run([sys.executable, '-c', 'import sys; import ra.types; assert not ({"numpy", "scipy", "pyscipopt"} & sys.modules.keys())'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_installed_infinity_magnitude_convention_matches_primitive_threshold():
    from pyscipopt import Model
    model = Model()
    try:
        threshold = model.infinity()
        for value in (0., 1., -1., math.nextafter(threshold, 0.), threshold,
                      math.nextafter(threshold, math.inf), -threshold):
            assert (abs(value) >= threshold) == bool(model.isInfinity(abs(value)))
            _, masks = normalize_transformed(value, 0., threshold, model.isInfinity)
            assert masks['value_infinite'] == bool(model.isInfinity(abs(value)))
    finally:
        model.freeProb()


def test_original_progress_is_affine_invariant_and_independent_of_transformed_references():
    schema = load_feature_schema(SCHEMA)
    batch = build_features(context(primal_original=25., dual_original=13., initial_primal_original=37.,
                                   initial_dual_original=7., lower_bound_transformed=-300., cutoff_transformed=-270.),
                           [node()], [1], {}, schema)
    assert column(batch, schema, 'primal_progress_original')[0] == pytest.approx(.4)
    assert column(batch, schema, 'dual_progress_original')[0] == pytest.approx(.2)
    assert column(batch, schema, 'child_local_utility_original')[0] == .6


@pytest.mark.parametrize('which', ['context', 'node', 'ancestry'])
def test_embedded_native_objects_cannot_cross_primitive_boundary(which):
    schema = load_feature_schema(SCHEMA)
    ctx, record, ancestry = context(), node(), {}
    if which == 'context':
        ctx = replace(ctx, primal_original=object())
    elif which == 'node':
        record = replace(record, parent=object())
    else:
        ancestry = {record.key: AncestrySummary(parent_estimate=object())}
    with pytest.raises(TypeError, match='primitive'):
        build_features(ctx, [record], [1], ancestry, schema)


def test_schema_boolean_version_and_caps_excluding_mask_placeholder_reject(tmp_path):
    payload = json.loads(SCHEMA.read_text())
    path = tmp_path/'bad.json'
    payload['schema_version'] = True
    path.write_text(json.dumps(payload))
    with pytest.raises(ConfigError):
        load_feature_schema(path)
    payload['schema_version'] = 1
    payload['features'][0]['cap'] = [1, 2]
    path.write_text(json.dumps(payload))
    with pytest.raises(ConfigError, match='cap'):
        load_feature_schema(path)


@pytest.mark.parametrize('which', ['bound', 'reference', 'utility', 'dual', 'density'])
def test_unexpected_nan_is_not_a_masked_zero(which):
    ctx, record = context(), node()
    if which == 'bound':
        record = replace(record, native_lower_bound=math.nan)
    else:
        name = {'reference':'lower_bound_transformed', 'utility':'utility_local', 'dual':'dual_original', 'density':'original_density'}[which]
        ctx = replace(ctx, **{name: math.nan})
    with pytest.raises(ValueError, match='NaN'):
        build_features(ctx, [record], [1], {}, load_feature_schema(SCHEMA))


def test_unavailable_primal_infinity_and_optional_none_have_distinct_masks():
    schema = load_feature_schema(SCHEMA)
    batch = build_features(context(primal_original=math.inf, original_density=None), [node()], [1], {}, schema)
    assert column(batch, schema, 'primal_progress_original__value_infinite')[0] == 1.
    assert column(batch, schema, 'primal_progress_original__missing')[0] == 0.
    assert column(batch, schema, 'original_density__missing')[0] == 1.
    assert column(batch, schema, 'original_density__value_infinite')[0] == 0.


def test_parent_summary_without_stored_service_history_masks_only_history():
    schema = load_feature_schema(SCHEMA)
    batch = build_features(context(), [node()], [1], {node().key: AncestrySummary(-10., 0.)}, schema)
    assert column(batch, schema, 'parent_bound__missing')[0] == 0.
    assert column(batch, schema, 'lineage_completed_work__missing')[0] == 1.
    assert column(batch, schema, 'lineage_gain_original__missing')[0] == 1.
    known_empty = build_features(context(), [node()], [1], {node().key: AncestrySummary(history=())}, schema)
    assert column(known_empty, schema, 'lineage_completed_work__missing')[0] == 0.
    assert column(known_empty, schema, 'lineage_completed_work')[0] == 0.


@pytest.mark.parametrize('which', ['node', 'context'])
def test_required_quantities_cannot_be_optional_missingness(which):
    ctx, record = context(), node()
    if which == 'node':
        record = replace(record, native_lower_bound=None)
    else:
        ctx = replace(ctx, utility_local=None)
    with pytest.raises(TypeError, match='required'):
        build_features(ctx, [record], [1], {}, load_feature_schema(SCHEMA))
