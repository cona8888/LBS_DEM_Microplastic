"""Per-segment independent audit kernel for the opt-in optimized stack.

No integration. Caller must verify frozen source/input/record seals first.
Terminal records require exact horizon or independently replayed whole-body
export. A clearance proof for a full trial also certifies its exit-truncated
prefix; it is never silently treated as a new shorter force solve.
"""
from pathlib import Path
from collections import Counter
import copy,math,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage177_staging'),str(ROOT/'algorithm_review_20260912/src')]
import audit_extended_preflight_v1 as verified
import exit_event_v1 as exit_event
api,parent=verified.api,verified.parent
KINEMATIC_POSITION_TOL_B=1e-12
KINEMATIC_AXIS_TOL=1e-12


def interval_geometry(x,p,q,a,b,outlet,dt,trial,end_x,end_p,is_last,status):
    api.require(0<dt<=trial,'positive accepted prefix of a numerical trial')
    api.require(trial==dt or (is_last and status=='full_window_exit'),'only export truncates a trial')
    xx,pp=exit_event.mechanics.advance_pose(np.array(x),np.array(p),np.array(q),a,dt)
    api.require(np.linalg.norm(xx-np.array(end_x))<=KINEMATIC_POSITION_TOL_B*b and np.linalg.norm(pp-np.array(end_p))<=KINEMATIC_AXIS_TOL,'accepted rigid pose replay')
    event=exit_event.linear_pose_exit_time(x,p,q,a,b,outlet,trial)
    if event is not None:
        api.require(is_last and status=='full_window_exit' and abs(event-dt)<=max(1e-14,trial*1e-12),'first whole-body export interval')
        clearance=exit_event.mechanics.full_exit_function(end_x,end_p,a,b,outlet)
        roundoff=32*np.finfo(float).eps*max(abs(end_x[0]),abs(outlet),a)
        api.require(clearance>=-roundoff,'whole body, not just centre, exported')
    return event


def terminal_label(status,t,horizon,exit_seen):
    api.require(status!='present_at_horizon' or t==horizon,'exact observation horizon')
    api.require(t!=horizon or status in {'present_at_horizon','full_window_exit'},'horizon cannot be labelled incomplete')
    api.require((status=='full_window_exit')==bool(exit_seen),'export label requires replayed event')


def evaluate(record,spec,binding,before,geometry,design_sha256,gap_semantics):
    started=time.perf_counter();r=record['result'];cp=r['checkpoint'];state=cp['state'];rows=record['rows'];effective=parent.model.binding_for(binding,True)
    api.require(record['design_sha256']==design_sha256 and record['spec']==spec and record['input_checkpoint_sha256']==api.digest(before),'frozen raw input binding')
    api.require(record['effective_binding']==effective and cp['contract']==parent.engine.prior.contracts.expected_contract(spec,effective),'runtime contract')
    api.require(cp['state_sha256']==api.digest(state),'checkpoint state SHA256')
    api.require(record['minimum_gap_semantics']==gap_semantics,'conservative gap semantics')
    allowed={'paused_checkpoint','incomplete_budget','present_at_horizon','full_window_exit'}
    api.require(r['status'] in allowed and r['rejected']==(before['state']['rejected'] if before else 0)==0,'supported nonfailed status, zero rejected trials')
    api.require(parent.engine.prior.reference.independent_health(r,spec)['passed'],'original numerical health gates')
    api.require(0<len(rows)==len(record['sweep_certificates'])<=record['step_cap'],'accepted trace and clearance proof coverage')
    cfg=spec['config'];a,b,_=cfg['prolate_semiaxes_m'];outlet=spec['field_metadata']['cell_length_m']
    if before:
        t=before['state']['t'];x=before['state']['x'];p=before['state']['p'];n=before['state']['steps'];first=before['state']['first_contact_dwell_time']
        monitor=verified.restore_monitor(spec,before['state'])
    else:
        t=0.;x=spec['initial_state']['position_m'];p=spec['initial_state']['orientation'];n=0;first=None;monitor=verified.stream_audit.make_monitor(spec)
    initial_t=t;certified=legacy=0;velocity_keys=Counter();exit_row=None
    if before and before['state'].get('pending_trial') is not None:
        pending=before['state']['pending_trial'];api.require(pending['attempt']==0 and pending['time_s']==t,'uncommitted inherited budget trial')
        api.require(record['sweep_certificates'][0]['dt_s']==pending['dt_s'],'pending trial resumed without changing timestep')
    for i,(row,proof) in enumerate(zip(rows,record['sweep_certificates'])):
        dt=row['dt_s'];trial=proof['dt_s'];q=row['velocity_generalized']
        api.require(dt>0 and t+dt==row['time_s'],'exact accepted clock')
        api.require(np.isfinite(row['position_m']+row['orientation']+q).all() and abs(np.linalg.norm(row['orientation'])-1)<=1e-10,'finite normalized accepted state')
        partial=trial!=dt
        api.require(not partial or (i==len(rows)-1 and r['status']=='full_window_exit' and trial>dt),'only terminal export may truncate a certified trial')
        if proof['certified']:
            verified.audit_proof(proof,geometry,x,p,q,trial,a,b);certified+=1
        else:
            value=verified.job.candidate.REFERENCE(geometry,np.array(x),np.array(p),np.array(q),a,b,trial)
            api.require(value==proof['reference_gap_m'] and value>=-1e-5*b,'original swept gate replay');legacy+=1
        event=interval_geometry(x,p,q,a,b,outlet,dt,trial,row['position_m'],row['orientation'],i==len(rows)-1,r['status'])
        if event is not None:
            exit_row=i
        dwell=monitor.update(dt,row['position_m'],q,row['active_contact_ids'],row['supported_bearing_ids'])
        api.require(dwell==row['dwell'],'interval dwell replay')
        if first is None and dwell['persistent_contact_observed']:first=row['time_s']
        velocity_keys[(trial,*q)]+=1;t=row['time_s'];x=row['position_m'];p=row['orientation']
    api.require(t==r['time_s']==state['t'] and r['steps']==state['steps']==n+len(rows),'all clocks and steps accounted')
    api.require(state['x']==r['position_m']==x and state['p']==p and state['q']==r['velocity_generalized']==rows[-1]['velocity_generalized'],'endpoint identity')
    api.require(api.digest(monitor.__dict__)==api.digest(state['monitor']) and rows[-1]['dwell']==state['last_trap_state']==r['trap_state'],'complete monitor state')
    api.require(first==state['first_contact_dwell_time']==r['first_contact_dwell_time_s'] and (first is not None)==r['persistent_contact_observed']==state['persistent_contact_observed'],'dwell observation flag and first time')
    api.require(initial_t<t<=spec['horizon_s'],'forward finite observation clock')
    terminal_label(r['status'],t,spec['horizon_s'],exit_row is not None)
    pending=state.get('pending_trial')
    if pending is not None:
        api.require(r['status']=='incomplete_budget' and pending['attempt']==0 and pending['time_s']==t and np.isfinite(pending['dt_s']) and 0<pending['dt_s']<=spec['horizon_s']-t,'valid uncommitted budget checkpoint')
    api.require(len(record['backend_calls'])==1 and record['backend_calls'][0]['enabled'],'qualified rigid backend')
    # Fail closed outside the observed qualified fallback coverage. Never infer
    # independent force verification from an unrecorded contact system.
    api.require(len(record['repairs'])==len(r['stage119_repair_calls'])==0,'no unrecorded fallback system')
    early=0;maxima=[0.,0.]
    for attempt in record['early_attempts']:
        if attempt['accepted']:
            key=(attempt['dt_s'],*attempt['velocity']);api.require(velocity_keys[key]>0,'force-system output tied to an accepted trial');velocity_keys[key]-=1
            values=verified.physical(attempt);maxima=[max(a,b) for a,b in zip(maxima,values)];early+=1
    for cert in record['certificates']:
        api.require(cert['roundoff_certificate_used'] and cert['exact_rational_inputs'] and cert['correctly_rounded_velocity_sum'],'roundoff certificate flags')
        api.require(0<=cert['force_residual']<=1e-8 and 0<cert['mobility_condition_number']<=1e8,'roundoff certificate gates')
    return {'passed':True,'steps':len(rows),'start_s':initial_t,'stop_s':t,'certified_sweeps':certified,'legacy_sweeps':legacy,
            'early_force_systems':early,'max_contact_residual':maxima[0],'max_force_residual':maxima[1],
            'status':r['status'],'complete_observation':r['status'] in {'present_at_horizon','full_window_exit'},'first_dwell_s':first,
            'output_checkpoint_state_sha256':cp['state_sha256'],'audit_seconds':time.perf_counter()-started}
