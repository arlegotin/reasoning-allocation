"""Read-only audit of Task11's first actual shard; no native solves or ranking."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from ra.collect import digest, label_leases, selected_training_manifest, residual_administration
from ra.runner import _atomic_json, _read_attempt
from ra.types import LeaseOutcome, NodeKey, ProgressRecord, SelectionBoundary
from ra.worker import strict_json


def main(output=Path('artifacts/checks/task11')):
    started = time.perf_counter_ns()
    root = Path('data/traces/train')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    schedule = strict_json((root / 'runs/schedule.json').read_text())
    sources = Path('artifacts/checks/task11/collection-source')
    for name, expected in schedule['inventory']['sources'].items():
        assert hashlib.sha256((sources / name).read_bytes()).hexdigest() == expected, name
    counts, lengths, behaviors, sizes = Counter(), Counter(), Counter(), Counter()
    originals, gains, pools = set(), [], []
    nanoseconds = Counter()
    attempts, eligibility_rows = [], []
    for path in sorted(root.rglob('attempt.json')):
        payload, final = _read_attempt(path.parent)
        assert final and payload['clock_aligned']
        trace = path.parent / 'trace'
        progress = [ProgressRecord(**strict_json(line)) for line in (path.parent / 'progress.jsonl').read_text().splitlines()]
        request = payload['request']
        assert request['phase'] == 'train'
        decisions = sorted(trace.glob('decision-*.json'))
        counts['attempts'] += 1
        counts[payload['status']] += 1
        counts['decisions'] += len(decisions)
        counts['max_decisions_per_attempt'] = max(counts['max_decisions_per_attempt'], len(decisions))
        summary = payload['resources']['collection']
        nanoseconds['historical_residual_administration'] += summary['residual_administration_ns']
        dispatched_entries = {strict_json(p.read_text())['entry_ns'] for p in trace.glob('dispatch-*.json')}
        nanoseconds['corrected_residual_administration'] += residual_administration(
            [SelectionBoundary(**b) for b in payload['resources']['selection_boundaries']], dispatched_entries=dispatched_entries)
        for file in trace.glob('*.npy'):
            sizes[file.stem.split('-')[0] + '_file_bytes'] += file.stat().st_size
            array = np.load(file, allow_pickle=False)
            assert np.isfinite(array).all()
            sizes[file.stem.split('-')[0] + '_payload_bytes'] += array.nbytes
        for decision in decisions:
            d = strict_json(decision.read_text())
            assert digest([[k['epoch'], k['number']] for k in d['pool_ids']]) == d['pool_hash']
            assert digest([d['pool_hash'], d['support_lengths']]) == d['support_hash']
            assert d['allocation']['seconds_prediction'] is None and d['allocation']['gain_prediction'] is None
            sizes['decision_metadata_bytes'] += decision.stat().st_size
            nanoseconds['local_feature_extraction'] += d['feature_extraction_ns']
            nanoseconds['pooled_feature_extraction'] += d['pooled_extraction_ns']
            nanoseconds['selected_and_pooled_array_storage'] += d['array_storage_ns']
            pools.append(len(d['pool_ids']))
            # Replay dedicated uniform/mixture stream conditional on the stored pool.
            import random
            def tuples(value):
                return tuple(tuples(x) for x in value) if isinstance(value, list) else value
            rng = random.Random()
            rng.setstate(tuples(d['behavior_rng_before']))
            explore = rng.random() < .2
            action = (rng.choice(d['pool_ids']), rng.choice(d['support_lengths'])) if explore else tuple(d['heuristic'])
            assert action == (d['allocation']['root'], d['allocation']['node_limit'])
            assert rng.getstate() == tuples(d['behavior_rng_after'])
            counts['exploration_draws'] += explore
        for label_path in trace.glob('label-*.json'):
            label = strict_json(label_path.read_text())
            outcome = strict_json((trace / label_path.name.replace('label-', 'outcome-')).read_text())
            o = LeaseOutcome(**{**outcome, 'root': NodeKey(**outcome['root'])})
            replay = label_leases([o], progress, request['deadline_ns'], request['p0'])[0]
            for key, value in replay.items():
                if key not in ('body_fit_eligible', 'duration_observation_known'):
                    assert value == label[key], (label_path, key)
            duration_known = (replay['duration_observation_known'] and payload['status'] != 'numerical_alarm'
                              and payload['resources'].get('timing_instrumentation_failed') is not True)
            eligibility_rows.append({'source_label': str(label_path),
                'source_label_sha256': hashlib.sha256(label_path.read_bytes()).hexdigest(),
                'source_attempt_manifest': str(path),
                'source_attempt_manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'attempt_id': payload['attempt_id'], 'request_id': payload['request_id'],
                'trace_index': label['trace_index'], 'body_ns': label['body_ns'], 'end_reason': label['end_reason'],
                'historical_body_fit_eligible': label['body_fit_eligible'],
                'duration_observation_known': duration_known, 'body_fit_eligible': duration_known})
            counts['eligibility_corrections'] += duration_known != label['body_fit_eligible']
            assert label['body_ns'] + label['admin_ns'] == label['full_ns']
            assert label['entry_ns'] <= label['snapshot_ns'] <= label['dispatch_ns'] <= label['end_ns']
            originals.add(request['instance_hash'])
            counts['labels'] += 1
            counts['zero_gain'] += label['endpoint_gain'] == 0
            counts['natural_completion_known'] += label['completion_outcome_known']
            counts['deadline_censored_leases'] += label['deadline_censored']
            counts['duration_lower_bound_leases'] += label['duration_lower_bound']
            counts['historical_body_fit_eligible'] += label['body_fit_eligible']
            counts['body_fit_eligible'] += duration_known
            for name in ('admin_ns', 'body_ns', 'full_ns'):
                nanoseconds[name] += label[name]
            lengths[label['node_limit']] += 1
            behaviors[request['method']] += 1
            gains.append(label['endpoint_gain'])
        attempts.append({'attempt_id': payload['attempt_id'], 'request_id': payload['request_id'],
                         'instance_id': request['instance_hash'], 'method': request['method'], 'status': payload['status'],
                         'code_hash': request['code_hash'], 'environment_hash': request['environment_hash'],
                         'collection': summary, 'end_to_end_ns': payload['resources']['end_to_end_ns'],
                         'overshoot_ns': payload['overshoot_ns'],
                         'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    generated = strict_json((root / 'inputs/manifest.json').read_text())
    protocol = strict_json((root / 'protocol.json').read_text())
    corrected = selected_training_manifest(generated, protocol['template_indices'])
    _atomic_json(output / 'derived-cohort-weights.json', {
        'source_selected_manifest_sha256': hashlib.sha256((root / 'inputs/selected-manifest.json').read_bytes()).hexdigest(),
        'reason': 'original selected manifest retained generator1/12 weights for6 of12; derived scheduled cohort preserves cell mass1/6',
        'instances': corrected['instances']}, immutable=True)
    eligibility_path = output / 'derived-duration-eligibility.json'
    _atomic_json(eligibility_path, {'schema_version': 2,
        'target': 'exact consumed dispatch-to-next-rebid or safe-terminal body nanoseconds, separate from natural completion',
        'raw_eligibility_status': 'superseded; Task12 must join this view by source label path/hash before fitting',
        'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          (Path('src/ra/collect.py'), Path('src/ra/runner.py'), Path(__file__))},
        'historical_eligible': counts['historical_body_fit_eligible'], 'eligible': counts['body_fit_eligible'],
        'changed': counts['eligibility_corrections'], 'rows': eligibility_rows}, immutable=True)
    report = {'version': 2, 'duration_eligibility': {'path': str(eligibility_path),
              'sha256': hashlib.sha256(eligibility_path.read_bytes()).hexdigest()}, 'counts': dict(counts), 'length_counts': dict(lengths), 'behavior_label_counts': dict(behaviors),
              'generated_originals': len(generated['instances']), 'scheduled_originals': len(corrected['instances']),
              'originals_with_labels': len(originals), 'original_ids': sorted(originals), 'sizes': dict(sizes),
              'nanoseconds': dict(nanoseconds), 'pool_min': min(pools), 'pool_max': max(pools),
              'maximum_observed_gain': max(gains), 'source_inventory': schedule['inventory']['sources'],
              'environment': schedule['inventory']['environment'], 'attempts': attempts,
              'audit_ns': time.perf_counter_ns() - started}
    _atomic_json(output / 'reconstruction.json', report, immutable=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('environment','attempts','source_inventory')}, indent=2))


if __name__ == '__main__':
    import sys
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path('artifacts/checks/task11'))
