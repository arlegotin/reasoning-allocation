"""Run a separately identified, serial diagnostic schedule through public harness."""
import os
os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
import sys,json,hashlib,subprocess,time
from pathlib import Path
from ra import runner
config,out=map(Path,sys.argv[1:3]);out.mkdir(parents=True,exist_ok=False)
worker=Path(__file__).with_name('pilot_profile_worker.py').resolve()
identity={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),worker]}
old=runner._runtime_identity

def runtime_identity():
    code,env,build,inventory=old()
    inventory={**inventory,'pilot_diagnostic_sources':identity}
    return runner._digest([code,identity]),env,build,inventory
runner._runtime_identity=runtime_identity
runner._worker_argv=lambda path:[sys.executable,str(worker),str(path)]
checks=[]
for argv in [['pmset','-g','batt'],['pmset','-g'],['uptime']]:
    p=subprocess.run(argv,capture_output=True,text=True);checks.append({'argv':argv,'stdout':p.stdout,'stderr':p.stderr,'returncode':p.returncode})
(out/'prospective.json').write_text(json.dumps({'sources':identity,'snapshots':checks,'scope':'separate charged diagnostic; never pooled as primary B0'},indent=2)+'\n')
start=time.perf_counter_ns();attempts=runner.run_schedule(config,'pilot',out/'runs')
(out/'driver-cost.json').write_text(json.dumps({'schedule_wall_ns':time.perf_counter_ns()-start,'attempts':len(attempts),'statuses':[a.status for a in attempts]},indent=2)+'\n')
print(json.dumps({'attempts':len(attempts),'statuses':[a.status for a in attempts]}))
