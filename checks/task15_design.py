"""Task15 prospective public pilot, calibration and artifact-only freeze preparation.

Run stages serially. Never solve/read a protected instance here. The source
milestone must be committed before pilot. All measured attempts remain immutable.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/task15/generation4'
BUDGETS=[526707240,2106828958,8427315832]
FIT='task13-matched-fit1'


def read(p):return json.loads(Path(p).read_text())


def write(p,value):
    from ra.runner import _atomic_json
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    _atomic_json(Path(p),value,immutable=True)


def methods():
    from ra.freeze import deployment_methods
    return deployment_methods(read(ROOT/'configs/mandatory_baselines.json'),4096)


def merge_owners(destination):
    from ra.provenance import SplitOwnership
    merged=SplitOwnership()
    for path in ('data/pilot/split_ownership.json','artifacts/task13/split_ownership.json','artifacts/models/final/split_ownership.json'):
        other=SplitOwnership.load(ROOT/path)
        for key,value in other.owners.items():
            if key in merged.owners and merged.owners[key]!=value:raise ValueError('historical split conflict')
            merged.owners[key]=value
    merged.save(destination)


def prepare():
    from ra.data import generate_workload
    from ra.runner import _runtime_identity
    from ra.freeze import reference,_check_committed_sources,_source_inventory
    import psutil
    source,env,build,inventory=_runtime_identity()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    _check_committed_sources(commit,_source_inventory())
    merge_owners(OUT/'public/split_ownership.json')
    manifest=generate_workload(read(ROOT/'configs/workload_manifest.json'),'validation',OUT/'public/validation')
    execution=read(ROOT/'configs/task12-final-train.json')
    execution={k:v for k,v in execution.items() if k not in ('training','collection')}
    execution.update(methods=list(methods().values()),input_manifests=[str(OUT/'public/validation/manifest.json')],
        solver_seeds=[17],budgets_ns=BUDGETS,run_order_seed=2026101501)
    write(OUT/'public-run.json',execution)
    write(OUT/'hardware.json',dict(platform=platform.platform(),machine=platform.machine(),processor=platform.processor(),
        physical_memory_bytes=psutil.virtual_memory().total,cpu_count=psutil.cpu_count(),
        cpu_brand=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        disk=psutil.disk_usage(str(ROOT))._asdict(),memory=psutil.virtual_memory()._asdict(),load=os.getloadavg(),
        power=subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout,
        thermal='not continuously instrumented',
        python=sys.version,executable=sys.executable))
    write(OUT/'prospective.json',dict(source_commit=commit,environment=dict(source_hash=source,environment_hash=env,build_hash=build),
        inventory=inventory,physical_methods=methods(),pilot_originals=12,pilot_repeats=2,pilot_fit_runs=1,
        source=reference(Path(__file__)),request_count=504,deadlines_ns=BUDGETS,
        useful_precision=.001,resource_budget_seconds=3600,resource_budget_storage_bytes=20*1024**3,
        design_options_templates_per_cell=[2,4,10,20,40,100],
        telemetry_limit=4096,prior_generation=reference(ROOT/'artifacts/task15/generation3/preflight.json'),
        transport_policy='Common linear receive buffering with128MiB frame bound; same complete-frame receipt semantics and2s grace; generation3 B2 faults retained; engineering improvement is not allocator evidence',
        telemetry_rationale='Ruling8:841 observed decisions;32–34kB trace/decision;4096 gives4.87x observed headroom. Fourfold artifact/worker sensitivity envelopes separate from actual measurements; no identified RSS slope or guarantee. All learned methods share the bounded cap; no fallback',
        planning_assumptions='One hour and20GiB are initial operational assumptions, not user hard limits. Inspect larger alternatives and actual capacity before freeze.',
        rationale='0.001 normalized frontier half-width resolves approximately half the earlier native shortfall; sensitivity only, not a success threshold',
        candidate_rationale='Matched-data adaptive ridge preserves primary allocation hypothesis and locality attribution against B6; fixed winner is not promoted',
        fit_scope='one existing complete matched-data fitted procedure; fit seed exports are aliases; no across-fit precision claim',
        stopping='fixed504 public requests; binding N60/2timings/1fit from Ruling7; no protected tuning or significance stopping'))
    print('prepared public pilot 504 physical requests',flush=True)


def pilot():
    from ra.runner import run_schedule,_runtime_identity
    expected=read(OUT/'prospective.json')['environment']
    source,env,build,_=_runtime_identity()
    assert expected==dict(source_hash=source,environment_hash=env,build_hash=build)
    for repeat in range(2):
        started=time.perf_counter_ns()
        attempts=run_schedule(OUT/'public-run.json','validation',OUT/f'pilot-repeat{repeat}')
        print('repeat',repeat,'requests',len(attempts),'seconds',(time.perf_counter_ns()-started)/1e9,
            'statuses',sorted({str(a.status) for a in attempts}),flush=True)


def summarize():
    from ra.runner import _read_attempt
    from ra.freeze import reference
    from ra.stats import calibrate_design
    import numpy as np
    rows=[];attempt_refs=[];batches=[]
    name_to_id={v['name']:k for k,v in methods().items()}
    for repeat in range(2):
        run=OUT/f'pilot-repeat{repeat}'
        schedule=read(run/'schedule.json');expected=set(schedule['request_order']);seen=set()
        for path in sorted((run/'attempts').rglob('attempt.json')):
            attempt,final=_read_attempt(path.parent)
            if not final or attempt['request_id'] not in expected or attempt['request_id'] in seen:
                raise ValueError('missing/duplicate/partial public cohort')
            seen.add(attempt['request_id']);request=attempt['request'];resource=attempt['resources']
            receipt=read(path.parent/'accounting.json')
            if receipt['manifest_sha256']!=reference(path)['sha256']:raise ValueError('publication hash mismatch')
            method=name_to_id[request['method']]
            rows.append(dict(phase='validation',template_id=attempt['template_id'],cell_id=attempt['cell_id'],
                repeat=repeat,budget_ns=request['budget_ns'],method=method,fit_id='shared' if method in ('B0','B1') else FIT,
                utility=attempt['available']['utility'],primal=attempt['available']['primal_original'],dual=attempt['available']['dual_original'],
                source_hash=request['code_hash'],wall_ns=resource['end_to_end_ns']+receipt['publication_ns'],
                peak_rss_bytes=resource.get('worker_peak_rss_bytes'),trace_bytes=sum(p.stat().st_size for p in path.parent.rglob('*') if p.is_file()),
                overshoot_ns=attempt['overshoot_ns'],status=attempt['status'],censored=attempt['duration_censored'],
                worker_cpu_ns=resource.get('worker_cpu_ns'),parent_cpu_ns=resource.get('parent_cpu_ns'),
                publication_ns=receipt['publication_ns'],release_confirmed=resource.get('resource_release_confirmed'),
                startup_ns=attempt['timestamps'].get('worker_start_ns',0)-attempt['timestamps']['launch_ns'],
                native_nodes=resource.get('native_nodes'),native_lps=resource.get('native_lps'),
                attempt_id=attempt['attempt_id'],attempt=reference(path)))
            attempt_refs += [reference(path),reference(path.parent/'accounting.json')]
        if seen!=expected:raise ValueError('incomplete pilot cohort')
        batches += [dict(path=str(p),**read(p)) for p in run.glob('batch-*/accounting.json')]
    write(OUT/'pilot-rows.json',rows)
    prospective=read(OUT/'prospective.json')
    write(OUT/'preflight.json',dict(environment=prospective['environment'],physical_methods=methods(),rows=reference(OUT/'pilot-rows.json'),
        attempts=attempt_refs,batches=batches,prospective=reference(OUT/'prospective.json'),
        total_physical_requests=len(rows),protected_outcomes_opened=False))
    # Independent native completion observations at the longest deadline; repeats average per original.
    native=[r for r in rows if r['method']=='B0' and r['budget_ns']==BUDGETS[-1]]
    completion={t:np.mean([r['wall_ns'] for r in native if r['template_id']==t and r['status']=='complete'])
        for t in sorted({r['template_id'] for r in native}) if all(r['status']=='complete' for r in native if r['template_id']==t)}
    scale=dict(native_originals=len({r['template_id'] for r in native}),fully_completed_originals=len(completion),
        median_complete_ns=float(np.median(list(completion.values()))) if completion else None,
        cold_complete_ns_by_template=completion,retained_T0_ns=BUDGETS[1],
        reason='Retain public pilot scale to cover startup/easy saturation, middle hard progress and long completion. No arbitrary recentering on easy-only median; native progress and remaining headroom are reported by budget.',
        native_summary_by_budget={str(b):dict(mean_utility=float(np.mean([r['utility'] for r in rows if r['method']=='B0' and r['budget_ns']==b])),
            fraction_complete=float(np.mean([r['status']=='complete' for r in rows if r['method']=='B0' and r['budget_ns']==b]))) for b in BUDGETS})
    write(OUT/'deadline-calibration.json',scale)
    cells={r['cell_id']:1/6 for r in rows}
    design=dict(deadlines=BUDGETS,cells=cells,methods=list(methods()),native_methods=['B0','B1'],fit_ids=[FIT],
        contrasts=[['A',k] for k in ('B0','B1','B2','B3','B5','B6')],sample_per_cell=2,timing_repeats=2,
        bootstrap_repetitions=65536,seed=2026101502,alpha=.05,useful_precision=prospective['useful_precision'])
    stability=[]
    for n in (65536,):
        design['bootstrap_repetitions']=n;result=calibrate_design(rows,design)
        stability.append(dict(repetitions=n,spreads=[r['quantile_batch_spread'] for r in result['contrasts']],
                              stable=all(r['quantile_stable'] for r in result['contrasts'])))
        if stability[-1]['stable']:break
    if not stability[-1]['stable']:raise ValueError('bootstrap stability unresolved after declared grid')
    options=[]
    for n in prospective['design_options_templates_per_cell']:
        d={**design,'sample_per_cell':n};r=calibrate_design(rows,d)
        options.append(dict(templates_per_cell=n,original_templates=6*n,request_count=r['resources']['request_count'],
            wall_seconds_with_reserve=r['resources']['wall_ns_with_reserve']/1e9,
            storage_bytes_with_reserve=r['resources']['storage_bytes_with_reserve'],
            empirical_half_widths=[(x['planned_interval_empirical'][1]-x['planned_interval_empirical'][0])/2 for x in r['contrasts']],
            conservative_half_width=r['conservative_half_width']))
    chosen=next(o for o in options if o['original_templates']==60);design['sample_per_cell']=10
    result=calibrate_design(rows,design)
    write(OUT/'design.json',design)
    write(OUT/'power-design.json',result)
    write(OUT/'design-selection.json',dict(prospective=reference(OUT/'prospective.json'),options=options,selected=chosen,
        monte_carlo_stability=stability,deadline_calibration=reference(OUT/'deadline-calibration.json'),
        decision='limited conditional-on-fit evaluation; no reliable across-fit power; empirical two-per-cell extrapolation cannot certify population precision',
        bounded_required_originals_for_half_width_001=2*__import__('math').log(240)/.001**2,
        pilot_wall_ns=sum(r['wall_ns'] for r in rows),batch_wall_ns=sum(b['total_observed_ns'] for b in batches)))
    print(json.dumps(dict(selected=chosen,stability=stability,scale=scale),indent=2),flush=True)


def package():
    """Prepare only the declared successor; never rewrite prior scientific assets."""
    from ra.freeze import reference,make_queue,ordinary_fault_policy,check_reused_ancestry
    c=read(ROOT/'configs/confirmatory-A002.json');previous=reference(ROOT/'protocol/freeze-A002.sha256')
    prospective=read(OUT/'prospective.json');design=read(OUT/'design.json');resources=read(OUT/'power-design.json')['resources']
    experiment='ra-wp06-e004'
    inputs=[r for ref in c['protected_manifests'] for r in read(ref['path'])['instances']]
    c.update(experiment_id=experiment,source_commit=prospective['source_commit'],environment=prospective['environment'],
        hardware=reference(OUT/'hardware.json'),planning=design,physical_methods=methods(),
        preflight=reference(OUT/'preflight.json'),resources=reference(OUT/'power-design.json'),
        outcome_directory=str(ROOT/'artifacts/runs'/experiment),
        execution_access_journal=str(ROOT/'artifacts/runs'/f'{experiment}.access.json'),
        protocol=reference(ROOT/'protocol/confirmatory-A003.md'),
        amendment=dict(number=3,previous=previous,reason='Correct ordinary fault scoring and ancestry reuse gate; Ruling8 common4096 telemetry with current-source calibration',
            input_reuse_basis='All60 e003 inputs remain unopened; entire predecessor ancestry checked; preserve all original manifests/registries and attempts.'))
    c['execution']['methods']=list(methods().values());c['exclusions'].update(ordinary_fault_policy())
    c['bootstrap']['monte_carlo']=reference(OUT/'planned-monte-carlo.json')
    c['telemetry']=dict(max_decisions=4096,scope='common bounded learned telemetry, charged in every applicable method',evidence=reference(OUT/'prospective.json'))
    c['capacity']=dict(storage_envelope_bytes=max(4*resources['storage_bytes_with_reserve'],4*8394067200),
        worker_peak_envelope_bytes=max(4*resources['peak_rss_bytes_observed'],4*265863168),
        coordinator_reserve_bytes=20*1024**3,os_reserve_bytes=4*1024**3,
        physical_memory_bytes=read(OUT/'hardware.json')['physical_memory_bytes'],free_storage_bytes=shutil.disk_usage(ROOT).free,
        basis='Separate conservative4x artifact/worker envelopes; no identified RSS slope, no guaranteed bound')
    write(OUT/'protected-access-at-freeze.json',dict(schema_version=1,events=[]))
    c['access_ledger']=reference(OUT/'protected-access-at-freeze.json')
    c['evidence']+=[reference(OUT/'planned-monte-carlo.json'),reference(OUT/'design-selection.json')]
    check_reused_ancestry(c,inputs)
    write(OUT/'protected-queue.json',make_queue(c,inputs));c['queue']=reference(OUT/'protected-queue.json')
    write(ROOT/'configs/confirmatory-A003.json',c)
    print('prepared unopened successor queue',len(read(OUT/'protected-queue.json')),flush=True)


if __name__=='__main__':
    {'prepare':prepare,'pilot':pilot,'summarize':summarize,'package':package}[sys.argv[1]]()
