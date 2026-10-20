"""Independent sealed local-evidence closure, not a production evaluator."""
from pathlib import Path
import copy,os,sys,time,traceback
import numpy as np
import bounded_contact_diagnostic_v1 as runner
import audit_two_contact_routes_v2 as oldaudit
import audit_two_contact_dispatch_v3 as newaudit
job,api,ROOT,source=runner.job,runner.api,runner.ROOT,runner.source
BASE=runner.EVALBASE;RUN=runner.RUNBASE
OUT=BASE/'local_closure_01'
EXPECTED=('local_replay_01','continuation_01','restart_a_01','restart_b_01','dispatch_replay_01','dispatch_full_01','dispatch_split_a_01','dispatch_split_b_01')


def run():
    w=api.read(source.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work cutoff')
    d=api.read(job.DESIGN);job.verify(d);case=next(c for c in d['cases'] if c['id']==source.NAME);geom=runner.geometry(case)
    used,pending=runner.ledger();api.require(not pending and used<=w['maximum_new_accepted_trajectory_steps'],'resolved complete step ledger');runner.require_no_diagnostic()
    files=[source.WORK,job.DESIGN,Path(__file__)];records={};states={};reports=[]
    for name in EXPECTED:
        p=runner.DESIGNBASE/(name+'.json');r=RUN/name/'results.json';api.require(p.exists() and r.exists(),'complete preregistered closure set')
        files += [p,r,r.parent/'completion.json',r.parent/'accounting.json',r.parent/'launch.json']
    bindings={str(f):api.sha(f) for f in files};OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'inputs':bindings})
    failure=None;comparisons={};guards=[]
    try:
        for name in EXPECTED:
            p=api.read(runner.DESIGNBASE/(name+'.json'));r=runner.sealed_result(RUN/name/'results.json');api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources']);api.verify_mapping(r['artifacts'])
            seed=p['seed_diagnostic']
            if seed is None:before=api.read(runner.RECON/'checkpoint_00196.json');prefix=runner.prefix196()
            else:before=records[seed]['result']['checkpoint'];prefix=states[seed]
            raw=RUN/name/'call.json.xz';rec,state=runner.frozen.pre.storage.codec.read_record(raw,api.sha(job.DESIGN),prefix)
            api.require(api.digest(before)==rec['input_checkpoint_sha256'],'exact input state lineage')
            steps=rec['result']['steps']-before['state']['steps'];account=api.read(RUN/name/'accounting.json')
            api.require(steps==account['accepted_steps']==r['steps'] and 0<steps<=p['maximum_new_steps'],'complete exact accepted-step accounting')
            api.require(account['raw_sha256']==api.sha(raw) and account['launch_sha256']==api.sha(RUN/name/'launch.json'),'raw/step ledger binding')
            audit=newaudit if p['candidate']==newaudit.repair.NAME else oldaudit
            check=audit.kernel(rec,case['spec'],job.binding(d,case),before,geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
            api.require(check['passed'] and rec['result']['rejected']==0,'original full numerical gates and zero rejected trials')
            api.require(rec['result']['checkpoint']==api.read(RUN/name/'checkpoint.json'),'exact saved checkpoint')
            records[name]=rec;states[name]=state;reports.append({'name':name,'passed':True,'steps':steps,'audit':check,'raw_sha256':api.sha(raw),'protocol_sha256':api.sha(runner.DESIGNBASE/(name+'.json'))});print('RE_AUDIT',name,steps,flush=True)
        comparisons['v2_split_all_rows_exact']=records['continuation_01']['rows']==records['restart_a_01']['rows']+records['restart_b_01']['rows']
        comparisons['v2_split_full_checkpoint_exact']=records['continuation_01']['result']['checkpoint']==records['restart_b_01']['result']['checkpoint']
        comparisons['v3_vs_v2_all_157_rows_exact']=records['dispatch_replay_01']['rows']==records['continuation_01']['rows']
        comparisons['v3_vs_v2_full_checkpoint_exact']=records['dispatch_replay_01']['result']['checkpoint']==records['continuation_01']['result']['checkpoint']
        comparisons['v3_full_split_all_rows_exact']=records['dispatch_full_01']['rows']==records['dispatch_split_a_01']['rows']+records['dispatch_split_b_01']['rows']
        comparisons['v3_full_split_complete_checkpoint_exact']=records['dispatch_full_01']['result']['checkpoint']==records['dispatch_split_b_01']['result']['checkpoint']
        comparisons['v3_pre_failure_9760_original_rows_exact']=records['dispatch_full_01']['rows'][:9760]==records['local_replay_01']['rows'][:9760]
        comparisons['v3_matches_v2_9806_local_rows']=records['dispatch_full_01']['rows'][:9806]==records['local_replay_01']['rows']
        good=api.read(BASE/'dispatch_qualification_03/fixture_00.json')
        def change(r,key,value):
            if isinstance(r,dict):
                if r.get('solver')==newaudit.repair.NAME:r[key]=copy.deepcopy(value)
                for val in r.values():change(val,key,value)
            elif isinstance(r,list):
                for val in r:change(val,key,value)
        f=good['fixture']['fallback_systems'][0]['health']['reactions']
        badnormal=list(f);badnormal[0]=-abs(badnormal[0]);badcone=list(f);badcone[1]+=1e-6
        mutations=[('negative_normal','reactions',badnormal),('friction_cone','reactions',badcone),('false_dispatch','scalar_dispatch_policy','unqualified'),('falsely_claim_mixed_attempt','original_mixed_attempted',True),('false_iterations','iterations',1001)]
        for label,key,value in mutations:
            bad=copy.deepcopy(good['fixture']);change(bad,key,value)
            try:newaudit.evaluate(bad,good['before'])
            except (RuntimeError,ValueError,KeyError,IndexError,AssertionError):guards.append({'test':label,'rejected':True})
            else:guards.append({'test':label,'rejected':False})
        api.require(all(comparisons.values()) and all(g['rejected'] for g in guards),'exact restart/trajectory and adversarial closure')
    except Exception as error:failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(bindings);job.verify(d)
    r={'passed':failure is None and len(reports)==len(EXPECTED),'new_trajectory_steps':0,'window_total_accepted_steps':used,'unresolved_reservations':pending,'raw_numerical_reaudits':reports,'exact_comparisons':comparisons,'mutation_rejections':guards,'inputs':bindings,'failure':failure,
       'local_157_step_compute_speedup':records['continuation_01']['compute_call_wall_s']/records['dispatch_replay_01']['compute_call_wall_s'] if 'dispatch_replay_01' in records else None,
       'claim':'Local independent numerical/storage/restart qualification. Stage200 remains failed/incomplete. No full-path, release, empirical validation or production authorization.'}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')});print('LOCAL_CLOSURE',r['passed'],used,flush=True)


if __name__=='__main__':run()
