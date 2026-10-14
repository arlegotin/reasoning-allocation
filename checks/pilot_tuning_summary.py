"""Reconstruct native validation rankings over coordinator-validated originals.

Inputs are original pilot instances (no derivatives); their request instance hash
is the stable unit even when a failed worker cannot return template provenance.
"""
import json
import statistics
import sys
from pathlib import Path
from collections import defaultdict
from ra.runner import _read_attempt


def summarize_records(rows, *, expected_budgets=None):
    if not rows:
        raise ValueError('nonempty retained native validation records required')
    phases={r['request']['phase'] for r in rows}
    if len(phases)!=1 or not phases <= {'discovery','pilot','validation'}:
        raise ValueError('one public phase required')
    phase=next(iter(phases))
    if (not isinstance(expected_budgets,(list,tuple)) or not expected_budgets
            or any(type(b) is not int or b<=0 for b in expected_budgets)
            or len(set(expected_budgets))!=len(expected_budgets)):
        raise ValueError('explicit unique positive declared budget grid required')
    budgets=sorted(expected_budgets)
    cohorts=defaultdict(list)
    for row in rows:
        request=row['request']
        cohorts[request['method'],request['instance_hash'],request['solver_seed']].append(request['budget_ns'])
    for values in cohorts.values():
        if len(values)!=len(set(values)): raise ValueError('duplicate budget in paired cohort')
        if sorted(values)!=budgets: raise ValueError('incomplete budget cohort')
    support={method:{(original,seed) for m,original,seed in cohorts if m==method}
             for method,_,_ in cohorts}
    if any(value!=next(iter(support.values())) for value in support.values()):
        raise ValueError('incomplete matched method cohort')
    weights=[.25,.5,.25] if len(budgets)==3 else [1/len(budgets)]*len(budgets)
    by=defaultdict(list)
    for r in rows:
        by[r['request']['method']].append(r)
    result={}
    for method,records in by.items():
        scores=defaultdict(float)
        for r in records:
            weight=weights[budgets.index(r['request']['budget_ns'])]
            scores[(r['request']['instance_hash'],r['request']['solver_seed'])]+=weight*r['available']['utility']
        originals=defaultdict(list)
        for (original,seed),score in scores.items():
            originals[original].append(score)
        fs={k:statistics.mean(v) for k,v in originals.items()}
        result[method]={'mean_F':statistics.mean(fs.values()),'original_F':fs,'templates':len(fs),
            'attempts':len(records),'wall_s':sum(r['resources']['end_to_end_ns'] for r in records)/1e9,
            'statuses':dict(__import__('collections').Counter(r['status'] for r in records))}
    return {'scope':f'public {phase} ranking over coordinator-validated original instances; finite candidates, no protected/fitted result',
        'budgets_ns':budgets,'weights':weights,'ranking':sorted(result,key=lambda m:result[m]['mean_F'],reverse=True),'methods':result}


def main(root, expected_budgets):
    root=Path(root)
    rows=[]
    for p in sorted(root.rglob('attempt.json')):
        a,complete=_read_attempt(p.parent)
        assert complete
        rows.append(a)
    output=summarize_records(rows,expected_budgets=expected_budgets)
    (root/'tuning-summary.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({m:{k:v for k,v in output['methods'][m].items() if k!='original_F'} for m in output['ranking']},indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('--budgets-ns',type=int,nargs='+',required=True)
    args=parser.parse_args()
    main(args.root,args.budgets_ns)
