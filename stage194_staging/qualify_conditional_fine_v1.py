"""Original fine timestep from one explicitly shared conditional checkpoint.

No fresh campaign or full-path refinement claim: the selected checkpoint's
physical state is copied exactly and only its contract is rebound to the
original frozen fine case. Four <=512-step calls reserve 2,048 new steps.
"""
from pathlib import Path
from datetime import timedelta
import copy,os,shutil,sys,traceback,types,importlib.util
import psutil
import numpy as np
import qualify_failure_codec_v1 as q
import early_semismooth_dispatch_v1 as repair
import audit_early_semismooth_v1 as auditor
job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/conditional_fine_01.json'
RUN=q.ROOT/'stage194_runs/evidence_repair_20260924/conditional_fine_01';OUT=BASE/'conditional_fine_01'
INITIAL_DESIGN=DESIGN.with_name('trajectory_qualification_01.json')
INITIAL_RAW=q.ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_01.json.xz'
SELECTED_DESIGN=DESIGN.with_name('early_semismooth_restart_01.json')
SELECTED_RAW=q.ROOT/'stage194_runs/evidence_repair_20260924/early_semismooth_restart_01/call_01.json.xz'
PAIR_AUDITOR=q.ROOT/'stage167_staging/audit_paired_deadline_campaign_v3.py'

def prerequisites():
    w=api.read(q.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc'])-timedelta(seconds=900),'launch margin')
    d=api.read(job.DESIGN);job.verify(d)
    closure=BASE/'early_restart_independent_closure_01';r=api.read(closure/'results.json')
    api.require(api.read(closure/'completion.json')['results_sha256']==api.sha(closure/'results.json'),'independent closure seal')
    api.require(r['diagnostic_numerical_and_evidence_audit_passed'] and not r['launcher_metadata_schema_passed'] and r['window_total_new_steps']==21700,'explicit immutable typo adjudication and step total')
    p=api.read(SELECTED_DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    api.verify_mapping(api.read(BASE/'early_semismooth_restart_01/results.json')['artifacts'])
    return w,d

def prepare():
    w,d=prerequisites();fine=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125');selected=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p0625')
    paths=[q.WORK,job.DESIGN,INITIAL_DESIGN,INITIAL_RAW,SELECTED_DESIGN,SELECTED_RAW,PAIR_AUDITOR,BASE/'early_restart_independent_closure_01/results.json',BASE/'early_restart_independent_closure_01/completion.json']+list(Path(__file__).parent.glob('*.py'))
    p={'stage':'Stage194 conditional original fine-timestep diagnostic','case':fine,'selected_case':selected,'original_binding':job.binding(d,fine),
       'prior_new_steps':21700,'call_caps':[512,512,512,512],'maximum_new_steps':2048,'maximum_window_steps_after_reservation':23748,
       'inputs':{str(x):api.sha(x) for x in paths},'sources':d['sources'],'initial_state_source_raw_sha256':api.sha(INITIAL_RAW),
       'conditional_contract_rebind_only':True,'physical_state_history_and_clock_must_remain_exact':True,'original_fine_numerics_unchanged':True,
       'frozen_numerical_gates':d['numerical_gates'],'integration_code_sha256':q.campaign.code_sha(job.execute_segment),
       'production_authorized':False,'full_fresh_pair_claim':False,'claim':'Local conditional step-size check; no complete observation or full fresh paired campaign gate.'}
    api.require(p['maximum_window_steps_after_reservation']<=w['maximum_new_accepted_trajectory_steps'],'step reserve');job.commit(DESIGN,p);print('CONDITIONAL_FINE_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    w,d=prerequisites();p=api.read(DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);api.require(not RUN.exists() and not OUT.exists(),'exclusive new diagnostic')
    allowed={'diagnostic_replay_01','trajectory_qualification_01','dispatch_restart_01','semismooth_restart_01','early_semismooth_restart_01'}
    for path in (q.ROOT/'stage194_runs').rglob('launch.json'):
        if api.read(path).get('reserved_new_accepted_steps',0)>0:api.require(path.parent.name in allowed,'no other diagnostic reservation')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.info['pid']==os.getpid() or 'python' not in (proc.info['name'] or '').lower():continue
        command=' '.join(proc.info['cmdline'] or []).lower();api.require('matdem_microplastic' not in command and 'stage194_staging' not in command,'one simulation worker')
    api.require(shutil.disk_usage(q.ROOT).free>w['minimum_free_disk_bytes']+2*q.repair.base.MAX_RAW,'disk reserve')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(minutes=10),job.policy.utc(w['work_end_utc'])-timedelta(seconds=900)).isoformat()
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop,'reserved_new_accepted_steps':2048,'prior_window_steps':21700,'protocol_sha256':api.sha(DESIGN),'blas_threads':1})
    initial=q.independent_file(INITIAL_RAW,api.sha(INITIAL_DESIGN))['result']['checkpoint'];selected=q.independent_file(SELECTED_RAW,api.sha(SELECTED_DESIGN));case=p['case'];binding=p['original_binding']
    before=job.parent.model.checkpoint(case['spec'],binding,initial,True)
    api.require(before['state']==initial['state'] and set(before)==set(initial),'only declared checkpoint contract rebind')
    api.require({k:v for k,v in before.items() if k!='contract'}=={k:v for k,v in initial.items() if k!='contract'},'all noncontract checkpoint fields preserved')
    job.commit(RUN/'conditional_seed.json',{'source_checkpoint_sha256':api.digest(initial),'fine_checkpoint':before,'fine_checkpoint_sha256':api.digest(before),'claim':p['claim']})
    ns={**job.execute_segment.__globals__,'DESIGN':DESIGN,'codec':q.repair.codec};execute=types.FunctionType(job.execute_segment.__code__,ns,'execute_segment',job.execute_segment.__defaults__,job.execute_segment.__closure__)
    api.require(q.campaign.code_sha(execute)==p['integration_code_sha256'],'unchanged integration bytecode')
    total=0;rows=[];reports=[];failure=None;local=None
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            _,data,meta=api.fields.load(2,1.,6);geometry=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            for i,cap in enumerate(p['call_caps']):
                api.require(job.utc()<job.policy.utc(stop),'bounded call clock');api.require(shutil.disk_usage(q.ROOT).free>w['minimum_free_disk_bytes']+2*q.repair.base.MAX_RAW,'disk reserve')
                raw=RUN/f'call_{i+1:02d}.json.xz';job.commit(RUN/f'call_{i+1:02d}.launch.json',{'input_checkpoint_sha256':api.digest(before),'cap':cap,'utc':job.utc().isoformat(),'known_new_steps':total})
                with repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):record,_,_,elapsed=execute(d,case,before,raw,cap,None,stop)
                n=len(record['rows']);total+=n;rows+=record['rows']
                job.commit(RUN/f'call_{i+1:02d}.accounting.json',{'accepted_steps':n,'cumulative_new_steps':total,'raw_sha256':api.sha(raw),'rejected_total':record['result']['rejected'],'status':record['result']['status']})
                api.require(total<=2048 and 21700+total<=50000,'step ledger')
                independent=q.independent_file(raw,api.sha(DESIGN));api.require(q.repair.base.raw_bytes(independent)==q.repair.base.raw_bytes(record),'complete independent decoder identity')
                check=auditor.kernel(independent,case['spec'],binding,before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])
                report={'index':i,'steps':n,'audit':check,'compute_seconds':record['compute_call_wall_s'],'transaction_seconds':elapsed,'raw_sha256':api.sha(raw)}
                reports.append(report);job.commit(OUT/f'call_{i+1:02d}.audit.json',report);print('CONDITIONAL_FINE_AUDIT',i,n,elapsed,flush=True)
                api.require(n==cap,'complete bounded diagnostic call');before=record['result']['checkpoint']
        # The original common-clock metric is reused on this local interval,
        # subtracting the same exact checkpoint time from BOTH trace clocks.
        spec=importlib.util.spec_from_file_location('stage194_exact_pair_metrics',PAIR_AUDITOR);metric=importlib.util.module_from_spec(spec);spec.loader.exec_module(metric)
        state=initial['state'];start=state['t']
        def array(items):return np.asarray([[0.,*state['x'],*state['p'],*state['q']]]+[[r['time_s']-start,*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in items],float)
        cfg=case['spec']['config'];m=metric.metrics(array(selected['rows']),array(rows),cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
        gates=p['frozen_numerical_gates'];checks={key:m[key]<=gates[key] for key in ('whole_position_over_b_max','whole_axis_vector_norm_max','endpoint_q_over_U_max','mean_L1_q_over_U_max')}
        da=selected['result']['checkpoint']['state']['monitor'];db=before['state']['monitor']
        local={'passed':all(checks.values()),'metrics':m,'checks':checks,'selected_observed_end_s':selected['result']['time_s'],'fine_observed_end_s':before['state']['t'],
           'selected_monitor':da,'fine_monitor':db,'claim':p['claim'],'full_fresh_campaign_gate_passed':False,'complete_observation':False}
        job.commit(OUT/'local_common_clock_comparison.json',local);api.require(local['passed'],'original local velocity/pose gates')
    except Exception as e:failure={'error':repr(e),'traceback':traceback.format_exc(),'known_new_steps':total};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    r={'passed':failure is None and len(reports)==4,'new_accepted_steps':total,'window_total_new_steps':21700+total,'remaining_step_allowance':50000-21700-total,
       'calls':reports,'failure':failure,'local_comparison':local,'protocol_sha256':api.sha(DESIGN),'complete_observation':False,'production_authorized':False,
       'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()},'claim':p['claim']}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')});print('CONDITIONAL_FINE_RESULT',r['passed'],total,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
