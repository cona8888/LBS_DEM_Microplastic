"""Two prospective diagnostic-only tests; no production or transport runner."""
from pathlib import Path
from types import ModuleType,FunctionType
from datetime import datetime,timezone,timedelta
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage240_staging'),str(ROOT/'stage241_staging')]
import replay_original_context_v1 as prior
import cycle_relaxation_v1 as method
for _name,_value in vars(prior).items():
    if not _name.startswith('__'):globals()[_name]=_value
SELF=Path(__file__).resolve();BASE='cycle_relaxation_20261012'
PLAN=ROOT/'stage241_designs'/BASE/'design_01.json';AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage241_evaluations'/BASE
c=ModuleType('_stage241_administration');c.__dict__.update(vars(prior.c))
c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=OUT;c.DESIGNS=PLAN.parent
for _name,_value in vars(prior.c).items():
    if isinstance(_value,FunctionType) and _value.__globals__ is vars(prior.c):setattr(c,_name,frozen.clone(_value,vars(c)))
# Only original administration needed here; custom run explicitly accounts
# for prospective algorithm differences and can retain a numerical negative.
for _name in ['resources','verify','launch']:
    globals()[_name]=frozen.clone(getattr(prior,_name),globals())
PREREQUISITE=prior.OUT/'final_disposition_01/results.json'
PREREQUISITE_SHA='01b28783b648ef008987b0830d1905b97003ba2c5438c5f7247e6320e5f2142d'

def bounds(a):
    require(a['maximum_nonadvancing_outer_calls']==a['planned_outer_calls']==2
        and a['maximum_map_evaluations_per_call']==80 and a['maximum_map_evaluations_total']==160
        and a['maximum_trajectory_steps']==a['maximum_saved_transport_steps']==0
        and a['workers']==a['threads']==1 and a['logical_cpu']==14
        and a['maximum_output_bytes']==32*1024**2 and a['minimum_free_disk_bytes']>=20*1024**3
        and not a['production_authorized'] and a['call_order']==['failed','halved'],
        'Exactly two independent zero-transport method/control diagnostics')
    start,end,cut=[datetime.fromisoformat(a[k]) for k in ('start_utc','end_utc','worker_cutoff_utc')]
    require(all(t.utcoffset() is not None for t in (start,end,cut)) and (end-start).total_seconds()==480
        and cut==end-timedelta(seconds=60),'Fresh bounded diagnostic window')

def controls():
    require(c.sha(PREREQUISITE)==PREREQUISITE_SHA,'Closed Stage240 attribution prerequisite')
    p=c.sealed(PREREQUISITE)
    require(p['scientific_diagnostic_passed'] and p['qualified_outer_calls']==4
        and not p['prior_stage238_failure_resolved'],'Failure reproduced; no prior promotion')
    return dict(passed=True,original_context=prior.adapter.controls(),method=method.controls(),
        outer_calls=0,contact_calls=0,new_trajectory_steps=0)

def prepare():
    c.environment();require(not AUTH.exists() and not PLAN.exists() and not OUT.exists(),'Create-only method gate')
    pure=controls();old=c.read(prior.PLAN)
    for p,d in old['source_files'].items():require(c.sha(p)==d,'Original bound source unchanged: '+p)
    for p,d in old['inputs'].items():require(c.sha(p)==d,'Original bound input unchanged: '+p)
    r=c.sealed(PREREQUISITE)
    for p,d in r['artifacts'].items():require(c.sha(p)==d,'Sealed attribution artifact unchanged')
    inventory=c.read(prior.OUT/'fixtures.json')
    imported={str(Path(m.__file__).resolve()):c.sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py'
        and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources=merge(old['source_files'],imported,{str(SELF):c.sha(SELF),str(Path(method.__file__).resolve()):c.sha(method.__file__)})
    inputs=merge(old['inputs'],{str(p):c.sha(p) for p in (prior.OUT/'fixtures.json',PREREQUISITE,PREREQUISITE.with_name('completion.json'))})
    start=datetime.now(timezone.utc);end=start+timedelta(seconds=480)
    a=dict(stage='Stage241 exact-cycle half-relaxation diagnostic',
        human_authorization='Human continue here on12October2026 authorizes the next bounded numerical stabilization test, not transport.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=60)).isoformat(),
        maximum_nonadvancing_outer_calls=2,planned_outer_calls=2,maximum_map_evaluations_per_call=80,maximum_map_evaluations_total=160,
        maximum_trajectory_steps=0,maximum_saved_transport_steps=0,workers=1,threads=1,logical_cpu=14,
        maximum_output_bytes=32*1024**2,minimum_free_disk_bytes=20*1024**3,production_authorized=False,
        short_seed_scope_repair_admitted=True,source_files=sources,inputs=inputs,call_order=['failed','halved'],
        physical_changes=[],accuracy_gate_changes=[],numerical_cap_changes=[],
        numerical_algorithm_change='On an exact repeated two-cycle, half-relax only the nonterminal guess. Retain the original undamped defect, actual final map output and momentum gate.',
        independent_diagnostic_controls=True,stop_dependent_production_on_any_failure=True,
        startup_accounting=old['startup_accounting'],
        claim='Prospective equation-preserving stabilization feasibility at archived failed/control poses; zero transport, no population or speedup claim. A failed method stays unqualified.')
    bounds(a);c.commit(AUTH,a);c.commit(OUT/'fixtures.json',inventory)
    p={**a,'authorization_sha256':c.sha(AUTH),'fixtures_sha256':c.sha(OUT/'fixtures.json'),'controls':pure,
        'kernel_sha256':KERNEL_SHA,'context_adapter_sha256':ADAPTER_SHA,'method_source_sha256':c.sha(method.__file__),
        'scientific_timing_exclusions':sorted(TIMING_FIELDS),
        'half_step_comparison':'All archived scientific fields exact after removing only the newly declared algorithm_trace metadata; no original field exclusions.'}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,controls=pure,design_sha256=c.sha(PLAN),outer_calls=0,utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('STAGE241_PREPARED',c.sha(PLAN),end.isoformat(),flush=True)

def run():
    p=verify();process=psutil.Process();process.cpu_affinity([14])
    require(not (OUT/'launch.json').exists(),'No duplicate method worker')
    c.commit(OUT/'launch.json',dict(pid=process.pid,created=process.create_time(),command=process.cmdline(),utc=c.utc(),design_sha256=c.sha(PLAN)))
    attempted=captured=maps=0;active=None;reports=[]
    try:
        inventory=c.read(OUT/'fixtures.json');rows={r['fixture_id']:r for r in inventory['fixtures']}
        JOB.parent.b.old.parent.configure();STACK.candidate.warm();kernel.warm();kernel.reset()
        for index,label in enumerate(p['call_order'],1):
            resources();require(time.time()<datetime.fromisoformat(p['worker_cutoff_utc']).timestamp()-30,'Pre-call time guard')
            require(attempted<2,'No extra method attempt')
            row=rows[label];folder=OUT/f'call_{index:02d}_{label}';folder.mkdir()
            active=dict(call=index,fixture_id=label,maximum_map_evaluations=80,outer_operands_sha256=row['outer_operands_sha256'])
            c.commit(folder/'reservation.json',{**active,'utc':c.utc(),'new_trajectory_steps':0});attempted+=1
            saved=method.capture(row,p);c.commit(folder/'captured_call.json',saved);captured+=1;active=None
            validation=method.audit(saved,row);maps+=validation['map_evaluations']
            require(maps<=160,'Shared map budget')
            result={**validation,'call':index,'fixture_id':label,'captured_call_sha256':c.sha(folder/'captured_call.json')}
            c.commit(folder/'results.json',result);c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
            reports.append(dict(call=index,fixture_id=label,path=str(folder/'results.json'),sha256=c.sha(folder/'results.json'),
                outer_solution_accepted=validation['outer_solution_accepted'],relaxation_activated=validation['relaxation_activated'],map_evaluations=validation['map_evaluations']))
            print('STAGE241_DIAGNOSTIC',label,validation['outer_solution_accepted'],validation['map_evaluations'],flush=True)
        resources();require(attempted==captured==len(reports)==2,'Both predeclared diagnostics accounted')
        viable=all(r['outer_solution_accepted'] for r in reports) and reports[0]['relaxation_activated']
        r=dict(passed=True,accounting_and_independent_audits_passed=True,method_viability_passed=viable,
            attempted_outer_calls=attempted,fully_captured_outer_calls=captured,qualified_diagnostic_calls=len(reports),unknown_outer_calls=0,
            total_map_evaluations=maps,reports=reports,production_authorized=False,numerical_path_promoted=False,
            new_trajectory_steps=0,new_saved_transport_steps=0,utc=c.utc(),claim=p['claim'])
        c.commit(OUT/'results.json',r);c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as issue:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(issue),traceback=traceback.format_exc(),
            attempted_outer_calls=attempted,fully_captured_outer_calls=captured,unresolved_call_reservation=active,
            unknown_outer_calls=1 if active else 0,reports=reports,known_completed_map_evaluations=maps,
            dependent_dispatch_stopped=True,production_authorized=False,new_trajectory_steps=0,utc=c.utc()))
        raise

def retire(code):
    p=verify();folder=OUT/'controller_01';identities=[]
    for path in (folder/'launch.json',folder/'worker_launch.json'):
        launch_record=c.read(path);inspection=controller.inspect(launch_record['pid'],launch_record['created'],launch_record['command'])
        require(inspection['retired'],'Exact owned process retired before closure')
        identities.append(dict(path=str(path),sha256=c.sha(path),inspection=inspection))
    exit_record=c.read(folder/'worker_exit.json');c.verify(exit_record['closed_logs'])
    complete=(OUT/'completion.json').exists();r=c.sealed(OUT/'results.json') if complete else c.read(OUT/'failure.json')
    reports=r['reports'];attempted=r['attempted_outer_calls'];captured=r['fully_captured_outer_calls']
    if complete:require(code==exit_record['returncode']==0 and not exit_record['forced_cutoff_stop'],'Unforced completed diagnostics')
    # Reconstruct known work from complete captures even if an audit failed.
    known_maps=sum(len(c.read(q)['fixture']['contact_trial_trace']['detailed_trials'][0]['inner_systems']) for q in OUT.glob('call_*/captured_call.json'))
    viable=complete and r['method_viability_passed'];artifacts={str(q):c.sha(q) for q in OUT.rglob('*') if q.is_file()}
    receipt=OUT/'final_disposition_01/results.json'
    result=dict(passed=True,accounting_authenticated=True,diagnostic_audits_completed=complete,method_viability_passed=viable,
        attempted_outer_calls=attempted,fully_captured_outer_calls=captured,qualified_diagnostic_calls=len(reports),
        known_unaccepted_outer_calls=captured-len(reports),unknown_outer_calls=r.get('unknown_outer_calls',0),
        known_map_evaluations=known_maps,maximum_map_evaluations_total=160,
        new_trajectory_steps=0,new_saved_transport_steps=0,production_authorized=False,transport_installed=False,
        prior_stage238_failure_resolved=False,identities=identities,controller_returncode_observed=code,worker_exit=exit_record,
        source_count=len(p['source_files']),input_count=len(p['inputs']),design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        artifacts=artifacts,startup_accounting=p['startup_accounting'],all_prior_failures_preserved=True,utc=c.utc())
    c.commit(receipt,result);c.commit(receipt.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(receipt)))
    print('STAGE241_RETIRED',c.sha(receipt),'method_viability_passed=',viable,flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='retire':retire(int(sys.argv[2]))
    elif action=='controls':print(controls())
    else:{'prepare':prepare,'run':run,'launch':launch}[action]()
