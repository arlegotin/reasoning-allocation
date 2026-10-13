"""Small design checks, not SCIP or MacBook performance experiments."""
from __future__ import annotations
import hashlib
import json
import platform
import random
import sys
from functools import lru_cache
from pathlib import Path


def choose(weights: list[tuple[int, int]], r: float) -> int:
    total = sum(w for _, w in weights)
    assert total > 0 and 0 <= r < 1
    target = r * total
    cumulative = 0
    for key, weight in weights:
        cumulative += weight
        if target < cumulative:
            return key
    raise AssertionError('Invalid weights')


def coupling(seed: int, steps: int = 200) -> int:
    rng = random.Random(seed)
    # Administrative copies share one computation and one evidence record.
    copies: dict[int, list[int]] = {i: [100] for i in range(10)}
    queue = {i: 100 for i in range(10)}
    evidence = {i: hashlib.sha256(str(i).encode()).hexdigest() for i in range(10)}
    original_evidence = evidence.copy()
    treasury = spent = decisions = 0
    work_pop = {i: 0 for i in range(10)}
    work_queue = work_pop.copy()
    for step in range(steps):
        if step % 7 == 0:
            p = rng.randrange(10)
            if copies[p]:
                mass = copies[p].pop()
                copies[p] += [mass // 2, mass - mass // 2]
        if step % 43 == 42:
            p = rng.randrange(10)
            treasury += queue[p]
            queue[p] = 0
            copies[p] = []
        if step % 47 == 46 and treasury:
            p = rng.randrange(10)
            queue[p] += treasury
            copies[p].append(treasury)
            treasury = 0
        assert all(sum(copies[p]) == queue[p] for p in queue)
        assert sum(queue.values()) + treasury + spent == 1000
        if sum(queue.values()) == 0:
            break
        r = rng.random()
        p_pop = choose([(p, w) for p in sorted(copies) for w in copies[p]], r)
        p_queue = choose(sorted(queue.items()), r)
        assert p_pop == p_queue
        for j, mass in enumerate(copies[p_pop]):
            if mass:
                copies[p_pop][j] -= 1
                break
        queue[p_queue] -= 1
        spent += 1
        work_pop[p_pop] += 1
        work_queue[p_queue] += 1
        decisions += 1
        assert work_pop == work_queue
        assert evidence == original_evidence
        assert sum(queue.values()) + treasury + spent == 1000
    return decisions


def delayed_reward() -> dict[str, object]:
    def utility(a: int, b: int) -> float:
        return max(0.6 if a >= 1 else 0.0, 1.0 if b >= 2 else 0.0)
    @lru_cache(None)
    def optimal(a: int, b: int, left: int) -> tuple[float, str]:
        if left == 0:
            return utility(a, b), ''
        options = []
        if a < 1:
            v, path = optimal(a + 1, b, left - 1)
            options.append((v, 'A' + path))
        if b < 2:
            v, path = optimal(a, b + 1, left - 1)
            options.append((v, 'B' + path))
        return max(options) if options else (utility(a, b), '')
    a = b = 0
    for _ in range(2):
        choices = []
        if a < 1:
            choices.append((utility(a + 1, b) - utility(a, b), 'A'))
        if b < 2:
            choices.append((utility(a, b + 1) - utility(a, b), 'B'))
        _, selected = max(choices)
        a += selected == 'A'
        b += selected == 'B'
    result = {'greedy_terminal_utility': utility(a, b),
              'optimal_terminal_utility': optimal(0, 0, 2)[0],
              'optimal_path': optimal(0, 0, 2)[1]}
    assert result == {'greedy_terminal_utility': 0.6,
                      'optimal_terminal_utility': 1.0, 'optimal_path': 'BB'}
    return result


def run_reference() -> dict[str, object]:
    # Reject an entry-point mode that would skip the supplied invariant checks.
    if not __debug__:
        raise RuntimeError('Appendix A requires enabled assertions (run Python without -O)')
    decisions = sum(coupling(seed) for seed in range(512))
    # One Bayes update; copying the record must not repeat the observation.
    posterior_once = 0.5 * 0.8 / (0.5 * 0.8 + 0.5 * 0.2)
    posterior_double_counted = 0.5 * 0.8**2 / (0.5 * 0.8**2 + 0.5 * 0.2**2)
    assert abs(posterior_once - 0.8) < 1e-12
    assert posterior_double_counted > posterior_once
    q, c, h = 0.8, 100.0, 40.0  # Illustrative microseconds; not measured hardware.
    results = {
        'environment': {'system': platform.system(), 'machine': platform.machine(),
                        'python': sys.version.split()[0]},
        'queue_population': {'seeds': 512, 'matched_decisions': decisions,
                            'budget_and_evidence_checks': 'passed'},
        'delayed_reward': delayed_reward(),
        'bayes_duplicate': {'single_observation': posterior_once,
                            'incorrect_double_counting': posterior_double_counted},
        'illustrative_overhead': {
            'baseline_work_us': c, 'new_work_fraction': q, 'bid_us': h,
            'time_ratio_lease_1': q * (c + h) / c,
            'time_ratio_lease_8': q * (c + h / 8) / c,
            'maximum_overhead_per_new_node_us': c * (1 / q - 1)}}
    return results


def main() -> None:
    # Entry-point adaptation only: mathematical procedures above are supplied.
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('artifacts/checks/appendix_a.json'))
    args = parser.parse_args()
    results = run_reference()
    payload = json.dumps(results, indent=2) + '\n'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding='utf-8')
    print(payload, end='')


if __name__ == '__main__':
    main()
