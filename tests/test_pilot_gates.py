"""Scientific pilot guards: no outcome deletion, leakage, or universal oracle."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from ra.types import Attempt, AvailableProgress, Request
from ra import pilot
from ra.config import native_parameter_support, resolve_native_overrides


def attempt(status='complete', nodes=1, method='B0', kind='native', phase='pilot'):
    req = Request('r', '/input', 'h', 'i', 'c', 's', 'e', method, phase, 0, 100, 20, 10,
                  method_config={'name':method,'kind':kind,'overrides':{}})
    return Attempt('r', status, AvailableProgress(True, 1., 2, 2., 'h'), True,
                   {'launch_ns':0,'parent_release_ns':120},
                   {'native_nodes':nodes,'native_lps':nodes,'end_to_end_ns':130,'worker_peak_rss_bytes':100},
                   20, status != 'complete', None, req, template_id='t', cell_id='c',
                   lineage={'cell':{'family':'uniform'}},instance_provenance_available=True)


def test_root_only_is_proxy_insufficiency_not_h1_falsification():
    summary=pilot.summarize_headroom([attempt()])
    assert summary['root_only_count']==1
    assert summary['interpretation']=='proxy_insufficiency'
    assert summary['h1_falsified'] is False


def test_finite_envelope_retains_easy_failed_oom_and_raw_utility():
    attempts=[attempt(),attempt('oom',None),attempt('implementation_error',None),attempt('deadline',20)]
    attempts[0]=replace(attempts[0],available=replace(attempts[0].available,utility=1.00000001))
    result=pilot.summarize_headroom(attempts)
    assert len(result['records'])==4
    assert result['status_counts']['oom']==1
    assert result['records'][0]['utility']==1.00000001
    assert result['envelope_scope']=='finite-tested schedules; not a universal oracle'
    assert result['missing_native_work_count']==2


@pytest.mark.parametrize('change',[{'phase':'confirmatory'},{'kind':'learned'},{'model_hash':'fitted'}])
def test_learned_outcome_cannot_select_population(change):
    row=pilot.summarize_headroom([attempt()])
    row['records'][0].update(change)
    with pytest.raises(ValueError,match='native'):
        pilot.recommend_population(row)


def test_recommendation_never_automatically_filters_easy_cells():
    summary=pilot.summarize_headroom([attempt(),replace(attempt(nodes=30),cell_id='other')])
    result=pilot.recommend_population(summary)
    assert result['cell_ids']==['c','other']
    assert result['requires_recorded_judgment'] is True


def test_memory_admission_and_forecast_keep_failed_overshoot():
    costs=[{'wall_ns':100,'overshoot_ns':0,'peak_rss_bytes':10,'status':'complete'},
           {'wall_ns':500,'overshoot_ns':200,'peak_rss_bytes':50,'status':'oom','censored':True}]
    result=pilot.forecast('pilot',costs,{'request_count':10,'available_memory_bytes':10000,'reserve_bytes':100,'coordinator_bytes':100,'safety_factor':2,'timed':True})
    assert result['admitted_workers']==1
    assert result['wall_ns_observed_range']==[1000,5000]
    assert result['failed_count']==1 and result['censored_count']==1
    assert result['overshoot_ns_total']==200
    assert result['upper_bound_available'] is False


def test_unknown_cost_is_missing_not_zero():
    result=pilot.forecast('pilot',[{'status':'oom'}],{'request_count':2,'timed':True})
    assert result['wall_ns_observed_range'] is None
    assert result['missing_wall_count']==1
    assert result['admitted_workers']==0


def test_native_support_is_strict_json_with_unbounded_null_preserving_bounds():
    support=native_parameter_support()
    encoded=json.dumps(support,allow_nan=False)
    assert json.loads(encoded)['nodeselection/estimate/maxplungequot']['maximum'] is None
    params={name:meta['default'] for name,meta in support.items()}
    assert resolve_native_overrides(params,{'nodeselection/estimate/maxplungequot':1e100})['nodeselection/estimate/maxplungequot']==1e100
    with pytest.raises(ValueError):resolve_native_overrides(params,{'nodeselection/estimate/maxplungequot':-1})
    json.loads(Path('configs/native/search_space.json').read_text(),parse_constant=lambda value:pytest.fail(value))


def test_finite_envelope_pairs_same_instance_seed_and_deadline():
    baseline=attempt(nodes=20)
    alternate=replace(attempt(nodes=10,method='B1'),available=replace(baseline.available,utility=.9))
    baseline=replace(baseline,available=replace(baseline.available,utility=.8))
    other_seed=replace(alternate,request=replace(alternate.request,solver_seed=17),available=replace(alternate.available,utility=1.))
    summary=pilot.summarize_headroom([baseline,alternate,other_seed])
    pairs=summary['finite_envelope']
    paired=next(x for x in pairs if x['solver_seed']==0)
    assert paired['gain_over_B0']==pytest.approx(.1)
    assert next(x for x in pairs if x['solver_seed']==17)['gain_over_B0'] is None


def test_installed_support_is_harvested_once_per_cold_process_with_defensive_copies():
    """Repeat validation must not pay for three identical native dump harvests."""
    import subprocess,sys
    code='''
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import pyscipopt
original=pyscipopt.Model
calls=[]
def model(*args,**kwargs):
    calls.append(1)
    return original(*args,**kwargs)
pyscipopt.Model=model
from ra.config import native_parameter_support
first=native_parameter_support()
first['nodeselection/estimate/maxplungequot']['maximum']=17
second=native_parameter_support()
assert second['nodeselection/estimate/maxplungequot']['maximum'] is None
assert len(calls)==1, f'harvested installed support {len(calls)} times'
'''
    p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert p.returncode==0,p.stderr


def test_ranking_missing_worker_identity_uses_validated_original_without_new_unit():
    from checks.pilot_tuning_summary import summarize_records
    from dataclasses import asdict
    records=[]
    for identity,values in [('first',[.8,.9,1.]),('second',[1.,1.,1.])]:
        for budget,value in zip([100,200,400],values):
            a=asdict(attempt(phase='validation'))
            a['request'].update(instance_hash=identity,budget_ns=budget)
            a['available']['utility']=value
            a['template_id']=None if budget==200 else identity
            records.append(a)
    result=summarize_records(records,expected_budgets=[100,200,400])['methods']['B0']
    assert result['templates']==2 and result['attempts']==6
    assert result['mean_F']==pytest.approx(.95)


def test_tuning_helper_preserves_discovery_scope_and_rejects_bad_budget_cohorts():
    from checks.pilot_tuning_summary import summarize_records
    from dataclasses import asdict
    records=[]
    for identity in ['first','second']:
        for budget in [100,200,400]:
            a=asdict(attempt(phase='discovery'))
            a['request'].update(instance_hash=identity,budget_ns=budget)
            records.append(a)
    assert 'public discovery' in summarize_records(records,expected_budgets=[100,200,400])['scope']
    with pytest.raises(ValueError,match='duplicate'): summarize_records(records+[records[0]],expected_budgets=[100,200,400])
    with pytest.raises(ValueError,match='incomplete'): summarize_records(records[:-1],expected_budgets=[100,200,400])
    records[-1]['request']['phase']='validation'
    with pytest.raises(ValueError,match='phase'): summarize_records(records,expected_budgets=[100,200,400])


def test_tuning_helper_requires_declared_grid_when_all_cohorts_omit_same_deadline():
    from checks.pilot_tuning_summary import summarize_records
    from dataclasses import asdict
    rows=[]
    for budget in [100,400]:
        row=asdict(attempt(phase='discovery'));row['request']['budget_ns']=budget;rows.append(row)
    with pytest.raises(ValueError,match='declared'):summarize_records(rows)
    with pytest.raises(ValueError,match='incomplete'):summarize_records(rows,expected_budgets=[100,200,400])
    assert summarize_records(rows,expected_budgets=[100,400])['budgets_ns']==[100,400]
