"""One clean local, fixed A004 numerical reproduction; never launch protected runs.

Use a fresh --out for each explicitly authorized reproduction. Existing outputs
are never reused/overwritten. This command is intentionally separate from report.
"""
from pathlib import Path
import argparse
import json
import os
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
EXPECTED='6339521bccab940fe0ec0546792a3c6012e65644fe7f63a5dde6418717b83d69'


def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def stage(name,out):
    from ra.freeze import read,reference
    from ra.report import _write_csv,_write_json
    if name=='parity':
        from ra.runner import _runtime_identity
        from ra.doctor import native_smoke
        identity=_runtime_identity()
        old=read(ROOT/'results/confirmatory/provenance.json')['analysis_runtime_inventory']['environment']
        smoke=native_smoke()
        receipt={'current_identity':identity,'historical_environment':old,
            'build_equal':identity[3]['environment']['build']==old['build'],
            'parameters_equal':smoke['parameters']==read(ROOT/'artifacts/environment/scip-parameters.json'),
            'native_smoke':smoke,'bootstrap_scope':'Python/venv/ensurepip and OS preexist; locked packages hash-installed; PYTHONPATH source is committed, not an editable install'}
        write(out/'parity.json',receipt)
        assert receipt['build_equal'] and receipt['parameters_equal'], 'native binary/config parity failed'
    elif name=='numerical':
        from ra.report import reconstruct_frozen,numerical_inference_digest,endpoint_curves,secondary_effects,resource_summary,calibration_summary
        from ra.metrics import summarize_attempts
        from ra.stats import paired_frontier_intervals
        target=out/'numerical';target.mkdir()
        config,audit,checked,attempts,metadata=reconstruct_frozen(ROOT/'configs/confirmatory-A004.json')
        assert config['bootstrap']['repetitions']==65536 and config['bootstrap']['seed']==2026101502
        rows=summarize_attempts(attempts,config)
        value=paired_frontier_intervals(rows,config)
        curves=endpoint_curves(rows,config)
        _write_json(target/'inference.json',value)
        for filename,table in [('endpoints.csv',rows),('primary.csv',value['contrasts']),('curves.csv',curves),
                ('secondary_effects.csv',secondary_effects(curves,config)),('resource_summary.csv',resource_summary(attempts,metadata)),
                ('calibration.csv',calibration_summary(attempts,metadata))]:
            _write_csv(target/filename,table)
        comparisons={name:(target/name).read_bytes()==(ROOT/'results/confirmatory'/name).read_bytes()
            for name in ('endpoints.csv','curves.csv','secondary_effects.csv','resource_summary.csv','calibration.csv')}
        receipt={'expected_numeric_digest':EXPECTED,'actual_numeric_digest':numerical_inference_digest(value),
            'tolerance':0,'exact_numeric_match':numerical_inference_digest(value)==EXPECTED,
            'exact_csv_matches':comparisons,'freeze_digest':checked['digest'],
            'request_count':len(rows),'solver_source':config['source_commit'],
            'reproduction_source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'source_inventory':__import__('ra.freeze',fromlist=['_source_inventory'])._source_inventory(),
            'scope':'one fixed numerical reproduction; no claim/seed/model/fit/contrast/cohort selection; current code distinct from original analysis',
            'artifacts':[reference(p) for p in sorted(target.iterdir())]}
        write(out/'numerical-verification.json',receipt)
        assert receipt['exact_numeric_match'] and all(comparisons.values()), 'reproduction mismatch; preserve outputs and stop'
    elif name=='native':
        from ra.runner import prepare_schedule,run_request
        from ra.report import reconstruct_attempt
        from dataclasses import asdict
        import shutil
        # A deterministic public original, chosen by stored manifest order before
        # execution. A fresh current-source request; no protected request/claim.
        source=ROOT/'artifacts/task13/validation-inputs/selected-manifest.json'
        manifest=read(source); item=manifest['instances'][0]
        inputs=out/'native-inputs';inputs.mkdir()
        shutil.copy2(source.parent/item['path'],inputs/item['path'])
        manifest={**manifest,'instances':[item],'instance_count':1,
            'ownership_registry':str(Path(manifest['ownership_registry']).resolve())}
        write(inputs/'manifest.json',manifest)
        config={'schema_version':1,'purpose':'exploratory','input_manifests':[str(inputs/'manifest.json')],
            'solver_seeds':[17],'run_order_seed':2026101420,'budgets_ns':[2106828958],
            'watchdog_grace_ns':2000000000,'lease_lengths':[1],'threads':1,
            'integrality_tolerance':1e-6,'bound_tolerance':1e-6,
            'methods':[{'name':'WP10-public-native-check','kind':'native','overrides':{}}]}
        write(out/'native-config.json',config)
        requests,metadata=prepare_schedule(out/'native-config.json','validation')
        write(out/'native-prospective.json',{'schedule':metadata,'requests':[asdict(r) for r in requests],
            'source_manifest':reference(source),'scope':'one public original/native default/cold request; reproducibility check, no effect comparison'})
        assert len(requests)==1
        attempt=run_request(requests[0],out/'native-attempts'/requests[0].request_id)
        # run_request stores an attempt UUID child; reconstruct authentic bytes.
        paths=list((out/'native-attempts').rglob('attempt.json'));assert len(paths)==1
        rebuilt=reconstruct_attempt(paths[0].parent)
        write(out/'native-result.json',{'attempt':asdict(attempt),'reconstructed_utility':rebuilt.available.utility,
            'scope':'public native rerun, independent process and request; no protected performance inference'})
        assert attempt.status in ('complete','deadline') and not attempt.quarantined
        assert attempt.available==rebuilt.available and attempt.available.assignment_available
    else: raise ValueError(name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--stage',choices=['parity','numerical','native'])
    args=parser.parse_args();out=args.out.resolve()
    if args.stage:
        started,cpu=time.perf_counter_ns(),time.process_time_ns();success=False
        try:stage(args.stage,out);success=True
        finally:
            child=resource.getrusage(resource.RUSAGE_CHILDREN)
            write(out/(args.stage+'-resources.json'),{'success':success,'wall_ns':time.perf_counter_ns()-started,
                'process_cpu_ns':time.process_time_ns()-cpu,'child_cpu_seconds':child.ru_utime+child.ru_stime,
                'peak_rss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'scope':'stage after imports through receipt preparation; final receipt and interpreter startup/exit excluded; wrapper envelopes overlap',
                'unknown_tails':['final receipt write','interactive/development/monitoring']})
        return
    out.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','LOKY_MAX_CPU_COUNT':'1'}
    python=out/'env/bin/python';commands=[('bootstrap',[sys._base_executable,'-m','venv',str(out/'env')]),
        ('install',[str(python),'-m','pip','install','--no-index','--find-links',str(ROOT/'artifacts/environment/wheels'),
            '--only-binary=:all:','--require-hashes','-r',str(ROOT/'requirements.lock')]),
        ('pip-check',[str(python),'-m','pip','check']),
        ('parity',[str(python),str(Path(__file__).resolve()),'--out',str(out),'--stage','parity']),
        ('analytical',[str(python),'-m','ra.cli','check','--suite','analytical','--out',str(out/'analytical')]),
        ('native-tests',[str(python),'-m','pytest','tests/test_scip_smoke.py','tests/test_scip_lifecycle.py','tests/test_enumeration.py','tests/test_equivalence.py','-q']),
        ('numerical',[str(python),str(Path(__file__).resolve()),'--out',str(out),'--stage','numerical']),
        ('native',[str(python),str(Path(__file__).resolve()),'--out',str(out),'--stage','native']),
        ('report',[str(python),'-m','ra.cli','report','--manifest','protocol/freeze-A004.sha256','--out',str(out/'REPORT.md')])]
    receipts=[]
    for name,command in commands:
        before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter_ns()
        with (out/(name+'.log')).open('w') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipts.append({'stage':name,'command':command,'returncode':result.returncode,'wall_ns':time.perf_counter_ns()-start,
            'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime})
        write(out/'commands.json',{'commands':receipts,'scope':'serial subprocess envelopes; overlap inner receipts, not additive to stage/native costs',
            'bootstrap':'base Python/venv/ensurepip not hash-installed; no network; original .venv unchanged',
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
        print(f'{name}: exit {result.returncode}',flush=True)
        if result.returncode: raise SystemExit(result.returncode)


if __name__=='__main__':main()
