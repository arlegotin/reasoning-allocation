"""Prospective Task13 collection, fitting and serial public validation.

Each stage writes new immutable artifacts. No protected data or historical
selection replay; original generator indices and six cell assignments persist.
"""
from pathlib import Path
import copy
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/task13'
LENGTHS=[1,2,4,8,16,32,64]
BUDGETS=[526707240,2106828958,8427315832]

def read(path): return json.loads(Path(path).read_text())
def write(path,payload):
    from ra.runner import _atomic_json
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    _atomic_json(Path(path),payload,immutable=True)

def base():
    c=read(ROOT/'configs/task12-final-train.json')
    return {k:v for k,v in c.items() if k not in ('training','collection')}

def prepare():
    from ra.config import load_config,load_feature_schema
    from ra.data import generate_workload
    from ra.collect import selected_training_manifest
    from ra.runner import _runtime_identity
    import shutil
    OUT.mkdir(parents=True,exist_ok=True)
    generation=load_config(ROOT/'configs/workload_manifest.json','generation')
    for phase,indices in [('train',list(range(12))),('validation',list(range(0,12,2)))]:
        manifest=generate_workload(generation,phase,OUT/(phase+'-inputs'))
        write(OUT/(phase+'-inputs')/'selected-manifest.json',selected_training_manifest(manifest,indices))
    source,env,build,inventory=_runtime_identity()
    write(OUT/'source-generation-1.json',dict(source_hash=source,environment_hash=env,build_hash=build,inventory=inventory))
    shutil.copytree(ROOT/'src/ra',OUT/'source-generation-1',ignore=shutil.ignore_patterns('__pycache__'))
    schema=load_feature_schema(ROOT/'configs/features.json')
    protocol=dict(version=1,purpose='B3/B4 exact action-regime support gaps; B6 pooled collection',
        train_indices=list(range(12)),validation_indices=list(range(0,12,2)),solver_seeds=[17],lengths=LENGTHS,
        budgets_ns=BUDGETS,weights=[.25,.5,.25],pool_seed=17,behavior_seed=20261014131,
        fixed_support='one separate run per supported length; epsilon .2 within that node/action support',
        preserved_mapping='configs/workload_manifest.json unchanged, no generator offset',
        stopping='all seven supported lengths; B6 matched ridge then hist7/hist15 capacity; native current-cohort selector/plunge neighbors; K32/128/512/all diagnostic',
        limitations='12 existing training originals, six existing public validation originals; deterministic fit seeds are not distribution replicates')
    write(OUT/'protocol.json',protocol)
    for length in LENGTHS:
        c=base();c.update(input_manifests=[str(OUT/'train-inputs/selected-manifest.json')],solver_seeds=[17],budgets_ns=BUDGETS,lease_lengths=[length],
            methods=[dict(name=f'collect-L{length}',kind='shared',pool_size=128,allocator=dict(policy='estimate',length=length),
                collection=dict(epsilon=.2,pool_seed=17,behavior_seed=20261014131,schema_path=str(ROOT/'configs/features.json'),
                                schema_hash=schema.hash,max_decisions=512,compact_logging=True))])
        write(OUT/f'collection-L{length}.json',c)
    print('prepared',flush=True)

def collect():
    from ra.runner import run_schedule
    for length in LENGTHS:
        started=time.perf_counter_ns()
        rows=run_schedule(OUT/f'collection-L{length}.json','train',OUT/f'collection-L{length}',resume=False)
        print('collected',length,len(rows),round((time.perf_counter_ns()-started)/1e9,2),{str(a.status) for a in rows},flush=True)

def fitting():
    from ra.train import fit_control
    for control,length in [('B3',1)]+[('B4',n) for n in LENGTHS[1:]]+[('B5',None),('B6',None)]:
        name=control+(f'-L{length}' if control=='B4' else '')
        c=base(); opts=read(ROOT/'configs/task12-final-train.json')['training']
        opts.update(schema=str(ROOT/'configs/features.json'),generation_config=str(ROOT/'configs/workload_manifest.json'),
            defer_validation=True,validation_extra_methods=[],additional_trace_roots=[],fallback_lengths=[4],fit_seeds=[17,43])
        if control=='B4': opts['fixed_length']=length
        if control=='B6':
            opts['grid']=[dict(name='ridge1',kind='ridge',parameters={'alpha':1.}),
                dict(name='hist7',kind='histogram',parameters=dict(max_iter=30,max_leaf_nodes=7,min_samples_leaf=10),quantile=True),
                dict(name='hist15',kind='histogram',parameters=dict(max_iter=80,max_leaf_nodes=15,min_samples_leaf=10),quantile=True)]
        if control in ('B5','B6'):
            trace=OUT/'collection-L1'
            opts['additional_trace_roots']=[str(OUT/f'collection-L{n}') for n in LENGTHS[1:]] + [str(ROOT/'data/traces/train'),str(ROOT/'data/traces/task12-odd')]
        else: trace=OUT/f'collection-L{length}'
        c['training']=opts
        write(OUT/f'fit-{name}.json',c)
        print(name,fit_control(control,OUT/f'fit-{name}.json',trace,OUT/f'models/{name}'),flush=True)

def methods():
    from ra.config import load_feature_schema
    from ra.train import learned_method
    schema=load_feature_schema(ROOT/'configs/features.json')
    methods=[dict(name='B0',kind='native',overrides={}),dict(name='B1-historical-default',kind='native',overrides={})]
    native={'no-plunge':{'nodeselection/estimate/maxplungedepth':0},
            'plunge2':{'nodeselection/estimate/maxplungedepth':2},
            'plunge8':{'nodeselection/estimate/maxplungedepth':8},
            'plunge32':{'nodeselection/estimate/maxplungedepth':32},
            **{s:{f'nodeselection/{s}/stdpriority':300000} for s in ('bfs','dfs','breadthfirst')}}
    methods += [dict(name='B1-'+n,kind='native',overrides=o) for n,o in native.items()]
    for policy in ('fifo','round_robin_parent_groups','uniform','estimate','bound','deepest'):
        for length in ([1,2,4,8,16,32,64] if policy in ('estimate','bound') else [1,4,16]):
            methods.append(dict(name=f'B2-{policy}-L{length}',kind='shared',pool_size=128,allocator=dict(policy=policy,length=length)))
    for bins,lengths in [([.52670724,2.106828958],[1,4,16]),([.26335362,1.053414479],[1,16,64])]:
        methods.append(dict(name='B2-budget-'+str(lengths[-1]),kind='shared',pool_size=128,
                            allocator=dict(policy='budget_sensitive',remaining_time_bins=bins,bin_lengths=lengths)))
    local=read(ROOT/'docs/superpowers/evidence/task12-model-card.json')['selected']
    local=copy.deepcopy(local);local['name']='local-historical-asset';local['learned'].update(pool_seed=17,behavior_seed=17,compact_logging=True)
    methods.append(local)
    aliases=[]
    for directory in sorted((OUT/'models').iterdir()):
        equivalent={}
        card=read(directory/'fit-card.json');control=card['control_id']
        for record in card['candidates']:
            if record['status']!='fitted': continue
            raw=read(record['asset'])
            signature=json.dumps({k:raw[k] for k in ('gain','body','q90','preprocessing','schema_hash','supported_lengths')},sort_keys=True)
            if signature in equivalent:
                aliases.append(dict(asset=record['asset'],equivalent_deployment=equivalent[signature],reason='exact exported numerical predictors/preprocessing/support equal; deterministic seed fit retained, no independent replicate'))
                continue
            equivalent[signature]=directory.name+'-'+record['name']
            m=learned_method(record['asset'],ROOT/'configs/features.json',schema,name=directory.name+'-'+record['name'],c_min=4.2e-8,fallback_length=4)
            m['allocator']['control_id']=control
            if control=='B4': m['allocator']['fixed_length']=int(directory.name.split('-L')[1])
            m['learned'].update(pool_seed=17,behavior_seed=17,compact_logging=True)
            methods.append(m)
            if control=='B3':
                fixed=copy.deepcopy(m);fixed['name']='B4-L1-'+record['name']
                fixed['allocator'].update(control_id='B4',fixed_length=1)
                methods.append(fixed)
            if control=='B5':
                matched=copy.deepcopy(m);matched['name']='local-matched-'+record['name'];matched['allocator'].pop('control_id')
                methods.append(matched)
    if not (OUT/'deterministic-fit-aliases.json').exists(): write(OUT/'deterministic-fit-aliases.json',aliases)
    return methods

def validate():
    from ra.runner import run_schedule
    contenders=methods()
    write(OUT/'contenders.json',contenders)
    for budget in BUDGETS:
        c=base();c.update(input_manifests=[str(OUT/'validation-inputs/selected-manifest.json')],methods=contenders,solver_seeds=[17],budgets_ns=[budget])
        path=OUT/f'validation-{budget}.json';write(path,c)
        rows=run_schedule(path,'validation',OUT/f'validation-{budget}',resume=False)
        print('validated',budget,len(rows),{str(a.status) for a in rows},flush=True)

def frontier():
    from ra.runner import run_schedule
    summary=read(ROOT/'docs/superpowers/evidence/task13.json')
    contenders={m['name']:m for m in read(OUT/'contenders.json')}
    estimate=max((n for n in summary['scores'] if n.startswith('B2-estimate-')),key=lambda n:summary['scores'][n])
    if summary.get('capacity_selected'):
        contenders.update({m['name']:m for m in read(OUT/'capacity-contenders.json')})
    names=[estimate,summary.get('capacity_selected',{}).get('local',summary['selected']['local-matched']),summary.get('capacity_selected',{}).get('B6',summary['selected']['B6'])]
    variants=[dict(name='frontier-B0',kind='native',overrides={})]
    for name in names:
        for k in (32,128,512,None):
            m=copy.deepcopy(contenders[name]);m['name']=name+'-K'+str(k if k else 'all');m['pool_size']=k
            variants.append(m)
    write(OUT/'frontier-protocol.json',dict(reason='candidate filtering/frontier uncertainty, measured all-frontier at public feasible scale',
        methods=variants,budgets_ns=BUDGETS[1:],originals=6,solver_seeds=[17],requests=156,
        reporting='binding pool rate and maximum observed frontier; K512/all may be identical support',
        fit_status='diagnostic on fixed selected assets; no unobserved past pools reconstructed'))
    for budget in BUDGETS[1:]:
        c=base();c.update(input_manifests=[str(OUT/'validation-inputs/selected-manifest.json')],methods=variants,solver_seeds=[17],budgets_ns=[budget])
        path=OUT/f'frontier-{budget}.json';write(path,c)
        rows=run_schedule(path,'validation',OUT/f'frontier-{budget}',resume=False)
        print('frontier',budget,len(rows),{str(a.status) for a in rows},flush=True)

def logging_diagnostic():
    from ra.runner import run_schedule
    summary=read(ROOT/'docs/superpowers/evidence/task13.json')
    contenders={m['name']:m for m in read(OUT/'contenders.json')}
    methods=[]
    if summary.get('capacity_selected'):
        contenders.update({m['name']:m for m in read(OUT/'capacity-contenders.json')})
    for name in ('local-historical-asset',summary.get('capacity_selected',{}).get('B6',summary['selected']['B6'])):
        for compact in (False,True):
            m=copy.deepcopy(contenders[name]);m['name']='logging-'+name+('-compact' if compact else '-full')
            m['learned']['compact_logging']=compact;methods.append(m)
    c=base();c.update(input_manifests=[str(OUT/'validation-inputs/selected-manifest.json')],methods=methods,solver_seeds=[17],budgets_ns=[BUDGETS[1]])
    write(OUT/'logging-protocol.json',dict(purpose='Measured shared compact/full publication burden; injected-clock tests establish logical action/RNG parity',
        methods=methods,originals=6,solver_seeds=[17],budgets_ns=[BUDGETS[1]],requests=24,
        limitations='Real-time closed-loop trajectories may change when costs change; no estimated subtraction'))
    write(OUT/'logging.json',c)
    rows=run_schedule(OUT/'logging.json','validation',OUT/'logging',resume=False)
    print('logging diagnostic',len(rows),{str(a.status) for a in rows},flush=True)

if __name__=='__main__':
    {'prepare':prepare,'collect':collect,'fit':fitting,'validate':validate,'frontier':frontier,'logging':logging_diagnostic}[sys.argv[1]]()
