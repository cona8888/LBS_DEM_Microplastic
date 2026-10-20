"""Bounded continuation of already-legal time-budget segments; no solver change.

The old exact-10000-step timing probes remain failed. This new contract tests
checkpoint continuation, exact partition identity and original numerical gates.
"""
from pathlib import Path
from datetime import timedelta
import copy, os, sys, time, traceback, shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage196_staging'))
import qualify_performance_stack_v1 as pre
import psutil
job,api=pre.job,pre.api
BASE='deadline_extension_20260926'
AUTH=ROOT/'stage197_designs'/BASE/'authorization_01.json'
DESIGN=AUTH.with_name('continuation_protocol_01.json')
RUN=Path('D:/MATDEM_MICROPLASTIC/stage197_runs')/BASE/'continuation_01'
OUT=ROOT/'stage197_evaluations'/BASE/'continuation_01'
OLD=Path('D:/MATDEM_MICROPLASTIC/stage196_runs/deadline_recovery_20260925/long_transactions_01/repaired_contact.json.xz')
COMPILED=OLD.parent.parent/'compiled_contact_01/record.json.xz'
COMPILED_DESIGN=ROOT/'stage196_designs/deadline_recovery_20260925/compiled_contact_01.json'
CLOSURE=ROOT/'stage196_evaluations/deadline_recovery_20260925/work_window_close_02/results.json'
AUDIT=Path(__file__).with_name('audit_budget_continuation_v1.py')

def prepare():
    d=api.read(job.DESIGN);job.verify(d);a=api.read(AUTH)
    api.require(api.sha(CLOSURE)=='bd7741bee9082431eb74a63186a0546fcc185618e8d1d9a8482fbf86e66461bb','frozen Stage196 closure')
    files=[AUTH,job.DESIGN,CLOSURE,CLOSURE.parent/'completion.json',OLD,OLD.with_suffix('.seal.json'),COMPILED,COMPILED.with_suffix('.seal.json'),COMPILED_DESIGN,
        job.OUT/'independent_readiness_01/results.json',job.OUT/'independent_readiness_01/completion.json']
    sources=[Path(__file__),AUDIT,ROOT/'stage167_staging/paired_deadline_campaign_v1.py',ROOT/'stage167_staging/audit_paired_deadline_campaign_v3.py',ROOT/'stage187_staging/integrated_paired_campaign_v1.py']
    p={'stage':'Stage197 audited time-budget continuation qualification','inputs':{str(p):api.sha(p) for p in files},'sources':{str(p):api.sha(p) for p in sources},
       'maximum_new_steps':21040,'calls':{'serial':270,'split_a':135,'split_b':135,'selected_long':10000,'selected_tail':500,'conditional_fine':10000},
       'prior_recovery_steps':35426,'one_worker':True,'logical_cpu':14,'wall_seconds':1200,'trajectory_design_sha256':api.sha(job.DESIGN),
       'legal_nonterminal_statuses':['paused_checkpoint','incomplete_budget'],
       'criteria':['all accepted rows pass original independent numerical/clock/health/balance gates','zero rejected trials','270 rows exactly reproduce the independently sealed compiled overlap','135+135 restart exactly equals 270 serial rows and state','time-budget continuation retains complete checkpoint state','fine conditional seed changes only original case contract; no fresh paired or release claim'],
       'old_exact_step_timing_tests_remain_failed':True,'physics_or_solver_changes':[],'production_authorized':False}
    api.require(sum(p['calls'].values())==p['maximum_new_steps'] and p['maximum_new_steps']<=a['maximum_new_qualification_steps_available'],'bounded reserve')
    p['binding']=api.digest(p);job.commit(DESIGN,p);print('FROZEN',api.sha(DESIGN),flush=True)

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'protocol identity')
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(api.read(job.DESIGN))

def run():
    p=api.read(DESIGN);verify(p);d=api.read(job.DESIGN);a=api.read(AUTH)
    api.require(job.utc()<job.policy.utc(a['simulation_cutoff_utc'])-timedelta(hours=1),'time reserve')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'one diagnostic worker')
    api.require(shutil.disk_usage(RUN.anchor).free>a['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'disk reserve')
    affinity=pre.wrapper.affinity.bind(p['logical_cpu']);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=(job.utc()+timedelta(seconds=p['wall_seconds'])).isoformat()
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop,'protocol_sha256':api.sha(DESIGN),'reserved_steps':p['maximum_new_steps'],'affinity':affinity})
    reports=[];total=0
    try:
        old,_=job.codec.read_record(OLD,api.sha(job.DESIGN));compiled,_=job.codec.read_record(COMPILED,api.sha(COMPILED_DESIGN))
        api.require(old['result']['status']=='incomplete_budget' and len(old['rows'])==4915 and len(compiled['rows'])==5185,'frozen observed budget boundary')
        case=next(c for c in d['cases'] if c['id']==d['stress_case']);seed=old['result']['checkpoint']
        job.commit(RUN/'selected_seed.json',{'checkpoint':seed,'source_sha256':api.sha(OLD),'pending_trial':seed['state'].get('pending_trial'),'diagnostic_only':True})
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            geo=pre.prior.geometry()
            def call(label,before,case=case,prefix=None):
                nonlocal total
                cap=p['calls'][label];path=RUN/(label+'.json.xz')
                api.require(job.utc()<job.policy.utc(stop)-timedelta(seconds=120),'bounded wall clock')
                job.commit(path.with_suffix('.launch.json'),{'label':label,'case':case['id'],'reserved_steps':cap,'input_checkpoint_sha256':api.digest(before),'protocol_sha256':api.sha(DESIGN),'utc':job.utc().isoformat()})
                rec,state,_,tx=job.execute_segment(d,case,copy.deepcopy(before),path,cap,prefix,stop)
                count=len(rec['rows']);total+=count
                job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':count,'rejected':rec['result']['rejected'],'raw_sha256':api.sha(path),'cumulative_new_steps':total})
                tick=time.perf_counter();decoded,reader=job.codec.read_record(path,api.sha(job.DESIGN),prefix);read_s=time.perf_counter()-tick
                api.require(job.codec.base.raw_bytes(decoded)==job.codec.base.raw_bytes(rec) and state==reader,'canonical byte and transport chain identity')
                audit=job.kernel.evaluate(decoded,case['spec'],job.binding(d,case),before,geo,api.sha(job.DESIGN),d['minimum_gap_semantics'])
                api.require(audit['passed'] and 0<count<=cap and rec['result']['rejected']==before['state']['rejected'],'healthy accepted prefix')
                api.require(rec['result']['status'] in p['legal_nonterminal_statuses'] or rec['result']['status'] in job.policy.COMPLETE,'original legal status')
                item={'label':label,'case':case['id'],'steps':count,'requested_steps':cap,'status':rec['result']['status'],'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':tx,'read_seconds':read_s,'audit_seconds':audit['audit_seconds'],'simulated_seconds':audit['stop_s']-audit['start_s'],'raw_sha256':api.sha(path),'audit':audit,'path':str(path),'compressed_bytes':path.stat().st_size}
                reports.append(item);job.commit(path.with_suffix('.audit.json'),item)
                print('CONTINUATION',label,count,rec['result']['status'],round(tx,3),'seconds',flush=True)
                api.require(total<=p['maximum_new_steps'],'accepted step ceiling')
                return rec,state
            serial,_=call('serial',seed)
            api.require(len(serial['rows'])==270 and serial['rows']==compiled['rows'][4915:5185] and serial['result']['checkpoint']['state']==compiled['result']['checkpoint']['state'],'exact independent 270-row overlap and full state')
            first,prefix=call('split_a',seed);second,_=call('split_b',first['result']['checkpoint'],prefix=prefix)
            api.require(first['rows']+second['rows']==serial['rows'] and second['result']['checkpoint']==serial['result']['checkpoint'],'exact partition restart identity')
            long,prefix=call('selected_long',seed)
            api.require(long['rows'][:270]==serial['rows'],'long continuation exact overlap')
            call('selected_tail',long['result']['checkpoint'],prefix=prefix)
            fine=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125')
            _,initial=pre.stress_seed(d)
            fine_cp=job.parent.model.checkpoint(fine['spec'],job.binding(d,fine),initial,True)
            api.require({k:v for k,v in fine_cp.items() if k!='contract'}=={k:v for k,v in initial.items() if k!='contract'},'conditional fine only original contract rebind')
            job.commit(RUN/'conditional_fine_seed.json',{'checkpoint':fine_cp,'original_selected_checkpoint_sha256':api.digest(initial),'diagnostic_only':True})
            call('conditional_fine',fine_cp,case=fine)
        verify(p)
        r={'passed':True,'new_accepted_steps':total,'cumulative_recovery_steps':35426+total,'calls':reports,'exact_budget_boundary_continuation':True,'exact_partition_restart':True,'observed_old_pending_trial':seed['state'].get('pending_trial'),'pending_trial_nonnull_not_exercised':seed['state'].get('pending_trial') is None,'old_tests_remain_failed':True,'production_authorized':False,'complete_observations':0,'protocol_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()}}
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('QUALIFICATION_COMPLETE',total,flush=True)
    except Exception as e:
        accounts=list(RUN.glob('*.accounting.json'));launches=list(RUN.glob('*.launch.json'))
        unresolved=[str(x) for x in launches if not x.with_name(x.name.replace('.launch.json','.accounting.json')).exists()]
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'known_new_steps':sum(api.read(x)['accepted_steps'] for x in accounts),'unresolved_reservations':unresolved});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
