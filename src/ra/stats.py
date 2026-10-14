"""Public-only crossed planning with explicit non-identifiability and cost tails.

Timing/solver repeats are paired within templates. Native rows have one shared
fit identity. No normal-theory power is inferred from seed aliases or singleton
strata. The bounded sensitivity is conservative, conditional on the frozen fit.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from collections.abc import Sequence
import math
import numpy as np
from ra.metrics import log_budget_weights


def calibrate_design(pilot_summary: Sequence[dict[str, object]], design: dict[str, object]) -> dict[str, object]:
    d = design
    required = {'deadlines','cells','methods','native_methods','fit_ids','contrasts',
                'sample_per_cell','timing_repeats','bootstrap_repetitions','seed','alpha','useful_precision'}
    if not required <= d.keys(): raise ValueError('incomplete planning design')
    weights = log_budget_weights(d['deadlines'])
    cells, methods, native, fits = dict(sorted(d['cells'].items())), d['methods'], d['native_methods'], d['fit_ids']
    if (not cells or any(not isinstance(k,str) or not k or not math.isfinite(v) or v<=0 for k,v in cells.items())
            or not math.isclose(sum(cells.values()),1) or not methods or len(set(methods))!=len(methods)
            or not set(native)<=set(methods) or not fits or len(set(fits))!=len(fits) or 'shared' in fits
            or d['alpha']!=.05 or not d['contrasts'] or len({tuple(c) for c in d['contrasts']})!=len(d['contrasts'])
            or any(len(c)!=2 or c[0]==c[1] or not set(c)<=set(methods) for c in d['contrasts'])
            or any(type(d[k]) is not int or d[k]<1 for k in ('sample_per_cell','timing_repeats','bootstrap_repetitions'))
            or not math.isfinite(d['useful_precision']) or d['useful_precision']<=0):
        raise ValueError('invalid planning dimensions/contrasts')
    if not pilot_summary: raise ValueError('public pilot observations required')
    table, strata, repeats = {}, {}, set()
    for r in pilot_summary:
        if not isinstance(r,dict) or r.get('phase') not in ('discovery','pilot','validation'):
            raise ValueError('planning cannot read protected outcomes')
        try:
            t,c,m,f,b,p,u = (r[k] for k in ('template_id','cell_id','method','fit_id','budget_ns','repeat','utility'))
            key=(t,m,f,b,p)
            valid=(isinstance(t,str) and bool(t) and c in cells and m in methods and b in d['deadlines']
                   and type(p) is int and p>=0 and math.isfinite(u) and 0<=u<=1
                   and f in (['shared'] if m in native else fits))
            if not valid or key in table or t in strata and strata[t]!=c: raise ValueError('invalid or duplicate paired row')
        except (KeyError,TypeError) as exc: raise ValueError('malformed pilot row') from exc
        table[key]=r; strata[t]=c; repeats.add(p)
    groups={c: sorted(t for t in strata if strata[t]==c) for c in cells}
    if any(not ts for ts in groups.values()): raise ValueError('missing pilot cell')
    ts=sorted(strata); ps=sorted(repeats)
    # Template x complete fit x paired repeat x method, integrated over budgets.
    values=np.empty((len(ts),len(fits),len(ps),len(methods)))
    for ti,t in enumerate(ts):
        for fi,f in enumerate(fits):
            for pi,p in enumerate(ps):
                for mi,m in enumerate(methods):
                    try:
                        values[ti,fi,pi,mi]=sum(w*table[t,m,'shared' if m in native else f,b,p]['utility']
                                              for w,b in zip(weights,d['deadlines']))
                    except KeyError as exc: raise ValueError('incomplete paired template/fit/repeat/budget cohort') from exc
    contrasts=np.array([values[:,:,:,methods.index(a)]-values[:,:,:,methods.index(b)] for a,b in d['contrasts']])
    indices={c: np.array([ts.index(t) for t in group]) for c,group in groups.items()}
    estimate=sum(cells[c]*contrasts[:,idx].mean(axis=(1,2,3)) for c,idx in indices.items())
    rng=np.random.default_rng(d['seed']); nboot=d['bootstrap_repetitions']; nc=len(d['contrasts'])
    conditional=np.zeros((nboot,nc)); crossed=np.zeros_like(conditional); planning=np.zeros_like(conditional)
    # Fit resampling is globally crossed, not a different fit draw per template.
    fit_draws=rng.integers(0,len(fits),(nboot,len(fits)))
    for c,idx in indices.items():
        for n,target in ((len(idx),'observed'),(d['sample_per_cell'],'planned')):
            picked=rng.choice(idx,size=(nboot,n),replace=True)
            # Average timing repeats before cluster resampling; paired methods and budgets remain intact.
            sampled=contrasts.mean(axis=3)[:,picked,:] # contrast, bootstrap, template, fit
            cond=sampled.mean(axis=(2,3)).T
            cross=np.take_along_axis(sampled,fit_draws[None,:,None,:],axis=3).mean(axis=(2,3)).T
            if target=='observed': conditional+=cells[c]*cond; crossed+=cells[c]*cross
            else: planning+=cells[c]*cross
    q=d['alpha']/(2*nc)
    identified=all(len(idx)>1 for idx in indices.values())
    result=[]
    for k,pair in enumerate(d['contrasts']):
        ci=np.quantile(conditional[:,k],[q,1-q]).tolist()
        ai=np.quantile(crossed[:,k],[q,1-q]).tolist() if len(fits)>1 else None
        batches=[np.quantile(block[:,k],[q,1-q]) for block in np.array_split(crossed,4)]
        spread=np.ptp(batches,axis=0).tolist()
        result.append(dict(method=pair[0],baseline=pair[1],estimate=float(estimate[k]),
            conditional_interval=ci,population_interval=ci if identified else None,across_fit_interval=ai,
            ordinary_interval=np.quantile(conditional[:,k],[.025,.975]).tolist(),
            planned_interval_empirical=np.quantile(planning[:,k],[q,1-q]).tolist() if identified else None,
            quantile_batch_spread=spread,quantile_stable=max(spread)<=d['useful_precision']*.05,
            paired_template_sd_by_cell={c:float(np.std(contrasts[k,idx].mean(axis=(1,2)),ddof=1)) if len(idx)>1 else None for c,idx in indices.items()},
            timing_sd_mean=float(np.mean(np.std(contrasts[k],axis=2,ddof=1))) if len(ps)>1 else None,
            fit_sd_of_mean=float(np.std(sum(cells[c]*contrasts[k,idx].mean(axis=(0,2)) for c,idx in indices.items()),ddof=1)) if len(fits)>1 else None))
    physical_per_block=len(native)+(len(methods)-len(native))*len(fits)
    nrequests=len(cells)*d['sample_per_cell']*d['timing_repeats']*len(weights)*physical_per_block
    costs=list(table.values())
    def measured(key): return [r[key] for r in costs if r.get(key) is not None]
    walls,peaks,storage=measured('wall_ns'),measured('peak_rss_bytes'),measured('trace_bytes')
    # Budget and method/fit stratification: sum the observed maximum in each planned slot.
    wall_forecast=storage_forecast=0
    for c in cells:
        for m in methods:
            for f in (['shared'] if m in native else fits):
                for b in d['deadlines']:
                    slot=[r for r in costs if r['cell_id']==c and r['method']==m and r['fit_id']==f and r['budget_ns']==b]
                    repetitions=d['sample_per_cell']*d['timing_repeats']
                    wall_forecast+=max((r['wall_ns'] for r in slot if r.get('wall_ns') is not None),default=b)*repetitions
                    storage_forecast+=max((r['trace_bytes'] for r in slot if r.get('trace_bytes') is not None),default=0)*repetitions
    half=math.sqrt(2*math.log(2*nc/d['alpha'])*sum(w*w/d['sample_per_cell'] for w in cells.values()))
    return dict(schema_version=1,scope='public pilot planning; no protected result',design=d,weights=weights,
        independent_templates=len(ts),templates_per_cell={c:len(idx) for c,idx in indices.items()},
        independent_fit_runs=len(fits),timing_repeats=len(ps),physical_observations=len(costs),contrasts=result,
        B=nc,alpha=d['alpha'],conservative_half_width=min(2.,half),
        conservative_basis='Hoeffding bounded paired differences [-1,1], independent templates, conditional on fixed fit; not empirical power',
        uncertainty=dict(within_cell_variance_identified=identified,across_fit_reliable=False,
            fit_scope='conditional on frozen fitted assets and training data; training-procedure variability unidentifiable' if len(fits)==1 else 'few complete crossed fits; fit distribution poorly identified',
            extrapolation='empirical resampling cannot identify unobserved tails; conditional pilot sensitivity, not guaranteed power'),
        resources=dict(request_count=nrequests,wall_ns_observed_max_stratified=wall_forecast,
            wall_ns_with_reserve=math.ceil(wall_forecast*1.5),reserve_factor=1.5,
            measured_wall_ns_total=sum(walls),peak_rss_bytes_observed=max(peaks,default=None),
            storage_bytes_observed_total=sum(storage),storage_bytes_with_reserve=math.ceil(storage_forecast*1.5),
            overshoot_ns_total=sum(measured('overshoot_ns')),failed_count=sum(r.get('status') not in ('complete','deadline') for r in costs),
            censored_count=sum(bool(r.get('censored')) for r in costs),status_counts=dict(Counter(r.get('status') for r in costs)),
            missing={k:len(costs)-len(measured(k)) for k in ('wall_ns','peak_rss_bytes','trace_bytes','overshoot_ns')},
            unknown_components=['future thermal/background variation','future tails beyond observed cell/method/budget maxima','CPU publication tail'],
            admitted_workers=1,forecast_is_upper_bound=False))


def write_pilot_report(rows, design, out):
    """Exercise the analysis/report path on public data, always labelled dry."""
    from pathlib import Path
    result=calibrate_design(rows,design)
    lines=['# DISCOVERY/VALIDATION DRY REPORT','',
        'Public pilot only. This is not a confirmatory result.', '',
        f"Independent originals: {result['independent_templates']}; complete fit runs: {result['independent_fit_runs']}.",
        '', 'Conditional paired frontier contrasts (Bonferroni intervals):','']
    for r in result['contrasts']:
        lines.append(f"- {r['method']} minus {r['baseline']}: {r['estimate']:.8f}; {r['conditional_interval']}")
    lines += ['',result['uncertainty']['extrapolation'],result['uncertainty']['fit_scope'],
        '', 'Failures and censored costs remain in the design artifact; startup failures score zero.']
    Path(out).parent.mkdir(parents=True,exist_ok=True)
    Path(out).write_text('\n'.join(lines)+'\n')
    return {'success':True,'dry_run':True,'out':str(out),'scope':result['scope']}
