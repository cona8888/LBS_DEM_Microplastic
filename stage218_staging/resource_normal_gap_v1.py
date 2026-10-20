"""Fresh measured resource forecast and explicit clocks; zero trajectories."""
from pathlib import Path
from datetime import timedelta
from types import FunctionType
import math,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage216_staging'),str(ROOT/'stage208_staging')]
import same_policy_stack_preflight_v1 as pre
import resource_cone_stack_v1 as old
api,job=pre.api,pre.job
BASE='normal_gap_resource_20261001';SELF=Path(__file__).resolve()
WORK=ROOT/'stage218_designs'/BASE/'contract_01.json'
PROTOCOL=WORK.with_name('resource_protocol_01.json')
OUT=ROOT/'stage218_evaluations'/BASE/'resource_01'
NUMERICAL=job.OUT/'failed_stack_independent_02/results.json'
FIXTURE=ROOT/'stage217_evaluations/isolated_drain_fixtures_20261001/independent_01/results.json'
FLOOR=ROOT/'stage208_evaluations/cone_feasibility_stack_20260930/resource_schedule_01/results.json'
HISTORY=old.HISTORY
LOCAL=pre.local.RUNBASE
NAMES=('serial_01','split_a_01','split_b_01')
schedule=FunctionType(old.old.schedule.__code__,{**old.old.schedule.__globals__,'api':api},'schedule')

def prerequisites():
    w=api.read(WORK);job.verify(api.read(job.DESIGN))
    n=pre.sealed(NUMERICAL);f=pre.sealed(FIXTURE)
    api.require(api.sha(NUMERICAL)=='d9cc0150e466d757e365338fa3cea7c338fe6c2f8b1d79e0307297646525f0c3'
        and not n['preflight_passed'] and n['numerical_qualification_passed'] and n['failure_accounting_closed']
        and n['saved_steps']==n['independently_physical_passing_steps']==17000,'explicit reused independently closed failed-preflight numerical evidence')
    api.require(api.sha(FIXTURE)=='50f2a2de99161ee3af40b4b70f2bc54fff9c505e15a40b1fd9ebd52843153d25'
        and f['passed'] and f['complementary_full_stack_qualification_passed'] and f['stage216_failure_preserved']
        and f['new_trajectory_steps']==0 and f['total_saved_policy_qualification_steps']==27600,'separate independently closed fixture complement')
    api.verify_mapping(n['inputs']);api.verify_mapping(f['inputs'])
    api.require(job.utc()<job.policy.utc(w['qualification_work_end_utc']) and not job.RUN.exists(),'local resource preparation clock/no production')
    return w

def prepare():
    w=prerequisites();floor=pre.sealed(FLOOR)
    api.require(not PROTOCOL.exists() and not OUT.exists(),'exclusive resource protocol')
    paths=[WORK,job.DESIGN,NUMERICAL,NUMERICAL.parent/'completion.json',FIXTURE,FIXTURE.parent/'completion.json',FLOOR,FLOOR.parent/'completion.json',HISTORY]
    paths += [LOCAL/n/'results.json' for n in NAMES]
    p={'new_trajectory_steps':0,'planning_segment_yield':min(3650,floor['planning_segment_yield']),
        'prior_saved_policy_qualification_steps':27600,'production_authorized':False,
        'inputs':{str(x):api.sha(x) for x in paths},
        'sources':{str(x):api.sha(x) for x in [SELF,SELF.with_name('audit_resource_normal_gap_v1.py'),Path(old.__file__),Path(old.old.__file__)]}}
    p['binding']=api.digest(p);job.commit(PROTOCOL,p);print('NORMAL_GAP_RESOURCE_PROTOCOL',api.sha(PROTOCOL),flush=True)

def samples():
    rows=[]
    def add(kind,case,steps,tx,audit,span,raw,evidence):
        raw=Path(raw);api.require(steps>0 and span>0,'positive cost sample')
        rows.append(dict(kind=kind,case=case,steps=steps,tx=tx,audit=audit,span=span,raw=str(raw),raw_sha256=api.sha(raw),bytes=raw.stat().st_size,evidence=str(evidence),evidence_sha256=api.sha(evidence)))
    for path in sorted((job.PREFLIGHT/'probes').glob('*.preflight_audit.json')):
        r=api.read(path);s=r['summary'];api.require(s['passed'] and r['raw_sha256']==api.sha(r['path']),'independently closed probe cost binding')
        add('probe',r['case'],r['steps'],r['transaction_seconds'],s['audit_seconds'],s['stop_s']-s['start_s'],r['path'],path)
    for c in api.read(job.DESIGN)['cases']:
        for index in (1,2):
            paths=job.paths(job.root_for('preflight'),c['id'],index);mark=api.read(paths['ready']);r=api.read(paths['receipt']);s=r['summary']
            api.require(s['passed'] and r['status']=='independently_verified' and mark['raw_sha256']==api.sha(paths['raw']),'independently closed live cost binding')
            add('live',c['id'],mark['steps'],mark['transaction_seconds'],s['audit_seconds'],s['stop_s']-s['start_s'],paths['raw'],paths['receipt'])
    for name in NAMES:
        folder=LOCAL/name;r=pre.sealed(folder/'results.json');s=r['audit'];api.verify_mapping(r['artifacts'])
        api.require(r['numerical_audit_passed'] and r['rejected']==0 and r['steps']==r['independently_accepted_steps'],'closed local cost sample')
        add('local','s2_i124_sphere_f0p0625',r['steps'],r['transaction_seconds'],s['audit_seconds'],s['stop_s']-s['start_s'],folder/'call.json.xz',folder/'results.json')
    api.require(len(rows)==30,'all27 full stack and3 closed local cost samples')
    return rows

def run():
    w=prerequisites();p=api.read(PROTOCOL)
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'resource protocol binding');api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    floor=pre.sealed(FLOOR);hist=pre.sealed(HISTORY);api.verify_mapping(hist['artifacts'])
    rows=samples();d=api.read(job.DESIGN);y=p['planning_segment_yield']
    late={k:max(floor['late_history_cost'][k],max(x[v] for x in hist['measurements'])) for k,v in [('write','write_seconds'),('read','read_seconds'),('hash','state_hash_seconds'),('bytes','compressed_bytes')]}
    costs={shape:{k:max(floor['shape_costs'][shape][k],max(x[v]/x['steps'] for x in rows if '_'+shape+'_' in x['case'])) for k,v in [('tx_per_step','tx'),('audit_per_step','audit')]} for shape in ('fibre','sphere')}
    allrows=rows+floor['samples'];perbyte=max(x['bytes']/x['steps'] for x in allrows);cases=[];rawbytes=0;calls=True
    for c in d['cases']:
        dt=min(x['span']/x['steps'] for x in allrows if x['case']==c['id']);steps=math.ceil(c['spec']['horizon_s']/dt)
        api.require(steps<=c['step_ceiling'],'original case step ceiling')
        cost=costs['fibre' if '_fibre_' in c['id'] else 'sphere'];count=math.ceil(steps/y);ceiling=math.ceil(c['step_ceiling']/y)
        cases.append(dict(case=c['id'],planning_steps=steps,records=count,ceiling_records=ceiling,producer_s=cost['tx_per_step']*y+late['write']+late['hash'],auditor_s=cost['audit_per_step']*y+late['read']+late['hash']+w['per_receipt_allowance_s'],source_step_seconds=dt))
        rawbytes+=c['step_ceiling']*perbyte+ceiling*late['bytes'];calls &= ceiling<=d['budget']['max_calls_per_case']
    queue=schedule(cases,w['production_workers'])
    hours=max(floor['production_hours_with_margin'],(queue['seconds']+w['startup_seconds'])*w['runtime_margin']/3600)
    audit=max(floor['required_final_audit_hours'],math.ceil((sum(c['records']*c['auditor_s'] for c in cases)+w['startup_seconds'])*w['runtime_margin']/3600))
    need=max(floor['storage_bytes_with_margin'],math.ceil((rawbytes+sum(c['step_ceiling'] for c in d['cases'])*13*8+sum(c['ceiling_records'] for c in cases)*8192+1024**3)*w['storage_margin']))
    now=job.utc();old_cutoff=job.policy.utc(w['original_simulation_cutoff_utc']);old_audit=job.policy.utc(w['original_final_audit_deadline_utc']);old_available=(old_cutoff-now).total_seconds()/3600
    earliest=now+timedelta(hours=hours+w['launch_headroom_hours']);cutoff=earliest.replace(hour=18,minute=59,second=0,microsecond=0)
    if cutoff<earliest:cutoff+=timedelta(days=1)
    reserve=max((old_audit-old_cutoff).total_seconds()/3600,audit);final=cutoff+timedelta(hours=reserve)
    free=shutil.disk_usage('D:/MATDEM_MICROPLASTIC').free;storage=need+w['minimum_free_disk_bytes']<=free
    passed=bool(calls and storage and (cutoff-now).total_seconds()/3600>=hours and reserve>=audit)
    r=dict(calculation_passed=True,resource_gate_passed=passed,new_trajectory_steps=0,production_authorized=False,
        production_hours_with_margin=hours,required_final_audit_hours=audit,storage_bytes_with_margin=need,minimum_reserve_bytes=w['minimum_free_disk_bytes'],free_D_bytes=free,
        original_calendar_fit_passed=bool(hours<=old_available and audit<=(old_audit-old_cutoff).total_seconds()/3600 and storage and calls),original_available_production_hours=old_available,
        original_simulation_cutoff_utc=old_cutoff.isoformat(),original_final_audit_deadline_utc=old_audit.isoformat(),
        proposed_simulation_cutoff_utc=cutoff.isoformat(),proposed_final_audit_deadline_utc=final.isoformat(),reserved_final_audit_hours=reserve,
        calendar_revision_not_yet_bound_to_production=True,call_limit_passed=bool(calls),samples=rows,cases=cases,shape_costs=costs,late_history_cost=late,
        queue=queue,planning_segment_yield=y,protocol_sha256=api.sha(PROTOCOL),utc=now.isoformat(),claim=w['claim'])
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('NORMAL_GAP_RESOURCE',passed,hours,audit,need,cutoff.isoformat(),final.isoformat(),flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run; zero trajectories')
