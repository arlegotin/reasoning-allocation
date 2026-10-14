from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from ra.config import load_feature_schema
from ra.features import build_features
from ra.models import ModelBundle, MaskPreprocessor, original_weights, fit_bundle
from test_features import context, node


def batch():
    schema = load_feature_schema(Path('configs/features.json'))
    return schema, build_features(context(), [node(i) for i in range(2, 22)], [1, 4], {}, schema)


def test_train_only_mask_aware_imputation_constant_scale_and_retained_masks():
    schema, b = batch()
    x = b.matrix.copy(); x[:, 0] = 3; x[0, 0] = 0; x[0, 1] = 1
    prep = MaskPreprocessor.fit(x, schema)
    assert prep.medians[0] == 3
    assert prep.scales[0] == 1
    extreme = x.copy(); extreme[:, 0] = 1e12
    prep.transform(extreme)
    assert prep.medians[0] == 3 and prep.scales[0] == 1
    assert prep.transform(x)[0, 1] == 1
    assert prep.transform(x)[0, 0] == 0
    assert np.isfinite(prep.transform(x)).all()


def test_original_total_weights_equal_even_after_body_exclusions():
    w = original_weights(['a', 'a', 'a', 'b'])
    assert sum(w[:3]) == pytest.approx(w[3])
    assert w.sum() == pytest.approx(4)


@pytest.mark.parametrize('kind', ['ridge', 'histogram'])
def test_direct_targets_zero_gains_censored_body_exclusion_and_roundtrip(kind, tmp_path):
    schema, b = batch()
    gain = np.zeros(40); gain[::3] = .1
    body = np.full(40, .05); body[0] = 1e6
    eligible = np.ones(40, dtype=bool); eligible[0] = False
    model = fit_bundle(b, schema, gain, body, ['a'] * 20 + ['b'] * 20,
                       eligible, kind=kind, seed=17, parameters={'max_iter': 10} if kind == 'histogram' else {})
    p = model.predict(b)
    assert p.gain.shape == p.body_seconds.shape == (40,)
    assert p.body_seconds == pytest.approx(np.full(40, .05))
    assert model.counts == {'gain_rows': 40, 'zero_gains': 26, 'body_rows': 39, 'excluded_body_rows': 1, 'originals': 2}
    model.save(tmp_path / 'model.pkl')
    loaded = ModelBundle.load(tmp_path / 'model.pkl')
    assert loaded.predict(b).gain == pytest.approx(p.gain)
    with pytest.raises(ValueError, match='schema'):
        loaded.predict(replace(b, schema_hash='wrong'))
    x = b.matrix.copy(); x[0, 0] = np.nan
    with pytest.raises(ValueError): loaded.predict(replace(b, matrix=x))
    with pytest.raises(ValueError): loaded.predict(replace(b, action_rows=b.action_rows[:-1]))
    with pytest.raises(ValueError): loaded.predict(replace(b, action_rows=((node().key, 99),) + b.action_rows[1:]))


@pytest.mark.skipif(not Path('data/traces/train').exists(), reason='private Task11 evidence diagnostic')
def test_historical_reader_joins_sealed_correction_and_never_pooled():
    from ra.train import load_training_rows
    data = load_training_rows([Path('data/traces/train')], load_feature_schema(Path('configs/features.json')))
    assert len(data['gain']) == 306
    assert sum(data['eligible']) == 306
    assert sum(g == 0 for g in data['gain']) == 231
    assert len(set(data['originals'])) == 6
    assert data['batch'].matrix.shape == (306,192)
    assert data['correction_sha256'] == '582ef2e113e0bec48017c5ab9dbe59a9dfaece8e75cf969f584bf010f9775b78'
    assert all('pooled' not in x for x in data['inventory'])


@pytest.mark.skipif(not Path('data/traces/train').exists(), reason='private Task11 evidence diagnostic')
def test_train_public_dry_run_leaves_output_empty(tmp_path):
    from ra.train import fit_models
    result = fit_models(Path('configs/exploratory.json'), Path('data/traces/train'), tmp_path/'models', dry_run=True)
    assert result['dry_run'] and result['originals'] == 6
    assert not (tmp_path/'models').exists()


def test_declared_calibrated_support_is_distinct_from_observed_subset():
    schema,b=batch()
    model=fit_bundle(b,schema,np.zeros(40),np.ones(40),['a']*40,[True]*40,kind='ridge',seed=1,
                     supported_lengths=(1,2,4,8,16,32,64))
    unseen=replace(b,action_rows=((node(999).key,64),)+b.action_rows[1:])
    assert model.predict(unseen).gain.shape==(40,)
    assert model.metadata['observed_lengths']==[1,4]


@pytest.mark.parametrize('kind',['ridge','histogram'])
def test_numeric_export_preserves_raw_predictions_and_decisions(kind,tmp_path):
    from ra.allocators import LocalBidder
    schema,b=batch()
    model=fit_bundle(b,schema,np.arange(40)/40,np.arange(40)/100+0.01,['a']*20+['b']*20,[True]*40,
        kind=kind,seed=17,parameters={'max_iter':10,'min_samples_leaf':3} if kind=='histogram' else {},
        quantile=kind=='histogram')
    path=tmp_path/'m.json';model.export(path)
    loaded=ModelBundle.load(path)
    a,z=model.predict(b),loaded.predict(b)
    assert z.gain==pytest.approx(a.gain,abs=1e-12)
    assert z.body_seconds==pytest.approx(a.body_seconds,abs=1e-12)
    if a.body_q90 is not None: assert z.body_q90==pytest.approx(a.body_q90,abs=1e-12)
    options={'c_min':1e-6,'clock':lambda:2_050_000_000}
    p=LocalBidder(model,schema,**options).choose(context(entry_ns=2_000_000_000),[node(i) for i in range(2,22)],[1,4])
    q=LocalBidder(loaded,schema,**options).choose(context(entry_ns=2_000_000_000),[node(i) for i in range(2,22)],[1,4])
    assert (p.root,p.node_limit)==(q.root,q.node_limit)


def test_export_rejects_unknown_format_and_tree_schema(tmp_path):
    import json
    schema,b=batch()
    model=fit_bundle(b,schema,np.arange(40)/40,np.ones(40),['a']*40,[True]*40,kind='histogram',seed=17,
                     parameters={'max_iter':2,'min_samples_leaf':2})
    path=tmp_path/'m.json';model.export(path);raw=json.loads(path.read_text())
    raw['gain']['trees'][0]['left'][0]=999999
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='tree'): ModelBundle.load(path)


def test_export_parity_on_unseen_masks_thresholds_and_ties(tmp_path):
    from ra.allocators import LocalBidder
    schema,b=batch()
    x=b.matrix.copy();x[:,0]=np.linspace(-5,5,len(x))
    b=replace(b,matrix=x)
    model=fit_bundle(b,schema,(x[:,0]>0).astype(float),np.abs(x[:,0]),['a']*20+['b']*20,[True]*40,
                     kind='histogram',seed=43,parameters={'max_iter':8,'min_samples_leaf':2},quantile=True)
    path=tmp_path/'m.json';model.export(path);other=ModelBundle.load(path)
    unseen=x.copy();unseen[:,0]=np.linspace(-20,20,len(x));unseen[::3,1]=1;unseen[1::7,2]=1
    threshold=model.gain_model._predictors[0][0].nodes[0]['num_threshold']
    # Feature0 is scaled: test exact learned threshold and adjacent representable inputs.
    for i,v in enumerate((np.nextafter(threshold,-np.inf),threshold,np.nextafter(threshold,np.inf))):
        unseen[i,0]=v*model.preprocessing.scales[0]+model.preprocessing.centers[0];unseen[i,1:6]=0
    test=replace(b,matrix=unseen)
    for key in ('gain','body_seconds','body_q90'):
        assert getattr(other.predict(test),key)==pytest.approx(getattr(model.predict(test),key),abs=1e-12)
    a=LocalBidder(model,schema,c_min=1e-6,clock=lambda:2_050_000_000)
    z=LocalBidder(other,schema,c_min=1e-6,clock=lambda:2_050_000_000)
    nodes=[node(i) for i in range(2,22)];ctx=context(entry_ns=2_000_000_000)
    left=a.choose_batch(ctx,nodes,test);right=z.choose_batch(ctx,nodes,test)
    assert (left.root,left.node_limit)==(right.root,right.node_limit)


def test_equal_original_weight_is_used_by_both_estimators():
    schema,b=batch();b=replace(b,matrix=np.tile(b.matrix[0],(4,1)),action_rows=b.action_rows[:4])
    for kind in ('ridge','histogram'):
        model=fit_bundle(b,schema,[0,0,0,1],[1,1,1,3],['a','a','a','b'],[True]*4,kind=kind,seed=1,
                         parameters={'max_iter':2} if kind=='histogram' else {})
        assert model.predict(b).gain==pytest.approx([.5]*4)
        assert model.predict(b).body_seconds==pytest.approx([2.]*4)


def test_grouped_split_preserves_declared_held_originals_on_expansion():
    from ra.train import learning_groups
    held,available=learning_groups(['a','b','c','d','e','f'],['b','d'])
    assert held=={'b','d'} and available==['a','c','e','f']
    held2,available2=learning_groups(['a','b','c','d','e','f','g','h'],['b','d'])
    assert held2==held and not held2.intersection(available2)
    with pytest.raises(ValueError): learning_groups(['a'],['missing'])


def test_validation_scores_use_declared_log_weights_not_pooled_rows():
    from ra.train import validation_scores
    from types import SimpleNamespace as S
    attempts=[]
    for method,values in [('a',[1,0]),('b',[0,1])]:
        for budget,value in zip([1,4],values):
            attempts.append(S(request=S(method=method,instance_hash='original',budget_ns=budget,solver_seed=17),available=S(utility=value)))
    scores=validation_scores(attempts,{1:.75,4:.25})
    assert scores=={'a':.75,'b':.25}
    with pytest.raises(ValueError): validation_scores(attempts+[attempts[0]],{1:.75,4:.25})


def test_prediction_rejects_nonprimitive_action_key():
    schema,b=batch()
    model=fit_bundle(b,schema,np.zeros(40),np.ones(40),['a']*40,[True]*40,kind='ridge',seed=17)
    invalid=replace(b,action_rows=(('not-a-node',1),)+b.action_rows[1:])
    with pytest.raises(ValueError,match='action'): model.predict(invalid)


def test_lower_bound_sensitivity_counts_survive_gain_exclusion():
    from ra.train import target_sensitivity
    labels=[{'gain_fit_eligible':False,'body_fit_eligible':False,'duration_lower_bound':True,
             'deadline_censored':True,'completion_outcome_known':False},
            {'gain_fit_eligible':True,'body_fit_eligible':True,'duration_lower_bound':False,
             'deadline_censored':True,'completion_outcome_known':False}]
    assert target_sensitivity(labels)=={'all_labels':2,'excluded_gain_rows':1,'body_ineligible':1,
                                       'duration_lower_bounds':1,'deadline_censored':2,'natural_unknown':2}


def test_known_body_can_fit_when_gain_target_is_ineligible():
    schema,b=batch();b=replace(b,matrix=np.tile(b.matrix[0],(2,1)),action_rows=b.action_rows[:2])
    model=fit_bundle(b,schema,[0,100],[1,3],['a','a'],[True,True],kind='ridge',seed=17,
                     gain_eligible=[True,False])
    assert model.predict(b).gain==pytest.approx([0,0])
    assert model.predict(b).body_seconds==pytest.approx([2,2])
    assert model.counts['gain_rows']==1 and model.counts['body_rows']==2
