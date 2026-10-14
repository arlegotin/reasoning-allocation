"""Claim language cannot turn dual/primal tradeoffs into uniform superiority."""
import pytest


@pytest.mark.parametrize('bounds,word',[([.01,.03],'positive'),([-.03,-.01],'negative'),([-.0001,.0001],'tight-null'),([-.1,.1],'inconclusive')])
def test_distinct_claim_classes(bounds,word):
    from ra.report import classify_claim
    assert word in classify_claim(bounds,precision=.001,useful_effect_scale=.001)


def test_primal_worsening_is_tradeoff_even_with_frontier_gain():
    from ra.report import guardrail_interpretation
    assert 'tradeoff' in guardrail_interpretation(frontier_effect=.02,primal_effect=1.,dual_effect=3.)


def test_partial_inventory_cannot_publish_primary(tmp_path):
    from ra.report import validate_inventory
    queue=[dict(request_id='a'),dict(request_id='b')]
    with pytest.raises(ValueError,match='incomplete'): validate_inventory(queue,{'effective_attempts':[{'request_id':'a','attempt_id':'x'}]})
    with pytest.raises(ValueError,match='duplicate'): validate_inventory(queue,{'effective_attempts':[{'request_id':'a','attempt_id':'x'},{'request_id':'a','attempt_id':'y'}]})


def raw_fixture(tmp_path):
    """Artificial immutable receipt trace; optimum2, anchor4, late optimal receipt."""
    import json, hashlib
    from dataclasses import asdict
    from scipy.sparse import csr_matrix
    from ra.types import CoverInstance, Request, Attempt, AvailableProgress, ProgressRecord
    from ra.exact import canonical_cover, verify_cover
    from ra.provenance import instance_hash
    from ra.runner import publish_attempt
    cover=CoverInstance('', 'tiny-original','c',csr_matrix([[1,1,0],[0,1,1]]),(1,2,1),{'split':'discovery','family':'uniform'})
    path=tmp_path/'input.json'
    path.write_text(json.dumps({**canonical_cover(cover),'instance_id':instance_hash(cover),
        'template_id':cover.template_id,'cell_id':'c','lineage':cover.lineage}))
    request=Request('r',str(path),hashlib.sha256(path.read_bytes()).hexdigest(),instance_hash(cover),
        'config','source','env','native','discovery',0,10,2,4,launch_ns=100,deadline_ns=110)
    directory=tmp_path/'raw';directory.mkdir();(directory/'solutions').mkdir()
    assignments=[verify_cover(cover,v,0) for v in [(1,1,1),(1,0,1)]]
    records=[ProgressRecord('r',1,105,110,4,1,assignments[0].content_hash,True),
             ProgressRecord('r',2,109,111,2,2,assignments[1].content_hash,True)]
    wire=[{'receipt_ns':104,'packet':{'kind':'pong','parent_send_ns':101,'child_ns':103}}]
    for r,a in zip(records,assignments):
        (directory/'solutions'/f'{a.content_hash}.json').write_text(json.dumps(asdict(a)))
        wire.append({'receipt_ns':r.receipt_ns,'packet':{'kind':'progress','record':{**asdict(r),'receipt_ns':None},'assignment':asdict(a)}})
    (directory/'wire.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in wire))
    (directory/'progress.jsonl').write_text(''.join(json.dumps(asdict(r))+'\n' for r in records))
    a=Attempt('r','deadline',AvailableProgress(True,.25,4,1,assignments[0].content_hash,1),True,
        {},{},1,False,None,request,template_id='tiny-original',cell_id='c',lineage=cover.lineage,instance_provenance_available=True)
    publish_attempt(a,directory)
    return directory,a


def test_immutable_reconstruction_uses_exact_boundary_and_verifies_assignments(tmp_path):
    from ra.report import reconstruct_attempt
    directory,expected=raw_fixture(tmp_path)
    a=reconstruct_attempt(directory)
    assert a.available.utility==.25 and a.available.primal_original==4
    assert a.available==expected.available
    # Authenticating just the utility field or manifest would miss this mutation.
    solution=next((directory/'solutions').glob('*.json')); solution.write_text('{}')
    with pytest.raises(ValueError,match='hash'): reconstruct_attempt(directory)


def test_authenticated_but_invalid_assignment_rejected(tmp_path):
    import json,hashlib
    from ra.report import reconstruct_attempt
    directory,_=raw_fixture(tmp_path)
    solution=next((directory/'solutions').glob('*.json'));v=json.loads(solution.read_text());v['binary']=[0,0,0];solution.write_text(json.dumps(v))
    # Reseal a corrupt producer's payload: independent feasibility still rejects.
    p=directory/'attempt.json';value=json.loads(p.read_text());value['files_sha256'][str(solution.relative_to(directory))]=hashlib.sha256(solution.read_bytes()).hexdigest();p.write_text(json.dumps(value))
    (directory/'attempt.sha256').write_text(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
    with pytest.raises(ValueError,match='cover|assignment'): reconstruct_attempt(directory)


def test_dry_run_does_not_read_outcomes_or_write(tmp_path):
    from pathlib import Path
    from ra.report import analyze
    out=tmp_path/'report'
    result=analyze(Path('configs/confirmatory-A004.json'),out,dry_run=True)
    assert result['dry_run'] and not out.exists() and result['expected_requests']==2520


def test_resource_scopes_keep_peak_and_missing_cpu_without_double_counting():
    from ra.report import resource_summary
    from test_metrics import attempt,protocol
    from dataclasses import replace
    ats=[replace(attempt(b,.2),resources={'end_to_end_ns':10,'publication_ns':2,'worker_cpu_ns':3,
        'worker_sampled_cpu_ns_lower_bound':2,'worker_peak_rss_bytes':100,'parent_cpu_ns':1}) for b in [1,4,16]]
    rows=resource_summary(ats,{a.request_id:{'method':'A','budget_ns':a.request.budget_ns} for a in ats})
    assert sum(r['wall_including_publication_ns'] for r in rows)==36
    assert sum(r['worker_cpu_ns_lower_bound'] for r in rows)==9
    assert max(r['peak_worker_rss_bytes'] for r in rows)==100
    assert sum(r['publication_ns_subset'] for r in rows)==6


def test_calibration_only_observed_supported_actions_and_censoring():
    from ra.report import calibration_summary
    from test_metrics import attempt
    from dataclasses import replace
    a=replace(attempt(1,.2),resources={'lease_outcomes':[
        {'support_hash':'s','gain_prediction':.1,'endpoint_gain':.2,'full_ns':2000000000,'body_ns':2000000000,'seconds_prediction':1.,'seconds_q90':3.,'censored':False},
        {'support_hash':'s','gain_prediction':.1,'endpoint_gain':None,'full_ns':1000000000,'seconds_prediction':1.,'seconds_q90':3.,'censored':True},
        {'support_hash':None,'gain_prediction':.1,'endpoint_gain':.2,'full_ns':2000000000,'body_ns':2000000000,'seconds_prediction':1.,'seconds_q90':3.,'censored':False}]})
    r=calibration_summary([a],{a.request_id:{'method':'A'}})[0]
    assert r['observed_supported']==2 and r['censored']==1 and r['completed']==1
    assert r['gain_mean_error']==pytest.approx(.1) and r['seconds_mean_error']==1.
    assert r['q90_coverage_observed_complete']==1.


def test_cli_analyze_routes_dry_run_without_writing(tmp_path,capsys):
    from ra.cli import main
    assert main(['analyze','--config','configs/confirmatory-A004.json','--out',str(tmp_path/'out'),'--dry-run'])==0
    assert not (tmp_path/'out').exists()


def test_project_costs_count_physical_attempt_once_and_ignore_cumulative_prior(tmp_path):
    import json
    from ra.report import project_cost_inventory
    project=tmp_path/'project';out=tmp_path/'out';out.mkdir()
    for directory in ['artifacts/run/attempts/a/x','artifacts/copied/attempts/a/x']:
        p=project/directory;p.mkdir(parents=True)
        (p/'attempt.json').write_text(json.dumps({'attempt_id':'a','request_id':'r','status':'implementation_error',
            'resources':{'end_to_end_ns':10,'worker_cpu_ns':4,'worker_sampled_cpu_ns_lower_bound':3},
            'overshoot_ns':2,'cumulative_prior_costs':{'end_to_end_ns':999}}))
    result=project_cost_inventory(out,project=project)
    assert result['unique_physical_attempts']==1 and result['duplicate_copies_ignored']==1
    assert sum(r['request_wall_ns_lower_bound'] for r in result['scopes'])==10
    assert sum(r['worker_cpu_ns_lower_bound'] for r in result['scopes'])==4
    assert result['scopes'][0]['status_counts']=={'implementation_error':1}


def test_receipt_calibration_rebuilds_gain_and_checks_observed_support(tmp_path):
    import json
    from dataclasses import replace
    from ra.report import reconstruct_calibration
    from ra.types import ProgressRecord
    directory,a=raw_fixture(tmp_path); trace=directory/'trace';trace.mkdir()
    label={'trace_index':0,'root':{'epoch':0,'number':1},'node_limit':4,'entry_ns':105,'end_ns':111,
        'endpoint_gain':.25,'parent_utility_entry':0.,'parent_utility_end':.25,'support_hash':'support'}
    decision={'index':0,'allocation':{'root':label['root'],'node_limit':4},'pool_ids':[label['root']],'support_lengths':[1,4],
        'support_hash':'support'}
    (trace/'label-000000.json').write_text(json.dumps(label));(trace/'decision-000000.json').write_text(json.dumps(decision))
    progress=[ProgressRecord(**json.loads(line)) for line in (directory/'progress.jsonl').read_text().splitlines()]
    assert reconstruct_calibration(directory,progress,a.request)[0]['endpoint_gain']==.25
    decision['support_lengths']=[1];(trace/'decision-000000.json').write_text(json.dumps(decision))
    with pytest.raises(ValueError,match='support'): reconstruct_calibration(directory,progress,a.request)


def test_q90_targets_body_duration_and_deadline_censoring_is_retained():
    from dataclasses import replace
    from ra.report import calibration_summary
    from test_metrics import attempt
    base={'support_hash':'s','endpoint_gain':.2,'gain_prediction':.1,'full_ns':2000000000,'body_ns':500000000,
        'seconds_prediction':1.,'seconds_q90':1.,'censored':False}
    a=replace(attempt(1,.2),resources={'analysis_calibration':[base,{**base,'deadline_censored':True}]})
    r=calibration_summary([a],{a.request_id:{'method':'A'}})[0]
    assert r['q90_coverage_observed_complete']==1.
    assert r['completed']==1 and r['censored']==1


def test_calibration_uses_final_dispatched_revision_not_initial_preparation(tmp_path):
    import json,hashlib
    from ra.report import reconstruct_calibration
    from ra.types import ProgressRecord
    directory,a=raw_fixture(tmp_path);trace=directory/'trace';trace.mkdir()
    root={'epoch':0,'number':1}
    initial={'index':0,'allocation':{'root':root,'node_limit':1},'pool_ids':[root],'support_lengths':[1,4],
        'support_hash':'s','selected_features':'first.npy'}
    prepared={**initial,'allocation':{'root':root,'node_limit':4},'selected_features':'final.npy'}
    path=trace/'revision.json';path.write_text(json.dumps(prepared))
    dispatch={'allocation':prepared['allocation'],'selected_features':'final.npy',
        'final_decision':{'prepared':{'path':'revision.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()},'heuristic':None}}
    label={'trace_index':0,'root':root,'node_limit':4,'entry_ns':105,'end_ns':111,'endpoint_gain':.25,
        'parent_utility_entry':0.,'parent_utility_end':.25,'support_hash':'s'}
    for name,value in [('decision-000000.json',initial),('dispatch-000000.json',dispatch),('label-000000.json',label)]:
        (trace/name).write_text(json.dumps(value))
    progress=[ProgressRecord(**json.loads(line)) for line in (directory/'progress.jsonl').read_text().splitlines()]
    assert reconstruct_calibration(directory,progress,a.request)[0]['node_limit']==4


def test_frozen_planning_sensitivity_is_not_a_practical_null_margin():
    import json
    from pathlib import Path
    from ra.report import classify_claim
    config=json.loads(Path('configs/confirmatory-A004.json').read_text())
    text=classify_claim([-.00077,.00065],precision=config['planning']['useful_precision'])
    assert 'inconclusive' in text and 'tight-null' not in text and 'no equivalence' in text


@pytest.mark.parametrize('frontier,primal,dual',[(.02,1.,3.),(-.02,3.,1.),(.02,-3.,-1.)])
def test_opposing_primal_dual_directions_are_exploratory_tradeoffs(frontier,primal,dual):
    from ra.report import guardrail_interpretation
    assert 'tradeoff' in guardrail_interpretation(frontier_effect=frontier,primal_effect=primal,dual_effect=dual)


def test_secondary_budget_effects_keep_raw_components_without_inference():
    from ra.report import secondary_effects
    from test_metrics import protocol
    curves=[dict(scope='all',method=m,budget_ns=b,utility=u,primal=p,dual=d,raw_gap=p-d,
        relative_gap=(p-d)/p,normalized_primal=p/100,normalized_dual=d/100,solved=0,fault=0,assignment_available=1,overshoot_ns=0)
        for b in [1,4,16] for m,u,p,d in [('A',.42,60,2),('B0',.4,50,-10)]]
    result=secondary_effects(curves,protocol())
    assert len(result)==3
    assert all(r['utility_difference']==pytest.approx(.02) and r['primal_difference']==10 and r['dual_difference']==12 for r in result)
    assert all(r['scope']=='all' and r['inference']=='exploratory point differences only' for r in result)


@pytest.mark.parametrize('scope', ['analytical', 'blocked', 'validation'])
def test_achieved_scope_cannot_promote_unexecuted_confirmation(scope, tmp_path):
    import json
    from ra.report import build_report
    manifest=tmp_path/'achieved.json'
    manifest.write_text(json.dumps({'schema_version':1,'scope':scope,
        'packages':[{'name':'native capability','status':'blocked','reason':'unavailable'},
                    {'name':'failed pilot','status':'failed','reason':'retained fault'}],
        'references':{},'limitations':['No protected experiment executed.']}))
    out=tmp_path/'REPORT.md'
    result=build_report(manifest,out)
    assert result['empirical_solver_claims']==[]
    text=out.read_text().lower()
    assert 'confirmation not executed' in text
    assert 'native capability' in text and 'failed pilot' in text and 'blocked' in text
    assert '60 independent' not in text and '65536' not in text


def test_blocked_manifest_cannot_smuggle_in_confirmatory_claims(tmp_path):
    import json
    from ra.report import build_report
    p=tmp_path/'scope.json';p.write_text(json.dumps({'schema_version':1,'scope':'blocked',
        'packages':[], 'references':{},'empirical_solver_claims':['beats contemporary selector']}))
    with pytest.raises(ValueError,match='claim'):build_report(p,tmp_path/'out.md')


def test_complete_report_rebuilds_all_headlines_and_dry_run_is_read_only(tmp_path):
    from pathlib import Path
    from ra.report import build_report
    out=tmp_path/'REPORT.md'
    result=build_report(Path('protocol/freeze-A004.sha256'),out,dry_run=True)
    assert not out.exists() and result['dry_run']
    result=build_report(Path('protocol/freeze-A004.sha256'),out)
    assert len(result['headline_rows'])==6
    for row in result['headline_rows']:
        assert {'competitor','population','templates','fits','deadlines_ns','estimate','simultaneous_interval',
                'primal_difference','dual_difference','resources','training','claim','caveat'}<=row.keys()
    assert all('positive frontier' not in c for c in result['empirical_solver_claims'])
    assert 'B6' in out.read_text() and 'UNSTABLE' in out.read_text()


def test_a004_renderer_rejects_alternate_input_before_writing(tmp_path):
    from ra.report import render_report
    with pytest.raises(ValueError,match='A004'):
        render_report(tmp_path,{'source_commit':'alternate'}, {'contrasts':[]},[],{})
    assert not (tmp_path/'confirmatory_report.md').exists()


def test_report_cli_manifest_dry_run(tmp_path,capsys):
    from ra.cli import main
    assert main(['report','--manifest','protocol/freeze-A004.sha256','--out',str(tmp_path/'out'),'--dry-run'])==0
    assert not (tmp_path/'out').exists()
