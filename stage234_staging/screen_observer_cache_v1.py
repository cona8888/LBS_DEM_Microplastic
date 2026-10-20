"""Small prospective fixed-pose observer-setup test; never integrates transport."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import ModuleType, FunctionType
import json, os, sys, time, traceback, shutil, subprocess

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'stage229_staging'))
import replay_cost_v1 as original
sys.path.insert(0,str(ROOT/'stage230_staging'))
import tail_common_v1 as common
import launch_tail_v1 as controller
sys.path.insert(0,str(SELF.parent))
import observer_template_cache_v1 as candidate

PLAN=ROOT/'stage234_designs/observer_setup_20261009/design_01.json'
AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage234_evaluations/observer_setup_20261009'
PRIOR=ROOT/'stage233_evaluations/sample124_fibre_20261009'
FAILED=ROOT/'stage229_evaluations/overnight_20261007/cost_screen_01/results.json'
c=ModuleType('_fresh_observer_cache_administration')
c.__dict__.update(vars(common))
c.ROOT=ROOT;c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.DESIGNS=PLAN.parent;c.RUN=OUT
for name,fn in vars(common).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(common):
        setattr(c,name,FunctionType(fn.__code__,vars(c),fn.__name__,fn.__defaults__,fn.__closure__))

PRIVATE={**vars(original),'c':c,'candidate':candidate}
for name,fn in vars(original).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(original):
        PRIVATE[name]=FunctionType(fn.__code__,PRIVATE,fn.__name__,fn.__defaults__,fn.__closure__)
call=PRIVATE['call']

def resources():
    a=c.bound();c.environment()
    assert shutil.disk_usage(ROOT).free>a['minimum_free_disk_bytes']
    assert sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())<a['maximum_output_bytes']
    return a

def prepare():
    c.environment();assert not AUTH.exists() and not PLAN.exists() and not (OUT/'launch.json').exists()
    controls=candidate.controls()
    assert controls['passed'] and controls['numerical_calls']==0
    retirement=c.sealed(PRIOR/'retirement_01/results.json')
    assert c.sha(PRIOR/'retirement_01/results.json')=='538a9dec4d41a00ec5bcfd82c964c8bf0f1c74e957b2ee969dc66a245ced2e5b'
    assert retirement['passed'] and retirement['all_exact_launch_identities_retired'] and not retirement['scientific_full_path_passed']
    failed=c.sealed(FAILED)
    assert failed['passed'] and failed['exact_paired_all_scientific_outputs'] and not failed['both_outer_and_transaction_all_strata_material_gain_passed']
    fixture_receipt=c.sealed(original.FIXTURE_DIR/'results.json');assert fixture_receipt['passed']
    inventory=c.read(original.FIXTURE_DIR/'fixtures.json')
    rows=[]
    for stratum in ('recorded_fallback','healthy_early_success'):
        selected=[x for x in inventory['fixtures'] if x['stratum']==stratum][:2]
        assert len(selected)==2
        rows.extend(selected)
    old_plan=c.read(ROOT/'stage233_designs/sample124_fibre_20261009/design_01.json')
    sources={**old_plan['source_files'],**inventory['sources'],
        **{str(path):c.sha(path) for path in original.source_files()},
        str(SELF):c.sha(SELF),str(Path(candidate.__file__).resolve()):c.sha(candidate.__file__)}
    inputs={**inventory['inputs']}
    for path in [PRIOR/'retirement_01/results.json',PRIOR/'retirement_01/completion.json',FAILED,FAILED.parent/'completion.json',
                 original.FIXTURE_DIR/'fixtures.json',original.FIXTURE_DIR/'results.json',original.FIXTURE_DIR/'completion.json']:
        inputs[str(path)]=c.sha(path)
    for mapping in (sources,inputs):
        for path,h in mapping.items():assert c.sha(path)==h,'Fresh same-path source/input hash mismatch: '+path
    start=datetime.now(timezone.utc);end=start+timedelta(minutes=15)
    authority=dict(stage='Stage234 immutable observer-template setup falsification',
        human_authorization='Fresh next9October after Stage233 contact-regime/cost review; bounded equation-preserving metadata engineering only.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=30)).isoformat(),
        maximum_nonadvancing_outer_calls=24,
        maximum_trajectory_steps=0,maximum_saved_transport_steps=0,workers=1,threads=1,logical_cpu=14,
        maximum_output_bytes=64*1024**2,minimum_free_disk_bytes=20*1024**3,
        minimum_material_gain_fraction=.05,production_authorized=False,automatic_continuation_authorized=False,
        physical_changes=[],timestep_changes=[],accuracy_gate_changes=[],prior_windows_remain_closed=True,
        claim='Small fixed-pose equivalence and local outer/complete scoped-transaction cost falsification only. Two healthy and two genuine saved fallback poses from one previous fibre segment. No representative trajectory speedup, difficult-placement transfer, restart/full-path qualification or population shape/flow inference. No prototype installation in transport.',
        research_decision='Stage233 reached two-contact fallback solving but recent dispatch cost implies conditional ~12.1h remaining. Test repeated immutable observer compilation before another long baseline block. Setup caching alone may still fail healthy performance.',
        frozen_negative_performance_source=str(FAILED),source_files=sources,inputs=inputs)
    c.commit(AUTH,authority);resources();c.verify(sources);c.verify(inputs)
    plan={**authority,'authorization_sha256':c.sha(AUTH),'fixture_ids':[x['fixture_id'] for x in rows],
        'modes':['original','reuse'],'phases':['qualification','timing_0','timing_1'],
        'qualification_outer_calls':8,'timing_outer_calls':16,'cache_warmup_in_qualification_only':True,
        'strict_paired_all_scientific_fields_including_residuals':True,
        'timing_field_exclusions':sorted(original.TIMING_FIELDS),'unchanged_independent_physics_and_reuse_audits':True,
        'fresh_actual_hit_corruption_and_live_binding_controls_required':True,'pure_cache_controls':controls,
        'timing_components':['seconds','scope_entry_seconds','scope_exit_seconds','telemetry_capture_seconds','scoped_transaction_seconds'],
        'scope_cost_definition':'Include context entry, original outer contact solve, telemetry capture and context exit. Exclude post-call independent audits and result serialization; report separately. No production amortization assumption.',
        'promotion_gate':'At least5percent gain in BOTH outer and complete scoped cost for BOTH strata; paired scientific/evidence/physical/cache/live guards must pass first. This tiny pass would authorize no transport promotion.',
        'source_files':sources,'inputs':inputs}
    plan['binding']=c.digest(plan);c.commit(PLAN,plan)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        pure_cache_controls=controls,source_count=len(sources),input_count=len(inputs),numerical_calls=0))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('OBSERVER_CACHE_PREPARED',end.isoformat(),c.sha(PLAN),flush=True)

def verify():
    a=resources();p=c.read(PLAN)
    assert p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH)
    assert all(p[k]==v for k,v in a.items())
    assert p['maximum_nonadvancing_outer_calls']==24 and p['maximum_trajectory_steps']==p['maximum_saved_transport_steps']==0
    assert not p['production_authorized'] and p['physical_changes']==p['timestep_changes']==p['accuracy_gate_changes']==[]
    c.verify(p['source_files']);c.verify(p['inputs'])
    return p

def run():
    p=verify();process=original.psutil.Process();process.cpu_affinity([14])
    c.commit(OUT/'launch.json',dict(pid=process.pid,created=process.create_time(),command=process.cmdline(),utc=c.utc(),
        design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),affinity=process.cpu_affinity(),
        threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')},new_trajectory_steps=0))
    inventory=c.read(original.FIXTURE_DIR/'fixtures.json');byid={x['fixture_id']:x for x in inventory['fixtures']}
    reports=[];calls=0;mutation=[];live=None;active=None
    try:
        original.JOB.parent.b.old.parent.configure();original.STACK.candidate.warm()
        for phase_index,phase in enumerate(p['phases']):
            for index,identity in enumerate(p['fixture_ids']):
                row=byid[identity];paired=None
                order=p['modes'] if (index+phase_index)%2==0 else list(reversed(p['modes']))
                for mode in order:
                    resources();assert calls<24;calls+=1
                    active=dict(call=calls,phase=phase,fixture_id=identity,mode=mode)
                    c.commit(OUT/'reservations'/f'{calls:02d}.json',active)
                    item=call(inventory,row,mode,p['end_utc'])
                    resources()
                    path=OUT/phase/f'{index:02d}_{mode}.json';c.commit(path,item)
                    report={k:item[k] for k in ('fixture_id','stratum','mode',*p['timing_components'])}
                    report.update(phase=phase,path=str(path),sha256=c.sha(path),reused_requests=0 if item['reuse_log'] is None else item['reuse_log']['reused_requests'])
                    reports.append(report);active=None
                    now=PRIVATE['scientific'](item['force_audit_fixture'])
                    if paired is None:paired=now
                    else:assert c.digest(paired)==c.digest(now),'Exact paired all scientific outputs, residuals and route rows'
                    if phase=='qualification' and mode=='reuse':
                        log=item['reuse_log']
                        if row['stratum']=='recorded_fallback':
                            assert log['reused_requests']>=1,'Genuine unchanged append-qualified fallback hit'
                            check=original.reuse_audit.mutation_checks(log,expected_deadline=datetime.fromisoformat(p['end_utc']).timestamp())
                            assert check['passed'];mutation.append(check)
                        else:assert log['reused_requests']==0,'No healthy negative reuse'
                print('OBSERVER_EXACT_PAIR',phase,identity,'calls',calls,flush=True)
            if phase=='qualification':
                live=original.reuse_audit.live_binding_controls(candidate,fingerprint=candidate._ScopeCodeMetadata().fingerprint,cutoff=candidate.cutoff_control,strict=True)
                assert live['passed'] and len(mutation)==2
        assert calls==24 and active is None
        verify();strata={};cache=candidate.cache_stats()
        assert cache['observer_builds']==1 and cache['template_hits']>=1 and cache['active_scopes']==0
        for stratum in ('recorded_fallback','healthy_early_success'):
            selected=[x for x in reports if x['phase']!='qualification' and x['stratum']==stratum]
            sums={key:{mode:sum(x[key] for x in selected if x['mode']==mode) for mode in p['modes']} for key in p['timing_components']}
            ratios={key:values['reuse']/values['original'] for key,values in sums.items() if key in ('seconds','scoped_transaction_seconds')}
            strata[stratum]=dict(timed_calls_per_mode=4,cost_sums_seconds=sums,candidate_to_original_ratios=ratios,
                outer_material_gain_passed=1-ratios['seconds']>=.05,scoped_material_gain_passed=1-ratios['scoped_transaction_seconds']>=.05)
        performance=all(x['outer_material_gain_passed'] and x['scoped_material_gain_passed'] for x in strata.values())
        result=dict(passed=True,scientific_evidence_and_physical_gates_passed=True,small_performance_gate_passed=performance,
            reason='small_local_performance_pass' if performance else 'performance_gate_failed_preserved',
            utc=c.utc(),design_sha256=c.sha(PLAN),outer_calls_attempted=calls,completed_outer_calls=len(reports),
            qualification_calls_excluded_from_timing=8,timed_calls=16,reports=reports,artifacts={x['path']:x['sha256'] for x in reports},
            original_actual_hit_mutation_controls=mutation,original_live_binding_controls=live,pure_cache_controls=p['pure_cache_controls'],
            strata=strata,observer_template_cache_stats=cache,
            exact_paired_scientific_outputs=True,independent_physical_audits_unchanged=True,
            new_trajectory_steps=0,new_saved_transport_steps=0,prototype_promoted=False,production_authorized=False,
            difficult_two_contact_transfer_qualified=False,transition_restart_full_path_qualified=False,
            profiled_timings_pooled=False,cold_qualification_excluded=True,claim=p['claim'])
        resources();c.commit(OUT/'results.json',result)
        resources();c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
        print('OBSERVER_CACHE_COMPLETE',calls,'performance',performance,c.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        observed=PRIVATE['failure_output'](error);extra={}
        if observed is not None:
            path=OUT/'failed_call.json';c.commit(path,observed);extra[str(path)]=c.sha(path)
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),utc=c.utc(),
            attempted_outer_calls=calls,completed_outer_calls=len(reports),unresolved_call=active,reports=reports,
            artifacts={**{x['path']:x['sha256'] for x in reports},**extra},new_trajectory_steps=0,new_saved_transport_steps=0,
            prototype_promoted=False,dependent_dispatch_stopped=True))
        raise

def launch():
    """One exact-identity child, with a hard cutoff inside the fresh window."""
    p=verify();folder=OUT/'controller_01';folder.mkdir(parents=True,exist_ok=False)
    parent=original.psutil.Process()
    c.commit(folder/'launch.json',dict(pid=parent.pid,created=parent.create_time(),command=parent.cmdline(),utc=c.utc(),
        authorization_sha256=c.sha(AUTH),design_sha256=c.sha(PLAN)))
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'run']
    env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):env[key]='1'
    child=birth=None;forced=False
    stop=FunctionType(controller.stop_owned.__code__,{**vars(controller),'c':c},controller.stop_owned.__name__,
        controller.stop_owned.__defaults__,controller.stop_owned.__closure__)
    try:
        with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            birth=original.psutil.Process(child.pid).create_time()
            assert original.psutil.Process(child.pid).cmdline()==command
            c.commit(folder/'worker_launch.json',dict(pid=child.pid,created=birth,command=command,utc=c.utc()))
            while child.poll() is None:
                if time.time()>=datetime.fromisoformat(p['worker_cutoff_utc']).timestamp():
                    stop(child,birth,command,folder);forced=True;break
                time.sleep(.25)
            code=child.wait(timeout=10)
        identity=controller.inspect(child.pid,birth,command);assert identity['retired']
        c.commit(folder/'worker_exit.json',dict(returncode=code,forced_cutoff_stop=forced,retired_exact_identity=True,
            identity=identity,launch_sha256=c.sha(folder/'worker_launch.json'),utc=c.utc(),
            closed_logs={str(path):c.sha(path) for path in folder.glob('*.log')}))
        if code==0 and not forced:
            resources();result=c.sealed(OUT/'results.json');assert result['outer_calls_attempted']==24
            resources();c.commit(folder/'completion.json',dict(passed=True,scientific_and_physical_passed=True,
                performance_passed=result['small_performance_gate_passed'],results_sha256=c.sha(OUT/'results.json'),utc=c.utc()))
        else:
            c.commit(folder/'failure.json',dict(passed=False,returncode=code,forced_cutoff_stop=forced,
                exact_worker_retired=True,partial_reservations_and_results_preserved=True,prototype_promoted=False,utc=c.utc()))
            raise RuntimeError('Fixed-pose worker failed or interrupted; no promotion')
    except Exception as error:
        if child is not None and birth is not None:stop(child,birth,command,folder)
        path=folder/'launch_failure.json'
        if not path.exists():c.commit(path,dict(passed=False,error=repr(error),traceback=traceback.format_exc(),utc=c.utc()))
        raise

if __name__=='__main__':{'prepare':prepare,'run':run,'launch':launch}[sys.argv[1]]()
