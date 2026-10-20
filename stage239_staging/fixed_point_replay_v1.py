"""Four fixed-pose failure/control replays; no trajectory entry point.

Expected exhaustion is a diagnostic observation, never physical acceptance.
Only administrative capture is new; every numerical scope/function is original.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import ModuleType, FunctionType
from contextlib import ExitStack
import copy, json, os, shutil, subprocess, sys, time, traceback
import numpy as np
import psutil

ROOT=Path(__file__).resolve().parents[1];SELF=Path(__file__).resolve()
sys.path[:0]=[str(ROOT/'stage238_staging'),str(ROOT/'stage236_staging'),str(ROOT/'stage183_staging')]
import continue_lm_case_v1 as inherited
import screen_lm_residual_v1 as qualified_screen
import audit_fallback_systems_v1 as physical
b=qualified_screen.b;kernel=inherited.kernel;reader=inherited.reader;controller=inherited.controller
api,JOB,RUNTIME,STACK=inherited.api,b.JOB,b.RUNTIME,b.STACK
BASE='fixed_point_cycle_20261009'
PLAN=ROOT/'stage239_designs'/BASE/'design_01.json';AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage239_evaluations'/BASE
KERNEL_SHA=inherited.KERNEL_SHA
OLD_FINAL=inherited.OUT/'final_disposition_01/results.json';OLD_RETIRE=inherited.OUT/'retirement_01/results.json'
FINAL_SHA='aad0d42bd206e1815e383550c90b8a794a7916e8f7efdeb3ab40d80390a7e4ac'
RETIRE_SHA='f9fe12fb12255a64047091b60aa5af8ce850b4f1858ab1a46f4c1d8a4617bb87'
ERROR="RuntimeError('inertial/contact fixed point did not converge')"
SCALAR_NAME='stage201_primary_failure_two_contact_scalar_v3'
FIELDS=('vfree','mobility','jacobian','gaps_m','velocity')
TIMING_FIELDS=frozenset(('certificate_seconds','wall_s'))

def clone(fn,namespace):return FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)
c=ModuleType('_fresh_fixed_point_replay_administration');c.__dict__.update(vars(inherited.c))
c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=OUT;c.DESIGNS=PLAN.parent
for key,fn in vars(inherited.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(inherited.c):setattr(c,key,clone(fn,vars(c)))

def require(value,message):api.require(value,message)
def merge(*maps):return inherited.merge_frozen(*maps)
def plain(value):return b.plain(value)
def scientific(value):
    if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k not in TIMING_FIELDS}
    if isinstance(value,list):return [scientific(v) for v in value]
    return plain(value)
def same(a,b):return c.digest(scientific(a))==c.digest(scientific(b))
def bits(a,b):return np.asarray(a,dtype=np.float64).tobytes()==np.asarray(b,dtype=np.float64).tobytes()
def plain_verify(mapping):
    for path,expected in mapping.items():require(c.sha(path)==expected,'Immutable archived source/input: '+path)

def structural_controls():
    inherited.clone_checks()
    require(JOB is inherited.job and JOB.observer is inherited.ORIGINAL_OBSERVER and RUNTIME is JOB.parent.engine.runtime,
        'Same actual original physical runtime/observer; no alternate model')
    require(c.sha(kernel.__file__)==KERNEL_SHA,'Exact qualified LM callback source')
    require(JOB.observer.backend.stage42.inertial_contact_step.__defaults__[-2:]==(1e-10,80)
        and JOB.observer.backend.stage42.CONTACT_ITERATION_CEILING==25000,'Unchanged outer/inner ceilings')
    return dict(passed=True,original_scoped_functions=True,original_outer_tolerance=1e-10,
        original_outer_iterations=80,original_contact_iteration_ceiling=25000,kernel_sha256=KERNEL_SHA,
        force_calls=0,new_trajectory_steps=0)

def normalized(trial,payload):
    """Rebase only observer indices; preserve every numerical field."""
    t=copy.deepcopy(trial);el,eh=t['early_range'];fl,fh=t['fallback_range']
    require(el==eh==0,'These genuine two-contact fixtures have no early route')
    t['trial_index']=0;t['early_range']=[0,eh-el];t['fallback_range']=[0,fh-fl]
    for item in t['inner_systems']:
        require('system_reference' not in item,'Selected detailed systems must be self-contained logical bodies')
        item['early_range']=[x-el for x in item['early_range']]
        item['fallback_range']=[x-fl for x in item['fallback_range']]
    return dict(contact_trial_trace=dict(schema=payload['contact_trial_trace']['schema'],
        structural_identity=payload['contact_trial_trace']['structural_identity'],trial_inner_counts=[len(t['inner_systems'])],
        trial_route_counts=[[eh-el,fh-fl]],detailed_trials=[t]),
        early_attempts=copy.deepcopy(payload['early_attempts'][el:eh]),fallback_systems=copy.deepcopy(payload['fallback_systems'][fl:fh]),
        repairs=copy.deepcopy(payload['repairs'][fl:fh]),result=dict(stage119_repair_calls=copy.deepcopy(payload['result']['stage119_repair_calls'][fl:fh])))

def fixed_point_audit(fixture,expected_failed):
    """No solve: exact original recurrence plus original independent force gates."""
    trace=fixture['contact_trial_trace'];trials=trace['detailed_trials']
    require(len(trials)==1 and len(trace['trial_inner_counts'])==len(trace['trial_route_counts'])==1,'One fully captured original outer call')
    trial=trials[0];require(trial['trial_index']==0 and len(trial['outer_inputs'])==14,'Complete positional outer operands')
    require(type(trial['accepted']) is bool and trial['accepted'] is not expected_failed,'Expected failed/accepted distinction is explicit')
    if expected_failed:require(trial.get('error')==ERROR and 'velocity' not in trial and 'health' not in trial,'Exact original exhaustion; no fabricated return')
    else:require('velocity' in trial and 'health' in trial and 'error' not in trial,'Original successful control return')
    args=trial['outer_inputs'];qold,bg,body,R,L,mass=[np.asarray(v,float) for v in args[:6]]
    contacts,ell,dt,mu,rhof,viscosity,diameter,sphericity=args[6:]
    require(len(contacts)==2 and len(args)==14 and dt>0 and ell>0,'Exact original two-contact fixed pose')
    J,g,_=JOB.observer.backend.stage41._prepare_geometry(contacts,ell)
    current=qold.copy();scale=max(np.linalg.norm(qold),np.linalg.norm(bg),1e-30)
    ratios=[];audits=[];finite_re=[];early=fallback=0;systems=trial['inner_systems']
    require(len(systems)==trace['trial_inner_counts'][0] and 1<=len(systems)<=80,'Complete bounded original fixed-point iterations')
    for index,item in enumerate(systems):
        require(item['inner_index']==index and item['accepted'] is True and item['dt_s']==dt and item['friction']==mu
            and item['tolerance']==1e-10 and item['maxiter']==25000,'Exact original inner controls/order')
        reynolds=JOB.observer.backend.finite_re.reynolds_number(current[:3]-bg[:3],rhof,viscosity,diameter)
        multiplier=JOB.observer.backend.finite_re.inertial_multiplier(reynolds,sphericity)
        drag=R.copy();drag[:3,:3]*=multiplier;M=np.linalg.inv(mass/dt+drag+L)
        v=M@(mass@qold/dt+drag@bg+body)
        for value,key in ((M,'mobility'),(v,'vfree'),(J,'jacobian'),(g,'gaps_m')):
            require(bits(value,item[key]),'Exact original finite-Re recurrence: '+key)
        require(item['early_range'][0]==early and item['fallback_range'][0]==fallback,'Ordered original captured route ranges')
        ee,ff=item['early_range'][1],item['fallback_range'][1]
        require(early==ee==0 and fallback<=ff<=len(fixture['fallback_systems']) and ff-fallback<=1,'Unchanged two-contact route coverage')
        for fi in range(fallback,ff):
            system=fixture['fallback_systems'][fi];call=fixture['result']['stage119_repair_calls'][fi];repair=fixture['repairs'][fi]
            route=b.ASSOCIATION.evaluate.__globals__
            route['check_stage194_accepted_route'](system,call,repair)
            route['input_route'](system,call,repair);route['solver_route'](system,repair)
            require(system['accepted'] and call['accepted'],'Original successful scalar fallback after recorded three-contact decline')
            for key in FIELDS:require(bits(system[key],item[key]),'Exact fallback-to-inner input/output: '+key)
            require(system['health']==item['health']==call['health'] and call['dt_s']==system['dt_s']
                and call['gaps_m']==system['gaps_m'] and system['health']['solver']==SCALAR_NAME,
                'Every original fallback health/route/certificate consumed exactly once')
        if item['health']['solver']==SCALAR_NAME:require(ff==fallback+1,'Scalar route record cannot be omitted')
        else:require(ff==fallback,'Primary or within-pose route cannot acquire a scalar record')
        audits.append(physical.physical(item));updated=np.asarray(item['velocity'],float)
        ratio=float(np.linalg.norm(updated-current)/scale);ratios.append(ratio)
        require((ratio<=1e-10)==(not expected_failed and index==len(systems)-1),'Unchanged original fixed-point termination criterion')
        finite_re.append(dict(inner_index=index,input_velocity=current.tolist(),reynolds=reynolds,multiplier=multiplier,
            fixed_point_ratio=ratio,returned_velocity=updated.tolist(),solver=item['health']['solver']))
        current=updated;early,fallback=ee,ff
    require(trial['early_range']==[0,early] and trial['fallback_range']==[0,fallback]
        and len(fixture['early_attempts'])==early and len(fixture['fallback_systems'])==len(fixture['repairs'])
            ==len(fixture['result']['stage119_repair_calls'])==fallback
        and trace['trial_route_counts']==[[early,fallback]],'Complete original route/certificate inventory')
    if expected_failed:
        require(len(systems)==80,'Original outer cap exhausted exactly; no increased cap or partial failure')
        require(all(all(bits(systems[i][key],systems[i-2][key]) for key in FIELDS) for i in range(5,80))
            and not bits(systems[-1]['velocity'],systems[-2]['velocity']),'Exact archived two-cycle from inner5 through80')
    else:
        require(bits(current,trial['velocity']) and systems[-1]['health']==trial['health']['contact'],'Exact final inner-to-outer control result')
        # The unchanged full accepted association auditor remains an additional gate.
        accepted=dict(fixture,rows=[dict(velocity_generalized=trial['velocity'],active_contact_ids=[int(z[0]) for z in contacts])],
            sweep_certificates=[dict(dt_s=dt)])
        require(b.ASSOCIATION.evaluate(accepted,dict(state=dict(q=args[0])))['passed'],'Original accepted-control association audit')
    return dict(passed=True,expected_exhaustion_verified=expected_failed,outer_solution_accepted=not expected_failed,
        inner_force_audits=audits,finite_re_recurrence=finite_re,original_caps_unchanged=True,
        numerical_path_promoted=False,new_trajectory_steps=0,new_saved_transport_steps=0)

def archived_fixtures():
    """Authenticated selected raw read; no expired Stage238 bound or solver call."""
    require(c.sha(OLD_FINAL)==FINAL_SHA and c.sha(OLD_RETIRE)==RETIRE_SHA,'Exact closed negative and retirement prerequisites')
    final=c.sealed(OLD_FINAL);retired=c.sealed(OLD_RETIRE);parent=c.read(inherited.PLAN)
    require(retired['passed'] and retired['retirement_and_accounting_authenticated'] and not retired['failed_segment_promoted']
        and retired['known_unaccepted_saved_steps']==1195 and retired['unknown_saved_steps_reservation_upper_bound']==0
        and retired['final_disposition_sha256']==FINAL_SHA and final['accounting_authenticated'],
        'Closed genuine rejection retained, known raw work and exact retirement')
    structural_controls();plain_verify(parent['source_files'])
    base=OLD_FINAL.parent/'recoverable';cp=c.read(base/'checkpoint.json');ref=c.read(base/'prefix.json')
    prefix=JOB.codec.HistoryState(**ref,history_bytes=JOB.codec.packed_history(cp['state']['history']))
    require(api.digest(cp)==retired['last_accepted_full_checkpoint_sha256'] and cp['state']['rejected']==0
        and cp['state']['recovery'] is False,'Last accepted full parent and original pre-failure recovery state')
    folder=inherited.RUN/inherited.NAME/'segment_00036';raw=folder/'call.json.xz'
    selected=[raw,raw.with_suffix('.seal.json'),folder/'accounting.json',folder/'launch.json',OLD_FINAL,OLD_RETIRE,
        OLD_FINAL.parent/'completion.json',OLD_RETIRE.parent/'completion.json',base/'checkpoint.json',base/'prefix.json',
        inherited.PLAN,inherited.AUTH,Path(prefix.path),Path(prefix.path).with_suffix('.seal.json')]
    inputs=merge(parent['physical_inputs'],{str(path):c.sha(path) for path in selected})
    require(inputs[str(raw)]==final['artifacts'][str(raw)]==c.read(folder/'accounting.json')['raw_sha256'],'Exact saved failed raw body')
    plain_verify(inputs);offline=reader.Reader(JOB.codec);offline.prime(prefix);payload,checked=offline.read_record(raw,parent['physical_design_sha256'],prefix)
    require(payload['input_checkpoint_sha256']==api.digest(cp) and len(payload['rows'])==1195 and payload['result']['rejected']==1
        and len(payload['contact_trial_trace']['trial_inner_counts'])==len(payload['normal_gap_operand_policy']['prepare_calls'])==1196,
        'Lossless original failed/accepted trial accounting')
    failed=[t for t in payload['contact_trial_trace']['detailed_trials'] if not t['accepted']]
    require(len(failed)==1 and failed[0]['trial_index']==955 and failed[0]['error']==ERROR,'Exact archived fatal outer trial')
    following=[t for t in payload['contact_trial_trace']['detailed_trials'] if t['trial_index']==956]
    require(len(following)==1 and following[0]['accepted'] and following[0]['outer_inputs'][8]==failed[0]['outer_inputs'][8]/2,
        'Actual immediate accepted half-step control required; never invent one')
    fixtures=[]
    for label,trial,recovery,accepted_index in [('failed',failed[0],False,None),('halved',following[0],True,955)]:
        prepare=payload['normal_gap_operand_policy']['prepare_calls'][trial['trial_index']]
        require(prepare['contacts']==trial['outer_inputs'][6] and prepare['raw_gaps_m']==prepare['effective_gaps_m']
            and all(not z['classification']['changed'] and not z['classification']['sphere'] for z in prepare['metadata']),
            'Original fibre signed gap and live pose operands unchanged')
        require(trial['outer_inputs'][0]==payload['rows'][954]['velocity_generalized'],'Original last accepted input velocity')
        if accepted_index is not None:require(trial['velocity']==payload['rows'][accepted_index]['velocity_generalized'],'Original halved-step return association')
        expected=normalized(trial,payload);audit=fixed_point_audit(expected,label=='failed')
        fixtures.append(dict(fixture_id=label,recovery_mode=recovery,outer_inputs=copy.deepcopy(trial['outer_inputs']),
            outer_operands_sha256=api.digest(trial['outer_inputs']),archived_trial_index=trial['trial_index'],
            original_global_ranges=dict(early=trial['early_range'],fallback=trial['fallback_range']),
            normal_gap_prepare=copy.deepcopy(prepare),expected=expected,saved_evidence_audit=audit))
    require(fixtures[0]['outer_operands_sha256']=='d58785fdde9209e008e608601e5b9fb039df023477ef817cf5b655553741906a'
        and fixtures[1]['outer_operands_sha256']=='ef63c108fec1e26011f8d27cc777f75b58d41a9972ce0752732ef5465f2726f8',
        'Prospectively selected exact original fourteen-operand fixtures')
    return dict(fixtures=fixtures,source_raw_sha256=c.sha(raw),original_spec=payload['spec'],original_binding=payload['effective_binding'],
        numerical_policy_contract_sha256=payload['numerical_policy_contract_sha256'],reader_stats=offline.stats,
        range_rebasing_only=True,no_trajectory_step_or_clock_dwell_replay=True),parent['source_files'],inputs

def bounds(a):
    require(a['maximum_nonadvancing_outer_calls']==a['planned_outer_calls']==4 and a['maximum_trajectory_steps']==a['maximum_saved_transport_steps']==0
        and a['workers']==a['threads']==1 and a['logical_cpu']==14 and a['maximum_output_bytes']==32*1024**2
        and a['minimum_free_disk_bytes']>=20*1024**3 and not a['production_authorized'],'Exact four-call zero-transport diagnostic bounds')
    require(a['call_order']==[['failed','original'],['failed','candidate'],['halved','original'],['halved','candidate']],
        'Exactly the prospectively paired failed and saved half-step variants')
    start,end,cut=[datetime.fromisoformat(a[k]) for k in ('start_utc','end_utc','worker_cutoff_utc')]
    require(all(t.utcoffset() is not None for t in (start,end,cut)) and (end-start).total_seconds()==480
        and cut==end-timedelta(seconds=60),'Fresh eight-minute diagnostic window with capture/retirement reserve')
    return True

def resources():
    a=c.bound();c.environment();bounds(a)
    require(shutil.disk_usage(ROOT).free>a['minimum_free_disk_bytes'],'Declared disk reserve')
    require(sum(x.stat().st_size for root in (OUT,PLAN.parent) for x in root.rglob('*') if x.is_file())
        <a['maximum_output_bytes'],'Bounded retained diagnostic output including fresh design and authority')
    return a

def prepare(start_utc=None):
    c.environment();require(not AUTH.exists() and not PLAN.exists() and not OUT.exists(),'Create-only fresh diagnostic admission')
    inventory,sources,inputs=archived_fixtures();pure=controls(inventory['fixtures'])
    imported={str(Path(module.__file__).resolve()):c.sha(module.__file__) for module in list(sys.modules.values())
        if getattr(module,'__file__',None) and Path(module.__file__).suffix=='.py' and ROOT in Path(module.__file__).resolve().parents
            and Path(module.__file__).is_file()}
    sources=merge(sources,imported,{str(SELF):c.sha(SELF)});plain_verify(sources)
    start=datetime.now(timezone.utc) if start_utc is None else datetime.fromisoformat(start_utc)
    require(start.utcoffset() is not None and abs(start.timestamp()-time.time())<=60,'Fresh admitting parent-selected clock')
    end=start+timedelta(seconds=480)
    a=dict(stage='Stage239 failure-aware original/candidate fixed-pose diagnostic',human_authorization='Fresh human next after authenticated closed Stage238 permits bounded diagnosis; earlier numerical window remains closed.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=60)).isoformat(),
        maximum_nonadvancing_outer_calls=4,planned_outer_calls=4,maximum_trajectory_steps=0,maximum_saved_transport_steps=0,
        workers=1,threads=1,logical_cpu=14,maximum_output_bytes=32*1024**2,minimum_free_disk_bytes=20*1024**3,
        production_authorized=False,source_files=sources,inputs=inputs,physical_changes=[],numerical_cap_changes=[],accuracy_gate_changes=[],
        call_order=[['failed','original'],['failed','candidate'],['halved','original'],['halved','candidate']],
        claim='Zero-transport causation diagnostic. Expected original outer exhaustion is negative evidence, not physical acceptance, production admission or a full numerical path pass.')
    bounds(a);c.commit(AUTH,a);c.commit(OUT/'fixtures.json',inventory)
    p={**a,'authorization_sha256':c.sha(AUTH),'fixtures_sha256':c.sha(OUT/'fixtures.json'),'controls':pure,
        'kernel_sha256':KERNEL_SHA,'scientific_timing_exclusions':sorted(TIMING_FIELDS),
        'range_rebasing':'Only trial_index and early/fallback range offsets rebase to a single fresh outer call; no health/physical field exclusions.'}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        fixtures_sha256=p['fixtures_sha256'],controls=pure,force_calls=0,new_trajectory_steps=0,new_saved_transport_steps=0,utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('FIXED_POINT_REPLAY_PREPARED',c.sha(PLAN),a['end_utc'],flush=True);return p

def verify():
    a=resources();p=c.read(PLAN)
    require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH)
        and all(p[k]==v for k,v in a.items()) and p['fixtures_sha256']==c.sha(OUT/'fixtures.json'),'Frozen fresh diagnostic authority/design/fixtures')
    c.verify(p['source_files']);c.verify(p['inputs']);structural_controls()
    require(c.sealed(OUT/'preparation_01/results.json')['design_sha256']==c.sha(PLAN),'Passing sealed preparation')
    return p

def capture_call(row,mode,p):
    """Original whole scoped outer pipeline; capture even an expected exception."""
    require(mode in ('original','candidate'),'Explicit diagnostic variant')
    JOB.clear_telemetry();RUNTIME._calls.clear();JOB.fast.capture_systems=True
    portfolio=RUNTIME.probe.RECOVERY.portfolio;prior_recovery=portfolio.recovery_mode()
    portfolio.set_recovery_mode(row['recovery_mode']);args=copy.deepcopy(row['outer_inputs']);before=api.digest(args)
    epoch=datetime.fromisoformat(p['worker_cutoff_utc']).timestamp();answer=None;error=None;trace=None;entry_recovery=None
    fixture=None;scope_error=None
    backend_before=JOB.observer.backend.inertial_contact_step;telemetry_before=kernel.telemetry()
    tick=time.perf_counter()
    try:
        with ExitStack() as scope:
            scope.enter_context(STACK.frozen.stack.repair.scope(RUNTIME,True,epoch))
            scope.enter_context(STACK.candidate.scope('compiled_direct'))
            scope.enter_context(b.candidate.previous.scope(RUNTIME,True,epoch))
            scope.enter_context(JOB.prior.p.hot.scope())
            scope.enter_context(JOB.parent.fix.scope())
            scope.enter_context(JOB.deadline.scope(RUNTIME,p['worker_cutoff_utc'],True))
            scope.enter_context(JOB.capture.scope(RUNTIME,True))
            scope.enter_context(JOB.prior.candidate.scope())
            trace=scope.enter_context(JOB.observer.scope(RUNTIME,True))
            if mode=='candidate':scope.enter_context(kernel.scope())
            scope.enter_context(RUNTIME.repair_scope())
            entry_recovery=portfolio.recovery_mode()
            require(entry_recovery is row['recovery_mode'],'Actual original recovery state at the outer dispatch')
            try:answer=JOB.observer.backend.inertial_contact_step(*args)
            except Exception as issue:error=dict(type=type(issue).__name__,message=str(issue),repr=repr(issue))
            fixture=dict(contact_trial_trace=copy.deepcopy(trace),early_attempts=copy.deepcopy(JOB.fast.attempts),
                fallback_systems=copy.deepcopy(JOB.capture.records),repairs=copy.deepcopy(JOB.fast.old.telemetry),
                result=dict(stage119_repair_calls=copy.deepcopy(RUNTIME._calls)))
    except Exception as issue:
        if fixture is None:raise
        scope_error=dict(type=type(issue).__name__,message=str(issue),repr=repr(issue))
    finally:portfolio.set_recovery_mode(prior_recovery)
    return plain(dict(fixture_id=row['fixture_id'],mode=mode,fixture=fixture,error=error,
        returned_answer=None if answer is None else dict(velocity=plain(answer[0]),health=plain(answer[1])),
        inputs_unchanged=api.digest(args)==before==row['outer_operands_sha256'],
        telemetry_before=telemetry_before,telemetry_after=kernel.telemetry(),scoped_seconds=time.perf_counter()-tick,
        scope_restored=JOB.observer.backend.inertial_contact_step is backend_before,scope_error=scope_error,
        prior_recovery_restored=portfolio.recovery_mode()==prior_recovery,
        recovery_mode_at_entry=entry_recovery,new_trajectory_steps=0,new_saved_transport_steps=0))

def returned_control_matches(saved):
    trial=saved['fixture']['contact_trial_trace']['detailed_trials'][0]
    return same(saved['returned_answer'],dict(velocity=trial['velocity'],health=trial['health']))

def validate_call(saved,row):
    require(saved['inputs_unchanged'] and saved['scope_restored'] and saved['prior_recovery_restored']
        and saved.get('scope_error') is None and saved['recovery_mode_at_entry'] is row['recovery_mode'],
        'Immutable operands and original scope/prior lifecycle')
    expected_failed=row['fixture_id']=='failed'
    if expected_failed:require(saved['error']==dict(type='RuntimeError',message='inertial/contact fixed point did not converge',repr=ERROR)
        and saved['returned_answer'] is None,'Expected exact exhaustion, never an invented output')
    else:require(saved['error'] is None and saved['returned_answer'] is not None
        and returned_control_matches(saved),'Saved accepted half-step actual return equals its full captured velocity/health')
    require(same(saved['fixture'],row['expected']),'All archived detailed science including residuals and routes exact')
    require(saved['telemetry_after']['scopes']-saved['telemetry_before']['scopes']==(1 if saved['mode']=='candidate' else 0),'Actual candidate scope entered only in candidate variant')
    if saved['mode']=='candidate':require(saved['telemetry_after']['compiled_callbacks']>saved['telemetry_before']['compiled_callbacks'],'Candidate callback used, not a no-op')
    audit=fixed_point_audit(saved['fixture'],expected_failed)
    return dict(passed=True,archived_full_scientific_record_exact=True,physical_audit=audit,
        expected_negative_reproduced=expected_failed,outer_solution_accepted=not expected_failed,numerical_path_promoted=False)

def controls(fixtures=None):
    """Pure evidence mutations; no solver, integration, authority or output."""
    checks=[structural_controls()]
    a=dict(start_utc='2026-10-09T16:00:00+00:00',end_utc='2026-10-09T16:08:00+00:00',worker_cutoff_utc='2026-10-09T16:07:00+00:00',
        maximum_nonadvancing_outer_calls=4,planned_outer_calls=4,maximum_trajectory_steps=0,maximum_saved_transport_steps=0,
        workers=1,threads=1,logical_cpu=14,maximum_output_bytes=32*1024**2,minimum_free_disk_bytes=20*1024**3,production_authorized=False,
        call_order=[['failed','original'],['failed','candidate'],['halved','original'],['halved','candidate']])
    bounds(a)
    for key,value in [('maximum_nonadvancing_outer_calls',5),('planned_outer_calls',2),('maximum_trajectory_steps',1),
        ('maximum_saved_transport_steps',1),('workers',2),('threads',2),('logical_cpu',15),('maximum_output_bytes',64*1024**2),
        ('production_authorized',True),('end_utc','2026-10-09T16:09:00+00:00'),('call_order',[['failed','original']]*4)]:
        try:bounds({**a,key:value})
        except RuntimeError:checks.append('negative_bound_'+key)
        else:raise AssertionError('Bounds mutation admitted')
    original={'inner':{'residual':1e-10,'velocity':[0.],'health':{'wall_s':1.}},'accepted':False,'error':ERROR}
    changed=copy.deepcopy(original);changed['inner']['health']['wall_s']=2.;require(same(original,changed),'Only declared wall timer may differ')
    for key,value in [('accepted',True),('error','other')]:
        changed=copy.deepcopy(original);changed[key]=value;require(not same(original,changed),'Failed/exception exact comparison');checks.append('negative_'+key)
    changed=copy.deepcopy(original);changed['inner']['residual']=1e-9;require(not same(original,changed),'Residual is never excluded');checks.append('negative_residual')
    changed=copy.deepcopy(original);changed['inner']['velocity'][0]=np.nextafter(0.,1.);require(not same(original,changed),'Operand/output byte change remains scientific');checks.append('negative_output_bits')
    if fixtures is not None:
        require([x['fixture_id'] for x in fixtures]==['failed','halved'],'Both actual archived trials are mandatory')
        for row in fixtures:
            require(api.digest(row['outer_inputs'])==row['outer_operands_sha256'],'Immutable fourteen-operand archive')
            fixed_point_audit(row['expected'],row['fixture_id']=='failed')
            for change in ('missing_inner','accepted_vs_failed','inner_cap','exception','inner_force','operand'):
                bad=copy.deepcopy(row['expected']);t=bad['contact_trial_trace']['detailed_trials'][0]
                if change=='missing_inner':t['inner_systems'].pop()
                elif change=='accepted_vs_failed':t['accepted']=not t['accepted']
                elif change=='inner_cap':t['inner_systems'][0]['maxiter']+=1
                elif change=='exception':t['error']='RuntimeError(\'other\')'
                elif change=='inner_force':t['inner_systems'][0]['health']['reactions'][0]=-1.
                else:t['inner_systems'][0]['vfree'][0]=np.nextafter(t['inner_systems'][0]['vfree'][0],np.inf)
                try:fixed_point_audit(bad,row['fixture_id']=='failed')
                except (RuntimeError,KeyError,ValueError):checks.append('negative_'+row['fixture_id']+'_'+change)
                else:raise AssertionError('Evidence mutation admitted: '+change)
            bad_force=copy.deepcopy(row['expected']['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0])
            bad_force['health']['reactions'][0]=-1.
            try:physical.physical(bad_force)
            except RuntimeError:checks.append('independent_force_negative_'+row['fixture_id'])
            else:raise AssertionError('Original independent force gate accepted corrupted force')
        control=fixtures[1]['expected'];trial=control['contact_trial_trace']['detailed_trials'][0]
        saved=dict(fixture=control,returned_answer=dict(velocity=trial['velocity'],health=trial['health']))
        require(returned_control_matches(saved),'Exact accepted archived control return')
        bad=copy.deepcopy(saved);bad['returned_answer']=copy.deepcopy(saved['returned_answer'])
        bad['returned_answer']['velocity'][0]=np.nextafter(trial['velocity'][0],np.inf)
        require(not returned_control_matches(bad),'A wrong returned answer cannot hide behind correct capture');checks.append('negative_actual_return')
    return dict(passed=True,checks=checks,force_calls=0,root_calls=0,outer_calls=0,new_trajectory_steps=0,new_saved_transport_steps=0,
        scope_functions_unchanged=True,negative_outcome_does_not_admit_production=True)

def run():
    p=verify();process=psutil.Process();process.cpu_affinity([14])
    require(not (OUT/'launch.json').exists(),'No duplicate diagnostic worker')
    c.commit(OUT/'launch.json',dict(pid=process.pid,created=process.create_time(),command=process.cmdline(),utc=c.utc(),design_sha256=c.sha(PLAN),
        authorization_sha256=c.sha(AUTH),affinity=process.cpu_affinity(),threads={name:os.environ[name] for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')},
        maximum_outer_calls=4,new_trajectory_steps=0,new_saved_transport_steps=0))
    attempted=completed=0;active=None;reports=[];pairs={}
    try:
        inventory=c.read(OUT/'fixtures.json');rows={x['fixture_id']:x for x in inventory['fixtures']}
        JOB.parent.b.old.parent.configure();STACK.candidate.warm();kernel.warm();kernel.reset()
        for index,(label,mode) in enumerate(p['call_order'],1):
            resources();require(time.time()<datetime.fromisoformat(p['worker_cutoff_utc']).timestamp()-30,'Bounded guard before each original outer call')
            require(attempted<4,'No silent retry or fifth call');folder=OUT/f'call_{index:02d}_{label}_{mode}';folder.mkdir()
            row=rows[label];active=dict(call=index,fixture_id=label,mode=mode,maximum_outer_calls=1,outer_operands_sha256=row['outer_operands_sha256'])
            c.commit(folder/'reservation.json',{**active,'utc':c.utc(),'new_trajectory_steps':0,'new_saved_transport_steps':0});attempted+=1
            saved=capture_call(row,mode,p)
            # Preserve the complete returned/failed trace before any validation.
            c.commit(folder/'captured_call.json',saved);completed+=1;active=None
            validation=validate_call(saved,row)
            if label in pairs:require(same(saved['fixture'],pairs[label]['fixture']) and saved['error']==pairs[label]['error']
                and same(saved['returned_answer'],pairs[label]['returned_answer']),'Strict current original/candidate pair including residuals')
            else:pairs[label]=saved
            c.commit(folder/'results.json',dict(validation,call=index,fixture_id=label,mode=mode,captured_call_sha256=c.sha(folder/'captured_call.json')))
            c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
            reports.append(dict(call=index,fixture_id=label,mode=mode,path=str(folder/'results.json'),sha256=c.sha(folder/'results.json'),
                expected_failure=label=='failed',outer_solution_accepted=label=='halved'))
            print('FIXED_POINT_DIAGNOSTIC_CALL_VERIFIED',index,label,mode,flush=True)
        resources();require(attempted==completed==4,'Exactly four prospectively planned outer calls')
        artifacts={str(q):c.sha(q) for q in OUT.rglob('*') if q.is_file()}
        result=dict(passed=True,diagnostic_pairs_exact=True,archived_original_failure_reproduced=True,archived_halved_control_reproduced=True,
            attempted_outer_calls=attempted,fully_captured_outer_calls=completed,known_failed_outer_calls=2,accepted_control_outer_calls=2,unknown_outer_calls=0,
            reports=reports,artifacts=artifacts,production_authorized=False,numerical_path_promoted=False,scientific_transport_passed=False,
            new_trajectory_steps=0,new_saved_transport_steps=0,claim=p['claim'],design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),utc=c.utc())
        c.commit(OUT/'results.json',result);c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as error:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),attempted_outer_calls=attempted,
            fully_captured_outer_calls=completed,unresolved_call_reservation=active,unknown_outer_calls=1 if active else 0,
            reports=reports,all_original_negatives_preserved=True,dependent_dispatch_stopped=True,production_authorized=False,
            numerical_path_promoted=False,new_trajectory_steps=0,new_saved_transport_steps=0,utc=c.utc()))
        raise

# Reuse the reviewed exact-identity bounded controller, with only this fresh
# administrative namespace. It stops this worker at the60second reserve.
launch=clone(qualified_screen.launch,globals())
if __name__=='__main__':{'prepare':prepare,'run':run,'launch':launch,'controls':lambda:print(controls())}[sys.argv[1]]()
