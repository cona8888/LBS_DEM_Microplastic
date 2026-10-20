"""Bounded continuation of an original case after separately closing its audit.

The numerical functions and physical reader remain the original implementations.
The one-pass history reader is scoped to administrative reconstruction only.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import FunctionType, ModuleType, SimpleNamespace
import copy, json, os, shutil, subprocess, sys, time, traceback
import numpy as np
import psutil

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
sys.path.insert(0,str(SELF.parent))
saved_plan=os.environ.pop('DEM_CASE_PLAN',None)
import single_case_v1 as old
if saved_plan is not None:os.environ['DEM_CASE_PLAN']=saved_plan
import verified_history_reader_v2 as reader
api,job,baseline=old.api,old.job,old.baseline
PLAN=ROOT/'stage232_designs/sample0_sphere_tail_20261008/design_01.json'
AUTH=PLAN.with_name('authorization_01.json')
RUN=ROOT/'stage232_runs/sample0_sphere_tail_20261008/run_01'
OUT=ROOT/'stage232_evaluations/sample0_sphere_tail_20261008'
OLD_PLAN=old.PLAN
OLD_RUN=old.c.RUN
OLD_OUT=old.c.OUT
NAME='s2_i0_sphere_f0p125'
RETIRE=OLD_OUT/'retirement_02/results.json'
CLOSED=OLD_OUT/'audit_recovery_02/final_disposition_01/results.json'
SEED=OUT/'seed_01/results.json'

def context(run,out,plan):
    result=ModuleType('_bounded_case_context')
    result.__dict__.update(vars(old.c))
    result.ROOT=ROOT;result.RUN=run;result.OUT=out;result.PLAN=plan;result.AUTH=AUTH;result.DESIGNS=AUTH.parent
    for key,fn in vars(old.c).items():
        if isinstance(fn,FunctionType) and fn.__globals__ is vars(old.c):
            result.__dict__[key]=FunctionType(fn.__code__,vars(result),fn.__name__,fn.__defaults__,fn.__closure__)
    return result

c=context(RUN,OUT,PLAN)
PRIVATE=dict(vars(old.prior),c=c,PLAN=PLAN,RUN=RUN,OUT=OUT,AUTH=AUTH)
for key in old.NAMES:
    fn=getattr(old.prior,key)
    PRIVATE[key]=FunctionType(fn.__code__,PRIVATE,fn.__name__,fn.__defaults__,fn.__closure__)

def original_case():
    d=PRIVATE['physical_design']();case=next(x for x in d['cases'] if x['id']==NAME)
    api.require(case['factor']==.125 and case['sample_id']==0 and case['shape']=='equal_volume_sphere','One unchanged original matched sphere')
    old.matched_physics(d,case);baseline.clone_check()
    for key in old.NAMES:api.require(PRIVATE[key].__code__ is getattr(old.prior,key).__code__,'Exact original transaction code '+key)
    return d,case

def verify_authority():
    a=c.bound();c.environment()
    c.verify(a['source_files']);c.verify(a['inputs'])
    api.require(a['only_case']==NAME and not a['successor_dispatch_authorized'] and not a['candidate_production_authorized']
        and a['physical_changes']==a['numerical_changes']==a['accuracy_gate_changes']==[],'One new bounded unchanged-model gate')
    return a

def prepare():
    c.environment();api.require(not AUTH.exists() and not PLAN.exists() and not RUN.exists(),'New authority only; no duplicate or closed-stage resume')
    p=old.c.read(OLD_PLAN)
    api.require(old.c.sha(old.SELF)==p['source_files'][str(old.SELF)],'Frozen failed administrative source preserved')
    retired=old.c.sealed(RETIRE)
    api.require(retired['passed'] and retired['all_exact_launch_identities_retired'] and not retired['all_raw_logical_bodies_reconstructed'],'Retired previous stage; raw recovery still required')
    start=datetime.now(timezone.utc);end=start+timedelta(hours=2)
    sources={**p['source_files'],str(SELF):c.sha(SELF),str(Path(reader.__file__).resolve()):c.sha(reader.__file__)}
    inputs={**p['inputs'],str(OLD_PLAN):c.sha(OLD_PLAN),str(old.c.AUTH):c.sha(old.c.AUTH),str(RETIRE):c.sha(RETIRE),
        str(RETIRE.parent/'completion.json'):c.sha(RETIRE.parent/'completion.json'),**retired['artifacts']}
    control=reader.controls(job.codec)
    auth=dict(stage='Stage232 separate audit recovery and matched sphere tail',human_authorization='Fresh human next after Stage231 cutoff and failed finalization; separately bounded closure and original sphere tail only.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=20)).isoformat(),
        only_case=NAME,maximum_saved_steps_including_diagnostics=500000,maximum_new_production_calls=50,
        maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,
        maximum_combined_sphere_production_calls=250,maximum_combined_sphere_saved_steps=2500000,
        step_cap_per_call=10000,qualification_steps_per_case=512,workers=1,threads=1,logical_cpu=14,maximum_unverified_records=1,
        minimum_free_disk_bytes=20*1024**3,maximum_new_output_bytes=4*1024**3,finalizer_retirement_reserve_seconds=30,
        source_files=sources,inputs=inputs,physical_changes=[],numerical_changes=[],accuracy_gate_changes=[],
        successor_dispatch_authorized=False,candidate_production_authorized=False,old_stage_remains_closed=True,
        prior_sphere_saved_steps=1730512,prior_sphere_physical_steps=1730000,prior_sphere_calls=173,
        reader_controls=control,retention='Preserve admitted raw/checkpoint/history, independent receipts and original failure; combined new output4GiB plus20GiB disk reserve. No model copies or speculative trials.',
        claim='Finite-level temporal verification of one labelled sphere at one packing/flow; no population shape/flow trend, permanent retention or experimental/spatial validation.')
    c.commit(AUTH,auth);verify_authority();original_case()
    print('CASE_REPAIR_AUTHORIZED',auth['end_utc'],flush=True)

def close_previous():
    """Reuse the frozen final accountant with a private, one-pass offline reader."""
    a=verify_authority();p=old.c.read(OLD_PLAN)
    retired=old.c.sealed(RETIRE);api.require(retired['all_exact_launch_identities_retired'],'All old task identities retired')
    for label in ('launch.json','worker_launch.json','finalizer_launch.json'):
        record=old.c.read(OLD_RUN.with_name(OLD_RUN.name+'_controller')/label)
        api.require(old.controller.inspect(record['pid'],record['created'],record['argv'])['retired'],'Fresh exact old retirement '+label)
    offline=reader.Reader(job.codec,fresh_bound=c.bound,
        progress=lambda stats:print('OLD_RAW_RECONSTRUCTION_PROGRESS',stats,flush=True))
    cc=context(OLD_RUN,OLD_OUT/'audit_recovery_02',OLD_PLAN)
    private=dict(vars(old),c=cc,PLAN=OLD_PLAN,RUN=OLD_RUN,OUT=cc.OUT)
    private['job']=SimpleNamespace(**{**vars(job),'codec':SimpleNamespace(**{**vars(job.codec),'read_record':offline.read_record})})
    def verified_closed_plan():
        verify_authority()
        api.require(p['binding']==old.c.digest({k:v for k,v in p.items() if k!='binding'}),'Immutable old design')
        c.verify(p['source_files']);c.verify(p['inputs']);old.static_case(p)
        return p
    private['verify']=verified_closed_plan
    private['update_plan']=lambda final:None
    for key in ('record_checks','authenticate'):
        fn=getattr(old,key);private[key]=FunctionType(fn.__code__,private,fn.__name__,fn.__defaults__,fn.__closure__)
    api.require(private['authenticate'].__code__ is old.authenticate.__code__ and job.codec.read_record is old.job.codec.read_record,
                'Original accountant code; transport reader untouched')
    exit_record=old.c.read(OLD_RUN.with_name(OLD_RUN.name+'_controller')/'worker_exit.json')
    private['authenticate'](exit_record)
    final=c.sealed(CLOSED);c.verify(final['artifacts'])
    api.require(final['accounting_authenticated'] and final['accepted_physical_steps']==1730000
        and final['discarded_diagnostic_steps']==512 and final['known_unaccepted_saved_steps']==final['unknown_saved_steps_reservation_upper_bound']==0
        and final['qualification_passed'] and not final['scientific_full_path_passed'],'Full old raw ancestry accepted; old observation remains incomplete')
    cpfile=CLOSED.parent/'recoverable/checkpoint.json';prefixfile=CLOSED.parent/'recoverable/prefix.json'
    cp=c.read(cpfile);prefix=c.read(prefixfile)
    api.require(api.digest(cp)=='2dd51ba29236edcc0a9ca5109ff167a004203dedda6857fe0f4f1b1375a08b49'
        and cp['state']['steps']==1730000 and cp['state']['t']==3.9087651707868227,'Exact reconstructed original sphere seed')
    row=dict(passed=True,authorization_sha256=c.sha(AUTH),closure_sha256=c.sha(CLOSED),retirement_sha256=c.sha(RETIRE),
        checkpoint_file=str(cpfile),checkpoint_sha256=api.digest(cp),prefix_file=str(prefixfile),prefix=prefix,
        inherited_segments=173,inherited_physical_steps=1730000,prior_saved_steps=1730512,time_s=cp['state']['t'],
        last_receipt_sha256=c.sha(OLD_RUN/NAME/'segment_00173/results.json'),
        trace_paths=[str(OLD_RUN/NAME/f'segment_{i:05d}/trace.npy') for i in range(1,174)],
        artifacts={**final['artifacts'],str(CLOSED):c.sha(CLOSED),str(CLOSED.parent/'completion.json'):c.sha(CLOSED.parent/'completion.json'),
            str(cpfile):c.sha(cpfile),str(prefixfile):c.sha(prefixfile)},
        original_failed_finalizer_preserved=True,all_old_raw_logical_bodies_reconstructed=True,reader_stats=offline.stats,
        offline_reader_only=True,new_numerical_calls=0,new_trajectory_steps=0,utc=c.utc())
    c.commit(SEED,row);c.commit(SEED.parent/'completion.json',dict(passed=True,results_sha256=c.sha(SEED)))
    print('CLOSED_RAW_CHAIN_RECOVERED',173,1730512,flush=True)
    return row

def prepare_transport(seed):
    a=verify_authority();d,case=original_case();oldplan=old.c.read(OLD_PLAN)
    cp=c.read(seed['checkpoint_file']);binding=job.binding(d,case)
    contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(binding,True))
    api.require(cp['contract']==contract,'Original complete checkpoint contract')
    p={**a,'authorization_sha256':c.sha(AUTH),'authorized_end_utc':a['end_utc'],
        'physical_design_sha256':c.sha(job.DESIGN),'numerical_policy_contract_sha256':c.sha(job.WORK),'physical_inputs':oldplan['physical_inputs'],
        'original_binding':binding,'checkpoint_contract':contract,'matched_physics':old.matched_physics(d,case),'reference_case':'s2_i0_sphere_f0p03125',
        'inherited':{**seed,'inputs':seed['artifacts']},'inputs':{**a['inputs'],**seed['artifacts'],str(SEED):c.sha(SEED),str(SEED.parent/'completion.json'):c.sha(SEED.parent/'completion.json')}}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        seed_sha256=c.sha(SEED),exact_original_function_code_objects=list(old.NAMES),transport_reader_unchanged=True,numerical_calls=0))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    return verify()

def verify():
    a=verify_authority();p=c.read(PLAN)
    api.require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH),'Frozen separate transport admission')
    for key,value in a.items():
        if key=='inputs':api.require(all(p['inputs'].get(path)==sha for path,sha in value.items()),'Every frozen authority input retained')
        else:api.require(p[key]==value,'Unchanged new authority '+key)
    c.verify(p['inputs']);d,case=original_case()
    api.require(p['original_binding']==job.binding(d,case) and p['matched_physics']==old.matched_physics(d,case),'Original physical matched-case binding')
    seed=c.sealed(SEED);api.require(seed['passed'] and seed['all_old_raw_logical_bodies_reconstructed'] and seed['checkpoint_sha256']==p['inherited']['checkpoint_sha256'],'Qualified inherited seed before numerical work')
    return p

def seed_state(p):
    s=p['inherited'];cp=c.read(s['checkpoint_file'])
    api.require(api.digest(cp)==s['checkpoint_sha256'] and api.digest(cp['state'])==cp['state_sha256'],'Exact original full seed and state')
    prefix=job.codec.HistoryState(**s['prefix'],history_bytes=job.codec.packed_history(cp['state']['history']))
    api.require(job.codec.digest(prefix.history_bytes)==prefix.history_sha256,'Exact inherited history bytes')
    return cp,prefix,s['last_receipt_sha256']

def output_bytes():
    roots=(RUN,OUT,PLAN.parent,RUN.with_name(RUN.name+'_controller'),CLOSED.parent)
    return sum(q.stat().st_size for q in {q.resolve() for root in roots for q in root.rglob('*') if q.is_file()})

def stop_reason(p,used,needed):
    c.bound()
    if time.time()>=datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp()-120:return 'simulation_cutoff'
    if used+needed>p['maximum_saved_steps_including_diagnostics'] or p['prior_sphere_saved_steps']+used+needed>p['maximum_combined_sphere_saved_steps']:return 'saved_step_ceiling'
    if output_bytes()+4*job.codec.base.MAX_COMPRESSED>=p['maximum_new_output_bytes']:return 'output_cap'
    if shutil.disk_usage(ROOT).free<=p['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:return 'disk_reserve'
    return None

def run():
    verify_authority();process=psutil.Process();process.cpu_affinity([c.read(AUTH)['logical_cpu']]);RUN.mkdir(parents=True,exist_ok=False)
    c.commit(RUN/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=c.utc(),authorization_sha256=c.sha(AUTH)))
    stage='old_raw_reconstruction';used=0;entries=[];cp=None;reservation=None
    try:
        seed=close_previous();p=prepare_transport(seed);update_plan('running',seed)
        d,case=original_case();geometry=baseline.geometry_for(case);cp,prefix,previous=seed_state(p)
        api.require(stop_reason(p,0,512) is None,'Fresh exact late restart fits new limits')
        stage='restart_qualification';reservation=dict(role='restart_diagnostic',maximum_saved_steps=512)
        diagnostic=PRIVATE['qualify'](p,d,case,geometry,cp,prefix,previous);used=diagnostic;reservation=None
        print('TAIL_RESTART_VERIFIED',diagnostic,flush=True);stage='production';rec=None;reason='call_limit'
        for index in range(1,p['maximum_new_production_calls']+1):
            reason=stop_reason(p,used,1)
            if reason:break
            if p['prior_sphere_calls']+len(entries)>=p['maximum_combined_sphere_production_calls']:reason='combined_call_ceiling';break
            cap=min(10000,p['maximum_saved_steps_including_diagnostics']-used,p['maximum_combined_sphere_saved_steps']-p['prior_sphere_saved_steps']-used,
                p['maximum_cumulative_physical_steps_per_case']-cp['state']['steps'])
            api.require(cap>0,'Positive remaining original bounded increment')
            reservation=dict(role='production',segment=index,maximum_saved_steps=cap,input_checkpoint_sha256=api.digest(cp))
            folder=RUN/NAME/f'segment_{index:05d}'
            rec,prefix,row=PRIVATE['segment'](p,d,case,geometry,cp,prefix,folder,cap,previous,'production')
            cp=rec['result']['checkpoint'];used+=row['new_saved_steps'];previous=c.sha(folder/'results.json')
            entries.append(dict(segment=index,new_saved_steps=row['new_saved_steps'],results_sha256=previous,stop_s=cp['state']['t']));reservation=None
            print('TAIL_SEGMENT_VERIFIED',index,used,cp['state']['t'],rec['result']['status'],flush=True)
            if rec['result']['status'] in job.policy.COMPLETE:reason='observation_complete';break
        result=dict(case=NAME,complete_observation=reason=='observation_complete',reason=reason,entries=entries,
            cumulative_physical_steps=cp['state']['steps'],cumulative_calls=173+len(entries),diagnostic_saved_steps=diagnostic,
            final_checkpoint_sha256=api.digest(cp),time_s=cp['state']['t'],horizon_s=case['spec']['horizon_s'],
            final_status='paused_checkpoint' if rec is None else rec['result']['status'])
        c.commit(RUN/NAME/'checkpoint.json',cp);c.commit(RUN/NAME/'prefix.json',prefix.reference());c.commit(RUN/NAME/'results.json',result)
        c.commit(RUN/NAME/'completion.json',dict(results_sha256=c.sha(RUN/NAME/'results.json')))
        comp=None
        if result['complete_observation']:
            stage='original_full_path_comparison';comp=PRIVATE['compare'](p,d,case,rec['result'],entries,seed['trace_paths'])
            reason='full_path_accuracy_passed' if comp['passed'] else 'full_path_accuracy_failed'
        c.commit(RUN/'results.json',dict(finished=True,passed=reason=='full_path_accuracy_passed',reason=reason,case=result,
            accepted_physical_steps=used-diagnostic,discarded_diagnostic_steps=diagnostic,saved_steps_including_diagnostics=used,
            comparison_sha256=None if comp is None else c.sha(OUT/NAME/'comparison_01/results.json'),design_sha256=c.sha(PLAN),utc=c.utc(),
            known_unaccepted_saved_steps=0,unknown_saved_steps_reservation_upper_bound=0,successor_cases_started=0,contact_prototype_promoted=False))
        c.commit(RUN/'completion.json',dict(results_sha256=c.sha(RUN/'results.json')))
    except Exception as error:
        c.commit(RUN/'failure.json',dict(stage=stage,error=repr(error),traceback=traceback.format_exc(),verified_new_saved_steps=used,
            accepted_entries=entries,unresolved_reservation=reservation,last_verified_checkpoint_sha256=api.digest(cp),utc=c.utc(),dependent_dispatch_stopped=True))
        raise

def finalize(exit_record):
    p=verify();d,case=original_case();seed_cp,seed_prefix,seed_previous=seed_state(p)
    controller=RUN.with_name(RUN.name+'_controller');worker=c.read(controller/'worker_launch.json')
    api.require(exit_record['retired_exact_identity'] and exit_record['launch_sha256']==c.sha(controller/'worker_launch.json'),'Exact retired numerical worker association')
    offline=reader.Reader(job.codec,fresh_bound=c.bound)
    identities=dict(authorization_sha256=p['authorization_sha256'],transport_design_sha256=c.sha(PLAN),physical_design_sha256=p['physical_design_sha256'],simulation_cutoff_utc=p['simulation_cutoff_utc'])
    def read_accepted(folder,parent,parent_prefix,previous,role,cap):
        c.bound()
        marker=c.read(folder/'launch.json');old.marker_checks(marker,role,cap,api.digest(parent),identities,p,worker)
        receipt=c.sealed(folder/'results.json');c.verify(receipt['artifacts'])
        rec,checked=offline.read_record(folder/'call.json.xz',p['physical_design_sha256'],parent_prefix)
        n=len(rec['rows']);cp=rec['result']['checkpoint'];old.saved_count(n,cp['state']['steps']-parent['state']['steps'],receipt['new_saved_steps'],cap)
        api.require(rec['spec']==case['spec'] and rec['effective_binding']==job.parent.model.binding_for(p['original_binding'],True)
            and rec['numerical_policy_contract_sha256']==p['numerical_policy_contract_sha256'] and cp['contract']==p['checkpoint_contract']
            and rec['input_checkpoint_sha256']==api.digest(parent) and receipt['input_checkpoint_sha256']==api.digest(parent)
            and receipt['previous_receipt_sha256']==previous and receipt['output_checkpoint_sha256']==api.digest(cp)
            and receipt['passed'] and receipt['summary']['passed'] and receipt['role']==role,'Original independent physical/raw/checkpoint ancestry')
        trace=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
        api.require(np.array_equal(trace,np.load(folder/'trace.npy',allow_pickle=False)),'Exact original raw/trace fields')
        return rec,checked,n
    qroot=RUN/NAME/'qualification_01';diagnostics={};diag=0
    for label,cap in (('serial_01',256),('split_a_01',128),('split_b_01',128)):
        if label=='split_b_01':parent,prefix=diagnostics['split_a_01'][0]['result']['checkpoint'],diagnostics['split_a_01'][1];previous=c.sha(qroot/'split_a_01/results.json')
        else:parent,prefix,previous=seed_cp,seed_prefix,seed_previous;offline.prime(prefix)
        rec,checked,n=read_accepted(qroot/label,parent,prefix,previous,'restart_diagnostic',cap);diag+=n;diagnostics[label]=(rec,checked)
    serial,a,b=[diagnostics[label][0] for label in ('serial_01','split_a_01','split_b_01')]
    proof=c.sealed(qroot/'results.json');c.verify(proof['artifacts'])
    qualified=bool(diag==512 and serial['rows']==a['rows']+b['rows'] and api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint'])
        and proof['passed'] and proof['production_seed_sha256']==api.digest(seed_cp) and not proof['diagnostic_trajectory_promoted'])
    api.require(qualified,'Exact late seed rows and FULL checkpoint; discarded512')
    cp,prefix,previous=seed_cp,seed_prefix,seed_previous;offline.prime(prefix);physical=unaccepted=unknown=0;entries=[];records=[];blocked=False
    for folder in sorted((RUN/NAME).glob('segment_*')):
        c.bound();cap=10000
        if not (folder/'completion.json').is_file():
            blocked=True
            try:
                rec,checked=offline.read_record(folder/'call.json.xz',p['physical_design_sha256'],prefix)
                n=len(rec['rows']);old.saved_count(n,rec['result']['checkpoint']['state']['steps']-cp['state']['steps'],n,cap)
                api.require(rec['spec']==case['spec'] and rec['input_checkpoint_sha256']==api.digest(cp),'Unaccepted raw binding')
                unaccepted+=n;records.append(dict(folder=str(folder),status='known_unaccepted',saved_steps=n))
            except Exception as error:unknown+=cap;records.append(dict(folder=str(folder),status='unknown',reserved_steps=cap,error=repr(error)))
            break
        api.require(not blocked,'No promotion after unresolved record')
        index=int(folder.name.removeprefix('segment_'));api.require(index==len(entries)+1,'Consecutive new accepted production ancestry')
        cap=min(10000,p['maximum_saved_steps_including_diagnostics']-physical-diag,p['maximum_combined_sphere_saved_steps']-1730512-physical-diag)
        rec,checked,n=read_accepted(folder,cp,prefix,previous,'production',cap);cp,prefix=rec['result']['checkpoint'],checked;previous=c.sha(folder/'results.json');physical+=n
        entries.append(dict(segment=index,new_saved_steps=n,results_sha256=previous,stop_s=cp['state']['t']))
        print('TAIL_FINAL_RECORD_VERIFIED',index,flush=True)
    result=c.sealed(RUN/'results.json') if (RUN/'completion.json').exists() else None;comp=None
    if result:
        api.require(unaccepted==unknown==0 and result['case']['entries']==entries and result['accepted_physical_steps']==physical
            and result['discarded_diagnostic_steps']==diag and result['saved_steps_including_diagnostics']==physical+diag
            and api.digest(cp)==result['case']['final_checkpoint_sha256']==api.digest(c.read(RUN/NAME/'checkpoint.json'))
            and prefix.reference()==c.read(RUN/NAME/'prefix.json'),'Complete final tail raw/checkpoint/history ledger')
        if result['comparison_sha256']:
            comp=c.sealed(OUT/NAME/'comparison_01/results.json');c.verify(comp['path_artifacts'])
            api.require(c.sha(OUT/NAME/'comparison_01/results.json')==result['comparison_sha256']
                and comp['case']==NAME and comp['reference_case']==p['reference_case'] and comp['inherited_segments']==173
                and comp['new_segments']==len(entries) and comp['full_original_start_to_terminal_path']
                and comp['transport_design_sha256']==c.sha(PLAN) and comp['physical_design_sha256']==p['physical_design_sha256'],'Original complete inherited-plus-tail comparison')
    scientific=bool(result and comp and qualified and not blocked and unaccepted==unknown==0 and result['passed'] and comp['passed']
        and comp['full_path_gates']['passed'] and all(comp['full_path_gates']['checks'].values()) and result['case']['complete_observation']
        and comp['observation']['complete_observation'] and comp['observation']['steps']==cp['state']['steps']
        and comp['observation']['stop_s']==cp['state']['t'] and exit_record['returncode']==0 and not exit_record['forced_cutoff_stop'])
    api.require(physical+diag+unaccepted+unknown<=500000 and 1730512+physical+diag+unaccepted+unknown<=2500000,'Combined old/new saved-step bounds')
    destination=OUT/'final_disposition_01';c.bound();c.commit(destination/'recoverable/checkpoint.json',cp);c.commit(destination/'recoverable/prefix.json',prefix.reference())
    artifacts={str(q):c.sha(q) for q in RUN.rglob('*') if q.is_file()};artifacts.update({str(q):c.sha(q) for q in (destination/'recoverable').glob('*.json')})
    if comp:artifacts.update({str(q):c.sha(q) for q in (OUT/NAME/'comparison_01').glob('*.json')})
    final=dict(passed=True,accounting_authenticated=True,scientific_full_path_passed=scientific,qualification_passed=qualified,
        accepted_physical_steps=physical,discarded_diagnostic_steps=diag,known_unaccepted_saved_steps=unaccepted,unknown_saved_steps_reservation_upper_bound=unknown,
        cumulative_physical_steps=cp['state']['steps'],cumulative_production_calls=173+len(entries),new_production_segments=len(entries),time_s=cp['state']['t'],
        reason='worker_failure' if result is None else result['reason'],worker_exit=exit_record,inherited_seed_sha256=c.sha(SEED),
        final_checkpoint_sha256=api.digest(cp),records=records,reader_stats=offline.stats,artifacts=artifacts,source_files=p['source_files'],utc=c.utc(),
        successor_cases_started=0,contact_prototype_promoted=False,claim=p['claim'])
    api.require(output_bytes()<p['maximum_new_output_bytes'],'Combined new retention cap');c.bound();c.commit(destination/'results.json',final)
    c.commit(destination/'completion.json',dict(passed=True,results_sha256=c.sha(destination/'results.json')));update_plan('finalized',final)
    print('TAIL_AUTHENTICATED',scientific,physical,unaccepted,unknown,flush=True)

def negative_finalization(exit_record,error):
    """Count diagnostic-only negatives without promoting them or assuming closure."""
    a=c.bound();control=RUN.with_name(RUN.name+'_controller')
    worker=c.read(control/'worker_launch.json')
    api.require(worker.get('authorization_sha256')==c.sha(AUTH)
        and type(a['maximum_saved_steps_including_diagnostics']) is int
        and 0<a['maximum_saved_steps_including_diagnostics']<=500000
        and a['qualification_steps_per_case']==512,'Frozen new clock and bounded failure authority')
    ceiling=min(a['maximum_saved_steps_including_diagnostics'],
        a['maximum_combined_sphere_saved_steps']-a['prior_sphere_saved_steps'])
    api.require(ceiling>=512,'Positive authorized diagnostic failure bound')
    records=[];observed=0
    row=dict(passed=False,accounting_authenticated=False,scientific_full_path_passed=False,
        qualification_passed=False,diagnostic_trajectory_promoted=False,dependent_dispatch_stopped=True,
        original_finalizer_error=repr(error),worker_exit=exit_record,authorization_sha256=c.sha(AUTH),
        discarded_diagnostic_steps=None,known_unaccepted_saved_steps=None,
        unknown_saved_steps_reservation_upper_bound=ceiling,
        conservative_possible_permitted_new_work_upper_bound=ceiling,
        upper_bound_meaning='Possible permitted saved work, not observed executed steps; manual closure required.',
        last_accepted_seed_file=str(SEED),last_original_raw_chain_preserved=True,
        promoted_new_physical_steps=0,successor_cases_started=0,contact_prototype_promoted=False,
        manual_closure_required=True,records=records)
    try:
        p=verify();d,case=original_case();seed_cp,seed_prefix,seed_previous=seed_state(p)
        api.require(isinstance(exit_record,dict) and exit_record.get('retired_exact_identity') is True
            and exit_record.get('launch_sha256')==c.sha(control/'worker_launch.json')
            and worker.get('argv')==[str(old.controller.PYTHON),'-B','-u',str(SELF),'run']
            and old.controller.inspect(worker['pid'],worker['created'],worker['argv'])['retired'],
            'Exact retired worker before diagnostic-only negative accounting')
        api.require(not any((RUN/NAME).glob('segment_*')),'Production exists; retain manual conservative closure')
        row.update(source_input_authentication_passed=True,inherited_seed_sha256=c.sha(SEED),
            final_checkpoint_sha256=api.digest(seed_cp),time_s=seed_cp['state']['t'],
            cumulative_physical_steps=seed_cp['state']['steps'],new_production_segments=0)
        offline=reader.Reader(job.codec,fresh_bound=c.bound)
        identities=dict(authorization_sha256=p['authorization_sha256'],transport_design_sha256=c.sha(PLAN),
            physical_design_sha256=p['physical_design_sha256'],simulation_cutoff_utc=p['simulation_cutoff_utc'])
        qroot=RUN/NAME/'qualification_01';decoded={};admitted={};discarded=unaccepted=unknown=0
        for label,cap in (('serial_01',256),('split_a_01',128),('split_b_01',128)):
            c.bound();folder=qroot/label;item=dict(folder=str(folder),role='restart_diagnostic',reserved_steps=cap)
            records.append(item)
            if label=='split_b_01':
                if 'split_a_01' not in decoded:
                    unknown+=cap;item.update(status='unknown',saved_step_upper_bound=cap,error='Independent split-a parent unavailable');continue
                parent,prefix=decoded['split_a_01'][0]['result']['checkpoint'],decoded['split_a_01'][1]
                previous=c.sha(qroot/'split_a_01/results.json') if (qroot/'split_a_01/results.json').is_file() else None
            else:
                parent,prefix,previous=seed_cp,seed_prefix,seed_previous;offline.prime(prefix)
            marker_ok=True
            try:old.marker_checks(c.read(folder/'launch.json'),'restart_diagnostic',cap,api.digest(parent),identities,p,worker)
            except Exception as issue:
                c.bound();marker_ok=False;item['marker_error']=repr(issue)
            try:
                rec,checked=offline.read_record(folder/'call.json.xz',p['physical_design_sha256'],prefix);c.bound()
                cp=rec['result']['checkpoint'];n=len(rec['rows'])
                api.require(type(cp['state']['steps']) is int and type(parent['state']['steps']) is int,
                    'Integer independent cumulative diagnostic steps')
                old.saved_count(n,cp['state']['steps']-parent['state']['steps'],n,cap)
                api.require(rec['spec']==case['spec'] and rec['effective_binding']==job.parent.model.binding_for(p['original_binding'],True)
                    and rec['numerical_policy_contract_sha256']==p['numerical_policy_contract_sha256']
                    and cp['contract']==p['checkpoint_contract'] and api.digest(cp['state'])==cp['state_sha256']
                    and rec['input_checkpoint_sha256']==api.digest(parent),'Original diagnostic raw/spec/binding/policy/full-checkpoint association')
            except Exception as issue:
                c.bound();unknown+=cap;item.update(status='unknown',saved_step_upper_bound=cap,error=repr(issue));continue
            decoded[label]=(rec,checked);observed+=n;receipt_ok=False
            complete=(folder/'results.json').is_file() and (folder/'completion.json').is_file()
            if complete:
                receipt=c.sealed(folder/'results.json');c.verify(receipt['artifacts']);c.bound()
                api.require(receipt['artifacts'].get(str(folder/'call.json.xz'))==c.sha(folder/'call.json.xz')
                    and receipt.get('role')=='restart_diagnostic' and receipt.get('new_saved_steps')==n
                    and receipt.get('input_checkpoint_sha256')==api.digest(parent)
                    and receipt.get('output_checkpoint_sha256')==api.digest(cp) and receipt.get('previous_receipt_sha256')==previous
                    and receipt.get('transport_design_sha256')==identities['transport_design_sha256']
                    and receipt.get('physical_design_sha256')==identities['physical_design_sha256']
                    and receipt.get('numerical_policy_contract_sha256')==p['numerical_policy_contract_sha256']
                    and receipt.get('original_binding')==p['original_binding'],'Sealed independent diagnostic evidence association')
                receipt_ok=receipt.get('passed') is True and receipt.get('summary',{}).get('passed') is True
                if receipt_ok:
                    api.require(receipt['artifacts'].get(str(folder/'trace.npy'))==c.sha(folder/'trace.npy'),'Sealed raw trace hash')
                    trace=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
                    api.require(np.array_equal(trace,np.load(folder/'trace.npy',allow_pickle=False)),'Exact independently decoded diagnostic trace')
            metadata_ok=True
            if (folder/'accounting.json').is_file():
                metadata=c.read(folder/'accounting.json')
                api.require(metadata.get('saved_steps_known') is True and metadata.get('role')=='restart_diagnostic'
                    and metadata.get('raw_sha256')==c.sha(folder/'call.json.xz'),'Independent diagnostic accounting/raw association')
                old.saved_count(n,cp['state']['steps']-parent['state']['steps'],metadata['saved_steps'],cap)
            accepted=bool(marker_ok and complete and receipt_ok and metadata_ok and n>0
                and (label!='split_b_01' or admitted.get('split_a_01') is True))
            admitted[label]=accepted
            if accepted:discarded+=n
            else:unaccepted+=n
            item.update(status='discarded_diagnostic' if accepted else 'known_unaccepted',saved_steps=n,
                independently_decoded=True,raw_sha256=c.sha(folder/'call.json.xz'))
        exact=False
        if len(decoded)==3:
            serial,split_a,split_b=[decoded[k][0] for k in ('serial_01','split_a_01','split_b_01')]
            exact=(len(serial['rows'])==256 and len(split_a['rows'])==len(split_b['rows'])==128
                and serial['rows']==split_a['rows']+split_b['rows']
                and api.digest(serial['result']['checkpoint'])==api.digest(split_b['result']['checkpoint']))
        if (qroot/'results.json').is_file() and (qroot/'completion.json').is_file():
            proof=c.sealed(qroot/'results.json');c.verify(proof['artifacts']);c.bound()
            api.require(proof.get('transport_design_sha256')==c.sha(PLAN)
                and proof.get('production_seed_sha256')==api.digest(seed_cp)
                and proof.get('diagnostic_trajectory_promoted') is False,'Negative qualification retains original production seed')
        api.require(discarded+unaccepted==observed and observed+unknown<=512,'Diagnostic-only independently decoded and conservative512 bound')
        row.update(accounting_authenticated=True,discarded_diagnostic_steps=discarded,known_unaccepted_saved_steps=unaccepted,
            unknown_saved_steps_reservation_upper_bound=unknown,conservative_possible_permitted_new_work_upper_bound=observed+unknown,
            exact_readable_restart_passed=exact,manual_closure_required=unknown>0,reader_stats=offline.stats,
            upper_bound_meaning='Independently decoded diagnostic work plus remaining frozen diagnostic reservations; no production promotion.')
    except Exception as issue:
        c.bound();row.update(accounting_error=repr(issue),manual_closure_required=True,
            unknown_saved_steps_reservation_upper_bound=max(0,ceiling-observed))
    row.update(independently_observed_diagnostic_steps=observed,utc=c.utc())
    artifacts={str(q):c.sha(q) for q in (AUTH,PLAN,SEED,control/'worker_launch.json',control/'worker_exit.json',RUN/'failure.json') if q.is_file()}
    row['artifacts']=artifacts;destination=OUT/'failure_disposition_01';c.bound();c.commit(destination/'results.json',row)
    c.bound();c.commit(destination/'completion.json',dict(passed=False,nonpromoting=True,results_sha256=c.sha(destination/'results.json')))
    print('TAIL_FAILURE_ACCOUNTED',row['accounting_authenticated'],observed,row['unknown_saved_steps_reservation_upper_bound'],flush=True)

def finalizer_entry():
    exit_record=None
    try:
        a=verify_authority();psutil.Process().cpu_affinity([a['logical_cpu']])
        exit_record=c.read(RUN.with_name(RUN.name+'_controller')/'worker_exit.json');finalize(exit_record)
    except Exception as error:
        try:negative_finalization(exit_record,error)
        except Exception as accounting_error:print('TAIL_NEGATIVE_ACCOUNTING_FAILED',repr(accounting_error),flush=True)
        raise

def launch():
    a=verify_authority();control=RUN.with_name(RUN.name+'_controller');control.mkdir(parents=True,exist_ok=False)
    process=psutil.Process();c.commit(control/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=c.utc(),authorization_sha256=c.sha(AUTH)))
    command=[str(old.controller.PYTHON),'-B','-u',str(SELF),'run'];env=os.environ.copy();child=birth=None
    def execute(command,stem,cutoff):
        child=birth=None;forced=False
        try:
            with (control/(stem+'_stdout.log')).open('xb') as stdout,(control/(stem+'_stderr.log')).open('xb') as stderr:
                child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                birth=psutil.Process(child.pid).create_time();api.require(psutil.Process(child.pid).cmdline()==command,'Exact '+stem+' command')
                c.commit(control/(stem+'_launch.json'),dict(pid=child.pid,created=birth,argv=command,utc=c.utc(),authorization_sha256=c.sha(AUTH)))
                while child.poll() is None:
                    if time.time()>=cutoff:old.controller.stop_owned(child,birth,command,control);forced=True;break
                    time.sleep(1)
                code=child.wait(timeout=10)
            identity=old.controller.inspect(child.pid,birth,command);api.require(identity['retired'],'Exact '+stem+' retired')
            row=dict(returncode=code,forced_cutoff_stop=forced,retired_exact_identity=True,identity=identity,launch_sha256=c.sha(control/(stem+'_launch.json')),
                closed_logs={str(q):c.sha(q) for q in control.glob(stem+'_*.log')},utc=c.utc())
            c.commit(control/(stem+'_exit.json'),row);return row
        except Exception:
            if child is not None and birth is not None:old.controller.stop_owned(child,birth,command,control)
            raise
    try:
        exit_record=execute(command,'worker',datetime.fromisoformat(a['simulation_cutoff_utc']).timestamp())
        if PLAN.exists() and (SEED.parent/'completion.json').exists():
            command=[str(old.controller.PYTHON),'-B','-u',str(SELF),'finalize']
            final_exit=execute(command,'finalizer',datetime.fromisoformat(a['end_utc']).timestamp()-30)
            api.require(final_exit['returncode']==0 and not final_exit['forced_cutoff_stop'],'Complete bounded final accounting')
        else:raise RuntimeError('Seed/admission incomplete; no numerical promotion or successor dispatch')
        c.bound();c.commit(control/'completion.json',dict(passed=True,authorization_sha256=c.sha(AUTH),closed_logs={str(q):c.sha(q) for q in control.glob('*.log')},utc=c.utc()))
    except Exception as error:
        c.commit(control/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),raw_work_preserved=True,utc=c.utc(),dependent_dispatch_stopped=True));raise

def update_plan(status,data):
    path=ROOT/'MASTER_PLAN.md';text=path.read_text(encoding='utf-8');begin='<!-- STAGE232_SPHERE_TAIL_BEGIN -->';end='<!-- STAGE232_SPHERE_TAIL_END -->'
    a=c.read(AUTH)
    if status=='running':
        paragraph=f"Stage232 has independently reconstructed the closed Stage231 raw/checkpoint/history chain:173 production segments /1,730,000 physical steps plus512 discarded diagnostics at3.9087651707868227s. The original forced finalizer failure remains preserved. A separately bounded original sphere tail is active under [design](stage232_designs/sample0_sphere_tail_20261008/design_01.json), ending numerical work at {a['simulation_cutoff_utc']} and all bounded auditing at {a['end_utc']}. Fresh late-seed512 exact rows/FULL-checkpoint qualification is mandatory before production. The reader repair is offline accounting only; original transport, physical gates, factor0.125 and fine-reference full-path/event gates remain unchanged. Limits:500,000 new saved steps including diagnostics,50 calls, original combined250-call/2.5million-saved-step ceilings,one worker/thread,4GiB new output and20GiB disk reserve. No successor case or contact prototype is authorized."
    else:
        paragraph=f"Stage232 numerical worker is retired. [Final accounting](stage232_evaluations/sample0_sphere_tail_20261008/final_disposition_01/results.json):{data['reason']}; original complete-path accuracy passed={data['scientific_full_path_passed']}. New accepted physical steps={data['accepted_physical_steps']},discarded diagnostics={data['discarded_diagnostic_steps']},known unaccepted={data['known_unaccepted_saved_steps']},unknown reserved upper bound={data['unknown_saved_steps_reservation_upper_bound']}. Combined sphere path:{data['cumulative_production_calls']} production segments/{data['cumulative_physical_steps']} physical steps at{data['time_s']:.12g}s. Full readable checkpoint/history ancestry is preserved; final controller retirement/log closure remains a separate check. Earlier failures remain preserved. One labelled packing/flow does not establish population shape/flow trends or irreversible retention."
    block=begin+'\n## Stage232 bounded sphere tail — 8 October 2026\n\n'+paragraph+'\n'+end
    if begin in text:
        left=text.index(begin);right=text.index(end,left)+len(end);text=text[:left]+block+text[right:]
    else:text=text.replace('<!-- STAGE231_SPHERE_BEGIN -->',block+'\n\n<!-- STAGE231_SPHERE_BEGIN -->',1)
    path.write_text(text,encoding='utf-8',newline='\n');(ROOT/'CURRENT_PLAN.md').write_text('# Current execution: Stage232 sphere tail '+status+'\n\n[MASTER_PLAN.md](MASTER_PLAN.md) is authoritative.\n\n'+paragraph+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':{'prepare':prepare,'launch':launch,'run':run,'finalize':finalizer_entry}[sys.argv[1]]()
