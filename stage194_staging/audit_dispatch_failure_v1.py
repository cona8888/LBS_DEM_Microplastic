"""Audit sealed second failure, without promoting its rejected trials."""
from pathlib import Path
import os,sys
import qualify_failure_codec_v1 as q
import audit_projection_routes_v2 as auditor
sys.path.insert(0,str(q.ROOT/'stage183_staging'))
import audit_fallback_systems_v1 as physical
job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924'
OUT=BASE/'dispatch_failure_audit_01';RUN=q.ROOT/'stage194_runs/evidence_repair_20260924'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/dispatch_restart_01.json'

def run():
    w=api.read(q.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work clock')
    summary=api.read(BASE/'dispatch_restart_01/results.json');api.verify_mapping(summary['artifacts'])
    api.require(api.read(BASE/'dispatch_restart_01/completion.json')['results_sha256']==api.sha(BASE/'dispatch_restart_01/results.json') and not summary['passed'],'sealed failed attempt')
    proto=api.read(DESIGN);api.verify_mapping(proto['inputs']);api.verify_mapping(proto['sources']);d=api.read(job.DESIGN);job.verify(d)
    record=q.independent_file(RUN/'dispatch_restart_01/call_01.json.xz',api.sha(DESIGN))
    prior=DESIGN.with_name('trajectory_qualification_01.json')
    before=q.independent_file(RUN/'trajectory_qualification_01/call_01.json.xz',api.sha(prior))['result']['checkpoint']
    oracle=q.independent_file(RUN/'trajectory_qualification_01/call_02.json.xz',api.sha(prior))
    OUT.mkdir(parents=True,exist_ok=False);inputs={str(x):api.sha(x) for x in (Path(__file__),DESIGN,BASE/'dispatch_restart_01/results.json',RUN/'dispatch_restart_01/call_01.json.xz')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0})
    r=record['result'];state=r['checkpoint']['state'];rows=record['rows'];trace=record['contact_trial_trace'];trials=trace['detailed_trials']
    api.require(record['input_checkpoint_sha256']==api.digest(before) and api.digest(state)==r['checkpoint']['state_sha256'],'checkpoint seals')
    api.require(rows==oracle['rows'] and len(rows)==55 and state['steps']-before['state']['steps']==55,'exact independently qualified accepted prefix and accounting')
    api.require(record['sweep_certificates']==oracle['sweep_certificates'],'exact independently qualified swept-clearance certificates')
    for k in ('t','x','p','q','monitor','steps'):api.require(state[k]==oracle['result']['checkpoint']['state'][k],'exact qualified accepted endpoint '+k)
    rejected_reason=None
    try:auditor.kernel(record,proto['case']['spec'],proto['original_binding'],before,None,api.sha(DESIGN),d['minimum_gap_semantics'])
    except RuntimeError as e:rejected_reason=str(e)
    api.require(rejected_reason=='supported nonfailed status, zero rejected trials','strict auditor still rejects')
    failed=[];systems=[];accepted_checks=[];by={t['trial_index']:t for t in trials};api.require(len(by)==len(trials),'unique trial identities')
    ai=0;fi=0;clock=before['state']['t']
    for index,count in enumerate(trace['trial_inner_counts']):
        t=by.get(index)
        if t is not None:
            api.require(len(t['inner_systems'])==count and t['outer_inputs'][0]==(before['state']['q'] if ai==0 else rows[ai-1]['velocity_generalized']),'exact inner count and accepted-parent velocity')
            for k,s in enumerate(t['inner_systems']):
                api.require(s['inner_index']==k,'sequential inner identity')
                if s['accepted']:accepted_checks.append(physical.physical(s))
                else:api.require(not t['accepted'] and 'error' in s and 'velocity' not in s and 'health' not in s,'lossless failed inner schema');systems.append(s)
            if not t['accepted']:
                e=state['rejected_trials'][fi]
                api.require(e['time_s']==clock and e['dt_s']==t['outer_inputs'][8] and t['error']=="RuntimeError('"+e['reason']+"')",'exact rejected trial accounting')
                api.require('velocity' not in t and 'health' not in t,'no fabricated failed outer result');failed.append(t);fi+=1;continue
        row=rows[ai];api.require(clock+row['dt_s']==row['time_s'],'exact accepted clock')
        if t is not None:api.require(t['accepted'] and t['velocity']==row['velocity_generalized'],'exact accepted trial-row association')
        ai+=1;clock=row['time_s']
    api.require(ai==55 and fi==r['rejected']==state['rejected']==3 and len(trace['trial_inner_counts'])==58 and clock==state['t'],'complete accepted/rejected clock and count')
    details={'failed_outer_trials':failed,'captured_systems':systems,'rejected_trials':state['rejected_trials'],'pending_trial':state.get('pending_trial')}
    job.commit(OUT/'failure_details.json',details);api.verify_mapping(inputs);api.verify_mapping(summary['artifacts'])
    result={'evidence_audit_passed':True,'numerical_campaign_gate_passed':False,'frozen_rejection':rejected_reason,'new_trajectory_steps':0,
       'new_attempt_accepted_steps':55,'window_total_new_steps':19396,'remaining_step_allowance':30604,'accepted_inner_checks':len(accepted_checks),
       'failed_trials':3,'failed_inner_systems':len(systems),'complete_observation':False,'exact_55_step_prefix':True,
       'compute_seconds':record['compute_call_wall_s'],'failure_details_sha256':api.sha(OUT/'failure_details.json'),'inputs':inputs}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('FAILED_DISPATCH_AUDITED',result,flush=True)
    for t in failed:print('FAILED',t['trial_index'],t['error'],t['inner_systems'][-1]['gaps_m'],t['inner_systems'][-1]['dt_s'],flush=True)

if __name__=='__main__':run()
