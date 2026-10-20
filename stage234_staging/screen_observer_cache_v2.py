"""Same-window authority-only repair; original independent audit code retained."""
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
from datetime import datetime
import copy, os, sys, time, traceback, subprocess, shutil

ROOT=Path(__file__).resolve().parents[1];SELF=Path(__file__).resolve()
sys.path.insert(0,str(SELF.parent))
import screen_observer_cache_v1 as frozen
original,candidate,controller=frozen.original,frozen.candidate,frozen.controller
AUTH=frozen.AUTH
AUTH_SHA='e375204b435e87f9b7a34214f99426cfb14cdd8267cac6760bbc2e4cecec4915'
PLAN=AUTH.with_name('design_02.json');OUT=frozen.OUT/'repair_02';SHARED=frozen.OUT
c=ModuleType('_same_window_repaired_administration');c.__dict__.update(vars(frozen.c))
c.PLAN=PLAN;c.OUT=OUT;c.RUN=OUT
for name,fn in vars(frozen.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(frozen.c):
        setattr(c,name,FunctionType(fn.__code__,vars(c),fn.__name__,fn.__defaults__,fn.__closure__))

def strict_authority(row,actual_sha,expected_authorization=None):
    assert actual_sha==AUTH_SHA and (expected_authorization is None or actual_sha==expected_authorization)
    assert row['stage']=='Stage234 immutable observer-template setup falsification'
    assert row['start_utc']=='2026-10-09T05:05:47.900185+00:00' and row['end_utc']=='2026-10-09T05:20:47.900185+00:00'
    assert row['maximum_nonadvancing_outer_calls']==24 and row['maximum_trajectory_steps']==row['maximum_saved_transport_steps']==0
    assert row['workers']==row['threads']==1 and row['logical_cpu']==14
    assert row['maximum_output_bytes']==64*1024**2 and row['minimum_free_disk_bytes']==20*1024**3
    assert row['minimum_material_gain_fraction']==.05 and not row['production_authorized'] and not row['automatic_continuation_authorized']
    assert row['physical_changes']==row['timestep_changes']==row['accuracy_gate_changes']==[] and row['prior_windows_remain_closed']
    start=datetime.fromisoformat(row['start_utc']).timestamp();stop=datetime.fromisoformat(row['end_utc']).timestamp()
    assert stop-start==900 and datetime.fromisoformat(row['worker_cutoff_utc']).timestamp()==stop-30
    return start,stop,actual_sha

def fresh_authorization(expected_authorization=None):
    return strict_authority(c.read(AUTH),c.sha(AUTH),expected_authorization)

AUDIT={**vars(original.reuse_audit)}
for name,fn in vars(original.reuse_audit).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(original.reuse_audit):
        AUDIT[name]=FunctionType(fn.__code__,AUDIT,fn.__name__,fn.__defaults__,fn.__closure__)
AUDIT['_authorization']=fresh_authorization
auditor=SimpleNamespace(**AUDIT)
PRIVATE={**frozen.PRIVATE,'c':c,'reuse_audit':auditor}
for name,fn in vars(original).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(original):
        PRIVATE[name]=FunctionType(fn.__code__,PRIVATE,fn.__name__,fn.__defaults__,fn.__closure__)
call=PRIVATE['call']

def controls():
    a=c.read(AUTH);strict_authority(a,c.sha(AUTH));checks=[]
    for key,value in [('maximum_nonadvancing_outer_calls',25),('maximum_trajectory_steps',1),('maximum_saved_transport_steps',1),
        ('production_authorized',True),('automatic_continuation_authorized',True),('physical_changes',['changed']),
        ('timestep_changes',['changed']),('accuracy_gate_changes',['changed']),('end_utc','2026-10-09T05:21:47.900185+00:00'),
        ('maximum_output_bytes',128*1024**2),('workers',2),('minimum_material_gain_fraction',.04)]:
        changed=copy.deepcopy(a);changed[key]=value
        try:strict_authority(changed,AUTH_SHA)
        except AssertionError:checks.append(key)
        else:raise AssertionError('Fresh authority mutation accepted: '+key)
    try:strict_authority(a,'0'*64)
    except AssertionError:checks.append('wrong_authority_sha')
    else:raise AssertionError('Changed authority bytes accepted')
    for name,fn in vars(original.reuse_audit).items():
        if isinstance(fn,FunctionType) and fn.__globals__ is vars(original.reuse_audit) and name!='_authorization':
            assert AUDIT[name].__code__ is fn.__code__ and AUDIT[name].__globals__ is AUDIT
    assert original.reuse_audit._authorization is not fresh_authorization and call.__code__ is original.call.__code__
    return dict(passed=True,mutation_controls=checks,original_audit_code_objects_retained=True,
        original_scientific_physical_and_evidence_gates_unchanged=True,numerical_calls=0)

def resources():
    a=c.bound();c.environment();strict_authority(a,c.sha(AUTH))
    assert shutil.disk_usage(ROOT).free>a['minimum_free_disk_bytes']
    assert sum(path.stat().st_size for path in SHARED.rglob('*') if path.is_file())<a['maximum_output_bytes']
    return a

def prepare():
    resources();assert not PLAN.exists() and not (OUT/'launch.json').exists()
    old=c.read(frozen.PLAN);assert c.sha(frozen.PLAN)=='3f33cfaf3dbf7bad4598ae1723dca7e90e7381a15d9d9d938cd2884213d20e2e'
    failure=c.read(SHARED/'failure.json');failed=c.read(SHARED/'failed_call.json')
    assert failure['attempted_outer_calls']==2 and failure['completed_outer_calls']==1
    assert 'only the frozen Stage229 authorization deadline' in failure['error']
    assert failed['audit']['passed'] and len(failed['answer'])==2 and failed['memo']['cache_retained'] is False
    assert failed['memo']['executed_requests']==failed['memo']['reused_requests']==1
    retirement={}
    for label in ('launch.json','worker_launch.json'):
        row=c.read(SHARED/'controller_01'/label)
        proof=controller.inspect(row['pid'],row['created'],row['command']);assert proof['retired'];retirement[label]=proof
    sources={**old['source_files'],str(SELF):c.sha(SELF)};inputs={**old['inputs'],str(frozen.PLAN):c.sha(frozen.PLAN)}
    for path in list((SHARED/'controller_01').glob('*'))+[SHARED/'failure.json',SHARED/'failed_call.json',SHARED/'launch.json',SHARED/'reservations/01.json',SHARED/'reservations/02.json',SHARED/'qualification/00_original.json']:
        if path.is_file():inputs[str(path)]=c.sha(path)
    c.verify(sources);c.verify(inputs);pure=controls()
    plan={**old,'source_files':sources,'inputs':inputs,'initial_known_executed_outer_calls':2,'maximum_new_outer_calls':20,
        'prior_failed_attempt_not_promoted':True,'same_absolute_authority_and_shared_budget':True,
        'phase_rows':{'qualification':old['fixture_ids'],'timing_0':old['fixture_ids'],
                      'timing_1':[old['fixture_ids'][0],old['fixture_ids'][2]]},
        'qualification_outer_calls':8,'timing_outer_calls':12,'timed_calls_per_mode_per_stratum':3,
        'extra_repeat_selection':'Prospectively repeat the first frozen fixture of each stratum; remaining two get one timed repetition. Equal weights between implementations; tiny falsification, no representative inference.',
        'administrative_repair':'Replace only hardcoded expired Stage229 _authorization with exact original Stage234 SHA/schema/window. All other independent audit/mutation code objects remain original in one private namespace.',
        'prior_failure_retirement':retirement,'authority_adapter_controls':pure}
    plan.pop('binding');plan['binding']=c.digest(plan);resources();c.commit(PLAN,plan)
    resources();c.commit(OUT/'preparation_01/results.json',dict(passed=True,design_sha256=c.sha(PLAN),controls=pure,
        initial_known_executed_calls=2,initial_calls_excluded_from_fresh_qualification_and_timing=True,new_calls_cap=20,shared_calls_cap=24,numerical_calls=0))
    resources();c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('SAME_WINDOW_REPAIR_PREPARED',c.sha(PLAN),'20new/24shared',flush=True)

def verify():
    resources();p=c.read(PLAN)
    assert p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==AUTH_SHA
    assert p['maximum_new_outer_calls']==20 and p['initial_known_executed_outer_calls']==2
    assert sum(len(x)*2 for x in p['phase_rows'].values())==20 and p['prior_failed_attempt_not_promoted']
    c.verify(p['source_files']);c.verify(p['inputs']);controls()
    return p

def run():
    p=verify();process=original.psutil.Process();process.cpu_affinity([14])
    c.commit(OUT/'launch.json',dict(pid=process.pid,created=process.create_time(),command=process.cmdline(),utc=c.utc(),
        design_sha256=c.sha(PLAN),authorization_sha256=AUTH_SHA,affinity=[14],new_trajectory_steps=0))
    inventory=c.read(original.FIXTURE_DIR/'fixtures.json');byid={x['fixture_id']:x for x in inventory['fixtures']}
    reports=[];calls=0;mutation=[];live=None;active=None
    try:
        original.JOB.parent.b.old.parent.configure();original.STACK.candidate.warm()
        for phase_index,phase in enumerate(p['phases']):
            for index,identity in enumerate(p['phase_rows'][phase]):
                row=byid[identity];paired=None
                order=p['modes'] if (index+phase_index)%2==0 else list(reversed(p['modes']))
                for mode in order:
                    resources();assert calls<20 and calls+2<24;calls+=1
                    active=dict(call=calls,phase=phase,fixture_id=identity,mode=mode)
                    c.commit(OUT/'reservations'/f'{calls:02d}.json',active)
                    item=call(inventory,row,mode,p['end_utc']);resources()
                    path=OUT/phase/f'{index:02d}_{mode}.json';c.commit(path,item)
                    report={k:item[k] for k in ('fixture_id','stratum','mode',*p['timing_components'])}
                    report.update(phase=phase,path=str(path),sha256=c.sha(path),reused_requests=0 if item['reuse_log'] is None else item['reuse_log']['reused_requests'])
                    reports.append(report);active=None
                    now=PRIVATE['scientific'](item['force_audit_fixture'])
                    if paired is None:paired=now
                    else:assert c.digest(paired)==c.digest(now),'Exact paired scientific fields including residuals and route rows'
                    if phase=='qualification' and mode=='reuse':
                        log=item['reuse_log']
                        if row['stratum']=='recorded_fallback':
                            assert log['reused_requests']>=1
                            check=auditor.mutation_checks(log,expected_deadline=datetime.fromisoformat(p['end_utc']).timestamp())
                            assert check['passed'];mutation.append(check)
                        else:assert log['reused_requests']==0
                print('REPAIR_EXACT_PAIR',phase,identity,'newcalls',calls,flush=True)
            if phase=='qualification':
                live=auditor.live_binding_controls(candidate,fingerprint=candidate._ScopeCodeMetadata().fingerprint,cutoff=candidate.cutoff_control,strict=True)
                assert live['passed'] and len(mutation)==2
        assert calls==20 and active is None;verify();cache=candidate.cache_stats()
        assert cache['observer_builds']==1 and cache['template_hits']>=1 and cache['active_scopes']==0
        strata={}
        for stratum in ('recorded_fallback','healthy_early_success'):
            selected=[x for x in reports if x['phase']!='qualification' and x['stratum']==stratum]
            assert all(sum(x['mode']==mode for x in selected)==3 for mode in p['modes'])
            sums={key:{mode:sum(x[key] for x in selected if x['mode']==mode) for mode in p['modes']} for key in p['timing_components']}
            ratios={key:value['reuse']/value['original'] for key,value in sums.items() if key in ('seconds','scoped_transaction_seconds')}
            strata[stratum]=dict(timed_calls_per_mode=3,cost_sums_seconds=sums,candidate_to_original_ratios=ratios,
                outer_material_gain_passed=1-ratios['seconds']>=.05,scoped_material_gain_passed=1-ratios['scoped_transaction_seconds']>=.05)
        performance=all(x['outer_material_gain_passed'] and x['scoped_material_gain_passed'] for x in strata.values())
        result=dict(passed=True,scientific_evidence_and_physical_gates_passed=True,small_performance_gate_passed=performance,
            reason='small_local_performance_pass' if performance else 'performance_gate_failed_preserved',utc=c.utc(),
            design_sha256=c.sha(PLAN),authorization_sha256=AUTH_SHA,outer_calls_attempted=calls,completed_outer_calls=len(reports),
            prior_known_executed_outer_calls=2,total_known_executed_outer_calls=22,shared_outer_calls_cap=24,
            qualification_calls_excluded_from_timing=8,timed_calls=12,reports=reports,artifacts={x['path']:x['sha256'] for x in reports},
            original_actual_hit_mutation_controls=mutation,original_live_binding_controls=live,authority_adapter_controls=p['authority_adapter_controls'],
            strata=strata,observer_template_cache_stats=cache,exact_paired_scientific_outputs=True,independent_physical_audits_unchanged=True,
            new_trajectory_steps=0,new_saved_transport_steps=0,prototype_promoted=False,production_authorized=False,
            prior_failure_preserved_not_promoted=True,initial_failed_attempt_excluded_from_all_performance_and_new_qualification=True,
            difficult_two_contact_transfer_qualified=False,transition_restart_full_path_qualified=False,
            profiled_timings_pooled=False,cold_qualification_excluded=True,claim=p['claim'])
        resources();c.commit(OUT/'results.json',result);resources();c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
        print('REPAIR_SCREEN_COMPLETE',calls,'shared22 performance',performance,c.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        observed=PRIVATE['failure_output'](error);extra={}
        if observed is not None:
            path=OUT/'failed_call.json';c.commit(path,observed);extra[str(path)]=c.sha(path)
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),utc=c.utc(),
            attempted_outer_calls=calls,prior_known_executed_outer_calls=2,completed_outer_calls=len(reports),unresolved_call=active,
            reports=reports,artifacts={**{x['path']:x['sha256'] for x in reports},**extra},new_trajectory_steps=0,prototype_promoted=False))
        raise

def launch():
    p=verify();folder=OUT/'controller_01';folder.mkdir(parents=True,exist_ok=False);parent=original.psutil.Process()
    c.commit(folder/'launch.json',dict(pid=parent.pid,created=parent.create_time(),command=parent.cmdline(),utc=c.utc(),design_sha256=c.sha(PLAN),authorization_sha256=AUTH_SHA))
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'run'];env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):env[key]='1'
    stop=FunctionType(controller.stop_owned.__code__,{**vars(controller),'c':c},controller.stop_owned.__name__,controller.stop_owned.__defaults__,controller.stop_owned.__closure__)
    child=birth=None;forced=False
    try:
        with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            birth=original.psutil.Process(child.pid).create_time();assert original.psutil.Process(child.pid).cmdline()==command
            c.commit(folder/'worker_launch.json',dict(pid=child.pid,created=birth,command=command,utc=c.utc()))
            while child.poll() is None:
                if time.time()>=datetime.fromisoformat(p['worker_cutoff_utc']).timestamp():stop(child,birth,command,folder);forced=True;break
                time.sleep(.25)
            code=child.wait(timeout=10)
        identity=controller.inspect(child.pid,birth,command);assert identity['retired']
        c.commit(folder/'worker_exit.json',dict(returncode=code,forced_cutoff_stop=forced,retired_exact_identity=True,identity=identity,
            launch_sha256=c.sha(folder/'worker_launch.json'),closed_logs={str(path):c.sha(path) for path in folder.glob('*.log')},utc=c.utc()))
        if code==0 and not forced:
            resources();result=c.sealed(OUT/'results.json');assert result['outer_calls_attempted']==20 and result['total_known_executed_outer_calls']==22
            resources();c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json'),performance_passed=result['small_performance_gate_passed'],utc=c.utc()))
        else:raise RuntimeError('Same-window repair failed; all evidence remains unpromoted')
    except Exception as error:
        if child is not None and birth is not None:stop(child,birth,command,folder)
        c.commit(folder/'failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),utc=c.utc()))
        raise

if __name__=='__main__':{'prepare':prepare,'run':run,'launch':launch}[sys.argv[1]]()
