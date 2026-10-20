"""Observer-template setup repair for a separately bounded fixed-pose screen.

Only compiled observer code and its immutable AST proof are cached. Numerical
operands, force outputs, live dependency keys, mutable defaults/closures,
certificate content and witnesses are never cached. The frozen Stage229 scope
generator keeps its exact code and receives a fresh private globals dictionary
at every entry. This adapter is unpromoted and does not install transport code.
"""
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType
import hashlib, json, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage229_staging'))
import failure_reuse_v1 as original

SOURCE_SHA={
    ROOT/'stage229_staging/failure_reuse_v1.py':'d99bfc206725a040a8e2ae420ad7daade975908b7cce86e03357e663a38026c2',
    ROOT/'stage194_staging/semismooth_rejected_seed_v1.py':'e53da0067032db13de84297966db17c3e83bf041600d7fce22abc8fbf9dfa86f',
}

def need(condition,message):
    if not condition:raise RuntimeError(message)

def sources_unchanged():
    for path,expected in SOURCE_SHA.items():
        need(hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Frozen observer/force source changed: '+str(path))

def binding_snapshot():
    force=original.prior.solve;observer=original._observer_clone
    generator=original.scope.__wrapped__
    return dict(force=force,force_code=force.__code__,force_globals=force.__globals__,
        observer=observer,observer_code=observer.__code__,observer_globals=observer.__globals__,
        observed_seed=original._observed_seed,observed_seed_code=original._observed_seed.__code__,
        hooks=original._Hooks,generator=generator,generator_code=generator.__code__,
        generator_globals=generator.__globals__)

class TemplateCache:
    """One strongly retained compiled template; fresh per-scope execution state."""
    def __init__(self):
        sources_unchanged();self._origin=binding_snapshot();self._template=None;self.active_scopes=0
        self.stats=dict(observer_builds=0,template_hits=0,fresh_namespaces=0,source_checks=1)

    def check_snapshot(self,current):
        need(set(current)==set(self._origin),'Complete immutable identity boundary required')
        for key,wanted in self._origin.items():
            need(current[key] is wanted,'Original immutable observer identity changed: '+key)

    def current(self):
        self.check_snapshot(binding_snapshot());sources_unchanged();self.stats['source_checks']+=1

    def __call__(self,seed_producer):
        self.current()
        if self._template is None:
            function,proof=self._origin['observer'](seed_producer)
            need(function.__closure__ is None and function.__kwdefaults__ is None
                and function.__defaults__==(None,) and function.__annotations__=={},
                'Original observer has only the immutable None deadline default')
            need(proof['stripped_ast_exact'] and not proof['equations_changed'],
                'Original observer AST strips to the original force equations exactly')
            # The code object and JSON proof bytes are immutable and strongly
            # retained. No returned function/globals or seed callback is kept.
            proof_bytes=json.dumps(proof,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            self._template=(function.__code__,function.__name__,function.__defaults__,proof_bytes)
            self.stats['observer_builds']+=1
        else:
            code,name,defaults,proof_bytes=self._template
            # Read the current source function globals anew. Numerical scopes
            # can legitimately install new analytic/native callable bindings;
            # the original request() still snapshots all live mutable leaves.
            namespace={**self._origin['force'].__globals__,
                'fast':original.SimpleNamespace(solve=self._origin['observed_seed'](seed_producer)),
                '_memo_hooks':self._origin['hooks']()}
            function=FunctionType(code,namespace,name,defaults)
            namespace[name]=function  # Same self binding as original exec().
            proof=json.loads(proof_bytes)
            self.stats['template_hits']+=1
        self.stats['fresh_namespaces']+=1
        return function,proof

_CACHE=TemplateCache()

def cache_stats():
    return {**_CACHE.stats,'active_scopes':_CACHE.active_scopes,'template_ready':_CACHE._template is not None}

def reset_cache():
    """Explicit cold setup for the screen; never reset inside a live scope."""
    global _CACHE
    need(_CACHE.active_scopes==0,'Cannot reset a live observer scope')
    _CACHE.current()  # Reset cannot re-anchor changed source/function/code.
    _CACHE=TemplateCache()
    return cache_stats()

@contextmanager
def scope(runtime,enabled=False,stop_epoch=None,policy_binding=None,
          certificate_binding=None,route_records=None,reuse=True):
    """Fresh private copy of the EXACT original scope-generator code."""
    cache=_CACHE;cache.current()
    generator=cache._origin['generator']
    private={**generator.__globals__,'_observer_clone':cache}
    bound=FunctionType(generator.__code__,private,generator.__name__,generator.__defaults__,generator.__closure__)
    cache.active_scopes+=1
    try:
        with contextmanager(bound)(runtime,enabled,stop_epoch,policy_binding,certificate_binding,route_records,reuse) as report:
            yield report
    finally:cache.active_scopes-=1

def __getattr__(name):
    # Reuse existing guard/auditor APIs without copying the candidate or model.
    return getattr(original,name)

def controls():
    """Pure construction, identity and isolation tests: no force execution."""
    cache=TemplateCache();before=binding_snapshot();checks=[]
    def seed_a(*args):raise AssertionError('Pure control invoked a force producer')
    def seed_b(*args):raise AssertionError('Pure control invoked a force producer')
    a,pa=cache(seed_a);b,pb=cache(seed_b)
    need(a.__code__ is b.__code__ and a is not b,'Shared immutable code, distinct helper functions')
    need(a.__globals__ is not b.__globals__ and a.__globals__ is not before['force_globals'],
         'Fresh helper namespaces without model-global mutation')
    need(a.__globals__['fast'] is not b.__globals__['fast']
        and a.__globals__['_memo_hooks'] is not b.__globals__['_memo_hooks'],
         'Fresh seed wrappers and witness hooks')
    def seed_callback(helper):
        observed=helper.__globals__['fast'].solve
        return dict(zip(observed.__code__.co_freevars,observed.__closure__))['seed_producer'].cell_contents
    need(seed_callback(a) is seed_a and seed_callback(b) is seed_b,'Exact current seed producer isolation')
    need(pa==pb and pa['stripped_ast_exact'] and not pa['equations_changed'],'Unchanged original observer proof')
    a.__globals__['scope_isolation_probe']=object();pa['stripped_ast_exact']=False
    z,pz=cache(seed_b)
    need('scope_isolation_probe' not in z.__globals__ and pz==pb,'Returned namespace/proof mutation does not leak')
    need(z.__globals__['solve'] is z,'Original helper self binding')
    checks.extend(('shared_immutable_code','fresh_functions','fresh_globals','fresh_hooks',
        'fresh_seed_wrappers','exact_current_seed_producer','exact_original_ast_proof',
        'returned_namespace_mutation_isolated','returned_proof_mutation_isolated','helper_self_binding'))
    for key in before:
        changed={**before,key:object()}
        try:cache.check_snapshot(changed)
        except RuntimeError:checks.append('changed_'+key+'_rejected')
        else:raise AssertionError('Immutable binding mutation was accepted: '+key)
    try:cache.check_snapshot({k:v for k,v in before.items() if k!='force_code'})
    except RuntimeError:checks.append('missing_identity_field_rejected')
    else:raise AssertionError('Incomplete immutable identity snapshot accepted')
    need(all(binding_snapshot()[key] is value for key,value in before.items()),'Original functions/code/global identities untouched')
    need(cache.stats['observer_builds']==1 and cache.stats['template_hits']==2
        and cache.stats['fresh_namespaces']==3,'Exactly one construction, fresh later instances')
    checks.extend(('original_binding_identities_unchanged','one_build_two_hits'))
    # Disabled entry never reaches any model/solver dependency and therefore
    # supplies a pure restoration/reset guard check without a force call.
    global_before=cache_stats();template_before=_CACHE._template
    with scope(None,enabled=False):
        need(cache_stats()['active_scopes']==1,'Exact live context association')
        try:reset_cache()
        except RuntimeError:checks.append('reset_during_live_scope_rejected')
        else:raise AssertionError('Live cache reset accepted')
    need(cache_stats()['active_scopes']==0 and _CACHE._template is template_before,
         'Disabled scope retires without compiling or executing force code')
    need(cache_stats()['observer_builds']==global_before['observer_builds'],
         'Disabled scope does not change template admission')
    checks.append('disabled_scope_restores_without_force_call')
    return dict(passed=True,checks=checks,controls_checked=len(checks),cache_stats=dict(cache.stats),
        original_scope_generator_code_retained=True,original_force_equations_unchanged=True,
        fresh_mutable_dependency_and_evidence_guards_unchanged=True,
        descriptor_serialization_changed=False,numerical_calls=0,force_calls=0,optimizer_calls=0,new_trajectory_steps=0,
        production_authorized=False)
