"""Configuration-driven original-model verification, with one bounded case.

Reuse the original transaction, restart and full-path functions by exact code
identity in private globals. No physical model or frozen source is copied or
modified. The configuration controls clocks, one admitted case and resources.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import FunctionType, ModuleType
import copy, math, os, shutil, subprocess, sys, time, traceback
import numpy as np
import psutil

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
DEFAULT=ROOT/'stage231_designs/sample0_sphere_20261008/design_01.json'
PLAN=Path(os.environ.get('DEM_CASE_PLAN',str(DEFAULT))).resolve()
api_path=ROOT/'stage229_staging'
sys.path.insert(0,str(api_path))
import continue_baseline_v3 as prior
sys.path.insert(0,str(ROOT/'stage230_staging'))
import tail_common_v1 as common
import launch_tail_v1 as controller

api,job,baseline=prior.api,prior.job,prior.baseline
c=ModuleType('_single_case_administration')
c.__dict__.update(vars(common))
c.ROOT=ROOT;c.PLAN=PLAN;c.AUTH=PLAN.with_name('authorization_01.json')
c.DESIGNS=PLAN.parent
c.RUN=ROOT/'stage231_runs'/PLAN.parent.name/'run_01'
c.OUT=ROOT/'stage231_evaluations'/PLAN.parent.name
for name,fn in vars(common).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(common):
        setattr(c,name,FunctionType(fn.__code__,vars(c),fn.__name__,fn.__defaults__,fn.__closure__))

NAMES=('verify_frozen_file','verify_frozen_mapping','physical_design','verify_scientific_inputs','segment','qualify','compare')
PRIVATE=dict(vars(prior),c=c,PLAN=PLAN,RUN=c.RUN,OUT=c.OUT,AUTH=c.AUTH)
for name in NAMES:
    fn=getattr(prior,name)
    PRIVATE[name]=FunctionType(fn.__code__,PRIVATE,fn.__name__,fn.__defaults__,fn.__closure__)
FIBRE=ROOT/'stage230_evaluations/sample0_fibre_terminal_20261008'
EXPECTED={
    str(FIBRE/'final_disposition_01/results.json'):'52bf65f6390722ecb59ec0639ab853c762f8e5e98e2351e4b0ead0b81018380b',
    str(FIBRE/'retirement_01/results.json'):'05799ca292d0160bbea197fc50b685acf277325db9aaec4847073d99c8666d1a',
    str(FIBRE/'final_receipt_01/results.json'):'2f464ff291c1b71122c77a8c569048afa0e8261551bc088a3da10e5c4fb4912c',
    str(baseline.PREREQUISITE):'8ddadfdee04ec86a38e327103957dc6b09c47b1392d61a001b4f6046c391a884',
}

def clone_checks():
    baseline.clone_check()
    for name in NAMES:
        api.require(PRIVATE[name].__code__ is getattr(prior,name).__code__ and PRIVATE[name].__globals__ is PRIVATE,
                    'Exact original private function '+name)
    api.require(prior.c is not c and prior.PLAN!=PLAN and job.DESIGN==baseline.PLAN,
                'Old closed administrative and original physical bindings unchanged')
    return dict(passed=True,exact_code_objects=list(NAMES),physical_binding_unchanged=True,
                numerical_calls=0,new_trajectory_steps=0)

def controls():
    """Reuse tested identity guards; exercise new resource and partial-ledger rules."""
    checks=[]
    for used,needed,want in [(0,512,True),(2500000,1,False),(2499900,512,False)]:
        assert (used+needed<=2500000)==want;checks.append('saved_step_reservation')
    assert saved_count(3,3,3,10)==3
    for args in [(3,4,3,10),(3,3,4,10),(11,11,11,10),(-1,-1,-1,10)]:
        try:saved_count(*args)
        except RuntimeError:checks.append('raw_step_count_tamper_rejected')
        else:raise AssertionError('Bad saved counts accepted')
    checks.extend(accounting_controls())
    old=c.sealed(FIBRE/'preflight_02/results.json')
    api.require(old['passed'] and old['numerical_calls']==old['process_actions']==0,'Qualified original identity/resource controls')
    for path,h in old['sources'].items():api.require(c.sha(path)==h,'Original reviewed helper source')
    return dict(passed=True,checks=checks,prior_exact_identity_read_controls=len(old['controls']),
                prior_controls_sha256=c.sha(FIBRE/'preflight_02/results.json'),clone_checks=clone_checks(),numerical_calls=0)

def saved_count(rows,delta,metadata,cap):
    api.require(all(type(x) is int for x in (rows,delta,metadata,cap)) and cap>0
                and 0<=rows<=cap and rows==delta==metadata,'Independent raw/count/cumulative ledger')
    return rows

def marker_checks(marker,role,cap,parent_digest,identities,window,worker):
    """A reservation comes from frozen limits, never an untrusted marker count."""
    api.require(isinstance(marker,dict) and type(marker.get('maximum_saved_steps')) is int
        and 0<marker['maximum_saved_steps']<=window['step_cap_per_call']
        and (cap is None or marker['maximum_saved_steps']==cap)
        and marker.get('role')==role,'Exact frozen role and positive bounded reservation')
    for key,value in identities.items():api.require(marker.get(key)==value,'Exact launch authority '+key)
    api.require(type(marker.get('pid')) is int and marker['pid']==worker['pid']
        and type(marker.get('created')) in (int,float) and marker['created']==worker['created']
        and bool(marker.get('argv')) and marker['argv']==worker['argv'],'Exact recorded worker birth and full command')
    if parent_digest is not None:
        api.require(marker.get('input_checkpoint_sha256')==parent_digest,'Exact launch checkpoint parent')
    clocks=[datetime.fromisoformat(x) for x in (window['start_utc'],marker['utc'],window['simulation_cutoff_utc'])]
    api.require(all(x.utcoffset() is not None for x in clocks) and clocks[0]<=clocks[1]<clocks[2],
                'Aware launch time within the frozen numerical window')
    return marker['maximum_saved_steps']

def qualification_checks(diagnostics,proof,design_sha256):
    """An exact-restart negative is a counted result, not an accounting exception."""
    if not all(k in diagnostics for k in ('serial_01','split_a_01','split_b_01')):return False,False
    a,b,z=[diagnostics[k][0] for k in ('serial_01','split_a_01','split_b_01')]
    exact=(len(a['rows'])==256 and len(b['rows'])==len(z['rows'])==128
        and a['rows']==b['rows']+z['rows']
        and api.digest(a['result']['checkpoint'])==api.digest(z['result']['checkpoint']))
    sealed=bool(exact and proof and proof.get('passed') is True
        and proof.get('diagnostic_saved_steps')==512
        and proof.get('exact_serial_split_rows') is True and proof.get('exact_full_checkpoint') is True
        and proof.get('all_three_independent_physical_audits_passed') is True
        and proof.get('production_seed_unchanged') is True
        and proof.get('production_seed_sha256')==api.digest(None)
        and proof.get('transport_design_sha256')==design_sha256
        and proof.get('diagnostic_trajectory_promoted') is False)
    return exact,sealed

def scientific_gate(result,comparison,qualified,exit_record,name,reference,production_count):
    checks=('endpoint_q_over_U_max','exit_time_difference','first_dwell_time_difference',
        'mean_L1_q_over_U_max','same_dwell_flag','same_terminal_label',
        'whole_axis_vector_norm_max','whole_position_over_b_max')
    if not result or not comparison:return False
    observation=comparison.get('observation',{});case=result.get('case',{});gates=comparison.get('full_path_gates',{})
    return bool(qualified and result.get('passed') is True and result.get('reason')=='full_path_accuracy_passed'
        and case.get('case')==name and case.get('complete_observation') is True
        and comparison.get('passed') is True and comparison.get('case')==name
        and comparison.get('reference_case')==reference and comparison.get('full_original_start_to_terminal_path') is True
        and comparison.get('inherited_segments')==0 and comparison.get('new_segments')==production_count
        and gates.get('passed') is True and all(gates.get('checks',{}).get(key) is True for key in checks)
        and observation.get('complete_observation') is True and observation.get('start_s')==0.
        and observation.get('steps')==case.get('cumulative_physical_steps')
        and observation.get('stop_s')==case.get('time_s')
        and type(exit_record.get('returncode')) is int and exit_record['returncode']==0
        and exit_record.get('retired_exact_identity') is True and exit_record.get('forced_cutoff_stop') is False)

def accounting_controls():
    """Pure authority, partial-count, restart-negative and missing-proof controls."""
    checks=[]
    for args in [(3,3,3.,10),(3,True,3,10),(3,3,3,True),(0,0,0,0)]:
        try:saved_count(*args)
        except RuntimeError:checks.append('noninteger_or_invalid_count_rejected')
        else:raise AssertionError('Untrusted saved count accepted')
    window=dict(start_utc='2026-10-08T12:00:00+00:00',simulation_cutoff_utc='2026-10-08T15:00:00+00:00',step_cap_per_call=10000)
    identities=dict(authorization_sha256='auth',transport_design_sha256='design',physical_design_sha256='physical',simulation_cutoff_utc=window['simulation_cutoff_utc'])
    worker=dict(pid=17,created=123.,argv=['python','case.py','run'])
    marker=dict(**identities,**worker,role='restart_diagnostic',maximum_saved_steps=256,
        input_checkpoint_sha256='parent',utc='2026-10-08T12:00:01+00:00')
    assert marker_checks(marker,'restart_diagnostic',256,'parent',identities,window,worker)==256
    for key,value in [('maximum_saved_steps',-1),('maximum_saved_steps',True),('maximum_saved_steps',10001),
        ('maximum_saved_steps',128),('role','production'),('authorization_sha256','wrong'),
        ('transport_design_sha256','wrong'),('physical_design_sha256','wrong'),('input_checkpoint_sha256','wrong'),
        ('pid',18),('created',124.),('argv',[]),('argv',['other']),('simulation_cutoff_utc','wrong'),
        ('utc','2026-10-08T12:00:01'),('utc','2026-10-08T15:00:00+00:00')]:
        bad={**marker,key:value}
        try:marker_checks(bad,'restart_diagnostic',256,'parent',identities,window,worker)
        except (RuntimeError,ValueError):checks.append('marker_tamper_rejected_'+key)
        else:raise AssertionError('Invalid launch marker accepted: '+key)
    cp={'state':{'steps':256},'contract':'same'}
    diagnostics={key:({'rows':rows,'result':{'checkpoint':copy.deepcopy(cp)}},None) for key,rows in
        [('serial_01',list(range(256))),('split_a_01',list(range(128))),('split_b_01',list(range(128,256)))]}
    proof=dict(passed=True,diagnostic_saved_steps=512,exact_serial_split_rows=True,exact_full_checkpoint=True,
        all_three_independent_physical_audits_passed=True,production_seed_unchanged=True,
        production_seed_sha256=api.digest(None),transport_design_sha256='design',diagnostic_trajectory_promoted=False)
    assert qualification_checks(diagnostics,proof,'design')==(True,True)
    assert qualification_checks(diagnostics,None,'design')==(True,False);checks.append('missing_qualification_seal_blocks_production')
    bad=copy.deepcopy(diagnostics);bad['split_b_01'][0]['rows'][0]=-1
    assert qualification_checks(bad,proof,'design')==(False,False)
    assert sum(len(x[0]['rows']) for x in bad.values())==512;checks.append('readable_restart_negative_keeps512_steps')
    bad=copy.deepcopy(diagnostics);bad['split_b_01'][0]['result']['checkpoint']['state']['steps']=257
    assert qualification_checks(bad,proof,'design')==(False,False);checks.append('full_checkpoint_restart_mismatch_blocks_production')
    for key,value in [('diagnostic_saved_steps',511),('production_seed_sha256','wrong'),('diagnostic_trajectory_promoted',True),('transport_design_sha256','wrong')]:
        assert qualification_checks(diagnostics,{**proof,key:value},'design')==(True,False)
        checks.append('qualification_proof_tamper_blocks_production_'+key)
    result=dict(passed=True,reason='full_path_accuracy_passed',case=dict(case='sphere',complete_observation=True,cumulative_physical_steps=10,time_s=1.))
    gate_names=('endpoint_q_over_U_max','exit_time_difference','first_dwell_time_difference','mean_L1_q_over_U_max',
        'same_dwell_flag','same_terminal_label','whole_axis_vector_norm_max','whole_position_over_b_max')
    comp=dict(passed=True,case='sphere',reference_case='fine',full_original_start_to_terminal_path=True,inherited_segments=0,new_segments=1,
        full_path_gates=dict(passed=True,checks=dict.fromkeys(gate_names,True)),observation=dict(complete_observation=True,start_s=0.,steps=10,stop_s=1.))
    exit_record=dict(returncode=0,retired_exact_identity=True,forced_cutoff_stop=False)
    assert scientific_gate(result,comp,True,exit_record,'sphere','fine',1)
    assert not scientific_gate(result,None,True,exit_record,'sphere','fine',1);checks.append('missing_comparison_blocks_scientific_promotion')
    assert not scientific_gate(result,comp,False,exit_record,'sphere','fine',1);checks.append('failed_restart_blocks_scientific_promotion')
    for key,value in [('passed',False),('reference_case','wrong'),('new_segments',2),('inherited_segments',1),('full_original_start_to_terminal_path',False)]:
        assert not scientific_gate(result,{**comp,key:value},True,exit_record,'sphere','fine',1)
        checks.append('comparison_tamper_blocks_promotion_'+key)
    bad=copy.deepcopy(comp);bad['full_path_gates']['checks']['whole_position_over_b_max']=False
    assert not scientific_gate(result,bad,True,exit_record,'sphere','fine',1);checks.append('failed_original_path_gate_blocks_promotion')
    assert not scientific_gate(result,comp,True,{**exit_record,'forced_cutoff_stop':True},'sphere','fine',1)
    checks.append('forced_cutoff_blocks_scientific_promotion')
    return checks

def matched_physics(d,case):
    fibre=next(x for x in d['cases'] if x['id']=='s2_i0_fibre_f0p125')
    sphere_spec,fibre_spec=case['spec'],fibre['spec']
    a,b=sphere_spec['config'],fibre_spec['config']
    for key in ('field_metadata','initial_state','seed','sample_id','cpd','flow_factor','horizon_pv','horizon_s','nominal_speed_m_s','refinement'):
        api.require(sphere_spec[key]==fibre_spec[key],'Original matched shape control '+key)
    api.require({k:v for k,v in a.items() if k!='prolate_semiaxes_m'}==
                {k:v for k,v in b.items() if k!='prolate_semiaxes_m'},'Original matched material, loading and numerical controls')
    sphere_volume=4*math.pi*math.prod(a['prolate_semiaxes_m'])/3
    fibre_volume=4*math.pi*math.prod(b['prolate_semiaxes_m'])/3
    api.require(sphere_volume>0 and math.isclose(sphere_volume,fibre_volume,rel_tol=1e-12,abs_tol=0),
                'Original equal particle volume to floating-point rounding')
    return dict(passed=True,sphere_volume_m3=sphere_volume,fibre_volume_m3=fibre_volume,
        equal_volume_relative_tolerance=1e-12,flow_m_s=a['target_mean_interstitial_velocity_m_s'],
        horizon_s=sphere_spec['horizon_s'],packing_seed=sphere_spec['seed'],placement=sphere_spec['sample_id'],
        same_field_material_initial_state_and_numerics=True,numerical_calls=0)

def static_case(plan):
    d=PRIVATE['physical_design']()
    case=next(x for x in d['cases'] if x['id']==plan['only_case'])
    api.require(case['id']=='s2_i0_sphere_f0p125' and case['sample_id']==0 and case['shape']=='equal_volume_sphere'
        and case['factor']==.125,'Exactly the next original matched sphere case')
    binding=job.binding(d,case)
    contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(binding,True))
    api.require(plan['original_binding']==binding and plan['checkpoint_contract']==contract,'Original fresh-case physical contract')
    api.require(plan['matched_physics']==matched_physics(d,case),'Frozen original matched physical controls')
    return d,case

def prepare():
    c.environment();clone_checks()
    api.require(not PLAN.exists() and not c.AUTH.exists() and not c.RUN.exists(),'Fresh single-case attempt only')
    pure=controls()
    start=datetime.now(timezone.utc);end=start+timedelta(hours=3.5)
    auth=dict(stage='Stage231 matched sphere numerical verification',start_utc=start.isoformat(),end_utc=end.isoformat(),
        simulation_cutoff_utc=(end-timedelta(minutes=30)).isoformat(),human_authorization='Fresh human next after completed Stage230; only next original matched sphere gate.',
        only_case='s2_i0_sphere_f0p125',maximum_saved_steps_including_diagnostics=2500000,maximum_new_production_calls=250,
        maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,step_cap_per_call=10000,
        qualification_steps_per_case=512,workers=1,threads=1,logical_cpu=14,maximum_unverified_records=1,
        finalizer_retirement_reserve_seconds=30,
        minimum_free_disk_bytes=20*1024**3,maximum_new_output_bytes=8*1024**3,
        successor_dispatch_authorized=False,candidate_production_authorized=False,physics_changes=[],accuracy_gate_changes=[],
        retention='Retain this admitted current verification raw/checkpoint/history, traces, compact failure/censoring metadata and required independent receipts. No model copies or speculative outputs; 8GiB output cap plus original20GiB disk reserve.',
        prior_campaigns_remain_closed=True,master_plan_sha256_at_authorization=c.sha(ROOT/'MASTER_PLAN.md'))
    c.commit(c.AUTH,auth)
    c.verify(EXPECTED)
    fibre=c.sealed(FIBRE/'final_disposition_01/results.json');retired=c.sealed(FIBRE/'retirement_01/results.json')
    api.require(fibre['scientific_full_path_passed'] and retired['all_exact_launch_identities_retired'],'Preceding original fibre gate complete and retired')
    oldplan=c.read(ROOT/'stage229_designs/overnight_20261007/transport_design_03.json')
    d=PRIVATE['physical_design']();baseline.verify(d);baseline.old.verify(api.read(baseline.old.DESIGN));baseline.source.bindings()
    case=next(x for x in d['cases'] if x['id']==auth['only_case'])
    ref=next(x for x in api.read(baseline.old.DESIGN)['cases'] if x['sample_id']==0 and x['shape']==case['shape'] and x['factor']==.03125)
    proof=c.sealed(baseline.PREREQUISITE);api.require(proof['passed'],'Original complete reference gates')
    traces=sorted((baseline.old.RUN/ref['id']).glob('segment_*.npy'))
    api.require(len(traces)==829,'Exact complete original fine sphere trace inventory')
    physical_inputs={**d['inputs'],str(job.DESIGN):c.sha(job.DESIGN),str(job.WORK):c.sha(job.WORK)}
    inputs={**physical_inputs,**EXPECTED,**{str(p):proof['artifacts'][str(p)] for p in traces}}
    for p in list(EXPECTED):inputs[str(Path(p).parent/'completion.json')]=c.sha(Path(p).parent/'completion.json')
    sources={**oldplan['source_files'],str(SELF):c.sha(SELF),**{str(p):c.sha(p) for p in (ROOT/'stage230_staging').glob('*.py')}}
    c.verify(sources);c.verify(inputs)
    binding=job.binding(d,case);contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(binding,True))
    plan=dict(**auth,authorization_sha256=c.sha(c.AUTH),authorized_end_utc=auth['end_utc'],source_files=sources,inputs=inputs,
        physical_inputs=physical_inputs,physical_design_sha256=c.sha(job.DESIGN),numerical_policy_contract_sha256=c.sha(job.WORK),
        original_binding=binding,checkpoint_contract=contract,reference_case=ref['id'],fresh_start=True,
        matched_physics=matched_physics(d,case),
        inherited=dict(inherited_segments=0,inherited_physical_steps=0,trace_paths=[],inputs=EXPECTED),
        physical_changes=[],numerical_changes=[],claim='Finite-level temporal verification of the labelled sample0 sphere at the same packing/flow as the fibre. No population shape/flow ranking, spatial convergence, experimental validation or guaranteed speedup.',
        controls=pure,planning_cost='About2.07million steps and2.25producer-plus-physical-audit hours inferred from original0.0625cost; planning estimate only, other decoding/hash overhead excluded.')
    plan['binding']=c.digest(plan);c.commit(PLAN,plan)
    c.commit(c.OUT/'preparation_01/results.json',dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(c.AUTH),
        controls=pure,reference_trace_count=len(traces),source_count=len(sources),input_count=len(inputs),numerical_calls=0,new_trajectory_steps=0))
    c.commit(c.OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(c.OUT/'preparation_01/results.json')))
    print('SINGLE_CASE_PREPARED',auth['only_case'],auth['end_utc'],flush=True)

def verify():
    auth=c.bound();c.environment();clone_checks();p=c.read(PLAN)
    api.require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(c.AUTH),'Frozen new single-case authority')
    for key,value in auth.items():api.require(p[key]==value,'Exact original bounded authority '+key)
    api.require(not p['successor_dispatch_authorized'] and not p['candidate_production_authorized']
                and p['physical_changes']==p['numerical_changes']==p['accuracy_gate_changes']==[],'No changed physics, gates or extra case')
    prep=c.sealed(c.OUT/'preparation_01/results.json');api.require(prep['passed'] and prep['design_sha256']==c.sha(PLAN),'Passing preparation')
    c.verify(p['source_files']);c.verify(p['inputs']);static_case(p)
    return p

def output_bytes():
    roots=(c.RUN,c.OUT,c.DESIGNS,c.RUN.with_name(c.RUN.name+'_controller'))
    paths={q.resolve() for root in roots for q in root.rglob('*') if q.is_file()}
    return sum(q.stat().st_size for q in paths)

def stop_reason(p,used,needed):
    c.bound()
    if job.utc()>=job.policy.utc(p['simulation_cutoff_utc'])-timedelta(seconds=120):return 'simulation_cutoff'
    if used+needed>p['maximum_saved_steps_including_diagnostics']:return 'saved_step_ceiling'
    if shutil.disk_usage(ROOT).free<=p['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:return 'disk_reserve'
    retained=output_bytes()
    if retained+4*job.codec.base.MAX_COMPRESSED>=p['maximum_new_output_bytes']:return 'retained_output_cap'
    return None

def run():
    p=verify();d,case=static_case(p)
    c.RUN.mkdir(parents=True,exist_ok=False);process=psutil.Process();process.cpu_affinity([p['logical_cpu']])
    c.commit(c.RUN/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=c.utc(),
        affinity=process.cpu_affinity(),design_sha256=c.sha(PLAN),authorization_sha256=c.sha(c.AUTH)))
    update_plan()
    geometry=baseline.geometry_for(case);cp=prefix=previous=None;entries=[];used=diagnostic=0;reservation=None;rec=None;reason='call_limit'
    try:
        api.require(stop_reason(p,0,512) is None,'Complete fresh qualification fits resources')
        reservation=dict(role='restart_diagnostic',maximum_saved_steps=512)
        diagnostic=PRIVATE['qualify'](p,d,case,geometry,None,None,None);used+=diagnostic;reservation=None
        print('SINGLE_CASE_RESTART_VERIFIED',diagnostic,flush=True)
        for index in range(1,p['maximum_new_production_calls']+1):
            reason=stop_reason(p,used,1)
            if reason:break
            remaining=min(p['maximum_saved_steps_including_diagnostics']-used,p['maximum_cumulative_physical_steps_per_case']-(0 if cp is None else cp['state']['steps']))
            if remaining<=0:reason='case_step_ceiling';break
            cap=min(p['step_cap_per_call'],remaining)
            reservation=dict(role='production',segment=index,maximum_saved_steps=cap,input_checkpoint_sha256=api.digest(cp))
            folder=c.RUN/case['id']/f'segment_{index:05d}'
            rec,prefix,row=PRIVATE['segment'](p,d,case,geometry,cp,prefix,folder,cap,previous,'production')
            cp=rec['result']['checkpoint'];used+=row['new_saved_steps'];previous=c.sha(folder/'results.json')
            entries.append(dict(segment=index,new_saved_steps=row['new_saved_steps'],results_sha256=previous,stop_s=cp['state']['t']))
            reservation=None
            print('SINGLE_CASE_SEGMENT_VERIFIED',index,used,cp['state']['t'],rec['result']['status'],flush=True)
            if rec['result']['status'] in job.policy.COMPLETE:reason='observation_complete';break
        else:reason='call_limit'
        folder=c.RUN/case['id'];result=dict(case=case['id'],complete_observation=reason=='observation_complete',reason=reason,entries=entries,
            cumulative_physical_steps=0 if cp is None else cp['state']['steps'],cumulative_calls=len(entries),diagnostic_saved_steps=diagnostic,
            final_checkpoint_sha256=api.digest(cp),time_s=0. if cp is None else cp['state']['t'],horizon_s=case['spec']['horizon_s'],
            final_status='not_started' if rec is None else rec['result']['status'])
        c.commit(folder/'checkpoint.json',cp);c.commit(folder/'prefix.json',None if prefix is None else prefix.reference())
        c.commit(folder/'results.json',result);c.commit(folder/'completion.json',dict(results_sha256=c.sha(folder/'results.json'),complete_observation=result['complete_observation']))
        comp=None
        if result['complete_observation']:
            comp=PRIVATE['compare'](p,d,case,rec['result'],entries,[])
            reason='full_path_accuracy_passed' if comp['passed'] else 'full_path_accuracy_failed'
        c.commit(c.RUN/'results.json',dict(finished=True,passed=reason=='full_path_accuracy_passed',reason=reason,case=result,
            saved_steps_including_diagnostics=used,accepted_physical_steps=used-diagnostic,discarded_diagnostic_steps=diagnostic,
            comparison_sha256=None if comp is None else c.sha(c.OUT/case['id']/'comparison_01/results.json'),
            known_unaccepted_saved_steps=0,unknown_saved_steps_reservation_upper_bound=0,utc=c.utc(),design_sha256=c.sha(PLAN),
            successor_cases_started=0,contact_prototype_promoted=False,claim=p['claim']))
        c.commit(c.RUN/'completion.json',dict(results_sha256=c.sha(c.RUN/'results.json'),finished=True))
    except Exception as error:
        c.commit(c.RUN/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),verified_saved_steps=used,
            verified_diagnostic_steps=diagnostic,accepted_entries=entries,unresolved_reservation=reservation,
            last_verified_checkpoint_sha256=api.digest(cp),utc=c.utc(),dependent_dispatch_stopped=True))
        raise

def record_checks(rec,d,case,parent,cap):
    cp=rec['result']['checkpoint'];n=len(rec['rows']);start=0 if parent is None else parent['state']['steps']
    api.require(rec['spec']==case['spec'] and rec['effective_binding']==job.parent.model.binding_for(job.binding(d,case),True)
        and rec['numerical_policy_contract_sha256']==c.sha(job.WORK) and rec['input_checkpoint_sha256']==api.digest(parent)
        and cp['contract']==c.read(PLAN)['checkpoint_contract'],'Original raw/spec/binding/policy/checkpoint association')
    saved_count(n,cp['state']['steps']-start,n,cap)
    return n

def authenticate(exit_record):
    """Retired-worker accounting; unsealed work is never promoted from metadata."""
    p=verify();d,case=static_case(p);name=case['id']
    api.require(exit_record.get('retired_exact_identity') is True,'Retired exact numerical worker')
    control=c.RUN.with_name(c.RUN.name+'_controller');worker=c.read(control/'worker_launch.json')
    api.require(exit_record['launch_sha256']==c.sha(control/'worker_launch.json')
        and bool(worker['argv']),'Exit belongs to the exact recorded worker launch')
    identities=dict(authorization_sha256=p['authorization_sha256'],transport_design_sha256=c.sha(PLAN),
        physical_design_sha256=p['physical_design_sha256'],simulation_cutoff_utc=p['simulation_cutoff_utc'])
    cp=prefix=previous=None;diagnostics={};decoded_diagnostics={};records=[];issues=[]
    physical=diag=unaccepted=unknown=0
    def reconstruct(folder,role,cap,parent,parent_prefix,want_previous,eligible,parent_available=True):
        nonlocal unaccepted,unknown
        c.bound();item=dict(folder=str(folder),role=role,reserved_steps=cap);marker_ok=True
        try:
            marker=c.read(folder/'launch.json')
            marker_checks(marker,role,cap if parent_available else None,
                api.digest(parent) if parent_available else None,identities,p,worker)
        except Exception as error:
            c.bound();marker_ok=False;item['marker_error']=repr(error)
        complete=(folder/'results.json').is_file() and (folder/'completion.json').is_file()
        try:
            api.require(parent_available,'Unavailable independently reconstructed parent')
            decoded,checked=job.codec.read_record(folder/'call.json.xz',prior.EXPECTED_PHYSICAL_SHA,parent_prefix)
            c.bound()
            n=record_checks(decoded,d,case,parent,max(cap,len(decoded['rows'])))
        except Exception as error:
            c.bound()
            if complete and marker_ok:raise
            unknown+=cap;item.update(status='unknown',error=repr(error),saved_step_upper_bound=cap)
            issues.append(dict(folder=str(folder),reason='unreadable_or_unbound_raw',detail=repr(error)))
            records.append(item);return None,None,False
        receipt_ok=False
        if complete:
            row=c.sealed(folder/'results.json');c.verify(row['artifacts']);c.bound()
            receipt_ok=(row.get('passed') is True and row.get('summary',{}).get('passed') is True
                and row.get('role')==role and row.get('new_saved_steps')==n and 0<n<=cap
                and row.get('input_checkpoint_sha256')==api.digest(parent)
                and row.get('output_checkpoint_sha256')==api.digest(decoded['result']['checkpoint'])
                and row.get('previous_receipt_sha256')==want_previous
                and row.get('transport_design_sha256')==identities['transport_design_sha256']
                and row.get('physical_design_sha256')==identities['physical_design_sha256']
                and row.get('numerical_policy_contract_sha256')==p['numerical_policy_contract_sha256']
                and row.get('original_binding')==p['original_binding'])
            trace=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in decoded['rows']],dtype=np.float64)
            receipt_ok=bool(receipt_ok and np.array_equal(trace,np.load(folder/'trace.npy',allow_pickle=False)))
        metadata_ok=True
        if (folder/'accounting.json').is_file():
            try:
                metadata=c.read(folder/'accounting.json')
                api.require(metadata['raw_sha256']==c.sha(folder/'call.json.xz') and metadata.get('role')==role
                    and metadata.get('saved_steps_known') is True,'Independent metadata/raw/role association')
                saved_count(n,decoded['result']['checkpoint']['state']['steps']-(0 if parent is None else parent['state']['steps']),metadata['saved_steps'],max(cap,n))
            except Exception as error:
                c.bound();metadata_ok=False;item['metadata_error']=repr(error)
        accepted=bool(marker_ok and complete and receipt_ok and metadata_ok and eligible and 0<n<=cap)
        item.update(status='accepted' if accepted else 'known_unaccepted',saved_steps=n,independently_decoded=True)
        if accepted:item['receipt_sha256']=c.sha(folder/'results.json')
        else:
            unaccepted+=n
            issues.append(dict(folder=str(folder),reason='readable_work_not_admitted',marker_valid=marker_ok,
                sealed_physical_receipt_valid=receipt_ok,metadata_valid=metadata_ok,ancestry_eligible=eligible))
        records.append(item);return decoded,checked,accepted
    qroot=c.RUN/name/'qualification_01';labels=('serial_01','split_a_01','split_b_01')
    production_folders=sorted((c.RUN/name).glob('segment_*'))
    qsealed=(qroot/'results.json').is_file() and (qroot/'completion.json').is_file()
    for index,label in enumerate(labels):
        c.bound();folder=qroot/label;cap=256 if label=='serial_01' else 128
        if not folder.exists():
            if production_folders or qsealed or any((qroot/later).exists() for later in labels[index+1:]):
                unknown+=cap;records.append(dict(folder=str(folder),role='restart_diagnostic',status='unknown',
                    reserved_steps=cap,saved_step_upper_bound=cap,error='Missing dispatched diagnostic ancestry'))
                issues.append(dict(folder=str(folder),reason='missing_diagnostic_ancestry'))
            continue
        parent=parent_prefix=want_previous=None;available=eligible=True
        if label=='split_b_01':
            available='split_a_01' in decoded_diagnostics;eligible='split_a_01' in diagnostics
            if available:parent,parent_prefix=decoded_diagnostics['split_a_01'][0]['result']['checkpoint'],decoded_diagnostics['split_a_01'][1]
            if (qroot/'split_a_01/results.json').is_file():want_previous=c.sha(qroot/'split_a_01/results.json')
        decoded,checked,accepted=reconstruct(folder,'restart_diagnostic',cap,parent,parent_prefix,want_previous,eligible,available)
        if decoded is not None:decoded_diagnostics[label]=(decoded,checked)
        if accepted:diag+=len(decoded['rows']);diagnostics[label]=(decoded,checked)
    qproof=None
    if qsealed:
        c.bound();qproof=c.sealed(qroot/'results.json');c.verify(qproof['artifacts'])
    exact_qualification,qualification=qualification_checks(diagnostics,qproof,identities['transport_design_sha256'])
    if len(diagnostics)==3 and not exact_qualification:issues.append(dict(reason='exact_restart_rows_or_full_checkpoint_failed'))
    if production_folders and not qualification:issues.append(dict(reason='production_without_authenticated_exact_restart'))
    logical_cp=logical_prefix=logical_previous=None;chain_available=True;production_blocked=not qualification
    accepted_entries=[];expected_index=1
    for folder in production_folders:
        c.bound()
        try:index=int(folder.name.removeprefix('segment_'))
        except ValueError:raise RuntimeError('Unrecognized production folder: '+str(folder))
        api.require(folder.name==f'segment_{index:05d}' and index>=expected_index
            and index<=p['maximum_new_production_calls'],'Original bounded production-folder order')
        while expected_index<index:
            c.bound();unknown+=p['step_cap_per_call'];missing=c.RUN/name/f'segment_{expected_index:05d}'
            records.append(dict(folder=str(missing),role='production',status='unknown',reserved_steps=p['step_cap_per_call'],
                saved_step_upper_bound=p['step_cap_per_call'],error='Missing dispatched production ancestry'))
            issues.append(dict(folder=str(missing),reason='missing_production_ancestry'))
            chain_available=False;production_blocked=True;expected_index+=1
        cap=p['step_cap_per_call']
        if chain_available:
            cap=min(cap,p['maximum_saved_steps_including_diagnostics']-physical-diag-unaccepted,
                p['maximum_cumulative_physical_steps_per_case']-(0 if logical_cp is None else logical_cp['state']['steps']))
        api.require(cap>0,'Positive frozen production reservation')
        decoded,checked,accepted=reconstruct(folder,'production',cap,logical_cp,logical_prefix,logical_previous,
            not production_blocked,chain_available)
        if decoded is None:chain_available=False;production_blocked=True
        else:
            logical_cp=decoded['result']['checkpoint'];logical_prefix=checked
            logical_previous=c.sha(folder/'results.json') if (folder/'results.json').is_file() else None
            if accepted:
                n=len(decoded['rows']);physical+=n;cp=logical_cp;prefix=logical_prefix;previous=logical_previous
                accepted_entries.append(dict(segment=index,new_saved_steps=n,results_sha256=previous,stop_s=cp['state']['t']))
            else:production_blocked=True
        expected_index=index+1
    known=physical+diag+unaccepted;api.require(known+unknown<=p['maximum_saved_steps_including_diagnostics'],'Conservative saved-step accounting')
    c.bound()
    result=c.sealed(c.RUN/'results.json') if (c.RUN/'completion.json').exists() else None
    if result:
        api.require(unaccepted==unknown==0 and qualification and physical==result['accepted_physical_steps']
            and diag==result['discarded_diagnostic_steps']==512 and known==result['saved_steps_including_diagnostics']
            and result['case']['entries']==accepted_entries and result['case']['case']==name
            and result['case']['cumulative_calls']==len(accepted_entries)
            and result['case']['cumulative_physical_steps']==physical
            and api.digest(cp)==result['case']['final_checkpoint_sha256']==api.digest(c.read(c.RUN/name/'checkpoint.json'))
            and (None if prefix is None else prefix.reference())==c.read(c.RUN/name/'prefix.json'),'Full accepted checkpoint/history and final ledger')
    comp=None
    if result and result['comparison_sha256']:
        c.bound()
        comp=c.sealed(c.OUT/name/'comparison_01/results.json');c.verify(comp['path_artifacts'])
        api.require(c.sha(c.OUT/name/'comparison_01/results.json')==result['comparison_sha256'] and comp['passed']==result['passed']
            and comp['transport_design_sha256']==identities['transport_design_sha256']
            and comp['physical_design_sha256']==p['physical_design_sha256']
            and comp['reference_evaluation_sha256']==EXPECTED[str(baseline.PREREQUISITE)],'Original authenticated full-path decision')
    scientific=bool(not issues and unaccepted==unknown==0
        and scientific_gate(result,comp,qualification,exit_record,name,p['reference_case'],len(accepted_entries)))
    reason='worker_failure' if result is None else result['reason']
    if len(diagnostics)==3 and not exact_qualification:reason='exact_restart_qualification_failed'
    elif result and result.get('passed') and not scientific:reason='scientific_evidence_not_admitted'
    c.bound();destination=c.OUT/'final_disposition_01';c.commit(destination/'recoverable/checkpoint.json',cp)
    c.bound()
    c.commit(destination/'recoverable/prefix.json',None if prefix is None else prefix.reference())
    c.bound()
    artifacts={str(q):c.sha(q) for q in c.RUN.rglob('*') if q.is_file()}
    artifacts.update({str(q):c.sha(q) for q in (destination/'recoverable').glob('*.json')})
    if comp:artifacts.update({str(q):c.sha(q) for q in (c.OUT/name/'comparison_01').glob('*.json')})
    final=dict(passed=True,accounting_authenticated=True,scientific_full_path_passed=scientific,qualification_passed=qualification,
        exact_restart_rows_and_full_checkpoint=exact_qualification,evidence_failures=issues,
        accepted_physical_steps=physical,discarded_diagnostic_steps=diag,new_known_saved_steps_including_diagnostics=known,
        known_unaccepted_saved_steps=unaccepted,unknown_saved_steps_reservation_upper_bound=unknown,records=records,
        case=None if result is None else result['case'],last_accepted_checkpoint_sha256=api.digest(cp),
        last_accepted_time_s=0. if cp is None else cp['state']['t'],worker_exit=exit_record,
        reason=reason,original_full_path_comparison_sha256=None if comp is None else result['comparison_sha256'],
        artifacts=artifacts,source_files=p['source_files'],utc=c.utc(),claim=p['claim'],successor_cases_started=0,contact_prototype_promoted=False)
    final['retained_output_bytes_before_receipt']=output_bytes()
    api.require(final['retained_output_bytes_before_receipt']<p['maximum_new_output_bytes'],
                'All new run, evaluation, design and controller outputs fit retention cap')
    c.bound();c.commit(destination/'results.json',final)
    c.bound();c.commit(destination/'completion.json',dict(passed=True,results_sha256=c.sha(destination/'results.json')))
    c.bound()
    update_plan(final)
    print('SINGLE_CASE_AUTHENTICATED',final['reason'],known,unknown,flush=True)

def bounded_finalize(exit_record):
    """The same-file read-only finalizer has an exact-identity hard-end watchdog."""
    p=verify();folder=c.RUN.with_name(c.RUN.name+'_controller')
    api.require(c.read(folder/'worker_exit.json')==exit_record,'Frozen controller exit association')
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'finalize']
    cutoff=datetime.fromisoformat(p['end_utc']).timestamp()-p['finalizer_retirement_reserve_seconds']
    api.require(time.time()<cutoff,'Finalizer retirement reserve remains')
    env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):env[key]='1'
    child=birth=None;forced=False
    try:
        with (folder/'finalizer_stdout.log').open('xb') as stdout,(folder/'finalizer_stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            birth=psutil.Process(child.pid).create_time()
            api.require(psutil.Process(child.pid).cmdline()==command,'Exact finalizer launch command')
            c.commit(folder/'finalizer_launch.json',dict(pid=child.pid,created=birth,argv=command,utc=c.utc(),
                design_sha256=c.sha(PLAN),authorization_sha256=c.sha(c.AUTH),worker_exit_sha256=c.sha(folder/'worker_exit.json')))
            while child.poll() is None:
                if time.time()>=cutoff:
                    controller.stop_owned(child,birth,command,folder);forced=True;break
                time.sleep(1)
            code=child.wait(timeout=10)
        identity=controller.inspect(child.pid,birth,command)
        api.require(identity['retired'],'Exact finalizer retired')
        c.bound()
        c.commit(folder/'finalizer_exit.json',dict(pid=child.pid,returncode=code,forced_hard_end_stop=forced,
            retired_exact_identity=True,identity=identity,launch_sha256=c.sha(folder/'finalizer_launch.json'),
            closed_logs={str(q):c.sha(q) for q in folder.glob('finalizer_*.log')},utc=c.utc()))
        api.require(code==0 and not forced,'Bounded finalizer completed; failed/incomplete evidence remains unpromoted')
        api.require(output_bytes()<p['maximum_new_output_bytes'],'Final retained output cap')
    except Exception:
        if child is not None and birth is not None:controller.stop_owned(child,birth,command,folder)
        raise

def final_authentication(exit_record):bounded_finalize(exit_record)
def failed_authentication(exit_record):bounded_finalize(exit_record)

def finalize():
    p=verify();psutil.Process().cpu_affinity([p['logical_cpu']])
    authenticate(c.read(c.RUN.with_name(c.RUN.name+'_controller')/'worker_exit.json'))

def update_plan(final=None):
    """Update only this admitted case's small working-plan block at material gates."""
    p=c.read(PLAN);path=ROOT/'MASTER_PLAN.md';text=path.read_text(encoding='utf-8')
    begin='<!-- STAGE231_SPHERE_BEGIN -->';end='<!-- STAGE231_SPHERE_END -->'
    if final is None:
        paragraph=f"Stage231 is running only the fresh matched sample-0 sphere at original factor0.125 under [design](stage231_designs/{PLAN.parent.name}/design_01.json), from {p['start_utc']} to {p['end_utc']} (numerical cutoff {p['simulation_cutoff_utc']}). Bound:2.5million new saved steps including512 discarded restart diagnostics,250 production calls,10k persegment,one worker/thread,8GiB retained output cap and20GiB disk reserve; original cumulative5million/1500 ceilings and all physical/full-path gates remain unchanged. Original D: fine-reference paths remain mandatory. The preceding fibre's full-path gates passed; the contact prototype remains unpromoted. No difficult-case or population successor dispatch is authorized."
    else:
        time_s=final['last_accepted_time_s']
        paragraph=f"Stage231 numerical worker is retired. [Final accounting](stage231_evaluations/{PLAN.parent.name}/final_disposition_01/results.json): {final['reason']}; full-path accuracy passed={final['scientific_full_path_passed']}. Accepted physical steps={final['accepted_physical_steps']}, discarded diagnostic steps={final['discarded_diagnostic_steps']}, known unaccepted={final['known_unaccepted_saved_steps']}, unknown reserved upper bound={final['unknown_saved_steps_reservation_upper_bound']}; last accepted time={time_s:.12g}s. All preserved new raw/checkpoint/history records were independently reconstructed where readable; unknown work was not promoted. No successor case or contact prototype was dispatched. Controller final retirement/log authentication remains a separate check. Both shapes remain labelled observations at one packing/flow, with no population escape-ranking or irreversible-retention claim."
    block=begin+'\n## Stage231 matched sphere verification — 8 October 2026\n\n'+paragraph+'\n'+end
    if begin in text:
        a=text.index(begin);b=text.index(end,a)+len(end);text=text[:a]+block+text[b:]
    else:
        at=text.index('<!-- STAGE230_TERMINAL_BEGIN -->');text=text[:at]+block+'\n\n'+text[at:]
    path.write_text(text,encoding='utf-8',newline='\n')
    status='active' if final is None else 'numerical worker retired; final disposition saved'
    (ROOT/'CURRENT_PLAN.md').write_text('# Current execution: Stage231 matched sphere '+status+'\n\n[MASTER_PLAN.md](MASTER_PLAN.md) is authoritative.\n\n'+paragraph+'\n',encoding='utf-8',newline='\n')

def launch():
    os.environ['DEM_CASE_PLAN']=str(PLAN)
    verify()
    fn=FunctionType(controller.launch.__code__,dict(controller.launch.__globals__,c=c,worker=sys.modules[__name__]),
                    'launch_single_case',controller.launch.__defaults__,controller.launch.__closure__)
    fn()

if __name__=='__main__':
    {'prepare':prepare,'launch':launch,'run':run,'finalize':finalize}[sys.argv[1]]()
