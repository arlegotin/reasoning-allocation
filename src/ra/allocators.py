"""Deterministic, primitive shared-adapter controls (B2)."""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import random
from typing import Protocol, Sequence

from ra.types import Allocation, DecisionContext, LeaseOutcome, NodeRecord


class Allocator(Protocol):
    def choose(self, context: DecisionContext, candidates: Sequence[NodeRecord],
               lease_lengths: Sequence[int]) -> Allocation: ...
    def observe(self, outcome: LeaseOutcome) -> None: ...


class _Control:
    def __init__(self, config: dict[str, object], seed: int):
        self.config = dict(config)
        self.rng = random.Random(seed)
        self.rebids = 0
        self.last_region = None

    def choose(self, context, candidates, lease_lengths):
        if (not candidates or len({n.key for n in candidates}) != len(candidates)
                or not lease_lengths or any(type(n) is not int or n <= 0 for n in lease_lengths)):
            raise ValueError('nonempty distinct candidates and positive supported lengths required')
        policy = self.config['policy']
        length = self.config.get('length', 1)
        if policy == 'budget_sensitive':
            remaining = max(0., (context.deadline_ns-context.snapshot_ns)/1e9)
            length = self.config['bin_lengths'][bisect.bisect_left(self.config['remaining_time_bins'], remaining)]
            policy = 'estimate' if self.rebids % 2 == 0 else 'bound'
        if length not in lease_lengths:
            raise ValueError('configured lease length is outside supported actions')
        probability = None
        if policy == 'uniform':
            node = self.rng.choice(sorted(candidates, key=lambda n: n.key))
            probability = 1/len(candidates)
        elif policy == 'round_robin_parent_groups':
            regions = sorted({n.parent or n.key for n in candidates})
            region = next((r for r in regions if self.last_region is None or r > self.last_region), regions[0])
            self.last_region = region
            node = min((n for n in candidates if (n.parent or n.key) == region), key=lambda n: (n.first_seen_selection, n.key))
        else:
            rank = {'estimate': lambda n: (n.native_estimate, n.native_lower_bound, n.key),
                    'bound': lambda n: (n.native_lower_bound, n.native_estimate, n.key),
                    'deepest': lambda n: (-n.depth, n.key),
                    'fifo': lambda n: (n.first_seen_selection, n.key)}[policy]
            node = min(candidates, key=rank)
        self.rebids += 1
        state = [self.config, self.rebids, repr(self.last_region), self.rng.getstate()]
        digest = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        return Allocation(node.key, length, 0., 0., None, probability, digest)

    def observe(self, outcome: LeaseOutcome) -> None:
        # Fixed controls do not fit outcome-dependent predictions.
        pass


def make_allocator(method_config: dict[str, object], seed: int) -> Allocator:
    if not isinstance(method_config, dict) or type(seed) is not int or seed < 0:
        raise ValueError('primitive method configuration and nonnegative seed required')
    policy = method_config.get('policy')
    if policy == 'local':
        return load_local_allocator(method_config)
    if policy not in ('estimate', 'bound', 'deepest', 'fifo', 'round_robin_parent_groups', 'uniform', 'budget_sensitive'):
        raise ValueError('unsupported allocation policy')
    allowed = {'policy', 'remaining_time_bins', 'bin_lengths'} if policy == 'budget_sensitive' else {'policy', 'length'}
    if method_config.keys()-allowed:
        raise ValueError('unknown policy configuration fields')
    if policy == 'budget_sensitive':
        bins, lengths = method_config.get('remaining_time_bins'), method_config.get('bin_lengths')
        if (not isinstance(bins, list) or any(isinstance(v, bool) or not isinstance(v, (float,int)) or not math.isfinite(v) or v <= 0 for v in bins)
                or any(b >= c for b,c in zip(bins,bins[1:])) or not isinstance(lengths,list)
                or len(lengths) != len(bins)+1 or any(type(v) is not int or v <= 0 for v in lengths)):
            raise ValueError('ordered finite remaining-time bins and positive bin lengths required')
    elif type(method_config.get('length', 1)) is not int or method_config.get('length',1) <= 0:
        raise ValueError('positive integer lease length required')
    return _Control(method_config, seed)


class BidderExpired(Exception):
    """Normal deadline expiry; runtime stops without issuing a new grant."""


class LocalBidder:
    def __init__(self, bundle, schema, *, c_min, fallback_length=4, clock=None, request_stop=None):
        import time
        if not math.isfinite(c_min) or c_min <= 0 or type(fallback_length) is not int or fallback_length <= 0:
            raise ValueError('positive measured floor and fixed fallback length required')
        self.bundle, self.schema = bundle, schema
        self.c_min, self.fallback_length = c_min, fallback_length
        self.clock, self.request_stop = clock or time.perf_counter_ns, request_stop
        self.ancestry = {}
        self._diagnostics = {}

    def choose(self, context, candidates, lease_lengths):
        from ra.features import build_features
        batch = build_features(context, candidates, lease_lengths, self.ancestry, self.schema)
        return self.choose_batch(context, candidates, batch)

    @property
    def last_diagnostics(self):
        return {k: v.tolist() if hasattr(v, "tolist") else v for k, v in self._diagnostics.items()}

    def choose_batch(self, context, candidates, batch):
        import time
        if context.entry_ns is None or context.entry_ns > context.snapshot_ns:
            raise ValueError('current rebid entry timing required')
        started = time.perf_counter_ns()
        prediction = self.bundle.predict(batch)
        prediction.validate(len(batch.action_rows))
        inference_ns = time.perf_counter_ns() - started
        self._prepared = (context, candidates, batch, prediction, inference_ns)
        self._prediction_hash = hashlib.sha256(b''.join(value.tobytes() for value in
            (prediction.gain, prediction.body_seconds, prediction.body_q90) if value is not None)).hexdigest()
        return self.refresh_batch()

    def refresh_batch(self):
        """Reprice cached predictions after trace preparation; never refit/reinfer."""
        import numpy as np
        context, candidates, batch, prediction, inference_ns = self._prepared
        now = self.clock()
        self.decision_ns = now
        administration = (now-context.entry_ns)/1e9
        if administration < 0: raise ValueError('invalid current administration timing')
        total = np.maximum(self.c_min, administration + prediction.body_seconds)
        rates = np.maximum(0., prediction.gain) / total
        surviving = (np.ones(len(rates), dtype=bool) if prediction.body_q90 is None else
                     prediction.body_q90 <= max(0., (context.deadline_ns-now)/1e9))
        tail_exception = not surviving.any()
        if tail_exception:
            surviving = np.array([length == 1 for _, length in batch.action_rows])
        # Keep arrays until after the final decision. Large diagnostic conversions
        # and hashes must not precede dispatch after the clock has been sampled.
        self._diagnostics = {'gain': prediction.gain, 'body_seconds': prediction.body_seconds,
            'body_q90': prediction.body_q90, 'rates': rates, 'surviving': surviving,
            'administration_seconds': administration, 'decision_ns': now,
            'prediction_ns': inference_ns, 'feature_extraction_ns': batch.extraction_ns,
            'expired': now >= context.deadline_ns, 'fallback': False, 'tail_exception': bool(tail_exception)}
        if now >= context.deadline_ns:
            if self.request_stop is not None: self.request_stop()
            raise BidderExpired()
        indices = np.flatnonzero(surviving).tolist()
        if not indices: raise ValueError('length-one deadline fallback requires supported action')
        if max(rates[indices]) > 0:
            selected = min(indices, key=lambda i: (-rates[i], batch.action_rows[i][1], batch.action_rows[i][0].number))
        else:
            self._diagnostics['fallback'] = True
            nodes = {n.key: n for n in candidates}
            root = min({batch.action_rows[i][0] for i in indices}, key=lambda key:
                (nodes[key].native_estimate, nodes[key].native_lower_bound, key.number))
            indices = [i for i in indices if batch.action_rows[i][0] == root]
            lengths = {batch.action_rows[i][1] for i in indices}
            length = max((n for n in lengths if n <= self.fallback_length), default=min(lengths))
            selected = next(i for i in indices if batch.action_rows[i][1] == length)
        root, length = batch.action_rows[selected]
        state = hashlib.sha256(json.dumps([self._prediction_hash, now, selected, self.c_min,
            self.fallback_length, self._diagnostics['fallback'], bool(tail_exception)]).encode()).hexdigest()
        return Allocation(root, length, float(prediction.gain[selected]), float(total[selected]),
            None if prediction.body_q90 is None else float(prediction.body_q90[selected]), None, state)

    def observe(self, outcome):
        pass  # Deployment does not fit on request outcomes.


def validate_local_config(config):
    from pathlib import Path
    required = {'policy', 'model_path', 'model_hash', 'schema_path', 'schema_hash', 'c_min', 'fallback_length'}
    if set(config) != required or config['policy'] != 'local':
        raise ValueError('invalid local model configuration')
    for key in ('model_path', 'schema_path'):
        if not isinstance(config[key], str) or not Path(config[key]).is_absolute():
            raise ValueError('absolute model/schema path required')
    for key in ('model_hash', 'schema_hash'):
        if not isinstance(config[key], str) or len(config[key]) != 64 or any(c not in '0123456789abcdef' for c in config[key]):
            raise ValueError('invalid model/schema hash')
    if (type(config['c_min']) not in (int, float) or not math.isfinite(config['c_min']) or config['c_min'] <= 0
            or type(config['fallback_length']) is not int or config['fallback_length'] <= 0):
        raise ValueError('invalid floor/fallback')


def load_local_allocator(config):
    import time
    from pathlib import Path
    started = time.perf_counter_ns()
    validate_local_config(config)
    from ra.config import load_feature_schema
    from ra.models import ModelBundle
    raw = Path(config['model_path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['model_hash']:
        raise ValueError('model hash mismatch')
    schema = load_feature_schema(Path(config['schema_path']))
    if schema.hash != config['schema_hash']:
        raise ValueError('schema hash mismatch')
    bundle = ModelBundle.load(config['model_path'])
    if bundle.schema_hash != schema.hash:
        raise ValueError('model schema mismatch')
    bidder = LocalBidder(bundle, schema, c_min=config['c_min'], fallback_length=config['fallback_length'])
    bidder.loading_ns, bidder.model_bytes = time.perf_counter_ns()-started, len(raw)
    return bidder
