"""Independent solver-gap provenance plus unchanged physical/clock/force audit."""
from contextlib import contextmanager
from pathlib import Path
from fractions import Fraction as F
import copy,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage210_staging'))
import authenticate_failed_system_v1 as source
job,api=source.job,source.api
backend=job.observer.backend.stage41;model=job.fast.gate.contact_model
NAME='stage213_independent_normal_solver_gap_audit_v1'

def band(x,c,a,r):
    # Separate exact-rational reductions, not the producer classifier/fsum.
    u=F(1,2**53);gamma=math.nextafter(float(64*u/(1-64*u)),math.inf)
    scale=math.nextafter(float(sum((abs(F.from_float(float(z))) for z in [*x,*c,a,r]),F(0))),math.inf)
    value=math.nextafter(gamma*scale,math.inf)
    api.require(math.isfinite(value) and 0<value<=1e-10*a,'independent bounded sphere arithmetic band')
    return value

def provenance(record,geometry,before):
    log=record['normal_gap_operand_policy'];api.require(log['policy']=='stage212_binary64_sphere_gap_band_v1'
        and log['scope']=='stage213_normal_solver_gap_operand_scope_v1'
        and log['raw_geometry_membership_lubrication_sweep_dwell_unchanged'],'explicit operand-only contract')
    calls=log['prepare_calls'];trace=record['contact_trial_trace'];rows=record['rows']
    api.require(len(calls)==len(trace['trial_inner_counts'])==len(rows),'one complete prepare per accepted trial')
    prepared={};original=backend._prepare_geometry
    spec=record['spec'];a,b,_=spec['config']['prolate_semiaxes_m']
    for i,call in enumerate(calls):
        api.require(call['index']==i and call['ell_m']==a,'sequential original body radius')
        x,p=(before['state']['x'],before['state']['p']) if i==0 and before else ((spec['initial_state']['position_m'],spec['initial_state']['orientation']) if i==0 else (rows[i-1]['position_m'],rows[i-1]['orientation']))
        contacts=call['contacts'];api.require(len(contacts)==len(call['metadata']) and [int(c[0]) for c in contacts]==rows[i]['active_contact_ids'],'full raw contact ordering')
        effective=[]
        for contact,item in zip(contacts,call['metadata']):
            k,raw,n,l=contact;c=item['context'];m=item['classification']
            delta=geometry.c[k]-np.asarray(x);delta-=geometry.L*np.round(delta/geometry.L);centre=np.asarray(x)+delta
            api.require(c['grain_id']==k and c['x']==x and c['p']==p and c['a']==a and c['b']==b
                and c['c']==centre.tolist() and c['r']==float(geometry.r[k]) and c['original_periodic_length_m']==geometry.L,'original stored pose/grain periodic identity')
            gg,nn,ll=model.ellipsoid_grain_contact(np.asarray(x),np.asarray(p),a,b,centre,float(geometry.r[k]))
            api.require(gg==raw==c['raw_gap_m']==m['raw_gap_m'] and np.array_equal(nn,n) and np.array_equal(ll,l)
                and c['normal']==n and c['lever']==l,'independent native raw geometry')
            api.require(raw<=c['original_skin_m'],'original skin membership')
            # Replay the original entire membership query at its recorded skin.
            # Skin itself is independently constrained by the unchanged timestep/clearance path.
            actual=geometry.contacts(np.asarray(x),np.asarray(p),a,b,c['original_skin_m'])
            api.require([[int(z[0]),float(z[1]),np.asarray(z[2]).tolist(),np.asarray(z[3]).tolist()] for z in actual]==contacts,'unmodified full raw membership')
            api.require(m['policy']==log['policy'] and m['sphere']==(a==b),'classification identity')
            if a==b:
                bound=band(x,centre,a,float(geometry.r[k]));zero=abs(raw)<=bound
                api.require(m['uncertainty_m']==bound and m['operations']==64 and m['unit_roundoff']==2.0**-53
                    and m['maximum_band_over_body_radius']==1e-10,'exact prior fixed policy constants')
                expected=0. if zero else raw
                api.require(m['classified_zero']==zero and m['changed']==(zero and raw!=0),'sphere flags')
            else:
                expected=raw;api.require(m['uncertainty_m']==0 and not m['changed'] and not m['classified_zero'],'unaltered fibre operands')
            api.require(float(m['effective_gap_m']).hex()==float(expected).hex(),'raw/effective exact declaration');effective.append(expected)
        J,g,_=original(contacts,a)
        api.require(call['jacobian_sha256']==api.digest(J.tolist()) and call['raw_gaps_m']==g.tolist()
            and call['effective_gaps_m']==effective,'unchanged J and revised-gap exact provenance')
        key=api.digest(contacts)
        api.require(key not in prepared or prepared[key]==effective,'unambiguous raw geometry to operand association')
        prepared[key]=effective
    for trial in trace['detailed_trials']:
        api.require(trial['outer_inputs'][6]==calls[trial['trial_index']]['contacts'],'original raw outer inputs unchanged')
    return prepared

def kernel(record,spec,binding,before,geometry,design_sha256,gap_semantics):
    api.require('numerical_policy_contract_sha256' in record,'explicit qualification contract binding')
    prepared=provenance(record,geometry,before);original=backend._prepare_geometry
    def independent_prepare(contacts,ell):
        plain=[[int(k),float(g),np.asarray(n).tolist(),np.asarray(l).tolist()] for k,g,n,l in contacts]
        key=api.digest(plain);api.require(key in prepared,'all audited solve inputs have independently verified raw provenance')
        J,g,frames=original(contacts,ell);return J,np.asarray(prepared[key]),frames
    backend._prepare_geometry=independent_prepare
    try:result=source.frozen.stack.auditor.kernel(record,spec,binding,before,geometry,design_sha256,gap_semantics)
    finally:backend._prepare_geometry=original
    return dict(result,normal_gap_operand_policy_verified=True,raw_geometry_contact_membership_unchanged=True,
                revised_sphere_gap_policy_explicit=True,original_raw_contract_numerical_pass=False)

