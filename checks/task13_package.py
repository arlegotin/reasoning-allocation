"""Seal compact public evidence and verify the final Task13 artifact boundary."""
from collections import Counter
import json
from pathlib import Path
from task13_controls import OUT,ROOT,read
from task13_summary import sha,write


def main():
    from ra.runner import _runtime_identity
    from ra.config import load_feature_schema
    from ra.features import pooled_schema
    summary=read(ROOT/'docs/superpowers/evidence/task13.json')
    rows=read(OUT/'raw-outcomes.json')
    assert len(rows)==1614 and set(r['status'] for r in rows)<={'complete','deadline'}
    assert Counter(r['phase'] for r in rows)=={'train':252,'validation':1362}
    assert _runtime_identity()[0]==read(OUT/'source-generation-2.json')['source_hash']
    assert len(summary['candidate_fits'])==30 and all(r['status']=='fitted' for r in summary['candidate_fits'])
    card=read(ROOT/'docs/superpowers/evidence/task13-controls-card.json')
    for method in card['selected'].values():
        if method['kind']=='shared' and 'model_path' in method['allocator']:
            assert sha(method['allocator']['model_path'])==method['allocator']['model_hash']
    protocols={n:read(OUT/(n+'.json')) for n in ('protocol','capacity-protocol','capacity-expansion-protocol','frontier-protocol','logging-protocol','native-timing-protocol')}
    protocols['native-timing-protocol']['context']['power']['stdout']='AC Power; battery 100%, charged (hardware identifier omitted)'
    write(ROOT/'protocol/task13-controls.json',protocols)
    schema=load_feature_schema(ROOT/'configs/features.json');pooled=pooled_schema(schema)
    card['features'].update(local_hash=schema.hash,pooled_hash=pooled.hash,pooled_names=pooled.names[192:],
        preprocessing=pooled.preprocessing,population='unique candidate nodes, first length row, finite aggregates with explicit unavailable masks')
    parity=read(OUT/'parity.json');card['parity']={k:v for k,v in parity.items() if k!='checks'}
    card['parity'].update(path=str((OUT/'parity.json').relative_to(ROOT)),sha256=sha(OUT/'parity.json'))
    card['limitations'] += [
        'Main pooled histogram15 and subsequent matched capacity ridge winners differ; public time blocks are not independent confirmation.',
        'Native no-plunge short-deadline incumbent is sensitive to cold startup/search timing; no robust native winner established.',
        'K128/512/all never bind on these observed frontiers; no large-frontier generalization.',
        'Initial22 candidate fitting process has no measured peak RSS; later capacity fitting peak RSS is observed.']
    card['fit_resource_envelopes']={n:read(OUT/(n+'.json')) for n in ('capacity-fitting-resources','capacity-expansion-resources')}
    manifest=[]
    for row in rows:
        p=ROOT/row['path'];account=p.parent/'accounting.json'
        manifest.append(dict(path=row['path'],sha256=sha(p),accounting_sha256=sha(account),attempt_id=row['attempt_id']))
    assets=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted((OUT/'models').glob('*/*')) if p.is_file()]
    write(OUT/'artifact-index.json',dict(attempts=manifest,models=assets,
        source_generations={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.glob('source-generation-*.json'))},
        scope='Attempt manifests transitively hash required progress/wire/label/feature/audit files; resource accounting retained separately.'))
    card['artifact_index']=dict(path=str((OUT/'artifact-index.json').relative_to(ROOT)),sha256=sha(OUT/'artifact-index.json'),attempts=len(manifest),model_files=len(assets))
    write(ROOT/'docs/superpowers/evidence/task13-controls-card.json',card)
    native=[]
    for row in rows:
        if row['method']!='B1-no-plunge' or not row['instance_hash'].startswith('edc897') or row['budget_ns']!=526707240:continue
        p=ROOT/row['path'];a=read(p);start=a['request']['deadline_ns']-row['budget_ns']
        progress=[json.loads(x) for x in (p.parent/'progress.jsonl').read_text().splitlines()]
        res=a['resources']
        native.append(dict(group=row['group'],attempt_id=row['attempt_id'],source_hash=row['source_hash'],
            method_config=a['request']['method_config'],available=row['available'],full_request_ns=row['full_request_ns'],
            publication_ns=row['publication_ns'],worker_exclusive_ns=res['worker_exclusive_ns'],elapsed_partition_ns=res['elapsed_partition_ns'],
            native_lps=res['native_lps'],native_nodes=res['native_nodes'],overshoot_ns=row['overshoot_ns'],
            progress=[dict(sequence=x['sequence'],child_elapsed_ns=x['child_ns']-start,receipt_elapsed_ns=x['receipt_ns']-start,
                           delivery_ns=x['receipt_ns']-x['child_ns'],primal=x['primal_original'],dual=x['dual_original']) for x in progress]))
    assert len(native)==3 and len({json.dumps(r['method_config'],sort_keys=True) for r in native})==1
    write(ROOT/'docs/superpowers/evidence/task13-native-timing.json',dict(attempts=native,
        scores=summary['native_timing_scores'],interpretation='Same settings/source, different cold/search timing before incumbent events. Thermal/background causation is not identified.'))
    print('verified1614 attempts,30 candidates,selected assets/source generation2; compact evidence and transitive artifact index written')


if __name__=='__main__':main()
