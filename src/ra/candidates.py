"""Deterministic primitive candidate support; excluded nodes remain live."""
from dataclasses import dataclass
import hashlib
import json
import random
from typing import Sequence

from ra.types import NodeKey, NodeRecord


@dataclass(frozen=True, slots=True)
class CandidatePool:
    records: tuple[NodeRecord, ...]
    ids: tuple[NodeKey, ...]
    pool_hash: str
    strata: tuple[tuple[str, tuple[NodeKey, ...]], ...]
    rng_state_before: tuple
    rng_state_after: tuple
    frontier_size: int


def build_pool(frontier: Sequence[NodeRecord], k: int | None, rng: random.Random) -> CandidatePool:
    if k is not None and (type(k) is not int or k <= 0):
        raise ValueError('pool size must be a positive integer or None')
    nodes = sorted(frontier, key=lambda n: n.key)
    if len({n.key for n in nodes}) != len(nodes):
        raise ValueError('duplicate live node keys')
    before = rng.getstate()
    strata = []
    if k is None or k < 5 or len(nodes) <= k:
        chosen = nodes
        strata.append(('all', tuple(n.key for n in chosen)))
    else:
        chosen, selected = [], set()
        ranks = (('estimate', lambda n: (n.native_estimate, n.key)),
                 ('lower_bound', lambda n: (n.native_lower_bound, n.key)),
                 ('depth', lambda n: (-n.depth, n.key)),
                 ('age', lambda n: (n.first_seen_selection, n.key)))
        for name, rank in ranks:
            group = [n for n in sorted(nodes, key=rank) if n.key not in selected][:k // 5]
            chosen.extend(group)
            selected.update(n.key for n in group)
            strata.append((name, tuple(n.key for n in group)))
        group = rng.sample([n for n in nodes if n.key not in selected], k - len(chosen))
        chosen.extend(group)
        strata.append(('random', tuple(n.key for n in group)))
    ids = tuple(n.key for n in chosen)
    canonical = json.dumps([[key.epoch, key.number] for key in ids], separators=(',', ':'))
    return CandidatePool(tuple(chosen), ids, hashlib.sha256(canonical.encode()).hexdigest(),
                         tuple(strata), before, rng.getstate(), len(nodes))
