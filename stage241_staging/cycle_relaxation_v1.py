"""Diagnostic-only exact two-cycle detection and half relaxation.

Changes only the nonterminal iterate assignment in original Stage42. The
original undamped convergence test, returned actual solve, contact solver,
80-evaluation ceiling and momentum gate remain intact. No transport entry.
"""
import ast,copy,hashlib,inspect
from contextlib import contextmanager
from types import FunctionType
import numpy as np
import replay_original_context_v1 as prior

original=prior.JOB.observer.backend.stage42.inertial_contact_step
SOURCE=inspect.getsource(original)
SOURCE_SHA=hashlib.sha256(SOURCE.encode()).hexdigest()
require=prior.require

class Relaxation:
    def __init__(self):
        self.outputs=[];self.active=False;self.records=[]
    def next(self,current,updated,index):
        require(index==len(self.records),'Sequential per-pose relaxation record')
        trigger=(len(self.outputs)>=3 and np.asarray(updated).tobytes()==self.outputs[-2].tobytes()
            and self.outputs[-1].tobytes()==self.outputs[-3].tobytes()
            and np.asarray(updated).tobytes()!=self.outputs[-1].tobytes())
        self.active=self.active or trigger
        result=(current+updated)*.5 if self.active else updated
        self.records.append(dict(inner_index=index,input_velocity=np.asarray(current).tolist(),
            map_output=np.asarray(updated).tolist(),cycle_detected=bool(trigger),relaxation_active=self.active,
            omega=.5 if self.active else 1.,next_iterate=np.asarray(result).tolist()))
        self.outputs.append(np.asarray(updated).copy())
        return result

def build(observed,relax):
    require(observed.__globals__.get('_observe_inner') is not None,'Original observation must already be active')
    tree=ast.parse(SOURCE);wrapped=0
    class Observe(ast.NodeTransformer):
        def visit_Call(self,node):
            nonlocal wrapped
            if isinstance(node.func,ast.Attribute) and node.func.attr=='_solve_prepared' and isinstance(node.func.value,ast.Name) and node.func.value.id=='stage41':
                wrapped+=1
                return ast.copy_location(ast.Call(func=ast.Name(id='_observe_inner',ctx=ast.Load()),
                    args=[node.func,ast.Name(id='iteration',ctx=ast.Load()),*node.args],keywords=node.keywords),node)
            return self.generic_visit(node)
    Observe().visit(tree);require(wrapped==1,'Same single original observed contact call')
    observed_sha=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()
    loops=[n for n in tree.body[0].body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='iteration']
    require(len(loops)==1,'Exact original outer loop')
    final=loops[0].body[-1]
    require(isinstance(final,ast.Assign) and ast.dump(final,include_attributes=False)==ast.dump(ast.parse('candidate = updated').body[0],include_attributes=False),
        'Only the nonterminal candidate assignment may change')
    loops[0].body[-1]=ast.copy_location(ast.parse('candidate = _relax_next(candidate, updated, iteration)').body[0],final)
    ast.fix_missing_locations(tree)
    namespace={**observed.__globals__,'_relax_next':relax.next}
    exec(compile(tree,__file__+'::cycle_half_relaxation','exec'),namespace)
    fn=namespace[original.__name__]
    require(fn.__defaults__==original.__defaults__,'Original tolerance and total outer ceiling unchanged')
    return fn,dict(original_source_sha256=SOURCE_SHA,original_observed_ast_sha256=observed_sha,
        stabilized_ast_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),
        observed_solver_calls=1,numerical_ast_edits=1,omega=.5,trigger='exact repeated two-cycle',
        original_undamped_stop_test_unchanged=True,original_momentum_gate_unchanged=True,total_map_cap=80)

@contextmanager
def scope(trace):
    backend=prior.JOB.observer.backend.stage42;previous=backend.inertial_contact_step
    relax=Relaxation();fn,proof=build(previous,relax)
    require(proof['original_observed_ast_sha256']==trace['structural_identity']['observed_ast_sha256'],
        'Exact original observed AST before the declared algorithm edit')
    trace['algorithm_trace']=dict(proof=proof,records=relax.records)
    backend.inertial_contact_step=fn
    try:yield
    finally:
        exact=backend.inertial_contact_step is fn
        backend.inertial_contact_step=previous
        require(exact,'No unexpected mutation of diagnostic solver binding')

class Stack(prior.adapter.ScopeStack):
    def __init__(self):super().__init__();self.trace=None;self.relax_entries=0
    def enter_context(self,context):
        result=super().enter_context(context);generator=getattr(context,'gen',None)
        if generator is not None and generator.gi_code is prior.JOB.observer.scope.__wrapped__.__code__:self.trace=result
        if generator is not None and generator.gi_code is prior.RUNTIME.repair_scope.__wrapped__.__code__:
            require(self.trace is not None and self.short_seed_entries==1 and self.relax_entries==0,'Original full context first')
            super().enter_context(scope(self.trace));self.relax_entries+=1
        return result

_capture=prior.frozen.clone(prior.adapter._capture,{**prior.adapter._capture.__globals__,'ExitStack':Stack})

def capture(row,plan):
    before=prior.JOB.observer.backend.stage42.inertial_contact_step
    saved=_capture(row,'candidate',plan)
    saved['leaf_binding_restored']=prior.JOB.observer.backend.stage42.inertial_contact_step is before
    return saved

def audit(saved,row):
    require(saved['scope_error'] is None and saved['scope_restored'] and saved['leaf_binding_restored']
        and saved['inputs_unchanged'] and saved['prior_recovery_restored'],'Complete original and prototype scope restoration')
    trace=saved['fixture']['contact_trial_trace'];algorithm=trace['algorithm_trace'];trial=trace['detailed_trials'][0]
    require(algorithm['proof']['original_source_sha256']==SOURCE_SHA and algorithm['proof']['numerical_ast_edits']==1,
        'Declared original-equation algorithm provenance')
    records=algorithm['records'];systems=trial['inner_systems'];accepted=trial['accepted']
    require(len(records)==len(systems)-(1 if accepted else 0),'Every nonterminal guess recorded exactly once')
    # Independent replay of the declared update from saved map outputs only.
    outputs=[];active=False
    def advance(current,updated,index):
        nonlocal active
        if accepted and index==len(systems)-1:return updated
        r=records[index]
        trigger=(len(outputs)>=3 and prior.bits(updated,outputs[-2]) and prior.bits(outputs[-1],outputs[-3]) and not prior.bits(updated,outputs[-1]))
        active=active or trigger;next_guess=(current+updated)*.5 if active else updated
        require(r['inner_index']==index and r['cycle_detected']==trigger and r['relaxation_active']==active
            and r['omega']==(.5 if active else 1.) and prior.bits(current,r['input_velocity'])
            and prior.bits(updated,r['map_output']) and prior.bits(next_guess,r['next_iterate']),
            'Independently reconstructed cycle detection and guess update')
        outputs.append(updated.copy());return next_guess
    # Original force, finite-Re equations, route coverage, true defect, cap and
    # accepted force/row association auditor, with only the explicit guess map
    # substituted. Original two-cycle classification is not assumed after a
    # prospective algorithm change; exhaustion still requires all80 evaluations.
    source=inspect.getsource(prior.frozen.fixed_point_audit);tree=ast.parse(source)
    edits=0
    class Update(ast.NodeTransformer):
        def visit_Assign(self,node):
            nonlocal edits
            if ast.dump(node,include_attributes=False)==ast.dump(ast.parse('current = updated').body[0],include_attributes=False):
                edits+=1;return ast.copy_location(ast.parse('current = _advance(current, updated, index)').body[0],node)
            return self.generic_visit(node)
        def visit_Expr(self,node):
            nonlocal edits
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='require' and any(isinstance(n,ast.Constant) and n.value=='Exact archived two-cycle from inner5 through80' for n in ast.walk(node)):
                edits+=1;return None
            return self.generic_visit(node)
    Update().visit(tree);require(edits==2,'Only declared guess update and obsolete archive-cycle classification change in audit')
    ast.fix_missing_locations(tree);ns={**prior.frozen.fixed_point_audit.__globals__,'_advance':advance}
    exec(compile(tree,__file__+'::independent_relaxed_recurrence_audit','exec'),ns)
    evidence=ns['fixed_point_audit'](saved['fixture'],not accepted)
    require(evidence['passed'] and len(systems)<=80,'Unchanged independent force and true-defect acceptance gates')
    if accepted:
        require(saved['error'] is None and prior.frozen.returned_control_matches(saved),'Actual solved output/reactions, never the mixed guess')
    else:require(saved['error']['repr']==prior.frozen.ERROR and saved['returned_answer'] is None,'Original exhaustion retained')
    exact_control=None
    if row['fixture_id']=='halved':
        actual=copy.deepcopy(saved['fixture']);actual['contact_trial_trace'].pop('algorithm_trace')
        exact_control=prior.frozen.same(actual,row['expected'])
        require(exact_control and not active and accepted,'Successful control scientific fields remain exact, including original proof')
    return dict(passed=True,outer_solution_accepted=accepted,relaxation_activated=active,
        map_evaluations=len(systems),original_undamped_stop_test_preserved=True,
        original_independent_force_and_recurrence_audit=evidence,half_step_control_scientifically_exact=exact_control,
        production_authorized=False,numerical_path_promoted=False)

def controls():
    r=Relaxation();a=np.ones(6);b=-a
    for i,u in enumerate([a,b,a,b]):r.next(np.zeros(6),u,i)
    require(r.active and prior.bits(r.records[-1]['next_iterate'],b*.5),'Exact two-cycle activation and half update')
    fresh=Relaxation();require(not fresh.active and fresh.records==[],'No history crosses pose boundaries')
    stable=Relaxation()
    for i in range(5):stable.next(np.zeros(6),a,i)
    require(not stable.active,'Repeated constant is not a two-cycle')
    tree=ast.parse(SOURCE)
    require(original.__defaults__[-2:]==(1e-10,80) and prior.JOB.observer.backend.stage42.CONTACT_ITERATION_CEILING==25000,
        'Original outer/inner numerical gates')
    require('_relax_next' not in SOURCE,'No frozen original source mutated')
    observed,identity=prior.JOB.observer.clone_step(original,lambda *args,**kwargs:None)
    constructed,proof=build(observed,Relaxation())
    require(proof['original_observed_ast_sha256']==identity['observed_ast_sha256']
        and constructed.__defaults__==original.__defaults__,'Actual observer/prototype construction without invocation')
    require(constructed.__globals__['stage41'] is original.__globals__['stage41']
        and constructed.__globals__['finite_re'] is original.__globals__['finite_re'],
        'Same original physical modules and solver dependencies')
    return dict(passed=True,pure_controls=7,contact_calls=0,outer_calls=0,source_sha256=SOURCE_SHA,
        construction_proof=proof)
