"""Immutable protocol rejects unresolved inputs, access and referenced-asset drift."""
import copy
import hashlib
import json
from pathlib import Path
import pytest


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True))
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def test_freeze_api_exists_and_missing_fields_reject(tmp_path):
    from ra.freeze import freeze_protocol,verify_protocol
    config=tmp_path/'config.json';config.write_text('{}')
    with pytest.raises(ValueError): freeze_protocol(config,tmp_path/'freeze.sha256')
    assert not (tmp_path/'freeze.sha256').exists()
    with pytest.raises((ValueError,OSError)): verify_protocol(tmp_path/'freeze.sha256')


def test_canonical_immutable_envelope_and_dry_run(tmp_path):
    from ra.freeze import seal_manifest,verify_envelope
    asset=write(tmp_path/'model.json',{'coefficient':1})
    manifest={'experiment_id':'test-v1','source_commit':'a'*40,'assets':[asset], 'settings':{'B':6,'alpha':.05}}
    out=tmp_path/'freeze.sha256'
    digest=seal_manifest(manifest,out,dry_run=True)
    assert not out.exists() and not out.with_suffix('.manifest.json').exists()
    assert seal_manifest(manifest,out)==digest
    assert verify_envelope(out)['digest']==digest
    with pytest.raises(ValueError,match='immutable'): seal_manifest(manifest,out)
    second=tmp_path/'other.sha256'
    assert seal_manifest(dict(reversed(list(manifest.items()))),second)==digest
    asset_path=Path(asset['path']);asset_path.write_text('changed')
    with pytest.raises(ValueError,match='hash'): verify_envelope(out)


@pytest.mark.parametrize('key',['hardware','environment','source_commit','models','features','baseline_register',
    'sample','deadlines_ns','weights','bootstrap','contrasts','watchdog','exclusions','resources','preflight',
    'queue','protected_manifests','protocol','access_ledger','execution','candidate','fit_ids','physical_methods'])
def test_missing_scientific_field_rejects_before_writing(tmp_path,key):
    from ra.freeze import validate_scientific_fields, REQUIRED_FIELDS
    c={k:{'placeholder':True} for k in REQUIRED_FIELDS};c.pop(key)
    with pytest.raises(ValueError,match=key): validate_scientific_fields(c)


def test_protected_access_and_existing_outcomes_fail_closed(tmp_path):
    from ra.freeze import check_unopened
    ledger=tmp_path/'access.json';write(ledger,{'schema_version':1,'events':[]})
    outputs=tmp_path/'outcomes'
    check_unopened(ledger,outputs)
    write(ledger,{'schema_version':1,'events':[{'operation':'read','phase':'confirmatory'}]})
    with pytest.raises(ValueError,match='protected'): check_unopened(ledger,outputs)
    write(ledger,{'schema_version':1,'events':[]})
    outputs.mkdir();(outputs/'partial.json').write_text('{}')
    with pytest.raises(ValueError,match='protected'): check_unopened(ledger,outputs)


def test_immutable_envelope_detects_manifest_tampering(tmp_path):
    from ra.freeze import seal_manifest,verify_envelope
    out=tmp_path/'freeze.sha256';seal_manifest({'experiment_id':'x'},out)
    p=out.with_suffix('.manifest.json');raw=json.loads(p.read_text());raw['experiment_id']='y';p.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='digest'):verify_envelope(out)


def test_queue_pairs_fits_repeats_budgets_and_native_sharing():
    from ra.freeze import make_queue
    config={'experiment_id':'e1','fit_ids':['f1','f2'],'sample':{'timing_repeats':2},
        'physical_methods':{'A':{'kind':'shared'},'B0':{'kind':'native'}},
        'deadlines_ns':[1,4,16],'execution':{'solver_seeds':[17],'run_order_seed':31}}
    inputs=[dict(template_id='t1',instance_id='i1',cell_id='c1')]
    queue=make_queue(config,inputs)
    assert len(queue)==18
    assert len({x['request_id'] for x in queue})==18
    assert sum(x['method']=='B0' for x in queue)==6
    assert {x['fit_id'] for x in queue if x['method']=='B0'}=={'shared'}
    assert make_queue(config,inputs)==queue
    with pytest.raises(ValueError):make_queue(config,inputs+inputs)


def test_runtime_identity_includes_imported_baseline_subpackage():
    from ra.runner import _runtime_identity
    _,_,_,inventory=_runtime_identity()
    assert 'baselines/register.py' in inventory['sources']


def test_public_report_is_plainly_dry_and_cannot_report_protected(tmp_path):
    from ra.stats import write_pilot_report
    from test_design_calibration import rows,design
    out=tmp_path/'report.md'
    result=write_pilot_report(rows(),design(),out)
    assert result['dry_run'] is True
    assert 'DISCOVERY/VALIDATION DRY REPORT' in out.read_text()
    bad=rows();bad[0]['phase']='confirmatory'
    with pytest.raises(ValueError):write_pilot_report(bad,design(),out)


@pytest.fixture
def scientific(tmp_path,monkeypatch):
    """Real inputs/queue/register; git commit check isolated from uncommitted test checkout."""
    from ra import freeze
    from ra.data import generate_workload
    from ra.runner import _runtime_identity
    from ra.stats import calibrate_design
    monkeypatch.setattr(freeze,'_check_committed_sources',lambda commit, inventory: None)
    selected=json.loads(Path('configs/mandatory_baselines.json').read_text())['selected']
    methods={'A':selected['local-matched'],**{k:selected[k] for k in ('B0','B1','B2','B3','B5','B6')}}
    population=json.loads(Path('configs/workload_manifest.json').read_text())
    population['master_seed']='artificial-freeze-tests-disjoint-v1'
    protected=tmp_path/'protected'
    manifest=generate_workload(population,'confirmatory',protected)
    cells={r['cell_id']:1/6 for r in manifest['instances']}
    d=dict(deadlines=[1,4,16],cells=cells,methods=list(methods),native_methods=['B0','B1'],
        fit_ids=['task13-matched-fit1'],contrasts=[['A',k] for k in ('B0','B1','B2','B3','B5','B6')],
        sample_per_cell=2,timing_repeats=1,bootstrap_repetitions=128,seed=12,alpha=.05,useful_precision=.001)
    source,environment,build,_=_runtime_identity()
    rows=[]
    for c in cells:
        for i in range(2):
            for m in methods:
                for b in d['deadlines']:
                    rows.append(dict(phase='validation',template_id=f'{c}-{i}',cell_id=c,repeat=0,budget_ns=b,
                        method=m,fit_id='shared' if m in ('B0','B1') else d['fit_ids'][0],utility=.5,
                        source_hash=source,wall_ns=b,peak_rss_bytes=10,trace_bytes=1,overshoot_ns=0,status='complete',censored=False))
    c=dict(schema_version=1,experiment_id='test-v1',source_commit='a'*40,
        hardware=write(tmp_path/'hardware.json',{'test_fixture':True}),
        environment=dict(source_hash=source,environment_hash=environment,build_hash=build),
        models=[freeze.reference(Path(p)) for p in sorted({m['allocator']['model_path'] for m in methods.values() if 'model_path' in m.get('allocator',{})})],
        features=[freeze.reference(Path('configs/features.json'))],baseline_register=freeze.reference(Path('configs/mandatory_baselines.json')),
        sample=dict(original_templates=12,templates_per_cell=2,timing_repeats=1,fit_runs=1),
        deadlines_ns=d['deadlines'],weights=[.25,.5,.25],bootstrap={'B':6,'alpha':.05,'repetitions':128},contrasts=d['contrasts'],
        watchdog={'workers':1,'grace_ns':2000000000},exclusions=freeze.ordinary_fault_policy(),capacity={'storage_envelope_bytes':100000,'worker_peak_envelope_bytes':40,'coordinator_reserve_bytes':100,'os_reserve_bytes':100,'physical_memory_bytes':1000,'free_storage_bytes':1000000},guardrails={'primal':'exploratory'},
        resources=write(tmp_path/'power.json',calibrate_design(rows,d)),
        protocol=write(tmp_path/'protocol.json',{'fixture':'no scientific evidence'}),
        execution_access_journal=str(tmp_path/'outcomes.access.json'),access_ledger=write(tmp_path/'access.json',{'schema_version':1,'events':[]}),outcome_directory=str(tmp_path/'outcomes'),
        candidate='local-matched',telemetry={'max_decisions':512},fit_ids=d['fit_ids'],physical_methods=methods,aliases={'B4':'B3'},gates={'WP04':'reviewed','WP05':'reviewed'},
        amendment={'number':0,'previous':None},population=population,planning=d,
        protected_manifests=[freeze.reference(protected/'manifest.json')])
    execution=json.loads(Path('configs/exploratory.json').read_text())
    execution.update(methods=list(methods.values()),budgets_ns=d['deadlines'],solver_seeds=[17],input_manifests=[str(protected/'manifest.json')])
    c['execution']=execution
    c['preflight']=write(tmp_path/'preflight.json',{'environment':c['environment'],'physical_methods':methods,'rows':write(tmp_path/'rows.json',rows)})
    c['queue']=write(tmp_path/'queue.json',freeze.make_queue(c,manifest['instances']))
    path=tmp_path/'config.json';write(path,c)
    return path,c,tmp_path/'freeze.sha256'


def test_complete_freeze_roundtrip_and_identical_dry_inputs(scientific):
    from ra.freeze import freeze_protocol,verify_protocol
    path,c,out=scientific
    dry=freeze_protocol(path,out,dry_run=True)
    assert not out.exists()
    assert freeze_protocol(path,out)==dry
    assert verify_protocol(out)['queue_count']==252
    with pytest.raises(ValueError,match='immutable'):freeze_protocol(path,out.parent/'second.sha256')


@pytest.mark.parametrize('mutation',['queue_missing','queue_duplicate','queue_order','config','model','split','source','status'])
def test_scientific_freeze_detects_real_drift(scientific,mutation,monkeypatch):
    from ra import freeze
    path,c,out=scientific
    freeze.freeze_protocol(path,out)
    if mutation=='source':
        real=freeze._source_inventory
        monkeypatch.setattr(freeze,'_source_inventory',lambda:{**real(),'drift.py':'0'*64})
    elif mutation in ('queue_missing','queue_duplicate','queue_order'):
        p=Path(c['queue']['path']);q=json.loads(p.read_text())
        if mutation=='queue_missing':q.pop()
        elif mutation=='queue_duplicate':q.append(q[0])
        else:q.reverse()
        write(p,q)
    elif mutation=='config': c['weights']=[.2,.5,.3];write(path,c)
    elif mutation=='model':
        # Alter the model pin in the config, never mutate shared repository model assets.
        c['models'][0]['sha256']='0'*64;write(path,c)
    elif mutation=='split':
        p=Path(c['protected_manifests'][0]['path']);m=json.loads(p.read_text());m['split']='validation';write(p,m)
    elif mutation=='status':c['gates']['WP05']='pending';write(path,c)
    with pytest.raises(ValueError):freeze.verify_protocol(out)


@pytest.mark.parametrize('mutation',['incomplete_queue','bad_weights','protected_access','incomplete_pilot','unmeasured_runtime','missing_model','bad_amendment'])
def test_freeze_rejects_invalid_resolved_science_before_publish(scientific,mutation):
    from ra.freeze import freeze_protocol
    path,c,out=scientific
    if mutation=='incomplete_queue':
        p=Path(c['queue']['path']);q=json.loads(p.read_text());q.pop();c['queue']=write(p,q)
    elif mutation=='bad_weights':c['weights']=[.5,.25,.25]
    elif mutation=='protected_access':c['access_ledger']=write(Path(c['access_ledger']['path']),{'schema_version':1,'events':[{'read':'protected'}]})
    elif mutation in ('incomplete_pilot','unmeasured_runtime'):
        p=Path(c['preflight']['path']);pre=json.loads(p.read_text());rp=Path(pre['rows']['path']);rows=json.loads(rp.read_text())
        if mutation=='incomplete_pilot':rows.pop()
        else: rows[0]['source_hash']='0'*64
        pre['rows']=write(rp,rows);c['preflight']=write(p,pre)
    elif mutation=='missing_model':c['models'].pop()
    else:c['amendment']={'number':0,'previous':'unrecorded'}
    write(path,c)
    with pytest.raises(ValueError):freeze_protocol(path,out)
    assert not out.exists()


def test_cli_freeze_and_verify_scientific_roundtrip(scientific,capsys):
    from ra.cli import main
    path,c,out=scientific
    assert main(['freeze','--config',str(path),'--out',str(out),'--dry-run'])==0
    assert not out.exists()
    assert main(['freeze','--config',str(path),'--out',str(out)])==0
    assert main(['verify-freeze','--manifest',str(out)])==0
    assert '"success": true' in capsys.readouterr().out


def test_successor_experiment_cannot_reset_amendment_counter(scientific):
    from ra.freeze import freeze_protocol,make_queue
    path,c,out=scientific
    freeze_protocol(path,out)
    new=copy.deepcopy(c);new['experiment_id']='test-v2'
    inputs=json.loads(Path(c['protected_manifests'][0]['path']).read_text())['instances']
    new['queue']=write(out.parent/'queue-v2.json',make_queue(new,inputs))
    nextpath=out.parent/'config-v2.json';write(nextpath,new)
    with pytest.raises(ValueError,match='amendment'):freeze_protocol(nextpath,out.parent/'freeze-v2.sha256')


def test_common_telemetry_overlay_preserves_all_selected_scientific_fields():
    from ra.freeze import deployment_methods
    register=json.loads(Path('configs/mandatory_baselines.json').read_text());before=copy.deepcopy(register)
    methods=deployment_methods(register,1024)
    for key,method in methods.items():
        expected=copy.deepcopy(register['selected']['local-matched' if key=='A' else key])
        if 'learned' in expected:expected['learned']['max_decisions']=1024
        assert method==expected
    assert register==before


def test_unresolved_public_method_fault_blocks_freeze(scientific):
    from ra.freeze import freeze_protocol
    from ra.stats import calibrate_design
    path,c,out=scientific
    p=Path(c['preflight']['path']);pre=json.loads(p.read_text());rp=Path(pre['rows']['path']);rows=json.loads(rp.read_text())
    rows[0]['status']='implementation_error'
    pre['rows']=write(rp,rows);c['preflight']=write(p,pre)
    c['resources']=write(Path(c['resources']['path']),calibrate_design(rows,c['planning']));write(path,c)
    with pytest.raises(ValueError,match='fault'):freeze_protocol(path,out)


def test_missing_transitive_preflight_asset_blocks_freeze(scientific):
    from ra.freeze import freeze_protocol
    path,c,out=scientific
    p=Path(c['preflight']['path']);pre=json.loads(p.read_text())
    pre['attempts']=[{'path':str(p.parent/'missing-attempt.json'),'sha256':'0'*64}]
    c['preflight']=write(p,pre);write(path,c)
    with pytest.raises(ValueError,match='hash'):freeze_protocol(path,out)


def successor(c, previous, base, number):
    from ra.freeze import make_queue,reference
    new=copy.deepcopy(c);new['experiment_id']=f'test-successor-{number}'
    new['amendment']={'number':number,'previous':reference(previous),'reason':'prospective correction'}
    new['outcome_directory']=str(base/f'outcomes-{number}')
    new['execution_access_journal']=str(base/f'outcomes-{number}.access.json')
    new['access_ledger']=write(base/f'access-{number}.json',{'schema_version':1,'events':[]})
    inputs=json.loads(Path(c['protected_manifests'][0]['path']).read_text())['instances']
    new['queue']=write(base/f'queue-{number}.json',make_queue(new,inputs))
    p=base/f'config-{number}.json';write(p,new)
    return p,new,base/f'freeze-{number}.sha256'


@pytest.mark.parametrize('observed',['none','immediate-outcome','earlier-outcome','earlier-journal'])
def test_successor_reused_inputs_require_unopened_entire_ancestry(scientific,observed):
    from ra.freeze import freeze_protocol,verify_envelope
    path,c,out=scientific;freeze_protocol(path,out)
    p1,c1,o1=successor(c,out,out.parent,1);freeze_protocol(p1,o1)
    p2,c2,o2=successor(c1,o1,out.parent,2)
    if observed.endswith('outcome'):
        ancestor=c1 if observed=='immediate-outcome' else c
        directory=Path(ancestor['outcome_directory']);directory.mkdir();(directory/'attempt.json').write_text('Do not open protected outcomes')
    elif observed=='earlier-journal':
        write(Path(c['outcome_directory']).with_suffix('.access.json'),{'schema_version':1,'events':[{'kind':'protected_input_opened'}]})
    if observed=='none':assert freeze_protocol(p2,o2)
    else:
        with pytest.raises(ValueError,match='reused|ancestor|protected'):freeze_protocol(p2,o2)
        assert not o2.exists()
    assert verify_envelope(out)['success'] and verify_envelope(o1)['success']


def test_zeroing_ordinary_fault_policy_is_rejected_before_freeze(scientific):
    from ra.freeze import freeze_protocol
    path,c,out=scientific
    c['exclusions']['method_fault']={'score':'zero','flag':'retain','action':'halt_and_diagnose'}
    write(path,c)
    with pytest.raises(ValueError,match='fault.*policy|fault.*score'):freeze_protocol(path,out)


def test_enlarged_trace_capacity_requires_conservative_resource_envelope(scientific):
    from ra.freeze import freeze_protocol
    path,c,out=scientific
    c['capacity']['storage_envelope_bytes']=0
    write(path,c)
    with pytest.raises(ValueError,match='capacity|envelope'):freeze_protocol(path,out)


def test_fresh_templates_do_not_inherit_observed_ancestor_reuse_ban(scientific):
    from ra.freeze import freeze_protocol,check_reused_ancestry
    path,c,out=scientific;freeze_protocol(path,out)
    _,new,_=successor(c,out,out.parent,1)
    directory=Path(c['outcome_directory']);directory.mkdir();(directory/'outcome.json').write_text('Do not read')
    check_reused_ancestry(new,[{'template_id':'fresh-template','instance_id':'fresh-instance'}])


def test_execution_access_journal_cannot_be_redirected(scientific):
    from ra.freeze import freeze_protocol
    path,c,out=scientific;c['execution_access_journal']=str(out.parent/'unrelated-empty.json');write(path,c)
    with pytest.raises(ValueError,match='journal'):freeze_protocol(path,out)
