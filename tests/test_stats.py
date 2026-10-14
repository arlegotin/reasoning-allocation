"""Paired, stratified inference with hand-checked effects and shared native rows."""
import copy
import pytest
from test_metrics import protocol


def rows(advantage=.02, fits=('f',)):
    data=[]
    for t in ['t0','t1']:
        for m in ['A','B0']:
            for f in (['shared'] if m=='B0' else fits):
                for p in [0,1]:
                    for b in [1,4,16]:
                        data.append(dict(template_id=t,cell_id='c',method=m,fit_id=f,repeat=p,budget_ns=b,
                            utility=.4+(advantage if m=='A' else 0),status='deadline',frontier=.4+(advantage if m=='A' else 0)))
    return data


@pytest.mark.parametrize('gain',[0.,.02,-.02])
def test_constant_paired_advantage_has_exact_endpoints(gain):
    from ra.stats import paired_frontier_intervals
    result=paired_frontier_intervals(rows(gain),protocol())
    c=result['contrasts'][0]
    assert c['estimate']==pytest.approx(gain)
    assert c['ordinary_interval']==pytest.approx([gain,gain])
    assert c['simultaneous_interval']==pytest.approx([gain,gain])
    assert c['across_fit_interval'] is None
    assert result['status_counts']=={'deadline':24}
    assert result['uncertainty']['across_fit_reliable'] is False


def test_strata_weights_not_empirical_population_frequency():
    from ra.stats import paired_frontier_intervals
    p=protocol(); p['planning']['cells']={'c':.25,'d':.75}
    r=rows(0)
    for row in rows(.04): r.append({**row,'template_id':'d'+row['template_id'],'cell_id':'d'})
    assert paired_frontier_intervals(r,p)['contrasts'][0]['estimate']==pytest.approx(.03)


def test_native_is_shared_across_fit_draws_and_complete_pairs_required():
    from ra.stats import paired_frontier_intervals
    p=protocol(); p['planning']['fit_ids']=p['fit_ids']=['f','g']
    r=rows(.02,('f','g'))
    # Different template/repeat baselines cancel only if all methods remain paired.
    for row in r: row['utility']+=.1*(row['template_id']=='t1')+.1*row['repeat']
    result=paired_frontier_intervals(r,p)
    assert result['contrasts'][0]['across_fit_interval']==pytest.approx([.02,.02])
    assert result['uncertainty']['across_fit_reliable'] is False
    for bad in [r[:-1],r+[r[0]]]:
        with pytest.raises(ValueError,match='duplicate|incomplete'): paired_frontier_intervals(bad,p)


def test_bonferroni_and_all_contrasts_retained():
    from ra.stats import paired_frontier_intervals
    p=protocol(); p['planning']['methods'].append('B1'); p['planning']['native_methods'].append('B1')
    p['contrasts'].append(['A','B1']); p['planning']['contrasts']=p['contrasts'];p['bootstrap']['B']=2
    r=rows();r += [{**v,'method':'B1','status':'startup_timeout'} for v in r if v['method']=='B0']
    result=paired_frontier_intervals(r,p)
    assert len(result['contrasts'])==2 and result['per_contrast_alpha']==.025
    assert result['status_counts']['startup_timeout']==12


@pytest.mark.parametrize('n',[1,2,3])
def test_planning_rejects_too_few_bootstrap_draws(n):
    from ra.stats import calibrate_design
    p=protocol()['planning'];p['bootstrap_repetitions']=n
    with pytest.raises(ValueError,match='bootstrap|dimensions'): calibrate_design([{**r,'phase':'pilot'} for r in rows()],p)
