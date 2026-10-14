from pathlib import Path
import numpy as np
import pytest
from ra.config import load_feature_schema
from ra.features import build_features
from ra import features
from ra.collect import pooled_features
from test_features import context, node


def test_pooled_context_unique_nodes_and_stored_runtime_parity():
    schema = load_feature_schema(Path('configs/features.json'))
    batch = build_features(context(frontier_size=7), [node(2, depth=1), node(3, depth=3)], [1,4], {}, schema)
    assert hasattr(features, 'append_pooled_context'), 'B6 context interface is missing'
    enriched = features.append_pooled_context(batch, schema)
    pooled_schema = features.pooled_schema(schema)
    assert enriched.matrix[:, pooled_schema.names.index('pool_node_depth_mean')] == pytest.approx(2)
    for name, value in [('population_std',1),('min',1),('max',3),('valid_count',2),('all_missing',0)]:
        assert enriched.matrix[:, pooled_schema.names.index('pool_node_depth_'+name)] == pytest.approx(value)
    historical, metadata, _ = pooled_features(batch,schema,2,2,7)
    assert historical.shape == (1,109)
    np.testing.assert_array_equal(enriched.matrix[:,192:],np.repeat(historical,4,axis=0))
    np.testing.assert_array_equal(enriched.matrix[:,:192],batch.matrix)
    assert enriched.schema_hash == pooled_schema.hash != schema.hash
    assert enriched.extraction_ns >= batch.extraction_ns
    assert not any('action_' in n for n in pooled_schema.names[192:])
    assert enriched.matrix[:,pooled_schema.names.index('pool_parent_estimate_all_missing')] == pytest.approx(1)
    assert enriched.matrix[:,pooled_schema.names.index('pool_frontier_size')] == pytest.approx(7)


def test_pooled_preprocessor_export_keeps_missing_masks_and_schema(tmp_path):
    from ra.models import fit_bundle, ModelBundle
    schema = load_feature_schema(Path('configs/features.json'))
    batch = build_features(context(),[node(2),node(3)],[1,4],{},schema)
    assert hasattr(features,'append_pooled_context'), 'B6 context interface is missing'
    batch = features.append_pooled_context(batch,schema)
    model = fit_bundle(batch,features.pooled_schema(schema),[0,1,0,2],[.1,.2,.3,.4],['a','a','b','b'],[True]*4,kind='ridge',seed=17)
    path=tmp_path/'model.json';model.export(path)
    np.testing.assert_allclose(ModelBundle.load(path).predict(batch).gain,model.predict(batch).gain,atol=1e-12)


def test_pooled_summary_survives_prepared_action_revision(tmp_path):
    import json
    from dataclasses import asdict
    from ra.collect import TraceWriter, read_decision
    schema=load_feature_schema(Path('configs/features.json'))
    batch=build_features(context(),[node(2),node(3)],[1],{},schema)
    writer=TraceWriter(tmp_path,schema,max_decisions=2)
    metadata={'context':{},'pool_hash':'pool','pool_ids':[], 'support_hash':'s', 'support_lengths':[1],
              'allocation':{'root':asdict(node(2).key),'node_limit':1}}
    writer.decision(batch.matrix[0],metadata,pooled_features(batch,schema,2,1,2))
    metadata['allocation']={'root':asdict(node(3).key),'node_limit':1}
    selected=writer.revision(batch.matrix[1],metadata,0,1)
    (tmp_path/'dispatch-000000.json').write_text(json.dumps({'allocation':metadata['allocation'],
        'selected_features':selected,'final_decision':{'prepared':writer.prepared,'heuristic':None}}))
    joined=read_decision(tmp_path/'decision-000000.json')
    assert 'pooled_features' in joined, 'revision lost immutable pool context'
    assert joined['selected_features'] == selected


def test_b6_retains_exact_pooled_input_for_runtime_audit():
    from ra.allocators import LocalBidder
    from test_attribution_controls import Model
    schema=load_feature_schema(Path('configs/features.json'))
    model=Model()
    bidder=LocalBidder(model,schema,c_min=1e-6,control_id='B6',clock=lambda:2_050_000_000)
    bidder.choose(context(entry_ns=2_000_000_000),[node(2),node(3)],[1,4])
    assert hasattr(bidder,'pooled_audit'), 'B6 must retain actual pooled model input for immutable trace audit'
    values,metadata,duration=bidder.pooled_audit
    np.testing.assert_array_equal(values,model.batch.matrix[:1,192:])
    assert metadata['source_local_schema']==schema.hash and duration > 0
