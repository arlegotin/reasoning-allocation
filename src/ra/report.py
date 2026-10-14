"""Historical protected analysis; never invokes or relaxes live launch guards."""
from __future__ import annotations


def classify_claim(interval, *, precision, useful_effect_scale=None):
    low, high = interval
    if low>0: return 'positive frontier effect'
    if high<0: return 'tight-negative frontier effect' if high-low<=2*precision else 'negative frontier effect'
    if useful_effect_scale is not None and low>=-useful_effect_scale and high<=useful_effect_scale:
        return 'descriptive tight-null relative to an explicitly declared useful-effect scale; not an equivalence test'
    if low>=-precision and high<=precision:
        return 'direction inconclusive; narrow interval relative to planning precision; no equivalence margin registered'
    return 'wide-inconclusive frontier effect'


def guardrail_interpretation(*, frontier_effect, primal_effect, dual_effect):
    if primal_effect>0 and dual_effect>0:
        return 'exploratory primal/dual tradeoff: worse primal and better dual; no uniform improvement'
    if primal_effect<0 and dual_effect<0:
        return 'exploratory primal/dual tradeoff: better primal and worse dual; no uniform improvement'
    return 'exploratory guardrails; frontier alone does not establish uniform primal/dual improvement'


def validate_inventory(queue, seal):
    expected=[r['request_id'] for r in queue]
    actual=[r['request_id'] for r in seal['effective_attempts']]
    ids=[r['attempt_id'] for r in seal['effective_attempts']]
    if len(set(expected))!=len(expected) or len(set(actual))!=len(actual) or len(set(ids))!=len(ids):
        raise ValueError('duplicate effective inventory')
    if expected!=actual: raise ValueError('incomplete or reordered effective inventory; primary analysis blocked')


def reconstruct_attempt(directory):
    """Authenticate raw artifacts and independently replay complete parent receipts."""
    from dataclasses import asdict, replace
    from pathlib import Path
    from ra.freeze import read
    from ra.runner import _read_attempt
    from ra.types import Attempt, AvailableProgress, Request, ProgressRecord
    from ra.metrics import progress_at, validate_clock_alignment
    from ra.exact import verify_cover
    from ra.worker import load_instance
    directory=Path(directory)
    payload, final=_read_attempt(directory)
    if not final: raise ValueError('incomplete raw attempt cannot supply primary endpoint')
    request=Request(**payload['request']); records=[]; brackets=[]
    with (directory/'wire.jsonl').open() as stream:
        import json
        for line in stream:
            if not line.endswith('\n'): raise ValueError('incomplete wire frame')
            value=json.loads(line); packet=value['packet']; receipt=value['receipt_ns']
            if packet['kind']=='pong': brackets.append((packet['parent_send_ns'],packet['child_ns'],receipt))
            if packet['kind']=='progress':
                raw=ProgressRecord(**packet['record'])
                if raw.receipt_ns is not None or raw.request_id!=request.request_id:
                    raise ValueError('invalid child progress receipt/identity')
                records.append(replace(raw,receipt_ns=receipt))
    with (directory/'progress.jsonl').open() as stream:
        journal=[ProgressRecord(**json.loads(line)) for line in stream if line.strip()]
    if records!=journal: raise ValueError('wire/parent progress journal disagreement')
    if records and (not payload['clock_aligned'] or not validate_clock_alignment(brackets)):
        raise ValueError('unverified raw clock alignment')
    instance=load_instance(request) if records else None
    verified={}
    for record in records:
        if record.assignment_available:
            identity=record.incumbent_hash
            if not isinstance(identity,str) or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):
                raise ValueError('invalid assignment identity')
            assignment=read(directory/'solutions'/f'{identity}.json')
            if identity not in verified: verified[identity]=verify_cover(instance,assignment['binary'],0.)
            checked=verified[identity]
            if checked.content_hash!=identity or assignment['content_hash']!=identity or checked.objective!=record.primal_original or assignment['objective']!=record.primal_original:
                raise ValueError('independent assignment/objective mismatch')
    available=progress_at(records,request.deadline_ns,request.p0,bound_tolerance=request.bound_tolerance)
    if asdict(available)!=payload['available']: raise ValueError('raw reconstructed utility differs from sealed endpoint')
    if instance is not None and (instance.template_id!=payload['template_id'] or instance.cell_id!=payload['cell_id']):
        raise ValueError('raw instance provenance mismatch')
    fields={k:v for k,v in payload.items() if k not in ('files_sha256','request','available')}
    accounting=directory/'accounting.json'
    if accounting.exists():
        import hashlib
        cost=read(accounting)
        if cost['attempt_id']!=payload['attempt_id'] or cost['manifest_sha256']!=hashlib.sha256((directory/'attempt.json').read_bytes()).hexdigest():
            raise ValueError('publication accounting identity mismatch')
        fields['resources']={**fields['resources'],'publication_ns':cost['publication_ns'],
            'parent_cpu_ns':fields['resources'].get('parent_cpu_ns',0)+cost['parent_cpu_ns']}
    fields['resources']['analysis_calibration']=reconstruct_calibration(directory,records,request)
    return Attempt(**fields,request=request,available=available)


def historical_inventory(config_path):
    """Authenticate historical envelope and committed executable, without launching."""
    from pathlib import Path
    from ra.config import frozen_execution_paths
    from ra.freeze import verify_envelope, read, _check_committed_sources
    digest_path, root=frozen_execution_paths(config_path)
    checked=verify_envelope(digest_path); manifest=checked['manifest']
    config=read(config_path)
    if manifest['scientific_config']!=config: raise ValueError('config differs from frozen envelope')
    _check_committed_sources(manifest['source_commit'],manifest['source_inventory'])
    return checked, root


def analyze(config_path, out, *, dry_run=False):
    """Reconstruct the entire fixed cohort once and persist all registered results."""
    from pathlib import Path
    from ra.freeze import read
    from ra.config import frozen_execution_paths
    config_path, out=Path(config_path),Path(out)
    config=read(config_path)
    if dry_run:
        frozen_execution_paths(config_path)
        return dict(success=True,dry_run=True,expected_requests=len(read(Path(config['queue']['path']))),
            out=str(out),scope='no outcomes read; historical authentication and reconstruction planned')
    return _analyze_complete(config_path,out)


def resource_summary(attempts, metadata):
    """Disjoint physical requests; maxima and overlapping subsets are labelled."""
    from collections import defaultdict, Counter
    groups=defaultdict(list)
    for a in attempts: groups[metadata[a.request_id]['method'],a.request.budget_ns].append(a)
    rows=[]
    for (method,budget),group in sorted(groups.items()):
        def total(key): return sum(a.resources.get(key) or 0 for a in group)
        cpu=[max((a.resources[k] for k in ('worker_cpu_ns','worker_sampled_cpu_ns_lower_bound') if a.resources.get(k) is not None),default=None) for a in group]
        peaks=[a.resources[k] for a in group for k in ('worker_peak_rss_bytes','worker_sampled_peak_rss_bytes') if a.resources.get(k) is not None]
        row=dict(method=method,budget_ns=budget,physical_attempts=len(group),
            wall_including_publication_ns=total('end_to_end_ns')+total('publication_ns'),
            publication_ns_subset=total('publication_ns'),worker_cpu_ns_lower_bound=sum(v for v in cpu if v is not None),
            worker_cpu_missing=sum(v is None for v in cpu),parent_cpu_ns=total('parent_cpu_ns'),
            peak_worker_rss_bytes=max(peaks,default=None),trace_bytes=total('trace_bytes'),
            overshoot_ns_subset=sum(a.overshoot_ns for a in group),duration_censored=sum(a.duration_censored for a in group),
            cpu_tail_unmeasured=sum(bool(a.resources.get('cpu_tail_unmeasured',True)) for a in group),
            parent_observation_ns_overlapping_worker=total('parent_observation_ns_overlapping_worker'),
            parent_sampling_ns_subset=total('parent_sampling_ns'),initialization_ns=total('initialization_ns'),
            status_counts=dict(Counter(str(a.status) for a in group)))
        for key in ('worker_exclusive_ns','elapsed_partition_ns'):
            for a in group:
                for name,value in (a.resources.get(key) or {}).items():
                    if isinstance(value,(float,int)): row[key+'_'+name]=row.get(key+'_'+name,0)+value
        rows.append(row)
    return rows


def calibration_summary(attempts, metadata):
    """Exploratory observed-support residuals, never hypothetical action labels."""
    from collections import defaultdict
    groups=defaultdict(list)
    for a in attempts:
        groups[metadata[a.request_id]['method']].extend(o for o in a.resources.get('analysis_calibration',a.resources.get('lease_outcomes',[])) if o.get('support_hash') is not None)
    rows=[]
    for method,outcomes in sorted(groups.items()):
        complete=[o for o in outcomes if not (o.get('censored') or o.get('deadline_censored') or o.get('duration_lower_bound'))]
        gain=[o['endpoint_gain']-o['gain_prediction'] for o in complete if o.get('endpoint_gain') is not None and o.get('gain_prediction') is not None]
        seconds=[o['full_ns']/1e9-o['seconds_prediction'] for o in complete if o.get('full_ns') is not None and o.get('seconds_prediction') is not None]
        coverage=[o['body_ns']/1e9<=o['seconds_q90'] for o in complete if o.get('body_ns') is not None and o.get('seconds_q90') is not None]
        mean=lambda v:sum(v)/len(v) if v else None
        rows.append(dict(method=method,observed_supported=len(outcomes),completed=len(complete),censored=len(outcomes)-len(complete),
            gain_mean_error=mean(gain),gain_mae=mean([abs(v) for v in gain]),gain_n=len(gain),
            seconds_mean_error=mean(seconds),seconds_mae=mean([abs(v) for v in seconds]),seconds_n=len(seconds),
            q90_coverage_observed_complete=mean(coverage),q90_n=len(coverage)))
    return rows


def _write_json(path,value):
    import json
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def _write_csv(path,rows):
    import csv,json
    names=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=names);writer.writeheader()
        writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)


def endpoint_curves(rows,protocol):
    """Population-weighted means; missing primals remain explicitly unavailable."""
    from collections import defaultdict,Counter
    groups=defaultdict(list)
    for row in rows:
        groups['all',row['method'],row['budget_ns']].append(row)
        groups[row['family'],row['method'],row['budget_ns']].append(row)
        groups[row['cell_id'],row['method'],row['budget_ns']].append(row)
    result=[]
    metrics=('utility','primal','dual','raw_gap','relative_gap','normalized_primal','normalized_dual','solved','fault','assignment_available','overshoot_ns')
    for (scope,method,budget),group in sorted(groups.items(),key=lambda item:str(item[0])):
        by_cell=defaultdict(list)
        for r in group: by_cell[r['cell_id']].append(r)
        weights={c:protocol['planning']['cells'][c] for c in by_cell}; total=sum(weights.values())
        item=dict(scope=scope,method=method,budget_ns=budget,physical_endpoints=len(group),status_counts=dict(Counter(r['status'] for r in group)))
        for k in metrics:
            missing=sum(r[k] is None for r in group)
            item[k]=None if missing else sum(weights[c]/total*sum(r[k] for r in records)/len(records) for c,records in by_cell.items())
            item[k+'_missing']=missing
        result.append(item)
    return result


def _authenticate_execution(config,root,checked):
    from pathlib import Path
    from ra.freeze import read,check_reference
    import hashlib,subprocess
    project=Path(__file__).resolve().parents[2]
    audit_path=project/'docs/superpowers/evidence/task16/execution-audit.json'
    committed=subprocess.run(['git','show','HEAD:'+str(audit_path.relative_to(project))],cwd=project,capture_output=True,check=True).stdout
    if committed!=audit_path.read_bytes(): raise ValueError('execution audit differs from committed evidence')
    audit=read(audit_path)
    if audit['freeze_digest']!=checked['digest'] or audit['source_commit']!=config['source_commit']:
        raise ValueError('execution/freeze identity mismatch')
    seal_path=root/'execution-seal.json'
    if hashlib.sha256(seal_path.read_bytes()).hexdigest()!=audit['execution_seal']['sha256']:
        raise ValueError('execution seal hash mismatch')
    inventory_path=project/audit['operational_inventory']['path']
    if hashlib.sha256(inventory_path.read_bytes()).hexdigest()!=audit['operational_inventory']['sha256']:
        raise ValueError('operational inventory hash mismatch')
    for ref in read(inventory_path)['artifacts']:
        check_reference({'path':str(project/ref['path']),'sha256':ref['sha256']})
    return audit,read(seal_path)


def _analyze_complete(config_path,out):
    import hashlib,time,subprocess,resource
    from pathlib import Path
    from dataclasses import asdict
    from ra.freeze import read,_source_inventory,reference
    from ra.runner import _frozen_requests,_request_identity,_runtime_identity
    from ra.metrics import summarize_attempts
    from ra.stats import paired_frontier_intervals
    if out.exists() and any(out.iterdir()): raise ValueError('analysis output exists; preserve original fixed analysis')
    start,cpu=time.perf_counter_ns(),time.process_time_ns()
    config,audit,checked,attempts,metadata = reconstruct_frozen(config_path)
    _,root=historical_inventory(config_path)
    reconstructed=time.perf_counter_ns()
    rows=summarize_attempts(attempts,config)
    inference=paired_frontier_intervals(rows,config)
    for c in inference['contrasts']:
        c['claim']='quarantined correctness alarm' if c['correctness_quarantined'] else classify_claim(c['simultaneous_interval'],precision=config['planning']['useful_precision'])
        if not c['quantile_stable']: c['claim']+='; frozen Monte Carlo stability diagnostic failed'
    out.mkdir(parents=True,exist_ok=True)
    _write_json(out/'inference.json',inference)
    _write_csv(out/'primary.csv',inference['contrasts'])
    _write_csv(out/'endpoints.csv',rows)
    _write_csv(out/'resource_summary.csv',resource_summary(attempts,metadata))
    _write_csv(out/'calibration.csv',calibration_summary(attempts,metadata))
    curves=endpoint_curves(rows,config);_write_csv(out/'curves.csv',curves)
    _write_csv(out/'secondary_effects.csv',secondary_effects(curves,config))
    print('FROZEN PRIMARY INFERENCE COMPLETE',flush=True)
    for c in inference['contrasts']: print(f"{c['method']}–{c['baseline']}: {c['estimate']:.10g}; simultaneous {c['simultaneous_interval']}; {c['claim']}",flush=True)
    identity=_runtime_identity()
    provenance=dict(executed_source_commit=config['source_commit'],executed_identity=config['environment'],
        freeze_digest=checked['digest'],config=reference(config_path),execution_seal=reference(root/'execution-seal.json'),
        analysis_source_commit=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip(),
        analysis_source_inventory=_source_inventory(),analysis_source_hash=identity[0],analysis_environment_hash=identity[1],
        analysis_build_hash=identity[2],analysis_runtime_inventory=identity[3],
        analysis_scope='historical reconstruction; current live A004 execution is rejected by strict launch guards',
        receipt_reconstruction_count=len(rows),verified_committed_source_files=len(checked['manifest']['source_inventory']))
    _write_json(out/'provenance.json',provenance)
    project_cost_inventory(out)
    render_report(out,config,inference,curves,audit)
    # Plotting is a separate hash-locked environment; inference stays on .venv.
    project=Path(__file__).resolve().parents[2]
    import os
    plot_env=project/'artifacts/task17/plot-env/bin/python'
    env={**os.environ,'PYTHONPATH':str(project/'src'),'MPLCONFIGDIR':str(project/'artifacts/task17/matplotlib')}
    child_before=resource.getrusage(resource.RUSAGE_CHILDREN)
    subprocess.run([str(plot_env),'-c','from ra.report import plot_report; from pathlib import Path; import sys; plot_report(Path(sys.argv[1]))',str(out.resolve())],env=env,check=True)
    child_after=resource.getrusage(resource.RUSAGE_CHILDREN)
    accounting=dict(wall_ns=time.perf_counter_ns()-start,cpu_ns=time.process_time_ns()-cpu,
        reconstruction_wall_ns=reconstructed-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plotting_child_cpu_seconds=(child_after.ru_utime+child_after.ru_stime-child_before.ru_utime-child_before.ru_stime),
        scope='analysis invocation through plot completion; final accounting/index writes and interactive/development/setup/test costs excluded; no solver execution',
        unknown_tails=['final accounting and artifact-index writes','development/interactive work','dependency preparation and failed network setup'])
    _write_json(out/'analysis_resources.json',accounting)
    _write_json(out/'artifacts.json',{'artifacts':[reference(p) for p in sorted(out.iterdir()) if p.is_file()]})
    return dict(success=True,dry_run=False,out=str(out),requests=len(rows),contrasts=len(inference['contrasts']),analysis_resources=accounting)


def project_cost_inventory(out, *, project=None):
    """All retained physical attempts, including pre-fix failures; no cumulative sums.

    Historical fit/driver envelopes are separate overlapping evidence scopes.
    Neither those envelopes nor request wall/CPU/overshoot/storage are added to
    one fictitious full-project total.
    """
    import os,json,hashlib
    from pathlib import Path
    from collections import defaultdict,Counter
    project=Path(project) if project is not None else Path(__file__).resolve().parents[2]
    candidates=[]; evidence=[]
    for top in ('artifacts','data'):
        for directory,subdirs,files in os.walk(project/top):
            subdirs[:]=[s for s in subdirs if s not in ('plot-env','matplotlib','solutions','trace','source','__pycache__')]
            base=Path(directory)
            for name in ('attempt.json','partial.json','bootstrap.json'):
                if name in files: candidates.append(base/name); break
            for name in files:
                if name.endswith('.json') and (name in ('fit-card.json','stage-cost.json','driver-cost.json','resources.json') or name.endswith('-resources.json') or name.endswith('-cost.json')):
                    path=base/name
                    value=json.loads(path.read_text())
                    # Preserve numerical resource measures and their original paths/scopes.
                    def costs(v,prefix=''):
                        found={}
                        if isinstance(v,dict):
                            for k,item in v.items():
                                field=prefix+k
                                if isinstance(item,(float,int)) and any(word in k for word in ('_ns','_bytes','seconds','cpu','wall','elapsed','duration','attempt','censored')): found[field]=item
                                elif isinstance(item,(dict,list)): found.update(costs(item,field+'.'))
                        elif isinstance(v,list):
                            for i,item in enumerate(v): found.update(costs(item,prefix+str(i)+'.'))
                        return found
                    measures=costs(value)
                    if measures: evidence.append(dict(path=str(path.relative_to(project)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),measures=measures,
                        scope='original nested resource evidence; may overlap physical requests/other driver or fit cards; never additive without reconciliation'))
    seen={};duplicates=0;manifest=[];groups=defaultdict(list)
    # Prefer a final publication to an earlier checkpoint copied elsewhere.
    for path in sorted(candidates,key=lambda p:(p.name!='attempt.json',str(p))):
        raw=path.read_bytes();p=json.loads(raw); aid=p.get('attempt_id')
        if not aid: continue
        if aid in seen: duplicates+=1;continue
        seen[aid]=path
        relative=str(path.relative_to(project));scope=relative.split('/attempts/')[0] if '/attempts/' in relative else str(path.parent.parent.relative_to(project))
        manifest.append(dict(path=relative,sha256=hashlib.sha256(raw).hexdigest(),attempt_id=aid,status=p.get('status'),final=path.name=='attempt.json'))
        r=p.get('resources',{});publication={}
        for name in ('accounting.json','publication.json'):
            if (path.parent/name).exists(): publication=json.loads((path.parent/name).read_text());break
        groups[scope].append(dict(status=p.get('status','unknown'),wall=r.get('end_to_end_ns',0),publication=publication.get('publication_ns',0),
            cpu=max((r[k] for k in ('worker_cpu_ns','worker_sampled_cpu_ns_lower_bound') if r.get(k) is not None),default=None),
            trace=r.get('trace_bytes',0),overshoot=p.get('overshoot_ns',0),partial=path.name!='attempt.json',
            cpu_tail=r.get('cpu_tail_unmeasured',True),publication_missing=not publication,
            peak=max((r[k] for k in ('worker_peak_rss_bytes','worker_sampled_peak_rss_bytes') if r.get(k) is not None),default=None)))
    scopes=[]
    for scope,items in sorted(groups.items()):
        scopes.append(dict(scope=scope,physical_attempts=len(items),status_counts=dict(Counter(r['status'] for r in items)),
            request_wall_ns_lower_bound=sum(r['wall']+r['publication'] for r in items),
            worker_cpu_ns_lower_bound=sum(r['cpu'] or 0 for r in items),worker_cpu_missing=sum(r['cpu'] is None for r in items),
            peak_worker_rss_bytes=max((r['peak'] for r in items if r['peak'] is not None),default=None),
            trace_bytes=sum(r['trace'] for r in items),overshoot_ns_subset=sum(r['overshoot'] for r in items),
            partial=sum(r['partial'] for r in items),cpu_tail_unmeasured=sum(r['cpu_tail'] for r in items),
            missing_publication=sum(r['publication_missing'] for r in items)))
    result=dict(unique_physical_attempts=len(seen),duplicate_copies_ignored=duplicates,scopes=scopes,
        scope='retained artifacts/data physical-attempt inventory, all statuses and pre-fix work; artificial fixture scopes identifiable by paths; no exact project total',
        limitations=['unrecorded early experiments/development/failed preparations/interactive time remain unknown',
            'cumulative_prior_costs deliberately excluded; sampled/exact CPU use maximum, never sum',
            'driver/training/tuning envelopes overlap nested request and fit costs; separate evidence, no sum',
            'old partial checkpoints are cost lower bounds; missing termination/publication tails remain unknown'])
    _write_csv(out/'project_costs.csv',scopes)
    _write_json(out/'project_costs.json',result)
    _write_json(out/'historical_resource_evidence.json',evidence)
    # The full physical metadata inventory is local; the compact published hash binds it.
    inventory=project/'artifacts/task17/project-attempt-inventory.json';inventory.parent.mkdir(parents=True,exist_ok=True)
    _write_json(inventory,manifest)
    _write_json(out/'project_cost_inventory.json',dict(path=str(inventory),sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(),records=len(manifest)))
    return result


def render_report(out,config,inference,curves,audit):
    """Legacy A004-only renderer; reject any alternate scientific input.

    Its narrative and historical costs are fixed. Future cohorts must use a new
    report contract, never inherit these claims by supplying different arrays.
    """
    _validate_a004_render(config,inference,curves,audit)
    from ra.freeze import read
    import csv
    all_curves={(r['method'],r['budget_ns']):r for r in curves if r['scope']=='all'}
    lines=['# A004 confirmatory paired solver analysis','',
        'Complete fixed cohort: 60 independent original templates (10 per cell), two timing repeats, three cold deadlines, seven physical methods, 2,520 requests. One genuine fitted bundle. Every utility was independently rebuilt from immutable complete-frame parent receipts and verified original-space assignments.',
        '', '## Registered primary frontier results','',
        'No registered positive superiority result is established. A is worse than B2 on the conditional primary frontier; the native comparisons and remaining directions are inconclusive. These conclusions concern this designed population, deadlines and one frozen fitted bundle; they do not establish transfer or training-procedure robustness.', '',
        'The frontier integrates all three independent cold deadlines using the frozen log-budget weights. Ordinary percentile intervals and Bonferroni simultaneous intervals use 65,536 draws, seed 2026101502, alpha 0.05 and six unique A–control contrasts. Inference is conditional on the frozen fitted assets and training data. Across-fit and training-procedure uncertainty are unavailable.', '',
        '| Contrast | Paired effect | Ordinary 95% interval | Simultaneous interval | Interpretation |','|---|---:|---|---|---|']
    for c in inference['contrasts']:
        fmt=lambda pair:'['+', '.join(f'{v:.9g}' for v in pair)+']'
        lines.append(f"| {c['method']}–{c['baseline']} | {c['estimate']:.9g} | {fmt(c['ordinary_interval'])} | {fmt(c['simultaneous_interval'])} | {c['claim']} |")
    lines += ['', 'B4 is the same outcome and contrast as B3. It contributes no extra test, fitted model, physical request, or sample. The frozen 0.001 planning sensitivity target is not a useful-effect or equivalence margin. B3/B5 intervals are narrower around zero but their directions remain inconclusive; practically relevant differences are not ruled out.',
        '', '### Monte Carlo and sampling limitations','',
        f"Four-batch endpoint diagnostic, tolerance {inference['quantile_stability_tolerance']:.6g}: "+'; '.join(f"{c['baseline']} {'stable' if c['quantile_stable'] else 'UNSTABLE'} (endpoint range {max(c['quantile_batch_spread']):.6g})" for c in inference['contrasts'])+'.',
        'The frozen draw count and seed are retained even where the numerical diagnostic is unstable. No additional seed, sample, model, deadline, or endpoint was selected from these results. Complete template clusters retain all paired methods, deadlines and repeats. Native results remain shared across fit resampling. A single fit cannot establish training-procedure robustness; empirical resampling also cannot reveal unobserved tails.',
        '', '## Raw deadline and guardrail endpoints (exploratory)','',
        '| Method | Deadline s | Utility | Primal | Dual | Raw gap | Solved fraction | Fault fraction |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for (method,budget),r in sorted(all_curves.items()):
        fmt=lambda v:'unavailable' if v is None else f'{v:.8g}'
        lines.append('| '+' | '.join([method,fmt(budget/1e9),*[fmt(r[k]) for k in ('utility','primal','dual','raw_gap','solved','fault')]])+' |')
    lines+=['','Raw primal/dual/gap values are population-weighted in original objective units. Missing primal output stays unavailable. Tolerance clipping is used only for the explicitly labelled plotting gap; inference and raw tables retain unrounded values. Family, cell, deadline, calibration and resource outcomes are exploratory; no simultaneous secondary improvement claim is made. Full family/cell/status curves are in `curves.csv`, paired per-budget/component effects in `secondary_effects.csv`, and all physical endpoints and timing fields in `endpoints.csv`.','']
    for c in inference['contrasts']:
        primal=dual=0.;missing=False
        for b,w in zip(config['deadlines_ns'],config['weights']):
            a,control=all_curves['A',b],all_curves[c['baseline'],b]
            if a['primal'] is None or control['primal'] is None: missing=True;break
            primal+=w*(a['primal']-control['primal']);dual+=w*(a['dual']-control['dual'])
        lines.append(f"- A–{c['baseline']}: "+('primal unavailable; no uniform improvement claim.' if missing else f"integrated raw primal difference {primal:.8g}; dual difference {dual:.8g}. "+guardrail_interpretation(frontier_effect=c['estimate'],primal_effect=primal,dual_effect=dual)))
    lines+=['','## Faults, calibration and costs','',
        f"All endpoint statuses retained: {inference['status_counts']}. Numerical/correctness alarms quarantine claims rather than deleting observations. Ordinary faults retain their last valid available utility.",
        'Mean time residuals compare full invocation estimates to full lease time; q90 coverage compares body-duration predictions to body time. Calibration in `calibration.csv` uses only actually observed supported lease actions. Completed-action mean residuals and q90 coverage are exploratory and selected/censoring-conditional; censored counts are retained, with no counterfactual or unsupported-action calibration claim.',
        '', 'Protected execution scopes (overlapping quantities are not summed):','',
        '| Scope | Recorded value |','|---|---:|',
        '| Batch wall including guards and requests | 3834.684718 s |',
        '| Strict entry / live guards, included in batch | 3.718029917 / 63.295173010 s |',
        '| Request wall including publication, included in batch | 3689.555684398 s |',
        '| Publication subset of request wall | 88.880694529 s |',
        '| Whole coordinator CPU | 514.584103 s |',
        '| Request parent CPU subset of coordinator | 377.562958 s |',
        '| Worker CPU lower bound | 3347.089174268 s |',
        '| Overshoot subset of consumed wall | 50.364064041 s |',
        '| Raw trace / whole protected output (different storage scopes) | 2522350036 / 4591473863 bytes |',
        '| Separate post-run audit wall / CPU | 104.118770833 / 77.585235 s |',
        '', 'Every protected attempt has an unmeasured CPU tail through process exit. Final batch/report write tails, interactive monitoring and failed static preparation are not fully measured. These values are not an exact full-project cost. Resource totals, missing counts, timing partitions and per-deadline costs are in `resource_summary.csv`; overlapping parent observation and overshoot are labelled subsets.',
        'The full retained project physical-attempt inventory is hashed by `project_cost_inventory.json`; `project_costs.csv` includes every retained old, failed, partial, pre-fix, training/tuning/calibration and protected scope. Duplicate physical-attempt copies are counted once; cumulative prior costs are never added again. `historical_resource_evidence.json` preserves separate fit/driver/generation/tuning envelopes. These envelopes overlap nested attempts and fit cards, so no unsupported grand total is computed. Unknown early/development/test/preparation tails remain explicit.',
        'Task 17 analysis time, CPU, peak memory and plotting subprocess CPU appear separately in `analysis_resources.json`. Plot dependencies are isolated and hash locked by `requirements/analysis-plot.lock`; the solver environment/native build is unchanged.',
        '', '## Provenance and exposure','',
        f"Historical executed source: `{config['source_commit']}`; freeze `{audit['freeze_digest']}`. `provenance.json` separately records current analysis source commit/inventory/environment, historical source/model/config/environment/build identities and execution seal. Historical reconstruction uses the immutable envelope plus committed executable inventory. Strict CURRENT A004 launch correctly rejects the changed source; no guard exemption or rerun occurred.",
        'Ruling10 selected stable original indices12–71: 48 retained unopened originals and 12 fresh replacements60–71, with equal cell weights. The inherited fixture shared identities0–11; 252 real startup probes at1/4/16ns never loaded input or made solver progress. Artificial/mock values were not scientific protected solutions. All earlier inputs/freezes/fixtures and their cost/exposure evidence remain preserved. No protected outcome selected a replacement.',
        'Deferred engineering triage: Task9 helper M2 duplicate/incomplete-budget validation remains unresolved because this analysis does not reuse that helper; Task16 orchestration maintainability M1 remains deferred. Task15 bootstrap counts1–3 validation is corrected here. Any desired scientific change requires a method amendment and appropriate fresh cohort.', '']
    (out/'confirmatory_report.md').write_text('\n'.join(lines))


def plot_report(out):
    """Standalone standard scientific PDF/PNG figures from persisted fixed results."""
    import csv,json,platform,sys,hashlib
    from importlib import metadata
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    inference=json.loads((out/'inference.json').read_text());contrasts=inference['contrasts']
    fig,ax=plt.subplots(figsize=(7,4.2),layout='constrained')
    for i,c in enumerate(contrasts):
        lo,hi=c['simultaneous_interval'];a,b=c['ordinary_interval'];estimate=c['estimate']
        ax.plot([lo,hi],[i,i],color='#254b74',linewidth=2)
        ax.plot([a,b],[i,i],color='#254b74',linewidth=5)
        ax.plot(estimate,i,'o',color='#c25724')
    ax.axvline(0,color='0.4',linewidth=.8);ax.set_yticks(range(len(contrasts)),[f"A − {c['baseline']}" + (" * UNSTABLE" if not c["quantile_stable"] else "") for c in contrasts])
    ax.set_xlabel('Paired frontier difference');ax.set_title('A004: conditional on one frozen fit\nThin: Bonferroni simultaneous; thick: ordinary 95%')
    ax.grid(axis='x',alpha=.2)
    if any(not c['quantile_stable'] for c in contrasts):
        ax.set_xlabel('Paired frontier difference\n* Frozen Monte Carlo endpoint diagnostic failed; no additional draws')
    for suffix in ('pdf','png'):fig.savefig(out/f'primary_intervals.{suffix}',dpi=180)
    plt.close(fig)
    with (out/'curves.csv').open() as stream: rows=[r for r in csv.DictReader(stream) if r['scope']=='all']
    fig,axes=plt.subplots(2,2,figsize=(9,6),layout='constrained')
    for method in sorted({r['method'] for r in rows}):
        group=sorted([r for r in rows if r['method']==method],key=lambda r:int(r['budget_ns']));x=[int(r['budget_ns'])/1e9 for r in group]
        for ax,key,label in zip(axes.flat,['utility','normalized_primal','normalized_dual','solved'],['Available utility','Primal / initial primal (lower better)','Dual / initial primal (higher better)','Solved fraction']):
            ax.plot(x,[float(r[key]) if r[key] else np.nan for r in group],marker='o',label=method)
            ax.set_xscale('log');ax.set_xlabel('Independent cold deadline (s)');ax.set_ylabel(label);ax.grid(alpha=.2)
    axes.flat[0].legend(ncol=4,fontsize=8);fig.suptitle('A004 exploratory endpoint curves; population cell weights')
    for suffix in ('pdf','png'):fig.savefig(out/f'endpoint_curves.{suffix}',dpi=180)
    plt.close(fig)
    _write_json(out/'plot_environment.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        packages={d.metadata['Name']:d.version for d in metadata.distributions()},
        lock_sha256=hashlib.sha256((__import__('pathlib').Path(__file__).resolve().parents[2]/'requirements/analysis-plot.lock').read_bytes()).hexdigest()))


def reconstruct_calibration(directory,records,request):
    """Validate observed action support and reconstruct lease gains from receipts."""
    from bisect import bisect_right
    from ra.collect import read_decision
    from ra.freeze import read
    from ra.metrics import ProgressStream
    import math
    stream=ProgressStream(request.deadline_ns,request.p0,bound_tolerance=request.bound_tolerance)
    receipts=[];utilities=[]
    for record in records:
        stream.accept(record)
        receipts.append(record.receipt_ns);utilities.append(stream.available.utility)
    def value_at(time):
        i=bisect_right(receipts,min(time,request.deadline_ns))-1
        return utilities[i] if i>=0 else 0.
    labels=[]
    for path in sorted((directory/'trace').glob('label-*.json')):
        label=read(path);decision=read_decision(path.with_name(f"decision-{label['trace_index']:06d}.json"))
        action=decision['allocation']
        if (label['root']!=action['root'] or label['node_limit']!=action['node_limit']
                or action['root'] not in decision['pool_ids'] or action['node_limit'] not in decision['support_lengths']
                or label['support_hash']!=decision['support_hash']): raise ValueError('calibration action outside observed support')
        begin,end=value_at(label['entry_ns']),value_at(label['end_ns'])
        if any(not math.isclose(x,y,abs_tol=1e-12) for x,y in ((begin,label['parent_utility_entry']),
                (end,label['parent_utility_end']),(end-begin,label['endpoint_gain']))): raise ValueError('raw receipt calibration gain mismatch')
        labels.append(label)
    return labels


def secondary_effects(curves,protocol):
    """Paired complete-cohort mean differences; no secondary interval/test claims."""
    table={(r['scope'],r['method'],r['budget_ns']):r for r in curves}
    result=[]
    for scope in sorted({r['scope'] for r in curves}):
        for budget in protocol['deadlines_ns']:
            for a,b in protocol['contrasts']:
                first,second=table[scope,a,budget],table[scope,b,budget]
                row=dict(scope=scope,budget_ns=budget,method=a,baseline=b,inference='exploratory point differences only')
                for metric in ('utility','primal','dual','raw_gap','relative_gap','normalized_primal','normalized_dual','solved','fault','assignment_available','overshoot_ns'):
                    x,y=first[metric],second[metric]
                    row[metric+'_difference']=None if x is None or y is None else x-y
                result.append(row)
    return result


def reconstruct_frozen(config_path):
    """Authenticate/reconstruct the complete historical cohort, with no writes."""
    import hashlib
    from pathlib import Path
    from dataclasses import asdict
    from ra.freeze import read
    from ra.runner import _frozen_requests, _request_identity
    checked,root=historical_inventory(config_path);config=checked['manifest']['scientific_config']
    audit,seal=_authenticate_execution(config,root,checked)
    queue=read(Path(config['queue']['path']));validate_inventory(queue,seal)
    metadata={r['request_id']:r for r in queue}
    expected={r.request_id:r for r in _frozen_requests(config,queue)}
    actual_dirs={p.parent.resolve() for p in root.glob('attempts/*/*/attempt.json')}
    effective_dirs={(root/r['directory']).resolve() for r in seal['effective_attempts']}
    if actual_dirs!=effective_dirs: raise ValueError('unreconciled physical attempts; explicit interruption accounting required')
    attempts=[]
    for i,entry in enumerate(seal['effective_attempts']):
        directory=root/entry['directory']
        if not directory.resolve().is_relative_to(root.resolve()): raise ValueError('attempt path escape')
        if hashlib.sha256((directory/'attempt.json').read_bytes()).hexdigest()!=entry['manifest_sha256']: raise ValueError('sealed attempt hash mismatch')
        a=reconstruct_attempt(directory); q=metadata[a.request_id]
        if (a.attempt_id!=entry['attempt_id'] or _request_identity(asdict(a.request))!=_request_identity(asdict(expected[a.request_id]))
                or a.template_id!=q['template_id'] or a.cell_id!=q['cell_id'] or a.request.deadline_ns-a.request.launch_ns!=q['budget_ns']):
            raise ValueError('historical raw request/model/source/environment/build/queue identity drift')
        attempts.append(a)
        if (i+1)%210==0: print(f'Authenticated and reconstructed {i+1}/{len(queue)} cold endpoints',flush=True)
    return config,audit,checked,attempts,metadata


def numerical_inference_digest(inference):
    """Claim text is presentation; every other inference field is numerical evidence."""
    import copy
    from ra.freeze import digest
    value=copy.deepcopy(inference)
    for contrast in value['contrasts']: contrast.pop('claim',None)
    return digest(value)


def _validate_a004_render(config,inference,curves,audit):
    from pathlib import Path
    from ra.freeze import read
    project=Path(__file__).resolve().parents[2]
    if (config!=read(project/'configs/confirmatory-A004.json')
            or numerical_inference_digest(inference)!='6339521bccab940fe0ec0546792a3c6012e65644fe7f63a5dde6418717b83d69'
            or audit!=read(project/'docs/superpowers/evidence/task16/execution-audit.json')
            or curves!=_read_table(project/'results/confirmatory/curves.csv')):
        raise ValueError('legacy renderer requires exact validated A004 inputs; alternate cohort rejected')


def _read_table(path):
    import csv,json
    with path.open() as stream:
        result=[]
        for raw in csv.DictReader(stream):
            row={}
            for key,value in raw.items():
                try: row[key]=json.loads(value) if value else None
                except (ValueError,TypeError): row[key]=value
            result.append(row)
    return result


def build_report(manifest_path, out, *, dry_run=False):
    """Build scope-limited prose/tables from authenticated stored artifacts only.

    JSON achieved-scope manifests support analytical, blocked and validation
    stops. A004's explicit .sha256 envelope is the sole completed experiment
    contract; it resolves the versioned handoff manifest and verifies its inputs.
    This command never calls a solver or recomputes bootstrap inference.
    """
    from pathlib import Path
    from ra.freeze import read,check_reference,verify_envelope
    project=Path(__file__).resolve().parents[2]
    manifest_path,out=Path(manifest_path),Path(out)
    if manifest_path.suffix=='.sha256':
        envelope=verify_envelope(manifest_path)
        if envelope['digest']!='72aba9929daa98bb48c64237ebba47e2c6d66e75d65165bf78a0355a53455457':
            raise ValueError('completed report supports only the authenticated A004 achieved scope')
        manifest=read(project/'configs/report-achieved.json')
        if manifest['scope']!='confirmation': raise ValueError('confirmation manifest scope mismatch')
    else:
        manifest=read(manifest_path)
        if manifest.get('scope')=='confirmation':
            raise ValueError('completed confirmation requires its explicit frozen .sha256 manifest')
    if manifest.get('schema_version')!=1 or manifest.get('scope') not in {'analytical','blocked','validation','confirmation'}:
        raise ValueError('invalid achieved-scope manifest')
    if manifest.get('empirical_solver_claims'): raise ValueError('claims must be derived from authenticated evidence')
    refs=manifest.get('references',{})
    for ref in refs.values(): check_reference({'path':str(project/ref['path']),'sha256':ref['sha256']})
    lines=['# Reasoning allocation: achieved scope','',f"Achieved scope: **{manifest['scope']}**.",'']
    claims=[];headlines=[]
    if manifest['scope']!='confirmation':
        lines+=['Confirmation not executed. No empirical solver gain is established by this report.','']
    else:
        config=read(project/refs['config']['path']); inference=read(project/refs['inference']['path'])
        audit=read(project/refs['audit']['path']); curves=_read_table(project/refs['curves']['path'])
        resources=_read_table(project/refs['resources']['path'])
        _validate_a004_render(config,inference,curves,audit)
        lines+=(project/refs['narrative']['path']).read_text().splitlines()+['']
        table={(r['method'],r['budget_ns']):r for r in curves if r['scope']=='all'}
        for contrast in inference['contrasts']:
            baseline=contrast['baseline']
            effects={key:sum(w*(table['A',b][key]-table[baseline,b][key])
                for b,w in zip(config['deadlines_ns'],config['weights'])) for key in ('primal','dual')}
            claim=classify_claim(contrast['simultaneous_interval'],precision=config['planning']['useful_precision'])
            if contrast['correctness_quarantined']:claim='quarantined correctness alarm; no solver claim'
            if not contrast['quantile_stable']:claim+='; Monte Carlo UNSTABLE'
            claims.append(f"A–{baseline}: {claim}")
            headlines.append(dict(competitor=f"A versus {baseline}: {manifest['methods'][baseline]}",
                population=manifest['population'],templates=inference['independent_templates'],fits=inference['independent_fit_runs'],
                deadlines_ns=config['deadlines_ns'],estimate=contrast['estimate'],ordinary_interval=contrast['ordinary_interval'],
                simultaneous_interval=contrast['simultaneous_interval'],primal_difference=effects['primal'],dual_difference=effects['dual'],
                resources=[r for r in resources if r['method'] in ('A',baseline)],training=manifest['training'],
                claim=claim,caveat='Conditional on one fitted bundle; near-ceiling designed population; exploratory primal/dual; no transfer'))
        lines+=['## Primary headline comparisons','',
            'All rows: '+manifest['population']+'; 60 independent originals; one genuine fit; two timing repeats. Cold deadlines (ns): '+str(config['deadlines_ns'])+'.',
            'Training/tuning: '+manifest['training'],
            'Paired absolute frontier effects; ordinary 95% and six-contrast Bonferroni simultaneous intervals. Primal/dual are exploratory integrated original-objective differences. Per-method resources are in the next table; no matched-quality positive time saving or break-even reuse is established.','',
            '| Exact competitor | Effect | Ordinary 95% | Simultaneous interval | Primal difference | Dual difference | Claim / caveat |',
            '|---|---:|---|---|---:|---:|---|']
        for row in headlines:
            lines.append('| '+' | '.join(str(row[k]) for k in ('competitor','estimate','ordinary_interval','simultaneous_interval','primal_difference','dual_difference'))+' | '+row['claim']+'; '+row['caveat']+' |')
        lines+=['','## Cold endpoint and resource table','',
            'Every row has 120 physical requests, 60 originals and two timing repeats. Wall includes publication; worker CPU is a lower bound, parent CPU overlaps wall. Overshoot is a wall subset; RSS is a maximum. These columns must not be added together. LP counts denote native LP solves, not LP iterations. All endpoint/native-work rows remain in `results/confirmatory/endpoints.csv`.','',
            '| Method | Deadline ns | Utility | Primal | Dual | Solved | Fault | Wall s | Worker CPU lower bound s | Parent CPU s | Overshoot s | Peak RSS bytes |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for r in resources:
            c=table[r['method'],r['budget_ns']]
            values=[r['method'],r['budget_ns'],*[c[k] for k in ('utility','primal','dual','solved','fault')],
                *[r[k]/1e9 for k in ('wall_including_publication_ns','worker_cpu_ns_lower_bound','parent_cpu_ns','overshoot_ns_subset')],r['peak_worker_rss_bytes']]
            lines.append('| '+' | '.join(str(v) for v in values)+' |')
        lines+=['','[Qualified standalone primary plot](results/handoff/primary_intervals.png); [PDF](results/handoff/primary_intervals.pdf). B6 carries its frozen Monte Carlo instability marker. Original plots and artifact indexes remain immutable.','']
    lines+=['## Package dispositions','', '| Package | Status | Evidence / reason |','|---|---|---|']
    for package in manifest['packages']:
        lines.append(f"| {package['name']} | {package['status']} | {package['reason']} |")
    lines+=['','## Limits','']+['- '+item for item in manifest.get('limitations',[])]+['','## Authenticated sources','']
    for name,ref in refs.items():lines.append(f"- {name}: [{ref['path']}]({ref['path']}), SHA256 `{ref['sha256']}`")
    result=dict(success=True,dry_run=dry_run,scope=manifest['scope'],empirical_solver_claims=claims,headline_rows=headlines,out=str(out))
    if not dry_run:
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text('\n'.join(lines)+'\n')
    return result
