"""Exact original numerical audit with explicit new fallback provenance.

Four routing-only sites change. No physical, clock, force, fixed-point,
clearance, rejection or horizon criterion changes. The new route must expose
the failed old reduced attempt plus the fully captured accepted new system.
"""
import hashlib,inspect,types
from pathlib import Path
import qualify_failure_codec_v1 as q
import sliding_projection_repair_v3 as repair

old=q.job.kernel.evaluate.__globals__['association']
require=old.require


def new_route(system):return system['health'].get('solver')==repair.NAME


def accepted_route(system,call,reduced):
    require(system['accepted'] is True and call['accepted'] is True,'successful recorded fallback')
    if not new_route(system):require(reduced['reduced_accepted'] is True,'successful original reduced fallback');return
    require(reduced['reduced_accepted'] is False and reduced.get('reduced_error') in repair.ERRORS,'new fallback exposes failed original reduced candidate')
    require(call.get('original_exception') in repair.ERRORS,'new fallback follows recorded original numerical failure')
    require(set(reduced)=={'reduced_accepted','reduced_error','wall_s'},'exact original failed reduced telemetry schema')


def input_route(system,call,reduced):
    require(call['dt_s']==system['dt_s'] and call['gaps_m']==system['gaps_m'],'original fallback input binding')
    if not new_route(system):require(call['dt_s']==reduced['dt_s'],'original reduced timestep binding')


def solver_route(system,reduced):
    h=system['health'];require(h['original_gaps_preserved'] is True,'original gaps required')
    if not new_route(system):require(h['solver']==reduced['solver']==old.producer.old.fast.old.NAME,'original qualified fallback');return
    require(h['contact_modes']==[2,2,2] and h['analytic_projection_jacobian'] is True,'new frozen algorithm identity')
    require(sorted(h['canonical_order'])==[0,1,2] and type(h['projection_seed_index']) is int and 0<=h['projection_seed_index']<57,'bounded canonical projection provenance')
    require(type(h['projection_nfev']) is int and 0<h['projection_nfev']<=57000,'bounded projection evaluations')


source=inspect.getsource(old.evaluate)
changes={
 "require(system['accepted'] is True and call['accepted'] is True and repair['reduced_accepted'] is True, 'successful recorded fallback')":"accepted_route(system,call,repair)",
 "require(call['dt_s'] == system['dt_s'] == repair['dt_s'] and call['gaps_m'] == system['gaps_m'], 'original fallback input binding')":"input_route(system,call,repair)",
 "require(system['health']['solver'] == repair['solver'] == producer.old.fast.old.NAME and system['health']['original_gaps_preserved'], 'original qualified fallback')":"solver_route(system,repair)",
 "if item['health']['solver'] == producer.old.fast.old.NAME:":"if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME):"}
for before,after in changes.items():
    if source.count(before)!=1:raise RuntimeError('routing source drift')
    source=source.replace(before,after)
namespace={**old.evaluate.__globals__,'accepted_route':accepted_route,'input_route':input_route,'solver_route':solver_route,'NEW_SOLVER_NAME':repair.NAME}
exec(compile(source,str(Path(__file__))+'::four_route_sites','exec'),namespace)
evaluate=namespace['evaluate']
STRUCTURAL_IDENTITY={'original_source_sha256':hashlib.sha256(inspect.getsource(old.evaluate).encode()).hexdigest(),
    'revised_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'routing_sites_changed':4,'physical_gate_changes':0,'numerical_limits_changed':0}

kernel_namespace={**q.job.kernel.evaluate.__globals__,'association':types.SimpleNamespace(evaluate=evaluate)}
kernel=types.FunctionType(q.job.kernel.evaluate.__code__,kernel_namespace,'evaluate',q.job.kernel.evaluate.__defaults__,q.job.kernel.evaluate.__closure__)
