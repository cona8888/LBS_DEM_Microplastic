"""Bounded, equation-preserving approaching-contact timecap experiment.

The shared original producer and physical auditor are unchanged. All work is
discarded diagnostic work; this local experiment cannot admit a Paper1 case.
"""
from pathlib import Path
from types import FunctionType
from datetime import datetime,timezone,timedelta
import copy,sys,time,shutil,traceback
import numpy as np
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_core_v2 as original
import contact_onset_timecap_v1 as controller
import audit_onset_timecap_v1 as policy_auditor
s=original.s;ROOT=s.ROOT;SELF=Path(__file__).resolve();PYTHON=s.PYTHON
DESIGNS=ROOT/'paper1_designs/onset_timecap_20261016'
OUT=ROOT/'paper1_runs/onset_timecap_20261016'
PLAN=DESIGNS/'design_01.json';AUTH=DESIGNS/'authorization_01.json'
PHYSICAL=DESIGNS/'physical_cases_01.json';PROPOSAL=DESIGNS/'proposal_01.json'
DOC=original.DOC
sha,read,require,commit,seal=original.sha,original.read,original.require,original.commit,original.seal
PRIOR_STEPS=5572915;PRIOR_CALLS=1136;STEP_CAP=140000;CALL_CAP=33
CONFIG=dict(enabled=True,policy=copy.deepcopy(controller.POLICY))


def clone(fn,namespace):
    result=FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)
    result.__kwdefaults__=copy.copy(fn.__kwdefaults__)
    return result


def bound():
    s.environment();p=read(PLAN)
    require(time.time()<datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(),'New experiment numerical cutoff')
    require(shutil.disk_usage(ROOT).free>20*1024**3,'Original free disk reserve')
    require(sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())<1024**3,'Timecap output ceiling')
    require(sum(x.stat().st_size for name in ('paper1_runs','paper1_designs','paper1_evaluations')
                for x in (ROOT/name).rglob('*') if x.is_file())<20*1024**3,'Unchanged total retention ceiling')
    return p


namespace={**vars(original),**globals()}
verify_inputs=clone(original.verify_inputs,namespace)
make_context=clone(original.make_context,namespace)
physical_transaction=clone(original.transaction,namespace)


def transaction(ctx,p,d,case,label,cap,before,prefix,previous):
    journal=[];saved_write=ctx.job.codec.write_record
    proof=controller.compile_candidate([],case['spec']['config']['target_mean_interstitial_velocity_m_s'])[1]
    def write_with_journal(path,record,prefix=None):
        record['onset_timecap']=dict(**CONFIG,journal=copy.deepcopy(journal),
            source_sha256=sha(controller.__file__),source_ast_proof=proof)
        return saved_write(path,record,prefix)
    ctx.job.codec.write_record=write_with_journal
    try:
        with controller.scope(journal,case['spec']['config']['target_mean_interstitial_velocity_m_s'],CONFIG['enabled']):
            rec,nxt,row=physical_transaction(ctx,p,d,case,label,cap,before,prefix,previous)
    finally:
        ctx.job.codec.write_record=saved_write
    require(rec.get('onset_timecap',{}).get('journal')==journal,'Every live selector witness persisted before original raw seal')
    extra=policy_auditor.audit(rec,before,case,CONFIG,ctx)
    require(extra['passed'],'Independent numerical-selector audit')
    folder=OUT/'records'/label
    seal(folder/'timecap_guard',dict(**extra,raw_sha256=sha(folder/'call.json.xz'),
        original_physical_guard_sha256=sha(folder/'guard_completion/results.json'),utc=s.utc()))
    return rec,nxt,row


def seed_for(index):return DOC.read(DESIGNS/f'seed_{index}.json'),None


def archived_pretrigger_control():
    """Exercise the supplemental auditor on256 exact archived old steps, no solve."""
    olddir=ROOT/'paper1_designs/onset_common_state_20261015'
    oldphysical=olddir/'physical_cases_01.json';case=read(oldphysical)['cases'][1]
    before=DOC.read(olddir/'seed_1.json');codec=original.archives.build(s.q.job.codec,preset=9)
    record,_=codec.read_record(ROOT/'paper1_runs/onset_common_state_20261015/records/branch1_serial/call.json.xz',sha(oldphysical),None)
    ctx=make_context();geometry=ctx.geometry_for(case);cfg=case['spec']['config'];n=cfg['numerics'];a,b,_=cfg['prolate_semiaxes_m']
    old=copy.deepcopy(before['state']);journal=[];reconstruction=controller.reconstruction
    with ctx.job.prior.snapshot.scope(s.api,case['spec']['field_metadata']):
        field,_,_=s.api.fields.load(case['spec']['seed'],case['spec']['flow_factor'],case['spec']['cpd'])
        for row in record['rows']:
            x,p,q=[np.asarray(old[k],float) for k in ('x','p','q')]
            full=float(reconstruction.ASSEMBLE(field,geometry,x,p,q,a,b,cfg['dynamic_viscosity_Pa_s'],cfg['particle_density_kg_m3'],
                cfg['fluid_density_kg_m3'],cfg['gravity_m_s2'],cfg['friction_coefficient'],np.inf,old['t'],cfg['added_mass_fraction'],
                .2,.01,n['displacement_fraction'],n['angle_limit_rad'],n['relaxation_fraction'],n['max_dt_s'],n['reynolds_limit'])[8])
            near=reconstruction.ASSEMBLE.__globals__['enrich'](geometry,geometry.contacts(x,p,a,b,.2*float(geometry.r.max())))
            base=min(full,case['spec']['horizon_s']-old['t'])
            selected,ids=controller.select(base,near,q,a,cfg['target_mean_interstitial_velocity_m_s'],untruncated_dt=full)
            require(selected==row['dt_s'] and not ids,'Archived pretrigger interval remains bit-exact')
            journal.append(dict(time_s=old['t'],steps=old['steps'],base_dt_s=base,untruncated_dt_s=full,selected_dt_s=selected,
                velocity_generalized=q.tolist(),near=[[int(c[0]),float(c[1]),np.asarray(c[2]).tolist(),np.asarray(c[3]).tolist()] for c in near],trigger_grain_ids=ids))
            old.update(t=row['time_s'],steps=old['steps']+1,x=row['position_m'],p=row['orientation'],q=row['velocity_generalized'])
    record['onset_timecap']=dict(**CONFIG,journal=journal,source_sha256=sha(controller.__file__),
        source_ast_proof=controller.compile_candidate([],cfg['target_mean_interstitial_velocity_m_s'])[1])
    result=policy_auditor.audit(record,before,case,CONFIG,ctx)
    require(result['passed'] and result['accepted_rows']==256,'Actual archived pretrigger independent policy replay')
    return result


def prepare():
    s.environment();require(not PLAN.exists() and not PROPOSAL.exists() and not OUT.exists(),'Create-only new experiment')
    pure=controller.controls();require(pure['passed'],'Pure selector controls')
    archived=archived_pretrigger_control()
    prior_dir=ROOT/'paper1_designs/onset_common_state_20261015'
    prior=read(prior_dir/'design_01.json')
    old_eval=ROOT/'paper1_runs/onset_common_state_20261015/evaluation_01/results.json'
    old=s.fields.sealed(old_eval);require(old['passed'] and old['all_exact_owned_identities_retired'],'Closed original onset comparison')
    s.api.verify_mapping(old['source_files']);s.api.verify_mapping(old['artifacts'])
    s.api.verify_mapping(prior['source_files']);s.api.verify_mapping(prior['physical_inputs'])
    before=DOC.read(prior_dir/'seed_source/checkpoint.json')
    require(before['state']['t']==.2269471661341095 and before['state']['steps']==365000
        and before['state']['pending_trial'] is None,'Authenticated exact pre-onset FULL state')
    cases=[];physics=[]
    for factor in (.0625,.03125):
        case,_,_=s.factory.load_case('p1_i0_rigid_prolate_ar4_u0p5',.01,factor,'core')
        case['id']+='__approaching_contact_diagnostic';case['role']='discarded_common_state_timecap_diagnostic'
        case['spec']['case_id']=case['id'];case['spec']['horizon_s']=before['state']['t']+.01
        normalized=copy.deepcopy(case['spec']);normalized.pop('case_id');normalized.pop('refinement')
        for k in s.factory.SCALED_CONTROLS:normalized['config']['numerics'].pop(k)
        physics.append(normalized);cases.append(case)
    require(physics[0]==physics[1],'Identical physics, field, complete seed and local endpoint')
    require(all(cases[1]['spec']['config']['numerics'][k]==cases[0]['spec']['config']['numerics'][k]/2
        for k in s.factory.SCALED_CONTROLS),'Original four controls exactly halve')
    physical=dict(cases=cases,diagnostic_only=True,seed_time_s=before['state']['t'],local_stop_s=before['state']['t']+.01,
        original_paper1_horizon_s=.9364396280429768,minimum_gap_semantics=read(prior_dir/'physical_cases_01.json')['minimum_gap_semantics'],
        numerical_controller=CONFIG,numerical_controller_source_sha256=sha(controller.__file__),
        physical_equation_changes=[],accuracy_gate_changes=[])
    physical['binding']=s.api.digest(physical);commit(PHYSICAL,physical)
    for i,case in enumerate(cases):
        seed=s.q.job.parent.model.checkpoint(case['spec'],s.q.job.binding(physical,case),before,True)
        require(seed['state']==before['state'] and seed['state_sha256']==before['state_sha256'],'Only checkpoint contract rebound')
        DOC.store(DESIGNS/f'seed_{i}.json',seed,sha(PHYSICAL))
    inputs={**prior['physical_inputs'],str(old_eval):sha(old_eval),str(prior_dir/'seed_source/checkpoint.json'):sha(prior_dir/'seed_source/checkpoint.json')}
    for path in DESIGNS.rglob('*'):
        if path.is_file():inputs[str(path)]=sha(path)
    sources={**prior['source_files']}
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).suffix=='.py' and ROOT in Path(file).resolve().parents and Path(file).is_file():
            sources[str(Path(file).resolve())]=sha(file)
    sources[str(SELF)]=sha(SELF)
    s.api.verify_mapping(sources);s.api.verify_mapping(inputs)
    require(physical_transaction.__code__ is original.transaction.__code__,'Original physics transaction bytecode')
    commit(PROPOSAL,dict(passed=True,dispatch_authorized=True,
        human_authorization='2026-10-16: next, resolve the contact-onset timestep bottleneck while keeping the physics, accuracy gates and existing budgets unchanged',
        question='Does a prospective approaching-contact finite-factor cap resolve the complete original10ms common-state velocity discrepancy?',
        factors=[.0625,.03125],controller=CONFIG,seed_time_s=before['state']['t'],local_stop_s=before['state']['t']+.01,
        maximum_new_saved_steps=STEP_CAP,maximum_conservative_new_call_charges=CALL_CAP,
        branch_nonrestart_step_caps=[40000,76000],branch_nonrestart_call_caps=[8,16],
        prelude_step_caps=[2048,5000],serial_steps=4096,split_steps=2048,
        maximum_restart_and_smoke_steps=23464,smoke_steps=32,
        prior_case_saved_steps=PRIOR_STEPS,prior_conservative_calls=PRIOR_CALLS,
        existing_case_saved_step_cap=6000000,existing_case_call_cap=1500,
        maximum_window_minutes=90,maximum_output_bytes=1024**3,maximum_total_retention_bytes=20*1024**3,
        minimum_free_disk_bytes=20*1024**3,workers=1,threads=1,logical_cpu=14,step_cap_per_call=5000,native_call_seconds=45,
        original_full_path_admission=False,successor_dispatch_authorized=False,
        source_files=sources,physical_inputs=inputs,pure_controls=pure,archived_pretrigger_control=archived,
        limitations='Approaching-contact selector is not an error estimator; misses rest/release/tangential-only transitions. Local screening cannot admit a fresh full path. Existing remaining case budget cannot fund complete new full-horizon refinement.',utc=s.utc()))
    seal(DESIGNS/'readiness_01',dict(passed=True,source_files=sources,proposal_sha256=sha(PROPOSAL),pure_controls=pure,archived_pretrigger_control=archived,
        original_physics_transaction_bytecode_unchanged=True,new_native_solves=0,new_saved_steps=0,utc=s.utc()))
    print('TIMECAP_READY_ZERO_STEPS',sha(PROPOSAL),flush=True)


def authorize():
    require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Fresh window, no closed run resumed')
    proposal=read(PROPOSAL);require(proposal['dispatch_authorized'],'Current explicit human instruction covers bounded repair')
    s.api.verify_mapping(proposal['source_files']);s.api.verify_mapping(proposal['physical_inputs'])
    require(PRIOR_STEPS+STEP_CAP<=6000000 and PRIOR_CALLS+CALL_CAP<=1500,'Unchanged cumulative budget')
    start=datetime.now(timezone.utc);end=start+timedelta(minutes=90)
    a=dict(start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=25)).isoformat(),
        worker_cutoff_utc=(end-timedelta(minutes=12)).isoformat(),maximum_saved_steps=STEP_CAP,
        maximum_cumulative_physical_steps_per_case=6000000,maximum_cumulative_calls_per_case=1500,
        maximum_unverified_records=1,workers=1,threads=1,logical_cpu=14,step_cap_per_call=5000,
        minimum_free_disk_bytes=20*1024**3,maximum_output_bytes=1024**3,
        accuracy_promotion_authorized=False,successor_cases_authorized=False)
    commit(AUTH,a)
    p={**a,'authorization_sha256':sha(AUTH),'physical_design_sha256':sha(PHYSICAL),
        'source_files':proposal['source_files'],'physical_inputs':{**proposal['physical_inputs'],str(PROPOSAL):sha(PROPOSAL),
        str(DESIGNS/'readiness_01/results.json'):sha(DESIGNS/'readiness_01/results.json')},
        'logical_core_id':'p1_i0_rigid_prolate_ar4_u0p5','diagnostic_only':True}
    p['binding']=s.api.digest(p);commit(PLAN,p)
    print('TIMECAP_FRESH_WINDOW',a['start_utc'],a['end_utc'],sha(PLAN),flush=True)


def run():
    p=bound();verify_inputs(p);require(not (OUT/'worker_launch.json').exists(),'No duplicate worker')
    me=psutil.Process();me.cpu_affinity([14]);d=read(PHYSICAL);proposal=read(PROPOSAL);ctx=make_context()
    commit(OUT/'worker_launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=s.utc()))
    used=0;admitted=[];branches=[];error=None;latest={}
    def invoke(case,index,label,cap,before,prefix,previous):
        nonlocal used
        verify_inputs(p);require(used+cap<=STEP_CAP,'Shared new-step budget including every diagnostic')
        require(len(list((OUT/'reservations').glob('*.json')))<CALL_CAP,'Shared conservative call cap')
        commit(OUT/'reservations'/f'{label}.json',dict(label=label,maximum_saved_steps=cap,
            input_checkpoint_sha256=s.api.digest(before),previous=previous))
        rec,nxt,row=transaction(ctx,p,d,case,label,cap,before,prefix,previous)
        used+=len(rec['rows']);admitted.append(label)
        if '_local_' in label:latest[index]=(rec['result']['checkpoint'],nxt)
        print('TIMECAP_RECORD_AUDITED',label,len(rec['rows']),rec['result']['checkpoint']['state']['t'],
            sum(bool(x['trigger_grain_ids']) for x in rec['onset_timecap']['journal']),flush=True)
        return rec,nxt,row
    try:
        s.q.reference.JOB.parent.b.old.parent.configure();s.q.kernel.warm();s.q.kernel.reset()
        initial,_=seed_for(0)
        smoke,_,_=invoke(d['cases'][0],0,'smoke',32,copy.deepcopy(initial),None,None)
        codec=original.archives.build(s.q.job.codec,preset=9)
        saved,_=codec.read_record(ROOT/'paper1_runs/onset_common_state_20261015/records/branch1_local_00001/call.json.xz',
            sha(ROOT/'paper1_designs/onset_common_state_20261015/physical_cases_01.json'),None)
        require(s.api.digest(smoke['rows'])==s.api.digest(saved['rows'][:32]),'Actual original pretrigger row bits unchanged')
        for i,case in enumerate(d['cases']):
            initial,_=seed_for(i)
            pre,preprefix,_=invoke(case,i,f'branch{i}_prelude',proposal['prelude_step_caps'][i],copy.deepcopy(initial),None,None)
            late=pre['result']['checkpoint'];previous=sha(OUT/'records'/f'branch{i}_prelude/results.json')
            serial,_,_=invoke(case,i,f'branch{i}_serial',4096,copy.deepcopy(late),preprefix,previous)
            a,pa,_=invoke(case,i,f'branch{i}_split_a',2048,copy.deepcopy(late),preprefix,previous)
            b,_,_=invoke(case,i,f'branch{i}_split_b',2048,a['result']['checkpoint'],pa,sha(OUT/'records'/f'branch{i}_split_a/results.json'))
            require(len(pre['rows'])==proposal['prelude_step_caps'][i] and len(serial['rows'])==4096 and len(a['rows'])==len(b['rows'])==2048
                and s.api.digest(serial['rows'])==s.api.digest(a['rows']+b['rows'])
                and s.api.digest(serial['result']['checkpoint'])==s.api.digest(b['result']['checkpoint']),
                'Exact triggered serial/split rows and FULL checkpoint/history')
            require(any(x['trigger_grain_ids'] for x in serial['onset_timecap']['journal'])
                and any(x['trigger_grain_ids'] for x in b['onset_timecap']['journal']),'Fresh restart qualification exercises real trigger in split successor')
            seal(OUT/f'restart_{i}',dict(passed=True,discarded_steps=8192,exact_rows=True,exact_full_checkpoint_history=True,
                trigger_in_serial_and_split_successor=True,late_seed_time_s=late['state']['t']))
            before=copy.deepcopy(initial);prefix=previous=None;labels=[];count=0
            limit=proposal['branch_nonrestart_step_caps'][i]
            for call in range(1,proposal['branch_nonrestart_call_caps'][i]+1):
                if before['state']['t']>=case['spec']['horizon_s']:break
                require(count<limit,'Frozen per-branch local cap')
                label=f'branch{i}_local_{call:05d}'
                rec,prefix,_=invoke(case,i,label,min(5000,limit-count),before,prefix,previous)
                count+=len(rec['rows']);before=rec['result']['checkpoint'];labels.append(label)
                previous=sha(OUT/'records'/label/'results.json')
                if rec['result']['status'] in ('present_at_horizon','full_window_exit'):break
            require(before['state']['t']==case['spec']['horizon_s'],'Complete declared10ms interval; no extrapolation')
            (OUT/f'recoverable_{i}').mkdir(exist_ok=False);DOC.store(OUT/f'recoverable_{i}/checkpoint.json',before,sha(PHYSICAL))
            commit(OUT/f'recoverable_{i}/prefix.json',prefix.reference())
            branches.append(dict(case_id=case['id'],factor=case['factor'],new_steps=count,labels=labels,checkpoint_sha256=s.api.digest(before)))
    except Exception as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc());raise
    finally:
        for i,(cp,prefix) in latest.items():
            folder=OUT/f'recoverable_{i}'
            if not folder.exists():
                folder.mkdir(exist_ok=False);DOC.store(folder/'checkpoint.json',cp,sha(PHYSICAL));commit(folder/'prefix.json',prefix.reference())
        known=unknown=0;reservations=list((OUT/'reservations').glob('*.json'))
        for path in reservations:
            r=read(path);label=r['label']
            if label not in admitted:
                accounting=OUT/'records'/label/'accounting.json'
                if accounting.exists():known+=read(accounting)['saved_steps']
                else:unknown+=r['maximum_saved_steps']
        require(used+known+unknown<=STEP_CAP and len(reservations)<=CALL_CAP,'Complete conservative ledger')
        seal(OUT/'final_disposition_01',dict(passed=error is None and known==unknown==0,error=error,diagnostic_only=True,
            discarded_diagnostic_steps=used,accepted_physical_steps=0,known_unaccepted_saved_steps=known,
            unknown_reserved_steps_upper_bound=unknown,production_labels=admitted,conservative_call_charges=len(reservations),
            branches=branches,native_complete=len(branches)==2,core_result_admitted=False,full_path_accuracy_passed=False,
            prior_case_saved_steps=PRIOR_STEPS,cumulative_saved_steps=PRIOR_STEPS+used+known+unknown,
            cumulative_conservative_calls=PRIOR_CALLS+len(reservations),design_sha256=sha(PLAN),utc=s.utc()))


def evaluate(code,session):
    p=read(PLAN);require(datetime.now(timezone.utc)<datetime.fromisoformat(p['end_utc']),'Fresh audit deadline')
    require(code==0,'Actual successful supervisor exit');s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['physical_inputs'])
    final=s.fields.sealed(OUT/'final_disposition_01/results.json');require(final['passed'] and final['native_complete'],'Complete local experiment')
    identities=[]
    for path in (OUT/'controller_01/launch.json',OUT/'controller_01/worker_launch.json',OUT/'worker_launch.json'):
        launch=read(path);state=s.identity(launch);require(state['retired'],'Exact task-owned identity retired')
        identities.append(dict(path=str(path),sha256=sha(path),inspection=state))
    exit=read(OUT/'controller_01/exit.json');require(exit['returncode']==0,'Native worker actually exited0');s.api.verify_mapping(exit['logs'])
    d=read(PHYSICAL);codec=original.archives.build(s.q.job.codec,preset=9);decoded={};refs={};artifacts={};used=0
    for label in final['production_labels']:
        i=0 if label=='smoke' else int(label[6]);case=d['cases'][i];initial,_=seed_for(i)
        if label in ('smoke',f'branch{i}_prelude') or '_local_00001' in label:before=initial;prefix=None
        elif label.endswith(('_serial','_split_a')):
            before=decoded[f'branch{i}_prelude']['result']['checkpoint'];prefix=refs[f'branch{i}_prelude']
        elif label.endswith('_split_b'):
            before=decoded[f'branch{i}_split_a']['result']['checkpoint'];prefix=refs[f'branch{i}_split_a']
        else:
            previous=f'branch{i}_local_{int(label.rsplit("_",1)[1])-1:05d}'
            before=decoded[previous]['result']['checkpoint'];prefix=refs[previous]
        folder=OUT/'records'/label;gate=s.fields.sealed(folder/'guard_completion/results.json');s.api.verify_mapping(gate['artifacts'])
        extra=s.fields.sealed(folder/'timecap_guard/results.json');require(gate['passed'] and extra['passed'],'Original physics and new policy gates')
        rec,nxt=codec.read_record(folder/'call.json.xz',sha(PHYSICAL),prefix)
        require(rec['spec']==case['spec'] and rec['input_checkpoint_sha256']==s.api.digest(before)
            and gate['full_checkpoint_sha256']==s.api.digest(rec['result']['checkpoint']),'Complete raw ancestry')
        require(extra['raw_sha256']==sha(folder/'call.json.xz'),'Policy guard binds exact raw')
        policy_auditor.audit(rec,before,case,CONFIG,make_context())
        trace=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],float)
        require(np.array_equal(np.load(folder/'trace.npy',allow_pickle=False),trace),'Exact raw-to-trace reconstruction')
        decoded[label]=rec;refs[label]=nxt;used+=len(rec['rows']);artifacts.update(gate['artifacts'])
        artifacts[str(folder/'guard_completion/results.json')]=sha(folder/'guard_completion/results.json')
        artifacts[str(folder/'timecap_guard/results.json')]=sha(folder/'timecap_guard/results.json')
    require(used==final['discarded_diagnostic_steps'],'All diagnostic work independently accounted')
    for i in (0,1):
        serial=decoded[f'branch{i}_serial'];a=decoded[f'branch{i}_split_a'];b=decoded[f'branch{i}_split_b']
        require(s.api.digest(serial['rows'])==s.api.digest(a['rows']+b['rows'])
            and s.api.digest(serial['result']['checkpoint'])==s.api.digest(b['result']['checkpoint']),'Independent exact restart')
    seeds=[seed_for(i)[0]['state'] for i in (0,1)];initial=[[x['t'],*x['x'],*x['p'],*x['q']] for x in seeds]
    def blocks(i):
        for label in final['branches'][i]['labels']:yield np.load(OUT/'records'/label/'trace.npy',mmap_mode='r',allow_pickle=False)
    spec=d['cases'][0]['spec'];cfg=spec['config'];stop=spec['horizon_s']
    metrics=s.q.job.path_metrics.metrics(blocks(0),blocks(1),initial[0],initial[1],stop,stop,cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
    gates=s.q.job.policy.GATES
    limits={k:gates[k] for k in ('whole_position_over_b_max','whole_axis_vector_norm_max','endpoint_q_over_U_max','mean_L1_q_over_U_max')}
    checks={k:bool(np.isfinite(metrics[k]) and 0<=metrics[k]<=v) for k,v in limits.items()}
    terminal=[decoded[x['labels'][-1]]['result'] for x in final['branches']]
    # No full fresh-path gate can be satisfied by this nonzero-start diagnostic.
    local_events_equal=terminal[0]['status']==terminal[1]['status'] and terminal[0]['persistent_contact_observed']==terminal[1]['persistent_contact_observed']
    dwell=[r['first_contact_dwell_time_s'] for r in terminal]
    local_dwell_times_pass=(dwell[0] is None and dwell[1] is None) or (dwell[0] is not None and dwell[1] is not None and abs(dwell[0]-dwell[1])<=gates['first_dwell_time_difference_s_max'])
    exits=[r['time_s'] if r['status']=='full_window_exit' else None for r in terminal]
    local_exit_times_pass=(exits[0] is None and exits[1] is None) or (exits[0] is not None and exits[1] is not None and abs(exits[0]-exits[1])<=gates['exit_time_difference_s_max'])
    require(metrics['common_start_s']==seeds[0]['t'] and metrics['common_stop_s']==stop,'Absolute full local clock unchanged')
    seal(OUT/'evaluation_01',dict(passed=True,local_screen_passed=all(checks.values()) and local_events_equal and local_dwell_times_pass and local_exit_times_pass,
        metrics=metrics,original_numeric_limits=limits,local_numeric_checks=checks,local_events_equal=local_events_equal,
        local_dwell_times_pass=local_dwell_times_pass,local_exit_times_pass=local_exit_times_pass,
        discarded_diagnostic_steps=used,cumulative_saved_steps=PRIOR_STEPS+used,cumulative_conservative_calls=final['cumulative_conservative_calls'],
        original_full_path_admission=False,publication_case_count_increment=0,observed_supervisor_exit_code=code,
        root_exec_session_id=session,all_exact_owned_identities_retired=True,identities=identities,closed_logs=exit['logs'],
        artifacts=artifacts,source_files=p['source_files'],utc=s.utc()))
    print('TIMECAP_EVALUATION',sha(OUT/'evaluation_01/results.json'),all(checks.values()),metrics,flush=True)


namespace.update(globals())
supervise=clone(original.supervise,{**original.supervise.__globals__,**namespace})
if __name__=='__main__':
    action=sys.argv[1]
    if action=='evaluate':evaluate(int(sys.argv[2]),int(sys.argv[3]))
    else:{'prepare':prepare,'authorize':authorize,'run':run,'supervise':supervise,'controls':controller.controls}[action]()
