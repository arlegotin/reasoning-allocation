"""Charged public latency treatment: native deadline, availability and scope guards."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from ra import runner
from ra.config import validate_run_config
from ra.worker import validate_request
from test_harness_controls import configuration


def delayed_method(delay):
    return {'name':'B2-delay', 'kind':'shared', 'allocator':{'policy':'estimate','length':1},
            'pool_size':128, 'diagnostic_delay_ns':delay}


def public_branching(tmp_path, delay, budget=2_000_000_000):
    from ra.data import GeneratorCell, generate_cover
    from ra.exact import canonical_cover
    from ra.provenance import SplitOwnership, instance_hash
    path=configuration(tmp_path,[delayed_method(delay)])
    c=json.loads(path.read_text());c['budgets_ns']=[budget];path.write_text(json.dumps(c))
    cover=generate_cover(GeneratorCell('uniform',64,64,8),17)
    cover=replace(cover,lineage={**cover.lineage,'split':'discovery'},instance_id='')
    cover=replace(cover,instance_id=instance_hash(cover))
    original=tmp_path/'input.json'
    original.write_text(json.dumps({**canonical_cover(cover),'instance_id':cover.instance_id,
        'template_id':cover.template_id,'cell_id':cover.cell_id,'lineage':cover.lineage}))
    owners=SplitOwnership();owners.register(cover,'discovery');owners.save(tmp_path/'ownership.json')
    manifest=tmp_path/'manifest.json';m=json.loads(manifest.read_text())
    m['instances'][0].update(instance_id=cover.instance_id,sha256=hashlib.sha256(original.read_bytes()).hexdigest())
    manifest.write_text(json.dumps(m))
    return path


def test_real_delay_is_inside_charged_administration_and_legal_lease(tmp_path):
    path=public_branching(tmp_path,3_000_000)
    a=runner.run_schedule(path,'discovery',tmp_path/'out')[0]
    assert a.status=='complete', a.error
    delays=a.resources['diagnostic_delays']
    assert delays and all(d['end_ns']-d['start_ns']>=3_000_000 for d in delays)
    assert all(not d['expired'] for d in delays)
    assert a.resources['worker_exclusive_ns']['administration']>=sum(d['end_ns']-d['start_ns'] for d in delays)
    assert a.resources['allocation_decisions'] and a.resources['completion_count']>0
    assert a.resources['resource_release_confirmed'] and a.resources['native_released']
    assert all(d['allocation']['root'] in d['pool_ids'] for d in a.resources['allocation_decisions'])


def test_delay_crossing_deadline_returns_legal_node_without_dispatch_credit(tmp_path):
    path=public_branching(tmp_path,700_000_000,budget=500_000_000)
    a=runner.run_schedule(path,'discovery',tmp_path/'out')[0]
    assert a.status=='deadline', a.error
    delay=a.resources['diagnostic_delays'][0]
    assert delay['expired'] and delay['end_ns']>a.timestamps['deadline_ns']
    assert a.resources['allocation_decisions']==[] and a.resources['lease_outcomes']==[]
    assert a.resources['selection_boundaries'][0]['kind']=='residual'
    assert a.resources['selection_boundaries'][0]['reason']=='deadline'
    assert a.resources['native_released'] and a.resources['resource_release_confirmed']
    assert a.overshoot_ns>0 and a.resources['worker_exclusive_ns']['administration']>=700_000_000
    progress=next((tmp_path/'out').rglob('progress.jsonl'))
    records=[json.loads(line) for line in progress.read_text().splitlines()]
    timely=[r for r in records if r['receipt_ns']<=a.timestamps['deadline_ns']]
    late=[r for r in records if r['receipt_ns']>a.timestamps['deadline_ns']]
    assert timely and a.available.utility==0
    assert a.available.primal_original==a.request.p0 and a.available.dual_original==0
    assert late and any(r['dual_original']>0 for r in late)


def test_delay_cannot_read_protected_input_under_public_manifest(tmp_path):
    path=public_branching(tmp_path,0)
    original=tmp_path/'input.json';raw=json.loads(original.read_text())
    raw['lineage']['split']='confirmatory';original.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='split mismatch'):
        runner.run_schedule(path,'discovery',tmp_path/'out',dry_run=True)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('delay',[-1,True,1.5,1_000_000_001])
def test_invalid_delay_rejects(tmp_path,delay):
    config=json.loads(configuration(tmp_path).read_text());config['methods']=[delayed_method(delay)]
    with pytest.raises(ValueError):validate_run_config(config)


@pytest.mark.parametrize('change',[{'allocator':{'policy':'uniform','length':1}}, {'allocator':{'policy':'estimate','length':4}},
    {'pool_size':None}, {'kind':'native','overrides':{}}, {'learned':{}}])
def test_diagnostic_cannot_change_other_scientific_components(tmp_path,change):
    config=json.loads(configuration(tmp_path).read_text());config['methods']=[{**delayed_method(4_000_000),**change}]
    with pytest.raises(ValueError):validate_run_config(config)


@pytest.mark.parametrize('phase',['confirmatory','train','pilot'])
def test_delay_is_public_diagnostic_only(tmp_path,phase):
    path=public_branching(tmp_path,0)
    req=runner.prepare_schedule(path,'discovery')[0][0]
    with pytest.raises(ValueError,match='public latency diagnostic'):validate_request(replace(req,phase=phase))


def test_finite_diagnostic_stops_on_fault_overshoot_and_elapsed_cap():
    from types import SimpleNamespace
    import importlib.util
    spec=importlib.util.spec_from_file_location('task18_latency',Path('checks/task18_latency.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    protocol={'stop':{'overshoot_fraction':.2,'elapsed_ns':180_000_000_000}}
    a=SimpleNamespace(status='deadline',quarantined=False,resources={'resource_release_confirmed':True},
                      overshoot_ns=100,request=SimpleNamespace(budget_ns=1000))
    assert module.stop_reason(a,1,protocol) is None
    a.overshoot_ns=201
    assert module.stop_reason(a,1,protocol)=='overshoot_threshold'
    a.overshoot_ns=0
    assert module.stop_reason(a,180_000_000_000,protocol)=='elapsed_cap'
    a.status='implementation_error'
    assert module.stop_reason(a,1,protocol)=='fault_or_quarantine'
    a.status='complete';a.resources['resource_release_confirmed']=False
    assert module.stop_reason(a,1,protocol)=='release_or_timing_failure'


def test_prospective_json_roundtrip_executes_and_rejects_changed_request(tmp_path,monkeypatch):
    from dataclasses import asdict
    import importlib.util
    from ra.data import generate_workload
    spec=importlib.util.spec_from_file_location('task18_roundtrip',Path('checks/task18_latency.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    generated=tmp_path/'inputs'
    generate_workload({'schema_version':1,'purpose':'workload','master_seed':'latency-roundtrip',
        'templates_per_cell':1,'cells':[{'family':'uniform','columns':8,'rows':8,'degree':4}]},'validation',generated)
    config=json.loads(configuration(tmp_path).read_text())
    config.update(input_manifests=[str(generated/'manifest.json')],methods=[delayed_method(0)])
    (tmp_path/'configs').mkdir();path=tmp_path/'configs/robustness.json';path.write_text(json.dumps(config))
    requests,metadata=runner.prepare_schedule(path,'validation')
    protocol={'files_sha256':{},'schedule':metadata,'requests':[asdict(r) for r in requests],
              'stop':{'overshoot_fraction':.2,'elapsed_ns':180_000_000_000}}
    pin=tmp_path/'protocol.json';pin.write_text(json.dumps(protocol))
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'PROTOCOL',pin);monkeypatch.setattr(module,'OUT',tmp_path/'out')
    status=module.execute()
    assert status['completed_finite_protocol'] and status['completed']==1
    assert len(list((tmp_path/'out').rglob('attempt.json')))==1
    protocol['requests'][0]['budget_ns']+=1;pin.write_text(json.dumps(protocol))
    monkeypatch.setattr(module,'OUT',tmp_path/'rejected')
    with pytest.raises(ValueError,match='prospective schedule'):module.execute()
    assert not (tmp_path/'rejected').exists()
