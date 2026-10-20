"""Routing-only qualification for original-law same-system seeded fallback."""
from pathlib import Path
import hashlib,types
import numpy as np
import audit_projection_routes_v2 as prior
import semismooth_rejected_seed_v1 as repair
q=prior.prior.q;require=prior.prior.require

def accepted(system,call,reduced):
    if system['health'].get('solver')!=repair.NAME:return prior.prior.accepted_route(system,call,reduced)
    require(system['accepted'] is True and call['accepted'] is True,'accepted same-system seeded fallback')
    require(reduced['reduced_accepted'] is False and reduced.get('reduced_error') in repair.ERRORS,'same-system seed follows failed original reduced solve')
    require(call.get('original_exception') in repair.ERRORS,'same-system seed follows original primary failure')
    require(set(reduced)=={'reduced_accepted','reduced_error','wall_s'},'exact reduced failure schema')

def inputs(system,call,reduced):
    if system['health'].get('solver')!=repair.NAME:return prior.prior.input_route(system,call,reduced)
    require(call['dt_s']==system['dt_s'] and call['gaps_m']==system['gaps_m'],'same-system original dt and gap binding')

def solver(system,reduced):
    if system['health'].get('solver')!=repair.NAME:return prior.prior.solver_route(system,reduced)
    h=system['health'];require(h['original_gaps_preserved'] is True and h['analytic_complementarity_jacobian'] is True and h['same_system_seed'] is True,'same-system analytic method identity')
    require(sorted(h['canonical_order'])==[0,1,2],'canonical permutation')
    require(type(h['seed_candidate_count']) is int and 1<=h['seed_candidate_count']<=64,'bounded original candidate count')
    require(type(h['seed_index']) is int and 0<=h['seed_index']<min(8,h['seed_candidate_count']),'bounded seed search')
    require(type(h['source_candidate_index']) is int and 0<=h['source_candidate_index']<h['seed_candidate_count'],'source candidate index')
    require(type(h['semismooth_nfev']) is int and 0<h['semismooth_nfev']<=2000,'bounded analytic iterations')
    require(h['seed_solver'] in (q.job.fast.NAME,q.job.fast.old.NAME) and (h['seed_gate_error'] is None or h['seed_gate_error'] in repair.ERRORS),'qualified original seed producer')
    require(np.asarray(h['seed_reactions']).shape==(9,) and np.isfinite(h['seed_reactions']).all(),'finite complete same-system seed')

source=prior.source
old='if item[\'health\'][\'solver\'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME):'
new='if item[\'health\'][\'solver\'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME, SEMISMOOTH_NAME):'
require(source.count(old)==1,'one exact new solver routing site');source=source.replace(old,new)
namespace={**prior.namespace,'check_stage194_accepted_route':accepted,'input_route':inputs,'solver_route':solver,'SEMISMOOTH_NAME':repair.NAME}
exec(compile(source,str(Path(__file__))+'::routing_only','exec'),namespace)
evaluate=namespace['evaluate']
STRUCTURAL_IDENTITY={**prior.STRUCTURAL_IDENTITY,'same_system_solver_added':repair.NAME,'revised_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'physical_gate_changes':0,'numerical_limits_changed':0}
kns={**q.job.kernel.evaluate.__globals__,'association':types.SimpleNamespace(evaluate=evaluate)}
kernel=types.FunctionType(q.job.kernel.evaluate.__code__,kns,'evaluate',q.job.kernel.evaluate.__defaults__,q.job.kernel.evaluate.__closure__)
