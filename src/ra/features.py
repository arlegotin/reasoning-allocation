"""Bounded pre-allocation features; never modify native search quantities."""
from __future__ import annotations

import math
import time
from dataclasses import fields
from typing import Callable, Mapping, Sequence

import numpy as np

from ra.types import AncestrySummary, DecisionContext, FeatureBatch, FeatureSchema, FeatureSpec, NodeKey, NodeRecord

MASKS = ('missing', 'value_infinite', 'lower_infinite', 'cutoff_infinite', 'out_of_range')
# A field's meaning and provenance cannot be overridden by a schema file.
WHITELIST = {
    'node_depth': ('nodes', 'node.depth'),
    'node_estimate': ('transformed-normalized', 'node.native_estimate'),
    'node_bound': ('transformed-normalized', 'node.native_lower_bound'),
    'node_estimate_minus_bound': ('transformed-normalized', 'node.estimate-bound'),
    'node_age': ('selections', 'context.selection_count-node.first_seen_selection'),
    'category_child': ('indicator', 'node.category'),
    'category_sibling': ('indicator', 'node.category'),
    'category_leaf': ('indicator', 'node.category'),
    'parent_branching_changes': ('changes', 'node.parent_branching_changes'),
    'parent_estimate': ('transformed-normalized', 'ancestry.parent_estimate'),
    'parent_bound': ('transformed-normalized', 'ancestry.parent_lower_bound'),
    'node_minus_parent_estimate': ('transformed-normalized', 'node.estimate-ancestry.parent_estimate'),
    'node_minus_parent_bound': ('transformed-normalized', 'node.bound-ancestry.parent_lower_bound'),
    'root_to_node_depth': ('nodes', 'node.depth'),
    'lineage_completed_work': ('nodes', 'ancestry.bounded_history.completed_work'),
    'lineage_gain_original': ('original-utility', 'ancestry.bounded_history.gain_original'),
    'seconds_since_service': ('seconds', 'context.snapshot_ns-ancestry.last_service_ns'),
    'original_columns': ('columns', 'context.original_columns'),
    'original_rows': ('rows', 'context.original_rows'),
    'original_density': ('fraction', 'context.original_density'),
    'remaining_time_fraction': ('fraction', 'context.start_snapshot_deadline'),
    'elapsed_seconds': ('seconds', 'context.snapshot_ns-context.start_ns'),
    'child_local_utility_original': ('original-utility', 'context.utility_local'),
    'primal_progress_original': ('original-normalized', 'context.initial_original_references-primal_original'),
    'dual_progress_original': ('original-normalized', 'context.dual_original-initial_original_references'),
    'frontier_size': ('nodes', 'context.frontier_size'),
    'completed_nodes': ('nodes', 'context.processed_nodes'),
    'seconds_since_verified_improvement': ('seconds', 'context.snapshot_ns-context.last_verified_improvement_ns'),
    'native_incumbent_count': ('solutions', 'context.native_incumbent_count'),
    'action_log1p_length': ('log-nodes', 'action.length'),
    'available_work': ('nodes', 'context.past_throughput_per_second*remaining_seconds'),
    'action_remaining_work_ratio': ('fraction', 'action.length/max(1,available_work)'),
}


def normalize_transformed(value: float, lower: float, cutoff: float,
                          is_infinity: Callable[[float], bool]) -> tuple[float, dict[str, bool]]:
    """SCIP predicates consume magnitude; offset uses finite lower, else zero.

    Difference features subtract two normalized quantities, canceling that offset.
    Scale follows the locked max(1, ...) rule, including subunit spans.
    """
    def infinite(x):
        if math.isnan(x):
            raise ValueError('unexpected NaN transformed quantity')
        return not math.isfinite(x) or bool(is_infinity(abs(x)))
    vi, li, ci = map(infinite, (value, lower, cutoff))
    scale = (max(1., abs(cutoff-lower)) if not li and not ci else
             max(1., abs(lower)) if not li else max(1., abs(cutoff)) if not ci else 1.)
    result = 0. if vi else value/scale - (lower/scale if not li else 0.)
    if not math.isfinite(result):
        raise ValueError('nonfinite transformed normalization')
    return result, {'value_infinite': vi, 'lower_infinite': li, 'cutoff_infinite': ci}


def validate_schema(schema: FeatureSchema) -> None:
    """Validate direct primitive schemas as strictly as loaded JSON schemas."""
    if (type(schema) is not FeatureSchema or type(schema.schema_version) is not int or schema.schema_version != 1 or schema.dtype != 'float64'
            or schema.preprocessing != 'explicit-masks-no-fitted-imputation'
            or type(schema.lineage_limit) is not int or not 1 <= schema.lineage_limit <= 8
            or type(schema.max_action_rows) is not int or not 1 <= schema.max_action_rows <= 65536):
        raise ValueError('unsupported feature schema/buffer bounds')
    names = []
    for item in schema.features:
        if type(item) is not FeatureSpec or type(item.name) is not str or item.name not in WHITELIST or (item.unit, item.origin) != WHITELIST[item.name]:
            raise ValueError('feature whitelist name/unit/origin violation')
        if (item.masks != MASKS or len(item.cap) != 2
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in item.cap)
                or item.cap[0] >= item.cap[1] or not item.cap[0] <= 0 <= item.cap[1]):
            raise ValueError('invalid feature caps/masks')
        names.append(item.name)
    if len(names) != len(set(names)) or set(names) != set(WHITELIST):
        raise ValueError('feature whitelist must occur exactly once')


def build_features(context: DecisionContext, candidates: Sequence[NodeRecord], lengths: Sequence[int],
                   ancestry: Mapping[NodeKey, object], schema: FeatureSchema) -> FeatureBatch:
    started = time.perf_counter_ns()
    validate_schema(schema)
    schema_hash = schema.hash
    if type(context) is not DecisionContext or any(type(node) is not NodeRecord for node in candidates):
        raise TypeError('feature inputs require exact primitive records')
    for field in fields(context):
        allowed = (str,) if field.name in ('request_id', 'feature_schema_hash') else (int, float, type(None))
        if type(getattr(context, field.name)) not in allowed:
            raise TypeError('context requires primitive scalar fields')
        value = getattr(context, field.name)
        if value is None and field.name in ('snapshot_ns', 'deadline_ns', 'utility_local', 'primal_original',
                                           'dual_original', 'lower_bound_transformed', 'cutoff_transformed',
                                           'processed_nodes', 'frontier_size'):
            raise TypeError('required context quantity cannot be missing')
        if type(value) in (int, float) and math.isnan(value):
            raise ValueError('unexpected NaN context quantity')
        if (type(value) in (int, float) and not math.isfinite(value)
                and field.name not in ('primal_original', 'lower_bound_transformed', 'cutoff_transformed')):
            raise ValueError('unexpected infinite context quantity')
    for node in candidates:
        for field in fields(node):
            value = getattr(node, field.name)
            allowed = ((NodeKey,) if field.name == 'key' else (NodeKey, type(None)) if field.name == 'parent'
                       else (str,) if field.name in ('ancestry_digest', 'category') else (int, float, type(None)))
            if type(value) not in allowed:
                raise TypeError('node requires primitive scalar/key fields')
            if value is None and field.name not in ('parent', 'parent_branching_changes'):
                raise TypeError('required node quantity cannot be missing')
            if type(value) is NodeKey and (type(value.epoch) is not int or type(value.number) is not int):
                raise TypeError('node keys require primitive integer fields')
    if context.feature_schema_hash and context.feature_schema_hash != schema_hash:
        raise ValueError('feature schema hash mismatch')
    if (not lengths or any(type(length) is not int or length <= 0 for length in lengths)
            or len(set(lengths)) != len(lengths)):
        raise ValueError('supported lengths must be distinct positive integers')
    if len({node.key for node in candidates}) != len(candidates):
        raise ValueError('duplicate candidate key')
    rows = len(candidates)*len(lengths)
    if rows > schema.max_action_rows:
        raise ValueError('feature action buffer limit exceeded')
    infinity = context.solver_infinity
    if type(infinity) not in (float, int) or not math.isfinite(infinity) or infinity <= 0:
        raise ValueError('installed solver infinity threshold required')
    is_infinity = lambda x: x >= infinity
    lower, cutoff = context.lower_bound_transformed, context.cutoff_transformed
    remaining = max(0, context.deadline_ns-context.snapshot_ns)/1e9
    matrix = np.empty((rows, len(schema.names)), dtype=np.float64)
    action_rows = []
    row_index = 0

    def scalar(value, masks=None):
        result_masks = {mask: False for mask in MASKS}
        if masks:
            result_masks.update(masks)
        if value is None:
            result_masks['missing'] = True
            value = 0.
        elif type(value) not in (int, float):
            raise TypeError('feature values must be primitive numbers')
        elif not math.isfinite(value):
            if math.isnan(value):
                raise ValueError('unexpected NaN feature quantity')
            result_masks['value_infinite'] = True
            value = 0.
        return float(value), result_masks

    def transformed(value):
        if value is None:
            return scalar(None)
        if type(value) not in (int, float):
            raise TypeError('transformed values must be primitive numbers')
        value, masks = normalize_transformed(value, lower, cutoff, is_infinity)
        return scalar(value, masks)

    def difference(left, right):
        a, ma = transformed(left)
        b, mb = transformed(right)
        masks = {mask: ma[mask] or mb[mask] for mask in MASKS}
        return scalar(0. if masks['missing'] or masks['value_infinite'] else a-b, masks)

    def seconds_since(timestamp):
        if timestamp is None:
            return None
        if type(timestamp) is not int or timestamp < 0 or timestamp > context.snapshot_ns:
            raise ValueError('invalid/future historical timestamp')
        return (context.snapshot_ns-timestamp)/1e9

    elapsed = seconds_since(context.start_ns)
    fraction = None
    if context.start_ns is not None:
        total = context.deadline_ns-context.start_ns
        if total <= 0:
            raise ValueError('positive request time budget required')
        fraction = remaining/(total/1e9)
    p0, d0 = context.initial_primal_original, context.initial_dual_original
    primal_progress = dual_progress = None
    if p0 is not None and d0 is not None:
        if not math.isfinite(p0) or not math.isfinite(d0) or p0 <= d0:
            raise ValueError('positive finite original reference span required')
        scale_original = p0-d0
        primal_progress = (p0-context.primal_original)/scale_original
        dual_progress = (context.dual_original-d0)/scale_original
    available_work = None if context.past_throughput_per_second is None else context.past_throughput_per_second*remaining
    if context.past_throughput_per_second is not None and (not math.isfinite(context.past_throughput_per_second) or context.past_throughput_per_second < 0):
        raise ValueError('nonnegative finite past throughput required')
    task = {
        'original_columns': context.original_columns, 'original_rows': context.original_rows,
        'original_density': context.original_density, 'remaining_time_fraction': fraction,
        'elapsed_seconds': elapsed, 'child_local_utility_original': context.utility_local,
        'primal_progress_original': primal_progress, 'dual_progress_original': dual_progress,
        'frontier_size': context.frontier_size, 'completed_nodes': context.processed_nodes,
        'seconds_since_verified_improvement': seconds_since(context.last_verified_improvement_ns),
        'native_incumbent_count': context.native_incumbent_count, 'available_work': available_work,
    }
    for node in candidates:
        summary = ancestry.get(node.key)
        if summary is not None and type(summary) is not AncestrySummary:
            raise TypeError('ancestry requires primitive optional summaries')
        if node.category not in ('child', 'sibling', 'leaf'):
            raise ValueError('unknown node category')
        history = None if summary is None or summary.history is None else summary.history[-schema.lineage_limit:]
        if history is not None:
            for service in history:
                seconds_since(service.end_ns)
                if type(service.completed_work) is not int or service.completed_work < 0 or type(service.gain_original) not in (int, float) or not math.isfinite(service.gain_original):
                    raise ValueError('invalid primitive lineage service')
            if any(a.end_ns > b.end_ns for a, b in zip(history, history[1:])):
                raise ValueError('out-of-order lineage history')
        parent_estimate = None if summary is None else summary.parent_estimate
        parent_bound = None if summary is None else summary.parent_lower_bound
        values = {name: scalar(value) for name, value in task.items()}
        values.update({
            'node_depth': scalar(node.depth), 'root_to_node_depth': scalar(node.depth),
            'node_age': scalar(None if context.selection_count is None else context.selection_count-node.first_seen_selection),
            'parent_branching_changes': scalar(node.parent_branching_changes),
            'node_estimate': transformed(node.native_estimate), 'node_bound': transformed(node.native_lower_bound),
            'node_estimate_minus_bound': difference(node.native_estimate, node.native_lower_bound),
            'parent_estimate': transformed(parent_estimate), 'parent_bound': transformed(parent_bound),
            'node_minus_parent_estimate': difference(node.native_estimate, parent_estimate),
            'node_minus_parent_bound': difference(node.native_lower_bound, parent_bound),
            'lineage_completed_work': scalar(None if history is None else sum(item.completed_work for item in history)),
            'lineage_gain_original': scalar(None if history is None else sum(item.gain_original for item in history)),
            'seconds_since_service': scalar(None if not history else seconds_since(history[-1].end_ns)),
            **{f'category_{category}': scalar(float(node.category == category)) for category in ('child', 'sibling', 'leaf')},
        })
        for length in lengths:
            values['action_log1p_length'] = scalar(math.log1p(length))
            values['action_remaining_work_ratio'] = scalar(None if available_work is None else length/max(1., available_work))
            col = 0
            for feature in schema.features:
                value, masks = values[feature.name]
                capped = min(feature.cap[1], max(feature.cap[0], value))
                matrix[row_index, col] = capped
                for offset, mask in enumerate(feature.masks, 1):
                    matrix[row_index, col+offset] = float(value != capped if mask == 'out_of_range' else masks[mask])
                col += 1+len(feature.masks)
            action_rows.append((node.key, length))
            row_index += 1
    return FeatureBatch(matrix, tuple(action_rows), schema_hash, time.perf_counter_ns()-started)


def pooled_schema(schema: FeatureSchema) -> FeatureSchema:
    """Distinct 301-column tabular treatment; the local schema is unchanged."""
    from dataclasses import replace
    validate_schema(schema)
    statistics = ('mean', 'population_std', 'min', 'max', 'unavailable_fraction',
                  'valid_count', 'all_missing', 'missing_fraction', 'infinite_fraction')
    pooled = tuple(FeatureSpec(f'pool_{f.name}_{stat}', f.unit if stat in statistics[:4] else 'count-or-fraction',
                              'pool.unique_nodes.' + f.name + '.' + stat, (-1e300, 1e300), ())
                   for f in schema.features if (f.origin.startswith('node.') or f.origin.startswith('ancestry.'))
                   and not f.name.startswith('category_') for stat in statistics)
    pooled += (FeatureSpec('pool_frontier_size', 'nodes', 'context.frontier_size', (0,1e300), ()),)
    return replace(schema, features=schema.features + pooled, preprocessing='local-masks-pooled-explicit-v1')


def append_pooled_context(batch: FeatureBatch, schema: FeatureSchema) -> FeatureBatch:
    """Append Task11's exact finite unique-node summaries, charging extraction."""
    from ra.collect import pooled_features
    started = time.perf_counter_ns()
    if batch.schema_hash != schema.hash or batch.matrix.shape != (len(batch.action_rows),len(schema.names)):
        raise ValueError('pooled context requires aligned local batch')
    first = {}
    for i, (key, length) in enumerate(batch.action_rows):
        first.setdefault(key, i)
    if not first:
        raise ValueError('pooled context requires candidate nodes')
    unique = FeatureBatch(batch.matrix[list(first.values())],tuple(batch.action_rows[i] for i in first.values()),schema.hash,0)
    frontier = batch.matrix[0,schema.names.index('frontier_size')]
    values, _, _ = pooled_features(unique,schema,len(first),1,frontier)
    matrix = np.concatenate((batch.matrix,np.repeat(values,len(batch.matrix),axis=0)),axis=1)
    return FeatureBatch(matrix,batch.action_rows,pooled_schema(schema).hash,batch.extraction_ns+time.perf_counter_ns()-started)
