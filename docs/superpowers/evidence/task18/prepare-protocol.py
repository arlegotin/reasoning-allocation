"""Read existing public costs and pin the prospective diagnostic; no solver run."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import statistics

from ra.runner import prepare_schedule, _digest

ROOT=Path.cwd()
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

public=[]
for budget in (526707240,2106828958,8427315832):
    for name in ('B2-estimate-L1','local-historical-asset'):
        rows=[];durations=[]
        for p in sorted(Path(f'artifacts/task13/validation-{budget}/attempts').glob('*/*/attempt.json')):
            a=read(p)
            if a['request']['method']!=name:continue
            r=a['resources']
            times=[b['end_ns']-b['entry_ns'] for b in r['selection_boundaries'] if b['kind']=='rebid' and b['end_ns'] is not None]
            durations.extend(times)
            rows.append({'path':str(p),'sha256':sha(p),'instance_id':a['request']['instance_hash'],
                'rebids':len(times),'end_to_end_ns':r['end_to_end_ns'],'administration_ns':r['worker_exclusive_ns']['administration'],
                'status':a['status'],'source_hash':a['request']['code_hash'],'method_config':a['request']['method_config']})
        public.append({'budget_ns':budget,'method':name,'requests':rows,'rebids':len(durations),
            'median_rebid_ns':statistics.median(durations),'mean_rebid_ns':statistics.mean(durations),
            'total_end_to_end_ns':sum(r['end_to_end_ns'] for r in rows)})
requests,schedule=prepare_schedule(Path('configs/robustness.json'),'validation')
manifest_path=Path('artifacts/task13/validation-inputs/selected-manifest.json')
manifest=read(manifest_path)
assert [i['template_index'] for i in manifest['instances']]==[0,2,4,6,8,10]
assert len({i['cell_id'] for i in manifest['instances']})==6
fixed=read('configs/confirmatory-A004.json')
pins=['configs/robustness.json','protocol/task18-latency.md','checks/task18_latency.py',
      'configs/workload_manifest.json','configs/confirmatory-A004.json',str(manifest_path),
      'docs/superpowers/evidence/task18/prepare-protocol.py',manifest['ownership_registry']]
pins += [str(manifest_path.parent/i['path']) for i in manifest['instances']]
pins += ['artifacts/checks/task3/verification.json','artifacts/checks/task3/reference-preservation.json']
result={'schema_version':1,'claim_level':'exploratory diagnostic','base_commit':'9f379e5118f78f95cf2df6782d09744aec1cec02',
 'dataset_namespace':'validation','selection_rule':'one original per cell, even generator index 0..10, no outcome screening',
 'selected_originals':manifest['instances'],'independent_originals':6,'timing_repeats':2,'fit_count':0,
 'control':fixed['physical_methods']['B2'],'control_hash':_digest(fixed['physical_methods']['B2']),
 'frozen_candidate_reference_only':fixed['physical_methods']['A'],'frozen_candidate_hash':_digest(fixed['physical_methods']['A']),
 'donor_costs':public,'donor_limit':'Task13 historical local asset, not direct primary A latency; full rebid interval, not inference-only',
 'varied_component':'constant post-choice wall latency in charged administration',
 'fixed_components':['B2 estimate ordering','length1','K128','solver/pool seed17','native kernel','original inputs','cold receipt deadline','one thread'],
 'dose_ns':[0,4_000_000,10_000_000],'deadline_ns':2106828958,
 'forecast':{'expected_elapsed_seconds':[35,50],'scheduled_budget_ns':36*2106828958,'watchdog_grace_ns_per_request':2_000_000_000,'basis':'existing six-request middle B2 block 5.717441333s; sleep can lengthen requests, overshoot/publication extra'},
 'stop':{'overshoot_fraction':.2,'elapsed_ns':180_000_000_000,'check':'after every attempt; fault/quarantine, release/timing failure; no retries'},
 'files_sha256':{str(Path(p).resolve().relative_to(ROOT)):sha(p) for p in pins},
 'schedule':schedule,'requests':[asdict(r) for r in requests],
 'gates':{'population':'unexecuted; no representation-specific resource question','other_robustness':'unexecuted; smallest latency treatment selected','optimization':'no expansion without controller measurement/forecast','promotion':'requires amendment and fresh protected confirmation'},
 'limits':['two repeats are not independent originals','one budget and six designed public originals','sleep does not reproduce CPU/cache/model information effects','changed timing can change native trajectory','no causal attribution of all A loss','no primary inference or bootstrap']}
path=Path('protocol/task18-latency.json')
with path.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
print('prospective protocol sha256',sha(path),'requests',len(requests))
