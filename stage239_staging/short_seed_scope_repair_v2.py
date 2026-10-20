"""Unadmitted fixed-pose context repair; no dispatcher or authority creation.

The original Stage89 trajectory wrapper installs its short-seed solver after
the outer observation/LM scopes. The v1 fixed-pose replay omitted that binding.
This adapter restores that exact original context, never edits a frozen source,
and retains the complete scientific comparator. The failed v1 observation is
excluded from an archive-qualified attribution pair. Its original four-call
protocol remains incomplete. A future fresh admission must freeze its own
clock, budgets and explicit partial claim before calling capture_call.
"""
from contextlib import contextmanager, ExitStack
from pathlib import Path
from types import FunctionType
import copy, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage239_staging'),str(ROOT/'stage89_staging')]
import fixed_point_replay_v1 as frozen
import trajectory_short_pgs_seed_v1 as short
scalar_context=short.parent

FROZEN_SHA='ae507adc513c61bae904a3cffee6873e8ebb86e155d60dcbb2379f7d71d81d57'
ENTRY_COUNTS={'short_seed_scopes':0}
_ACTIVE=False

def require(value,message):frozen.require(value,message)

def source_checks():
    require(frozen.c.sha(frozen.__file__)==FROZEN_SHA,'Unchanged failed v1 source')
    plan=frozen.c.read(frozen.PLAN)
    path=str(Path(short.__file__).resolve())
    require(path in plan['source_files'] and frozen.c.sha(path)==plan['source_files'][path],
        'Same mandatory original Stage89 source, no new solver')
    scalar_path=str(Path(scalar_context.__file__).resolve())
    require(scalar_path in plan['source_files'] and frozen.c.sha(scalar_path)==plan['source_files'][scalar_path]
        and scalar_context.kernels is frozen.kernel.hot.scalar,
        'Same original nested Stage81 scalar context')
    require(short.PGS_SEED_SWEEPS==64 and short.stage50 is frozen.kernel.hot.s50
        and short.stage53 is frozen.kernel.s53 and short.portfolio is frozen.RUNTIME.probe.RECOVERY.portfolio
        and short._original_solve is frozen.kernel.ORIGINAL_ZERO,
        'Exact original Stage89 solver dependencies, seed cap and fallback')
    frozen.structural_controls()
    return dict(passed=True,original_short_seed_source_sha256=plan['source_files'][path],
        unchanged_source=True,original_short_seed_sweeps=64,force_calls=0,new_trajectory_steps=0)

@contextmanager
def short_seed_scope():
    """The exact Stage89 integrate() binding and original finally restoration."""
    global _ACTIVE
    require(not _ACTIVE,'Nonreentrant original trajectory binding')
    previous=short.stage53._solve
    original_scalar=(scalar_context.s50._project,scalar_context.s50._residual,scalar_context.s63._solve)
    require(previous is short._original_solve or
        (previous.__code__ is frozen.kernel._dispatch.__code__
         and previous.__globals__.get('_original_solver') is short._original_solve
         and previous.__globals__.get('_kind')=='zero'),
        'Only original or qualified live zero-LM binding may precede Stage89')
    _ACTIVE=True;short.stage53._solve=short.solve;ENTRY_COUNTS['short_seed_scopes']+=1
    # Exact nested Stage81 assignments from its original integrate() wrapper.
    scalar_context.s50._project=scalar_context.kernels.project
    scalar_context.s50._residual=scalar_context.kernels.residual
    scalar_context.s63._solve=scalar_context.kernels.sor_solve
    bound_scalar=(scalar_context.kernels.project,scalar_context.kernels.residual,scalar_context.kernels.sor_solve)
    exact=False
    try:
        yield
    finally:
        exact=short.stage53._solve is short.solve and all(a is b for a,b in zip(
            (scalar_context.s50._project,scalar_context.s50._residual,scalar_context.s63._solve),bound_scalar))
        scalar_context.s50._project,scalar_context.s50._residual,scalar_context.s63._solve=original_scalar
        short.stage53._solve=previous;_ACTIVE=False
        require(exact,'Original Stage89 binding was unexpectedly mutated within the pose')

class ScopeStack(ExitStack):
    """Insert only the missing original trajectory context after runtime repair."""
    def __init__(self):
        super().__init__();self.short_seed_entries=0
    def enter_context(self,context):
        result=super().enter_context(context)
        generator=getattr(context,'gen',None)
        if generator is not None and generator.gi_code is frozen.RUNTIME.repair_scope.__wrapped__.__code__:
            require(self.short_seed_entries==0,'Exactly one original runtime repair boundary')
            super().enter_context(short_seed_scope());self.short_seed_entries+=1
        return result

# Exact capture code, original scope objects and all14 positional arguments.
# The sole private global change inserts the missing trajectory context.
_capture=FunctionType(frozen.capture_call.__code__,
    {**frozen.capture_call.__globals__,'ExitStack':ScopeStack},frozen.capture_call.__name__,
    frozen.capture_call.__defaults__,frozen.capture_call.__closure__)

def capture_call(row,mode,plan):
    """Only an externally admitted caller may execute this nonadvancing call."""
    require(plan.get('short_seed_scope_repair_admitted') is True
        and plan.get('production_authorized') is False
        and plan.get('maximum_trajectory_steps')==plan.get('maximum_saved_transport_steps')==0,
        'Fresh explicit nonadvancing repair authority required; this source creates none')
    before=ENTRY_COUNTS['short_seed_scopes'];saved=_capture(row,mode,plan)
    saved['original_short_seed_scope_entries']=ENTRY_COUNTS['short_seed_scopes']-before
    saved['full_four_call_protocol_qualified']=False
    saved['original_failed_attempt_preserved']=True
    return saved

def validate_call(saved,row):
    require(saved['original_short_seed_scope_entries']==1
        and saved['full_four_call_protocol_qualified'] is False,
        'One restored original context; partial diagnosis cannot become full protocol')
    return frozen.validate_call(saved,row)

def controls():
    """Binding/isolation controls only; never call a contact or outer solver."""
    source=source_checks();original=short.stage53._solve
    frozen.kernel.validate_sources();frozen.kernel.build()  # AST/code metadata only; no callback or solve.
    seed_stats=short.stats();telemetry=frozen.kernel.telemetry();entries=ENTRY_COUNTS['short_seed_scopes']
    with short_seed_scope():
        require(short.stage53._solve is short.solve,'Exact original function installed')
        try:
            with short_seed_scope():pass
        except RuntimeError:pass
        else:raise AssertionError('Nested trajectory context admitted')
    require(short.stage53._solve is original and not _ACTIVE,'Normal scope restoration')
    try:
        with short_seed_scope():raise ValueError('pure_exception_control')
    except ValueError:pass
    require(short.stage53._solve is original and not _ACTIVE,'Exception scope restoration')
    # Actual qualified surrounding scopes; no invocation of installed solvers.
    with frozen.JOB.prior.p.hot.scope(),frozen.JOB.parent.fix.scope():
        with frozen.kernel.scope():
            qualified=short.stage53._solve
            with ScopeStack() as scopes:
                scopes.enter_context(frozen.RUNTIME.repair_scope())
                require(scopes.short_seed_entries==1 and short.stage53._solve is short.solve,
                    'Original trajectory context follows active observer/kernel runtime context')
            require(short.stage53._solve is qualified,'Qualified zero-LM binding restored before kernel exit')
    require(short.stage53._solve is original and not _ACTIVE and short.stats()==seed_stats,
        'No original short-seed solve occurred; complete surrounding restoration')
    now=frozen.kernel.telemetry()
    require(now['compiled_callbacks']==telemetry['compiled_callbacks'],
        'No residual/contact/outer calls in pure binding controls')
    require(_capture.__code__ is frozen.capture_call.__code__ and
        {k for k,v in _capture.__globals__.items() if v is not frozen.capture_call.__globals__[k]}=={'ExitStack'},
        'Only the private context insertion differs from exact original capture')
    # Proof that scientific fields still cannot be normalized away.
    a=dict(health=dict(pgs_seed_iterations=64,residual=1e-10,reactions=[1.]),velocity=[1.])
    for key,value in [('pgs_seed_iterations',25000),('residual',1e-9),('reactions',[2.])]:
        bad=copy.deepcopy(a);bad['health'][key]=value
        require(not frozen.same(a,bad),'No scientific exclusions in repaired comparator')
    require(not frozen.same(a,{**a,'velocity':[2.]}),'Actual output cannot be excluded')
    return dict(passed=True,source=source,pure_binding_controls=12,
        short_seed_scope_entries=ENTRY_COUNTS['short_seed_scopes']-entries,
        force_calls=0,root_calls=0,outer_calls=0,new_trajectory_steps=0,
        original_and_qualified_bindings_restored=True,full_four_call_protocol_qualified=False,
        fresh_authorization_created=False,production_authorized=False,
        claim='Unadmitted scope repair only; past window closed and failed v1 retained.')

if __name__=='__main__':
    require(sys.argv[1:]==['controls'],'This future-gate source has no run, launch or prepare entry point')
    print(controls())
