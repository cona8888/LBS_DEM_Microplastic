"""Explicit new-route provenance; original physical and clock gates unchanged."""
import copy,hashlib,types
import numpy as np
import audit_two_contact_polish_v4 as prior
import two_contact_cone_feasibility_v1 as candidate
require=prior.require

def old_system(system):
    result=copy.deepcopy(system)
    result['health']['solver']=system['health']['pre_retraction_solver']
    require(result['health']['solver'] in (candidate.prior.NAME,candidate.prior.prior.NAME),'qualified old route identity')
    return result

def accepted(system,call,reduced):
    if system['health'].get('solver')!=candidate.NAME:return prior.namespace['check_stage194_accepted_route'](system,call,reduced)
    return prior.namespace['check_stage194_accepted_route'](old_system(system),call,reduced)

def inputs(system,call,reduced):
    if system['health'].get('solver')!=candidate.NAME:return prior.namespace['input_route'](system,call,reduced)
    return prior.namespace['input_route'](old_system(system),call,reduced)

def solver(system,reduced):
    if system['health'].get('solver')!=candidate.NAME:return prior.namespace['solver_route'](system,reduced)
    prior.namespace['solver_route'](old_system(system),reduced)
    h=system['health'];v,M,J,g=[np.asarray(system[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    require(h['cone_feasibility_projection'] is True and h['unmodified_v4_failure'] in candidate.ERRORS,'failure-only feasibility route')
    require(h['cone_system_sha256']==candidate.input_hash(v,M,J,g,system['dt_s'],system['friction']),'same original contact equations')
    original=np.asarray(h['cone_trial_reactions'],float);force=np.asarray(h['reactions'],float)
    require(original.shape==(6,) and force.shape==(6,) and np.isfinite(original).all() and np.all(original[::3]>=0),'bounded finite admissible normals')
    mu=system['friction'];norm=max(np.linalg.norm(original),1e-30)
    excess=max(np.linalg.norm(original[3*k+1:3*k+3])-mu*original[3*k] for k in range(2))/norm
    require(excess>1e-12,'original candidate failed original cone gate')
    projected=original.copy()
    for k in range(2):
        i=3*k;radius=mu*original[i];length=np.linalg.norm(original[i+1:i+3])
        if length>radius:projected[i+1:i+3]*=radius/length
    delta=float(np.linalg.norm(projected-original)/norm)
    require(np.array_equal(force,projected) and np.array_equal(force[::3],original[::3]),'exact cone trial projection, unchanged normal reactions')
    require(0<delta<=1e-10 and h['cone_relative_force_retraction']==delta and h['cone_retraction_limit']==1e-10,'bounded representation correction, no gate change')
    require(h['cone_trial_method'] in ('stage201_held_scalar_two_contact','stage201_held_eliminated_two_contact'),'original enumerated candidate method')

source=prior.source
before="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME, TWO_CONTACT_NAME, POLISH_NAME):"
after="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME, TWO_CONTACT_NAME, POLISH_NAME, CONE_NAME):"
require(source.count(before)==1,'one explicit audited method addition');source=source.replace(before,after)
namespace={**prior.namespace,'check_stage194_accepted_route':accepted,'input_route':inputs,'solver_route':solver,'CONE_NAME':candidate.NAME}
exec(compile(source,__file__+'::route_identity_only','exec'),namespace)
evaluate=namespace['evaluate']
STRUCTURAL_IDENTITY={**prior.STRUCTURAL_IDENTITY,'cone_feasibility_route':candidate.NAME,'revised_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'physical_gate_changes':0,'numerical_limits_changed':0}
kernel=types.FunctionType(prior.kernel.__code__,{**prior.kernel.__globals__,'association':types.SimpleNamespace(evaluate=evaluate)},'evaluate',prior.kernel.__defaults__,prior.kernel.__closure__)
