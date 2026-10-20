"""Fresh four-call diagnostic consuming the reviewed Stage239 context adapter.

Stage239's failed protocol remains incomplete. This is a separate admission;
only this fresh four-call protocol can pass. No transport is implemented.
"""
from pathlib import Path
from types import ModuleType, FunctionType
from datetime import datetime, timezone, timedelta
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage239_staging'))
import fixed_point_replay_v1 as frozen
import short_seed_scope_repair_v2 as adapter

# Reviewed original numerical code and administration, with fresh paths only.
for _name,_value in vars(frozen).items():
    if not _name.startswith('__'):globals()[_name]=_value
SELF=Path(__file__).resolve()
BASE='original_context_20261012'
PLAN=ROOT/'stage240_designs'/BASE/'design_01.json'
AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage240_evaluations'/BASE
c=ModuleType('_stage240_administration');c.__dict__.update(vars(frozen.c))
c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=OUT;c.DESIGNS=PLAN.parent
for _name,_value in vars(frozen.c).items():
    if isinstance(_value,FunctionType) and _value.__globals__ is vars(frozen.c):
        setattr(c,_name,frozen.clone(_value,vars(c)))
for _name,_value in vars(frozen).items():
    if isinstance(_value,FunctionType) and _value.__globals__ is vars(frozen):
        globals()[_name]=frozen.clone(_value,globals())

ADAPTER_SHA='fba00e6c3f60a411cefe399ca42f7699258431b350e58e2ffa49b5867a071cd2'
NEGATIVE=ROOT/'stage239_evaluations/fixed_point_cycle_20261009/final_disposition_01/results.json'
ADDENDUM=NEGATIVE.parents[1]/'closure_addendum_01/results.json'

def controls(fixtures=None):
    original=frozen.controls(fixtures)
    repair=adapter.controls()
    require(original['passed'] and repair['passed'],'Original evidence and exact context pure controls')
    require(c.sha(adapter.__file__)==ADAPTER_SHA,'Reviewed adapter bytes')
    require(run.__code__ is frozen.run.__code__ and launch.__code__ is frozen.launch.__code__,
        'Original bounded four-call runner/controller bytecode, no transport entry point')
    return dict(passed=True,original=original,context_repair=repair,
        outer_calls=0,force_calls=0,new_trajectory_steps=0,new_saved_transport_steps=0)

def prepare():
    c.environment()
    require(not AUTH.exists() and not PLAN.exists() and not OUT.exists(),'Create-only fresh diagnostic')
    require(c.sha(NEGATIVE)=='57f99ce58dedb1c6b2afc422c6809e0bfaf423bf14257402a4aa7b16ef93c3df'
        and c.sha(ADDENDUM)=='2a3ad23f8a0b142193dce16ee1b7018e28c30d51ac061e6c2f27037f32fffa77',
        'Prior failed attempt/closure retained unchanged')
    negative=c.sealed(NEGATIVE);addendum=c.sealed(ADDENDUM)
    require(negative['attempted_outer_calls']==1 and negative['unknown_outer_calls']==0
        and not negative['causation_pair_passed'] and not addendum['future_repair']['qualified'],
        'No promotion or substitution of prior wrong-context call')
    inventory,sources,inputs=archived_fixtures()
    pure=controls(inventory['fixtures'])
    imported={str(Path(m.__file__).resolve()):c.sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py'
        and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources=merge(sources,imported,{str(SELF):c.sha(SELF)})
    inputs=merge(inputs,{str(p):c.sha(p) for p in (NEGATIVE,ADDENDUM,
        NEGATIVE.with_name('completion.json'),ADDENDUM.with_name('completion.json'))})
    plain_verify(sources);plain_verify(inputs)
    start=datetime.now(timezone.utc);end=start+timedelta(seconds=480)
    a=dict(stage='Stage240 complete-original-context causation diagnostic',
        human_authorization='Human next on 12 October 2026 authorizes the next bounded diagnostic. Closed earlier windows stay closed.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=60)).isoformat(),
        maximum_nonadvancing_outer_calls=4,planned_outer_calls=4,maximum_trajectory_steps=0,maximum_saved_transport_steps=0,
        workers=1,threads=1,logical_cpu=14,maximum_output_bytes=32*1024**2,minimum_free_disk_bytes=20*1024**3,
        production_authorized=False,short_seed_scope_repair_admitted=True,source_files=sources,inputs=inputs,
        physical_changes=[],numerical_cap_changes=[],accuracy_gate_changes=[],
        call_order=[['failed','original'],['failed','candidate'],['halved','original'],['halved','candidate']],
        stage239_failed_protocol_remains_incomplete=True,
        startup_accounting=addendum['startup_accounting'],
        claim='Fresh original/candidate attribution at two archived fixed poses, zero transport. Expected exhaustion is a numerical negative, never transport acceptance. No performance claim from four calls.')
    bounds(a);c.commit(AUTH,a);c.commit(OUT/'fixtures.json',inventory)
    p={**a,'authorization_sha256':c.sha(AUTH),'fixtures_sha256':c.sha(OUT/'fixtures.json'),'controls':pure,
        'kernel_sha256':KERNEL_SHA,'context_adapter_sha256':ADAPTER_SHA,
        'scientific_timing_exclusions':sorted(TIMING_FIELDS),
        'range_rebasing':'Only observer indices rebase; no physical or health field exclusion.',
        'context':'Original Stage89 then Stage81 live bindings; Stage104 three-contact rescue unreachable at both two-contact fixtures.'}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,controls=pure,design_sha256=c.sha(PLAN),
        fixtures_sha256=p['fixtures_sha256'],outer_calls=0,new_trajectory_steps=0,utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('STAGE240_PREPARED',c.sha(PLAN),end.isoformat(),flush=True)

def capture_call(row,mode,p):
    require(p['short_seed_scope_repair_admitted'] is True and p['context_adapter_sha256']==ADAPTER_SHA,
        'Fresh context admission and immutable source')
    # The component's false full_four_call_protocol_qualified flag refers to its
    # uncompleted Stage239 protocol; the fresh runner separately requires all4.
    return adapter.capture_call(row,mode,p)

def validate_call(saved,row):
    return adapter.validate_call(saved,row)

def retire(controller_returncode):
    p=verify();folder=OUT/'controller_01';identities=[]
    for path in (folder/'launch.json',folder/'worker_launch.json'):
        saved=c.read(path);inspection=controller.inspect(saved['pid'],saved['created'],saved['command'])
        require(inspection['retired'],'Exact task-owned identity must be retired')
        identities.append(dict(path=str(path),sha256=c.sha(path),inspection=inspection))
    exit_record=c.read(folder/'worker_exit.json');c.verify(exit_record['closed_logs'])
    success=(OUT/'completion.json').exists()
    result=c.sealed(OUT/'results.json') if success else c.read(OUT/'failure.json')
    attempted=result['attempted_outer_calls'];captured=result['fully_captured_outer_calls']
    qualified=len(result['reports']);unknown=result.get('unknown_outer_calls',0)
    if success:
        require(controller_returncode==exit_record['returncode']==0 and not exit_record['forced_cutoff_stop']
            and attempted==captured==qualified==4 and unknown==0 and result['diagnostic_pairs_exact'],
            'Complete fresh four-call gate and unforced retirement')
    artifacts={str(q):c.sha(q) for q in OUT.rglob('*') if q.is_file() and 'final_disposition_01' not in q.parts}
    receipt=OUT/'final_disposition_01/results.json'
    r=dict(passed=True,accounting_authenticated=True,scientific_diagnostic_passed=success,
        fresh_four_call_protocol_completed=success,stage239_failed_protocol_remains_incomplete=True,
        attempted_outer_calls=attempted,fully_captured_outer_calls=captured,qualified_outer_calls=qualified,
        known_unaccepted_outer_calls=captured-qualified,unknown_outer_calls=unknown,
        expected_failed_outer_calls=2 if success else None,accepted_half_step_controls=2 if success else None,
        original_map_exhaustion_reproduced=success,optimized_map_scientifically_exact=success,
        prior_stage238_failure_resolved=False,transport_continuation_authorized=False,
        new_trajectory_steps=0,new_saved_transport_steps=0,identities=identities,
        controller_returncode_observed=controller_returncode,worker_exit=exit_record,
        design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),source_count=len(p['source_files']),input_count=len(p['inputs']),
        startup_accounting=p['startup_accounting'],artifacts=artifacts,production_authorized=False,
        claim=p['claim'],utc=c.utc())
    c.commit(receipt,r);c.commit(receipt.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(receipt)))
    print('STAGE240_RETIRED',c.sha(receipt),'scientific_diagnostic_passed=',success,flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='retire':retire(int(sys.argv[2]))
    elif action=='controls':print(controls())
    else:{'prepare':prepare,'launch':launch,'run':run}[action]()
