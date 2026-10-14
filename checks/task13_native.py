"""Small prospective native time-block diagnostic, retaining both earlier grids."""
import datetime
import subprocess
from task13_controls import OUT, BUDGETS, base, read, write


def main():
    from ra.runner import run_schedule
    names = ('B0', 'B1-no-plunge', 'B1-bfs')
    methods = [m for m in read(OUT/'contenders.json') if m['name'] in names]
    context = {}
    for name, command in [('power', ['pmset', '-g', 'batt']),
                          ('thermal', ['pmset', '-g', 'therm']),
                          ('load', ['uptime'])]:
        result = subprocess.run(command, capture_output=True, text=True)
        context[name] = dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    write(OUT/'native-timing-protocol.json', dict(
        purpose='No-plunge main/capacity short-deadline incumbent sensitivity; one additional paired time block, not reselection',
        observations=dict(main_primal=1360, capacity_primal=2115, main_incumbent_receipt_ms=500.779,
                          capacity_last_incumbent_receipt_ms=526.267, deadline_ms=526.70724,
                          main_startup_ms=145.573, capacity_startup_ms=157.719957,
                          native_lps=[87,79], native_nodes=[1,1]),
        hypothesis='Cold startup and search progress timing cross an incumbent event; existing delivery delays ~2.3ms cannot alone explain the whole shift',
        methods=methods, originals=6, solver_seeds=[17], budgets_ns=BUDGETS,
        requests=54, repeats=1, stopping='One block, all outcomes retained; assess sensitivity, no robust native winner claim',
        limitations='No process isolation, thermal attribution or earlier power telemetry; deterministic seed repeat is not an independent original',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), context=context))
    for budget in BUDGETS:
        config=base()
        config.update(input_manifests=[str(OUT/'validation-inputs/selected-manifest.json')],
                      methods=methods,solver_seeds=[17],budgets_ns=[budget])
        path=OUT/f'native-timing-{budget}.json';write(path,config)
        rows=run_schedule(path,'validation',OUT/f'native-timing-{budget}',resume=False)
        print('native timing',budget,len(rows),{str(a.status) for a in rows},flush=True)


if __name__=='__main__':main()
