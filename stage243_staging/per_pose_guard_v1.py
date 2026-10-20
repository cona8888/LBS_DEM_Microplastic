"""Diagnostic transport adapter for the passing Stage242 numerical policy.

Reuse the exact tested Cycle and scalar primitive. Create a fresh guard on
EVERY original outer call; no guard/reaction state is carried between poses.
"""
from contextlib import contextmanager
from types import FunctionType
import time
import numpy as np
import contact_consistency_v1 as core
prior=core.prior;require=core.require

@contextmanager
def scope(trace,epoch):
    backend=prior.JOB.observer.backend.stage42;old=backend.inertial_contact_step
    observer=old.__globals__.get('_observe_inner');require(observer is not None,'Original observer must precede per-pose guard')
    journal=[];trace['cycle_guard_trials']=journal;cycle=None
    def wrapped(solver,index,*args,**kwargs):
        nonlocal cycle
        if index==0:
            cycle=core.Cycle(epoch)
            journal.append(dict(trial_index=len(trace['trial_inner_counts']),records=cycle.records))
        require(cycle is not None,'Fresh pose initializer must precede every inner call')
        return cycle.observe(observer,solver,index,*args,**kwargs)
    fn=FunctionType(old.__code__,{**old.__globals__,'_observe_inner':wrapped},old.__name__,old.__defaults__,old.__closure__)
    require(fn.__code__ is old.__code__ and fn.__defaults__==old.__defaults__,'Unchanged original outer numerical bytecode')
    backend.inertial_contact_step=fn
    try:yield
    finally:
        exact=backend.inertial_contact_step is fn;backend.inertial_contact_step=old
        require(exact,'Per-pose solver binding unexpectedly changed')

def audit(record):
    trace=record['contact_trial_trace'];journal=trace['cycle_guard_trials'];counts=trace['trial_inner_counts']
    require(len(journal)==len(counts),'One fresh guard per complete original outer trial')
    detailed={t['trial_index']:t for t in trace['detailed_trials']};canonical_calls=activated=0;proved=set()
    for index,entry in enumerate(journal):
        rows=entry['records'];require(entry['trial_index']==index and len(rows)==counts[index],'Complete per-pose map coverage')
        outputs=[];active=False
        for inner,r in enumerate(rows):
            require(r['inner_index']==inner,'No guard history crossed a pose or restart')
            q=np.asarray(r['map_output']);trigger=(len(outputs)>=3 and prior.bits(q,outputs[-2])
                and prior.bits(outputs[-1],outputs[-3]) and not prior.bits(q,outputs[-1]))
            # All production-target inputs are fibres; the explicit g==2 guard
            # is additionally checked against actual detailed canonical systems.
            if r['canonical_selected']:
                require(active and index in detailed,'Canonical route needs saved exact-cycle antecedents')
                item=detailed[index]['inner_systems'][inner]
                require(len(item['gaps_m'])==2 and item['health']['solver']==core.NAME
                    and item['health']['stateless_same_system'] and item['health']['original_gaps_preserved']
                    and item['health']==r['health'] and prior.bits(item['velocity'],q)
                    and r['input_sha256']==core.digest_args(core.arguments(item))
                    and item['early_range'][0]==item['early_range'][1] and item['fallback_range'][0]==item['fallback_range'][1],
                    'Explicit original scalar primitive at identical saved inputs; no false failure provenance')
                prior.physical.physical(item);canonical_calls+=1;proved.add((index,inner))
            elif index in detailed:
                item=detailed[index]['inner_systems'][inner]
                require(not(active and len(item['gaps_m'])==2) and item['health']['solver']!=core.NAME,
                    'No omitted or premature canonical dispatch')
            if r['cycle_detected']:
                require(trigger and index in detailed and len(detailed[index]['inner_systems'][inner]['gaps_m'])==2,
                    'Exact repeated two-cycle proved from observed physical map outputs')
                if not active:activated+=1
            active=active or r['cycle_detected'];outputs.append(q.copy())
    observed={(i,k) for i,t in detailed.items() for k,item in enumerate(t['inner_systems']) if item['health']['solver']==core.NAME}
    require(proved==observed,'Every canonical force solution has exact-cycle and same-system provenance')
    return dict(passed=True,outer_trials=len(journal),activated_poses=activated,canonical_calls=canonical_calls,
        original_independent_force_gates_unchanged=True,no_cross_pose_guard_state=True)

def controls():
    backend=prior.JOB.observer.backend.stage42;original=backend.inertial_contact_step
    observed,identity=prior.JOB.observer.clone_step(original,lambda *args,**kwargs:None)
    # Two mocked outer calls each start at index0. This catches an accidental
    # segment-wide history, without evaluating a contact/outer physical solve.
    calls=[]
    def mock_observer(solver,index,*args,**kwargs):return solver(*args,kwargs['tol'],kwargs['maxiter'])
    observed=FunctionType(observed.__code__,{**observed.__globals__,'_observe_inner':mock_observer},observed.__name__,observed.__defaults__,observed.__closure__)
    backend.inertial_contact_step=observed
    trace=dict(trial_inner_counts=[],detailed_trials=[],structural_identity=identity)
    try:
        with scope(trace,time.time()+60):
            callback=backend.inertial_contact_step.__globals__['_observe_inner']
            for pose in range(2):
                callback(lambda *args:(calls.append(pose) or np.zeros(6),{'solver':'pure_mock'}),0,
                    np.zeros(6),np.eye(6),np.zeros((0,6)),np.zeros(0),.01,.3,tol=1e-10,maxiter=25000)
                trace['trial_inner_counts'].append(1)
        require(len(trace['cycle_guard_trials'])==2 and [e['trial_index'] for e in trace['cycle_guard_trials']]==[0,1],
            'Distinct guard history per original outer call')
        require(all(len(e['records'])==1 and not e['records'][0]['canonical_selected'] for e in trace['cycle_guard_trials']),
            'No canonical state leaked to the next pose')
    finally:backend.inertial_contact_step=original
    require(calls==[0,1] and backend.inertial_contact_step is original,'Complete mock/context restoration')
    return dict(passed=True,pure_controls=3,contact_calls=0,outer_calls=0,all_dispatches_mock_only=True)
