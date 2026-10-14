"""Prospective bounded tuning in actual B3/B4/B5 deployment regimes."""
import copy
import json
from pathlib import Path
import resource
import sys
import time
from task13_controls import OUT,ROOT,LENGTHS,BUDGETS,base,read,write

FIX=OUT/'fix1'
ANCHORS=('B0','B1-no-plunge','B2-estimate-L1')
GRID=[dict(name='ridge0p1',kind='ridge',parameters={'alpha':.1}),
      dict(name='ridge10',kind='ridge',parameters={'alpha':10.}),
      dict(name='hist7',kind='histogram',parameters=dict(max_iter=30,max_leaf_nodes=7,min_samples_leaf=10),quantile=True)]


def deployment(template,name,asset,model_hash,control,length=None):
    method=copy.deepcopy(template);method['name']=name
    method['allocator'].update(model_path=str(asset),model_hash=model_hash,control_id=control)
    method['allocator'].pop('fixed_length',None)
    if control=='B4':method['allocator']['fixed_length']=length
    method['learned'].update(pool_seed=17,behavior_seed=17,compact_logging=True)
    return method


def survivors(methods,scores):
    chosen=set(ANCHORS)|{'fix1-L1-ridge1','fix1-B5-ridge1'}
    order=lambda names:sorted(names,key=lambda n:(-scores[n],n))
    fixed=[]
    for length in LENGTHS:
        names=order(n for n in scores if n.startswith(f'fix1-L{length}-'))
        chosen.add(names[0]);fixed.extend(names)
        if length==1:chosen.add(names[1])
    chosen.add(order(n for n in fixed if n not in chosen)[0])
    chosen.update(order(n for n in scores if n.startswith('fix1-B5-'))[:2])
    assert len(chosen)<=16
    return [m for m in methods if m['name'] in chosen]


def expansion_request(name,utility_gain,cold_cost_ratio,median_prediction_ns):
    if utility_gain < .0002 or cold_cost_ratio > 1.25 or median_prediction_ns > 5_000_000:
        return None
    return {'ridge0p1':'ridge0p01','ridge10':'ridge100','hist7':'hist15'}.get(name.rsplit('-',1)[1])


def prepare():
    from ra.runner import _runtime_identity
    source,environment,build,_=_runtime_identity()
    write(FIX/'protocol.json',dict(version=1,reason='Review I1: fresh B3/B4/B5 actual-regime tuning lacked stopping evidence',
        base_commit='328013b',source_hash=source,environment_hash=environment,build_hash=build,
        training_indices=list(range(12)),validation_indices=list(range(0,12,2)),solver_seeds=[17],fit_seeds=[17],
        exact_regimes=LENGTHS,new_regime_grid=GRID,new_B5_grid=GRID[:2],
        reuse='alpha1 exact-regime assets; B5 matched6564-row hist7/15/31 assets deployed with control_id=B5; no duplicate fits',
        fit_candidates=23,fit_executions_including_two_curves_each=69,
        screen=dict(budgets_ns=[BUDGETS[1]],methods=37,originals=6,requests=222,
                    purpose='Resource screening only; omitted candidates have unmeasured short/long-budget advantages, flagged explicitly'),
        survivors='Winner per fixed regime; L1 runner-up; highest remaining fixed contender; top2 B5; original L1/B5 ridge1; B0/no-plunge/estimate-L1. At most16 methods; exact count/config sealed after screening, before timing.',
        final=dict(budgets_ns=BUDGETS,weights=[.25,.5,.25],requests_max=288),
        selection='Completed three-budget weighted utility, ties lower total cold request wall then model bytes/name; no seed aliases or screen score used as final score.',
        expansion=dict(utility_threshold=.0002,max_cold_cost_ratio=1.25,max_median_prediction_ns=5000000,
            rule='Only the best B3, best B4 and best B5 deployments: if improvement over same-stage ridge1 original baseline >=.0002 and full cold sum ratio<=1.25 and measured median inference<=5ms, extend a winning alpha.1/10 boundary once to.01/100, or winning hist7 once tohist15. Reuse B5 assets when identical. Deduplicate L1. Other fixed regimes are bounded joint-search screening, not globally saturated.',
            max_new_candidates=3,max_additional_methods=9,max_requests=162),
        resource_stop='One actual-regime nonlinear rung and two regularization neighbors per regime, hierarchical survivor allocation, at mostone conditional outward step for each winning control. Further tuning stops at this finite resource allocation; report any continuing trend, do not call it statistical/global convergence.',
        max_new_requests=672,scope='Public exploratory conditional-on-fit tuning; six originals remain six; preserve all previous1614 attempts/cards; no protected outcomes',
        run_order_seed=base()['run_order_seed'],source_freeze='No runtime changes, fitting or tests during timed stages'))
    print('prospective protocol sealed',flush=True)


def fit():
    started,cpu=time.perf_counter_ns(),time.process_time_ns()
    from ra.train import fit_control
    results=[]
    for length in LENGTHS+[None]:
        name='B5' if length is None else f'L{length}'
        control='B5' if length is None else 'B3' if length==1 else 'B4'
        original='B5' if length is None else 'B3' if length==1 else f'B4-L{length}'
        config=read(OUT/f'fit-{original}.json')
        config['training'].update(grid=GRID[:2] if length is None else GRID,fit_seeds=[17])
        path=FIX/f'fit-{name}.json';write(path,config)
        result=fit_control(control,path,OUT/f'collection-L{length or 1}',FIX/f'models/{name}')
        results.append(result);print(name,result,flush=True)
    write(FIX/'fit-resources.json',dict(results=results,wall_ns=time.perf_counter_ns()-started,cpu_ns=time.process_time_ns()-cpu,
        peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
        scope='Full tuning fit process from pre-import through export, includes nested fit-card stages; do not add both'))


def methods():
    from ra.train import sha
    originals={m['name']:m for m in read(OUT/'contenders.json')}
    result=[originals[n] for n in ANCHORS]
    for length in LENGTHS+[None]:
        name='B5' if length is None else f'L{length}'
        control='B5' if length is None else 'B3' if length==1 else 'B4'
        original='B5' if length is None else 'B3' if length==1 else f'B4-L{length}'
        template=originals[original+'-ridge1-seed17']
        candidates=[('ridge1',template['allocator']['model_path'])]
        fitcard=read(FIX/f'models/{name}/fit-card.json')
        assert fitcard['rows']==read(OUT/f'models/{original}/fit-card.json')['rows']
        candidates += [(c['name'].removesuffix('-seed17'),c['asset']) for c in fitcard['candidates'] if c['status']=='fitted']
        if length is None:
            for model,directory in [('hist7','local-capacity'),('hist15','local-capacity'),('hist31','local-capacity-expanded')]:
                reused=read(OUT/f'models/{directory}/fit-card.json')
                assert (reused['rows']==6564 and reused['training_originals']==fitcard['training_originals']
                        and reused['data_hash']==fitcard['data_hash'])
                candidates.append((model,str(OUT/f'models/{directory}/{model}-seed17.json')))
        for model,asset in candidates:
            raw=read(asset);assert raw['supported_lengths']==([length] if length is not None else LENGTHS)
            result.append(deployment(template,f'fix1-{name}-{model}',asset,sha(asset),control,length))
    assert len(result)==37
    return result


def run(stage,contenders,budgets):
    from ra.runner import run_schedule,_runtime_identity
    assert _runtime_identity()[0]==read(FIX/'protocol.json')['source_hash']
    for budget in budgets:
        config=base();config.update(input_manifests=[str(OUT/'validation-inputs/selected-manifest.json')],
                                   methods=contenders,solver_seeds=[17],budgets_ns=[budget])
        path=FIX/f'{stage}-{budget}.json';write(path,config)
        rows=run_schedule(path,'validation',FIX/f'{stage}-{budget}',resume=False)
        print(stage,budget,len(rows),{str(a.status) for a in rows},flush=True)


def scores(stage,budgets):
    from types import SimpleNamespace
    from ra.train import validation_scores
    rows=[]
    for budget in budgets:
        for path in sorted((FIX/f'{stage}-{budget}').glob('attempts/*/*/attempt.json')):
            a=read(path);assert a['status'] in ('complete','deadline')
            rows.append(SimpleNamespace(request=SimpleNamespace(**a['request']),available=SimpleNamespace(**a['available'])))
    return validation_scores(rows,dict(zip(budgets,[1.] if len(budgets)==1 else [.25,.5,.25])))


def screen():
    contenders=methods();write(FIX/'screen-contenders.json',contenders)
    run('screen',contenders,[BUDGETS[1]])


def final():
    contenders=read(FIX/'screen-contenders.json');screen_scores=scores('screen',[BUDGETS[1]])
    chosen=survivors(contenders,screen_scores)
    write(FIX/'final-protocol.json',dict(screen_scores=screen_scores,methods=chosen,requests=len(chosen)*18,
        budgets_ns=BUDGETS,originals=6,solver_seeds=[17],weights=[.25,.5,.25],
        omitted=[dict(method=m['name'],flag='Short/long-budget rank unmeasured; screened under finite resource allocation, not declared saturated') for m in contenders if m not in chosen]))
    run('final',chosen,BUDGETS)


if __name__=='__main__':{'prepare':prepare,'fit':fit,'screen':screen,'final':final}[sys.argv[1]]()
