"""Candidate support must not prune live nodes or depend on input order."""
import hashlib
import json
import random

import pytest

from ra.candidates import build_pool
from ra.types import NodeKey, NodeRecord


@pytest.fixture
def overlapping_frontier_100():
    return [NodeRecord(NodeKey(0, i), None, i, float(100-i), float(100-i),
                       100-i, str(i), 'leaf') for i in range(1, 101)]


def test_pool_overlap_fills_unique_slots(overlapping_frontier_100):
    before = tuple(node.key for node in overlapping_frontier_100)
    pool = build_pool(overlapping_frontier_100, 32, random.Random(7))
    assert len({node.key for node in pool.records}) == 32
    assert tuple(node.key for node in overlapping_frontier_100) == before
    assert [k.number for k in pool.strata[0][1]] == [100, 99, 98, 97, 96, 95]
    assert [k.number for k in pool.strata[1][1]] == [94, 93, 92, 91, 90, 89]
    assert [k.number for k in pool.strata[2][1]] == [88, 87, 86, 85, 84, 83]
    assert [k.number for k in pool.strata[3][1]] == [82, 81, 80, 79, 78, 77]


@pytest.mark.parametrize('k', [None, 1, 4, 100, 128])
def test_all_frontier_modes_keep_every_node(overlapping_frontier_100, k):
    rng = random.Random(7)
    before = rng.getstate()
    pool = build_pool(overlapping_frontier_100, k, rng)
    assert pool.ids == tuple(n.key for n in overlapping_frontier_100)
    assert rng.getstate() == before
    assert pool.frontier_size == 100


def test_rank_ties_and_rng_hash_parity(overlapping_frontier_100):
    nodes = [NodeRecord(n.key, None, 0, 0., 0., 0, '', 'leaf')
             for n in overlapping_frontier_100]
    rng = random.Random(7)
    pool = build_pool(list(reversed(nodes)), 32, rng)
    replay = random.Random()
    replay.setstate(pool.rng_state_before)
    duplicate = build_pool(nodes, 32, replay)
    assert pool == duplicate
    assert pool.rng_state_after == rng.getstate() == replay.getstate()
    assert [k.number for k in pool.ids[:24]] == list(range(1, 25))
    payload = json.dumps([[k.epoch, k.number] for k in pool.ids], separators=(',', ':'))
    assert pool.pool_hash == hashlib.sha256(payload.encode()).hexdigest()


@pytest.mark.parametrize('k', [0, -1, True, 3.5])
def test_invalid_pool_size_is_rejected(k):
    with pytest.raises(ValueError):
        build_pool([], k, random.Random(7))


def test_duplicate_keys_cannot_inflate_pool(overlapping_frontier_100):
    with pytest.raises(ValueError, match='duplicate'):
        build_pool(overlapping_frontier_100 * 2, 32, random.Random(7))
