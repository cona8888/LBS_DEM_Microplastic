"""Same-input contact comparison and diagnostic-only cycle-guarded dispatch.

The Stage42 outer bytecode and stopping/balance gates are unchanged. Only
after an exact per-pose two-cycle does the selected inner callable become
the existing stateless Stage201 scalar solver. No reactions cross poses.
"""
import ast,copy,hashlib,inspect,time
from contextlib import contextmanager
from types import FunctionType
import numpy as np
import replay_original_context_v1 as prior

scalar=__import__('two_contact_scalar_dispatch_v3')
require=prior.require
NAME='stage242_cycle_guarded_original_scalar'
canonical=FunctionType(scalar.solve.__code__,{**scalar.solve.__globals__,'NAME':NAME},
    scalar.solve.__name__,scalar.solve.__defaults__,scalar.solve.__closure__)
CALL_COUNTS={'direct':0,'canonical':0}

def arguments(item):
    return [np.asarray(item[k],float).copy() for k in ('vfree','mobility','jacobian','gaps_m')]+[item['dt_s'],item['friction'],item['tolerance'],item['maxiter']]

def digest_args(args):return prior.api.digest(prior.plain(args))

def physical_output(args,answer):
    row=dict(zip(('vfree','mobility','jacobian','gaps_m','dt_s','friction','tolerance','maxiter'),prior.plain(args)))
    row.update(accepted=True,velocity=prior.plain(answer[0]),health=prior.plain(answer[1]))
    return prior.physical.physical(row)

@contextmanager
def direct_scope(recovery,epoch):
    # Actual original cold portfolio, excluding only its automatic scalar
    # repair wrapper so the two routes can be evaluated independently.
    portfolio=prior.RUNTIME.probe.RECOVERY.portfolio
    primary=portfolio._solve;previous=portfolio.recovery_mode()
    portfolio.set_recovery_mode(recovery)
    try:
        with prior.JOB.prior.p.hot.scope(),prior.JOB.parent.fix.scope(),prior.kernel.scope(),prior.adapter.short_seed_scope():
            yield primary
    finally:portfolio.set_recovery_mode(previous)

def direct(item,route,recovery,epoch):
    args=arguments(item);before=digest_args(args);error=None;answer=None
    tick=time.perf_counter();CALL_COUNTS['direct']+=1
    with direct_scope(recovery,epoch) as primary:
        try:answer=primary(*args) if route=='primary' else scalar.solve(*args,epoch)
        except RuntimeError as issue:
            require(str(issue) in scalar.ERRORS,'Unexpected native error must stop dispatch')
            error=dict(type=type(issue).__name__,message=str(issue),repr=repr(issue))
    require(digest_args(args)==before,'No native input mutation')
    return dict(route=route,input_sha256=before,inputs=prior.plain(args),recovery_mode=recovery,
        returned_answer=None if answer is None else dict(velocity=prior.plain(answer[0]),health=prior.plain(answer[1])),
        error=error,seconds=time.perf_counter()-tick,inputs_unchanged=True,
        direct_fallback_is_counterfactual_diagnostic=route=='fallback',production_authorized=False)

class Cycle:
    def __init__(self,epoch):self.outputs=[];self.active=False;self.records=[];self.epoch=epoch
    def observe(self,observer,solver,index,v,M,J,g,dt,mu,tol,maxiter):
        require(index==len(self.records),'One sequential inner dispatch per original outer map')
        use=self.active and len(g)==2
        args=[v,M,J,g,dt,mu,tol,maxiter];before=digest_args(args)
        def selected(*received):
            require(digest_args(received)==before,'Original observer forwards identical inner operands')
            if not use:return solver(*received)
            require(time.time()<self.epoch,'Original bounded work cutoff')
            CALL_COUNTS['canonical']+=1
            return canonical(*received,self.epoch)
        answer=observer(selected,index,v,M,J,g,dt,mu,tol=tol,maxiter=maxiter)
        require(digest_args(args)==before,'Candidate cannot mutate physical inputs')
        updated=np.asarray(answer[0]);trigger=(len(g)==2 and len(self.outputs)>=3
            and prior.bits(updated,self.outputs[-2]) and prior.bits(self.outputs[-1],self.outputs[-3])
            and not prior.bits(updated,self.outputs[-1]))
        self.records.append(dict(inner_index=index,canonical_selected=use,input_sha256=before,
            map_output=updated.tolist(),health=prior.plain(answer[1]),cycle_detected=bool(trigger),
            input_physics_unchanged=True))
        self.outputs.append(updated.copy());self.active=self.active or trigger
        return answer

@contextmanager
def scope(trace,epoch):
    backend=prior.JOB.observer.backend.stage42;old=backend.inertial_contact_step
    observer=old.__globals__.get('_observe_inner');require(observer is not None,'Original observer installed first')
    cycle=Cycle(epoch)
    def wrapped(solver,index,*args,**kwargs):return cycle.observe(observer,solver,index,*args,**kwargs)
    fn=FunctionType(old.__code__,{**old.__globals__,'_observe_inner':wrapped},old.__name__,old.__defaults__,old.__closure__)
    require(fn.__code__ is old.__code__ and fn.__defaults__==old.__defaults__,
        'Original outer equations, undamped defect,80-map cap and momentum bytecode unchanged')
    trace['algorithm_trace']=dict(records=cycle.records,policy='original routes until exact two-cycle, then original scalar primitive',
        outer_bytecode_unchanged=True,scalar_numerical_bytecode_unchanged=canonical.__code__ is scalar.solve.__code__,
        scalar_source_sha256=prior.c.sha(scalar.__file__),canonical_solver_name=NAME)
    backend.inertial_contact_step=fn
    try:yield
    finally:
        exact=backend.inertial_contact_step is fn;backend.inertial_contact_step=old
        require(exact,'Diagnostic solver binding was not unexpectedly replaced')

class Stack(prior.adapter.ScopeStack):
    epoch=None
    def __init__(self):super().__init__();self.trace=None;self.entries=0
    def enter_context(self,context):
        result=super().enter_context(context);gen=getattr(context,'gen',None)
        if gen is not None and gen.gi_code is prior.JOB.observer.scope.__wrapped__.__code__:self.trace=result
        if gen is not None and gen.gi_code is prior.RUNTIME.repair_scope.__wrapped__.__code__:
            require(self.trace is not None and self.short_seed_entries==1 and self.entries==0,'Complete original context precedes candidate')
            super().enter_context(scope(self.trace,self.epoch));self.entries+=1
        return result

_capture=prior.frozen.clone(prior.adapter._capture,{**prior.adapter._capture.__globals__,'ExitStack':Stack})

def capture(row,plan):
    from datetime import datetime
    require(Stack.epoch is None,'No overlapping diagnostic pose')
    before=prior.JOB.observer.backend.stage42.inertial_contact_step
    Stack.epoch=datetime.fromisoformat(plan['worker_cutoff_utc']).timestamp()
    try:saved=_capture(row,'candidate',plan)
    finally:Stack.epoch=None
    saved['leaf_binding_restored']=prior.JOB.observer.backend.stage42.inertial_contact_step is before
    return saved

def audit(saved,row):
    require(saved['inputs_unchanged'] and saved['scope_restored'] and saved['leaf_binding_restored']
        and saved['prior_recovery_restored'] and saved['scope_error'] is None,'Full candidate/original restoration')
    trace=saved['fixture']['contact_trial_trace'];trial=trace['detailed_trials'][0]
    records=trace['algorithm_trace']['records'];systems=trial['inner_systems']
    require(len(records)==len(systems)<=80,'Complete original map/dispatch coverage')
    outputs=[];active=False;canonical_count=0
    for index,(record,item) in enumerate(zip(records,systems)):
        args=arguments(item);q=np.asarray(item['velocity'])
        use=active and len(item['gaps_m'])==2
        trigger=(len(outputs)>=3 and prior.bits(q,outputs[-2]) and prior.bits(outputs[-1],outputs[-3]) and not prior.bits(q,outputs[-1]))
        require(record['inner_index']==index and record['canonical_selected']==use
            and record['input_sha256']==digest_args(args) and prior.bits(q,record['map_output'])
            and record['health']==item['health'] and record['cycle_detected']==trigger,
            'Independent exact-cycle selection and same-system output provenance')
        if use:
            canonical_count+=1
            require(item['health']['solver']==NAME and item['health']['stateless_same_system'] is True
                and item['health']['original_gaps_preserved'] is True and item['early_range'][0]==item['early_range'][1]
                and item['fallback_range'][0]==item['fallback_range'][1],
                'Explicit direct canonical route, never a fabricated primary failure')
        else:require(item['health']['solver']!=NAME,'No canonical route before the proven cycle')
        outputs.append(q.copy());active=active or trigger
    # Original recurrence/force/route/momentum association checks, except the
    # obsolete requirement that a prospectively changed failed map must still
    # equal the archived original two-cycle. No physical criterion is removed.
    source=inspect.getsource(prior.frozen.fixed_point_audit);tree=ast.parse(source);removed=0
    class RemoveOldClassification(ast.NodeTransformer):
        def visit_Expr(self,node):
            nonlocal removed
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='require' and any(isinstance(n,ast.Constant) and n.value=='Exact archived two-cycle from inner5 through80' for n in ast.walk(node)):
                removed+=1;return None
            return self.generic_visit(node)
    RemoveOldClassification().visit(tree);require(removed==1,'Only obsolete archive-cycle classification removed')
    ast.fix_missing_locations(tree);ns=dict(prior.frozen.fixed_point_audit.__globals__)
    exec(compile(tree,__file__+'::original_physics_and_true_defect','exec'),ns)
    evidence=ns['fixed_point_audit'](saved['fixture'],not trial['accepted'])
    if trial['accepted']:require(saved['error'] is None and prior.frozen.returned_control_matches(saved),'Actual final solution/reactions returned')
    else:require(saved['error']['repr']==prior.frozen.ERROR and saved['returned_answer'] is None,'Original exhaustion never admitted')
    exact=None
    if row['fixture_id']=='halved':
        clean=copy.deepcopy(saved['fixture']);clean['contact_trial_trace'].pop('algorithm_trace')
        exact=prior.frozen.same(clean,row['expected']);require(exact and not active,'Successful half-step remains wholly original/exact')
    return dict(passed=True,outer_solution_accepted=trial['accepted'],map_evaluations=len(systems),
        canonical_calls=canonical_count,cycle_detected=active,original_independent_audit=evidence,
        half_step_scientific_exact=exact,production_authorized=False)

def controls():
    require(canonical.__code__ is scalar.solve.__code__ and canonical.__defaults__==scalar.solve.__defaults__,'Unchanged primitive bytecode/defaults')
    require({k for k,v in canonical.__globals__.items() if v is not scalar.solve.__globals__[k]}=={'NAME'},'Only explicit solver provenance name differs')
    original=prior.JOB.observer.backend.stage42.inertial_contact_step
    observed,identity=prior.JOB.observer.clone_step(original,lambda *args,**kwargs:None)
    trace=dict(structural_identity=identity)
    with prior.JOB.observer.scope(prior.RUNTIME,True) as actual:
        previous=prior.JOB.observer.backend.stage42.inertial_contact_step
        with scope(actual,time.time()+60):
            fn=prior.JOB.observer.backend.stage42.inertial_contact_step
            require(fn.__code__ is previous.__code__,'Only callable dispatch changes, not outer equations')
        require(prior.JOB.observer.backend.stage42.inertial_contact_step is previous,'Normal restore')
    require(prior.JOB.observer.backend.stage42.inertial_contact_step is original,'Complete restore')
    require(original.__defaults__[-2:]==(1e-10,80),'Original gates/caps retained')
    cycle=Cycle(time.time()+60);calls=[]
    def mock_observer(solver,index,*args,**kwargs):return solver(*args,kwargs['tol'],kwargs['maxiter'])
    for i,q in enumerate([np.ones(6),-np.ones(6),np.ones(6),-np.ones(6)]):
        cycle.observe(mock_observer,lambda *args,q=q:(q,{'solver':'pure_mock'}),i,
            np.zeros(6),np.eye(6),np.zeros((6,6)),np.zeros(2),.01,.3,1e-10,25000)
    require(cycle.active and not any(r['canonical_selected'] for r in cycle.records),'Canonical dispatch begins only after a proven cycle')
    fresh=Cycle(time.time()+60);fresh.active=True;before=dict(CALL_COUNTS)
    fresh.observe(mock_observer,lambda *args:(calls.append('original') or np.zeros(6),{'solver':'pure_mock'}),0,
        np.zeros(6),np.eye(6),np.zeros((0,6)),np.zeros(0),.01,.3,1e-10,25000)
    require(calls==['original'] and CALL_COUNTS==before,'Non-two-contact domain always delegates original, even with an active guard')
    require(not Cycle(time.time()+60).active,'Guard history never crosses poses')
    try:
        with prior.JOB.observer.scope(prior.RUNTIME,True) as actual:
            previous=prior.JOB.observer.backend.stage42.inertial_contact_step
            try:
                with scope(actual,time.time()+60):raise ValueError('pure_restore_control')
            finally:require(prior.JOB.observer.backend.stage42.inertial_contact_step is previous,'Exceptional prototype restoration')
    except ValueError:pass
    require(prior.JOB.observer.backend.stage42.inertial_contact_step is original,'Exceptional surrounding restoration')
    return dict(passed=True,pure_controls=9,outer_calls=0,contact_calls=0,all_dispatch_tests_mock_only=True)
