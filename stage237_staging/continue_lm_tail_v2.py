"""Same-window comparator repair; frozen v1 negative remains unchanged.

Every v1 numerical, restart, physical, deadline and accounting code object is
reused in a private namespace. Only result.runtime_seconds, proved to be a wall
timer by the original source, joins the existing three timing exclusions. The
new attempt pays for another1,024 diagnostics inside the original31,024 budget.
"""
from pathlib import Path
from types import FunctionType
import ast, copy, os, sys

ROOT=Path(__file__).resolve().parents[1];SELF=Path(__file__).resolve()
PLAN=Path(os.environ.get('DEM_CASE_PLAN',str(ROOT/'stage237_designs/lm_tail_20261009/design_02.json'))).resolve()
sys.path.insert(0,str(SELF.parent))
saved=os.environ.pop('DEM_CASE_PLAN',None)
import continue_lm_tail_v1 as frozen
if saved is not None:os.environ['DEM_CASE_PLAN']=saved
api,job,baseline,kernel,reader,controller=frozen.api,frozen.job,frozen.baseline,frozen.kernel,frozen.reader,frozen.controller
AUTH=frozen.AUTH
RUN=ROOT/'stage237_runs'/PLAN.parent.name/'run_02'
OUT=ROOT/'stage237_evaluations'/PLAN.parent.name/'repair_02'
PRIOR_RETIREMENT=frozen.OUT/'retirement_01/results.json'
EXPECTED_V1='eeb9d0ff859c42e28be4411140ad6734c246eaa68dfb2216dc9da32e29739bb0'
EXPECTED_RETIREMENT='ed22c3538224bd0b99cb918a5d1ef0c1fd5935dbc35c0d41f93d1a3d1bb4eb68'
TIMER_SOURCE=ROOT/'stage119_staging/checkpoint_core_v3.py'
ns={**vars(frozen),'__name__':__name__,'__file__':str(SELF),'SELF':SELF,'PLAN':PLAN,'AUTH':AUTH,'RUN':RUN,'OUT':OUT,'FINAL_PROGRESS':None}
for key,fn in vars(frozen).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(frozen):ns[key]=frozen.clone(fn,ns)
c=ns['context'](RUN);ns['c']=c
ns['PRIVATE']=ns['transactions'](RUN,True)
ns['DIAGNOSTIC']={mode:ns['transactions'](RUN/('diagnostic_'+mode),mode=='candidate') for mode in ('original','candidate')}
# Keep the original recursive field list. The additional exclusion is a path.
EXACT_TIMING_PATHS=[['result','runtime_seconds']]
original_commit=c.commit

def commit(path,value):
    path=Path(path)
    if path==RUN/'qualification_pair_01/results.json' or path==OUT/'final_disposition_01/results.json':
        p=c.read(PLAN);value={**value,'excluded_timing_paths':EXACT_TIMING_PATHS,
            'wall_timer_proof':p['wall_timer_proof'],'comparator_repair_source_sha256':c.sha(SELF),
            'prior_attempt_saved_steps':1024,'shared_saved_step_ceiling':31024}
    return original_commit(path,value)

c.commit=commit

def scientific_record(value,path=()):
    if isinstance(value,dict):
        return {k:scientific_record(v,path+(k,)) for k,v in value.items()
            if k not in frozen.TIMING_FIELDS and path+(k,)!=('result','runtime_seconds')}
    if isinstance(value,list):return [scientific_record(v,path+(i,)) for i,v in enumerate(value)]
    if isinstance(value,tuple):return tuple(scientific_record(v,path+(i,)) for i,v in enumerate(value))
    return value

ns['scientific_record']=scientific_record
pair_equal=ns['pair_equal']

def output_bytes():
    roots=(frozen.RUN,RUN,frozen.OUT,PLAN.parent,
        frozen.RUN.with_name(frozen.RUN.name+'_controller'),RUN.with_name(RUN.name+'_controller'))
    return sum(q.stat().st_size for q in {q.resolve() for root in roots for q in root.rglob('*') if q.is_file()})

ns['output_bytes']=output_bytes

def wall_timer_proof():
    tree=ast.parse(TIMER_SOURCE.read_text(encoding='utf-8'))
    integrate=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='integrate')
    started=[n for n in integrate.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='started' for t in n.targets)]
    finish=next(x for x in integrate.body if isinstance(x,ast.FunctionDef) and x.name=='finish')
    returns=[x for x in finish.body if isinstance(x,ast.Return) and isinstance(x.value,ast.Dict)]
    api.require(len(started)==len(returns)==1 and ast.unparse(started[0].value)=='time.perf_counter()','Original wall-timer start expression')
    fields=dict((k.value,v) for k,v in zip(returns[0].value.keys,returns[0].value.values) if isinstance(k,ast.Constant))
    api.require(ast.unparse(fields['runtime_seconds'])=='time.perf_counter() - started'
        and ast.unparse(fields['time_s'])=='t','Wall time is distinct from physical time_s')
    return dict(passed=True,source=str(TIMER_SOURCE),source_sha256=c.sha(TIMER_SOURCE),
        start_line=started[0].lineno,finish_wall_timer_line=fields['runtime_seconds'].lineno,
        exact_additional_exclusion_path=['result','runtime_seconds'],physical_clock_and_FULL_checkpoint_unchanged=True)

def repair_checks(p):
    original=c.read(AUTH);frozen.budget_checks(original);ns['budget_checks'](p)
    api.require(p['prior_attempt_saved_steps']==1024 and p['prior_attempt_physical_steps']==0
        and p['prior_attempt_production_calls']==0 and p['maximum_saved_steps_including_diagnostics']==30000
        and p['maximum_new_physical_steps']==28976 and p['maximum_new_production_calls']==20
        and p['qualification_steps_per_case']==1024
        and p['prior_attempt_saved_steps']+p['maximum_saved_steps_including_diagnostics']==original['maximum_saved_steps_including_diagnostics']==31024,
        'Two attempts share original31,024 cap; repeat diagnostics reduce physical allowance')
    for key in ('start_utc','end_utc','simulation_cutoff_utc','maximum_new_production_calls','maximum_cumulative_physical_steps_per_case',
        'maximum_cumulative_calls_per_case','step_cap_per_call','workers','threads','logical_cpu','maximum_unverified_records',
        'minimum_free_disk_bytes','maximum_new_output_bytes','finalizer_retirement_reserve_seconds'):
        api.require(p[key]==original[key],'Original absolute clock/resource retained: '+key)
    return True

def prior_failure():
    api.require(c.sha(frozen.SELF)==EXPECTED_V1 and c.sha(PRIOR_RETIREMENT)==EXPECTED_RETIREMENT,'Frozen failed source and exact sealed retirement')
    r=c.sealed(PRIOR_RETIREMENT);ns['retirement_checks'](r)
    api.require(r['accounting_authenticated'] and r['initial_attempt_passed'] is False
        and r['accepted_physical_steps']==0 and r['discarded_diagnostic_steps']==1024
        and r['known_unaccepted_saved_steps']==r['unknown_saved_steps_reservation_upper_bound']==0
        and r['zero_production_dispatch'] and r['accepted_rows_and_full_checkpoint_exact']
        and r['original_and_candidate_independent_restart_proofs_passed'] and r['all_other_scientific_fields_exact']
        and r['only_complete_record_difference']=='result.runtime_seconds' and r['wall_timer_ast_proven']
        and r['wall_timer_source_sha256']==c.sha(TIMER_SOURCE) and r['production_authorized'] is False,
        'Comparator-only negative, both restart proofs, zero production and complete failed-attempt ledger')
    closure=c.sealed(frozen.OUT/'final_disposition_01/results.json');c.verify(closure['artifacts'])
    api.require(closure['accounting_authenticated'] and closure['accepted_physical_steps']==0
        and closure['discarded_diagnostic_steps']==1024 and closure['known_unaccepted_saved_steps']==closure['unknown_saved_steps_reservation_upper_bound']==0
        and not closure['qualification_passed'] and not closure['scientific_full_path_passed']
        and r['final_disposition_sha256']==c.sha(frozen.OUT/'final_disposition_01/results.json'),
        'Frozen negative closure is preserved, not promoted')
    api.require(not any((frozen.RUN/frozen.NAME).glob('segment_*')),'Original attempt has no production dispatch')
    return r,closure

def verify():
    a=c.bound();c.environment();p=c.read(PLAN);repair_checks(p);ns['clone_checks']()
    api.require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH),'Frozen same-authority repair design')
    changes={'source_files','inputs','maximum_new_physical_steps','maximum_saved_steps_including_diagnostics'}
    for key,value in a.items():
        if key not in changes:api.require(p[key]==value,'Original authority retained: '+key)
    original=c.read(frozen.PLAN)
    api.require(all(p['source_files'].get(path)==expected for path,expected in original['source_files'].items())
        and all(p['inputs'].get(path)==expected for path,expected in original['inputs'].items()),'No original frozen source/input binding replaced')
    c.verify(p['source_files']);c.verify(p['inputs']);c.verify(p['inherited']['inputs'])
    api.require(p['source_files'][str(SELF)]==c.sha(SELF) and p['source_files'][str(frozen.SELF)]==EXPECTED_V1
        and p['source_files'][str(Path(kernel.__file__).resolve())]==c.sha(kernel.__file__) and p['wall_timer_proof']==wall_timer_proof(),
        'Explicit separately bound administrative repair and exact original wall-timer proof')
    api.require(p['scientific_timing_exclusions']==dict(recursive_fields=list(frozen.TIMING_FIELDS),exact_paths=EXACT_TIMING_PATHS),
        'Exactly three original recursive cost fields plus one explicitly bounded result path')
    prior_failure();d,case=ns['original_case']();ns['seed_state'](p)
    api.require(p['inherited']==original['inherited'] and p['physical_inputs']==original['physical_inputs']
        and p['original_binding']==job.binding(d,case)==original['original_binding']
        and p['checkpoint_contract']==original['checkpoint_contract'] and p['matched_physics']==original['matched_physics']
        and p['physical_design_sha256']==c.sha(job.DESIGN) and p['numerical_policy_contract_sha256']==c.sha(job.WORK),
        'Same original production seed, full history and physical/numerical controls')
    gate=p['candidate_gate'];api.require(c.sha(gate['path'])==gate['sha256'],'Same positive frozen candidate screen')
    screen=c.sealed(Path(gate['path']));ns['gate_checks'](screen);c.verify(screen['artifacts'])
    screen_design=p['candidate_screen_design'];api.require(c.sha(screen_design['path'])==screen_design['sha256']==screen['design_sha256'],
        'Same measured candidate screen design')
    api.require(c.read(screen_design['path'])['source_files'][str(Path(kernel.__file__).resolve())]==c.sha(kernel.__file__),
        'Only originally measured candidate is permitted')
    retirement=p['candidate_retirement'];api.require(c.sha(retirement['path'])==retirement['sha256'],'Same candidate screen retirement')
    ns['retirement_checks'](c.sealed(Path(retirement['path'])))
    prep=c.sealed(OUT/'preparation_02/results.json')
    api.require(prep['passed'] and prep['design_sha256']==c.sha(PLAN) and prep['authorization_sha256']==c.sha(AUTH),
        'Passing same-window separately sealed repair preparation')
    return p

ns['verify']=verify

def controls():
    result=ns['controls']();checks=result['checks']
    a={'rows':[1,2],'result':{'checkpoint':{'state':{'t':3.,'history':[[4]]}},'time_s':3.,'runtime_seconds':1.},
        'another':{'runtime_seconds':5.},'wall_s':1.}
    b=copy.deepcopy(a);b['result']['runtime_seconds']=9.;b['wall_s']=8.
    api.require(pair_equal(a,b),'Exact result-path wall timer is excluded')
    checks.append('exact_result_runtime_seconds_wall_timer_only_excluded')
    b['another']['runtime_seconds']=6.;api.require(not pair_equal(a,b),'Same field name outside result path remains scientific')
    checks.append('runtime_seconds_outside_exact_result_path_retained')
    b=copy.deepcopy(a);b['result']['checkpoint']['state']['t']=3.000000001
    api.require(not pair_equal(a,b),'FULL checkpoint physical time remains exact')
    checks.append('physical_checkpoint_clock_never_excluded')
    proof=wall_timer_proof();checks.append('original_perf_counter_AST_proves_wall_timer')
    result['wall_timer_proof']=proof;result['excluded_timing_fields']=list(ns['TIMING_FIELDS']);result['excluded_timing_paths']=EXACT_TIMING_PATHS
    result['reused_numerical_and_auditor_code_objects']=list(frozen.old.NAMES)
    return result

def prepare_repair():
    c.environment();c.bound();api.require(not PLAN.exists() and not RUN.exists() and not OUT.exists(),'Separate create-only repair attempt')
    original=c.read(frozen.PLAN);a=c.read(AUTH)
    api.require(original['binding']==c.digest({k:v for k,v in original.items() if k!='binding'})
        and original['authorization_sha256']==c.sha(AUTH),'Frozen original Stage237 authority and design')
    retirement,closure=prior_failure();proof=wall_timer_proof();pure=controls()
    source_files=ns['merge_frozen'](original['source_files'],{str(SELF):c.sha(SELF)})
    inputs=ns['merge_frozen'](original['inputs'],retirement['artifacts'],retirement['closed_logs'],closure['artifacts'])
    for path in (frozen.PLAN,AUTH,PRIOR_RETIREMENT,PRIOR_RETIREMENT.parent/'completion.json',frozen.OUT/'final_disposition_01/results.json',
        frozen.OUT/'final_disposition_01/completion.json',frozen.RUN/'failure.json'):
        inputs=ns['merge_frozen'](inputs,{str(path):c.sha(path)})
    p={**original,'maximum_saved_steps_including_diagnostics':30000,'maximum_new_physical_steps':28976,
        'source_files':source_files,'inputs':inputs,'prior_attempt_saved_steps':1024,'prior_attempt_physical_steps':0,
        'prior_attempt_production_calls':0,'wall_timer_proof':proof,'controls':pure,
        'scientific_timing_exclusions':dict(recursive_fields=list(frozen.TIMING_FIELDS),exact_paths=EXACT_TIMING_PATHS),
        'prior_attempt_retirement_sha256':EXPECTED_RETIREMENT,'prior_attempt_retirement_file':str(PRIOR_RETIREMENT),
        'repair_stage':'Stage237 same-window exact result-wall-timer comparator repair',
        'implementation_changes':original['implementation_changes']+['Exclude only original result.runtime_seconds wall timer in the complete-science comparator; failed v1 remains failed.'],
        'production_admission':'Repeat both exact512-step restart qualifications and complete original/candidate256 comparison under the same clocks and shared31,024 saved-step budget. Restore original Stage233 production seed; discard all diagnostics.',
        'claim':original['claim'],'repair_authorization':'Same human request and original absolute authorization; no window/cap extension. Prior1,024 saved diagnostics charged before new30,000 allowance.',
        'repair_master_plan_sha256_at_admission':c.sha(ROOT/'MASTER_PLAN.md')}
    p.pop('binding',None);repair_checks(p);c.verify(source_files);c.verify(inputs)
    p['binding']=c.digest(p);c.commit(PLAN,p)
    receipt=dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),original_failed_source_sha256=EXPECTED_V1,
        prior_retirement_sha256=EXPECTED_RETIREMENT,controls=pure,prior_saved_steps=1024,new_saved_step_allowance=30000,
        new_physical_step_allowance=28976,new_discarded_diagnostics=1024,original_absolute_clock_and_shared_caps_unchanged=True,
        no_new_authorization_window=True,numerical_calls=0,new_trajectory_steps=0,utc=c.utc())
    c.commit(OUT/'preparation_02/results.json',receipt);c.commit(OUT/'preparation_02/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_02/results.json')))
    verify();print('LM_TAIL_REPAIR_PREPARED',c.sha(PLAN),p['end_utc'],flush=True);return p

original_authenticate=ns['authenticate']
def authenticate(exit_record):
    p=verify();path=RUN/'qualification_pair_01/results.json'
    if (path.parent/'completion.json').exists():
        proof=c.sealed(path)
        api.require(proof['excluded_timing_paths']==EXACT_TIMING_PATHS and proof['excluded_timing_fields']==list(frozen.TIMING_FIELDS)
            and proof['wall_timer_proof']==p['wall_timer_proof'] and proof['comparator_repair_source_sha256']==c.sha(SELF),
            'Retired-worker accountant independently requires the exact path-specific comparator admission')
    original_authenticate(exit_record)
    final_path=OUT/'final_disposition_01/results.json'
    if final_path.exists():
        final=c.sealed(final_path)
        api.require(1024+final['accepted_physical_steps']+final['discarded_diagnostic_steps']+final['known_unaccepted_saved_steps']
            +final['unknown_saved_steps_reservation_upper_bound']<=31024,'Both attempts remain inside original shared saved-step ceiling')

ns['authenticate']=authenticate
run=ns['run'];launch=ns['launch'];finalize=ns['finalize'];final_authentication=ns['final_authentication'];failed_authentication=ns['failed_authentication']
bounded_finalize=ns['bounded_finalize']

if __name__=='__main__':{'prepare':prepare_repair,'launch':launch,'run':run,'finalize':finalize,'controls':lambda:print(controls())}[sys.argv[1]]()
