"""Offline verification of stored/runtime B6 input and executed predictions."""
from pathlib import Path
import json
import time
import numpy as np
from task13_controls import OUT,ROOT,read,LENGTHS,write


def audit():
    from ra.config import load_feature_schema
    from ra.features import pooled_schema
    from ra.train import load_training_rows,sha
    from ra.models import ModelBundle
    from ra.types import FeatureBatch,NodeKey
    from ra.collect import read_decision,digest,pooled_metadata
    started=time.perf_counter_ns()
    schema=load_feature_schema(ROOT/'configs/features.json')
    roots=[OUT/f'collection-L{n}' for n in LENGTHS]+[ROOT/'data/traces/train',ROOT/'data/traces/task12-odd']
    local=load_training_rows(roots,schema,control_id='B5')
    pooled=load_training_rows(roots,schema,control_id='B6')
    assert local['originals']==pooled['originals'] and local['batch'].action_rows==pooled['batch'].action_rows
    np.testing.assert_array_equal(local['batch'].matrix,pooled['batch'].matrix[:,:192])
    for key in ('gain','body','eligible','gain_eligible'):np.testing.assert_array_equal(local[key],pooled[key])
    assert pooled['batch'].matrix.shape[1]==301 and pooled['batch'].schema_hash==pooled_schema(schema).hash
    historical=load_training_rows([ROOT/'data/traces/train'],schema,control_id='B6')
    models={};checks=[]
    for path in sorted(OUT.rglob('attempt.json')):
        a=read(path);config=a['request']['method_config'].get('allocator',{})
        if config.get('control_id')!='B6': continue
        asset=config['model_path']
        if asset not in models:
            assert sha(asset)==config['model_hash'];models[asset]=ModelBundle.load(asset)
        for dispatch_path in sorted((path.parent/'trace').glob('dispatch-*.json')):
            dispatch=read(dispatch_path);i=dispatch['trace_index']
            row=read_decision(path.parent/'trace'/f'decision-{i:06d}.json')
            assert row['pooled_schema']==pooled_metadata(schema)
            assert row['pooled_schema_hash']==digest(row['pooled_schema'])
            pool_path=path.parent/'trace'/row['pooled_features']
            assert sha(pool_path)==row['pooled_sha256']
            x=np.concatenate((np.load(path.parent/'trace'/row['selected_features']),np.load(pool_path)),axis=1)
            action=(NodeKey(**dispatch['allocation']['root']),dispatch['allocation']['node_limit'])
            pred=models[asset].predict(FeatureBatch(x,(action,),pooled_schema(schema).hash,0))
            raw=dispatch['allocation']['gain_prediction']
            np.testing.assert_allclose(pred.gain[0],raw,atol=1e-12,rtol=1e-12)
            q=dispatch['allocation']['seconds_q90']
            if q is not None: np.testing.assert_allclose(pred.body_q90[0],q,atol=1e-12,rtol=1e-12)
            checks.append(dict(attempt_id=a['attempt_id'],index=i,absolute_gain_error=abs(float(pred.gain[0])-raw)))
    selected=read(ROOT/'docs/superpowers/evidence/task12-model-card.json')['selected']['allocator']
    assert sha(selected['model_path'])==selected['model_hash']
    report=dict(rows=len(local['gain']),originals=len(set(local['originals'])),historical_task11_rows=len(historical['gain']),
        local_schema_hash=schema.hash,pooled_schema_hash=pooled_schema(schema).hash,columns=[192,301],
        paired_training_targets=True,selected_runtime_rows=len(checks),max_gain_error=max(x['absolute_gain_error'] for x in checks),
        historical_local_asset_unchanged=selected['model_hash'],checks=checks,wall_ns=time.perf_counter_ns()-started)
    write(OUT/'parity.json',report)
    print({k:v for k,v in report.items() if k!='checks'})

if __name__=='__main__':audit()
