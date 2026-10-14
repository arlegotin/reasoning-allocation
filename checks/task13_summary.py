"""Reconstruct paired Task13 scores and actual costs from immutable attempts."""
from collections import Counter,defaultdict
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import statistics
import time
from task13_controls import OUT, ROOT, BUDGETS, read


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def dist(v):return dict(count=len(v),min=min(v),median=statistics.median(v),max=max(v),sum=sum(v)) if v else None


def summarize():
    from ra.train import validation_scores
    started=time.perf_counter_ns()
    groups=defaultdict(list);raw=[];validation=[];actuals=[];frontier=[];capacity=[];native=[]
    for path in sorted(OUT.rglob('attempt.json')):
        a=read(path);r=a['request'];res=a['resources'];account=read(path.parent/'accounting.json')
        assert account['attempt_id']==a['attempt_id'] and account['manifest_sha256']==sha(path)
        group=path.relative_to(OUT).parts[0]
        row=dict(group=group,path=str(path.relative_to(ROOT)),attempt_id=a['attempt_id'],method=r['method'],phase=r['phase'],
            instance_hash=r['instance_hash'],cell=a['lineage']['cell'],template_id=a['template_id'],solver_seed=r['solver_seed'],
            budget_ns=r['budget_ns'],status=a['status'],error=a.get('error'),available=a['available'],
            source_hash=r['code_hash'],environment_hash=r['environment_hash'],model_hash=r.get('model_hash'),
            full_request_ns=account['total_observed_ns'],publication_ns=account['publication_ns'],
            end_to_end_ns=res['end_to_end_ns'],worker_cpu_ns=res.get('worker_cpu_ns'),parent_cpu_ns=res.get('parent_cpu_ns'),
            rss_bytes=res.get('worker_peak_rss_bytes'),trace_bytes=res.get('trace_bytes'),overshoot_ns=a['overshoot_ns'],
            model_loading_ns=res.get('model_loading_ns'),model_bytes=res.get('model_bytes'))
        groups[group].append(row);raw.append(row);actuals.append((row,a))
        if group.startswith('validation-'):
            validation.append(SimpleNamespace(request=SimpleNamespace(**r),available=SimpleNamespace(**a['available'])))
        if group.startswith('capacity-'):
            capacity.append(SimpleNamespace(request=SimpleNamespace(**r),available=SimpleNamespace(**a['available'])))
        if group.startswith('frontier-'):
            frontier.append(SimpleNamespace(request=SimpleNamespace(**r),available=SimpleNamespace(**a['available'])))
        if group.startswith('native-timing-'):
            native.append(SimpleNamespace(request=SimpleNamespace(**r),available=SimpleNamespace(**a['available'])))
    assert len({r['attempt_id'] for r in raw})==len(raw)
    scores=validation_scores(validation,dict(zip(BUDGETS,[.25,.5,.25])))
    contenders={m['name']:m for m in read(OUT/'contenders.json')}
    assert set(scores)==set(contenders)
    statuses=defaultdict(Counter)
    for r in raw:
        if r['group'].startswith('validation-') and r['method'] in contenders: statuses[r['method']][r['status']]+=1
    def best(prefix):
        eligible=[n for n in scores if n.startswith(prefix) and not (set(statuses[n])-{'complete','deadline','startup_timeout'})]
        return max(eligible,key=lambda n:(scores[n],-Path(contenders[n]['allocator']['model_path']).stat().st_size if 'model_path' in contenders[n].get('allocator',{}) else 0,n)) if eligible else None
    capacity_scores=validation_scores(capacity,dict(zip(BUDGETS,[.25,.5,.25]))) if capacity else {}
    capacity_contenders={m['name']:m for m in read(OUT/'capacity-contenders.json')} if capacity else {}
    capacity_selected={}
    for group,prefix in [('local','local-'),('B6','B6-')]:
        names=[n for n in capacity_scores if n.startswith(prefix) and not any(r['status'] not in ('complete','deadline','startup_timeout') for r in raw if r['group'].startswith('capacity-') and r['method']==n)]
        if names: capacity_selected[group]=max(names,key=lambda n:(capacity_scores[n],-Path(capacity_contenders[n]['allocator']['model_path']).stat().st_size))
    selected={c:best(c+'-') for c in ('B1','B2','B3','B4','B5','B6')}
    selected['B6-matched']=best('B6-ridge')
    selected['local-matched']=best('local-matched')
    selected['local']=best('local-')
    totals={}
    for group,rows in groups.items():
        totals[group]=dict(attempts=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
            full_request_ns=sum(r['full_request_ns'] for r in rows),publication_ns=sum(r['publication_ns'] for r in rows),
            worker_cpu_ns=sum(r['worker_cpu_ns'] or 0 for r in rows),parent_cpu_ns=sum(r['parent_cpu_ns'] or 0 for r in rows),
            trace_bytes=sum(r['trace_bytes'] for r in rows),overshoot_ns=sum(r['overshoot_ns'] for r in rows),
            max_rss_bytes=max(r['rss_bytes'] or 0 for r in rows))
    comparisons=[]
    main=[r for g,rs in groups.items() if g.startswith('validation-') for r in rs]
    b0={(r['instance_hash'],r['solver_seed'],r['budget_ns']):r for r in main if r['method']=='B0'}
    for method in scores:
        for budget in BUDGETS:
            rows=[r for r in main if r['method']==method and r['budget_ns']==budget]
            assert len(rows)==6 and len({r['instance_hash'] for r in rows})==6
            comparisons.append(dict(method=method,budget_ns=budget,originals=6,
                primal_mean=sum(r['available']['primal_original'] for r in rows)/6,
                dual_mean=sum(r['available']['dual_original'] for r in rows)/6,
                raw_gap_mean=sum(r['available']['primal_original']-r['available']['dual_original'] for r in rows)/6,
                primal_difference_vs_B0=sum(r['available']['primal_original']-b0[(r['instance_hash'],r['solver_seed'],budget)]['available']['primal_original'] for r in rows)/6,
                dual_difference_vs_B0=sum(r['available']['dual_original']-b0[(r['instance_hash'],r['solver_seed'],budget)]['available']['dual_original'] for r in rows)/6))
    batches=[dict(path=str(p.relative_to(ROOT)),**read(p)) for p in sorted(OUT.glob('*/batch-*/accounting.json'))]
    fits=[read(p) for p in sorted((OUT/'models').rglob('fit-card.json'))]
    diagnostics=defaultdict(list); diagnostic_rows=defaultdict(list)
    for row,a in actuals:
        if row['phase']=='validation':
            key=row['group'].split('-')[0]+':'+row['method']
            diagnostic_rows[key].append(row)
            diagnostics[key].extend(a['resources'].get('bidder_diagnostics',[]))
    all_measured={}
    for n,ds in diagnostics.items():
        rows=diagnostic_rows[n]
        all_measured[n]=dict(decisions=len(ds),loading_ns=dist([r['model_loading_ns'] for r in rows if r['model_loading_ns'] is not None]),
            extraction_ns=dist([d['feature_extraction_ns'] for d in ds]),prediction_ns=dist([d['prediction_ns'] for d in ds]),
            full_request_ns=dist([r['full_request_ns'] for r in rows]),publication_ns=dist([r['publication_ns'] for r in rows]),
            rss_bytes=dist([r['rss_bytes'] for r in rows if r['rss_bytes'] is not None]),
            worker_cpu_ns=sum(r['worker_cpu_ns'] or 0 for r in rows),parent_cpu_ns=sum(r['parent_cpu_ns'] or 0 for r in rows),
            trace_bytes=dist([r['trace_bytes'] for r in rows]),negative_selected_gains=sum(d.get('selected_gain',0)<0 for d in ds),
            overshoot_ns=dist([r['overshoot_ns'] for r in rows]),
            fallbacks=sum(d.get('fallback',False) for d in ds),expiry=sum(d.get('expired',False) for d in ds))
    measured={n.removeprefix('validation:'):v for n,v in all_measured.items() if n.startswith('validation:')}
    capacity_measured={n.removeprefix('capacity:'):v for n,v in all_measured.items() if n.startswith('capacity:')}
    write(OUT/'raw-outcomes.json',raw)
    frontier_scores=validation_scores(frontier,dict(zip(BUDGETS[1:],[.5,.5]))) if frontier else {}
    native_scores=validation_scores(native,dict(zip(BUDGETS,[.25,.5,.25]))) if native else {}
    stage_comparisons=[];frontier_pools=defaultdict(list)
    for stage,baseline in [('capacity','B0'),('native-timing','B0'),('frontier','frontier-B0')]:
        rows=[r for r in raw if r['group'].startswith(stage+'-')]
        reference={(r['instance_hash'],r['solver_seed'],r['budget_ns']):r for r in rows if r['method']==baseline}
        for method,budget in sorted({(r['method'],r['budget_ns']) for r in rows}):
            subset=[r for r in rows if r['method']==method and r['budget_ns']==budget]
            assert len(subset)==6 and len({r['instance_hash'] for r in subset})==6
            stage_comparisons.append(dict(stage=stage,method=method,budget_ns=budget,
                primal_mean=statistics.mean(r['available']['primal_original'] for r in subset),
                dual_mean=statistics.mean(r['available']['dual_original'] for r in subset),
                utility_mean=statistics.mean(r['available']['utility'] for r in subset),
                raw_gap_mean=statistics.mean(r['available']['primal_original']-r['available']['dual_original'] for r in subset),
                primal_difference_vs_B0=statistics.mean(r['available']['primal_original']-reference[(r['instance_hash'],r['solver_seed'],budget)]['available']['primal_original'] for r in subset),
                dual_difference_vs_B0=statistics.mean(r['available']['dual_original']-reference[(r['instance_hash'],r['solver_seed'],budget)]['available']['dual_original'] for r in subset)))
    for row,a in actuals:
        if not row['group'].startswith('frontier-'):continue
        decisions=a['resources'].get('allocation_decisions',[])
        trace=ROOT/row['path'];trace=trace.parent/'trace'
        if trace.exists():decisions=[read(p) for p in sorted(trace.glob('decision-*.json'))]
        for d in decisions:
            frontier_pools[row['method']].append((d['context']['frontier_size'],len(d['pool_ids'])))
    pool_summary={n:dict(decisions=len(v),maximum_frontier=max(x[0] for x in v),maximum_pool=max(x[1] for x in v),
        binding_decisions=sum(f>p for f,p in v),binding_rate=sum(f>p for f,p in v)/len(v)) for n,v in frontier_pools.items()}
    attribution={
        'estimate_one_node':scores.get('B2-estimate-L1'),
        'estimate_best_fixed':max(v for n,v in scores.items() if n.startswith('B2-estimate-')),
        'estimate_adaptive':scores[selected['B5']] if selected['B5'] else None,
        'learned_one_node':scores[selected['B3']] if selected['B3'] else None,
        'learned_best_fixed':scores[selected['B4']] if selected['B4'] else None,
        'learned_adaptive_matched_data':scores[selected['local-matched']] if selected['local-matched'] else None,
        'learned_adaptive_historical_asset':scores['local-historical-asset'],
        'native_plunging':scores['B0'],
        'native_best_measured':scores[selected['B1']] if selected['B1'] else None,
        'pooled_matched_capacity':scores[selected['B6-matched']] if selected['B6-matched'] else None,
        'pooled_best_capacity':scores[selected['B6']] if selected['B6'] else None}
    logging_costs={}
    for row in groups.get('logging',[]): logging_costs.setdefault(row['method'],[]).append(row)
    logging_summary={n:dict(requests=len(rs),full_ns=dist([r['full_request_ns'] for r in rs]),
        publication_ns=dist([r['publication_ns'] for r in rs]),trace_bytes=dist([r['trace_bytes'] for r in rs]),
        mean_utility=sum(r['available']['utility'] for r in rs)/len(rs)) for n,rs in logging_costs.items()}
    payload=dict(version=1,stage_comparisons=stage_comparisons,native_timing_scores=native_scores,frontier_pools=pool_summary,
        capacity_measured=capacity_measured,capacity_scores=capacity_scores,capacity_selected=capacity_selected,logging_diagnostic=logging_summary,ranking_by_horizon=attribution,frontier_scores=frontier_scores,scope='corrected-runtime exploratory public selection, no freeze or protected success claim',
        selected=selected,scores=scores,statuses={k:dict(v) for k,v in statuses.items()},raw_outcomes=str((OUT/'raw-outcomes.json').relative_to(ROOT)),
        raw_outcomes_sha256=sha(OUT/'raw-outcomes.json'),batch_accounting=batches,
        inclusive_batch_wall_ns=sum(b['total_observed_ns'] for b in batches),cost_groups=totals,comparisons=comparisons,measured=measured,
        fit_cards=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted((OUT/'models').rglob('fit-card.json'))],
        fit_stage_wall_ns=sum(f['wall_ns'] for f in fits),fit_stage_cpu_ns=sum(f['cpu_ns'] for f in fits),
        candidate_fits=[dict(control=f['control_id'],name=c['name'],status=c['status'],wall_ns=c['fit_wall_ns'],cpu_ns=c['fit_cpu_ns'],error=c.get('error')) for f in fits for c in f['candidates']],
        source_generations=sorted({r['source_hash'] for r in raw}),
        training_originals=sorted(set(g for f in fits for g in f['training_originals'])),validation_originals=sorted({r['instance_hash'] for r in main}),
        validation_weights=dict(zip(BUDGETS,[.25,.5,.25])),historical='Task12 585 attempts/scores are pre-fix; task12-fix1 is one integration, not reselection',
        limitations=['Only six public validation originals and one solver seed17; no final power or precision claim.',
            'Seeds17/43 are deterministic fits; exact equal exports are aliased explicitly, not independent training-distribution replicates.',
            'Pooled tabular uses unique candidate pools, not unseen all-frontier values; K treatment is measured separately.',
            'B4 retains its fixed lease even for a quantile tail exception; no q90 completion guarantee.',
            'Cold request/publication costs are observed, not subtracted or estimated; native paths are unchanged.'],
        reconstruction_ns=time.perf_counter_ns()-started)
    write(ROOT/'docs/superpowers/evidence/task13.json',payload)
    card={k:contenders[v] for k,v in selected.items() if v is not None}
    card.update({k:capacity_contenders[v] for k,v in capacity_selected.items()})
    card.update(B0=contenders['B0'],historical_local=contenders['local-historical-asset'])
    write(ROOT/'configs/mandatory_baselines.json',dict(version=1,scope=payload['scope'],selected=card,evidence='docs/superpowers/evidence/task13.json',all_contenders=str((OUT/'contenders.json').relative_to(ROOT)),tested_configurations=list(contenders.values()),capacity_configurations=list(capacity_contenders.values())))
    selection_scores={k:scores[v] if v else None for k,v in selected.items()}
    selection_scores.update({k:capacity_scores[v] for k,v in capacity_selected.items()})
    write(ROOT/'docs/superpowers/evidence/task13-controls-card.json',dict(selected=card,capacity_scores=capacity_scores,capacity_selected=capacity_selected,
        scores=selection_scores,selection_stage={k:'capacity' if k in capacity_selected else 'main' for k in selected},
        main_stage_selected=selected,features={'local':192,'pooled_tabular':301},fits=payload['fit_cards'],limitations=payload['limitations']))
    print(json.dumps(dict(selected=selected,scores={k:scores[v] if v else None for k,v in selected.items()},costs=totals),indent=2))

if __name__=='__main__':summarize()
