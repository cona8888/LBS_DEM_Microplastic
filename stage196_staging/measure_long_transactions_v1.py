"""Two bounded diagnostic transactions; original integration and 45-s call cap.

Measure the repaired-contact regime before spending budget on broader cost
sampling. Partial calls are sealed/accounted and never counted as full passes.
"""
from pathlib import Path
from datetime import timedelta
import copy, os, psutil, shutil, sys, time, traceback
import qualify_performance_stack_v1 as pre
job,api,q=pre.job,pre.api,pre.q
ROOT=pre.ROOT
DESIGN=ROOT/'stage196_designs/deadline_recovery_20260925/long_transactions_01.json'
RUN=Path('D:/MATDEM_MICROPLASTIC/stage196_runs/deadline_recovery_20260925/long_transactions_01')
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/long_transactions_01'
AUDIT=job.OUT/'independent_readiness_01/results.json'
SEED=ROOT/'stage194_evaluations/evidence_repair_20260924/seed_extraction_01/diagnostic_seed_01.json'
ORACLE=ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_01.json.xz'
ORACLE_DESIGN=ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json'


def prepare():
    d=api.read(job.DESIGN);job.verify(d);a=api.read(AUDIT)
    api.require(a['numerical_qualification_passed'] and a['process_qualification_passed'] and a['window_new_accepted_steps']==25326,'independent preflight prerequisite')
    api.require(api.read(AUDIT.parent/'completion.json')['results_sha256']==api.sha(AUDIT),'audit seal')
    inputs=[pre.wrapper.WORK,job.DESIGN,AUDIT,AUDIT.parent/'completion.json',SEED,ORACLE,ORACLE.with_suffix('.seal.json'),ORACLE_DESIGN]
    p={'stage':'Stage196 bounded long-transaction resource measurement','prior_window_steps':25326,
       'calls':[{'label':'repaired_contact','steps':10000},{'label':'healthy_prefix','steps':9641}],
       'maximum_new_steps':19641,'maximum_window_steps':44967,'one_worker':True,'logical_cpu':14,
       'immutable_integration_design_sha256':api.sha(job.DESIGN),'sources':{str(Path(__file__).resolve()):api.sha(__file__)},
       'inputs':{str(x):api.sha(x) for x in inputs},'physics_timestep_gate_changes':[],
       'stop_on_incomplete':True,'new_production_authorized':False,
       'claim':'Local diagnostics only; no completed observation or deadline fit from these calls alone.'}
    p['binding']=api.digest(p);job.commit(DESIGN,p);print('LONG_TRANSACTIONS_FROZEN',api.sha(DESIGN),flush=True)


def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'protocol binding')
    api.verify_mapping(p['sources']);api.verify_mapping(p['inputs']);job.verify(api.read(job.DESIGN))


def run():
    p=api.read(DESIGN);verify(p);d=api.read(job.DESIGN);w=api.read(pre.wrapper.WORK)
    api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc'])-timedelta(minutes=10),'launch reserve')
    api.require(p['maximum_window_steps']<=w['maximum_new_qualification_accepted_steps'],'step reserve')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'no competing simulation or benchmark')
    info=pre.wrapper.affinity.bind(p['logical_cpu'])
    api.require(shutil.disk_usage(RUN.parent).free>w['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'D reserve')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(minutes=10),job.policy.utc(w['last_diagnostic_launch_utc']))
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop.isoformat(),
        'protocol_sha256':api.sha(DESIGN),'maximum_new_steps':19641,'owned_affinity':info})
    reports=[];total=0
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            geo=pre.prior.geometry()
            for plan in p['calls']:
                api.require(job.utc()<stop-timedelta(seconds=120),'bounded diagnostic clock')
                case,cp=pre.stress_seed(d);oracle=None
                if plan['label']=='healthy_prefix':
                    saved=api.read(SEED);api.require(saved['case']==case['id'],'same selected fibre')
                    cp=job.parent.model.checkpoint(case['spec'],job.binding(d,case),saved['checkpoint'],True)
                    api.require(cp['state']==saved['checkpoint']['state'],'unchanged healthy seed')
                    oracle=q.independent_file(ORACLE,api.sha(ORACLE_DESIGN))
                path=RUN/(plan['label']+'.json.xz')
                job.commit(path.with_suffix('.launch.json'),{'utc':job.utc().isoformat(),'reserved_steps':plan['steps'],
                    'input_checkpoint_sha256':api.digest(cp),'protocol_sha256':api.sha(DESIGN)})
                rec,state,_,tx=job.execute_segment(d,case,copy.deepcopy(cp),path,plan['steps'],None,stop.isoformat())
                count=len(rec['rows']);total+=count
                job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':count,'rejected':rec['result']['rejected'],'raw_sha256':api.sha(path)})
                tick=time.perf_counter();decoded,rs=job.codec.read_record(path,api.sha(job.DESIGN));read_s=time.perf_counter()-tick
                api.require(rs==state and job.codec.base.raw_bytes(decoded)==job.codec.base.raw_bytes(rec),'full canonical storage identity')
                summary=job.kernel.evaluate(decoded,case['spec'],job.binding(d,case),cp,geo,api.sha(job.DESIGN),d['minimum_gap_semantics'])
                exact=None
                if oracle is not None:
                    exact=rec['rows']==oracle['rows'][:count]
                    if count==plan['steps']:exact=exact and rec['result']['checkpoint']['state']==oracle['result']['checkpoint']['state']
                    api.require(exact,'original healthy numerical identity')
                else:
                    reference=q.independent_file(Path(d['stress_oracle_raw']),api.sha(d['stress_oracle_design']))
                    overlap=min(count,len(reference['rows']));api.require(rec['rows'][:overlap]==reference['rows'][:overlap],'exact repaired known prefix')
                item={'label':plan['label'],'case':case['id'],'requested_steps':plan['steps'],'accepted_steps':count,
                    'complete_requested_call':count==plan['steps'] and rec['result']['status']=='paused_checkpoint',
                    'path':str(path),'raw_sha256':api.sha(path),'status':rec['result']['status'],'compute_seconds':rec['compute_call_wall_s'],
                    'transaction_seconds':tx,'read_seconds':read_s,'audit_seconds':summary['audit_seconds'],
                    'simulated_seconds':summary['stop_s']-summary['start_s'],'numerical_audit':summary,'exact_healthy_oracle':exact,
                    'compressed_bytes':path.stat().st_size,'input_checkpoint_sha256':api.digest(cp)}
                reports.append(item);job.commit(path.with_suffix('.measurement.json'),item)
                print('LONG_TRANSACTION',plan['label'],count,rec['result']['status'],'compute',rec['compute_call_wall_s'],'tx',tx,flush=True)
                if not item['complete_requested_call'] or not summary['passed']:break
        passed=len(reports)==2 and all(x['complete_requested_call'] and x['numerical_audit']['passed'] for x in reports)
        verify(p)
        r={'passed':passed,'measurements':reports,'new_accepted_steps':total,'prior_window_steps':25326,'window_new_accepted_steps':25326+total,
           'unlaunched_calls':[x for x in p['calls'] if x['label'] not in {y['label'] for y in reports}],
           'protocol_sha256':api.sha(DESIGN),'all_raw_saved':True,'production_authorized':False,
           'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()}}
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
        print('LONG_MEASUREMENTS_COMPLETE',passed,total,flush=True)
    except Exception as e:
        resolved=[];unresolved=[]
        for launch in RUN.glob('*.json.launch.json'):
            account=launch.with_name(launch.name.replace('.launch.json','.accounting.json'))
            if account.exists():resolved.append(api.read(account)['accepted_steps'])
            else:unresolved.append(str(launch))
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'known_new_accepted_steps':sum(resolved),'unresolved':unresolved});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
