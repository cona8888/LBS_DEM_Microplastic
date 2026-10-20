"""8,000-step maximum combined pure-solver/storage qualification.

All six archived contact conditions plus the repaired contact and exact split
restart. No production, no altered physics, time steps or acceptance limits.
"""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy, os, shutil, sys, time, traceback
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage195_staging'))
import qualify_repaired_stack_v1 as pre
import constant_analytic_pair_v1 as opt
import lossless_fast_xz_v1 as storage
job,api,q=pre.job,pre.api,pre.q
WORK=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
DESIGN=WORK.with_name('combined_segments_01.json')
RUN=Path('D:/MATDEM_MICROPLASTIC/stage196_runs/deadline_recovery_20260925/combined_segments_01')
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/combined_segments_01'

def run():
    w=api.read(WORK);d=api.read(job.DESIGN);job.verify(d);storage.verify_bindings()
    api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc'])-timedelta(minutes=20),'launch time reserve')
    for p in psutil.process_iter(['pid','name','cmdline']):
        if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(p.info['cmdline'] or []).lower(),'exclusive diagnostic worker')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    prerequisites=[ROOT/'stage196_evaluations/deadline_recovery_20260925'/label/'results.json' for label in ('constant_pair_01','fast_storage_01')]
    for path in prerequisites:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed prerequisite')
        api.verify_mapping(r['inputs'])
        if 'artifacts' in r:api.verify_mapping(r['artifacts'])
    prior_result=ROOT/'stage196_evaluations/deadline_recovery_20260925/segment_profile_01/results.json'
    pr=api.read(prior_result);api.require(pr['new_accepted_steps']==326 and pr['unresolved_reservation']==0,'prior exact ledger')
    files=[WORK,job.DESIGN,Path(__file__),Path(opt.__file__),Path(storage.__file__),prior_result]+prerequisites
    protocol={'stage':'Stage196 combined exact segments','inputs':{str(p):api.sha(p) for p in files},'sources':d['sources'],
        'maximum_new_steps':8000,'prior_window_accepted_steps':326,'maximum_total_window_steps':8326,
        'unchanged_integration_code_sha256':q.campaign.code_sha(pre.wrapper.raw_execute),
        'case_contracts':d['cases'],'numerical_gates':d['numerical_gates'],'production_authorized':False}
    job.commit(DESIGN,protocol);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(minutes=20),job.policy.utc(w['last_diagnostic_launch_utc'])).isoformat()
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop,'protocol_sha256':api.sha(DESIGN),'maximum_new_steps':8000,'reserved_new_accepted_steps':0})
    ns={**pre.wrapper.raw_execute.__globals__,'DESIGN':DESIGN,'codec':storage.codec}
    execute=FunctionType(pre.wrapper.raw_execute.__code__,ns,'execute_segment',pre.wrapper.raw_execute.__defaults__,pre.wrapper.raw_execute.__closure__)
    api.require(q.campaign.code_sha(execute)==protocol['unchanged_integration_code_sha256'],'identical integration code')
    accepted=0;reports=[];unresolved=0
    def call(case,before,name,cap,geo,expected_rows=None,prefix=None,prior_rows=None,prior_ref=None):
        nonlocal accepted,unresolved
        api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']) and accepted+cap<=8000,'bounded call budget/time')
        api.require(shutil.disk_usage(RUN).free>w['minimum_free_disk_bytes']+4*storage.base.MAX_COMPRESSED,'D disk reserve')
        path=RUN/(name+'.json.xz')
        job.commit(path.with_suffix('.launch.json'),{'pid':os.getpid(),'utc':job.utc().isoformat(),'reserved_new_accepted_steps':cap,'known_window_steps_before':326+accepted,'input_checkpoint_sha256':api.digest(before),'protocol_sha256':api.sha(DESIGN)})
        unresolved=cap
        with opt.scope(True),pre.wrapper.repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):
            record,next_prefix,seal,transaction=execute(d,case,copy.deepcopy(before),path,cap,prefix,stop)
        count=len(record['rows']);accepted+=count;unresolved=0
        job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':count,'rejected':record['result']['rejected'],'raw_sha256':api.sha(path),'window_new_accepted_steps':326+accepted})
        t=time.perf_counter();decoded=q.independent_file(path,api.sha(DESIGN),prior_rows,prior_ref)
        api.require(storage.base.raw_bytes(decoded)==storage.base.raw_bytes(record),'exact independent record bytes')
        summary=job.kernel.evaluate(decoded,case['spec'],job.binding(d,case),before,geo,api.sha(DESIGN),d['minimum_gap_semantics'])
        audit_s=time.perf_counter()-t
        row={'case':case['id'],'name':name,'accepted_steps':count,'compute_seconds':record['compute_call_wall_s'],'transaction_seconds':transaction,'independent_audit_seconds':audit_s,
            'simulated_seconds':summary['stop_s']-summary['start_s'],'archive_bytes':seal['compressed_bytes'],'numerical_audit':summary,
            'exact_expected_rows':record['rows']==expected_rows if expected_rows is not None else None,'raw_sha256':api.sha(path)}
        reports.append(row);job.commit(path.with_suffix('.audit.json'),row)
        api.require(count==cap and record['result']['status']=='paused_checkpoint' and summary['passed'],'exact bounded success')
        if expected_rows is not None:api.require(row['exact_expected_rows'],'exact baseline rows')
        print('COMBINED_SEGMENT',name,count,round(transaction,3),round(record['compute_call_wall_s'],3),flush=True)
        return record,next_prefix
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            geo=pre.geometry()
            for case in d['cases']:
                before,oracle=pre.seed(d,case)
                record,_=call(case,before,case['id']+'_contact',1000,geo,oracle['rows'])
                api.require(record['result']['checkpoint']['state']==oracle['result']['checkpoint']['state'],'exact contact full state')
            case,before=pre.stress_seed(d)
            oracle=q.independent_file(Path(d['stress_oracle_raw']),api.sha(d['stress_oracle_design']))
            serial,_=call(case,before,'stress_serial',1000,geo,oracle['rows'][:1000])
            first,prefix=call(case,before,'stress_first',371,geo,serial['rows'][:371])
            last,_=call(case,first['result']['checkpoint'],'stress_last',629,geo,serial['rows'][371:],prefix,first['result']['history'],prefix.reference())
            api.require(last['result']['checkpoint']['state']==serial['result']['checkpoint']['state'],'exact split full state')
        api.verify_mapping(protocol['inputs']);api.verify_mapping(protocol['sources']);storage.verify_bindings()
        api.require(accepted==8000,'exact qualification ledger')
        result={'passed':True,'new_accepted_steps':accepted,'window_new_accepted_steps':326+accepted,'unresolved_steps':unresolved,'reports':reports,
            'inputs':protocol['inputs'],'protocol_sha256':api.sha(DESIGN),'exact_restart':True,'production_authorized':False,
            'artifacts':{str(p):api.sha(p) for p in RUN.iterdir() if p.is_file()}}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('COMBINED_PASS',accepted,flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'accepted_steps':accepted,'window_accepted_steps':326+accepted,'unresolved_steps':unresolved,'reports':reports});raise

if __name__=='__main__':run()
