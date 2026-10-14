"""Native-only pilot evidence summaries; decisions require recorded judgment.

Missing measurements remain null. Forecast ranges describe observations, never
probabilistic upper bounds. Primary admission remains serial regardless of RAM.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from collections.abc import Sequence
import math
from ra.types import Attempt


def summarize_headroom(attempts: Sequence[Attempt]) -> dict[str, object]:
    records=[]
    for a in attempts:
        r=a.resources
        records.append({'attempt_id':a.attempt_id,'template_id':a.template_id,'cell_id':a.cell_id,
            'family':(a.lineage or {}).get('cell',{}).get('family'),
            'phase':a.request.phase,'kind':a.request.method_config.get('kind'),
            'method':a.request.method,'model_hash':a.request.model_hash,'model_path':a.request.model_path,
            'status':str(a.status),'utility':a.available.utility,'assignment_available':a.available.assignment_available,
            'primal_original':a.available.primal_original,'dual_original':a.available.dual_original,
            'native_nodes':r.get('native_nodes'),'native_lps':r.get('native_lps'),
            'wall_ns':r.get('end_to_end_ns'),'peak_rss_bytes':r.get('worker_peak_rss_bytes'),
            'worker_cpu_ns':r.get('worker_cpu_ns'),'trace_bytes':r.get('trace_bytes'),
            'overshoot_ns':a.overshoot_ns,'censored':a.duration_censored,
            'worker_exclusive_ns':r.get('worker_exclusive_ns'),
            'budget_ns':a.request.budget_ns,'solver_seed':a.request.solver_seed,
            'instance_id':a.request.instance_hash,'source_hash':a.request.code_hash,
            'config_hash':a.request.config_hash,'environment_hash':a.request.environment_hash,
            'build_hash':a.request.build_hash,'quarantined':a.quarantined})
    paired=defaultdict(list)
    for row in records:
        paired[(row['instance_id'],row['solver_seed'],row['budget_ns'])].append(row)
    envelope=[]
    for (instance,seed,budget), rows in sorted(paired.items()):
        valid=[r for r in rows if not r['quarantined'] and r['status'] not in ('implementation_error','numerical_alarm')]
        baseline=[r['utility'] for r in valid if r['method']=='B0']
        best=max((r['utility'] for r in valid),default=None)
        envelope.append({'instance_id':instance,'solver_seed':seed,'budget_ns':budget,
            'methods':[r['method'] for r in rows],'best_utility':best,
            'gain_over_B0':best-baseline[0] if best is not None and len(baseline)==1 else None,
            'scope':'finite tested schedules only; failures remain in records'})
    measured=[r['native_nodes'] for r in records if r['native_nodes'] is not None]
    root_only=sum(n<=1 for n in measured)
    return {'schema_version':1,'records':records,'status_counts':dict(Counter(a.status for a in attempts)),
            'root_only_count':root_only,'missing_native_work_count':len(records)-len(measured),
            'interpretation':'proxy_insufficiency' if measured and root_only==len(measured) else 'requires_headroom_judgment',
            'h1_falsified':False,'finite_envelope':envelope,
            'envelope_scope':'finite-tested schedules; not a universal oracle'}


def recommend_population(discovery_summary: dict[str, object]) -> dict[str, object]:
    records=discovery_summary['records']
    if not records or any(r.get('phase') not in ('pilot','discovery','validation') or
        r.get('kind') not in ('native','shared') or r.get('model_hash') or r.get('model_path')
        for r in records):
        raise ValueError('population selection requires public native/fixed-control evidence only')
    return {'schema_version':1,'cell_ids':sorted({r['cell_id'] for r in records if r.get('cell_id')}),
            'requires_recorded_judgment':True,'automatic_outcome_filtering':False,
            'root_only_interpretation':discovery_summary['interpretation'],
            'decision':None,'reason':None,'weights':None}


def forecast(stage: str, observed_costs: Sequence[dict[str, object]], design: dict[str, object]) -> dict[str, object]:
    count=design['request_count']
    if type(count) is not int or count<0: raise ValueError('nonnegative request count required')
    wall=[c['wall_ns'] for c in observed_costs if c.get('wall_ns') is not None]
    rss=[c['peak_rss_bytes'] for c in observed_costs if c.get('peak_rss_bytes') is not None]
    safety=design.get('safety_factor',2.)
    if not math.isfinite(safety) or safety<=1: raise ValueError('memory safety factor must exceed one')
    memory_keys=('available_memory_bytes','reserve_bytes','coordinator_bytes')
    capacity=0
    if rss and max(rss)>0 and all(k in design for k in memory_keys):
        available=design['available_memory_bytes']-design['reserve_bytes']-design['coordinator_bytes']
        capacity=max(0,math.floor(available/(max(rss)*safety)))
    return {'schema_version':1,'stage':stage,'request_count':count,'observations':len(observed_costs),
        'admitted_workers':min(1,capacity) if design.get('timed',True) else capacity,
        'memory_basis':'observed maximum RSS with safety factor; not guaranteed future peak',
        'wall_ns_observed_range':[min(wall)*count,max(wall)*count] if wall else None,
        'missing_wall_count':len(observed_costs)-len(wall),
        'failed_count':sum(c.get('status') not in ('complete','deadline') for c in observed_costs),
        'censored_count':sum(bool(c.get('censored')) for c in observed_costs),
        'overshoot_ns_total':sum(c['overshoot_ns'] for c in observed_costs if c.get('overshoot_ns') is not None),
        'missing_overshoot_count':sum(c.get('overshoot_ns') is None for c in observed_costs),
        'peak_rss_bytes_observed':max(rss) if rss else None,'upper_bound_available':False,
        'uncertainty':'Failed, censored and overshooting attempts retained; unobserved scale/training costs unknown.',
        'design':design}
