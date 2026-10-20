"""Independent provenance/accounting audit of a explicitly FAILED diagnostic.

The frozen numerical auditor must reject it. Separate raw/clock/pose/dwell and
accepted-system checks describe preserved evidence, never promote the failure.
"""
from pathlib import Path
import os,time,sys
import numpy as np
import qualify_failure_codec_v1 as q
sys.path.insert(0,str(q.ROOT/'stage183_staging'))
import audit_fallback_systems_v1 as physical

job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924';OUT=BASE/'diagnostic_independent_audit_01'


def run():
    work=api.read(q.WORK);api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work clock')
    d=api.read(job.DESIGN);job.verify(d)
    source=BASE/'diagnostic_replay_01';summary=api.read(source/'results.json');api.verify_mapping(summary['raw_artifacts'])
    api.require(api.read(source/'completion.json')['results_sha256']==api.sha(source/'results.json'),'diagnostic seal')
    protocol=q.ROOT/'stage194_designs/evidence_repair_20260924/diagnostic_replay_01.json';api.verify_mapping(api.read(protocol)['inputs'])
    seed_path=BASE/'seed_extraction_01/diagnostic_seed_01.json';seed=api.read(seed_path);before=seed['checkpoint']
    record=q.independent_file(q.ROOT/'stage194_runs/evidence_repair_20260924/diagnostic_replay_01/diagnostic.json.xz',api.sha(job.DESIGN))
    case=next(c for c in d['cases'] if c['id']==seed['case']);binding=job.binding(d,case);r=record['result'];cp=r['checkpoint'];state=cp['state'];rows=record['rows']
    OUT.mkdir(parents=True,exist_ok=False);inputs={str(p):api.sha(p) for p in (Path(__file__),q.WORK,protocol,seed_path,source/'results.json',source/'completion.json')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0})
    rejected_reason=None
    try:job.kernel.evaluate(record,case['spec'],binding,before,None,api.sha(job.DESIGN),d['minimum_gap_semantics'])
    except RuntimeError as error:rejected_reason=str(error)
    api.require(rejected_reason=='supported nonfailed status, zero rejected trials','unchanged frozen numerical auditor rejects diagnostic')
    api.require(api.digest(before)==summary['input_checkpoint_sha256']==record['input_checkpoint_sha256'],'complete input checkpoint digest')
    api.require(api.digest(cp)==summary['output_checkpoint_sha256'] and api.digest(state)==cp['state_sha256'],'complete output checkpoint digest')
    api.require(len(rows)==summary['new_accepted_steps']==9645 and state['steps']-before['state']['steps']==len(rows),'exact step ledger')
    detail=api.read(source/'failure_details.json');api.require(api.sha(source/'failure_details.json')==summary['failure_details_sha256'],'failure detail SHA')
    trace=record['contact_trial_trace'];failed=[t for t in trace['detailed_trials'] if not t['accepted']]
    api.require(failed==detail['failed_outer_trials'] and len(failed)==r['rejected']==state['rejected']==5,'full failed-trial accounting')
    by_index={t['trial_index']:t for t in trace['detailed_trials']};api.require(len(by_index)==len(trace['detailed_trials']),'unique trial IDs')
    failed_by_index={t['trial_index']:t for t in failed};ai=0;clock=before['state']['t'];failed_seen=[];systems=0;maxima=[0.,0.]
    for ti,count in enumerate(trace['trial_inner_counts']):
        trial=by_index.get(ti)
        if trial is not None:
            api.require(len(trial['inner_systems'])==count and [s['inner_index'] for s in trial['inner_systems']]==list(range(count)),'complete sequential inner systems')
            api.require(trial['outer_inputs'][0]==(before['state']['q'] if ai==0 else rows[ai-1]['velocity_generalized']),'outer input bound to preceding accepted state, not trial index')
            for inner in trial['inner_systems']:
                if inner['accepted']:
                    a=physical.physical(inner);systems+=1;maxima=[max(maxima[0],a['contact_residual']),max(maxima[1],a['force_residual'])]
                else:api.require(not trial['accepted'] and 'error' in inner and 'velocity' not in inner,'failed inner preserved without fabricated result')
        if ti in failed_by_index:
            trial=failed_by_index[ti];entry=state['rejected_trials'][len(failed_seen)]
            api.require(entry['time_s']==clock and entry['dt_s']==trial['outer_inputs'][8] and trial['error']=="RuntimeError('"+entry['reason']+"')",'failure clock/dt/reason bound to rejected ledger')
            api.require('velocity' not in trial and 'health' not in trial,'failed outer remains heterogeneous')
            failed_seen.append(ti);continue
        row=rows[ai];api.require(clock+row['dt_s']==row['time_s'] and row['dt_s']>0,'accepted exact clock')
        if trial is not None:api.require(trial['accepted'] and trial['velocity']==row['velocity_generalized'],'accepted outer result bound to correct row')
        clock=row['time_s'];ai+=1
    api.require(ai==len(rows) and len(trace['trial_inner_counts'])==ai+len(failed)==9650,'all accepted and rejected trials accounted')
    # Pose, swept clearance and dwell are rechecked without waiving rejected-trial failure.
    original=job.kernel.original;verified=original.verified;spec=case['spec'];a,b,_=spec['config']['prolate_semiaxes_m'];outlet=spec['field_metadata']['cell_length_m']
    monitor=verified.restore_monitor(spec,before['state']);x=before['state']['x'];p=before['state']['p'];certified=0;legacy=0
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,spec['field_metadata']):
        _,data,meta=api.fields.load(2,1.,6)
        geometry=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
        for i,(row,proof) in enumerate(zip(rows,record['sweep_certificates'])):
            velocity=row['velocity_generalized'];dt=row['dt_s'];trialdt=proof['dt_s']
            if proof['certified']:verified.audit_proof(proof,geometry,x,p,velocity,trialdt,a,b);certified+=1
            else:
                value=verified.job.candidate.REFERENCE(geometry,np.array(x),np.array(p),np.array(velocity),a,b,trialdt)
                api.require(value==proof['reference_gap_m'] and value>=-1e-5*b,'original swept gap');legacy+=1
            original.interval_geometry(x,p,velocity,a,b,outlet,dt,trialdt,row['position_m'],row['orientation'],i==len(rows)-1,r['status'])
            dwell=monitor.update(dt,row['position_m'],velocity,row['active_contact_ids'],row['supported_bearing_ids'])
            api.require(dwell==row['dwell'],'independent dwell replay');x=row['position_m'];p=row['orientation']
    api.require(len(rows)==len(record['sweep_certificates'])==certified+legacy,'all clearance certificates checked')
    api.require(api.digest(monitor.__dict__)==api.digest(state['monitor']),'full monitor identity')
    api.require(clock==state['t']==r['time_s']<spec['horizon_s'] and x==state['x'] and p==state['p'] and rows[-1]['velocity_generalized']==state['q'],'endpoint and incomplete horizon')
    api.verify_mapping(inputs);api.verify_mapping(summary['raw_artifacts']);job.verify(d)
    result={'provenance_accounting_audit_passed':True,'numerical_campaign_gate_passed':False,'frozen_rejection':rejected_reason,
            'new_trajectory_steps_this_audit':0,'window_new_steps_accounted':len(rows),'remaining_step_allowance':work['maximum_new_accepted_trajectory_steps']-len(rows),
            'failed_trials':len(failed),'outer_trials':len(trace['trial_inner_counts']),'accepted_inner_systems_independently_checked':systems,
            'max_contact_residual':maxima[0],'max_force_residual':maxima[1],'certified_sweeps':certified,'legacy_sweeps':legacy,
            'complete_observation':False,'end_time_s':clock,'old_missing_block174_still_unknown':True,'inputs':inputs}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('FAILED_DIAGNOSTIC_AUDITED',len(rows),len(failed),systems,flush=True)


if __name__=='__main__':run()
