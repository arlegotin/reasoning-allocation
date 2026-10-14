from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from ra.allocators import LocalBidder, BidderExpired
from ra.models import PredictionBatch
from ra.config import load_feature_schema
from test_features import context, node

class FixedModel:
    def __init__(self, gain, body, q90=None):
        self.values = PredictionBatch(np.array(gain), np.array(body), None if q90 is None else np.array(q90))
    def predict(self, batch): return self.values


def bidder(gain, body, q90=None, now=2_050_000_000, **kw):
    return LocalBidder(FixedModel(gain, body, q90), load_feature_schema(Path('configs/features.json')),
                       c_min=1e-6, fallback_length=4, clock=lambda: now, **kw)


def test_current_administration_changes_rate_ranking():
    b = bidder([.2,.3], [.05,.2])
    ctx = context(entry_ns=2_000_000_000)
    a = b.choose(ctx, [node(2),node(3)], [1])
    assert a.root == node(2).key
    assert a.seconds_prediction == pytest.approx(.1)
    assert b.last_diagnostics['rates'] == pytest.approx([2,1.2])


def test_tail_uses_future_body_without_charging_past_admin_twice():
    b = bidder([.2,.3], [.05,.2], [.06,.2])
    a = b.choose(context(entry_ns=1_500_000_000, deadline_ns=2_150_000_000), [node(2),node(3)], [1])
    assert a.root == node(2).key
    assert b.last_diagnostics['surviving'] == [True, False]


def test_tail_fallback_length_one_and_negative_raw_prediction():
    b = bidder([-.2,-.3,0,0], [.1]*4, [1]*4)
    a = b.choose(context(entry_ns=2_000_000_000,deadline_ns=2_150_000_000), [node(2),node(3,native_estimate=1.)], [1,4])
    assert (a.root,a.node_limit) == (node(3).key,1)
    assert b.last_diagnostics['gain'] == [-.2,-.3,0,0]
    assert b.last_diagnostics['fallback'] is True


def test_positive_ties_shorter_then_node_and_zero_fixed_fallback():
    b = bidder([1]*4,[.1]*4)
    assert b.choose(context(entry_ns=2_000_000_000),[node(3),node(2)],[4,1]).node_limit == 1
    assert b.choose(context(entry_ns=2_000_000_000),[node(3),node(2)],[4,1]).root == node(2).key
    b = bidder([0]*4,[.1]*4)
    assert b.choose(context(entry_ns=2_000_000_000),[node(3),node(2)],[1,4]).node_limit == 4


def test_expiry_records_prediction_cost_requests_stop_and_returns_no_allocation():
    stopped=[]
    b = bidder([1],[.1],now=3_000_000_000,request_stop=lambda: stopped.append(True))
    with pytest.raises(BidderExpired):
        b.choose(context(entry_ns=2_000_000_000,deadline_ns=2_500_000_000), [node()], [1])
    assert stopped == [True]
    assert b.last_diagnostics['expired'] and 'prediction_ns' in b.last_diagnostics


def test_local_config_requires_exact_model_hash_and_loads(tmp_path):
    import hashlib
    from ra.models import fit_bundle
    from ra.features import build_features
    from ra.allocators import make_allocator
    schema = load_feature_schema(Path('configs/features.json'))
    batch = build_features(context(), [node(2),node(3)], [1,4], {}, schema)
    model = fit_bundle(batch, schema, np.zeros(4),np.ones(4),['a']*4,[True]*4,kind='ridge',seed=1)
    path = tmp_path/'m.pkl'; model.save(path)
    config = {'policy':'local','model_path':str(path),'model_hash':hashlib.sha256(path.read_bytes()).hexdigest(),
              'schema_path':str(Path('configs/features.json').resolve()),'schema_hash':schema.hash,
              'c_min':.000001,'fallback_length':4}
    assert isinstance(make_allocator(config,0),LocalBidder)
    config['model_hash']='0'*64
    with pytest.raises(ValueError,match='hash'): make_allocator(config,0)
