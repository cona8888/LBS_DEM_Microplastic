"""Independent original-byte, failure, chain and cache-lifetime qualification."""
from pathlib import Path
from types import FunctionType
import copy,sys,time,traceback
import transaction_json_memo_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage196_staging'))
import qualify_compact_storage_v1 as tests
import native_storage_v2 as previous
api,job,q=tests.api,tests.job,tests.q
WORK=ROOT/'stage199_designs/eight_hour_optimization_20260926/contract_01.json'
DESIGN=WORK.with_name('transaction_json_01.json')
RUN=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/transaction_json_01')
OUT=ROOT/'stage199_evaluations/eight_hour_optimization_20260926/transaction_json_01'
ns={**tests.__dict__,'candidate':candidate,'WORK':WORK,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'__file__':__file__}
run=FunctionType(tests.run.__code__,ns,tests.run.__name__,tests.run.__defaults__,tests.run.__closure__)

def main():
    api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    prerequisite=OUT.parent/'native_storage_02/results.json';r=api.read(prerequisite)
    api.require(r['passed'] and api.read(prerequisite.parent/'completion.json')['results_sha256']==api.sha(prerequisite),'sealed prerequisite')
    raw=Path('D:/MATDEM_MICROPLASTIC/stage198_runs/direct_trf_20260926/fine_01/serial.json.xz')
    files=[Path(__file__),Path(candidate.__file__),Path(candidate.native.__file__),Path(candidate.prior.__file__),Path(tests.__file__),Path(previous.__file__),WORK,prerequisite,raw,raw.with_suffix('.seal.json')]
    mapping={str(x):api.sha(x) for x in files}
    job.commit(DESIGN.with_name('transaction_json_harness_01.json'),{'stage':'Stage199 one-write canonical memo verification','inputs':mapping,'new_trajectory_steps':0,'bound':'Only known never-mutated evidence fields during one frozen encode/pack/write transaction;128MiB cap; no reader or cross-record memo.'})
    run()
    # This supplements, never replaces, the original20 full-record/chain and
    #19failed-record checks, each independently reconstructed and rehashed.
    benchmark=RUN/'benchmark';benchmark.mkdir(exist_ok=False)
    sha=api.read(raw.with_suffix('.seal.json'))['design_sha256'];record=q.independent_file(raw,sha);expected=candidate.base.raw_bytes(record)
    info=__import__('qualify_performance_stack_v1').wrapper.affinity.bind(14)
    results=[]
    for round_index in range(3):
        for label,module in (('previous',previous),('memo',candidate)) if round_index%2==0 else (('memo',candidate),('previous',previous)):
            api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
            path=benchmark/f'{label}_{round_index}.json.xz';tick=time.perf_counter();seal,_=module.codec.write_record(path,record);elapsed=time.perf_counter()-tick
            stats=copy.deepcopy(candidate.last_stats) if label=='memo' else None
            decoded=q.independent_file(path,sha);api.require(candidate.base.raw_bytes(decoded)==expected,'full independent benchmark bytes')
            api.require(candidate._active.get() is None,'memo cleared after each record')
            results.append({'mode':label,'round':round_index,'seconds':elapsed,'stats':stats,'raw_sha256':api.sha(path)});print('TRANSACTION_JSON_TIME',label,elapsed,stats,flush=True)
    # Mutation BETWEEN records must be observed, not stale-cached.
    record['step_cap']+=1;dest=benchmark/'changed_input.json.xz';candidate.codec.write_record(dest,record)
    api.require(candidate.base.raw_bytes(q.independent_file(dest,sha))==candidate.base.raw_bytes(record),'changed next-record input observed')
    try:candidate.codec.write_record(dest,record)
    except FileExistsError:pass
    else:raise AssertionError('immutable collision accepted')
    api.require(candidate._active.get() is None,'memo cleared after exception')
    candidate.verify_bindings();api.verify_mapping(mapping)
    means={m:sum(x['seconds'] for x in results if x['mode']==m)/3 for m in ('previous','memo')}
    result={'passed':True,'new_trajectory_steps':0,'measurements':results,'means':means,'mean_speedup':means['previous']/means['memo'],'changed_next_record_and_failure_cleanup_passed':True,'affinity':info,'inputs':mapping,'full_fixture_results_sha256':api.sha(OUT/'results.json'),'artifacts':{str(x):api.sha(x) for x in benchmark.iterdir() if x.is_file()}}
    job.commit(OUT/'benchmark.json',result);job.commit(OUT/'benchmark_completion.json',{'passed':True,'benchmark_sha256':api.sha(OUT/'benchmark.json')});print('TRANSACTION_JSON_PASS',result['mean_speedup'],flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        path=OUT.parent/'transaction_json_failure_01.json'
        if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
        raise
