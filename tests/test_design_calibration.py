"""Planning must preserve independent units and paired/shared observations."""
import copy
import pytest
from ra import metrics


def design():
    return dict(deadlines=[1,4,16], cells={'a':.5,'b':.5}, methods=['P','B0'],
        native_methods=['B0'], fit_ids=['fit1','fit2'], contrasts=[['P','B0']],
        sample_per_cell=4, timing_repeats=2, bootstrap_repetitions=1024,
        seed=83, alpha=.05, useful_precision=.02)


def rows():
    result=[]
    for cell in ('a','b'):
        for t in range(2):
            for repeat in range(2):
                for budget in (1,4,16):
                    for method,fit,value in [('B0','shared',.5),('P','fit1',.5+.1*t),('P','fit2',.6+.1*t)]:
                        result.append(dict(phase='validation',template_id=f'{cell}{t}',cell_id=cell,
                            repeat=repeat,budget_ns=budget,method=method,fit_id=fit,utility=value,
                            wall_ns=budget+1,peak_rss_bytes=100,trace_bytes=10,overshoot_ns=1,
                            status='complete',censored=False))
    return result


def calibrate(data=None, config=None):
    from ra.stats import calibrate_design
    return calibrate_design(rows() if data is None else data, design() if config is None else config)


def test_log_budget_weights_and_invalid_grid():
    assert hasattr(metrics,'log_budget_weights'), 'log budget integration missing'
    assert metrics.log_budget_weights((1,4,16)) == pytest.approx((.25,.5,.25))
    for bad in ((1,1,16),(0,1,4),(4,1,16),(1,), (1,float('nan')), (1,True)):
        with pytest.raises(ValueError): metrics.log_budget_weights(bad)


def test_crossed_fits_shared_native_and_paired_budgets():
    out=calibrate()
    assert out['independent_templates']==4
    assert out['independent_fit_runs']==2
    assert out['physical_observations']==72
    assert out['contrasts'][0]['estimate']==pytest.approx(.1)
    assert out['resources']['request_count']==144 # 8 templates * 2 repeats * 3 budgets * (1 native + 2 fits)
    assert out['uncertainty']['across_fit_reliable'] is False


def test_repeats_do_not_create_templates_or_fits():
    data=rows(); more=[{**r,'repeat':r['repeat']+2} for r in data]
    a,b=calibrate(data),calibrate(data+more)
    assert a['independent_templates']==b['independent_templates']==4
    assert a['independent_fit_runs']==b['independent_fit_runs']==2
    assert a['contrasts'][0]['estimate']==b['contrasts'][0]['estimate']


@pytest.mark.parametrize('mutation',['duplicate','missing','protected','native-fit','nonfinite','wrongcell'])
def test_incomplete_or_invalid_public_cohorts_reject(mutation):
    data=rows()
    if mutation=='duplicate': data.append(data[0])
    if mutation=='missing': data.pop()
    if mutation=='protected': data[0]['phase']='confirmatory'
    if mutation=='native-fit': data[0]['fit_id']='fit1'
    if mutation=='nonfinite': data[0]['utility']=float('nan')
    if mutation=='wrongcell': data[0]['cell_id']='b'
    with pytest.raises(ValueError): calibrate(data)


def test_one_per_cell_cannot_produce_population_precision():
    data=[r for r in rows() if r['template_id'].endswith('0') and r['fit_id']!='fit2']
    d=design();d['fit_ids']=['fit1']
    out=calibrate(data,d)
    assert out['uncertainty']['within_cell_variance_identified'] is False
    assert out['contrasts'][0]['population_interval'] is None
    assert out['contrasts'][0]['across_fit_interval'] is None
    assert out['conservative_half_width']>0


def test_strong_pairing_has_zero_difference_variation():
    data=rows()
    for r in data: r['utility']=.2+.1*int(r['template_id'][-1])+.02*r['repeat']
    out=calibrate(data)
    assert out['contrasts'][0]['conditional_interval']==pytest.approx([0,0])
    assert out['contrasts'][0]['across_fit_interval']==pytest.approx([0,0])


def test_calibration_is_invariant_to_json_object_order():
    a=design();b=copy.deepcopy(a);b['cells']=dict(reversed(list(a['cells'].items())))
    # Unequal cells expose accidental dependence of RNG assignment on dict order.
    data=rows()
    data += [{**r,'template_id':r['template_id']+'new','utility':r['utility']*.89} for r in data if r['cell_id']=='b']
    for r in data:
        if r['cell_id']=='b' and r['method']=='P':r['utility']+=.03
    x,y=calibrate(data,a),calibrate(list(reversed(data)),b)
    assert x['contrasts']==y['contrasts']
