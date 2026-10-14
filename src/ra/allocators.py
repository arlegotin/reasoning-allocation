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
