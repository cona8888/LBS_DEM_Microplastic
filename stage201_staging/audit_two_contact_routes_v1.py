"""New solver identity only; retain every frozen physical association gate."""
from pathlib import Path
import hashlib, types
import numpy as np
import two_contact_scalar_repair_v1 as repair
import audit_early_semismooth_v1 as prior

require=prior.require


def accepted(system,call,reduced):
    if system['health'].get('solver')!=repair.NAME:return prior.prior.accepted(system,call,reduced)
    require(system['accepted'] is True and call['accepted'] is True,'accepted two-contact fallback')
    require(reduced['reduced_accepted'] is False and reduced.get('reduced_error') in repair.ERRORS,'two-contact fallback exposes original reduced failure')
    require(call.get('original_exception') in repair.ERRORS,'two-contact fallback follows original primary failure')
    require(set(reduced)=={'reduced_accepted','reduced_error','wall_s'},'exact original reduced failure schema')


def inputs(system,call,reduced):
    if system['health'].get('solver')!=repair.NAME:return prior.prior.inputs(system,call,reduced)
    require(call['dt_s']==system['dt_s'] and call['gaps_m']==system['gaps_m'],'two-contact original timestep/gap binding')


def solver(system,reduced):
    if system['health'].get('solver')!=repair.NAME:return prior.prior.solver(system,reduced)
    h=system['health']
    require(len(system['gaps_m'])==2 and np.asarray(system['jacobian']).shape==(6,6),'explicit two-contact domain')
    require(h['original_gaps_preserved'] is True and h['stateless_same_system'] is True,'original same-system gaps')
    require(h['contact_modes'] in ([1,2],[2,1]),'one-stick/one-slide identity')
    require(type(h['scalar_mode_seed']) is int and 0<=h['scalar_mode_seed']<16,'bounded scalar seed')
    require(np.isfinite(h['scalar_coordinate']),'finite scalar coordinate')


source=prior.source
before="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME):"
after="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME, TWO_CONTACT_NAME):"
require(source.count(before)==1,'exactly one explicit solver route addition');source=source.replace(before,after)
namespace={**prior.ns,'check_stage194_accepted_route':accepted,'input_route':inputs,'solver_route':solver,'TWO_CONTACT_NAME':repair.NAME}
exec(compile(source,str(Path(__file__))+'::route_identity_only','exec'),namespace)
evaluate=namespace['evaluate']
STRUCTURAL_IDENTITY={**prior.STRUCTURAL_IDENTITY,'two_contact_solver_added':repair.NAME,'revised_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'physical_gate_changes':0,'numerical_limits_changed':0}
kns={**prior.q.job.kernel.evaluate.__globals__,'association':types.SimpleNamespace(evaluate=evaluate)}
kernel=types.FunctionType(prior.q.job.kernel.evaluate.__code__,kns,'evaluate',prior.q.job.kernel.evaluate.__defaults__,prior.q.job.kernel.evaluate.__closure__)
