"""Artifact-only scientific freeze; never launches a protected solver.

Every reference is content checked. A freeze is an exclusive immutable pair of
files, with the manifest excluded from its own preimage. Runtime changes require
an explicit numbered successor experiment, preserving the original files.
"""
from __future__ import annotations
from collections import Counter
import copy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
import subprocess

from ra.metrics import log_budget_weights

REQUIRED_FIELDS = frozenset(('schema_version experiment_id source_commit hardware environment models features '
    'baseline_register sample deadlines_ns weights bootstrap contrasts watchdog exclusions resources preflight '
    'queue protected_manifests protocol access_ledger outcome_directory execution candidate fit_ids physical_methods '
    'aliases gates guardrails amendment population planning telemetry capacity execution_access_journal').split())


def canonical(value) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    from ra.worker import strict_json
    return strict_json(Path(path).read_text())


def reference(path: Path) -> dict[str,str]:
    path=Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def check_reference(ref):
    if not isinstance(ref,dict) or not {'path','sha256'}<=ref.keys() or not isinstance(ref['path'],str):
        raise ValueError('hash-addressed asset reference required')
    p=Path(ref['path'])
    if not p.is_file() or reference(p)['sha256']!=ref['sha256']:
        raise ValueError(f'asset hash drift: {p}')
    return p


def _references(value):
    if isinstance(value,dict):
        if {'path','sha256'}<=value.keys():
            yield value
        for v in value.values(): yield from _references(v)
    elif isinstance(value,list):
        for v in value: yield from _references(v)


def validate_scientific_fields(config):
    if not isinstance(config,dict):raise ValueError('scientific configuration object required')
    missing=sorted(k for k in REQUIRED_FIELDS if k not in config or config[k] is None or config[k]=='' or config[k]==[])
    if missing:raise ValueError('unresolved scientific fields: '+', '.join(missing))


def check_unopened(ledger: Path, outcome_directory: Path):
    access=read(ledger)
    if not isinstance(access,dict) or access.get('schema_version')!=1 or access.get('events')!=[]:
        raise ValueError('prior protected outcome access or unresolved access ledger')
    out=Path(outcome_directory)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('protected outcome namespace already contains artifacts')


def ordinary_fault_policy():
    """Binding endpoint: faults preserve validated progress; alarms quarantine claims."""
    return {
        'method_fault': {'score': 'last_valid_available_by_deadline', 'flag': 'retain',
                         'action': 'halt_and_diagnose'},
        'startup_timeout': {'score': 'zero_if_no_valid_progress'},
        'numerical_alarm': {'action': 'quarantine_scientific_claims', 'retain_evidence': True},
    }


def execution_access_path(config):
    # Historical freezes predate the explicit field. Their deterministic namespace
    # remains monitored; successors cannot redirect an ancestor's access record.
    expected=Path(config['outcome_directory']).with_suffix('.access.json').resolve()
    if 'execution_access_journal' in config and Path(config['execution_access_journal']).resolve()!=expected:
        raise ValueError('execution access journal must use the experiment namespace')
    return expected


def check_execution_unopened(config):
    check_unopened(check_reference(config['access_ledger']),Path(config['outcome_directory']))
    journal=execution_access_path(config)
    if journal.exists():
        data=read(journal)
        if not isinstance(data,dict) or data.get('schema_version')!=1 or data.get('events')!=[]:
            raise ValueError('protected execution access already recorded or unresolved')


def check_reused_ancestry(config, inputs):
    """Inspect only frozen inputs/access metadata and namespace existence, never outcomes."""
    templates={x['template_id'] for x in inputs}
    instances={x['instance_id'] for x in inputs}
    link=config['amendment'].get('previous');seen=set()
    while link is not None:
        key=str(check_reference(link).resolve())
        if key in seen:raise ValueError('cyclic amendment ancestry')
        seen.add(key)
        ancestor=verify_envelope(Path(key))['manifest']['scientific_config']
        old_inputs=[x for ref in ancestor['protected_manifests']
                    for x in read(check_reference(ref))['instances']]
        if any(x['template_id'] in templates or x['instance_id'] in instances for x in old_inputs):
            try:check_execution_unopened(ancestor)
            except (ValueError,OSError) as exc:
                raise ValueError('reused protected inputs have observed or unresolved ancestor access') from exc
        link=ancestor['amendment'].get('previous')


def check_capacity(config, forecast):
    cap=config['capacity'];keys=('storage_envelope_bytes','worker_peak_envelope_bytes',
        'coordinator_reserve_bytes','os_reserve_bytes','physical_memory_bytes','free_storage_bytes')
    if not isinstance(cap,dict) or any(type(cap.get(k)) is not int or cap[k]<=0 for k in keys):
        raise ValueError('positive integer capacity envelope required')
    multiplier=max(1,config['telemetry']['max_decisions']/1024)
    if (cap['storage_envelope_bytes']<multiplier*forecast['storage_bytes_with_reserve'] or
            cap['worker_peak_envelope_bytes']<multiplier*forecast['peak_rss_bytes_observed']):
        raise ValueError('capacity envelope below telemetry sensitivity reserve')
    if (cap['storage_envelope_bytes']>cap['free_storage_bytes'] or
        sum(cap[k] for k in ('worker_peak_envelope_bytes','coordinator_reserve_bytes','os_reserve_bytes'))>cap['physical_memory_bytes']):
        raise ValueError('capacity envelope exceeds available hardware')


def make_queue(config, instances):
    identities=[r['template_id'] for r in instances]
    if not identities or len(set(identities))!=len(identities) or len({r['instance_id'] for r in instances})!=len(instances):
        raise ValueError('missing/duplicate original protected inputs')
    queue=[]
    for repeat in range(config['sample']['timing_repeats']):
        templates=list(instances)
        random.Random(digest([config['execution']['run_order_seed'],repeat])).shuffle(templates)
        for instance in templates:
            for seed in config['execution']['solver_seeds']:
                for budget in config['deadlines_ns']:
                    block=[]
                    for method,definition in config['physical_methods'].items():
                        for fit in (['shared'] if definition['kind']=='native' else config['fit_ids']):
                            row=dict(experiment_id=config['experiment_id'],template_id=instance['template_id'],
                                instance_id=instance['instance_id'],cell_id=instance['cell_id'],method=method,
                                fit_id=fit,repeat=repeat,solver_seed=seed,budget_ns=budget)
                            block.append({**row,'request_id':digest(row)})
                    random.Random(digest([config['execution']['run_order_seed'],instance['template_id'],repeat,seed,budget])).shuffle(block)
                    queue.extend(block)
    if len({r['request_id'] for r in queue})!=len(queue):raise ValueError('duplicate queue request')
    return queue


def deployment_methods(register, max_decisions):
    """Explicit common telemetry overlay; selected policy/model fields stay intact."""
    if type(max_decisions) is not int or not 1<=max_decisions<=4096:
        raise ValueError('bounded common telemetry limit required')
    selected=register['selected']
    methods=copy.deepcopy({'A':selected['local-matched'],**{k:selected[k] for k in ('B0','B1','B2','B3','B5','B6')}})
    for method in methods.values():
        if 'learned' in method:method['learned']['max_decisions']=max_decisions
    return methods


def _source_inventory():
    root=Path(__file__).parent
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.py'))}


def _check_committed_sources(commit, inventory):
    root=Path(__file__).resolve().parents[2]
    if not isinstance(commit,str) or re.fullmatch('[0-9a-f]{40}',commit) is None:
        raise ValueError('full source commit identity required')
    for name,expected in inventory.items():
        got=subprocess.run(['git','show',f'{commit}:src/ra/{name}'],cwd=root,capture_output=True)
        if got.returncode or hashlib.sha256(got.stdout).hexdigest()!=expected:
            raise ValueError(f'current source is not the declared source commit: {name}')


def _protected_inputs(config):
    from ra.provenance import SplitOwnership
    from ra.worker import load_instance
    from ra.types import Request
    all_inputs=[]; assets=[]; ownership=SplitOwnership()
    for ref in config['protected_manifests']:
        p=check_reference(ref); manifest=read(p)
        if manifest.get('split')!='confirmatory' or manifest.get('config')!=config['population']:
            raise ValueError('protected population/split mismatch')
        registry=Path(manifest['ownership_registry']);owners=SplitOwnership.load(registry)
        assets.extend([ref,reference(registry)])
        for item in manifest['instances']:
            path=(p.parent/item['path']).resolve()
            if not path.is_relative_to(p.parent):raise ValueError('protected asset path escape')
            asset={'path':str(path),'sha256':item['sha256']};check_reference(asset)
            payload=read(path)
            provisional=Request('freeze-input',str(path),item['sha256'],item['instance_id'],
                'mechanical','mechanical','mechanical','native','confirmatory',0,1,1,sum(payload['costs']))
            instance=load_instance(provisional)
            if instance.template_id!=item['template_id'] or instance.cell_id!=item['cell_id']:
                raise ValueError('protected template/cell identity drift')
            local=SplitOwnership();local.register(instance,'confirmatory')
            if any(owners.owners.get(k)!=v for k,v in local.owners.items()):
                raise ValueError('protected input split ownership unresolved')
            ownership.register(instance,'confirmatory')
            all_inputs.append(item);assets.append(asset)
    counts=Counter(r['cell_id'] for r in all_inputs)
    if counts!={c:config['sample']['templates_per_cell'] for c in config['planning']['cells']}:
        raise ValueError('incomplete protected cell cohort')
    if len(all_inputs)!=config['sample']['original_templates']:raise ValueError('protected sample count mismatch')
    return all_inputs,assets


def resolve_protocol(config_path: Path, *, require_unopened=True):
    from ra.baselines.register import read_card,validate_register
    from ra.config import validate_run_config
    from ra.runner import _runtime_identity
    from ra.stats import calibrate_design
    c=read(config_path);validate_scientific_fields(c)
    if c['schema_version']!=1 or not isinstance(c['experiment_id'],str) or not re.fullmatch('[a-zA-Z0-9_-]+',c['experiment_id']):
        raise ValueError('invalid experiment identity/schema')
    if c['gates']!={'WP04':'reviewed','WP05':'reviewed'}:raise ValueError('unresolved WP04/05 gates')
    if not c['exclusions'] or not c['guardrails'] or not c['models'] or not c['features']:
        raise ValueError('unresolved failure/guardrail/model/feature policy')
    for ref in _references(c):check_reference(ref)
    execution_access_path(c)
    if require_unopened:check_execution_unopened(c)
    if any(c['exclusions'].get(k)!=v for k,v in ordinary_fault_policy().items()):
        raise ValueError('ordinary fault score policy or correctness quarantine mismatch')
    actual=_runtime_identity(); source,environment,build,inventory=actual
    if c['environment']!={'source_hash':source,'environment_hash':environment,'build_hash':build}:
        raise ValueError('current executable source/environment/build hash drift')
    sources=_source_inventory();_check_committed_sources(c['source_commit'],sources)
    hardware=read(check_reference(c['hardware']))
    if not isinstance(hardware,dict) or not hardware:raise ValueError('hardware inventory missing')
    register=read(check_reference(c['baseline_register']))
    cards=[read_card(ref) for ref in register['baseline_register']['cards']];validate_register(register,cards)
    selected=register['selected'];methods=c['physical_methods']
    if set(methods)!={'A','B0','B1','B2','B3','B5','B6'} or c['aliases']!={'B4':'B3'}:
        raise ValueError('required real controls and explicit B4 alias required')
    resolved=deployment_methods(register,c['telemetry']['max_decisions'])
    if c['candidate']!='local-matched' or methods['A']!=resolved['A']:
        raise ValueError('primary must be the declared matched-data adaptive candidate')
    for k in ('B0','B1','B2','B3','B5','B6'):
        if methods[k]!=resolved[k]:raise ValueError('selected mandatory control configuration drift')
    # Verify this specific one-node alias is numerical/support equivalent before sharing.
    a,b=selected['B3'],selected['B4']
    if (a['allocator']['model_hash']!=b['allocator']['model_hash'] or b['allocator'].get('fixed_length')!=1):
        raise ValueError('B3/B4 no longer a verified single-node alias')
    model_refs={str(check_reference(r)):r['sha256'] for r in c['models']}
    feature_refs={str(check_reference(r)):r['sha256'] for r in c['features']}
    for m in methods.values():
        opts=m.get('allocator',{})
        if 'model_path' in opts:
            if model_refs.get(str(Path(opts['model_path']).resolve()))!=opts['model_hash']:
                raise ValueError('model asset missing or hash drift')
            if str(Path(opts['schema_path']).resolve()) not in feature_refs:raise ValueError('feature schema asset missing')
            from ra.config import load_feature_schema
            if load_feature_schema(Path(opts['schema_path'])).hash!=opts['schema_hash']:
                raise ValueError('feature schema semantic hash drift')
    execution=c['execution'];validate_run_config(execution)
    if (execution['methods']!=list(methods.values()) or execution['budgets_ns']!=c['deadlines_ns']
            or execution['watchdog_grace_ns']!=c['watchdog']['grace_ns'] or execution['threads']!=1
            or c['watchdog'].get('workers')!=1):raise ValueError('execution/watchdog mismatch')
    expected=log_budget_weights(c['deadlines_ns'])
    if len(expected)!=len(c['weights']) or any(not math.isclose(a,b,rel_tol=1e-12) for a,b in zip(expected,c['weights'])):
        raise ValueError('deadline weights mismatch')
    contrasts=[['A',k] for k in ('B0','B1','B2','B3','B5','B6')]
    if c['contrasts']!=contrasts or c['bootstrap'].get('B')!=len(contrasts) or c['bootstrap'].get('alpha')!=.05:
        raise ValueError('required prespecified native/attribution/global contrasts missing')
    if c['sample']['fit_runs']!=len(c['fit_ids']) or c['fit_ids']!=['task13-matched-fit1']:
        raise ValueError('only one genuine fitted procedure available; seed aliases are not fit replicates')
    if any(type(c['sample'][k]) is not int or c['sample'][k]<1 for k in ('original_templates','templates_per_cell','timing_repeats','fit_runs')):
        raise ValueError('positive integer sample dimensions required')
    planning=c['planning']
    if (planning['contrasts']!=contrasts or planning['deadlines']!=c['deadlines_ns'] or planning['fit_ids']!=c['fit_ids']
            or planning['sample_per_cell']!=c['sample']['templates_per_cell'] or planning['timing_repeats']!=c['sample']['timing_repeats']
            or planning['bootstrap_repetitions']!=c['bootstrap']['repetitions']):raise ValueError('planning/frozen design mismatch')
    preflight=read(check_reference(c['preflight']))
    if preflight.get('environment')!=c['environment'] or preflight.get('physical_methods')!=methods:
        raise ValueError('current executable public preflight required')
    for ref in _references(preflight):check_reference(ref)
    rows=read(check_reference(preflight['rows']))
    for ref in _references(rows):check_reference(ref)
    if any(r.get('status') not in ('complete','deadline','startup_timeout') for r in rows):
        raise ValueError('unresolved current public preflight method fault')
    if any(r.get('source_hash')!=source for r in rows):raise ValueError('pilot does not measure current deployment')
    calibrated=calibrate_design(rows,planning)
    forecast=read(check_reference(c['resources']))
    if forecast!=calibrated:raise ValueError('resource/precision calibration drift')
    check_capacity(c,calibrated['resources'])
    if not all(r['quantile_stable'] for r in calibrated['contrasts']):raise ValueError('bootstrap quantile Monte Carlo stability unresolved')
    inputs,assets=_protected_inputs(c)
    if read(check_reference(c['queue']))!=make_queue(c,inputs):raise ValueError('missing/duplicate/incomplete or changed frozen queue')
    if calibrated['resources']['request_count']!=len(make_queue(c,inputs)):raise ValueError('forecast/queue size mismatch')
    amendment=c['amendment']
    if amendment.get('number')==0:
        if amendment!={'number':0,'previous':None}:raise ValueError('invalid original amendment record')
    else:
        previous=verify_envelope(check_reference(amendment['previous']))['manifest']
        old=previous['scientific_config']
        if (amendment['number']!=old['amendment']['number']+1 or c['experiment_id']==old['experiment_id']
                or not amendment.get('reason')):raise ValueError('numbered amendment and new experiment identity required')
    check_reused_ancestry(c,inputs)
    assets += list(_references(c)) + list(_references(preflight)) + list(_references(rows)) + [reference(config_path)]
    # Register transitive evidence and statuses as independently verified frozen assets.
    assets += list(_references(register))
    for card in cards:assets += list(_references(card))
    unique={str(Path(r['path']).resolve()):r['sha256'] for r in assets}
    for p,h in unique.items():check_reference({'path':p,'sha256':h})
    return dict(schema_version=1,experiment_id=c['experiment_id'],scientific_config=c,
        config_path=str(Path(config_path).resolve()),source_commit=c['source_commit'],source_inventory=sources,
        runtime_inventory=inventory,assets=[{'path':p,'sha256':h} for p,h in sorted(unique.items())],
        protected_outcomes_opened=False,queue_count=len(make_queue(c,inputs)),
        inference_scope='conditional on frozen fitted assets and training data; across-fit and training-procedure variability unidentifiable')


def seal_manifest(manifest: dict, out: Path, *, dry_run=False) -> str:
    out=Path(out); target=out.with_suffix('.manifest.json'); value=digest(manifest)
    if dry_run:return value
    if out.exists() or target.exists():raise ValueError('immutable freeze already exists; use numbered amendment and new experiment')
    out.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as f:f.write(canonical(manifest).decode()+'\n')
    with out.open('x') as f:f.write(value+'  '+target.name+'\n')
    return value


def verify_envelope(digest_path: Path) -> dict[str,object]:
    p=Path(digest_path)
    parts=p.read_text().strip().split('  ')
    if len(parts)!=2 or Path(parts[1]).name!=parts[1]:raise ValueError('invalid freeze digest reference')
    manifest=read(p.parent/parts[1])
    if digest(manifest)!=parts[0]:raise ValueError('frozen manifest digest drift')
    for ref in _references(manifest):check_reference(ref)
    return {'success':True,'digest':parts[0],'manifest':manifest}


def freeze_protocol(config_path: Path, out: Path, *, dry_run=False) -> str:
    manifest=resolve_protocol(config_path)
    # Refuse reusing an experiment identity at a different filename in this protocol directory.
    for p in Path(out).parent.glob('*.manifest.json'):
        prior=read(p)
        if prior.get('experiment_id')==manifest['experiment_id']:
            raise ValueError('immutable experiment ID already frozen; numbered amendment required')
        if manifest['scientific_config']['amendment']['number']==0:
            raise ValueError('existing protocol requires numbered amendment, not a reset experiment')
    return seal_manifest(manifest,out,dry_run=dry_run)


def verify_protocol(digest_path: Path) -> dict[str,object]:
    checked=verify_envelope(digest_path);manifest=checked['manifest']
    if 'scientific_config' not in manifest:raise ValueError('not a complete scientific freeze')
    current=resolve_protocol(Path(manifest['config_path']),require_unopened=False)
    if current!=manifest:raise ValueError('resolved protocol/source/environment drift')
    return {'success':True,'digest':checked['digest'],'experiment_id':manifest['experiment_id'],
            'queue_count':manifest['queue_count'],'source_commit':manifest['source_commit']}
