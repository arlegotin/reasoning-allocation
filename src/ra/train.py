"""Audited local trace fitting and public, cold closed-loop model selection."""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

CORRECTION = Path('artifacts/checks/task11/fix1/reconstruction/derived-duration-eligibility.json')
CORRECTION_HASH = '582ef2e113e0bec48017c5ab9dbe59a9dfaece8e75cf969f584bf010f9775b78'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_training_rows(roots, schema):
    """Read selected executed local rows only; raw historical flags never win."""
    import numpy as np
    from ra.types import FeatureBatch, NodeKey
    from ra.worker import strict_json, load_instance, Request
    from ra.collect import validate_training_instance
    inventory, matrices, labels, originals, families, budgets, actions = {}, [], [], [], [], [], []
    corrections = {}
    if CORRECTION.exists():
        if sha(CORRECTION) != CORRECTION_HASH: raise ValueError('duration correction hash mismatch')
        corrections = {str(Path(r['source_label']).resolve()): r for r in strict_json(CORRECTION.read_text())['rows']}
    attempts, seen, all_labels = {}, set(), []
    for root in roots:
        for path in sorted(Path(root).rglob('label-*.json')):
            path = path.resolve()
            if path in seen: raise ValueError('duplicate selected label across training roots')
            seen.add(path)
            attempt_path = path.parent.parent/'attempt.json'
            if attempt_path not in attempts:
                attempt = strict_json(attempt_path.read_text())
                request = Request(**attempt['request'])
                if request.phase != 'train': raise ValueError('training requires train namespace')
                instance = load_instance(request)
                index = validate_training_instance(instance)
                attempts[attempt_path] = (attempt, index)
                inventory[str(attempt_path)] = sha(attempt_path)
            attempt, index = attempts[attempt_path]
            label = strict_json(path.read_text())
            inventory[str(path)] = sha(path)
            correction = corrections.get(str(path))
            if correction:
                if (inventory[str(path)] != correction['source_label_sha256'] or
                        inventory[str(attempt_path)] != correction['source_attempt_manifest_sha256'] or
                        label['body_ns'] != correction['body_ns'] or label['trace_index'] != correction['trace_index']):
                    raise ValueError('historical target join mismatch')
                label['body_fit_eligible'] = correction['body_fit_eligible']
            elif 'duration_observation_known' not in label:
                raise ValueError('historical duration labels require sealed correction')
            all_labels.append(label)
            if not label['gain_fit_eligible'] and not label['body_fit_eligible']:
                continue
            decision_path = path.with_name(f"decision-{label['trace_index']:06d}.json")
            decision = strict_json(decision_path.read_text())
            selected = path.parent / decision['selected_features']
            if selected.parent.resolve() != path.parent or decision['feature_schema_hash'] != schema.hash:
                raise ValueError('local selected row/schema mismatch')
            if sha(selected) != decision['selected_features_sha256']:
                raise ValueError('selected row hash mismatch')
            allocation = decision['allocation']
            if (allocation['root'] != label['root'] or allocation['node_limit'] != label['node_limit']
                    or decision['index'] != label['trace_index'] or label['selected_features'] != selected.name
                    or label['dispatch_ns'] is None):
                raise ValueError('executed action alignment mismatch')
            matrix = np.load(selected, allow_pickle=False)
            if matrix.shape != (1,len(schema.names)) or matrix.dtype != np.float64 or not np.isfinite(matrix).all():
                raise ValueError('invalid selected local matrix')
            inventory[str(selected)] = sha(selected); inventory[str(decision_path)] = sha(decision_path)
            matrices.append(matrix[0]); labels.append(label)
            originals.append(attempt['request']['instance_hash'])
            families.append(attempt['lineage']['cell']['family'])
            budgets.append(attempt['request']['budget_ns'])
            # Offline rows span decisions: synthetic row keys keep action alignment unique.
            actions.append((NodeKey(0,len(actions)), label['node_limit']))
    if not matrices: raise ValueError('no supported training rows')
    return {'batch': FeatureBatch(np.asarray(matrices), tuple(actions), schema.hash, 0),
            'gain': np.asarray([x['endpoint_gain'] for x in labels]),
            'body': np.asarray([x['body_ns']/1e9 for x in labels]),
            'eligible': np.asarray([x['body_fit_eligible'] for x in labels],dtype=bool),
            'gain_eligible':np.asarray([x['gain_fit_eligible'] for x in labels],dtype=bool),
            'originals': originals, 'families': families, 'budgets': budgets, 'labels': labels,
            'censoring':['lower_bound' if x['duration_lower_bound'] else 'deadline' if x['deadline_censored']
                         else 'natural_unknown' if not x['completion_outcome_known'] else 'natural_known' for x in labels],
            'sensitivity':target_sensitivity(all_labels), 'inventory': inventory, 'correction_sha256': CORRECTION_HASH if corrections else None,
            'scheduled_originals': sorted({a['request']['instance_hash'] for a,_ in attempts.values()})}



def target_sensitivity(labels):
    return {'all_labels':len(labels),'excluded_gain_rows':sum(not x['gain_fit_eligible'] for x in labels),
            'body_ineligible':sum(not x['body_fit_eligible'] for x in labels),
            'duration_lower_bounds':sum(x['duration_lower_bound'] for x in labels),
            'deadline_censored':sum(x['deadline_censored'] for x in labels),
            'natural_unknown':sum(not x['completion_outcome_known'] for x in labels)}


def subset(data, rows):
    from ra.types import FeatureBatch
    import numpy as np
    ix = np.asarray(rows, dtype=int)
    b = data['batch']
    return {'batch': FeatureBatch(b.matrix[ix],tuple(b.action_rows[i] for i in ix),b.schema_hash,0),
            **{k: data[k][ix] for k in ('gain','body','eligible','gain_eligible')},
            **{k:[data[k][i] for i in ix] for k in ('originals','families','budgets','censoring')}}


def fit(data, schema, candidate, seed):
    from ra.models import fit_bundle
    return fit_bundle(data['batch'], schema, data['gain'], data['body'], data['originals'], data['eligible'],
                      kind=candidate['kind'], seed=seed, parameters=candidate['parameters'],
                      quantile=candidate.get('quantile',False), supported_lengths=(1,2,4,8,16,32,64),
                      gain_eligible=data['gain_eligible'])


def diagnostics(model, data):
    import numpy as np
    from ra.models import original_weights
    p = model.predict(data['batch']); eligible = data['eligible']
    def metrics(indices):
        ix = np.asarray(indices,dtype=int)
        gain_ix=ix[data['gain_eligible'][ix]]
        weights = original_weights([data['originals'][i] for i in gain_ix]) if len(gain_ix) else None
        body_ix = ix[eligible[ix]]
        return {'rows':len(ix),'originals':len({data['originals'][i] for i in ix}),
            'zero_gains':int((data['gain'][ix]==0).sum()), 'body_rows':len(body_ix),
            'gain_mse':float(np.average((p.gain[gain_ix]-data['gain'][gain_ix])**2,weights=weights)) if len(gain_ix) else None,
            'body_mse':float(np.average((p.body_seconds[body_ix]-data['body'][body_ix])**2,
                weights=original_weights([data['originals'][i] for i in body_ix]))) if len(body_ix) else None,
            'q90_observed_coverage':float(np.average(data['body'][body_ix]<=p.body_q90[body_ix],
                weights=original_weights([data['originals'][i] for i in body_ix]))) if p.body_q90 is not None and len(body_ix) else None}
    result = {'all':metrics(range(len(data['gain'])))}
    for field in ('families','budgets','eligible','censoring'):
        result[field] = {str(value):metrics([i for i,v in enumerate(data[field]) if v==value]) for value in sorted(set(data[field]))}
    result['length_support'] = dict(Counter(str(length) for _,length in data['batch'].action_rows))
    return result


def learned_method(path, schema_path, schema, *, name, c_min, fallback_length, collection=False):
    config = {'policy':'local','model_path':str(Path(path).resolve()),'model_hash':sha(path),
              'schema_path':str(Path(schema_path).resolve()),'schema_hash':schema.hash,
              'c_min':c_min,'fallback_length':fallback_length}
    runtime = {'epsilon':.2,'pool_seed':2026101412,'behavior_seed':2026101413,
               'schema_path':config['schema_path'],'schema_hash':schema.hash,'max_decisions':512}
    return {'name':name,'kind':'shared','allocator':config,'pool_size':128,
            'collection' if collection else 'learned':runtime}



def learning_groups(originals, held_originals=None):
    originals=sorted(set(originals))
    held=set(originals[::3] if held_originals is None else held_originals)
    if not held or not held <= set(originals) or held == set(originals):
        raise ValueError('nonempty disjoint supported original groups required')
    return held,[g for g in originals if g not in held]



def validation_scores(attempts, budget_weights):
    """Matched original/seed/budget grid; never lease- or survivor-weight utility."""
    from collections import defaultdict
    cells=defaultdict(dict)
    if not budget_weights or any(w<=0 for w in budget_weights.values()):
        raise ValueError('positive predeclared budget weights required')
    for a in attempts:
        r=a.request;key=(r.instance_hash,r.solver_seed,r.budget_ns)
        if key in cells[r.method]: raise ValueError('duplicate validation cell')
        cells[r.method][key]=a.available.utility
    if not cells or len({frozenset(x) for x in cells.values()})!=1:
        raise ValueError('unmatched validation cohort')
    result={}
    for method,values in cells.items():
        blocks=defaultdict(dict)
        for (original,seed,budget),value in values.items(): blocks[(original,seed)][budget]=value
        if any(set(v)!=set(budget_weights) for v in blocks.values()): raise ValueError('incomplete budget grid')
        originals=defaultdict(list)
        for (original,seed),values in blocks.items():
            originals[original].append(sum(values[b]*w for b,w in budget_weights.items())/sum(budget_weights.values()))
        result[method]=sum(sum(v)/len(v) for v in originals.values())/len(originals)
    return result


def fit_models(config_path: Path, trace_root: Path, output: Path, *, dry_run=False):
    import fcntl
    import tempfile
    from ra.config import load_config, load_feature_schema
    from ra.runner import _atomic_json, _runtime_identity, _run_schedule
    started, cpu = time.perf_counter_ns(), time.process_time_ns()
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    config = load_config(config_path,'run'); options = config['training']
    schema_path = (config_path.parent/options['schema']).resolve(); schema = load_feature_schema(schema_path)
    # One admission lock spans fitting and serial validation. Heavy fitting stops before timed requests.
    with (Path(tempfile.gettempdir())/'ra-primary-timed.lock').open('a+b') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('training cannot overlap timed solver work') from None
        roots = [Path(trace_root), *[(config_path.parent/p).resolve() for p in options.get('additional_trace_roots',[])]]
        data = load_training_rows(roots,schema)
        forecast = {'success':True,'dry_run':dry_run,'rows':len(data['gain']),
                    'originals':len(set(data['originals'])),'candidates':len(options['grid'])*len(options['fit_seeds'])}
        if dry_run: return forecast
        if output.exists() and any(output.iterdir()): raise ValueError('model output must be empty; fits are immutable')
        output.mkdir(parents=True,exist_ok=True)
        code_hash, environment_hash, build_hash, runtime = _runtime_identity()
        _atomic_json(output/'data-inventory.json',data['inventory'],immutable=True)
        _atomic_json(output/'runtime-inventory.json',runtime,immutable=True)
        _atomic_json(output/'config.json',config,immutable=True)
        import shutil
        (output/'source').mkdir()
        for path in Path(__file__).parent.glob('*.py'): shutil.copyfile(path,output/'source'/path.name)
        shutil.copyfile(schema_path,output/'features.json')
        records=[]; originals=sorted(set(data['originals']))
        # Fixed original-held-out diagnostics; no lease from a held-out original enters fitting.
        held, available = learning_groups(originals,options.get('diagnostic_holdout_originals'))
        held_data=subset(data,[i for i,g in enumerate(data['originals']) if g in held])
        for candidate in options['grid']:
            for seed in options['fit_seeds']:
                name=f"{candidate['name']}-seed{seed}"
                begin, cpu_begin = time.perf_counter_ns(),time.process_time_ns()
                record={'name':name,'candidate':candidate,'seed':seed,'status':'failed','curves':[]}
                try:
                    for count in sorted({max(1,len(available)//2),len(available)}):
                        ids=set(available[:count]); train=subset(data,[i for i,g in enumerate(data['originals']) if g in ids])
                        cb=time.perf_counter_ns(); m=fit(train,schema,candidate,seed)
                        record['curves'].append({'train_originals':sorted(ids),'held_originals':sorted(held),
                            'fit_ns':time.perf_counter_ns()-cb,'diagnostics':diagnostics(m,held_data)})
                    model=fit(data,schema,candidate,seed)
                    # Supported actions are calibrated runtime support, with observed support reported separately.
                    model.supported_lengths=tuple(config['lease_lengths'])
                    original_asset=output/(name+'.pkl'); model.save(original_asset)
                    asset=output/(name+'.json'); model.export(asset)
                    from ra.models import ModelBundle
                    import numpy as np
                    exported=ModelBundle.load(asset)
                    original_prediction=model.predict(data['batch']); exported_prediction=exported.predict(data['batch'])
                    for key in ('gain','body_seconds','body_q90'):
                        a,z=getattr(original_prediction,key),getattr(exported_prediction,key)
                        if a is not None: np.testing.assert_allclose(z,a,rtol=1e-12,atol=1e-12)
                    record.update(status='fitted',asset=str(asset),sha256=sha(asset),model_bytes=asset.stat().st_size,
                        counts=model.counts,training_diagnostics=diagnostics(model,data),
                        original_asset=str(original_asset),original_sha256=sha(original_asset),export_parity=True)
                except Exception as exc:
                    record['error']=f'{type(exc).__name__}: {exc}'
                record.update(fit_wall_ns=time.perf_counter_ns()-begin,fit_cpu_ns=time.process_time_ns()-cpu_begin)
                records.append(record); _atomic_json(output/(name+'.fit.json'),record,immutable=True)
        if not any(r['status']=='fitted' for r in records):
            _atomic_json(output/'failed-training.json', {'success':False,'candidates':records,
                'wall_ns':time.perf_counter_ns()-started,'cpu_ns':time.process_time_ns()-cpu},immutable=True)
            return {'success':False,'dry_run':False,'reason':'all fits failed','output':str(output)}
        # This boundary starts only after all fits and diagnostics finish.
        from ra.data import generate_workload
        generation=load_config((config_path.parent/options['generation_config']).resolve(),'generation')
        generated=generate_workload(generation,'validation',output/'validation-inputs')
        from ra.collect import selected_training_manifest
        manifest=selected_training_manifest(generated,options['validation_indices'])
        _atomic_json(output/'validation-inputs'/'selected-manifest.json',manifest,immutable=True)
        methods=[{'name':'B0','kind':'native','overrides':{}}, {'name':'B1-tuned','kind':'native','overrides':{}},
                 {'name':'B1-no-plunge','kind':'native','overrides':{'nodeselection/estimate/maxplungedepth':0}}]
        fallback_lengths=options.get('fallback_lengths',[options['fallback_length']])
        for r in records:
            if r['status']=='fitted':
                for length in fallback_lengths:
                    name=r['name'] if len(fallback_lengths)==1 else f"{r['name']}-fallback{length}"
                    methods.append(learned_method(r['asset'],schema_path,schema,name=name,
                        c_min=options['c_min'],fallback_length=length))
        methods.extend(options.get('validation_extra_methods',[]))
        run={k:v for k,v in config.items() if k not in ('training','collection')}
        run.update(input_manifests=[str(output/'validation-inputs'/'selected-manifest.json')],methods=methods,
                   solver_seeds=options['validation_solver_seeds'],budgets_ns=options['validation_budgets_ns'])
        _atomic_json(output/'validation-run.json',run,immutable=True)
        attempts=_run_schedule(output/'validation-run.json','validation',output/'validation',resume=False)
        utility={m['name']:[] for m in methods}; costs={m['name']:[] for m in methods}; failures=Counter()
        for a in attempts:
            utility[a.request.method].append(a.available.utility)
            costs[a.request.method].append({'attempt_id':a.attempt_id,'end_to_end_ns':a.resources['end_to_end_ns'],
                'model_loading_ns':a.resources.get('model_loading_ns'), 'peak_rss_bytes':a.resources.get('worker_peak_rss_bytes'),
                'model_bytes':a.resources.get('model_bytes'), 'overshoot_ns':a.overshoot_ns,
                'diagnostics':a.resources.get('bidder_diagnostics',[]),'status':str(a.status),
                'instance_hash':a.request.instance_hash,'budget_ns':a.request.budget_ns,
                'available_utility':a.available.utility,'primal_original':a.available.primal_original,
                'dual_original':a.available.dual_original})
            if str(a.status) not in ('complete','deadline','startup_timeout'): failures[a.request.method]+=1
        means={name:sum(values)/len(values) for name,values in utility.items()}
        budget_weights=dict(zip(options['validation_budgets_ns'],options.get('validation_budget_weights',
                                [1.]*len(options['validation_budgets_ns'])),strict=True))
        scores=validation_scores(attempts,budget_weights)
        eligible=[m for m in methods if m['kind']=='shared' and not failures[m['name']]]
        selected=max(eligible,key=lambda m:(scores[m['name']],-Path(m['allocator']['model_path']).stat().st_size)) if eligible else None
        import resource,sys
        card={**forecast,'dry_run':False,'success':selected is not None,'schema':asdict(schema),'schema_hash':schema.hash,
              'source_hash':code_hash,'environment_hash':environment_hash,'build_hash':build_hash,
              'config_hash':sha(output/'config.json'),'data_hash':sha(output/'data-inventory.json'),
              'correction_sha256':data['correction_sha256'],'candidates':records,
              'selected':None if selected is None else selected['name'],
              'selected_deployment':selected,'validation_budget_weights':budget_weights,'validation_weighted_scores':scores,
              'selection':'maximum equal-original predeclared-budget-weighted cold public validation utility; faults ineligible; smaller asset breaks ties',
              'validation_mean_utility':means,'validation_costs':costs,'validation_failures':dict(failures),
              'target_sensitivity':data['sensitivity'],'training_originals':originals,'supported_lengths':config['lease_lengths'],
              'targets':'receipt-endpoint gain; exact consumed dispatch-to-next-entry/safe-terminal seconds; duration lower bounds excluded',
              'preprocessing':'train only unweighted medians; any missing/value/reference-infinity mask excludes observation; all-missing median zero; mean/std after imputation; constant scale one; masks retained unscaled; identical ridge/boosted path',
              'weights':'equal total original weight separately for gain and eligible body; zero gains retained',
              'q90':'observed original-held-out coverage in curves; finite support, no calibration guarantee',
              'c_min':options['c_min'],'c_min_source':options['c_min_source'],
              'fallback_length':None if selected is None else selected['allocator']['fallback_length'],'wall_ns':time.perf_counter_ns()-started,
              'cpu_ns':time.process_time_ns()-cpu,'peak_rss_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
              'claim':'exploratory working bidder only; Task13 controls, Task14 gates and Task15 freeze pending'}
        _atomic_json(output/'model-card.json',card,immutable=True)
        return {'success':card['success'],'dry_run':False,'selected':card['selected'],'card':str(output/'model-card.json')}
