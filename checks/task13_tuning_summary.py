"""Separate fix1 outcomes, actual-regime stops and current control selection."""
from collections import Counter,defaultdict
import copy
import json
from pathlib import Path
import statistics
import time
from task13_tuning import FIX,OUT,ROOT,BUDGETS,LENGTHS,read,scores,expansion_request
from task13_summary import sha,write,dist


def main():
    from ra.runner import _runtime_identity
    started,cpu=time.perf_counter_ns(),time.process_time_ns()
    source=_runtime_identity()[0];assert source==read(FIX/'protocol.json')['source_hash']
    stages={};all_rows=[];inventory=[]
    for stage,budgets in [('screen',[BUDGETS[1]]),('final',BUDGETS)]:
        rows=[];diagnostics=defaultdict(list)
        for budget in budgets:
            for path in sorted((FIX/f'{stage}-{budget}').glob('attempts/*/*/attempt.json')):
                a=read(path);r=a['request'];res=a['resources'];account=read(path.parent/'accounting.json')
                assert account['manifest_sha256']==sha(path) and account['attempt_id']==a['attempt_id']
                assert r['code_hash']==source and a['status'] in ('complete','deadline') and r['phase']=='validation'
                name=r['method'];allocator=r['method_config'].get('allocator',{})
                if name.startswith('fix1-B5-'):assert allocator['control_id']=='B5'
                elif name.startswith('fix1-L'):
                    length=int(name.split('-')[1][1:]);assert allocator['control_id']==('B3' if length==1 else 'B4')
                    if length!=1:assert allocator['fixed_length']==length
                row=dict(stage=stage,path=str(path.relative_to(ROOT)),attempt_id=a['attempt_id'],request_id=r['request_id'],
                    source_hash=r['code_hash'],environment_hash=r['environment_hash'],model_hash=r.get('model_hash'),
                    method=name,instance_hash=r['instance_hash'],cell=a['lineage']['cell'],template_id=a['template_id'],solver_seed=r['solver_seed'],
                    budget_ns=budget,status=a['status'],available=a['available'],full_request_ns=account['total_observed_ns'],
                    publication_ns=account['publication_ns'],worker_cpu_ns=res.get('worker_cpu_ns'),parent_cpu_ns=res.get('parent_cpu_ns'),
                    peak_rss_bytes=res.get('worker_peak_rss_bytes'),trace_bytes=res['trace_bytes'],overshoot_ns=a['overshoot_ns'],
                    model_loading_ns=res.get('model_loading_ns'),model_bytes=res.get('model_bytes'))
                rows.append(row);diagnostics[name].extend(res.get('bidder_diagnostics',[]))
                inventory.append(dict(path=row['path'],sha256=sha(path),accounting_sha256=sha(path.parent/'accounting.json')))
        stage_scores=scores(stage,budgets);measured={};comparisons=[]
        for name in stage_scores:
            own=[r for r in rows if r['method']==name];ds=diagnostics[name]
            measured[name]=dict(requests=len(own),statuses=dict(Counter(r['status'] for r in own)),
                full_request_ns=dist([r['full_request_ns'] for r in own]),publication_ns=dist([r['publication_ns'] for r in own]),
                worker_cpu_ns=sum(r['worker_cpu_ns'] or 0 for r in own),parent_cpu_ns=sum(r['parent_cpu_ns'] or 0 for r in own),
                peak_rss_bytes=max(r['peak_rss_bytes'] or 0 for r in own),trace_bytes=sum(r['trace_bytes'] for r in own),
                overshoot_ns=sum(r['overshoot_ns'] for r in own),prediction_ns=dist([d['prediction_ns'] for d in ds]),
                extraction_ns=dist([d['feature_extraction_ns'] for d in ds]),loading_ns=dist([r['model_loading_ns'] for r in own if r['model_loading_ns'] is not None]))
            for budget in budgets:
                subset=[r for r in own if r['budget_ns']==budget]
                assert len(subset)==6 and len({r['instance_hash'] for r in subset})==6
                comparisons.append(dict(method=name,budget_ns=budget,
                    utility_mean=statistics.mean(r['available']['utility'] for r in subset),
                    primal_mean=statistics.mean(r['available']['primal_original'] for r in subset),
                    dual_mean=statistics.mean(r['available']['dual_original'] for r in subset),
                    raw_gap_mean=statistics.mean(r['available']['primal_original']-r['available']['dual_original'] for r in subset)))
        stages[stage]=dict(scores=stage_scores,measured=measured,comparisons=comparisons,requests=len(rows),
            totals={k:sum(r[k] or 0 for r in rows) for k in ('full_request_ns','publication_ns','worker_cpu_ns','parent_cpu_ns','trace_bytes','overshoot_ns')},
            peak_rss_bytes=max(r['peak_rss_bytes'] for r in rows),statuses=dict(Counter(r['status'] for r in rows)))
        all_rows.extend(rows)
    assert stages['screen']['requests']==222 and stages['final']['requests']==270 and len({r['attempt_id'] for r in all_rows})==492
    final=stages['final'];methods={m['name']:m for m in read(FIX/'final-protocol.json')['methods']}
    def best(prefix):
        return max((n for n in final['scores'] if n.startswith(prefix)),key=lambda n:(final['scores'][n],
            -final['measured'][n]['full_request_ns']['sum'],-Path(methods[n]['allocator']['model_path']).stat().st_size,n))
    selected={'B3':best('fix1-L1-'),'B4':best('fix1-L'),'B5':best('fix1-B5-')};stops={}
    for control,name in selected.items():
        baseline='fix1-B5-ridge1' if control=='B5' else 'fix1-L1-ridge1'
        gain=final['scores'][name]-final['scores'][baseline]
        ratio=final['measured'][name]['full_request_ns']['sum']/final['measured'][baseline]['full_request_ns']['sum']
        prediction=final['measured'][name]['prediction_ns']['median']
        requested=expansion_request(name,gain,ratio,prediction)
        stops[control]=dict(selected=name,baseline=baseline,utility_gain=gain,cold_cost_ratio=ratio,median_prediction_ns=prediction,
            requested_expansion=requested,reason='Observed improvement below predeclared .0002 outward-allocation trigger; retain finite tuned search and omitted-budget uncertainty')
        assert requested is None,'Measured rule requires prospectively sealed further fit/validation before completion'
    fits=[read(p) for p in sorted((FIX/'models').glob('*/fit-card.json'))]
    assert sum(len(f['candidates']) for f in fits)==23 and all(c['status']=='fitted' for f in fits for c in f['candidates'])
    batches=[dict(path=str(p.relative_to(ROOT)),**read(p)) for p in sorted(FIX.glob('*-*/batch-*/accounting.json'))]
    write(FIX/'raw-outcomes.json',all_rows)
    model_index=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted((FIX/'models').glob('*/*')) if p.is_file()]
    write(FIX/'artifact-index.json',dict(attempts=inventory,models=model_index,source_hash=source))
    evidence=dict(scope='Review fix1 public actual-regime bounded tuning; no protected/frozen/superiority claim',
        source_hash=source,stages=stages,selected=selected,stopping=stops,
        fit_resources=read(FIX/'fit-resources.json'),new_candidate_fits=23,new_fits_including_curves=69,
        reused_B5_assets=['local-capacity/hist7-seed17.json','local-capacity/hist15-seed17.json','local-capacity-expanded/hist31-seed17.json'],
        training_originals=12,validation_originals=6,solver_seeds=[17],fit_seeds=[17],
        fit_cards=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),data_hash=read(p)['data_hash']) for p in sorted((FIX/'models').glob('*/fit-card.json'))],
        protocol=read(FIX/'protocol.json'),final_protocol=read(FIX/'final-protocol.json'),
        batch_accounting=batches,inclusive_batch_wall_ns=sum(b['total_observed_ns'] for b in batches),
        raw_outcomes=dict(path=str((FIX/'raw-outcomes.json').relative_to(ROOT)),sha256=sha(FIX/'raw-outcomes.json')),
        artifact_index=dict(path=str((FIX/'artifact-index.json').relative_to(ROOT)),sha256=sha(FIX/'artifact-index.json')),
        historical=dict(attempts=1614,evidence='docs/superpowers/evidence/task13.json',preserved=True),
        limitations=['Screening omitted short/long budget outcomes; no global or every-model saturation claim.',
            'B5 improvement is smaller than previously observed timing displacement; no confirmed effect.',
            'B3/B4-L1 share one identical logical policy/asset and physical outcome set.',
            'Seed17 and reused assets are conditional-on-fit evidence; no independent original or fit population added.'],
        reconstruction_wall_ns=time.perf_counter_ns()-started,reconstruction_cpu_ns=time.process_time_ns()-cpu)
    write(ROOT/'docs/superpowers/evidence/task13-fix1.json',evidence)
    mandatory=read(ROOT/'configs/mandatory_baselines.json')
    for control,name in selected.items():
        method=copy.deepcopy(methods[name])
        if control=='B4':
            length=int(name.split('-')[1][1:]);method['allocator'].update(control_id='B4',fixed_length=length)
            method['name']='fix1-B4-'+name.removeprefix('fix1-')
        mandatory['selected'][control]=method
    mandatory['prior_evidence']='docs/superpowers/evidence/task13.json'
    mandatory['evidence']='docs/superpowers/evidence/task13-fix1.json'
    mandatory['selection_evidence']={k:'docs/superpowers/evidence/task13-fix1.json' if k in selected else 'docs/superpowers/evidence/task13-controls-card.json' for k in mandatory['selected']}
    mandatory['tuning_configurations']=read(FIX/'screen-contenders.json')
    write(ROOT/'configs/mandatory_baselines.json',mandatory)
    write(ROOT/'docs/superpowers/evidence/task13-fix1-controls-card.json',dict(selected=mandatory['selected'],selection_evidence=mandatory['selection_evidence'],
        selected_scores={k:final['scores'][v] for k,v in selected.items()},stopping=stops,source_hash=source,
        alias='B4-L1 is the B3 L1 policy/asset with identical action support; shared physical outcomes counted once',limitations=evidence['limitations']))
    print(json.dumps(dict(selected=selected,stops=stops,costs={k:v['totals'] for k,v in stages.items()}),indent=2))


if __name__=='__main__':main()
