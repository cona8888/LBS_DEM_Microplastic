"""One worker, 9,641-step exact prefix plus <=1,000 repaired diagnostic steps.

New immutable evidence only. Original campaign remains failed. All returned
raw data are persisted before strict audit; no production or continuation loop.
"""
from pathlib import Path
from datetime import timedelta
import copy,os,shutil,sys,traceback,types
import psutil
import qualify_failure_codec_v1 as q
import sliding_projection_repair_v3 as repair
import audit_projection_routes_v2 as auditor

job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json'
RUN=q.ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01';OUT=BASE/'trajectory_qualification_01'


def prerequisites():
    w=api.read(q.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc'])-timedelta(seconds=900),'diagnostic launch clock')
    d=api.read(job.DESIGN);job.verify(d)
    for name in ('sliding_qualification_03','outer_qualification_01','route_audit_qualification_02'):
        root=BASE/name;r=api.read(root/'results.json');api.require(r['passed'] and api.read(root/'completion.json')['results_sha256']==api.sha(root/'results.json'),'qualified '+name)
    for name in ('sliding_qualification_03_sources.json','route_audit_sources_02.json'):
        api.verify_mapping(api.read(DESIGN.with_name(name))['source_sha256'])
    r=api.read(BASE/'diagnostic_independent_audit_01/results.json')
    api.require(r['provenance_accounting_audit_passed'] and not r['numerical_campaign_gate_passed'] and r['window_new_steps_accounted']==9645,'prior failed step ledger')
    seedpath=BASE/'seed_extraction_01/diagnostic_seed_01.json';seed=api.read(seedpath)
    api.require(api.sha(seedpath)==api.read(BASE/'seed_extraction_01/results.json')['seed_sha256'],'verified diagnostic seed')
    return w,d,seed


def prepare():
    w,d,seed=prerequisites();case=next(c for c in d['cases'] if c['id']==seed['case'])
    paths=[q.WORK,job.DESIGN,BASE/'seed_extraction_01/diagnostic_seed_01.json',BASE/'diagnostic_independent_audit_01/results.json']
    paths+=list(Path(__file__).parent.glob('*.py'))
    for name in ('sliding_qualification_03','outer_qualification_01','route_audit_qualification_02','diagnostic_replay_01'):
        paths+=list((BASE/name).glob('*.json'))
    paths+=[DESIGN.with_name(n) for n in ('sliding_qualification_03_sources.json','route_audit_sources_02.json')]
    p={'stage':'Stage194 bounded original-law trajectory qualification','case':case,'prior_new_steps':9645,'call_caps':[9641,1000],
       'maximum_new_steps':10641,'maximum_window_steps_after_reservation':20286,'sources':d['sources'],
       'inputs':{str(x):api.sha(x) for x in paths},'original_design_sha256':api.sha(job.DESIGN),'original_binding':job.binding(d,case),
       'frozen_numerical_gates':d['numerical_gates'],'physical_and_timestep_changes':[],
       'integration_code_sha256':q.campaign.code_sha(job.execute_segment),'execute_namespace_changes':['DESIGN','codec'],
       'routing_auditor_identity':auditor.STRUCTURAL_IDENTITY,'original_numerical_kernel_bytecode':q.campaign.code_sha(job.kernel.evaluate),
       'prefix_requires_exact_original_rows':9641,'production_authorized':False,
       'claim':'Local conditional numerical test only, not full-path, release or empirical-validation evidence.'}
    api.require(p['maximum_window_steps_after_reservation']<=w['maximum_new_accepted_trajectory_steps'],'work step reserve')
    job.commit(DESIGN,p);print('TRAJECTORY_PROTOCOL_FROZEN',api.sha(DESIGN),flush=True)


def run():
    w,d,seed=prerequisites();p=api.read(DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    api.require(not RUN.exists() and not OUT.exists(),'exclusive new run')
    prior_launch=q.ROOT/'stage194_runs/evidence_repair_20260924/diagnostic_replay_01/launch.json'
    for path in (q.ROOT/'stage194_runs').rglob('launch.json'):
        if api.read(path).get('reserved_new_accepted_steps',0)>0:api.require(path==prior_launch,'no competing step reservation')
    for proc in psutil.process_iter(['pid','cmdline','name']):
        if proc.info['pid']==os.getpid() or 'python' not in (proc.info['name'] or '').lower():continue
        command=' '.join(proc.info['cmdline'] or []).lower()
        api.require('matdem_microplastic' not in command and 'stage194_staging' not in command,'no other workspace Python worker')
    api.require(shutil.disk_usage(q.ROOT).free>w['minimum_free_disk_bytes']+2*q.repair.base.MAX_RAW,'disk reserve')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(minutes=15),job.policy.utc(w['work_end_utc'])-timedelta(seconds=900)).isoformat()
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop,
               'reserved_new_accepted_steps':p['maximum_new_steps'],'protocol_sha256':api.sha(DESIGN),'prior_window_steps':9645,'blas_threads':1})
    oldraw=q.independent_file(q.ROOT/'stage194_runs/evidence_repair_20260924/diagnostic_replay_01/diagnostic.json.xz',api.sha(job.DESIGN))
    namespace=dict(job.execute_segment.__globals__);namespace.update(codec=q.repair.codec,DESIGN=DESIGN)
    execute=types.FunctionType(job.execute_segment.__code__,namespace,'execute_segment',job.execute_segment.__defaults__,job.execute_segment.__closure__)
    api.require(q.campaign.code_sha(execute)==p['integration_code_sha256'] and execute.__code__ is job.execute_segment.__code__,'identical integration bytecode')
    api.require(sorted(k for k in namespace if namespace[k] is not job.execute_segment.__globals__[k])==p['execute_namespace_changes'],'only declared namespace substitutions')
    before=copy.deepcopy(seed['checkpoint']);case=p['case'];total=0;summaries=[];failure=None
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            _,data,meta=api.fields.load(2,1.,6);geometry=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            for index,cap in enumerate(p['call_caps']):
                api.require(job.utc()<job.policy.utc(stop),'bounded work call clock')
                api.require(shutil.disk_usage(q.ROOT).free>w['minimum_free_disk_bytes']+2*q.repair.base.MAX_RAW,'disk reserve')
                raw=RUN/f'call_{index+1:02d}.json.xz'
                job.commit(RUN/f'call_{index+1:02d}.launch.json',{'input_checkpoint_sha256':api.digest(before),'cap':cap,'utc':job.utc().isoformat(),'known_steps_before_call':total})
                with repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):
                    record,_,_,elapsed=execute(d,case,before,raw,cap,None,stop)
                n=len(record['rows']);total+=n
                job.commit(RUN/f'call_{index+1:02d}.accounting.json',{'accepted_steps':n,'cumulative_new_steps':total,'rejected_total':record['result']['rejected'],'status':record['result']['status'],'raw_sha256':api.sha(raw)})
                api.require(total<=p['maximum_new_steps'] and 9645+total<=50000,'window accounting')
                independent=q.independent_file(raw,api.sha(DESIGN))
                api.require(q.repair.base.raw_bytes(record)==q.repair.base.raw_bytes(independent),'complete independent decode identity')
                if index==0:api.require(record['rows']==oldraw['rows'][:n],'exact original healthy prefix')
                check=auditor.kernel(independent,case['spec'],p['original_binding'],before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])
                entry={'index':index,'steps':n,'transaction_seconds':elapsed,'exact_old_prefix':index==0,'audit':check,'raw_sha256':api.sha(raw)}
                summaries.append(entry);job.commit(OUT/f'call_{index+1:02d}.audit.json',entry)
                print('TRAJECTORY_AUDITED',index,n,record['result']['rejected'],check['stop_s'],flush=True)
                before=record['result']['checkpoint']
                if index==0 and n<cap:break
    except Exception as error:
        failure={'error':repr(error),'traceback':traceback.format_exc(),'known_new_steps':total,'reserved_steps':p['maximum_new_steps']}
        job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    result={'passed':failure is None and len(summaries)==2,'new_accepted_steps':total,'window_total_new_steps':9645+total,
            'reserved_new_steps':p['maximum_new_steps'],'calls':summaries,'failure':failure,'protocol_sha256':api.sha(DESIGN),
            'complete_observation':False,'production_authorized':False,'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()},
            'claim':p['claim']}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('TRAJECTORY_QUALIFICATION',result['passed'],total,flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
