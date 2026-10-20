"""128-step serial versus 64+64 restart; all 256 new steps are budgeted."""
from pathlib import Path
from datetime import timedelta
import copy,os,shutil,sys,traceback,types
import psutil
import qualify_failure_codec_v1 as q
import projection_fallback_dispatch_v1 as repair
import audit_projection_routes_v2 as auditor
job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/dispatch_restart_01.json'
RUN=q.ROOT/'stage194_runs/evidence_repair_20260924/dispatch_restart_01';OUT=BASE/'dispatch_restart_01'
PRIOR=q.ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json'
OLD_RUN=q.ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01'

def prerequisites():
    w=api.read(q.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc'])-timedelta(seconds=900),'diagnostic launch clock')
    d=api.read(job.DESIGN);job.verify(d)
    for name in ('fallback_dispatch_qualification_01','trajectory_qualification_01'):
        r=api.read(BASE/name/'results.json');api.require(r['passed'] and api.read(BASE/name/'completion.json')['results_sha256']==api.sha(BASE/name/'results.json'),'qualified '+name)
        api.verify_mapping(r['artifacts'])
    for proto in (PRIOR,DESIGN.with_name('fallback_dispatch_qualification_01.json')):
        p=api.read(proto);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    api.require(api.read(BASE/'trajectory_qualification_01/results.json')['window_total_new_steps']==19341,'previous exact window total')
    return w,d

def prepare():
    w,d=prerequisites();old=api.read(PRIOR);paths=[q.WORK,job.DESIGN,PRIOR,BASE/'trajectory_qualification_01/results.json',BASE/'fallback_dispatch_qualification_01/results.json',DESIGN.with_name('fallback_dispatch_qualification_01.json')]
    paths+=list(Path(__file__).parent.glob('*.py'))+list(OLD_RUN.glob('*'))
    p={'stage':'Stage194 bounded fallback dispatch exact restart','case':old['case'],'prior_new_steps':19341,'call_caps':[128,64,64],
       'maximum_new_steps':256,'maximum_window_steps_after_reservation':19597,'sources':d['sources'],'inputs':{str(x):api.sha(x) for x in paths if x.is_file()},
       'original_binding':old['original_binding'],'physics_timestep_horizon_gate_changes':[],
       'integration_code_sha256':q.campaign.code_sha(job.execute_segment),'execute_namespace_changes':['DESIGN','codec'],
       'production_authorized':False,'claim':'Local conditional numerical and restart verification, not a full observation.'}
    api.require(p['maximum_window_steps_after_reservation']<=w['maximum_new_accepted_trajectory_steps'],'step reserve')
    job.commit(DESIGN,p);print('RESTART_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    w,d=prerequisites();p=api.read(DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);api.require(not RUN.exists() and not OUT.exists(),'exclusive run')
    allowed={'diagnostic_replay_01','trajectory_qualification_01'}
    for path in (q.ROOT/'stage194_runs').rglob('launch.json'):
        if api.read(path).get('reserved_new_accepted_steps',0)>0:api.require(path.parent.name in allowed,'no unresolved/other trajectory reservation')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.info['pid']==os.getpid() or 'python' not in (proc.info['name'] or '').lower():continue
        command=' '.join(proc.info['cmdline'] or []).lower();api.require('matdem_microplastic' not in command and 'stage194_staging' not in command,'single worker')
    api.require(shutil.disk_usage(q.ROOT).free>w['minimum_free_disk_bytes']+2*q.repair.base.MAX_RAW,'disk reserve')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(minutes=10),job.policy.utc(w['work_end_utc'])-timedelta(seconds=900)).isoformat()
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop,'reserved_new_accepted_steps':256,
       'protocol_sha256':api.sha(DESIGN),'prior_window_steps':19341,'blas_threads':1})
    source=q.independent_file(OLD_RUN/'call_01.json.xz',api.sha(PRIOR));oracle=q.independent_file(OLD_RUN/'call_02.json.xz',api.sha(PRIOR))
    initial=source['result']['checkpoint'];case=p['case'];binding=p['original_binding'];total=0;records=[];summaries=[];failure=None
    ns={**job.execute_segment.__globals__,'DESIGN':DESIGN,'codec':q.repair.codec}
    execute=types.FunctionType(job.execute_segment.__code__,ns,'execute_segment',job.execute_segment.__defaults__,job.execute_segment.__closure__)
    api.require(q.campaign.code_sha(execute)==p['integration_code_sha256'] and execute.__code__ is job.execute_segment.__code__,'integration bytecode identity')
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            _,data,meta=api.fields.load(2,1.,6);geometry=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            for i,cap in enumerate(p['call_caps']):
                api.require(job.utc()<job.policy.utc(stop),'call clock');api.require(shutil.disk_usage(q.ROOT).free>w['minimum_free_disk_bytes']+2*q.repair.base.MAX_RAW,'disk reserve')
                before=copy.deepcopy(initial if i<2 else records[1]['result']['checkpoint']);raw=RUN/f'call_{i+1:02d}.json.xz'
                job.commit(RUN/f'call_{i+1:02d}.launch.json',{'input_checkpoint_sha256':api.digest(before),'cap':cap,'utc':job.utc().isoformat(),'known_steps_before_call':total})
                with repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):record,_,_,elapsed=execute(d,case,before,raw,cap,None,stop)
                total+=len(record['rows']);records.append(record)
                job.commit(RUN/f'call_{i+1:02d}.accounting.json',{'accepted_steps':len(record['rows']),'cumulative_new_steps':total,'status':record['result']['status'],
                   'rejected_total':record['result']['rejected'],'raw_sha256':api.sha(raw)})
                api.require(total<=256 and 19341+total<=50000,'step accounting')
                independent=q.independent_file(raw,api.sha(DESIGN));api.require(q.repair.base.raw_bytes(independent)==q.repair.base.raw_bytes(record),'independent complete raw identity')
                check=auditor.kernel(independent,case['spec'],binding,before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])
                entry={'index':i,'steps':len(record['rows']),'transaction_seconds':elapsed,'audit':check,'raw_sha256':api.sha(raw)}
                summaries.append(entry);job.commit(OUT/f'call_{i+1:02d}.audit.json',entry)
                api.require(len(record['rows'])==cap,'complete bounded diagnostic call')
                if i==0:api.require(record['rows'][:55]==oracle['rows'],'exact previously accepted 55-step path')
                print('RESTART_CALL_AUDITED',i,len(record['rows']),elapsed,flush=True)
            api.require(records[0]['rows']==records[1]['rows']+records[2]['rows'],'exact split rows')
            api.require(records[0]['result']['checkpoint']['state']==records[2]['result']['checkpoint']['state'],'exact complete split checkpoint state')
    except Exception as e:
        failure={'error':repr(e),'traceback':traceback.format_exc(),'known_new_steps':total};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    r={'passed':failure is None and len(summaries)==3,'new_accepted_steps':total,'window_total_new_steps':19341+total,'reserved_new_steps':256,
       'calls':summaries,'failure':failure,'exact_restart':failure is None,'protocol_sha256':api.sha(DESIGN),'complete_observation':False,
       'production_authorized':False,'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()},'claim':p['claim']}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('RESTART_RESULT',r['passed'],total,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
