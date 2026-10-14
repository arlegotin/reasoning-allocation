"""Named local/global histogram capacity uncertainty on identical training rows."""
import copy
import json
from pathlib import Path
import resource
import sys
import time
from task13_controls import OUT,ROOT,BUDGETS,base,read,write


def fit():
    from ra.train import fit_control
    started,cpu=time.perf_counter_ns(),time.process_time_ns()
    config=read(OUT/'fit-B5.json')
    config['training']['grid']=read(OUT/'fit-B6.json')['training']['grid'][1:]
    write(OUT/'fit-local-capacity.json',config)
    protocol=dict(reason='Main matched-data local was ridge only; histogram pooling contrasts need local models at identical capacity/data.',
        source_generation='source-generation-2.json',originals=12,rows=6564,seeds=[17,43],
        training_config=str(OUT/'fit-local-capacity.json'),validation_budgets_ns=BUDGETS,
        validation_indices=list(range(0,12,2)),solver_seeds=[17],weights=[.25,.5,.25],
        scope='Fresh fits, all costs retained; exact deterministic export aliases do not represent distribution replicates.')
    write(OUT/'capacity-protocol.json',protocol)
    result=fit_control('B5',OUT/'fit-local-capacity.json',OUT/'collection-L1',OUT/'models/local-capacity')
    write(OUT/'capacity-fitting-resources.json',dict(result=result,wall_ns=time.perf_counter_ns()-started,
        cpu_ns=time.process_time_ns()-cpu,peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
        scope='Separate local histogram refit process, including imports/configuration and fitting; nested fit-card costs are not added twice.'))
    print(result,flush=True)


def expand():
    from ra.train import fit_control
    summary=read(ROOT/'docs/superpowers/evidence/task13.json')
    candidate=dict(name='hist31',kind='histogram',parameters=dict(max_iter=160,max_leaf_nodes=31,min_samples_leaf=10),quantile=True)
    write(OUT/'capacity-expansion-protocol.json',dict(reason='Pooled hist15 wins the upper edge of the initial measured capacity grid; compare one larger matched local/global rung.',
        prior_scores={n:v for n,v in summary['scores'].items() if n.startswith('B6-')},
        prior_costs={n:v for n,v in summary['measured'].items() if n.startswith('B6-')},
        candidate=candidate,fit_seeds=[17,43],training_rows=6564,validation_budgets_ns=BUDGETS,
        stopping='Use measured quality, inference/total costs and held-original learning trend to decide resource value; no expansion from favorable rank alone.'))
    started,cpu=time.perf_counter_ns(),time.process_time_ns();results=[]
    for control,name in [('B5','local-capacity-expanded'),('B6','B6-capacity-expanded')]:
        config=read(OUT/('fit-B5.json' if control=='B5' else 'fit-B6.json'))
        config['training']['grid']=[candidate]
        path=OUT/f'fit-{name}.json';write(path,config)
        result=fit_control(control,path,OUT/'collection-L1',OUT/f'models/{name}');results.append(result)
        print(name,result,flush=True)
    write(OUT/'capacity-expansion-resources.json',dict(results=results,wall_ns=time.perf_counter_ns()-started,
        cpu_ns=time.process_time_ns()-cpu,peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
        scope='Separate matched local/global hist31 fitting process; nested fit-card costs are not summed twice.'))


def validate():
    from ra.train import learned_method
    from ra.config import load_feature_schema
    from ra.runner import run_schedule
    summary=read(ROOT/'docs/superpowers/evidence/task13.json')
    original={m['name']:m for m in read(OUT/'contenders.json')}
    names=['B0',summary['selected']['B1'],'local-matched-ridge1-seed17',
           'B6-ridge1-seed17','B6-hist7-seed17','B6-hist15-seed17']
    methods=[copy.deepcopy(original[n]) for n in names]
    schema=load_feature_schema(ROOT/'configs/features.json')
    aliases=[]
    for directory,pooled in [('local-capacity',False),('local-capacity-expanded',False),('B6-capacity-expanded',True)]:
        card=read(OUT/f'models/{directory}/fit-card.json');seen={}
        for record in card['candidates']:
            if record['status']!='fitted':continue
            raw=read(record['asset'])
            signature=json.dumps({k:raw[k] for k in ('gain','body','q90','preprocessing','schema_hash','supported_lengths')},sort_keys=True)
            if signature in seen:
                aliases.append(dict(asset=record['asset'],equivalent_deployment=seen[signature],reason='exact numeric predictors/preprocessing/support equal'))
                continue
            name=('B6-' if pooled else 'local-capacity-')+record['name'];seen[signature]=name
            m=learned_method(record['asset'],ROOT/'configs/features.json',schema,name=name,c_min=4.2e-8,fallback_length=4)
            if pooled:m['allocator']['control_id']='B6'
            m['learned'].update(pool_seed=17,behavior_seed=17,compact_logging=True)
            methods.append(m)
    write(OUT/'capacity-fit-aliases.json',aliases);write(OUT/'capacity-contenders.json',methods)
    for budget in BUDGETS:
        c=base();c.update(input_manifests=[str(OUT/'validation-inputs/selected-manifest.json')],methods=methods,solver_seeds=[17],budgets_ns=[budget])
        path=OUT/f'capacity-{budget}.json';write(path,c)
        rows=run_schedule(path,'validation',OUT/f'capacity-{budget}',resume=False)
        print('capacity',budget,len(rows),{str(a.status) for a in rows},flush=True)

if __name__=='__main__':{'fit':fit,'expand':expand,'validate':validate}[sys.argv[1]]()
