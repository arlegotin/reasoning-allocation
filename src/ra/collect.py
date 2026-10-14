"""Training-only randomized leases and receipt-authoritative offline targets.

Numerical imports are lazy: worker thread limits must precede them. Array shards
contain one selected row each, bounding live trace memory independently of runs.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import random
import time
from typing import Sequence

from ra.types import Allocation, LeaseOutcome, NodeKey, ProgressRecord


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def mixture_probability(selected: tuple[NodeKey, int], heuristic: tuple[NodeKey, int],
                        pool_size: int, length_count: int, epsilon: float) -> float:
    if (type(pool_size) is not int or pool_size <= 0 or type(length_count) is not int or length_count <= 0
            or type(epsilon) not in (int, float) or not math.isfinite(epsilon) or not 0 < epsilon <= 1):
        raise ValueError('positive support and epsilon in (0,1] required')
    return epsilon / (pool_size * length_count) + ((1 - epsilon) if selected == heuristic else 0.)


class RandomizedBehavior:
    def __init__(self, config, epsilon, seed):
        from ra.allocators import make_allocator
        if config.get('policy') not in ('estimate', 'bound', 'deepest', 'fifo', 'local'):
            raise ValueError('collection requires a declared fixed deterministic heuristic')
        mixture_probability((NodeKey(0, 1), 1), (NodeKey(0, 1), 1), 1, 1, epsilon)
        self.heuristic = make_allocator(config, seed)
        self.config, self.epsilon, self.seed = dict(config), epsilon, seed
        self.rng = random.Random(seed)

    def choose(self, context, candidates, lengths, batch=None):
        if len(set(lengths)) != len(lengths):
            raise ValueError('duplicate supported length')
        h = (self.heuristic.choose_batch(context, candidates, batch) if self.config['policy'] == 'local' and batch is not None
             else self.heuristic.choose(context, candidates, lengths))
        self.last_rng_before = self.rng.getstate()
        self.explored = self.rng.random() < self.epsilon
        action = ((self.rng.choice(candidates).key, self.rng.choice(lengths)) if self.explored
                  else (h.root, h.node_limit))
        self.last_rng_after = self.rng.getstate()
        self._exploration_action = action
        self._rng_hash = digest([self.config, self.epsilon, self.seed, self.last_rng_before, self.last_rng_after])
        return self._with_heuristic(h, candidates, lengths)

    def refresh_batch(self, candidates, lengths):
        return self._with_heuristic(self.heuristic.refresh_batch(), candidates, lengths)

    def _with_heuristic(self, h, candidates, lengths):
        # Rescoring never draws again or changes the declared uniform support.
        action = self._exploration_action if self.explored else (h.root, h.node_limit)
        self.last_heuristic = (h.root, h.node_limit)
        probability = mixture_probability(action, self.last_heuristic, len(candidates), len(lengths), self.epsilon)
        state = digest([self._rng_hash, h.policy_state_hash])
        # Explicit unavailable predictions, never a zero-second duration estimate.
        return Allocation(*action, None, None, None, probability, state)

    def observe(self, outcome):
        pass


def label_leases(leases: Sequence[LeaseOutcome], progress: Sequence[ProgressRecord],
                 deadline_ns: int, p0: int) -> list[dict[str, object]]:
    from ra.metrics import progress_at
    labels = []
    for lease in leases:
        if lease.dispatch_ns is None:
            continue
        if any(type(value) is not int or value < 0 for value in
               (lease.entry_ns, lease.dispatch_ns, lease.end_ns, lease.body_ns)):
            raise ValueError('body timing requires nonnegative integer nanoseconds')
        if not lease.entry_ns <= lease.dispatch_ns <= lease.end_ns:
            raise ValueError('invalid lease interval')
        if lease.snapshot_ns is not None and not lease.entry_ns <= lease.snapshot_ns <= lease.dispatch_ns:
            raise ValueError('snapshot outside administration')
        if lease.body_ns != lease.end_ns - lease.dispatch_ns:
            raise ValueError('body interval mismatch')
        begin = progress_at(progress, min(lease.entry_ns, deadline_ns), p0)
        end = progress_at(progress, min(lease.end_ns, deadline_ns), p0)
        lower_bound = lease.end_reason in ('watchdog', 'missing_terminal', 'external_interrupt')
        natural = lease.natural_completion and not lease.censored and lease.end_ns <= deadline_ns
        # The target is consumed dispatch-to-boundary time, not eventual grant
        # completion. Exact safe stops/deletions remain observed durations.
        duration_known = lease.end_reason in ('node_limit', 'exhaustion', 'terminal',
            'ancestor_deleted', 'restart', 'deadline', 'search_exit') and not lower_bound
        labels.append({**asdict(lease), 'admin_ns': lease.dispatch_ns - lease.entry_ns,
                       'full_ns': lease.end_ns - lease.entry_ns, 'endpoint_gain': end.utility - begin.utility,
                       'endpoint_ns': min(lease.end_ns, deadline_ns), 'parent_utility_entry': begin.utility,
                       'parent_utility_end': end.utility, 'last_observation_sequence': end.sequence,
                       'completion_outcome_known': natural, 'natural_completion': True if natural else None,
                       'duration_lower_bound': lower_bound,
                       'duration_observation_known': duration_known,
                       'body_fit_eligible': duration_known,
                       'deadline_censored': lease.end_ns > deadline_ns or lease.end_reason == 'deadline',
                       'overshoot_ns': max(0, lease.end_ns - deadline_ns)})
    return labels


def residual_administration(boundaries, *, dispatched_entries=None):
    return sum(b.end_ns - b.entry_ns for b in boundaries if b.end_ns is not None and
               (b.kind == 'residual' or b.kind == 'rebid' and dispatched_entries is not None
                and b.entry_ns not in dispatched_entries))


class TraceWriter:
    """Exclusive immutable per-decision array shard and JSON alignment record."""
    def __init__(self, directory, schema, *, max_decisions):
        from ra.runner import _atomic_json
        self.directory, self.schema = Path(directory), schema
        self.directory.mkdir(parents=True, exist_ok=True)
        self.maximum, self.count = max_decisions, 0
        if type(max_decisions) is not int or not 1 <= max_decisions <= 512:
            raise ValueError('trace limit must be in 1..512')
        _atomic_json(self.directory / 'schema.json', {'schema': asdict(schema), 'hash': schema.hash,
                     'max_decisions': max_decisions, 'rows_per_shard': 1}, immutable=True)

    def decision(self, row, metadata, pooled=None):
        if self.count >= self.maximum:
            raise ValueError('trace decision limit reached')
        name = self._write(row, metadata, pooled, self.count, '')
        self.count += 1
        return name

    def revision(self, row, metadata, index, revision):
        if index != self.count - 1 or type(revision) is not int or revision <= 0:
            raise ValueError('invalid prepared decision revision')
        return self._write(row, metadata, None, index, f'-revision-{revision:06d}')

    def _write(self, row, metadata, pooled, index, suffix):
        import numpy as np
        from ra.runner import _atomic_json
        row = np.asarray(row, dtype=np.float64)
        if row.shape != (len(self.schema.names),) or not np.isfinite(row).all():
            raise ValueError('invalid selected feature row')
        name = f'selected-{index:06d}{suffix}.npy'
        started = time.perf_counter_ns()
        with (self.directory / name).open('xb') as stream:
            np.save(stream, row[None, :], allow_pickle=False)
            stream.flush()
        record = {**metadata, 'index': index, 'selected_features': name, 'selected_row': 0,
                  'selected_features_sha256': hashlib.sha256((self.directory / name).read_bytes()).hexdigest(),
                  'feature_schema_hash': self.schema.hash}
        if pooled is not None:
            matrix, schema, extraction_ns = pooled
            pooled_name = f'pooled-{index:06d}.npy'
            with (self.directory / pooled_name).open('xb') as stream:
                np.save(stream, matrix, allow_pickle=False)
            record.update(pooled_features=pooled_name, pooled_schema=schema, pooled_schema_hash=digest(schema),
                          pooled_extraction_ns=extraction_ns,
                          pooled_sha256=hashlib.sha256((self.directory / pooled_name).read_bytes()).hexdigest())
        record['array_storage_ns'] = time.perf_counter_ns() - started
        record_name = (f'prepared-{index:06d}{suffix}.json' if suffix else f'decision-{index:06d}.json')
        record_path = self.directory / record_name
        _atomic_json(record_path, finite_metadata(record), immutable=True)
        self.prepared = {'path': record_name, 'sha256': hashlib.sha256(record_path.read_bytes()).hexdigest()}
        return name


def read_decision(path, *, inventory=None):
    """Join immutable preparation to its authoritative final dispatch decision."""
    from ra.worker import strict_json
    path = Path(path)
    def read(p):
        raw = p.read_bytes()
        if inventory is not None:
            inventory[str(p)] = hashlib.sha256(raw).hexdigest()
        return strict_json(raw.decode())
    initial = read(path)
    dispatch_path = path.with_name(f"dispatch-{initial['index']:06d}.json")
    if not dispatch_path.exists():
        return initial
    dispatch = read(dispatch_path)
    final = dispatch.get('final_decision')
    if final is None:  # Historical traces retain their original exact semantics.
        return initial
    prepared_path = path.parent / final['prepared']['path']
    if (prepared_path.parent.resolve() != path.parent.resolve() or
            hashlib.sha256(prepared_path.read_bytes()).hexdigest() != final['prepared']['sha256']):
        raise ValueError('prepared decision hash/path mismatch')
    prepared = read(prepared_path)
    if any(prepared.get(k) != initial.get(k) for k in
           ('index', 'context', 'pool_hash', 'pool_ids', 'support_hash', 'support_lengths', 'feature_schema_hash')):
        raise ValueError('prepared decision context/support mismatch')
    if any(prepared['allocation'][k] != dispatch['allocation'][k] for k in ('root', 'node_limit')):
        raise ValueError('prepared/final action mismatch')
    if prepared['selected_features'] != dispatch['selected_features']:
        raise ValueError('prepared/final selected row mismatch')
    pool = {k:v for k,v in initial.items() if k.startswith('pooled_')}
    return {**pool, **prepared, 'allocation': dispatch['allocation'], 'heuristic': final['heuristic']}


def pooled_features(batch, schema, pool_size, length_count, frontier_size):
    """Separate B6 preparation, never part of the local runtime feature schema."""
    import numpy as np
    started = time.perf_counter_ns()
    fields = [f.name for f in schema.features if (f.origin.startswith('node.') or f.origin.startswith('ancestry.'))
              and not f.name.startswith('category_')]
    rows = batch.matrix[::length_count]
    if len(rows) != pool_size:
        raise ValueError('pool/action alignment mismatch')
    result = []
    for field in fields:
        i = schema.names.index(field)
        values = rows[:, i]
        # Missing/infinite transformed references are unavailable, not finite zero.
        valid = ~np.any(rows[:, [schema.names.index(field + '__' + mask) for mask in
                                  ('missing', 'value_infinite', 'lower_infinite', 'cutoff_infinite')]] != 0, axis=1)
        observed = values[valid]
        result.extend([float(observed.mean()), float(observed.std()), float(observed.min()), float(observed.max())]
                      if len(observed) else [0.] * 4)
        result.extend([1 - len(observed) / pool_size, len(observed), int(not len(observed)),
                       float(np.mean(rows[:, schema.names.index(field + '__missing')] != 0)),
                       float(np.mean(np.any(rows[:, [schema.names.index(field + '__' + mask) for mask in
                           ('value_infinite', 'lower_infinite', 'cutoff_infinite')]] != 0, axis=1)))])
    result.append(frontier_size)
    metadata = pooled_metadata(schema)
    return np.asarray(result, dtype=np.float64)[None, :], metadata, time.perf_counter_ns() - started


def pooled_metadata(schema):
    fields = [f.name for f in schema.features if (f.origin.startswith('node.') or f.origin.startswith('ancestry.'))
              and not f.name.startswith('category_')]
    return {'version': 1, 'fields': fields,
                'statistics': ['mean', 'population_std', 'min', 'max', 'unavailable_fraction', 'valid_count', 'all_missing', 'missing_fraction', 'infinite_fraction'],
                'tail': ['frontier_size'], 'source_local_schema': schema.hash,
                'population': 'unique pre-allocation candidate pool nodes, one row per node',
                'invalid': 'any missing/value-infinity/reference-infinity mask; capped finite observations retained'}

def collect_traces(config_path: Path, split: str, out: Path, *, dry_run: bool = False) -> dict[str, object]:
    if split != 'train':
        raise ValueError('collection is restricted to train namespace')
    return _collect_traces(Path(config_path), Path(out), dry_run=dry_run)


def validate_collection_method(config):
    if not isinstance(config, dict) or set(config) - {'compact_logging'} != {'epsilon', 'pool_seed', 'behavior_seed', 'schema_path', 'schema_hash', 'max_decisions'}:
        raise ValueError('invalid collection method fields')
    if 'compact_logging' in config and type(config['compact_logging']) is not bool:
        raise ValueError('compact logging requires a boolean')
    if config['epsilon'] != .2 or type(config['epsilon']) is not float:
        raise ValueError('epsilon is locked at .2 pending support evidence')
    if any(type(config[k]) is not int or config[k] < 0 for k in ('pool_seed', 'behavior_seed')):
        raise ValueError('dedicated RNG seeds required')
    if type(config['max_decisions']) is not int or not 1 <= config['max_decisions'] <= 512:
        raise ValueError('invalid bounded trace limit')
    if not isinstance(config['schema_path'], str) or not Path(config['schema_path']).is_absolute():
        raise ValueError('resolved feature schema path required')
    from ra.config import load_feature_schema
    if load_feature_schema(Path(config['schema_path'])).hash != config['schema_hash']:
        raise ValueError('feature schema identity mismatch')


class CollectionRuntime:
    """Callback-local primitives, bounded history and immutable disk records."""
    def __init__(self, request, instance, model, observer, directory):
        from collections import OrderedDict
        from ra.config import load_feature_schema
        from ra.leases import LeaseController
        if 'collection' in request.method_config:
            validate_training_instance(instance)
        self.request, self.instance, self.model, self.observer = request, instance, model, observer
        config = request.method_config.get('collection', request.method_config.get('learned'))
        self.schema = load_feature_schema(Path(config['schema_path']))
        self.writer = TraceWriter(directory, self.schema, max_decisions=config['max_decisions'])
        self.pool_rng = random.Random(config['pool_seed'])
        from ra.allocators import make_allocator
        self.randomized = 'collection' in request.method_config
        self.behavior = (RandomizedBehavior(request.method_config['allocator'], config['epsilon'], config['behavior_seed'])
                         if self.randomized else make_allocator(request.method_config['allocator'], config['behavior_seed']))
        local = self.behavior.heuristic if self.randomized else self.behavior
        local.compact_logging = config.get('compact_logging', False)
        self.diagnostics = []
        self.pending_decision = None
        self.lease = LeaseController({}, deadline_ns=request.deadline_ns,
            on_dispatch=self.dispatched, on_finish=self.finished, retain_outcomes=False)
        self.bounds, self.history = OrderedDict(), OrderedDict()
        self.last_utility, self.last_improvement = 0., None
        self.backend = None
        self.callbacks_limit = config['max_decisions'] * (max(request.method_config['lease_lengths']) + 1) + 2

    def full(self):
        if (self.writer.count >= self.writer.maximum or
                self.backend is not None and self.backend.selection_count >= self.callbacks_limit):
            raise RuntimeError('collection trace resource limit reached; unfinished lease is censored')
        return False

    def dispatched(self, payload):
        from ra.runner import _atomic_json
        started = time.perf_counter_ns()
        payload = {**payload, 'allocation': asdict(payload['allocation'])}
        pending = getattr(self, 'pending_decision', None)
        if pending is not None:
            payload.update(final_decision=pending['final'], decision_ns=pending['decision_ns'],
                           decision_residual_ns=payload['dispatch_ns'] - pending['decision_ns'])
        _atomic_json(self.writer.directory / f"dispatch-{payload['trace_index']:06d}.json", payload, immutable=True)
        if pending is not None:
            diagnostics = pending['local'].compact_diagnostics if getattr(pending['local'], 'compact_logging', False) else pending['local'].last_diagnostics
            diagnostics.update(prepared_revisions=pending['revisions'],
                               decision_residual_ns=payload['decision_residual_ns'])
            diagnostics['dispatch_journal_ns'] = time.perf_counter_ns() - started
            self.diagnostics.append(diagnostics)
            self.pending_decision = None

    def finished(self, outcome):
        from ra.runner import _atomic_json
        from ra.types import LineageService
        utility = self.observer.available_local()[2]
        outcome = replace(outcome, local_utility_end=utility)
        _atomic_json(self.writer.directory / f'outcome-{outcome.trace_index:06d}.json', asdict(outcome), immutable=True)
        if outcome.dispatch_ns is not None:
            history = (*self.history.get(outcome.root, ()), LineageService(outcome.work,
                utility - (outcome.local_utility_entry or 0.), outcome.end_ns))[-8:]
            self.history[outcome.root] = history
            self.history.move_to_end(outcome.root)
            if len(self.history) > 4096:
                self.history.popitem(last=False)

    def choose(self, records):
        from ra.candidates import build_pool
        from ra.features import build_features
        from ra.types import AncestrySummary, DecisionContext
        b, model = self.backend, self.model
        pool = build_pool(records, self.request.method_config['pool_size'], self.pool_rng)
        primal, dual, utility = self.observer.available_local()
        snapshot = time.perf_counter_ns()
        if utility > self.last_utility:
            self.last_improvement = self.observer.records[-1].child_ns if self.observer.records else snapshot
            self.last_utility = utility
        elapsed = max(1, snapshot - self.request.launch_ns)
        rows, columns = self.instance.incidence.shape
        context = DecisionContext(self.request.request_id, snapshot, self.request.deadline_ns, utility, primal, dual,
            float(model.getLowerbound()), float(model.getCutoffbound()), b.processed_nodes, len(records), self.schema.hash,
            start_ns=self.request.launch_ns, selection_count=b.selection_count, original_columns=columns,
            original_rows=rows, original_density=self.instance.incidence.nnz/(rows*columns),
            initial_primal_original=self.request.p0, initial_dual_original=0.,
            last_verified_improvement_ns=self.last_improvement, native_incumbent_count=int(model.getNSolsFound()),
            past_throughput_per_second=b.processed_nodes*1e9/elapsed, solver_infinity=float(model.infinity()), entry_ns=b.last_callback_entry_ns)
        for n in records:
            self.bounds[n.key] = (n.native_lower_bound, n.native_estimate)
            self.bounds.move_to_end(n.key)
            if len(self.bounds) > 4096:
                self.bounds.popitem(last=False)
        ancestry = {}
        for n in pool.records:
            parent = self.bounds.get(n.parent, (None, None))
            key, services = n.key, []
            for _ in range(8):
                if key is None:
                    break
                services.extend(self.history.get(key, ()))
                key = b.parents[key]  # Required correctness ancestry is never guessed.
            history = tuple(sorted(services, key=lambda h: h.end_ns)[-8:]) if services or key is None else None
            ancestry[n.key] = AncestrySummary(*parent, history)
        lengths = self.request.method_config['lease_lengths']
        local = self.behavior.heuristic if self.randomized else self.behavior
        if hasattr(local, 'action_lengths'): lengths = list(local.action_lengths(lengths))
        batch = build_features(context, pool.records, lengths, ancestry, self.schema)
        pooled = (pooled_features(batch, self.schema, len(pool.ids), len(lengths), len(records))
                  if self.randomized else None)
        from ra.allocators import BidderExpired
        local = self.behavior.heuristic if self.randomized else self.behavior
        try:
            allocation = (self.behavior.choose(context, pool.records, lengths, batch=batch) if self.randomized
                          else self.behavior.choose_batch(context, pool.records, batch))
        except BidderExpired:
            self.diagnostics.append((local.compact_diagnostics if getattr(local, "compact_logging", False) else dict(local.last_diagnostics)))
            b.request_stop()
            return min(pool.records, key=lambda n: n.key).key
        if getattr(local, 'control_id', None) == 'B6':
            pooled = local.pooled_audit
        action = (allocation.root, allocation.node_limit)
        selected = batch.action_rows.index(action)
        support_hash = digest([pool.pool_hash, lengths])
        index = self.writer.count
        metadata = {'context': asdict(context), 'entry_ns': b.last_callback_entry_ns,
                    'pool_ids': [asdict(k) for k in pool.ids], 'pool_hash': pool.pool_hash,
                    'strata': [(name, [asdict(k) for k in keys]) for name, keys in pool.strata],
                    'pool_rng_before': pool.rng_state_before, 'pool_rng_after': pool.rng_state_after,
                    'behavior_rng_before': self.behavior.last_rng_before if self.randomized else None,
                    'behavior_rng_after': self.behavior.last_rng_after if self.randomized else None,
                    'explored': self.behavior.explored if self.randomized else False,
                    'heuristic': [asdict(self.behavior.last_heuristic[0]), self.behavior.last_heuristic[1]] if self.randomized else None,
                    'support_lengths': lengths, 'support_hash': support_hash, 'allocation': asdict(allocation),
                    'prediction_status': 'model' if hasattr(local, 'bundle') else 'unavailable-no-model', 'feature_extraction_ns': batch.extraction_ns,
                    'rng_streams': {'solver': self.request.solver_seed, **{k: self.request.method_config.get('collection', self.request.method_config.get('learned'))[k]
                                   for k in ('pool_seed', 'behavior_seed')}}, 'selected_parent': asdict(next(n for n in pool.records if n.key == allocation.root).parent)
                    if next(n for n in pool.records if n.key == allocation.root).parent is not None else None}
        path = self.writer.decision(batch.matrix[selected], metadata, pooled)
        if hasattr(local, 'refresh_batch'):
            revision = 0
            while True:
                try:
                    final = (self.behavior.refresh_batch(pool.records, lengths) if self.randomized
                             else local.refresh_batch())
                except BidderExpired:
                    diagnostics = local.compact_diagnostics if getattr(local, "compact_logging", False) else local.last_diagnostics
                    diagnostics['prepared_revisions'] = revision
                    self.diagnostics.append(diagnostics)
                    b.request_stop()
                    return allocation.root  # Prepared rows remain explicitly undispatched.
                if (final.root, final.node_limit) == (allocation.root, allocation.node_limit):
                    allocation = final
                    break
                allocation = final
                selected = batch.action_rows.index((allocation.root, allocation.node_limit))
                parent = next(n.parent for n in pool.records if n.key == allocation.root)
                metadata.update(allocation=asdict(allocation), selected_parent=asdict(parent) if parent is not None else None,
                    heuristic=[asdict(self.behavior.last_heuristic[0]), self.behavior.last_heuristic[1]] if self.randomized else None)
                revision += 1
                path = self.writer.revision(batch.matrix[selected], metadata, index, revision)
                # Every material write is followed by another clock/rate/tail check.
            self.pending_decision = {'local': local, 'decision_ns': local.decision_ns, 'revisions': revision,
                'final': {'prepared': self.writer.prepared,
                          'heuristic': [asdict(self.behavior.last_heuristic[0]), self.behavior.last_heuristic[1]]
                          if self.randomized else None}}
        if time.perf_counter_ns() >= self.request.deadline_ns:
            b.request_stop()  # This selected row has no dispatched lease and receives no label.
            if hasattr(local, 'last_diagnostics'):
                self.diagnostics.append({**(local.compact_diagnostics if getattr(local, 'compact_logging', False) else local.last_diagnostics), 'expired_before_lease': True})
            self.pending_decision = None
            return allocation.root
        self.lease.begin(allocation, b.last_callback_entry_ns, metadata={'snapshot_ns': snapshot,
            'trace_index': index, 'selected_features': path, 'pool_hash': pool.pool_hash,
            'support_hash': support_hash, 'local_utility_entry': utility})
        return allocation.root


def finalize_trace(out, progress, request, release_ns, aligned, boundaries, status, censored, *, timing_valid=True):
    """Called before parent finalization; retains interrupted evidence and costs."""
    from ra.runner import _atomic_json
    from ra.worker import strict_json
    from ra.types import SelectionBoundary
    import numpy as np
    started = time.perf_counter_ns()
    directory = Path(out) / 'trace'
    summary = {'decisions': 0, 'dispatched': 0, 'labels': 0, 'zero_gains': 0, 'body_fit_eligible': 0,
               'duration_lower_bounds': 0, 'unknown_dispatches': 0, 'status': str(status), 'attempt_duration_censored': censored,
               'residual_administration_ns': residual_administration([SelectionBoundary(**b) for b in boundaries]),
               'full_lease_ns': 0, 'admin_ns': 0, 'body_ns': 0, 'support_lengths_observed': [],
               'trace_bytes': 0, 'finalization_ns': 0}
    observed, dispatched_entries = set(), set()
    if directory.exists():
        for path in sorted(directory.glob('decision-*.json')):
            item = read_decision(path)
            index = item['index']
            summary['decisions'] += 1
            selected = directory / item['selected_features']
            if not selected.resolve().is_relative_to(directory.resolve()):
                raise ValueError('selected feature path outside trace')
            if hashlib.sha256(selected.read_bytes()).hexdigest() != item['selected_features_sha256']:
                raise ValueError('selected feature hash mismatch')
            matrix = np.load(selected, allow_pickle=False)
            if matrix.shape != (1, 192) or not np.isfinite(matrix).all():
                raise ValueError('invalid aligned selected feature shard')
            dispatch_path = directory / f'dispatch-{index:06d}.json'
            if not dispatch_path.exists():
                summary['unknown_dispatches'] += 1
                _atomic_json(directory / f'unlabelled-{index:06d}.json', {'index': index,
                    'reason': 'no authoritative dispatch record; features are not an action outcome'}, immutable=True)
                continue
            dispatch = strict_json(dispatch_path.read_text())
            if dispatch['allocation'] != item['allocation'] or dispatch['pool_hash'] != item['pool_hash']:
                raise ValueError('decision/dispatch alignment mismatch')
            allocation = item['allocation']
            root = NodeKey(**allocation['root'])
            pool = [NodeKey(**key) for key in item['pool_ids']]
            lengths = item['support_lengths']
            if root not in pool or allocation['node_limit'] not in lengths:
                raise ValueError('dispatched action outside support')
            if item['heuristic'] is None:
                if ('learned' not in request.method_config or request.method_config['allocator']['policy'] != 'local'
                        or allocation['selection_probability'] is not None):
                    raise ValueError('invalid deterministic learned propensity metadata')
            else:
                h = (NodeKey(**item['heuristic'][0]), item['heuristic'][1])
                expected = mixture_probability((root, allocation['node_limit']), h, len(pool), len(lengths), .2)
                if allocation['selection_probability'] != expected:
                    raise ValueError('behavior propensity mismatch')
            summary['dispatched'] += 1
            dispatched_entries.add(dispatch['entry_ns'])
            observed.add(allocation['node_limit'])
            outcome_path = directory / f'outcome-{index:06d}.json'
            if outcome_path.exists():
                raw = strict_json(outcome_path.read_text())
                outcome = LeaseOutcome(**{**raw, 'root': NodeKey(**raw['root'])})
                if outcome.trace_index != index or outcome.dispatch_ns != dispatch['dispatch_ns'] or outcome.root != root:
                    raise ValueError('outcome/dispatch alignment mismatch')
            else:
                outcome = LeaseOutcome(root, allocation['node_limit'], None, dispatch['entry_ns'], dispatch['dispatch_ns'],
                    release_ns, 'watchdog' if censored else 'missing_terminal', False, True, None,
                    release_ns-dispatch['dispatch_ns'], 0, None, snapshot_ns=dispatch['snapshot_ns'], trace_index=index,
                    selected_features=item['selected_features'], pool_hash=item['pool_hash'], support_hash=item['support_hash'],
                    selection_probability=allocation['selection_probability'], policy_state_hash=allocation['policy_state_hash'],
                    local_utility_entry=dispatch['local_utility_entry'])
            if aligned:
                label = label_leases([outcome], progress, request.deadline_ns, request.p0)[0]
                label.update(attempt_status=str(status), attempt_duration_censored=censored,
                             gain_fit_eligible=status != 'numerical_alarm' and not label['duration_lower_bound']
                                 and (label['completion_outcome_known'] or status in ('complete', 'deadline')),
                             duration_observation_known=label['duration_observation_known'] and timing_valid and status != 'numerical_alarm',
                             body_fit_eligible=label['body_fit_eligible'] and timing_valid and status != 'numerical_alarm')
                _atomic_json(directory / f'label-{index:06d}.json', label, immutable=True)
                summary['labels'] += 1
                summary['zero_gains'] += label['endpoint_gain'] == 0
                summary['body_fit_eligible'] += label['body_fit_eligible']
                summary['duration_lower_bounds'] += label['duration_lower_bound']
                for k in ('full_ns', 'admin_ns', 'body_ns'):
                    summary['full_lease_ns' if k == 'full_ns' else k] += label[k]
        summary['support_lengths_observed'] = sorted(observed)
        summary['trace_bytes'] = sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
    summary['residual_administration_ns'] = (None if censored and not boundaries else
        residual_administration([SelectionBoundary(**b) for b in boundaries], dispatched_entries=dispatched_entries))
    summary['finalization_ns'] = time.perf_counter_ns() - started
    _atomic_json(Path(out) / 'collection.json', summary, immutable=True)
    return summary


def _collection_plan(config_path):
    from ra.config import load_config, load_feature_schema
    from ra.worker import strict_json
    config_path = config_path.resolve()
    base = load_config(config_path, 'run')
    protocol_path = (config_path.parent / base['collection']).resolve()
    protocol = strict_json(protocol_path.read_text())
    required = {'version', 'population_evidence', 'generation_config', 'features', 'template_indices',
                'behaviors', 'epsilon', 'pool_size', 'lease_lengths', 'budget_ns', 'solver_seed',
                'pool_seed', 'behavior_seed', 'max_decisions'}
    if set(protocol) != required or protocol['version'] != 1:
        raise ValueError('invalid collection protocol')
    def resolved(name):
        return (protocol_path.parent / protocol[name]).resolve()
    evidence = strict_json(resolved('population_evidence').read_text())['population_lock']
    generation = load_config(resolved('generation_config'), 'generation')
    if generation != evidence['generation_config']:
        raise ValueError('generation differs from locked finite cells/indexed namespace')
    namespace = evidence['namespaces']['train']
    if digest({k: v for k, v in namespace.items() if k != 'namespace_sha256'}) != namespace['namespace_sha256']:
        raise ValueError('locked train namespace hash mismatch')
    indices = protocol['template_indices']
    if (not isinstance(indices, list) or not indices or len(set(indices)) != len(indices)
            or any(type(i) is not int or not 0 <= i < len(generation['cells'])*generation['templates_per_cell'] for i in indices)):
        raise ValueError('invalid locked template indices')
    if protocol['lease_lengths'] != [1, 2, 4, 8, 16, 32, 64] or protocol['pool_size'] != 128:
        raise ValueError('collection support differs from calibrated support')
    schema_path = resolved('features')
    schema = load_feature_schema(schema_path)
    method_collection = {k: protocol[k] for k in ('epsilon', 'pool_seed', 'behavior_seed', 'max_decisions')}
    method_collection.update(schema_path=str(schema_path), schema_hash=schema.hash)
    validate_collection_method(method_collection)
    methods = []
    for behavior in protocol['behaviors']:
        RandomizedBehavior(behavior, protocol['epsilon'], protocol['behavior_seed'])
        methods.append({'name': 'collect-' + behavior['policy'], 'kind': 'shared', 'allocator': behavior,
                        'pool_size': protocol['pool_size'], 'collection': method_collection})
    run = {k: v for k, v in base.items() if k not in ('collection', 'training')}
    run.update(methods=methods, solver_seeds=[protocol['solver_seed']], budgets_ns=[protocol['budget_ns']],
               lease_lengths=protocol['lease_lengths'], input_manifests=['placeholder'])
    from ra.config import validate_run_config
    validate_run_config(run)
    forecast = {'success': True, 'dry_run': True, 'epsilon': protocol['epsilon'],
                'independent_originals': len(indices), 'requests': len(indices)*len(methods),
                'generated_originals': len(generation['cells'])*generation['templates_per_cell'],
                'support_lengths': protocol['lease_lengths'], 'pool_size': protocol['pool_size'],
                'selected_row_bytes': len(schema.names)*8, 'action_buffer_bytes': 128*7*len(schema.names)*8,
                'maximum_selected_array_bytes': len(indices)*len(methods)*protocol['max_decisions']*(len(schema.names)*8+128),
                'request_wall_limit_ns': len(indices)*len(methods)*(protocol['budget_ns']+run['watchdog_grace_ns']),
                'rss_forecast': 'pilot worker <239MB; measure feature/history/trace overhead in this collection',
                'metadata_bytes_forecast': 'RNG states/support dominate; measured first shard replaces unknown byte forecast',
                'protocol_hash': digest(protocol), 'train_namespace_hash': namespace['namespace_sha256']}
    return forecast, protocol, generation, run


def _collect_traces(config_path, out, *, dry_run):
    import fcntl
    import resource
    import sys
    import tempfile
    from ra.runner import _atomic_json, _run_schedule, schedule_succeeded
    if dry_run:
        return _collection_plan(config_path)[0]
    started, cpu = time.perf_counter_ns(), time.process_time_ns()
    # Admission precedes preparation/generation/labeling and all cold requests.
    with (Path(tempfile.gettempdir()) / 'ra-primary-timed.lock').open('a+b') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another primary timed run is active') from None
        forecast, protocol, generation, run = _collection_plan(config_path)
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        if any(out.iterdir()):
            raise ValueError('collection output must be empty; prior attempts are immutable')
        _atomic_json(out / 'forecast.json', forecast, immutable=True)
        _atomic_json(out / 'protocol.json', protocol, immutable=True)
        from ra.data import generate_workload
        generated = generate_workload(generation, 'train', out / 'inputs')
        selected_manifest = selected_training_manifest(generated, protocol['template_indices'])
        _atomic_json(out / 'inputs' / 'selected-manifest.json', selected_manifest, immutable=True)
        run['input_manifests'] = [str(out / 'inputs' / 'selected-manifest.json')]
        _atomic_json(out / 'run.json', run, immutable=True)
        attempts = _run_schedule(out / 'run.json', 'train', out / 'runs', resume=False)
        summaries = [a.resources.get('collection', {}) for a in attempts]
        total_bytes = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        elapsed = time.perf_counter_ns() - started
        result = {**forecast, 'dry_run': False, 'success': schedule_succeeded(out / 'runs'),
                  'attempt_ids': [a.attempt_id for a in attempts], 'status_counts': {s: sum(str(a.status)==s for a in attempts) for s in sorted({str(a.status) for a in attempts})},
                  'labels': sum(s.get('labels', 0) for s in summaries),
                  'zero_gains': sum(s.get('zero_gains', 0) for s in summaries),
                  'body_fit_eligible': sum(s.get('body_fit_eligible', 0) for s in summaries),
                  'observed_lengths': sorted({n for s in summaries for n in s.get('support_lengths_observed', [])}),
                  'total_bytes': total_bytes, 'collection_wall_ns': elapsed,
                  'coordinator_cpu_ns': time.process_time_ns() - cpu,
                  'coordinator_peak_rss_bytes': int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
                  'worker_peak_rss_bytes': max((a.resources.get('worker_peak_rss_bytes', 0) for a in attempts), default=0),
                  'request_wall_ns': sum(a.resources['end_to_end_ns'] for a in attempts),
                  'request_worker_cpu_ns': sum(a.resources.get('worker_cpu_ns', 0) for a in attempts),
                  'overshoot_ns': sum(a.overshoot_ns for a in attempts),
                  'scope': 'entry through admitted preparation, generation, all attempts/publication, labels, status audit and byte accounting; final report write measured separately'}
        result['bytes_per_label'] = total_bytes / result['labels'] if result['labels'] else None
        result['labels_per_second'] = result['labels']*1e9/elapsed
        publication = time.perf_counter_ns()
        _atomic_json(out / 'collection.json', result, immutable=True)
        _atomic_json(out / 'publication.json', {'publication_ns': time.perf_counter_ns()-publication,
                     'reporting_tail_ns': None}, immutable=True)
        return result


def validate_training_instance(instance):
    """Reject discovery/protected assets even if their outer phase was relabelled."""
    from ra.data import GeneratorCell, generate_cover
    from ra.provenance import derive_seed
    from ra.worker import strict_json
    evidence = Path(__file__).resolve().parents[2] / 'docs/superpowers/evidence/task9.json'
    locked = strict_json(evidence.read_text())['population_lock']['generation_config']
    for cell_index, cell in enumerate(locked['cells']):
        for offset in range(locked['templates_per_cell']):
            index = cell_index * locked['templates_per_cell'] + offset
            seed = derive_seed(locked['master_seed'], 'train', index)
            if instance.lineage.get('template_seed') == seed and instance.lineage.get('cell') == cell:
                original = generate_cover(GeneratorCell(**cell), seed)
                if instance.instance_id == original.instance_id:
                    return index
    raise ValueError('collection input is not an original from locked indexed train namespace')


def finite_metadata(value):
    """Encode deliberate IEEE infinities explicitly; unexpected NaN remains a fault."""
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            raise ValueError('unexpected NaN metadata')
        return {'nonfinite': '+infinity' if value > 0 else '-infinity'}
    if isinstance(value, dict):
        return {key: finite_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_metadata(item) for item in value]
    return value


def selected_training_manifest(generated, indices):
    """Keep the locked cell masses when scheduling fewer indexed originals."""
    from collections import Counter
    selected = [dict(r) for r in generated['instances'] if r['template_index'] in indices]
    counts = Counter(r['cell_id'] for r in selected)
    cells = {r['cell_id'] for r in generated['instances']}
    if set(counts) != cells:
        raise ValueError('first collection must represent every locked cell')
    mass = {cell: sum(r['population_weight'] for r in generated['instances'] if r['cell_id'] == cell)
            for cell in cells}
    for row in selected:
        row['generation_population_weight'] = row['population_weight']
        row['population_weight'] = mass[row['cell_id']] / counts[row['cell_id']]
    return {**generated, 'instances': selected, 'instance_count': len(selected)}
