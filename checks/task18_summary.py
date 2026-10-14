"""Authenticate and descriptively summarize the fixed public latency experiment."""
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import statistics
import time

from ra.exact import verify_cover
from ra.metrics import progress_at
from ra.runner import _read_attempt, _request_identity, _digest, _atomic_json
from ra.types import ProgressRecord, Request
from ra.worker import load_instance

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'artifacts/task18/latency'
OUT=ROOT/'results/ablations/task18-latency'


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    started=time.perf_counter_ns()
    protocol=read(ROOT/'protocol/task18-latency.json')
    assert read(RAW/'protocol-receipt.json')['sha256']==sha(ROOT/'protocol/task18-latency.json')
    status=read(RAW/'status.json')
    assert status['completed_finite_protocol'] and status['completed']==36
    rows=[];audit=[]
    for index,expected in enumerate(protocol['requests']):
        directory=RAW/'attempts'/expected['request_id']
        a,complete=_read_attempt(directory)
        assert complete and _digest(_request_identity(a['request']))==_digest(_request_identity(expected))
        assert not a['quarantined'] and a['clock_aligned'] and not a['error']
        r=a['resources'];t=a['timestamps'];request=Request(**a['request'])
        records=[ProgressRecord(**json.loads(line)) for line in (directory/'progress.jsonl').read_text().splitlines()]
        available=progress_at(records,request.deadline_ns,request.p0,clock_aligned=True,bound_tolerance=request.bound_tolerance)
        assert asdict(available)==a['available']
        instance=load_instance(request)
        for solution in (directory/'solutions').glob('*.json'):
            saved=read(solution);checked=verify_cover(instance,saved['binary'],0.)
            assert checked.content_hash==saved['content_hash'] and checked.objective==saved['objective']
        delays=r['diagnostic_delays'];delay_ns=request.method_config['diagnostic_delay_ns']
        assert delays and all(d['requested_ns']==delay_ns and d['end_ns']-d['start_ns']>=delay_ns for d in delays)
        actual=sum(d['end_ns']-d['start_ns'] for d in delays)
        assert r['worker_exclusive_ns']['administration']>=actual
        assert r['timing_partition_complete'] and not r['timing_instrumentation_failed']
        assert sum(r['worker_exclusive_ns'].values())==t['worker_release_ns']-t['worker_entry_ns']
        assert r['resource_release_confirmed'] and r['native_released'] and r['solver_threads']==r['lp_threads']==1
        call=read(RAW/f'call-{index:02d}.json')
        assert call['attempt_id']==a['attempt_id'] and call['request_id']==request.request_id and call['stop_reason'] is None
        if rows:assert rows[-1]['parent_release_ns']<t['launch_ns']
        row={'index':index,'instance_id':request.instance_hash,'template_id':a['template_id'],'cell_id':a['cell_id'],
            'method':request.method,'repeat':int(request.method[-1]),'dose_ms':delay_ns/1e6,'status':a['status'],
            'utility':available.utility,'primal':available.primal_original,'dual':available.dual_original,
            'nodes':r['native_nodes'],'lps':r['native_lps'],'completion_count':r['completion_count'],
            'delay_calls':len(delays),'expired_delays':sum(d['expired'] for d in delays),'actual_delay_ns':actual,
            'end_to_end_ns':r['end_to_end_ns'],'full_call_ns':call['call_end_ns']-call['call_start_ns'],
            'overshoot_ns':a['overshoot_ns'],'worker_cpu_ns':r['worker_cpu_ns'],'parent_cpu_ns':r['parent_cpu_ns'],
            'worker_peak_rss_bytes':r['worker_peak_rss_bytes'],'trace_bytes':r['trace_bytes'],
            'parent_release_ns':t['parent_release_ns'],**{f'{k}_ns':v for k,v in r['worker_exclusive_ns'].items()}}
        rows.append(row)
        audit.append({'path':str(directory.relative_to(ROOT)),'attempt_sha256':sha(directory/'attempt.json'),
                      'attempt_id':a['attempt_id'],'artifact_count':len(a['files_sha256'])})
    cells=sorted({r['cell_id'] for r in rows})
    pairs=[]
    for cell in cells:
        for dose in (4.,10.):
            by_repeat=[]
            for repeat in (0,1):
                control=next(r for r in rows if (r['cell_id'],r['dose_ms'],r['repeat'])==(cell,0.,repeat))
                treated=next(r for r in rows if (r['cell_id'],r['dose_ms'],r['repeat'])==(cell,dose,repeat))
                by_repeat.append({key:treated[key]-control[key] for key in ('utility','primal','dual','nodes','lps','end_to_end_ns')})
            pairs.append({'cell_id':cell,'dose_ms':dose,'repeat_differences':by_repeat,
                          'mean_differences':{key:statistics.mean(x[key] for x in by_repeat) for key in by_repeat[0]}})
    doses=[]
    for dose in (0.,4.,10.):
        subset=[r for r in rows if r['dose_ms']==dose]
        dose_pairs=[p for p in pairs if p['dose_ms']==dose]
        diffs=[p['mean_differences']['utility'] for p in dose_pairs]
        doses.append({'dose_ms':dose,'requests':len(subset),'complete':sum(r['status']=='complete' for r in subset),
            'deadline':sum(r['status']=='deadline' for r in subset),'mean_utility':statistics.mean(r['utility'] for r in subset),
            'paired_original_mean_utility_difference':statistics.mean(diffs) if diffs else 0.,
            'paired_original_difference_range':[min(diffs),max(diffs)] if diffs else [0.,0.],
            'maximum_repeat_difference_spread':max((abs(p['repeat_differences'][0]['utility']-p['repeat_differences'][1]['utility']) for p in dose_pairs),default=0.),
            'peak_worker_rss_bytes':max(r['worker_peak_rss_bytes'] for r in subset),
            **{key:sum(r[key] for r in subset) for key in ('actual_delay_ns','delay_calls','expired_delays','nodes','lps','completion_count','end_to_end_ns','full_call_ns','overshoot_ns','worker_cpu_ns','parent_cpu_ns','trace_bytes','startup_ns','native_ns','administration_ns','observation_ns','finalization_ns','residual_ns')}})
    OUT.mkdir(parents=True,exist_ok=False)
    with (OUT/'requests.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={'claim_level':'exploratory descriptive latency sensitivity','independent_originals':6,'timing_repeats':2,
        'fit_count':0,'budget_ns':2106828958,'protocol_sha256':sha(ROOT/'protocol/task18-latency.json'),
        'executed_commit':'bc93c88','summary_source_sha256':sha(Path(__file__)),
        'status':status,'accounting':read(RAW/'accounting.json'),'doses':doses,'paired_originals':pairs,
        'audit':audit,'uncertainty':'per-original contrast range and within-original repeat spread only; no confidence interval or resampling',
        'limits':protocol['limits'],'gates':protocol['gates'],
        'audit_elapsed_ns':time.perf_counter_ns()-started}
    _atomic_json(OUT/'summary.json',summary,immutable=True)
    index={str(p.relative_to(ROOT)):sha(p) for p in [OUT/'requests.csv',OUT/'summary.json',RAW/'status.json',RAW/'accounting.json',RAW/'reporting.json',RAW/'protocol-receipt.json']}
    _atomic_json(OUT/'artifact-index.json',index,immutable=True)
    print(json.dumps({'doses':doses,'accounting':summary['accounting'],'audit_elapsed_ns':summary['audit_elapsed_ns']},indent=2))


if __name__=='__main__':main()
