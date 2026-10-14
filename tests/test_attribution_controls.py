from pathlib import Path
import numpy as np
import pytest
from ra.allocators import LocalBidder
from ra.config import load_feature_schema
from ra.models import PredictionBatch
from ra import train
from test_features import context,node

class Model:
    def predict(self,batch):
        self.batch=batch
        return PredictionBatch(np.arange(len(batch.matrix),dtype=float)+1,np.ones(len(batch.matrix)))


def control(control_id, fixed_length=None):
    schema=load_feature_schema(Path('configs/features.json'))
    assert 'control_id' in __import__('inspect').signature(LocalBidder).parameters, 'matched controls missing'
    return LocalBidder(Model(),schema,c_min=1e-6,clock=lambda:2_050_000_000,control_id=control_id,fixed_length=fixed_length)


def test_b3_refit_interface_and_one_node_support():
    assert hasattr(train,'fit_control'), 'refitted control interface missing'
    b=control('B3')
    assert b.choose(context(entry_ns=2_000_000_000),[node(2),node(3)],[1,4]).node_limit == 1
    assert {length for _,length in b.bundle.batch.action_rows} == {1}


def test_b4_holds_supported_fixed_length_across_decisions():
    b=control('B4',4)
    for candidates in ([node(2)], [node(2),node(3)]):
        assert b.choose(context(entry_ns=2_000_000_000),candidates,[1,4,16]).node_limit == 4
        assert {length for _,length in b.bundle.batch.action_rows} == {4}
    with pytest.raises(ValueError,match='support'):
        b.choose(context(entry_ns=2_000_000_000),[node(2)],[1])


def test_b5_estimate_node_even_when_other_node_prediction_better():
    b=control('B5')
    a=b.choose(context(entry_ns=2_000_000_000),[node(2,native_estimate=1),node(3,native_estimate=9)],[1,4])
    assert a.root == node(2).key
    assert a.node_limit == 4


def test_compact_diagnostics_preserve_decision_and_selected_raw_prediction():
    b=control('B5')
    a=b.choose(context(entry_ns=2_000_000_000),[node(2),node(3)],[1,4])
    full=b.last_diagnostics
    assert hasattr(b,'compact_diagnostics'), 'compact audit interface missing'
    compact=b.compact_diagnostics
    assert compact['selected_gain'] == a.gain_prediction
    assert compact['prediction_ns'] == full['prediction_ns']
    assert compact['prediction_sha256'] == b._prediction_hash
    assert 'rates' not in compact and len(compact) < 30
    assert b.refresh_batch() == a


def test_b3_rejects_historical_mixed_action_regime():
    from ra.train import load_training_rows
    root=Path('data/traces/train')
    if not root.exists(): pytest.skip('historical local evidence is not installed')
    schema=load_feature_schema(Path('configs/features.json'))
    with pytest.raises(ValueError,match='no supported training rows'):
        load_training_rows([root],schema,control_id='B3')


def test_b4_tail_exception_never_changes_fixed_lease():
    b=control('B4',4)
    class TailModel(Model):
        def predict(self,batch):
            p=super().predict(batch)
            return PredictionBatch(p.gain,p.body_seconds,np.full(len(batch.matrix),100.))
    b.bundle=TailModel()
    a=b.choose(context(entry_ns=2_000_000_000),[node(2)],[1,4])
    assert a.node_limit == 4 and b.last_diagnostics['tail_exception']


def test_compact_expiry_has_no_stale_selected_prediction():
    from ra.allocators import BidderExpired
    b=control('B5')
    b.choose(context(entry_ns=2_000_000_000),[node(2),node(3)],[1,4])
    b.clock=lambda:20_000_000_000
    with pytest.raises(BidderExpired):
        b.choose(context(entry_ns=2_000_000_000),[node(2)],[1])
    compact=b.compact_diagnostics
    assert compact['expired'] and 'selected_gain' not in compact


def test_compact_logging_keeps_negative_selected_raw_gain_and_body():
    from test_bidder import FixedModel
    schema=load_feature_schema(Path('configs/features.json'))
    b=LocalBidder(FixedModel([-.2],[-.1]),schema,c_min=1e-6,clock=lambda:2_050_000_000)
    a=b.choose(context(entry_ns=2_000_000_000),[node(2)],[1])
    d=b.compact_diagnostics
    assert a.gain_prediction == d['selected_gain'] == -.2
    assert d['selected_body_seconds'] == -.1
    assert d['negative_gain_count'] == d['negative_body_count'] == 1
    assert a.seconds_prediction == 1e-6


def test_tuning_deployment_keeps_actual_control_regime(monkeypatch):
    monkeypatch.syspath_prepend(str(Path('checks').resolve()))
    from task13_tuning import deployment
    template={'name':'old','kind':'shared','pool_size':128,
              'allocator':{'policy':'local','control_id':'B5','fixed_length':4},
              'learned':{'pool_seed':17}}
    for control_id,length in [('B3',1),('B4',8),('B5',None)]:
        m=deployment(template,'new','/tmp/asset.json','hash',control_id,length)
        assert m['allocator']['control_id']==control_id
        assert m['allocator'].get('fixed_length')==(length if control_id=='B4' else None)
        assert m['allocator']['model_path']=='/tmp/asset.json'
        assert m['learned']['compact_logging'] is True
    assert template['allocator']['fixed_length']==4


def test_tuning_survivors_preserve_regime_winners_and_ridge_anchors(monkeypatch):
    monkeypatch.syspath_prepend(str(Path('checks').resolve()))
    from task13_tuning import survivors
    methods=[{'name':f'fix1-L{n}-{model}'} for n in (1,2,4,8,16,32,64) for model in ('ridge1','ridge0p1','ridge10','hist7')]
    methods += [{'name':'fix1-B5-'+model} for model in ('ridge1','ridge0p1','ridge10','hist7','hist15','hist31')]
    methods += [{'name':n} for n in ('B0','B1-no-plunge','B2-estimate-L1')]
    scores={m['name']:float(i) for i,m in enumerate(methods)}
    chosen=survivors(methods,scores)
    names={m['name'] for m in chosen}
    assert all(f'fix1-L{n}-hist7' in names for n in (1,2,4,8,16,32,64))
    assert {'fix1-L1-ridge1','fix1-B5-ridge1','fix1-B5-hist31','fix1-B5-hist15','B0','B1-no-plunge','B2-estimate-L1'}<=names
    assert len(names)==len(chosen)<=16


def test_tuning_expansion_uses_measured_quality_and_actual_deployment_cost(monkeypatch):
    monkeypatch.syspath_prepend(str(Path('checks').resolve()))
    from task13_tuning import expansion_request
    assert expansion_request('fix1-B5-hist7',.0003,1.1,1_200_000)=='hist15'
    assert expansion_request('fix1-L8-ridge0p1',.0003,1.1,200_000)=='ridge0p01'
    assert expansion_request('fix1-L1-ridge10',.0003,1.1,200_000)=='ridge100'
    assert expansion_request('fix1-B5-hist7',.00005,1.1,1_200_000) is None
    assert expansion_request('fix1-B5-hist7',.0003,1.3,1_200_000) is None
    assert expansion_request('fix1-B5-hist7',.0003,1.1,6_000_000) is None
