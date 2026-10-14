"""Reconstruct Task9 tables from immutable attempts; no new native execution."""
import json,csv,time,hashlib,statistics,re,resource
from pathlib import Path
from dataclasses import fields
from collections import Counter
from ra.runner import _read_attempt
from ra.types import Attempt,Request,AvailableProgress
from ra.pilot import summarize_headroom,recommend_population,forecast
root=Path('artifacts/pilot');entry=time.perf_counter_ns();cpu=time.process_time_ns()

def write(path,value):
 Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')

def pct(values,q):
 if not values:return None
 a=sorted(values);return a[round((len(a)-1)*q)]

raw=[];attempts=[];locations={}
for path in sorted(root.rglob('attempt.json')):
 if '/sources/' in str(path):continue
 a,complete=_read_attempt(path.parent);assert complete
 stage=str(path.relative_to(root)).split('/')[0]
 raw.append((stage,a,path));locations[a['attempt_id']]=str(path)
 value={k:v for k,v in a.items() if k in {f.name for f in fields(Attempt)}}
 value['request']=Request(**value['request']);value['available']=AvailableProgress(**value['available'])
 attempts.append(Attempt(**value))
summary=summarize_headroom(attempts)
assert len({a.attempt_id for a in attempts})==len(attempts)
recommend_population(summary)  # Reject any learned/protected contamination.
# Only matched stage cohorts define competitive finite envelopes. The charged
# profile is cost evidence, never another primary/native contender.
summary['finite_envelope']=[{'stage':stage,**item} for stage in sorted({s for s,_,_ in raw}) if stage!='profile'
 for item in summarize_headroom([a for a,(s,_,_) in zip(attempts,raw) if s==stage])['finite_envelope']]
summary['attempt_paths']=locations
summary['comparison_scope']='within matched stage only; pre-cache native tuning provisional, profile excluded from competitive envelopes'
write(root/'headroom-summary.json',summary)
rows=[]
for (stage,a,path),r in zip(raw,summary['records']):
 row={k:r[k] for k in ['attempt_id','instance_id','template_id','cell_id','family','phase','kind','method','status','utility','primal_original','dual_original','native_nodes','native_lps','wall_ns','peak_rss_bytes','worker_cpu_ns','overshoot_ns','censored','budget_ns','solver_seed','source_hash','config_hash','environment_hash','build_hash']}
 row.update(stage=stage,diagnostic=stage=='profile',worker_provenance_available=a['instance_provenance_available'])
 # Join original identity only through coordinator-validated exact input hash.
 p=Path(a['request']['instance_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==a['request']['instance_sha256']
 original=json.loads(p.read_text());assert original['instance_id']==a['request']['instance_hash']
 row.update(coordinator_template_id=original['template_id'],coordinator_cell_id=original['cell_id'],coordinator_family=original['lineage']['cell']['family'])
 row['worker_sampled_peak_rss_bytes']=a['resources'].get('worker_sampled_peak_rss_bytes')
 rows.append(row)
with (root/'headroom.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
stages={}
for name in sorted({s for s,_,_ in raw}):
 group=[a for s,a,_ in raw if s==name];cost=[a['resources'] for a in group]
 stages[name]={'attempts':len(group),'statuses':dict(Counter(a['status'] for a in group)),
  'known_request_wall_ns':sum(c['end_to_end_ns'] for c in cost),'known_worker_cpu_ns':sum(c.get('worker_cpu_ns',0) for c in cost),
  'missing_worker_cpu':sum('worker_cpu_ns' not in c for c in cost),'overshoot_ns_total':sum(a['overshoot_ns'] for a in group),
  'maximum_overshoot_ns':max(a['overshoot_ns'] for a in group),'peak_worker_rss_bytes':max((c['worker_peak_rss_bytes'] for c in cost if 'worker_peak_rss_bytes'in c),default=None)}
write(root/'stage-summary.json',stages)
batch=[json.loads(p.read_text()) for p in root.glob('*/runs/batch-*/accounting.json')]
# Include the separately identified profile nested run at the same glob depth.
free=[]
for p in root.rglob('prospective.json'):
 s=json.loads(p.read_text()).get('snapshots',[]);s=list(s.values()) if isinstance(s,dict) else s
 for probe in s:
  text=probe.get('stdout','');page=re.search(r'page size of (\d+)',text);pages=re.search(r'Pages free: (\d+)',text)
  if page and pages:free.append(int(page[1])*int(pages[1]))
available=min(free);reserve=max(free)-min(free)
coordinator=max(c['coordinator_peak_rss_bytes'] for c in batch)
design={'request_count':100,'scenario':'per100 requests at observed pilot mixture; not a planned sample count',
 'available_memory_bytes':available,'reserve_bytes':reserve,'reserve_basis':'observed free-memory range across prospective snapshots',
 'coordinator_bytes':coordinator,'safety_factor':2,'timed':True}
forecasts={}
for name,kind in [('native','native'),('fixed_shared','shared')]:
 costs=[r for r in summary['records'] if r['kind']==kind]
 forecasts[name]=forecast(name,costs,design)
forecast_report={'schema_version':1,'conditional_forecasts':forecasts,'stage_costs':stages,
 'known_batch_wall_ns':sum(c['total_observed_ns'] for c in batch),'known_coordinator_cpu_ns':sum(c['coordinator_cpu_ns'] for c in batch),
 'batch_cpu_overlaps_worker_wall':True,'final_reporting_tails':'measured reporting.json intervals retained; receipt-own/return tails unavailable, never zero',
 'planned_confirmatory_templates':None,'planned_fits':None,'planned_repeats':None,'desired_useful_precision':None,
 'power_status':'unresolved; requires training/validation paired variance and user-relevant useful precision before WP06 protected freeze',
 'future_model_training_inference_cost':'unmeasured; no model exists; observed fixed-control costs are conditional planning inputs, not learned estimates',
 'generation_cost_scope':'recorded setup_ns/elapsed_ns retain measured generation intervals; earliest preparation-script import/return tails were not separately timed and remain unknown',
 'unmeasured_early_command_tails':True}
write(root/'resource_forecast.json',forecast_report)
profiles=[]
for stage,a,p in raw:
 if stage!='profile':continue
 r=a['resources'];d=r['pilot_profile'];t=a['timestamps'];solve=t['solve_end_ns']-t['solve_start_ns'];root_proxy=d['root_and_first_main_ns'];nodes=r['native_nodes']
 profiles.append({'attempt_id':a['attempt_id'],'family':a['lineage']['cell']['family'],'solver_seed':a['request']['solver_seed'],
 'root_and_first_main_ns':root_proxy,'solve_ns':solve,'post_first_main_ns':solve-root_proxy,
 'post_first_main_share_of_solve':(solve-root_proxy)/solve,'post_first_main_share_of_cold_request':(solve-root_proxy)/r['end_to_end_ns'],
 'cold_nonsteerable_proxy_ns':r['end_to_end_ns']-(solve-root_proxy),
 'main_lp_per_second_proxy':(r['native_lps']-d['lps_at_first_main_completion'])/((solve-root_proxy)/1e9) if d['lps_at_first_main_completion'] is not None and solve>root_proxy else None,
 'frontier_histogram':d['frontier_histogram'],
 'native_nodes':nodes,'native_lps':r['native_lps'],'raw_lp_iterations':d['native_final']['lp_iterations'],
 'observation_ns':r['worker_exclusive_ns']['observation'],
 'post_first_main_ns_per_remaining_native_node_proxy':(solve-root_proxy)/(nodes-1) if nodes>1 else None,
 'scope':'charged diagnostic; first completed nonroot node overestimates root; raw native counts, not lease completion labels'})
write(root/'root-frontier-profile.json',profiles)
observer=[]
for stage,a,p in raw:
 r=a['resources'];t=a['timestamps']
 if a['request']['method_config']['kind']!='native' or not r.get('worker_exclusive_ns') or not t.get('solve_end_ns'):continue
 original=json.loads(Path(a['request']['instance_path']).read_text());cell=original['lineage']['cell']
 if cell['columns']!=256:continue
 observation=r['worker_exclusive_ns']['observation'];solve=t['solve_end_ns']-t['solve_start_ns']
 observer.append({'stage':stage,'attempt_id':a['attempt_id'],'observation_ns':observation,'solve_ns':solve,
 'observation_to_solve_ratio':observation/solve if solve else None,
 'scope':'required observer ledger includes anchor and terminal outside solve; ratio is a conservative whole-request-observation/solve share, not randomized observer effect'})
write(root/'observer-share.json',observer)
pools=[]
for stage,a,p in raw:
 if stage!='pool-length':continue
 r=a['resources'];cfg=a['request']['method_config'];decisions=r.get('allocation_decisions',[]);leases=r.get('lease_outcomes',[])
 rebids=[b['dispatch_ns']-b['entry_ns'] for b in r.get('selection_boundaries',[]) if b['kind']=='rebid' and b['dispatch_ns'] is not None]
 pools.append({'attempt_id':a['attempt_id'],'K':cfg['pool_size'],'length':cfg['allocator']['length'],'status':a['status'],'utility':a['available']['utility'],
 'native_nodes':r.get('native_nodes'),'rebids':len(decisions),'maximum_frontier':max((d['context']['frontier_size'] for d in decisions),default=None),
 'maximum_pool':max((len(d['pool_ids']) for d in decisions),default=None),'rebid_median_ns':pct(rebids,.5),'rebid_p95_ns':pct(rebids,.95),
 'administration_ns':(r.get('worker_exclusive_ns') or {}).get('administration'),'native_ns':(r.get('worker_exclusive_ns') or {}).get('native'),
 'natural_completion_count':sum(l['natural_completion'] for l in leases),'censored_lease_count':sum(l['censored'] for l in leases),
 'lease_work_total':sum(l['work'] for l in leases),'release_overshoot_ns':a['overshoot_ns'],'trace_bytes':r.get('trace_bytes')})
write(root/'pool-length-profile.json',pools)
cs=[p['post_first_main_ns_per_remaining_native_node_proxy'] for p in profiles if p['post_first_main_ns_per_remaining_native_node_proxy'] is not None]
hs=[p['rebid_median_ns'] for p in pools if p['rebid_median_ns'] is not None]
c=statistics.median(cs);h=statistics.median(hs);q=.8
write(root/'overhead-arithmetic.json',{'schema_version':1,'measured_c_ns':c,'measured_h_ns':h,'c_scope':'diagnostic post-first-main wall/native-node proxy, includes required observation','h_scope':'median charged rebid entry-to-dispatch including pool/admin across testedK/L; no learned inference',
 'illustrative_q':q,'q_scope':'hypothetical20percent reduction in work; not measured learned improvement',
 'illustrative_time_ratio_L1':q*(c+h)/c,'illustrative_time_ratio_L8':q*(c+h/8)/c,
 'illustrative_maximum_extra_overhead_per_new_node_ns':c*(1/q-1),
 'limitation':'arithmetic for steerable segment only; root/startup/finalization and future inference remain charged; no claimed end-to-end speedup'})
safe=[max(0,a['timestamps']['safe_return_ns']-a['request']['deadline_ns']) for _,a,_ in raw if a['timestamps'].get('safe_return_ns') is not None]
release=[a['overshoot_ns'] for _,a,_ in raw]
write(root/'tails.json',{'safe_return_debt_ns':{'median':pct(safe,.5),'p95':pct(safe,.95),'maximum':max(safe)},
 'release_overshoot_ns':{'median':pct(release,.5),'p95':pct(release,.95),'maximum':max(release)},
 'missing_safe_return_count':len(raw)-len(safe),'retained_duration_censored_count':sum(a['duration_censored'] for _,a,_ in raw),
 'watchdog_grace_ns':2_000_000_000,'reason':'Retain conservative2s grace; compare measured maximum safe-return/release debt and finite-support uncertainty. Not a hard upper bound.'})
write(root/'reconstruction-cost.json',{'wall_ns':time.perf_counter_ns()-entry,'cpu_ns':time.process_time_ns()-cpu,'peak_rss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'all immutable attempt hash audits and summary computations/writes through before this final receipt; final receipt tail unavailable'})
print(json.dumps({'attempts':len(raw),'stages':stages,'overhead_c_ns':c,'overhead_h_ns':h},indent=2))
