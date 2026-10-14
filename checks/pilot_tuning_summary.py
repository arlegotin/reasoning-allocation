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


def summarize_records(rows):
    if not rows:
        raise ValueError('nonempty retained native validation records required')
    budgets=sorted({r['request']['budget_ns'] for r in rows})
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
    return {'scope':'public validation ranking over coordinator-validated original instances; finite candidates, no protected/fitted result',
        'budgets_ns':budgets,'weights':weights,'ranking':sorted(result,key=lambda m:result[m]['mean_F'],reverse=True),'methods':result}


def main(root):
    root=Path(root)
    rows=[]
    for p in sorted(root.rglob('attempt.json')):
        a,complete=_read_attempt(p.parent)
        assert complete
        rows.append(a)
    output=summarize_records(rows)
    (root/'tuning-summary.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({m:{k:v for k,v in output['methods'][m].items() if k!='original_F'} for m in output['ranking']},indent=2))


if __name__=='__main__':
    main(sys.argv[1])
