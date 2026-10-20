"""Bounded same-input comparison, then conditional fixed-pose repair tests."""
from pathlib import Path
from types import ModuleType,FunctionType
from datetime import datetime,timezone,timedelta
import sys,copy
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage240_staging'),str(ROOT/'stage242_staging')]
import replay_original_context_v1 as prior
import contact_consistency_v1 as core
for _name,_value in vars(prior).items():
    if not _name.startswith('__'):globals()[_name]=_value
SELF=Path(__file__).resolve();BASE='identical_inputs_20261012'
PLAN=ROOT/'stage242_designs'/BASE/'design_01.json';AUTH=PLAN.with_name('authorization_01.json');OUT=ROOT/'stage242_evaluations'/BASE
c=ModuleType('_stage242_admin');c.__dict__.update(vars(prior.c))
c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=OUT;c.DESIGNS=PLAN.parent
for _name,_value in vars(prior.c).items():
    if isinstance(_value,FunctionType) and _value.__globals__ is vars(prior.c):setattr(c,_name,frozen.clone(_value,vars(c)))
for _name in ('resources','verify','launch'):globals()[_name]=frozen.clone(getattr(prior,_name),globals())
PREVIOUS=ROOT/'stage241_evaluations/cycle_relaxation_20261012'

def bounds(a):
    require(a['maximum_direct_route_calls']==32 and a['maximum_nonadvancing_outer_calls']==4
        and a['maximum_map_evaluations_per_outer']==80 and a['maximum_total_outer_maps']==320
        and a['maximum_trajectory_steps']==a['maximum_saved_transport_steps']==0
        and a['workers']==a['threads']==1 and a['logical_cpu']==14 and not a['production_authorized']
        and a['maximum_output_bytes']==64*1024**2 and a['minimum_free_disk_bytes']>=20*1024**3,
        'Frozen contact comparison/conditional repair budget')
    start,end,cut=[datetime.fromisoformat(a[k]) for k in ('start_utc','end_utc','worker_cutoff_utc')]
    require(all(t.utcoffset() is not None for t in (start,end,cut)) and (end-start).total_seconds()==1200
        and cut==end-timedelta(seconds=60),'Fresh twenty-minute bounded work window')

def pure():
    return dict(passed=True,context=prior.adapter.controls(),candidate=core.controls(),contact_calls=0,outer_calls=0)

def prepare():
    c.environment();require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Create-only comparison admission')
    old=c.read(prior.PLAN);plain_verify(old['source_files']);plain_verify(old['inputs'])
    final=PREVIOUS/'final_disposition_01/results.json'
    require(c.sha(final)=='761b864a75300648ccc719ff5324e6b2ae6dfb7c8aef9cd745e386f760815aab','Preserved closed stabilization failure')
    negative=c.sealed(final);require(not negative['method_viability_passed'] and negative['known_map_evaluations']==82,'No failed repair promoted')
    plain_verify(negative['artifacts']);controls=pure()
    inventory=c.read(prior.OUT/'fixtures.json');failed=inventory['fixtures'][0];half=inventory['fixtures'][1]
    relaxed=c.read(PREVIOUS/'call_01_failed/captured_call.json')['fixture']['contact_trial_trace']['detailed_trials'][0]
    direct=[]
    for label,row,index in [('original_scalar',failed['expected'],0),('original_primary',failed['expected'],1),
            ('relaxed_primary',dict(contact_trial_trace=dict(detailed_trials=[relaxed])),70),
            ('relaxed_scalar',dict(contact_trial_trace=dict(detailed_trials=[relaxed])),71),('half_control',half['expected'],0)]:
        item=copy.deepcopy(row['contact_trial_trace']['detailed_trials'][0]['inner_systems'][index])
        direct.append(dict(id=label,item=item,recovery_mode=label=='half_control',outer_velocity_scale=max(np.linalg.norm(failed['outer_inputs'][0]),np.linalg.norm(failed['outer_inputs'][1]),1e-30)))
    frozen_inventory=dict(direct=direct,outer=inventory['fixtures'])
    imported={str(Path(m.__file__).resolve()):c.sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources=merge(old['source_files'],imported,{str(SELF):c.sha(SELF),str(Path(core.__file__).resolve()):c.sha(core.__file__)})
    selected=[final,final.with_name('completion.json'),PREVIOUS/'call_01_failed/captured_call.json',PREVIOUS/'call_01_failed/results.json',prior.OUT/'fixtures.json']
    inputs=merge(old['inputs'],{str(p):c.sha(p) for p in selected});plain_verify(sources);plain_verify(inputs)
    start=datetime.now(timezone.utc);end=start+timedelta(seconds=1200)
    a=dict(stage='Stage242 identical-input contact comparison and conditional cycle repair',
        human_authorization='Human explicitly requested identical-input primary/fallback comparison and bottleneck repair while preserving physics and accuracy gates.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=60)).isoformat(),
        maximum_direct_route_calls=32,maximum_nonadvancing_outer_calls=4,maximum_map_evaluations_per_outer=80,maximum_total_outer_maps=320,
        maximum_trajectory_steps=0,maximum_saved_transport_steps=0,workers=1,threads=1,logical_cpu=14,
        maximum_output_bytes=64*1024**2,minimum_free_disk_bytes=20*1024**3,production_authorized=False,
        short_seed_scope_repair_admitted=True,source_files=sources,inputs=inputs,physical_changes=[],accuracy_gate_changes=[],numerical_cap_changes=[],
        candidate_policy='Only after exact per-pose two-cycle, use unchanged stateless scalar primitive; original outer bytecode and final gates unchanged.',
        direct_repeat_count=2,direct_order=['primary','fallback'],candidate_order=['failed','halved','contact_order','rotation'],
        conditional_candidate_gate='All accepted primary outputs independently physical; all fallback comparisons accepted, repeated output exact, contact-order/rotation error <=1e-8 of free-speed, and at least one primary/fallback velocity difference exceeds original outer defect tolerance.',
        covariance_tolerance=1e-8,startup_accounting=old['startup_accounting'],
        claim='Same-input solver consistency and fixed-pose repair feasibility only; no transport, population or representative-speedup claim.')
    bounds(a);c.commit(AUTH,a);c.commit(OUT/'fixtures.json',frozen_inventory)
    p={**a,'authorization_sha256':c.sha(AUTH),'fixtures_sha256':c.sha(OUT/'fixtures.json'),'controls':controls,
        'kernel_sha256':KERNEL_SHA,'context_adapter_sha256':ADAPTER_SHA,'method_source_sha256':c.sha(core.__file__)}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,controls=controls,design_sha256=c.sha(PLAN),contact_calls=0,outer_calls=0,utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('STAGE242_PREPARED',c.sha(PLAN),end.isoformat(),flush=True)

ROT=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
Q=np.zeros((6,6));Q[:3,:3]=Q[3:,3:]=ROT

def derived_inner(item,kind):
    result=copy.deepcopy(item)
    if kind=='contact_order':
        order=[3,4,5,0,1,2];result['jacobian']=np.asarray(item['jacobian'])[order].tolist();result['gaps_m']=list(reversed(item['gaps_m']))
    else:
        result['vfree']=(Q@np.asarray(item['vfree'])).tolist();result['mobility']=(Q@np.asarray(item['mobility'])@Q.T).tolist()
        result['jacobian']=(np.asarray(item['jacobian'])@Q.T).tolist()
    return result

def derived_outer(row,kind):
    result=copy.deepcopy(row);result['fixture_id']=kind;a=result['outer_inputs']
    if kind=='contact_order':a[6]=list(reversed(a[6]))
    else:
        for k in range(3):a[k]=(Q@np.asarray(a[k])).tolist()
        for k in range(3,6):a[k]=(Q@np.asarray(a[k])@Q.T).tolist()
        a[6]=[[c[0],c[1],(ROT@np.asarray(c[2])).tolist(),(ROT@np.asarray(c[3])).tolist()] for c in a[6]]
    result['outer_operands_sha256']=api.digest(a);result['derived_from_original_operands_sha256']=row['outer_operands_sha256']
    return result

def run():
    p=verify();proc=psutil.Process();proc.cpu_affinity([14]);require(not (OUT/'launch.json').exists(),'No duplicate comparison worker')
    c.commit(OUT/'launch.json',dict(pid=proc.pid,created=proc.create_time(),command=proc.cmdline(),utc=c.utc(),design_sha256=c.sha(PLAN)))
    direct=outer=maps=0;active=None;direct_reports=[];outer_reports=[]
    def direct_call(row,route,repeat):
        nonlocal direct,active
        resources();require(direct<32 and time.time()<epoch-30,'Direct call cap and work guard')
        direct+=1;folder=OUT/'direct'/f'{direct:02d}_{row["id"]}_{route}_{repeat}';folder.mkdir(parents=True)
        active=dict(kind='direct',call=direct,system=row['id'],route=route)
        c.commit(folder/'reservation.json',{**active,'utc':c.utc()})
        saved=core.direct(row['item'],route,row['recovery_mode'],epoch)
        c.commit(folder/'captured_call.json',saved);active=None
        accepted=saved['returned_answer'] is not None
        audit=None
        if accepted:
            answer=saved['returned_answer'];audit=core.physical_output(core.arguments(row['item']),(np.asarray(answer['velocity']),answer['health']))
        result=dict(passed=True,accepted=accepted,physical_audit=audit,captured_sha256=c.sha(folder/'captured_call.json'))
        c.commit(folder/'results.json',result);c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
        direct_reports.append(dict(**active) if active else dict(call=direct,system=row['id'],route=route,accepted=accepted,path=str(folder/'results.json')))
        return saved
    try:
        inventory=c.read(OUT/'fixtures.json');epoch=datetime.fromisoformat(p['worker_cutoff_utc']).timestamp()
        JOB.parent.b.old.parent.configure();STACK.candidate.warm();kernel.warm();kernel.reset()
        comparison=[];all_fallback=True;repeat_exact=True;largest=0.;baseline=None
        for row in inventory['direct']:
            values={r:[] for r in p['direct_order']}
            for repeat in range(2):
                for route in p['direct_order']:values[route].append(direct_call(row,route,repeat))
            for route in values:
                repeat_exact=repeat_exact and frozen.same(values[route][0]['returned_answer'],values[route][1]['returned_answer']) and values[route][0]['error']==values[route][1]['error']
            all_fallback=all_fallback and all(v['returned_answer'] is not None for v in values['fallback'])
            delta=None;load_difference=None
            if values['primary'][0]['returned_answer'] is not None and values['fallback'][0]['returned_answer'] is not None:
                a,b=[v[0]['returned_answer'] for v in values.values()]
                delta=float(np.linalg.norm(np.asarray(a['velocity'])-np.asarray(b['velocity']))/row['outer_velocity_scale']);largest=max(largest,delta)
                J=np.asarray(row['item']['jacobian']);fa=np.asarray(a['health']['reactions']);fb=np.asarray(b['health']['reactions'])
                load_difference=float(np.linalg.norm(J.T@(fa-fb))/max(np.linalg.norm(J.T@fb),1e-30))
            comparison.append(dict(system=row['id'],primary_accepted=values['primary'][0]['returned_answer'] is not None,
                fallback_accepted=values['fallback'][0]['returned_answer'] is not None,velocity_difference_over_outer_scale=delta,relative_load_difference=load_difference,
                same_input_sha256=values['primary'][0]['input_sha256']))
            require(all(v['input_sha256']==values['primary'][0]['input_sha256'] for z in values.values() for v in z),'Bit-identical paired operands')
            if row['id']=='original_scalar':baseline=(row,values['fallback'][0]['returned_answer'])
        cov=[]
        if all_fallback and repeat_exact:
            base_row,base_answer=baseline
            for kind in ('contact_order','rotation'):
                row={**base_row,'id':kind,'item':derived_inner(base_row['item'],kind)}
                results=[direct_call(row,'fallback',r) for r in range(2)]
                accepted=all(v['returned_answer'] is not None for v in results)
                error=None
                if accepted:
                    expected=np.asarray(base_answer['velocity']);expected=Q@expected if kind=='rotation' else expected
                    error=max(float(np.linalg.norm(np.asarray(v['returned_answer']['velocity'])-expected)/max(np.linalg.norm(base_row['item']['vfree']),1e-15)) for v in results)
                passed=accepted and frozen.same(results[0]['returned_answer'],results[1]['returned_answer']) and error<=p['covariance_tolerance']
                cov.append(dict(kind=kind,accepted=accepted,velocity_error_over_free_speed=error,passed=passed))
        compare_gate=all_fallback and repeat_exact and len(cov)==2 and all(x['passed'] for x in cov) and largest>1e-10
        c.commit(OUT/'comparison.json',dict(passed=compare_gate,systems=comparison,all_fallback_accepted=all_fallback,repeat_exact=repeat_exact,
            maximum_velocity_difference_over_outer_scale=largest,covariance=cov,direct_calls=direct,production_authorized=False))
        if compare_gate:
            failed,half=inventory['outer'];rows=[failed,half,derived_outer(failed,'contact_order'),derived_outer(failed,'rotation')];reference=None
            for index,row in enumerate(rows,1):
                resources();require(outer<4 and time.time()<epoch-30,'Outer cap and time guard')
                outer+=1;folder=OUT/'outer'/f'{outer:02d}_{row["fixture_id"]}';folder.mkdir(parents=True)
                active=dict(kind='outer',call=outer,fixture=row['fixture_id'],maximum_map_evaluations=80)
                c.commit(folder/'reservation.json',{**active,'utc':c.utc()})
                saved=core.capture(row,p);c.commit(folder/'captured_call.json',saved);active=None
                check=core.audit(saved,row);maps+=check['map_evaluations'];require(maps<=320,'Shared map ceiling')
                covariance_passed=None;covariance_error=None
                if check['outer_solution_accepted'] and row['fixture_id'] in ('contact_order','rotation'):
                    expected=np.asarray(reference['returned_answer']['velocity']);expected=Q@expected if row['fixture_id']=='rotation' else expected
                    covariance_error=float(np.linalg.norm(np.asarray(saved['returned_answer']['velocity'])-expected)/max(np.linalg.norm(failed['outer_inputs'][1]),np.linalg.norm(failed['outer_inputs'][0]),1e-30))
                    covariance_passed=covariance_error<=p['covariance_tolerance']
                if index==1:reference=saved
                result={**check,'covariance_passed':covariance_passed,'covariance_error_over_outer_scale':covariance_error}
                c.commit(folder/'results.json',result);c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
                outer_reports.append(dict(fixture=row['fixture_id'],accepted=check['outer_solution_accepted'],maps=check['map_evaluations'],canonical_calls=check['canonical_calls'],
                    cycle_detected=check['cycle_detected'],covariance_passed=covariance_passed,path=str(folder/'results.json')))
                print('STAGE242_OUTER',row['fixture_id'],check['outer_solution_accepted'],check['map_evaluations'],flush=True)
                if not check['outer_solution_accepted'] or covariance_passed is False:break
        resources();viable=compare_gate and len(outer_reports)==4 and all(x['accepted'] for x in outer_reports) and all(x['covariance_passed'] for x in outer_reports[2:])
        result=dict(passed=True,accounting_and_independent_audits_passed=True,comparison_gate_passed=compare_gate,fixed_pose_repair_qualified=viable,
            direct_route_calls=direct,outer_calls=outer,total_outer_maps=maps,canonical_calls=core.CALL_COUNTS['canonical'],direct_reports=direct_reports,outer_reports=outer_reports,
            unknown_direct_calls=0,unknown_outer_calls=0,new_trajectory_steps=0,new_saved_transport_steps=0,production_authorized=False,utc=c.utc())
        c.commit(OUT/'results.json',result);c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as issue:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(issue),traceback=traceback.format_exc(),direct_route_calls=direct,outer_calls=outer,
            direct_reports=direct_reports,outer_reports=outer_reports,unresolved_reservation=active,
            unknown_direct_calls=int(active is not None and active['kind']=='direct'),unknown_outer_calls=int(active is not None and active['kind']=='outer'),
            new_trajectory_steps=0,production_authorized=False,utc=c.utc()));raise

def retire(code):
    p=verify();folder=OUT/'controller_01';identities=[]
    for path in (folder/'launch.json',folder/'worker_launch.json'):
        launch_record=c.read(path);inspection=controller.inspect(launch_record['pid'],launch_record['created'],launch_record['command'])
        require(inspection['retired'],'Exact owned process retired');identities.append(dict(path=str(path),sha256=c.sha(path),inspection=inspection))
    exit_record=c.read(folder/'worker_exit.json');c.verify(exit_record['closed_logs'])
    complete=(OUT/'completion.json').exists();r=c.sealed(OUT/'results.json') if complete else c.read(OUT/'failure.json')
    if complete:require(code==exit_record['returncode']==0 and not exit_record['forced_cutoff_stop'],'Unforced completed evidence')
    raw_direct=list((OUT/'direct').glob('*/captured_call.json')) if (OUT/'direct').exists() else []
    raw_outer=list((OUT/'outer').glob('*/captured_call.json')) if (OUT/'outer').exists() else []
    map_count=sum(len(c.read(q)['fixture']['contact_trial_trace']['detailed_trials'][0]['inner_systems']) for q in raw_outer)
    receipt=OUT/'final_disposition_01/results.json'
    result=dict(passed=True,accounting_authenticated=True,diagnostic_audits_completed=complete,
        comparison_gate_passed=r.get('comparison_gate_passed',False),fixed_pose_repair_qualified=r.get('fixed_pose_repair_qualified',False),
        attempted_direct_calls=r['direct_route_calls'],fully_captured_direct_calls=len(raw_direct),qualified_direct_diagnostics=len(r['direct_reports']),
        native_primary_or_fallback_failures=sum(c.read(q)['returned_answer'] is None for q in raw_direct),
        attempted_outer_calls=r['outer_calls'],fully_captured_outer_calls=len(raw_outer),qualified_outer_diagnostics=len(r['outer_reports']),known_outer_maps=map_count,
        unknown_direct_calls=r['unknown_direct_calls'],unknown_outer_calls=r['unknown_outer_calls'],
        known_unaccepted_direct_diagnostics=len(raw_direct)-len(r['direct_reports']),known_unaccepted_outer_diagnostics=len(raw_outer)-len(r['outer_reports']),
        source_count=len(p['source_files']),input_count=len(p['inputs']),identities=identities,worker_exit=exit_record,controller_returncode_observed=code,
        artifacts={str(q):c.sha(q) for q in OUT.rglob('*') if q.is_file()},design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        production_authorized=False,transport_installed=False,new_trajectory_steps=0,new_saved_transport_steps=0,all_failures_preserved=True,utc=c.utc())
    c.commit(receipt,result);c.commit(receipt.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(receipt)))
    print('STAGE242_RETIRED',c.sha(receipt),'fixed_pose_repair_qualified=',result['fixed_pose_repair_qualified'],flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='retire':retire(int(sys.argv[2]))
    elif action=='controls':print(pure())
    else:{'prepare':prepare,'launch':launch,'run':run}[action]()
