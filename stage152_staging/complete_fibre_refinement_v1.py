"""Budget-only amendment: finish Stage151 and test a different restart split.

No historical mutation, trajectory-control change or production promotion.
The old dynamics binding is retained exactly; new workflow provenance is separate.
"""
from pathlib import Path
import copy
import datetime
import os
import platform
import sys
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage151_staging'))
import verify_rigid_rotation_v2 as imported
w=imported.workflow
api,engine,model,hot=w.api,w.engine,w.model,w.hot
BASE='fibre_refinement_completion_20260922'
DESIGN=ROOT/'stage152_designs'/BASE/'design_01.json'
RUN=ROOT/'stage152_runs'/BASE/'run_01'
OUT=ROOT/'stage152_evaluations'/BASE/'evaluation_01'
OLD_AUDIT=w.OUT.parent/'independent_audit_01'


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'workflow binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    old=api.read(w.DESIGN);w.verify(old)
    api.require(d['acceptance']==old['moving'],'unchanged acceptance and numerics')
    return old


def prepare():
    old=api.read(w.DESIGN);w.verify(old)
    audit=api.read(OLD_AUDIT/'results.json')
    api.require(api.sha(OLD_AUDIT/'results.json')==api.read(OLD_AUDIT/'completion.json')['results_sha256'],'old audit seal')
    api.verify_mapping(audit['artifact_hashes'])
    api.require(audit['finest_case_numerically_healthy_but_incomplete'] and not audit['moving_refinement_qualified'],'expected bounded incomplete result')
    fine_path=w.OUT/'rigid_0.25.json';fine=api.read(fine_path)
    api.require(fine['result']['status']=='incomplete_budget' and fine['health']['passed'] and fine['clock']['passed'],'healthy saved checkpoint')
    old_binding=api.digest([old['binding'],.25,True,False])
    api.require(model.binding_for(old_binding,True)==fine['effective_binding'],'original dynamics binding')
    inputs={str(p):api.sha(p) for p in [w.DESIGN,OLD_AUDIT/'results.json',OLD_AUDIT/'completion.json',Path(old['case']['source'])]}
    inputs.update(audit['artifact_hashes'])
    sources={str(Path(m.__file__).resolve()):api.sha(m.__file__) for m in list(sys.modules.values())
             if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
    d={'stage':'Stage152','question':'Do the completed local moving-fibre three-level test and two restart partitions pass the unchanged Stage151 gates?',
       'amendment':'Operational budget only: one 45-s continuation from the saved finest checkpoint, followed by at most two 45-s replay segments for exact restart. Original failed attempts remain unchanged.',
       'user_authority':'User next request after the explicit Stage151 handoff to resume the finest checkpoint and verify restart.',
       'spec':fine['spec'],'dynamics_binding':old_binding,'effective_binding':fine['effective_binding'],
       'saved_record':str(fine_path),'acceptance':old['moving'],
       'restart':'After completion, split the finest replay after floor(total accepted steps/2) from the original saved state. Compare final checkpoint state, pose, velocity, exact clock, and all accepted-interval records against the completed original partition.',
       'budget':{'maximum_calls':3,'cooperative_wall_s_per_call':45.,'accepted_step_cap_per_call':6000,'cpu_workers':1,'blas_threads':1},
       'physical_changes':[],'numerical_controls_changed':[],
       'stop':'No automatic retry or extra segment if one call fails or exhausts its budget. No longer physical horizon, contact-history model or production launch.',
       'claim':old['scope'],'sources':sources,'inputs':inputs}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def check_record(record,cp,spec,expected_binding):
    r=record['result'];rows=record['rows']
    api.require(cp['state_sha256']==api.digest(cp['state']),'input state hash')
    contract=engine.prior.contracts.expected_contract(spec,expected_binding)
    api.require(cp['contract']==r['checkpoint']['contract']==contract,'dynamics contract')
    health=engine.prior.reference.independent_health(r,spec)
    clock=w.prior.audit.clock_chain(cp['state']['t'],rows,r['time_s'])
    checks={'independent_health':health['passed'],'exact_clock':clock['passed'],
            'checkpoint_state_hash':r['checkpoint']['state_sha256']==api.digest(r['checkpoint']['state']),
            'accepted_steps_accounted':len(rows)==r['steps']-cp['state']['steps'],
            'no_unqualified_fallback':not r.get('stage119_repair_calls'),
            'input_checkpoint_hash':record['input_checkpoint_sha256']==api.digest(cp)}
    return {'passed':all(checks.values()),'checks':checks,'health':health,'clock':clock}


def execute(d,label,cp,pause=None):
    folder=RUN/label;folder.mkdir(exist_ok=False)
    before=copy.deepcopy(cp);call_start=len(model.calls)
    with hot.scope(),model.scope(True):
        result,rows=engine.runtime.execute(d['spec'],d['dynamics_binding'],checkpoint=cp,
            pause=cp['state']['steps']+(pause if pause is not None else d['budget']['accepted_step_cap_per_call']))
    record={'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(before),
            'workflow_design_sha256':api.sha(DESIGN),'effective_binding':d['effective_binding'],
            'runtime_backend_calls':copy.deepcopy(model.calls[call_start:])}
    record['checks']=check_record(record,before,d['spec'],d['effective_binding'])
    api.write(folder/'record.json',record,raw=True)
    api.write(folder/'completion.json',{'record_sha256':api.sha(folder/'record.json'),'health_passed':record['checks']['passed']})
    print(label,result['status'],len(rows),'HEALTH',record['checks']['passed'],flush=True)
    api.require(record['checks']['passed'],'independent runtime gate')
    api.require(len(record['runtime_backend_calls'])==1 and record['runtime_backend_calls'][0]['enabled'],'explicit live inertia backend')
    expected='paused_checkpoint' if pause is not None else 'present_at_horizon'
    api.require(result['status']==expected,'bounded segment incomplete or failed; no extra dispatch')
    return record


def compare_levels(old,fine):
    cases=[api.read(w.OUT/'rigid_1.0.json'),api.read(w.OUT/'rigid_0.5.json'),fine]
    errors=[w.compare(a['result'],b['result'],fine['spec']) for a,b in zip(cases,cases[1:])]
    moving=old['moving'];checks={}
    for k,limit in moving['limits'].items():
        checks[k]={'under_limit':errors[1][k]<=limit,
                   'refinement_trend':errors[1][k]<=moving['error_reduction_ratio_max']*errors[0][k] or max(errors[0][k],errors[1][k])<moving['noise_floor']}
    return {'passed':all(all(x.values()) for x in checks.values()),'errors':errors,'checks':checks}


def evaluate(d):
    old=verify(d);spec=d['spec'];original=api.read(old['case']['source'])['result']['checkpoint']
    original=model.checkpoint(spec,d['dynamics_binding'],original,True)
    saved=api.read(d['saved_record'])
    original_checks=check_record(saved,original,spec,d['effective_binding'])
    api.require(original_checks['passed'],'saved segment independent recheck')
    records={}
    for label in ['completion','restart_first','restart_second']:
        p=RUN/label/'record.json'
        api.require(api.sha(p)==api.read(p.parent/'completion.json')['record_sha256'],'new record seal')
        records[label]=api.read(p)
        api.require(records[label]['workflow_design_sha256']==api.sha(DESIGN),'new record workflow')
    starts={'completion':saved['result']['checkpoint'],'restart_first':original,'restart_second':records['restart_first']['result']['checkpoint']}
    checks={label:check_record(record,starts[label],spec,d['effective_binding']) for label,record in records.items()}
    final=records['completion']['result'];other=records['restart_second']['result']
    joined=saved['rows']+records['completion']['rows'];replay=records['restart_first']['rows']+records['restart_second']['rows']
    restart={'final_checkpoint_state_exact':final['checkpoint']['state_sha256']==other['checkpoint']['state_sha256'] and final['checkpoint']['state']==other['checkpoint']['state'],
             'final_pose_velocity_clock_exact':all(final[k]==other[k] for k in ['position_m','orientation','velocity_generalized','time_s']),
             'every_accepted_interval_exact':joined==replay,
             'different_split_points':len(saved['rows'])!=len(records['restart_first']['rows']),
             'halfway_split':len(records['restart_first']['rows'])==len(joined)//2}
    completed=all(r['result']['status']=='present_at_horizon' and r['result']['time_s']==spec['horizon_s'] for r in [records['completion'],records['restart_second']])
    fine={'result':final,'spec':spec};comparison=compare_levels(old,fine)
    baseline=api.read(w.OUT/'quasistatic.json')
    cost={'finest_original_plus_continuation_s':saved['result']['runtime_seconds']+final['runtime_seconds'],
          'restart_replay_s':sum(records[k]['result']['runtime_seconds'] for k in ['restart_first','restart_second']),
          'quasistatic_s':baseline['result']['runtime_seconds'],'finest_accepted_steps':len(joined),
          'new_continuation_accepted_steps':len(records['completion']['rows']),
          'finest_new_rejections':final['rejected']-original['state']['rejected']}
    result={'stage':'Stage152','passed':completed and all(x['passed'] for x in checks.values()) and comparison['passed'] and all(restart.values()),
            'same_horizon_completed':completed,'three_level':comparison,'restart':restart,'checks':checks,
            'quasistatic_to_rigid_finest_difference':w.compare(baseline['result'],final,spec),
            'cost':cost,'time_s':final['time_s'],'window_s':old['moving']['window_s'],
            'claim':d['claim'],'production_promotion':False,'historical_failures_preserved':True,
            'design_sha256':api.sha(DESIGN),'sources_and_inputs_verified':True,
            'artifacts':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()}}
    OUT.mkdir(parents=True,exist_ok=False);api.write(OUT/'results.json',result,raw=True)
    api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('STAGE152_PASS',result['passed'],'ERRORS',comparison['errors'],'RESTART',restart,flush=True)
    return 0 if result['passed'] else 4


def run():
    d=api.read(DESIGN);old=verify(d);RUN.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,
        'threads':{k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']},'design_sha256':api.sha(DESIGN)})
    w.prior.parent.old.prior.prior.configure();hot.warmup()
    saved=api.read(d['saved_record']);completed=execute(d,'completion',saved['result']['checkpoint'])
    fine={'result':completed['result'],'spec':d['spec']};comparison=compare_levels(old,fine)
    api.write(RUN/'three_level_precheck.json',comparison)
    api.require(comparison['passed'],'three-level gate; do not spend restart compute')
    source=api.read(old['case']['source'])['result']['checkpoint']
    initial=model.checkpoint(d['spec'],d['dynamics_binding'],source,True)
    count=completed['result']['steps']-initial['state']['steps'];half=count//2
    api.require(0<half<d['budget']['accepted_step_cap_per_call'],'bounded restart split')
    first=execute(d,'restart_first',initial,pause=half)
    execute(d,'restart_second',first['result']['checkpoint'])
    return evaluate(d)


if __name__=='__main__':
    try:
        if sys.argv[1]=='prepare':prepare()
        elif sys.argv[1]=='run':raise SystemExit(run())
        elif sys.argv[1]=='evaluate':
            w.prior.parent.old.prior.prior.configure();raise SystemExit(evaluate(api.read(DESIGN)))
        else:raise ValueError('unknown command')
    except Exception as exc:
        if RUN.exists() and not (RUN/'failure.json').exists():api.write(RUN/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise
