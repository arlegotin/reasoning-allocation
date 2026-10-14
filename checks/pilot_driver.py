"""Task9 reproducible public pilot preparation and verified reconstruction.

Executed stages are explicit CLI calls, not an automatic outcome filter.
"""
import os
os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
import argparse, json, time, subprocess, hashlib
from pathlib import Path
from dataclasses import asdict, fields
from ra.data import config_cells, generate_cover
from ra.exact import canonical_cover
from ra.provenance import SplitOwnership, derive_seed
from ra.types import Attempt, Request, AvailableProgress
from ra.runner import _read_attempt
from ra.pilot import summarize_headroom


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def prepare(n,budget):
    out=Path(f'artifacts/pilot/scale-{n}');out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter_ns()
    grid=json.loads(Path('configs/workload_probes.json').read_text())
    grid['column_counts']=[64*2**k for k in range(n.bit_length()-6)]
    cells=[c for c in config_cells(grid) if c.columns==n]
    inputs=Path(f'data/pilot/discovery-{n}');inputs.mkdir(parents=True,exist_ok=False)
    owners_path=Path('data/pilot/split_ownership.json');owners=SplitOwnership.load(owners_path) if owners_path.exists() else SplitOwnership()
    records=[];failures=[]
    for i,cell in enumerate(cells):
        index=(n.bit_length()-7)*len(cells)+i
        seed=derive_seed(grid['master_seed'],'discovery',index)
        try:instance=generate_cover(cell,seed)
        except Exception as exc:
            failures.append({'cell':asdict(cell),'seed':seed,'index':index,'error':repr(exc)})
            continue
        owners.register(instance,'discovery')
        path=inputs/f'{instance.instance_id}.json'
        write(path,{**canonical_cover(instance),'instance_id':instance.instance_id,'template_id':instance.template_id,'cell_id':instance.cell_id,'lineage':instance.lineage})
        records.append({'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'instance_id':instance.instance_id,'cell_id':instance.cell_id,'cell':asdict(cell),'template_index':index,'seed':seed})
    owners.save(owners_path)
    write(inputs/'manifest.json',{'schema_version':1,'split':'discovery','ownership_registry':str(owners_path.resolve()),'instances':records,'generation_failures':failures,'grid':grid})
    config=json.loads(Path('configs/exploratory.json').read_text())
    config.update(input_manifests=[str((inputs/'manifest.json').resolve())],methods=[{'name':'B0','kind':'native','overrides':{}}],budgets_ns=[budget],solver_seeds=[0,17])
    write(out/'run.json',config)
    snapshots={}
    for label,argv in [('power',['pmset','-g','batt']),('mode',['pmset','-g']),('load',['uptime']),('memory',['memory_pressure']),('disk',['df','-k','.'])]:
        p=subprocess.run(argv,capture_output=True,text=True);snapshots[label]={'argv':argv,'stdout':p.stdout,'stderr':p.stderr,'returncode':p.returncode}
    write(out/'prospective.json',{'columns':n,'budget_ns':budget,'grid':grid,'cells':len(cells),'failures':failures,'setup_ns':time.perf_counter_ns()-start,'snapshots':snapshots,'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'reason':'Start at64 then geometric native/resource discovery; preserve normal enhancements and all seeds. Budget is a probe, not a success threshold.'})
    print(json.dumps({'config':str(out/'run.json'),'instances':len(records),'failures':len(failures)}))


def reconstruct(directory):
    attempts=[]
    for p in sorted(Path(directory).rglob('attempt.json')):
        raw,complete=_read_attempt(p.parent)
        assert complete
        raw={k:v for k,v in raw.items() if k in {f.name for f in fields(Attempt)}}
        raw['request']=Request(**raw['request']);raw['available']=AvailableProgress(**raw['available'])
        attempts.append(Attempt(**raw))
    summary=summarize_headroom(attempts)
    write(Path(directory)/'headroom-summary.json',summary)
    print(json.dumps({'attempts':len(attempts),'statuses':summary['status_counts'],'root_only':summary['root_only_count'],
        'max_nodes':max((a.resources.get('native_nodes',0) for a in attempts),default=None),
        'max_rss':max((a.resources.get('worker_peak_rss_bytes',0) for a in attempts),default=None),
        'wall_s':sum(a.resources.get('end_to_end_ns',0) for a in attempts)/1e9}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','summarize']);p.add_argument('value');p.add_argument('--budget-ns',type=int,default=1_000_000_000);args=p.parse_args()
    prepare(int(args.value),args.budget_ns) if args.mode=='prepare' else reconstruct(args.value)
