"""Separate charged Task9 diagnostics; never a primary baseline worker.

Scalar native counters sample event boundaries without B0 frontier scans. The
instrumented callbacks and terminal samples are additional charged observation.
"""
import os,sys,time,hashlib
from pathlib import Path
os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
from ra.worker import Channel,execute_request
from ra.scip_backend import _ProgressEvents,ScipBackend,_contain_callback
from collections import Counter
samples=Counter();first_main=None;last_main=None;root_lps=None;hooks=[];native_final={}
original_event=_ProgressEvents.eventexec
@_contain_callback
def eventexec(self,event):
    global first_main,last_main,root_lps
    started=time.perf_counter_ns()
    original_event(self,event)
    # Solved-node events are valid solving-stage scalar observations.
    from pyscipopt import SCIP_EVENTTYPE
    if int(event.getType()) & int(SCIP_EVENTTYPE.NODESOLVED):
        depth=self.model.getDepth();frontier=self.model.getNNodesLeft()
        samples[frontier]+=1
        if depth>0:
            if first_main is None:first_main=started;root_lps=int(self.model.getNLPs())
            last_main=time.perf_counter_ns()
    hooks.append(time.perf_counter_ns()-started)
_ProgressEvents.eventexec=eventexec
original_optimize=ScipBackend.optimize
def optimize(self):
    original_optimize(self)
    native_final.update(lp_iterations=int(self.model.getNLPIterations()),
                        strong_branch_lp_iterations=int(self.model.getNStrongbranchLPIterations()),
                        maximum_depth=int(self.model.getMaxTotalDepth()))
ScipBackend.optimize=optimize
original_send=Channel.send

def send(self,packet):
    if packet['kind']=='terminal':
        t=packet['timestamps'];start=t.get('solve_start_ns');end=t.get('solve_end_ns')
        packet['resources']['pilot_profile']={
            'scope':'separate charged diagnostic; root interval ends at first completed nonroot node and overestimates true root work',
            'first_main_completion_ns':first_main,'last_main_completion_ns':last_main,
            'root_and_first_main_ns':(first_main or end)-start if start is not None and end is not None else None,
            'lps_at_first_main_completion':root_lps,
            'frontier_histogram':dict(samples),'profile_event_calls':len(hooks),
            'nested_observation_ns':sum(hooks),
            'native_final':native_final,
            'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    original_send(self,packet)
Channel.send=send
raise SystemExit(execute_request(Path(sys.argv[1])))
