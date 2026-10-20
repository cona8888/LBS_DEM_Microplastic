"""Explicit seeded-elimination provenance; unchanged physical/clock gates."""
from pathlib import Path
import hashlib,types
import numpy as np
import audit_two_contact_dispatch_v3 as prior
import two_contact_seeded_polish_v4 as repair
ns0=prior.ns;require=ns0['require']


def accepted(system,call,reduced):
    if system['health'].get('solver')!=repair.NAME:return ns0['accepted'](system,call,reduced)
    require(system['accepted'] is True and call['accepted'] is True,'accepted seeded two-contact solve')
    require(call.get('original_exception') in repair.ERRORS,'original primary numerical failure')
    require(reduced=={'reduced_accepted':False,'reduced_error':'stage169 supports exactly three six-DOF contacts','wall_s':reduced['wall_s']},'exact original reduced-domain exclusion')


def inputs(system,call,reduced):
    if system['health'].get('solver')!=repair.NAME:return ns0['inputs'](system,call,reduced)
    require(call['dt_s']==system['dt_s'] and call['gaps_m']==system['gaps_m'],'exact original input binding')


def solver(system,reduced):
    if system['health'].get('solver')!=repair.NAME:return ns0['solver'](system,reduced)
    h=system['health'];require(len(system['gaps_m'])==2 and np.asarray(system['jacobian']).shape==(6,6),'two-contact domain')
    require(h['original_gaps_preserved'] is True and h['stateless_same_system'] is True,'same original system')
    require(h['scalar_dispatch_policy']=='after_original_primary_failure' and h['original_mixed_attempted'] is False,'primary-failure dispatch provenance')
    require(h['scalar_first_error'] in repair.ERRORS,'failed first scalar candidate')
    require(h['seeded_system_sha256']==repair.input_hash(*[system[k] for k in ('vfree','mobility','jacobian','gaps_m','dt_s','friction')]),'same-system seed identity')
    seeds=np.asarray(h['seed_reactions']);require(seeds.ndim==2 and seeds.shape[1]==6 and 1<=len(seeds)<=3 and np.isfinite(seeds).all(),'bounded finite rejected-scalar seeds')
    require(type(h['elimination_mode_index']) is int and 0<=h['elimination_mode_index']<9,'bounded active-mode search')
    require(type(h['elimination_seed_index']) is int and 0<=h['elimination_seed_index']<3+len(seeds),'bounded seed search')
    require(type(h['elimination_nfev']) is int and 0<=h['elimination_nfev']<=2000 and h['iterations']==h['elimination_nfev'],'bounded explicit optimization')
    require(len(h['contact_modes'])==2 and all(type(m) is int and m in (0,1,2) for m in h['contact_modes']),'original open/stick/slide modes')
    active=[3*k+j for k,m in enumerate(h['contact_modes']) if m for j in range(3)];J=np.asarray(system['jacobian']);sv=np.linalg.svd(J.T[:,active],compute_uv=False)
    rank=int(sum(sv>sv[0]*1e-12)) if len(sv) else 0
    require(h['force_map_rank']==rank and h['force_nullspace_width']==len(active)-rank,'actual active force rank/nullity')


source=ns0['source']
before="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME, TWO_CONTACT_NAME):"
after="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME, TWO_CONTACT_NAME, POLISH_NAME):"
require(source.count(before)==1,'one explicit method route addition');source=source.replace(before,after)
namespace={**ns0['namespace'],'check_stage194_accepted_route':accepted,'input_route':inputs,'solver_route':solver,'POLISH_NAME':repair.NAME}
exec(compile(source,__file__+'::route_identity_only','exec'),namespace)
evaluate=namespace['evaluate'];STRUCTURAL_IDENTITY={**prior.STRUCTURAL_IDENTITY,'failure_only_polisher':repair.NAME,'revised_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'physical_gate_changes':0,'numerical_limits_changed':0}
kernel=types.FunctionType(prior.kernel.__code__,{**prior.kernel.__globals__,'association':types.SimpleNamespace(evaluate=evaluate)},'evaluate',prior.kernel.__defaults__,prior.kernel.__closure__)
