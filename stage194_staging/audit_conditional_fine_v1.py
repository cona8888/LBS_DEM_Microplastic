"""Independent read-only audit of the bounded conditional fine comparison."""
from pathlib import Path
import os,importlib.util,shutil
import numpy as np
import psutil
import qualify_conditional_fine_v1 as test
q=test.q;job,api=q.job,q.api;BASE=test.BASE;OUT=BASE/'conditional_fine_independent_audit_01'

def run():
    w=api.read(q.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'audit work clock');d=api.read(job.DESIGN);job.verify(d)
    p=api.read(test.DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);r=api.read(test.OUT/'results.json')
    api.require(r['passed'] and api.read(test.OUT/'completion.json')['results_sha256']==api.sha(test.OUT/'results.json'),'completion seal');api.verify_mapping(r['artifacts'])
    launch=api.read(test.RUN/'launch.json');api.require(not psutil.pid_exists(launch['pid']),'fine worker retired')
    initial=q.independent_file(test.INITIAL_RAW,api.sha(test.INITIAL_DESIGN))['result']['checkpoint'];selected=q.independent_file(test.SELECTED_RAW,api.sha(test.SELECTED_DESIGN))
    seed=api.read(test.RUN/'conditional_seed.json');case=p['case'];before=seed['fine_checkpoint']
    api.require(api.digest(initial)==seed['source_checkpoint_sha256'] and api.digest(before)==seed['fine_checkpoint_sha256'],'exact conditional seed seals')
    api.require(before==job.parent.model.checkpoint(case['spec'],p['original_binding'],initial,True),'only declared conditional contract rebind')
    OUT.mkdir(parents=True,exist_ok=False);inputs={str(x):api.sha(x) for x in (Path(__file__),test.DESIGN,test.OUT/'results.json',test.OUT/'completion.json',q.WORK)}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0})
    rows=[];audits=[];total=0;job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        _,data,meta=api.fields.load(2,1.,6);geometry=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
        for i in range(4):
            path=test.RUN/f'call_{i+1:02d}.json.xz';record=q.independent_file(path,api.sha(test.DESIGN));account=api.read(test.RUN/f'call_{i+1:02d}.accounting.json');cl=api.read(test.RUN/f'call_{i+1:02d}.launch.json')
            api.require(api.digest(before)==cl['input_checkpoint_sha256']==record['input_checkpoint_sha256'],'complete predecessor binding')
            api.require(len(record['rows'])==account['accepted_steps']==cl['cap']==512 and account['raw_sha256']==api.sha(path),'exact capped call and raw SHA')
            check=test.auditor.kernel(record,case['spec'],p['original_binding'],before,geometry,api.sha(test.DESIGN),d['minimum_gap_semantics'])
            total+=512;api.require(account['cumulative_new_steps']==total,'cumulative ledger');rows+=record['rows'];before=record['result']['checkpoint'];audits.append(check)
            print('INDEPENDENT_FINE',i,check['passed'],flush=True)
    state=initial['state'];start=state['t'];sp=importlib.util.spec_from_file_location('stage194_verified_local_metrics',test.PAIR_AUDITOR);metrics=importlib.util.module_from_spec(sp);sp.loader.exec_module(metrics)
    def arr(items):return np.asarray([[0.,*state['x'],*state['p'],*state['q']]]+[[row['time_s']-start,*row['position_m'],*row['orientation'],*row['velocity_generalized']] for row in items])
    cfg=case['spec']['config'];m=metrics.metrics(arr(selected['rows']),arr(rows),cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
    api.require(m==r['local_comparison']['metrics'],'independent exact common-clock metric reconstruction')
    checks={k:m[k]<=p['frozen_numerical_gates'][k] for k in ('whole_position_over_b_max','whole_axis_vector_norm_max','endpoint_q_over_U_max','mean_L1_q_over_U_max')}
    api.require(all(checks.values()) and before['state']['t']==selected['result']['time_s'],'local kinematic gates and matched observed end')
    ledger=api.read(BASE/'early_restart_independent_closure_01/results.json');api.require(ledger['window_total_new_steps']==21700 and r['new_accepted_steps']==total==2048,'full known ledger')
    api.verify_mapping(inputs);api.verify_mapping(r['artifacts']);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    result={'passed':True,'new_trajectory_steps':0,'fine_steps_verified':total,'window_total_new_steps':23748,'remaining_step_allowance':26252,
      'local_metrics':m,'local_checks':checks,'audits':audits,'local_interval_start_s':start,'local_interval_end_s':before['state']['t'],
      'conditional_not_fresh':True,'complete_observation':False,'full_pair_gate_passed':False,'dwell_exit_event_convergence_demonstrated':False,
      'no_release_or_validation_claim':True,'production_authorized':False,'worker_retired':True,'free_disk_bytes':shutil.disk_usage(q.ROOT).free,'inputs':inputs}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')});print('FINE_INDEPENDENT_CLOSURE',23748,flush=True)

if __name__=='__main__':run()
