"""Read-only Task12 reconstruction; no fitting, solving or protected data."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import statistics
import time
from types import SimpleNamespace


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)+'\n')
def distribution(values):
    return {'n':len(values),'min':min(values),'median':statistics.median(values),'max':max(values)} if values else None


def reconstruct():
    started=time.perf_counter_ns()
    from ra.runner import _read_attempt
    from ra.train import load_training_rows, diagnostics, validation_scores
    from ra.models import ModelBundle
    from ra.config import load_feature_schema
    out=Path('artifacts/checks/task12')
    roots=[Path('artifacts/models'),Path('data/traces/task12-odd'),Path('data/traces/task12-learned'),out]
    # Read each physical attempt once, including the interrupted coordinator's partial request.
    attempts=[]
    for root in roots:
        for path in sorted(root.rglob('request.json')):
            if not (path.parent/'bootstrap.json').exists(): continue
            a,complete=_read_attempt(path.parent)
            receipt=path.parent/'accounting.json'
            if receipt.exists():
                accounting=read(receipt)
                assert accounting['attempt_id']==a['attempt_id']
                if complete: assert accounting['manifest_sha256']==sha(path.parent/'attempt.json')
                a['resources']['publication_ns']=accounting['publication_ns']
                a['resources']['full_observed_ns']=accounting['total_observed_ns']
            attempts.append((path.parent,a,complete))
    assert len({a['attempt_id'] for _,a,_ in attempts})==len(attempts)
    costs=defaultdict(list)
    for path,a,complete in attempts:
        group=('final' if path.is_relative_to(Path('artifacts/models/final')) else
               'expanded' if path.is_relative_to(Path('artifacts/models/expanded')) else
               'first-valid' if path.is_relative_to(Path('artifacts/models/first-valid')) else
               'first-corrected-interrupted' if path.is_relative_to(Path('artifacts/models/first-corrected')) else
               'initial-failed-fit' if path.is_relative_to(Path('artifacts/models')) else
               'odd-collection' if path.is_relative_to(Path('data/traces/task12-odd')) else
               'learned-round' if path.is_relative_to(Path('data/traces/task12-learned')) else
               'export-diagnostic' if path.is_relative_to(out/'diagnostic-export') else 'pickle-diagnostic')
        costs[group].append((a,complete))
    cost_summary={}
    for group,rows in costs.items():
        cost_summary[group]={'attempts':len(rows),'partial_attempts':sum(not complete for _,complete in rows),
            'status_counts':dict(Counter(a.get('status','unfinished') for a,_ in rows)),
            'end_to_end_ns_or_lower_bound':sum(a['resources'].get('end_to_end_ns',0) for a,_ in rows),
            'publication_ns':sum(a['resources'].get('publication_ns',0) for a,_ in rows),
            'full_request_ns_or_lower_bound':sum(a['resources'].get('full_observed_ns',a['resources'].get('end_to_end_ns',0)) for a,_ in rows),
            'missing_publication_receipts':sum('publication_ns' not in a['resources'] for a,_ in rows),
            'worker_cpu_ns_or_lower_bound':sum(max(a['resources'].get('worker_cpu_ns',0),a['resources'].get('worker_sampled_cpu_ns_lower_bound',0)) for a,_ in rows),
            'trace_bytes':sum(a['resources'].get('trace_bytes',0) for a,_ in rows),
            'model_bytes_loaded':sum(a['resources'].get('model_bytes',0) for a,_ in rows),
            'overshoot_ns':sum(a.get('overshoot_ns',0) for a,_ in rows),
            'max_worker_rss_bytes':max(max(a['resources'].get('worker_peak_rss_bytes',0),a['resources'].get('worker_sampled_peak_rss_bytes',0)) for a,_ in rows)}
    final=read('artifacts/models/final/model-card.json'); selected=final['selected_deployment']
    selected_path=Path(selected['allocator']['model_path'])
    assert sha(selected_path)==selected['allocator']['model_hash']
    final_attempts=[a for path,a,complete in attempts if path.is_relative_to(Path('artifacts/models/final'))]
    scores=validation_scores([SimpleNamespace(request=SimpleNamespace(**a['request']),available=SimpleNamespace(**a['available'])) for a in final_attempts],
                             {int(k):v for k,v in final['validation_budget_weights'].items()})
    assert scores==final['validation_weighted_scores']
    grouped=defaultdict(list)
    for a in final_attempts: grouped[(a['request']['method'],a['request']['budget_ns'])].append(a)
    cohort={(a['request']['instance_hash'],a['request']['solver_seed']) for a in final_attempts}
    assert len(cohort)==6
    comparison=[]
    for budget in sorted({budget for _,budget in grouped}):
        own=grouped[(final['selected'],budget)]
        keys=lambda a:(a['request']['instance_hash'],a['request']['solver_seed'])
        assert {keys(a) for a in own}==cohort
        for baseline in ('B0','B1-tuned','B1-no-plunge','pre-refit-ridge1'):
            other={keys(a):a for a in grouped[(baseline,budget)]}
            assert set(other)==cohort
            pairs=[(a,other[keys(a)]) for a in own]
            available=[(a,b) for a,b in pairs if a['available']['primal_original'] is not None and b['available']['primal_original'] is not None]
            comparison.append({'budget_ns':budget,'baseline':baseline,'originals':6,
                'mean_utility_difference':statistics.mean(a['available']['utility']-b['available']['utility'] for a,b in pairs),
                'mean_primal_cost_difference':statistics.mean(a['available']['primal_original']-b['available']['primal_original'] for a,b in available) if available else None,
                'paired_available_assignments':len(available),
                'mean_dual_cost_difference':statistics.mean(a['available']['dual_original']-b['available']['dual_original'] for a,b in pairs)})
    selected_attempts=[a for a in final_attempts if a['request']['method']==final['selected']]
    decision_rows=[d for a in selected_attempts for d in a['resources'].get('bidder_diagnostics',[])]
    deployment={key:distribution([a['resources'][key] for a in selected_attempts if key in a['resources']]) for key in
                ('model_loading_ns','worker_peak_rss_bytes','end_to_end_ns','full_observed_ns','publication_ns','worker_cpu_ns','trace_bytes')}
    deployment.update({key:distribution([d[key] for d in decision_rows]) for key in ('prediction_ns','feature_extraction_ns')})
    deployment.update(decisions=len(decision_rows),zero_bid_fallbacks=sum(d['fallback'] for d in decision_rows),
                      expired_scoring=sum(d['expired'] for d in decision_rows),
                      raw_negative_gain_predictions=sum(v<0 for d in decision_rows for v in d['gain']),
                      raw_negative_body_predictions=sum(v<0 for d in decision_rows for v in d['body_seconds']),
                      status_counts=dict(Counter(a['status'] for a in selected_attempts)))
    schema=load_feature_schema(Path('configs/features.json'))
    data=load_training_rows([Path('data/traces/train'),Path('data/traces/task12-odd'),Path('data/traces/task12-learned/runs')],schema)
    model=ModelBundle.load(selected_path)
    data_card={'schema':asdict(schema),'schema_file':{'path':'configs/features.json','sha256':sha('configs/features.json')},'schema_hash':schema.hash,'target_sensitivity':data['sensitivity'],'training_originals':sorted(set(data['originals'])),
        'originals':len(set(data['originals'])),'rows':len(data['gain']),'zero_gains':int((data['gain']==0).sum()),
        'support_by_length':dict(Counter(str(length) for _,length in data['batch'].action_rows)),
        'support_by_budget':dict(Counter(str(b) for b in data['budgets'])),
        'original_weight_rule':'N_rows/(N_originals * rows_of_this_original), separately within eligible gain and body subsets',
        'preprocessing':final['preprocessing'],'correction_sha256':data['correction_sha256'],
        'pooled_fields_used':False,'gain_mse_unit':'squared original utility fraction; unscaled',
        'body_mse_unit':'seconds squared; unscaled','in_sample_diagnostics':diagnostics(model,data),
        'data_inventory_sha256':sha('artifacts/models/final/data-inventory.json'),
        'state_shift_evidence':{'path':'artifacts/checks/task12/learned-state-shift.json','sha256':sha(out/'learned-state-shift.json')}}
    # Old histogram models evaluate the new behavior/budget rows without refitting.
    learned=load_training_rows([Path('data/traces/task12-learned/runs')],schema)
    tail_shift={}
    for name in ('hist7-seed17','hist15-seed17'):
        asset=Path('artifacts/models/expanded')/(name+'.json')
        tail_shift[name]={'model_sha256':sha(asset),'diagnostics':diagnostics(ModelBundle.load(asset),learned),
                         'scope':'unseen behavior/budget labels on previously trained originals; no independent-original coverage guarantee'}
    write(out/'tail-state-shift.json',tail_shift)
    data_card['tail_state_shift']={'path':str(out/'tail-state-shift.json'),'sha256':sha(out/'tail-state-shift.json')}
    fits=[]
    for directory in (Path('artifacts/models'),Path('artifacts/models/first-corrected'),Path('artifacts/models/first-valid'),Path('artifacts/models/expanded'),Path('artifacts/models/final')):
        for path in sorted(directory.glob('*.fit.json')):
            item=read(path)
            fits.append({'path':str(path),'sha256':sha(path),**{k:item[k] for k in ('name','candidate','seed','status','fit_wall_ns','fit_cpu_ns')},
                         'error':item.get('error'),'curves':item['curves'],'counts':item.get('counts'),
                         'asset_sha256':item.get('sha256'),'original_asset_sha256':item.get('original_sha256')})
    model_card={'selected':selected,'selected_model_sha256':sha(selected_path),'model_bytes':selected_path.stat().st_size,
        'format':'numeric-threshold-v1; export version1; parity-validated scikit-learn1.9.1; exact masks/preprocessing retained',
        'targets':final['targets'],'fits':fits,'fitted_seed_interpretation':'seeds17/43 are separate executions of deterministic estimators on the same data; they do not estimate independent training-distribution variance',
        'validation_cohort':[{'instance_hash':instance,'solver_seed':seed} for instance,seed in sorted(cohort)],
        'independent_originals':12,'validation_originals':6,'validation_solver_seeds':[17],
        'validation_weighted_scores':scores,'budget_weights':final['validation_budget_weights'],
        'comparison':comparison,'deployment_costs':deployment,'all_attempt_costs':cost_summary,
        'fit_wall_ns':sum(f['fit_wall_ns'] for f in fits),'fit_cpu_ns':sum(f['fit_cpu_ns'] for f in fits),
        'inference_and_extraction_are_nested_not_additive_to_request_wall':True,
        'limits':'Exploratory finite grid, single host/solver seed and six validation originals; no learned advantage; Task13 controls,14 access/literature and15 freeze pending'}
    write('docs/superpowers/evidence/task12-data-card.json',data_card)
    write('docs/superpowers/evidence/task12-model-card.json',model_card)
    from ra.worker import THREAD_SETTINGS
    environment=read('artifacts/models/final/runtime-inventory.json')['environment']
    write('docs/superpowers/evidence/task12-environment-card.json',{'environment_hash':final['environment_hash'],
        'environment':environment,'worker_thread_environment':THREAD_SETTINGS,'native_threads':1,
        'hardware':'Previously discovered Apple M3 Max,36GiB; same host as Task1/9; native ARM64',
        'cold_request_boundary':'new worker process; imports/model loading/native setup/observation/finalization/publication charged'})
    actual_sources={}
    for name,path in [('failed','artifacts/models/reconstructed-failed-source'),('interrupted','artifacts/models/first-corrected/source'),
                      ('first-valid','artifacts/models/first-valid/source'),('expanded','artifacts/models/expanded/source'),
                      ('learned','data/traces/task12-learned/source'),('final','artifacts/models/final/source')]:
        actual_sources[name]={str(p):sha(p) for p in sorted(Path(path).glob('*.py'))}
    inventory={str(p):sha(p) for root in roots for p in sorted(root.rglob('*')) if p.is_file()
               and p.name not in ('raw-inventory.json','reconstruction.json','reconstruction-receipt.json','reconstruction-output.txt')}
    write(out/'raw-inventory.json',inventory)
    evidence={'schema_version':1,'implementation_commit':'485d27c','raw_inventory':{'path':str(out/'raw-inventory.json'),
        'sha256':sha(out/'raw-inventory.json'),'files':len(inventory)},'actual_source_snapshots':actual_sources,
        'current_sources':{str(p):sha(p) for p in sorted(Path('src/ra').glob('*.py'))},
        'config_and_tests':{str(p):sha(p) for p in [*sorted(Path('configs').glob('*task12*')),Path('configs/exploratory.json'),
            Path('protocol/collection-task12.json'),Path('protocol/task12-learned-round.json'),Path('configs/features.json'),Path('tests/test_models.py'),Path('tests/test_bidder.py'),
            Path('tests/test_lease_labels.py'),Path(__file__)]},
        'cards':{str(p):sha(p) for p in [Path('docs/superpowers/evidence/task12-data-card.json'),Path('docs/superpowers/evidence/task12-model-card.json'),Path('docs/superpowers/evidence/task12-environment-card.json')]},
        'actual_environment_hash':final['environment_hash'],'actual_code_hash':final['source_hash'],
        'environment_inventory':{'path':'artifacts/models/final/runtime-inventory.json','sha256':sha('artifacts/models/final/runtime-inventory.json')},
        'all_attempt_costs':cost_summary,'public_request_count':len(attempts),'fit_count':len(fits),
        'failed_fits':sum(f['status']=='failed' for f in fits),'selected':selected,'weighted_scores':scores,
        'data_summary':{k:data_card[k] for k in ('originals','rows','zero_gains','target_sensitivity','support_by_budget','support_by_length')},
        'verification':{'full_suite':'519 passed in27.26s before final target-eligibility independence fix',
                        'final_covering_suite':'99 passed in2.38s after that fix; no affected cohort targets changed'},
        'scope':'Actual cold exploratory requests and bounded support/model selection; no protected outcome or H1 conclusion',
        'reconstruction_ns':time.perf_counter_ns()-started}
    write('docs/superpowers/evidence/task12.json',evidence)
    write(out/'reconstruction.json',evidence)
    print(json.dumps({'selected':selected['name'],'attempts':len(attempts),'fits':len(fits),'rows':len(data['gain']),
                      'weighted_scores':scores,'deployment':deployment,'costs':cost_summary},indent=2))


if __name__=='__main__': reconstruct()
