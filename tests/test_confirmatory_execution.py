"""Artificial frozen cohorts exercise execution; never touch real protected outcomes."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import pytest

from test_freeze import scientific, write
from ra import runner, freeze
from ra.runner import run_request as real_run_request
from ra.types import Attempt, AvailableProgress


INTERRUPTION = {'action': 'retry_entire_paired_block',
    'block_keys': ['template_id', 'repeat', 'solver_seed', 'budget_ns'],
    'effective': 'first_fully_completed_generation',
    'prior_attempts': 'retain_all_costs', 'trigger': 'external_interrupt_or_incomplete_generation'}
RESOURCE = {'minimum_free_storage_bytes': 1, 'minimum_available_memory_bytes': 1,
    'action': 'halt_and_quarantine', 'temperature': 'record_available_sensor_or_unavailable'}


@pytest.fixture
def frozen(scientific):
    path, c, digest = scientific
    c['exclusions']['external_interrupt'] = INTERRUPTION
    c['exclusions']['execution_resource'] = RESOURCE
    c['capacity'].update(worker_peak_envelope_bytes=2**40, coordinator_reserve_bytes=2**40,
        storage_envelope_bytes=2**40, physical_memory_bytes=2**44, free_storage_bytes=2**44)
    write(path, c)
    freeze.freeze_protocol(path, digest)
    return path, c, digest, Path(c['outcome_directory'])


def execute(*args, **kwargs):
    function = getattr(runner, 'execute_frozen', None)
    assert callable(function), 'protected execute_frozen API is missing'
    return function(*args, **kwargs)


@pytest.fixture
def artificial_worker(monkeypatch):
    """Replace only expensive solver; retain real immutable publication and recovery."""
    calls = []
    statuses = {}
    def run(request, out):
        # The access admission must precede any solver/old-outcome access.
        journal = out.parents[2].with_suffix('.access.json')
        assert json.loads(journal.read_text())['events']
        calls.append(request)
        status = statuses.pop(len(calls), 'complete')
        out.mkdir(parents=True)
        (out/'solutions').mkdir()
        request = replace(request, launch_ns=100, deadline_ns=100+request.budget_ns)
        runner._atomic_json(out/'request.json', asdict(request))
        attempt = Attempt(request.request_id, status, AvailableProgress(True, .25, request.p0, 0., None),
            True, {'launch_ns':100}, {'end_to_end_ns':20,'parent_cpu_ns':2,
            'worker_cpu_ns':3,'worker_peak_rss_bytes':5,'resource_release_confirmed':True},
            0, status=='external_interrupt', None, request, quarantined=status=='numerical_alarm')
        runner.publish_attempt(attempt, out)
        return attempt
    monkeypatch.setattr(runner, 'run_request', run)
    return calls, statuses


def test_frozen_execution_rejects_changed_model_before_output(frozen):
    path,c,digest,out = frozen
    c['models'][0]['sha256']='0'*64
    write(path,c)
    with pytest.raises(ValueError,match='hash'):
        execute(digest,out)
    assert not out.exists()
    assert not Path(c['execution_access_journal']).exists()


def test_exact_serial_queue_and_independent_deadlines(frozen, artificial_worker):
    _,c,digest,out = frozen
    calls,_ = artificial_worker
    results = execute(digest,out)
    queue=json.loads(Path(c['queue']['path']).read_text())
    assert len(results)==len(calls)==252
    assert [r.request_id for r in calls]==[q['request_id'] for q in queue]
    assert sum(r.method=='B0' for r in calls)==36
    assert {r.budget_ns for r in calls}=={1,4,16}
    assert all(r.launch_ns is None and r.deadline_ns is None for r in calls)
    assert all(r.phase=='confirmatory' for r in calls)
    seal=json.loads((out/'execution-seal.json').read_text())
    assert seal['logical_request_count']==seal['physical_attempt_count']==252
    assert seal['status_counts']=={'complete':252}
    assert len(seal['effective_attempts'])==252
    assert execute(digest,out,resume=True)==[]
    assert len(calls)==252


def test_dry_run_and_wrong_namespace_have_no_access(frozen):
    _,c,digest,out=frozen
    assert execute(digest,out,dry_run=True)==[]
    assert not out.exists() and not Path(c['execution_access_journal']).exists()
    with pytest.raises(ValueError,match='namespace'):
        execute(digest,out.parent/'wrong')


@pytest.mark.parametrize('status',['implementation_error','oom','numerical_alarm'])
def test_faults_remain_and_stop_without_retry(frozen,artificial_worker,status):
    _,c,digest,out=frozen
    calls,statuses=artificial_worker;statuses[2]=status
    execute(digest,out)
    assert len(calls)==2
    assert not (out/'execution-seal.json').exists()
    outcomes=[json.loads(p.read_text()) for p in out.rglob('attempt.json')]
    assert any(a['status']==status and a['available']['utility']==.25 for a in outcomes)
    with pytest.raises(ValueError,match='halt|quarantin'):
        execute(digest,out,resume=True)
    assert len(calls)==2


def test_external_interrupt_retries_whole_block_and_keeps_prior_cost(frozen,artificial_worker):
    _,c,digest,out=frozen
    calls,statuses=artificial_worker;statuses[3]='external_interrupt'
    execute(digest,out)
    assert len(calls)==3
    first=[r.request_id for r in calls]
    results=execute(digest,out,resume=True)
    queue=json.loads(Path(c['queue']['path']).read_text())
    assert len(results)==252 and len(calls)==255
    assert [r.request_id for r in calls[3:]]==[q['request_id'] for q in queue]
    assert [r.request_id for r in calls[3:6]]==first
    assert all(len(r.prior_attempt_ids)==1 and r.prior_costs['end_to_end_ns']==20 for r in calls[3:6])
    seal=json.loads((out/'execution-seal.json').read_text())
    assert seal['physical_attempt_count']==255 and seal['logical_request_count']==252
    assert seal['costs']['end_to_end_ns']==5100
    assert len(list(out.rglob('attempt.json')))==255


def test_resume_rejects_hash_drift_even_after_seal(frozen,artificial_worker):
    path,c,digest,out=frozen
    execute(digest,out)
    c['weights']=[.1,.8,.1];write(path,c)
    with pytest.raises(ValueError,match='hash'):
        execute(digest,out,resume=True)


def test_no_significance_input_changes_fixed_queue(frozen,artificial_worker):
    _,c,digest,out=frozen
    # Unregistered inferential files are not an execution control interface.
    write(out.parent/'simulated-significance.json',{'p_value':0.,'stop':True,'sample':1})
    execute(digest,out)
    assert len(artificial_worker[0])==252


def test_real_cold_artificial_queue_exhausts_and_resumes(frozen):
    _,c,digest,out=frozen
    results=execute(digest,out)
    assert len(results)==252
    assert all(a.status=='startup_timeout' and a.available.utility==0 for a in results)
    assert len({a.attempt_id for a in results})==252
    assert all(a.request.deadline_ns-a.request.launch_ns==a.request.budget_ns for a in results)
    assert execute(digest,out,resume=True)==[]


def test_unavailable_background_sensor_is_recorded(monkeypatch):
    def denied(): raise PermissionError('sandbox sensor unavailable')
    monkeypatch.setattr(runner.psutil, 'pids', denied)
    conditions = runner._execution_conditions()
    assert conditions['process_count'] is None
    assert 'unavailable' in conditions['process_count_unavailable']


def test_unfrozen_confirmatory_request_is_rejected():
    from ra.worker import validate_request
    from ra.types import Request
    request=Request('x','/tmp/artificial','0'*64,'0'*64,'0'*64,'0'*64,'0'*64,
                    'native','confirmatory',1,1,1,1)
    with pytest.raises(ValueError,match='frozen'):
        validate_request(request)


def test_cli_uses_exact_successor_config_and_frozen_namespace(frozen,artificial_worker,capsys):
    from ra.cli import main
    path,c,digest,out=frozen
    assert main(['run','--config',str(path),'--phase','confirmatory','--dry-run'])==0
    assert not out.exists()
    assert main(['run','--config',str(path),'--phase','confirmatory','--resume'])==0
    assert '"success": true' in capsys.readouterr().out
    assert len(artificial_worker[0])==252
    assert runner.schedule_succeeded(out)


def test_coordinator_interruption_retries_incomplete_generation(frozen,artificial_worker,monkeypatch):
    _,c,digest,out=frozen
    real=runner.run_request;counter=0
    def interrupted(request,directory):
        nonlocal counter
        counter+=1
        if counter==4: raise KeyboardInterrupt('artificial coordinator interruption')
        return real(request,directory)
    monkeypatch.setattr(runner,'run_request',interrupted)
    with pytest.raises(KeyboardInterrupt):execute(digest,out)
    partial_batch=next(out.glob('batch-*'))
    assert (partial_batch/'start.json').exists()
    receipts=[json.loads(p.read_text()) for p in partial_batch.glob('*.json') if p.name!='start.json']
    assert len(receipts)==3 and all(r['coordinator_cpu_ns_lower_bound']>=0 for r in receipts)
    assert not (partial_batch/'accounting.json').exists()
    monkeypatch.setattr(runner,'run_request',real)
    execute(digest,out,resume=True)
    seal=json.loads((out/'execution-seal.json').read_text())
    assert seal['logical_request_count']==252 and seal['physical_attempt_count']==255


def test_live_source_drift_halts_before_next_worker(frozen,artificial_worker,monkeypatch):
    _,c,digest,out=frozen
    real=runner.run_request
    identity=runner._runtime_identity
    def drift_after_first(request,directory):
        result=real(request,directory)
        source,env,build,inventory=identity()
        monkeypatch.setattr(runner,'_runtime_identity',lambda:('0'*64,env,build,inventory))
        return result
    monkeypatch.setattr(runner,'run_request',drift_after_first)
    execute(digest,out)
    assert len(artificial_worker[0])==1
    assert json.loads((out/'halt.json').read_text())['reason']=='live_hash_drift'
    assert not (out/'execution-seal.json').exists()


def test_resource_alarm_is_persistent_without_retry(frozen,artificial_worker,monkeypatch):
    _,c,digest,out=frozen
    real=runner._execution_conditions
    monkeypatch.setattr(runner,'_execution_conditions',lambda:{**real(),'free_storage_bytes':0})
    assert execute(digest,out)==[]
    assert json.loads((out/'halt.json').read_text())['reason']=='resource_alarm'
    with pytest.raises(ValueError,match='halt|quarantin'):execute(digest,out,resume=True)
    assert not artificial_worker[0]


def test_real_native_frozen_request_matches_enumerated_optimum(scientific,artificial_worker,monkeypatch):
    """One actual solver in an artificial frozen queue; independent finite optimum."""
    import itertools
    import copy
    from ra.data import generate_workload
    from ra.stats import calibrate_design
    from ra.metrics import progress_at
    from ra.types import ProgressRecord
    path,c,digest=scientific
    population=copy.deepcopy(c['population'])
    for index,cell in enumerate(population['cells']):
        cell.update(columns=4 if index%2==0 else 8,rows=2 if index%2==0 else 4,degree=2)
    population['templates_per_cell']=2
    manifest=generate_workload(population,'confirmatory',path.parent/'tiny')
    cells=sorted({i['cell_id'] for i in manifest['instances']})
    oldcells=sorted(c['planning']['cells']);budgets={1:500_000_000,4:2_000_000_000,16:8_000_000_000}
    c['population']=population;c['planning']['cells']={k:1/6 for k in cells}
    c['deadlines_ns']=list(budgets.values());c['planning']['deadlines']=c['deadlines_ns']
    c['execution']['budgets_ns']=c['deadlines_ns']
    c['execution']['input_manifests']=[str(path.parent/'tiny/manifest.json')]
    c['protected_manifests']=[freeze.reference(path.parent/'tiny/manifest.json')]
    pre=json.loads(Path(c['preflight']['path']).read_text())
    rows=json.loads(Path(pre['rows']['path']).read_text())
    for row in rows:
        row['cell_id']=cells[oldcells.index(row['cell_id'])]
        row['budget_ns']=budgets[row['budget_ns']]
    pre['rows']=write(Path(pre['rows']['path']),rows)
    c['preflight']=write(Path(c['preflight']['path']),pre)
    c['resources']=write(Path(c['resources']['path']),calibrate_design(rows,c['planning']))
    c['queue']=write(Path(c['queue']['path']),freeze.make_queue(c,manifest['instances']))
    c['exclusions'].update(external_interrupt=INTERRUPTION,execution_resource=RESOURCE)
    c['capacity'].update(worker_peak_envelope_bytes=2**40,coordinator_reserve_bytes=2**40,
        storage_envelope_bytes=2**40,physical_memory_bytes=2**44,free_storage_bytes=2**44)
    write(path,c);freeze.freeze_protocol(path,digest)
    fake=runner.run_request;actual=[]
    def one_native(request,directory):
        if request.method=='B0' and not actual:
            result=real_run_request(request,directory);actual.append((result,directory));return result
        return fake(request,directory)
    monkeypatch.setattr(runner,'run_request',one_native)
    results=execute(digest,Path(c['outcome_directory']))
    assert len(results)==252 and len(actual)==1
    attempt,directory=actual[0]
    raw=json.loads(Path(attempt.request.instance_path).read_text())
    optimum=min(sum(x*c for x,c in zip(bits,raw['costs']))
        for bits in itertools.product((0,1),repeat=len(raw['costs']))
        if all(any(bits[j] for j in row) for row in raw['rows']))
    assert attempt.available.assignment_available and attempt.available.primal_original==optimum
    assert attempt.available.utility>0 and attempt.clock_aligned
    progress=[ProgressRecord(**json.loads(line)) for line in (directory/'progress.jsonl').read_text().splitlines()]
    assert progress_at(progress,attempt.request.deadline_ns,attempt.request.p0)==attempt.available
    assert all(r.receipt_ns<=attempt.request.deadline_ns for r in progress if r.sequence==attempt.available.sequence)
    queue=json.loads(Path(c['queue']['path']).read_text())
    row=next(r for r in queue if r['request_id']==attempt.request_id)
    assert row['method']=='B0' and row['fit_id']=='shared'
    assert row['instance_id']==attempt.request.instance_hash and row['budget_ns']==attempt.request.budget_ns


def test_partial_worker_still_alive_blocks_recovery(frozen,artificial_worker):
    import os
    _,c,digest,out=frozen
    calls,statuses=artificial_worker;statuses[1]='external_interrupt'
    execute(digest,out)
    directory=next(out.rglob('attempt.json')).parent
    payload=json.loads((directory/'attempt.json').read_text())
    payload['resources'].update(resource_release_confirmed=False,worker_pid=os.getpid(),
        worker_create_time=runner.psutil.Process().create_time())
    write(directory/'partial.json',payload)
    for name in ('attempt.json','attempt.sha256','publication.json'):(directory/name).unlink()
    for p in out.rglob('*.closed.json'):p.unlink()
    with pytest.raises(ValueError,match='worker.*running'):
        execute(digest,out,resume=True)
    assert len(calls)==1


def test_artificial_frozen_cohort_is_disjoint_from_registered_protected_inputs(frozen):
    _,c,_,_=frozen
    real=json.loads(Path('configs/confirmatory-A003.json').read_text())
    registered=[item for ref in real['protected_manifests'] for item in json.loads(Path(ref['path']).read_text())['instances']]
    artificial=[item for ref in c['protected_manifests'] for item in json.loads(Path(ref['path']).read_text())['instances']]
    assert not ({i['instance_id'] for i in registered} & {i['instance_id'] for i in artificial})
    assert not ({i['template_id'] for i in registered} & {i['template_id'] for i in artificial})
