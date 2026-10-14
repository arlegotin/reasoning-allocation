"""Append-only audit snapshots; controller reruns after final review closure.

Copy all SDD evidence and historical progress before cleanup. Each new generation
has a complete inventory; its receipt is outside the tree it hashes (no loop).
No raw data, models, wheels or historical frozen bytes are deleted or rewritten.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def archive(source,out,*,phase):
    source,out=Path(source).resolve(),Path(out).resolve()
    if out==source or out.is_relative_to(source):raise ValueError('archive destination must be outside source')
    out.mkdir(parents=True,exist_ok=False)
    shutil.copytree(source,out/'sdd')
    for name in ('PROGRESS.md','README.md','DECISIONS.md'):
        if (ROOT/name).exists(): shutil.copy2(ROOT/name,out/name)
    entries=[{'path':str(p.relative_to(out)),'sha256':digest(p),'bytes':p.stat().st_size}
        for p in sorted(out.rglob('*')) if p.is_file()]
    ledger=out/'sdd/progress.md'
    rulings=[line for line in ledger.read_text().splitlines() if 'Ruling:' in line] if ledger.exists() else []
    receipt={'schema_version':1,'phase':phase,'source':str(source),'archive':str(out),
        'source_restore_mapping':{'from':str(out/'sdd'),'to':str(source),'mode':'restore exact original bytes at original absolute paths; do not rewrite frozen references'},
        'files':entries,'rulings_in_order':rulings,'ruling_count':len(rulings),
        'closure':'pending controller Task20 review, final broad review, optional one fix wave and scoped rereview; refresh after closure' if phase=='pre-final' else 'controller-specified closure snapshot; review outcomes are in archived ledger'}
    # Receipt is a sibling, never part of the hashed archive it describes.
    receipt_path=out.with_name(out.name+'-receipt.json')
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt_path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'.superpowers/sdd/2026-10-13-reasoning-allocation')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--phase',choices=['pre-final','final'],required=True)
    a=p.parse_args();receipt=archive(a.source,a.out,phase=a.phase)
    print(receipt)


if __name__=='__main__':main()
