"""One bounded public discovery snapshot; diagnostic only, no lease labels/fitting."""
import os
import time
STARTED_NS = time.perf_counter_ns()
os.environ.update({key: '1' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                                       'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')})

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import sys

import numpy as np
from pyscipopt import Model, quicksum
from scipy.sparse import csr_matrix

from ra.config import load_feature_schema
from ra.exact import canonical_cover
from ra.features import WHITELIST, build_features
from ra.observer import Observer
from ra.provenance import instance_hash
from ra.scip_backend import ScipBackend
from ra.types import AncestrySummary, CoverInstance, DecisionContext


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else 'artifacts/checks/task10/discovery')
    out.mkdir(parents=True, exist_ok=False)
    manifest_path = Path('data/pilot/discovery-256/manifest.json')
    manifest = json.loads(manifest_path.read_text())
    assert manifest['split'] == 'discovery'
    # Prospectively choose a public cell from dimensions, never an outcome.
    record = next(item for item in manifest['instances'] if item['cell']['family'] == 'uniform'
                  and item['cell']['rows'] == 512 and item['cell']['degree'] == 16)
    input_path = manifest_path.parent/record['path']
    assert sha(input_path) == record['sha256']
    payload = json.loads(input_path.read_text())
    rows, costs = payload['rows'], tuple(payload['costs'])
    rr = [i for i, row in enumerate(rows) for _ in row]
    cc = [j for row in rows for j in row]
    incidence = csr_matrix(([1]*len(cc), (rr, cc)), shape=tuple(payload['shape']))
    instance = CoverInstance(payload['instance_id'], payload['template_id'], payload['cell_id'],
                             incidence, costs, payload['lineage'])
    canonical_cover(instance)
    assert instance_hash(instance) == record['instance_id']
    schema = load_feature_schema(Path('configs/features.json'))
    lengths = json.loads(Path('configs/exploratory.json').read_text())['lease_lengths']
    scale, offset = 3, 7
    model = Model('task10-diagnostic')
    model.hideOutput()
    model.setIntParam('parallel/maxnthreads', 1)
    model.setIntParam('lp/threads', 1)
    model.setRealParam('limits/time', 5.)
    defaults = model.getParams()
    variables = [model.addVar(name=f'x{i}', vtype='B', obj=scale*cost) for i, cost in enumerate(costs)]
    model.addObjoffset(offset)
    for row in rows:
        model.addCons(quicksum(variables[j] for j in row) >= 1)
    observer = Observer(instance, request_id='task10-discovery', objective_scale=scale, objective_offset=offset)
    observer.validate_incumbent((1,)*len(costs), time.perf_counter_ns())
    anchor = model.createSol()
    for variable in variables:
        model.setSolVal(anchor, variable, 1.)
    assert model.addSol(anchor, free=True)
    captured = {}

    def choose(records):
        if not captured and any(node.depth > 0 for node in records):
            snapshot = time.perf_counter_ns()
            pool = sorted(records, key=lambda node: node.key.number)[:128]
            summaries = {}
            for node in pool:
                parent = backend.resolve_live(node.key).getParent()
                summaries[node.key] = AncestrySummary(None if parent is None else float(parent.getLowerbound()),
                                                      None if parent is None else float(parent.getEstimate()))
            primal, dual, local_utility = backend.validated_progress()
            improved = max((progress.child_ns for progress in observer.records), default=None)
            ctx = DecisionContext('task10-discovery', snapshot, STARTED_NS+5_000_000_000,
                                  local_utility, primal, dual, float(model.getLowerbound()),
                                  float(model.getCutoffbound()), backend.processed_nodes, len(records), schema.hash,
                                  start_ns=STARTED_NS, selection_count=backend.selection_count,
                                  original_columns=len(costs), original_rows=len(rows),
                                  original_density=incidence.nnz/(len(costs)*len(rows)),
                                  initial_primal_original=float(observer.p0), initial_dual_original=observer.d0,
                                  last_verified_improvement_ns=improved, native_incumbent_count=int(model.getNSols()),
                                  past_throughput_per_second=backend.processed_nodes/((snapshot-STARTED_NS)/1e9),
                                  solver_infinity=float(model.infinity()))
            batch = build_features(ctx, pool, lengths, summaries, schema)
            assert batch.matrix.dtype == np.float64 and np.isfinite(batch.matrix).all()
            assert {spec.name for spec in schema.features} == set(WHITELIST)
            transformed_sol = float(model.getSolObjVal(model.getBestSol(), original=False))
            original_sol = float(model.getSolObjVal(model.getBestSol(), original=True))
            assert original_sol == observer.primal
            verified_objective = observer.assignments[observer.incumbent_hash].objective
            assert original_sol == scale*verified_objective+offset
            captured.update({'context': asdict(ctx), 'candidates': [asdict(node) for node in pool],
                             'ancestry': [{'key': asdict(key), 'summary': asdict(value)} for key, value in summaries.items()],
                             'action_rows': [[asdict(key), length] for key, length in batch.action_rows],
                             'feature_names': schema.names, 'schema_hash': schema.hash,
                             'dimension': list(batch.matrix.shape), 'matrix_bytes': batch.matrix_bytes,
                             'feature_extraction_ns': batch.extraction_ns,
                             'whole_snapshot_extraction_ns': time.perf_counter_ns()-snapshot,
                             'original_dimensions': list(incidence.shape),
                             'transformed_dimensions': [model.getNConss(), model.getNVars()],
                             'original_objective': original_sol, 'transformed_objective': transformed_sol,
                             'verified_unscaled_original_objective': verified_objective,
                             'objective_scale': scale, 'objective_offset': offset,
                             'original_offset': model.getObjoffset(original=True),
                             'transformed_offset': model.getObjoffset(original=False),
                             'snapshot_is_preallocation': True, 'lineage_history_available': False})
            np.save(out/'features.npy', batch.matrix, allow_pickle=False)
            captured['matrix_sha256'] = sha(out/'features.npy')
            captured['matrix_file_bytes'] = (out/'features.npy').stat().st_size
            backend.request_stop()
        return min(records, key=lambda node: (node.native_estimate, node.native_lower_bound, node.key.number)).key

    backend = ScipBackend(model, costs=costs, rows=rows, choose=choose, observer=observer,
                          objective_scale=scale, objective_offset=offset)
    setup_end = time.perf_counter_ns()
    try:
        backend.optimize()
        assert captured, 'no nonroot snapshot; retain failure, do not silently retry'
        safe_return = time.perf_counter_ns()
        captured.update({'native_status': str(model.getStatus()), 'setup_imports_ns': setup_end-STARTED_NS,
                         'native_and_snapshot_ns': safe_return-setup_end,
                         'selector_enhancement_overrides': {name: value for name, value in model.getParams().items()
                             if name.startswith(('presolving/', 'heuristics/', 'separating/')) and defaults[name] != value},
                         'purpose': 'single bounded discovery feature/objective inspection; no comparative performance claim',
                         'source_split': 'discovery', 'input_path': str(input_path), 'input_sha256': sha(input_path),
                         'manifest_sha256': sha(manifest_path), 'instance_id': instance.instance_id,
                         'template_id': instance.template_id, 'cell_id': instance.cell_id, 'lineage': instance.lineage,
                         'solver_seed': 0, 'base_commit': 'aaac6f9',
                         'source_hashes': {path: sha(path) for path in ('checks/task10_features.py', 'src/ra/features.py',
                             'src/ra/types.py', 'src/ra/config.py', 'src/ra/scip_backend.py', 'configs/features.json',
                             'configs/exploratory.json')},
                         'pyscipopt_version': __import__('pyscipopt').__version__,
                         'solver_version': [model.getMajorVersion(), model.getMinorVersion(), model.getTechVersion()]})
    finally:
        model.freeProb()
    captured['through_native_release_ns'] = time.perf_counter_ns()-STARTED_NS
    captured['process_cpu_ns'] = round((resource.getrusage(resource.RUSAGE_SELF).ru_utime+
                                        resource.getrusage(resource.RUSAGE_SELF).ru_stime)*1e9)
    captured['cost_scope'] = 'script body imports/setup/snapshot/native/release; external wrapper includes interpreter/return/report tails'
    (out/'inspection.json').write_text(json.dumps(captured, sort_keys=True, indent=2, allow_nan=False)+'\n')
    print(json.dumps({name: captured[name] for name in ('dimension', 'matrix_bytes', 'feature_extraction_ns',
                                                      'original_objective', 'transformed_objective', 'native_status')}))


if __name__ == '__main__':
    main()
