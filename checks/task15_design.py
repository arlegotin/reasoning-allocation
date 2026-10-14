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
OUT=ROOT/'artifacts/task15/generation2'
BUDGETS=[526707240,2106828958,8427315832]
FIT='task13-matched-fit1'


def read(p):return json.loads(Path(p).read_text())


def write(p,value):
    from ra.runner import _atomic_json
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    _atomic_json(Path(p),value,immutable=True)


def methods():
    from ra.freeze import deployment_methods
    return deployment_methods(read(ROOT/'configs/mandatory_baselines.json'),1024)


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
        telemetry_limit=1024,prior_generation=reference(ROOT/'artifacts/task15/preflight.json'),
        telemetry_rationale='Two retained B3 failures at512 decisions in7.227s/18.52MB/162.40MB RSS;1024 doubles bounded capacity for all learned methods, projected~670 decisions by8.427s. Measure fresh full cohort; no fallback.',
        planning_assumptions='One hour and20GiB are initial operational assumptions, not user hard limits. Inspect larger alternatives and actual capacity before freeze.',
        rationale='0.001 normalized frontier half-width resolves approximately half the earlier native shortfall; sensitivity only, not a success threshold',
        candidate_rationale='Matched-data adaptive ridge preserves primary allocation hypothesis and locality attribution against B6; fixed winner is not promoted',
        fit_scope='one existing complete matched-data fitted procedure; fit seed exports are aliases; no across-fit precision claim',
        stopping='fixed public collection; no protected tuning; select largest finite design within predeclared resource reserve; explicit inconclusive if sensitivity insufficient'))
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
        bootstrap_repetitions=4096,seed=2026101502,alpha=.05,useful_precision=prospective['useful_precision'])
    stability=[]
    for n in (4096,16384,65536):
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
    affordable=[o for o in options if o['wall_seconds_with_reserve']<=prospective['resource_budget_seconds'] and o['storage_bytes_with_reserve']<=prospective['resource_budget_storage_bytes']]
    if not affordable:raise ValueError('no affordable finite design')
    chosen=affordable[-1];design['sample_per_cell']=chosen['templates_per_cell']
    result=calibrate_design(rows,design)
    write(OUT/'design.json',design)
    write(ROOT/'artifacts/pilot/power_design.json',result)
    write(OUT/'design-selection.json',dict(prospective=reference(OUT/'prospective.json'),options=options,selected=chosen,
        monte_carlo_stability=stability,deadline_calibration=reference(OUT/'deadline-calibration.json'),
        decision='limited conditional-on-fit evaluation; no reliable across-fit power; empirical two-per-cell extrapolation cannot certify population precision',
        bounded_required_originals_for_half_width_001=2*__import__('math').log(240)/.001**2,
        pilot_wall_ns=sum(r['wall_ns'] for r in rows),batch_wall_ns=sum(b['total_observed_ns'] for b in batches)))
    print(json.dumps(dict(selected=chosen,stability=stability,scale=scale),indent=2),flush=True)


def package():
    from ra.freeze import reference,make_queue
    from ra.data import generate_indexed_workload
    from ra.worker import THREAD_SETTINGS
    design=read(OUT/'design.json');prospective=read(OUT/'prospective.json')
    experiment='ra-wp06-e001'
    protected=ROOT/'data/confirmatory'/experiment
    merge_owners(protected.parent/'split_ownership.json')
    population=read(ROOT/'configs/workload_manifest.json')
    generated=generate_indexed_workload(population,'confirmatory',protected,templates_per_cell=design['sample_per_cell'])
    write(OUT/'protected-access-at-freeze.json',{'schema_version':1,'events':[]})
    execution=read(OUT/'public-run.json');execution['input_manifests']=[str(protected/'manifest.json')]
    physical=methods()
    c=dict(schema_version=1,experiment_id=experiment,source_commit=prospective['source_commit'],
        hardware=reference(OUT/'hardware.json'),environment=prospective['environment'],
        models=[reference(Path(p)) for p in sorted({m['allocator']['model_path'] for m in physical.values() if 'model_path' in m.get('allocator',{})})],
        features=[reference(ROOT/'configs/features.json')],baseline_register=reference(ROOT/'configs/mandatory_baselines.json'),
        sample=dict(original_templates=6*design['sample_per_cell'],templates_per_cell=design['sample_per_cell'],timing_repeats=2,fit_runs=1,train_originals=12),
        deadlines_ns=BUDGETS,weights=[.25,.5,.25],
        bootstrap=dict(B=6,alpha=.05,repetitions=design['bootstrap_repetitions'],seed=design['seed'],
            algorithm='stratified original-template bootstrap, all paired methods/budgets/repeats kept together; complete fit runs independently crossed',
            ordinary='two-sided percentile .025/.975 conditional on frozen fit',simultaneous='two-sided Bonferroni alpha/(2B), B=6 unique contrasts; B3/B4 same outcome/contrast',
            few_fit='one genuine fit; across-fit interval unavailable, no seed-alias resampling',monte_carlo=reference(OUT/'design-selection.json')),
        contrasts=design['contrasts'],watchdog=dict(workers=1,grace_ns=execution['watchdog_grace_ns'],native_threads=1,numerical_threads=THREAD_SETTINGS,
            policy='cooperative absolute deadline; parent grace then termination; only independently validated parent receipts by deadline score'),
        exclusions=dict(startup_timeout='zero utility retained',deadline='available utility retained; overshoot fully costed',
            method_fault='retained zero utility, halt and diagnose; any scientific fix requires numbered amendment and fresh untouched confirmation where needed',
            numerical_alarm='quarantine configuration; no superiority claim; halt',external_interrupt='only same immutable request retry allowed; preserve all prior attempts and costs',
            missing='no complete primary analysis until every queue key has one authoritative effective outcome',
            censoring='cost lower bounds and unknown tails retained, no deletion',stopping='one fixed queue, no significance stopping, no protected tuning'),
        guardrails=dict(status='secondary exploratory; no simultaneous secondary improvement claim',
            budgets='primal-only, dual-only, absolute objectives, raw gap, solved fraction, first verified improvement/optimality, gap-time area',
            resources='failures, overshoot/release/publication, wall/CPU/RSS/storage, native work/admin fraction and supported action calibration',
            primal_regression='frontier win with primal regression is a tradeoff; never unqualified improvement',
            interpretation='tight negative, tight-null, wide inconclusive reported distinctly; no fixed-control result rebranded adaptive',
            training='separate sunk training/tuning/failure costs; no wall-time subtraction or invented amortization'),
        resources=reference(ROOT/'artifacts/pilot/power_design.json'),preflight=reference(OUT/'preflight.json'),
        protected_manifests=[reference(protected/'manifest.json')],protocol=reference(ROOT/'protocol/confirmatory.md'),
        access_ledger=reference(OUT/'protected-access-at-freeze.json'),outcome_directory=str(ROOT/'artifacts/runs'/experiment),
        telemetry={'max_decisions':1024,'scope':'common learned trace bound, charged in every applicable method','evidence':reference(OUT/'prospective.json')},
        execution=execution,candidate='local-matched',fit_ids=[FIT],physical_methods=physical,aliases={'B4':'B3'},
        gates={'WP04':'reviewed','WP05':'reviewed'},amendment={'number':0,'previous':None},population=population,planning=design,
        evidence=[reference(ROOT/p) for p in ('docs/superpowers/evidence/task13-fix1.json','docs/superpowers/evidence/task13-fix1-controls-card.json',
            'artifacts/environment/doctor.json','artifacts/environment/wheel-manifest.json','artifacts/environment/scip-parameters.json')])
    write(OUT/'protected-queue.json',make_queue(c,generated['instances']))
    c['queue']=reference(OUT/'protected-queue.json')
    write(ROOT/'configs/confirmatory.json',c)
    print('packaged untouched inputs and queue',len(generated['instances']),len(read(OUT/'protected-queue.json')),flush=True)


if __name__=='__main__':
    {'prepare':prepare,'pilot':pilot,'summarize':summarize,'package':package}[sys.argv[1]]()
