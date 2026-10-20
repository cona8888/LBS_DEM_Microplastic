"""Independent record-chain, physics-gate and three-level regression audit."""
import copy
import sys
import numpy as np
import repair_regression_v1 as job
api=job.api
OUT=job.EVAL/'independent_evaluation_01'


def group_checks(cm,mf,t,event):
    def trend(k,b):return mf[k]<=t['refinement_trend_multiplier_max']*cm[k]+t['trend_roundoff_floor'] or max(cm[k],mf[k])<=t['trend_waiver_fraction_of_budget']*b
    return {'position':mf['position_difference_over_b']<=t['fine_medium_position_over_b_max'],
        'axis':mf['apolar_axis_angle_rad']<=t['fine_medium_axis_angle_rad_max'],
        'velocity':mf['translational_velocity_relative_difference']<=t['fine_medium_translational_velocity_relative_max'],
        'position_trend':trend('position_difference_over_b',t['fine_medium_position_over_b_max']),
        'axis_trend':trend('apolar_axis_angle_rad',t['fine_medium_axis_angle_rad_max']),
        'time':mf['time_difference_s']<=t['exit_time_difference_s_max'],**event}


def evaluator_tests(t):
    zero={k:0. for k in ['position_difference_over_b','apolar_axis_angle_rad','translational_velocity_relative_difference','time_difference_s']}
    results={'valid_pass':all(group_checks(zero,zero,t,{'same_dwell':True}).values())}
    for key,threshold in [('position_difference_over_b','fine_medium_position_over_b_max'),('apolar_axis_angle_rad','fine_medium_axis_angle_rad_max'),('translational_velocity_relative_difference','fine_medium_translational_velocity_relative_max'),('time_difference_s','exit_time_difference_s_max')]:
        bad=dict(zero);bad[key]=t[threshold]*1.1
        results[key+'_rejected']=not all(group_checks(zero,bad,t,{'same_dwell':True}).values())
    results['dwell_mismatch_rejected']=not all(group_checks(zero,zero,t,{'same_dwell':False}).values())
    for key,threshold in [('position_difference_over_b','fine_medium_position_over_b_max'),('apolar_axis_angle_rad','fine_medium_axis_angle_rad_max')]:
        bad=dict(zero);bad[key]=t[threshold]*.5
        results[key+'_nonconvergent_trend_rejected']=not all(group_checks(zero,bad,t,{}).values())
    return results


def main():
    d=api.read(job.DESIGN);job.verify(d);done=api.read(job.RUN/'completion.json');manifest=api.read(job.RUN/'manifest.json')
    api.require(done['design_sha256']==manifest['design_sha256']==api.sha(job.DESIGN),'run design drift')
    api.require(done['manifest_sha256']==api.sha(job.RUN/'manifest.json'),'manifest drift')
    api.require([x['case_id'] for x in done['ledger']]==manifest['case_order']==[c['id'] for c in d['cases']],'case order drift')
    records={};ledger=[];artifacts={};tests=evaluator_tests(d['acceptance'])
    for c,entry in zip(d['cases'],done['ledger']):
        name=c['id'];segments=[];previous=None;rows=[]
        for i in range(1,entry.get('segments',0)+1):
            p=job.RUN/name/f'segment_{i:02d}';r=api.read(p/'record.json');comp=api.read(p/'completion.json');launch=api.read(p/'launch.json')
            api.require(comp['record_sha256']==api.sha(p/'record.json') and comp['launch_sha256']==api.sha(p/'launch.json'),'record binding drift')
            api.require(r['case_id']==launch['case_id']==name and r['design_sha256']==launch['design_sha256']==api.sha(job.DESIGN) and r['segment']==i,'case identity drift')
            api.require(r['prior_record_sha256']==(None if previous is None else api.sha(p.parent/f'segment_{i-1:02d}/record.json')),'chain drift')
            if previous is not None:
                expected_cp=previous['result']['checkpoint']
                api.require(previous['result']['status']=='incomplete_budget','invalid predecessor')
            elif c['source_checkpoint']:
                source=api.read(c['source_checkpoint'])['result']['checkpoint'];expected_cp=copy.deepcopy(source)
                expected_cp['contract']=job.prior.contracts.expected_contract(c['spec'],job.binding(d,c))
                api.require(r['migration']['exact_state_preserved'] and source['state_sha256']==c['initial_state_sha256'],'migration state drift')
            else:expected_cp=None
            api.require(r['checkpoint_input_sha256']==(None if expected_cp is None else api.digest(expected_cp)),'input checkpoint drift')
            state=r['result'];cp=state['checkpoint']
            api.require(cp['contract']==job.prior.contracts.expected_contract(c['spec'],job.binding(d,c)) and cp['state_sha256']==api.digest(cp['state']),'output checkpoint integrity drift')
            api.require(cp['state']['t']==state['time_s'] and cp['state']['x']==state['position_m'] and cp['state']['q']==state['velocity_generalized'],'checkpoint/result state drift')
            dense=api.read(p/'accepted_intervals.json');api.require(api.sha(p/'accepted_intervals.json')==r['accepted_intervals_sha256'],'dense evidence drift')
            if dense:api.require(abs(dense[-1]['time_s']-state['time_s'])<1e-12,'dense endpoint drift')
            rows.extend(dense);health=job.prior.reference.independent_health(state,c['spec'])
            segments.append({'segment':i,'health':health,'runtime_s':state['runtime_seconds'],'status':state['status'],'repair_calls':len(state['stage119_repair_calls']),'accepted_repairs':sum(x['accepted'] for x in state['stage119_repair_calls'])})
            for path in p.iterdir():
                if path.is_file():artifacts[str(path)]=api.sha(path)
            previous=r
        if previous is None:ledger.append({'case_id':name,'qualified':False,'status':entry['status'],'segments':[]});continue
        api.require(api.sha(entry['last_record'])==entry['record_sha256'],'final record drift')
        records[name]=previous
        ledger.append({'case_id':name,'qualified':all(s['health']['passed'] for s in segments) and previous['result']['status']=='present_at_horizon',
            'status':previous['result']['status'],'time_s':previous['result']['time_s'],'segments':segments,
            'runtime_s':sum(s['runtime_s'] for s in segments),'new_accepted_intervals':len(rows),'max_interval_s':max((x['dt_s'] for x in rows),default=0.),
            'repair_calls':sum(s['repair_calls'] for s in segments),'accepted_repairs':sum(s['accepted_repairs'] for s in segments),
            'explicit_rejection_count':len(previous['result']['rejected_trials'])})
    groups=[]
    for g in d['groups']:
        row={'name':g['name'],'ids':g['ids'],'passed':False}
        if all(any(x['case_id']==name and x['qualified'] for x in ledger) for name in g['ids']):
            r=[records[name] for name in g['ids']];spec=next(c['spec'] for c in d['cases'] if c['id']==g['ids'][0])
            cm=job.prior.reference.difference(r[0],r[1],spec);mf=job.prior.reference.difference(r[1],r[2],spec)
            observed=[x['result']['persistent_contact_observed'] for x in r]
            event={'same_dwell':len(set(observed))==1,'event_time':not any(observed) or (all(observed) and max(x['result']['first_contact_dwell_time_s'] for x in r)-min(x['result']['first_contact_dwell_time_s'] for x in r)<=d['event_acceptance']['first_dwell_time_difference_max_s']),
                'fine_interval':next(x['max_interval_s'] for x in ledger if x['case_id']==g['ids'][-1])<=d['event_acceptance']['finest_max_accepted_interval_s']}
            checks=group_checks(cm,mf,d['acceptance'],event)
            row.update(coarse_medium=cm,medium_fine=mf,checks=checks,passed=all(checks.values()))
        else:row['reason']='incomplete or unhealthy triplet'
        groups.append(row)
    no_failure=not list(job.RUN.rglob('failure.json')) and not done['stopped_on_failure'] and not any(p.stat().st_size for p in job.RUN.glob('*.stderr.txt'))
    passed=all(x['qualified'] for x in ledger) and all(g['passed'] for g in groups) and no_failure and all(tests.values())
    result={'passed':passed,'status':'bounded_repair_regression_passed' if passed else 'bounded_repair_regression_failed_or_incomplete',
        'ledger':ledger,'groups':groups,'evaluator_tests':tests,'no_failure_or_stderr':no_failure,'wall_s':done['wall_s'],
        'total_integrator_s':sum(x.get('runtime_s',0.) for x in ledger),'design_sha256':api.sha(job.DESIGN),'run_completion_sha256':api.sha(job.RUN/'completion.json'),
        'artifacts':artifacts,'limitations':['Saved episode includes inherited historical state; it is not full-path convergence.','Fresh sentinels use seed 1, CPD2 and a 0.5-s endpoint only.','Extreme retry29 contact remains fail-closed, not universally repaired.','No population release fraction, permeability validation, or physical validation established.'],
        'next':'If all gates pass, extend corrected-flow matched seed2 CPD2/CPD4 sentinels under a new bounded contract. Otherwise diagnose failed gate without relaxing acceptance.'}
    job.verify(d);OUT.mkdir(parents=True,exist_ok=False);api.write(OUT/'results.json',result)
    api.write(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
    print('EVALUATION',passed,'qualified',sum(x['qualified'] for x in ledger),'/9','groups',sum(g['passed'] for g in groups),'/3',flush=True)
    for g in groups:print(g,flush=True)
    return 0 if passed else 4


if __name__=='__main__':raise SystemExit(main())
