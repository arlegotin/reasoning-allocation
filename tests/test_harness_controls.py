"""Real cold requests and serial schedule/recovery contracts."""
from dataclasses import replace
import json
import hashlib
from pathlib import Path
import pytest
from scipy.sparse import csr_matrix
from ra.types import CoverInstance, Request
from ra.exact import canonical_cover
from ra.provenance import instance_hash, SplitOwnership
from ra import runner
from ra.cli import main


def public_input(tmp_path):
    cover = CoverInstance('', 'public-null', 'tiny', csr_matrix([[1,1,0],[0,1,1]]), (1,2,1), {'split':'discovery'})
    digest = instance_hash(cover)
    cover = replace(cover, instance_id=digest)
    path = tmp_path/'input.json'
    path.write_text(json.dumps({**canonical_cover(cover), 'instance_id':digest, 'template_id':cover.template_id, 'cell_id':'tiny','lineage':cover.lineage}))
    owners = SplitOwnership(); owners.register(cover,'discovery'); owners.save(tmp_path/'ownership.json')
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'schema_version':1,'split':'discovery','ownership_registry':str(tmp_path/'ownership.json'), 'instances':[{'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'instance_id':digest}]}))
    return manifest


def configuration(tmp_path, methods=None):
    manifest = public_input(tmp_path)
    config = {'schema_version':1,'purpose':'exploratory','input_manifests':[str(manifest)],
              'methods':methods or [{'name':'B0','kind':'native','overrides':{}},{'name':'alias','kind':'native','overrides':{}}],
              'solver_seeds':[17], 'run_order_seed':31,'budgets_ns':[2_000_000_000], 'watchdog_grace_ns':1_000_000_000,
              'lease_lengths':[1,2,4], 'threads':1,'integrality_tolerance':1e-6,'bound_tolerance':1e-6}
    path=tmp_path/'run.json';path.write_text(json.dumps(config));return path


def test_identical_named_native_controls_couple_logical_output_and_reap_serially(tmp_path):
    attempts = runner.run_schedule(configuration(tmp_path), 'discovery', tmp_path/'runs')
    assert len(attempts)==2
    assert [(a.status,a.available.utility,a.available.primal_original,a.available.dual_original,a.resources['native_nodes'],a.resources['native_lps']) for a in attempts] == [('complete',1.,2,2.,0,0)]*2
    assert attempts[0].timestamps['parent_release_ns'] < attempts[1].timestamps['launch_ns']
    assert all(a.resources['selection_count']==0 for a in attempts)
    assert runner.run_schedule(tmp_path/'run.json','discovery',tmp_path/'runs',resume=True)==[]
    accounting = list((tmp_path/'runs').glob('batch-*/accounting.json'))
    assert len(accounting)==2
    audit=json.loads(accounting[0].read_text())
    assert audit['total_observed_ns']>0 and audit['coordinator_cpu_ns']>0
    assert audit['report_generation_tail_ns'] is None


def test_dry_run_validates_without_writing_and_order_is_reproducible(tmp_path):
    path=configuration(tmp_path)
    assert runner.run_schedule(path,'pilot',tmp_path/'absent',dry_run=True)==[]
    assert not (tmp_path/'absent').exists()
    assert runner.prepare_schedule(path,'pilot')[0]==runner.prepare_schedule(path,'pilot')[0]
    assert main(['run','--config',str(path),'--phase','pilot','--out',str(tmp_path/'cli'),'--dry-run'])==0
    assert not (tmp_path/'cli').exists()


@pytest.mark.parametrize('phase', ['confirmatory','shift','invented'])
def test_protected_execution_is_unavailable_even_dry_run(tmp_path,phase):
    with pytest.raises(ValueError): runner.run_schedule(configuration(tmp_path),phase,tmp_path/'out',dry_run=True)


def test_manifest_cannot_lie_about_protected_input_or_hash(tmp_path):
    path=configuration(tmp_path)
    manifest=tmp_path/'manifest.json'; payload=json.loads(manifest.read_text());payload['split']='train';manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError):runner.run_schedule(path,'train',tmp_path/'out',dry_run=True)


def test_native_override_changes_do_not_leak_into_next_worker(tmp_path):
    methods=[{'name':'B1','kind':'native','overrides':{'nodeselection/dfs/stdpriority':300000}}, {'name':'B0','kind':'native','overrides':{}}]
    attempts=runner.run_schedule(configuration(tmp_path,methods),'discovery',tmp_path/'runs')
    by_name={a.request.method:a for a in attempts}
    assert by_name['B1'].resources['native_settings']['nodeselection/dfs/stdpriority']==300000
    assert by_name['B0'].resources['native_settings']['nodeselection/dfs/stdpriority']==0
    assert all(a.status=='complete' and a.resources['selection_count']==0 for a in attempts)


def test_delayed_publication_worsens_real_parent_deadline_score(tmp_path, monkeypatch):
    from test_worker import driver
    path=configuration(tmp_path); requests,_=runner.prepare_schedule(path,'discovery')
    baseline=runner.run_request(requests[0],tmp_path/'normal')
    driver(monkeypatch,tmp_path, '''
from ra.worker import Channel, execute_request
import time
original=Channel.send
def send(self, packet):
    if packet['kind']=='progress': time.sleep(1.1)
    original(self,packet)
Channel.send=send
''')
    delayed=runner.run_request(replace(requests[0],budget_ns=700_000_000),tmp_path/'delayed')
    assert baseline.available.utility==1
    assert delayed.available.utility==0
    assert delayed.status in ('deadline','startup_timeout')


def test_shared_alias_uses_same_logical_lease_trajectory(tmp_path):
    from ra.data import GeneratorCell, generate_cover
    from ra.exact import canonical_cover
    from ra.provenance import SplitOwnership
    path=configuration(tmp_path,[{'name':n,'kind':'shared','allocator':{'policy':'estimate','length':2},'pool_size':None} for n in ['estimate','alias']])
    cover=generate_cover(GeneratorCell('uniform',64,64,8),17)
    # Generation is original public data; retain declared discovery ownership.
    cover=replace(cover,lineage={**cover.lineage,'split':'discovery'},instance_id='')
    cover=replace(cover,instance_id=instance_hash(cover))
    input_path=tmp_path/'input.json'
    input_path.write_text(json.dumps({**canonical_cover(cover),'instance_id':cover.instance_id,'template_id':cover.template_id,'cell_id':cover.cell_id,'lineage':cover.lineage}))
    owners=SplitOwnership();owners.register(cover,'discovery');owners.save(tmp_path/'ownership.json')
    manifest=tmp_path/'manifest.json'; m=json.loads(manifest.read_text());m['instances'][0].update(instance_id=cover.instance_id,sha256=hashlib.sha256(input_path.read_bytes()).hexdigest());manifest.write_text(json.dumps(m))
    attempts=runner.run_schedule(path,'discovery',tmp_path/'runs')
    assert all(a.status=='complete' for a in attempts),[a.error for a in attempts]
    assert all(a.resources['allocation_decisions'] for a in attempts)
    def logical(a):
        return [(d['allocation']['root'],d['allocation']['node_limit'],d['pool_ids']) for d in a.resources['allocation_decisions']]
    assert logical(attempts[0])==logical(attempts[1])
    assert [(a.available.primal_original,a.available.dual_original,a.resources['native_nodes'],a.resources['native_lps']) for a in attempts[:1]]==[(a.available.primal_original,a.available.dual_original,a.resources['native_nodes'],a.resources['native_lps']) for a in attempts[1:]]


def test_named_depth_native_alias_does_not_install_custom_selector(tmp_path):
    methods=[{'name':'depth','kind':'native','overrides':{}}]
    attempts=runner.run_schedule(configuration(tmp_path,methods),'discovery',tmp_path/'runs')
    assert attempts[0].resources['selector_installed'] is False
    assert attempts[0].resources['selection_count']==0
    assert attempts[0].resources['selection_boundaries']==[]


def test_generated_public_manifest_is_accepted_without_invented_lineage_fields(tmp_path):
    from ra.data import generate_workload
    config={'schema_version':1,'purpose':'workload','master_seed':'public','templates_per_cell':1,
            'cells':[{'family':'uniform','columns':8,'rows':8,'degree':4}]}
    manifest=generate_workload(config,'discovery',tmp_path/'generated')
    path=configuration(tmp_path);raw=json.loads(path.read_text());raw['input_manifests']=[str(tmp_path/'generated'/'manifest.json')];path.write_text(json.dumps(raw))
    assert runner.run_schedule(path,'discovery',tmp_path/'absent',dry_run=True)==[]


def test_primary_schedules_cannot_overlap_across_output_directories(tmp_path):
    import fcntl, tempfile
    path=configuration(tmp_path)
    with (Path(tempfile.gettempdir())/'ra-primary-timed.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='timed run'):
            runner.run_schedule(path,'discovery',tmp_path/'runs')


@pytest.mark.parametrize('replacement',[{}, {'split':'discovery','ownership_registry':False,'instances':[]},
    {'split':'discovery','ownership_registry':'ownership.json','instances':[{'path':'input.json'}]}])
def test_malformed_manifest_has_clean_cli_failure(tmp_path,replacement,capsys):
    path=configuration(tmp_path)
    (tmp_path/'manifest.json').write_text(json.dumps(replacement))
    assert main(['run','--config',str(path),'--phase','discovery','--dry-run'])==1
    assert 'failed:' in capsys.readouterr().err


@pytest.mark.parametrize('changes',[{'threads':True},{'solver_seeds':[True]},{'budgets_ns':[0]},
    {'run_order_seed':True},{'lease_lengths':[1,1]},{'bound_tolerance':float('inf')},
    {'methods':[{'name':'bad','kind':'shared','allocator':{'policy':'estimate','length':3},'pool_size':None}]}])
def test_bad_run_schema_rejects_before_output(tmp_path,changes):
    path=configuration(tmp_path);config=json.loads(path.read_text());config.update(changes);path.write_text(json.dumps(config))
    with pytest.raises(ValueError):runner.run_schedule(path,'discovery',tmp_path/'out',dry_run=True)
    assert not (tmp_path/'out').exists()
