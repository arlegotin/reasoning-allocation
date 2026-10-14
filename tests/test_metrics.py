"""Known endpoints: no terminal leakage, status deletion, or budget averaging."""
from dataclasses import replace
import pytest
from ra.types import Attempt, AvailableProgress, Request, ProgressRecord
from ra.metrics import progress_at


def protocol():
    return {'deadlines_ns':[1,4,16], 'weights':[.25,.5,.25],
        'planning':{'cells':{'c':1.},'methods':['A','B0'],'native_methods':['B0'],
            'fit_ids':['f'],'deadlines':[1,4,16],'sample_per_cell':2,'timing_repeats':2,
            'contrasts':[['A','B0']],'bootstrap_repetitions':256,'seed':17,'alpha':.05,'useful_precision':.001},
        'bootstrap':{'repetitions':256,'seed':17,'alpha':.05,'B':1},
        'contrasts':[['A','B0']], 'aliases':{},'fit_ids':['f'],
        'physical_methods':{'A':{'name':'candidate'},'B0':{'name':'native'}},
        'execution':{'bound_tolerance':1e-6}}


def attempt(budget, value, method='candidate', template='t', status='complete'):
    request=Request(f'{template}-{method}-{budget}', '', 'input', 'instance', 'config', 'code', 'env',
        method,'confirmatory',0,budget,1,100,launch_ns=0,deadline_ns=budget)
    available=AvailableProgress(True,value,100,100*value,'hash',1)
    return Attempt(request.request_id,status,available,True,{}, {'end_to_end_ns':budget,'worker_cpu_ns':budget},
        0,False,None,request,template_id=template,cell_id='c',lineage={'family':'uniform'})


def test_frontier_uses_all_deadlines_and_retains_fault_output():
    from ra.metrics import summarize_attempts
    ats=[attempt(b,u,status='implementation_error' if b==4 else 'complete') for b,u in zip([1,4,16],[.2,.4,.8])]
    rows=summarize_attempts(ats,protocol())
    assert len(rows)==3
    assert [r['frontier'] for r in rows]==pytest.approx([.45]*3)
    assert rows[1]['utility']==.4 and rows[1]['fault']
    assert rows[1]['status']=='implementation_error'
    assert rows[1]['population_cell_weight']==1.


def test_summary_rejects_duplicate_and_incomplete_budget_groups():
    from ra.metrics import summarize_attempts
    ats=[attempt(b,.2) for b in [1,4,16]]
    for broken in [ats[:-1],ats+[ats[0]]]:
        with pytest.raises(ValueError,match='duplicate|incomplete'): summarize_attempts(broken,protocol())


def test_receipt_boundary_missing_assignment_and_alarm():
    records=[ProgressRecord('r',1,1,2,100,20,'a',True),ProgressRecord('r',2,2,5,50,40,'b',True)]
    assert progress_at(records,2,100).utility==pytest.approx(.2)
    assert progress_at(records,4,100).utility==pytest.approx(.2)
    assert progress_at(records,5,100).utility==pytest.approx(.9)
    assert progress_at([],4,100).utility==0
    with pytest.raises(ValueError): progress_at([replace(records[0],dual_original=101)],4,100)


def test_raw_gap_is_not_tolerance_plot_clipped():
    from ra.metrics import summarize_attempts
    ats=[replace(attempt(b,1.),available=AvailableProgress(True,1.000000005,100,100.0000005,'h',1)) for b in [1,4,16]]
    row=summarize_attempts(ats,protocol())[0]
    assert row['raw_gap']<0 and row['plot_gap']==0
    assert row['utility']>1 and row['solved'] and not row['correctness_alarm']


def test_actual_generator_lineage_preserves_family():
    from ra.metrics import summarize_attempts
    ats=[replace(attempt(b,.2),lineage={'cell':{'family':'block'}}) for b in [1,4,16]]
    assert {r['family'] for r in summarize_attempts(ats,protocol())}=={'block'}
