"""New qualified figures from saved inference; no numerical recomputation."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import time


def main():
    from ra.freeze import read,reference,check_reference
    from ra.report import plot_report,numerical_inference_digest
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];source=root/'results/confirmatory'
    for ref in read(source/'artifacts.json')['artifacts']:check_reference(ref)
    inference=read(source/'inference.json')
    assert numerical_inference_digest(inference)=='6339521bccab940fe0ec0546792a3c6012e65644fe7f63a5dde6418717b83d69'
    a.out.mkdir(parents=True,exist_ok=False);start,cpu=time.perf_counter_ns(),time.process_time_ns()
    for name in ('inference.json','curves.csv'):shutil.copy2(source/name,a.out/name)
    plot_report(a.out)
    receipt={'scope':'saved-inference presentation only; no reconstruction/bootstrap/solver/seed change',
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'source_inputs':[reference(source/name) for name in ('inference.json','curves.csv','artifacts.json')],
        'outputs':[reference(f) for f in sorted(a.out.iterdir())],
        'wall_ns':time.perf_counter_ns()-start,'cpu_ns':time.process_time_ns()-cpu,
        'cost_scope':'copy and plot after imports; final receipt write excluded',
        'standalone_annotation':'B6 UNSTABLE: frozen Monte Carlo endpoint diagnostic failed; no additional draws'}
    (a.out/'derivation.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
