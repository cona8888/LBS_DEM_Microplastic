"""Independent whole-byte, failure/chain and owned-reader lifetime checks."""
from pathlib import Path
from types import FunctionType
import copy,sys,time,traceback
import owned_decode_storage_v1 as candidate
import qualify_transaction_json_v1 as prior
api,job,q,WORK=prior.api,prior.job,prior.q,prior.WORK
DESIGN=WORK.with_name('owned_decode_01.json');RUN=prior.RUN.with_name('owned_decode_01');OUT=prior.OUT.with_name('owned_decode_01')
ns={**prior.tests.__dict__,'candidate':candidate,'WORK':WORK,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'__file__':__file__}
f=prior.tests.run;run_fixtures=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def main():
    api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    sealed=prior.OUT/'results.json';api.require(api.read(sealed)['passed'] and api.read(sealed.parent/'completion.json')['results_sha256']==api.sha(sealed),'qualified prior codec')
    raw=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/current_prefix_01/serial.json.xz')
    mapping={str(x):api.sha(x) for x in (Path(__file__),Path(candidate.__file__),Path(candidate.memo_storage.__file__),Path(prior.tests.__file__),WORK,sealed,sealed.parent/'completion.json',raw,raw.with_suffix('.seal.json'))}
    job.commit(DESIGN.with_name('owned_decode_harness_01.json'),{'stage':'Stage199 owned fresh-decoder tree qualification','inputs':mapping,'new_trajectory_steps':0,'benchmark_rounds':3,'reader_speedup_gate':1.1,
        'ownership_proof':'Only the frozen path-based bounded reader creates the private tree. No caller-provided wrapper, cached record, producer object or prefix object enters copy-elision. All generic unpack copies and all per-system copies/checks/hashes remain.',
        'structural_change':'Remove one redundant deep copy of a uniquely owned, freshly json-decoded wrapper; no scientific or resource gate changed.'})
    run_fixtures()
    design=api.read(raw.with_suffix('.seal.json'))['design_sha256'];expected=q.independent_file(raw,design);original=prior.candidate;expected_bytes=candidate.base.raw_bytes(expected)
    info=__import__('qualify_performance_stack_v1').wrapper.affinity.bind(14);rows=[]
    for i in range(3):
        for label,module in (('original',original),('owned',candidate)) if i%2==0 else (('owned',candidate),('original',original)):
            tick=time.perf_counter();decoded,_=module.codec.read_record(raw,design);elapsed=time.perf_counter()-tick
            api.require(candidate.base.raw_bytes(decoded)==expected_bytes,'full original canonical independent read identity')
            rows.append({'round':i,'mode':label,'read_seconds':elapsed});print('OWNED_READ',label,elapsed,flush=True)
    # Public unpack must still preserve a caller-owned tree. Synthetic fixture
    # public paths are independently hashed above; explicitly test no mutation.
    envelope=prior.tests.q.fixtures()[0][1];packed=candidate.instance.pack(envelope);before=candidate.base.raw_bytes(packed)
    candidate.instance.unpack(packed);api.require(candidate.base.raw_bytes(packed)==before,'generic caller-owned unpack unchanged')
    a,_=candidate.codec.read_record(raw,design);b,_=candidate.codec.read_record(raw,design)
    a['rows'][0]['velocity_generalized'][0]+=1
    api.require(candidate.base.raw_bytes(b)==expected_bytes,'separate reads have no shared mutable output')
    c,_=candidate.codec.read_record(raw,design);api.require(candidate.base.raw_bytes(c)==expected_bytes,'mutation cannot leak into subsequent read')
    means={label:sum(x['read_seconds'] for x in rows if x['mode']==label)/3 for label in ('original','owned')};speed=means['original']/means['owned']
    candidate.verify_bindings();api.verify_mapping(mapping)
    r={'passed':True,'new_trajectory_steps':0,'reader_speedup':speed,'material_reader_gain_passed':speed>=1.1,'reader_speedup_gate':1.1,'measurements':rows,'means':means,'public_input_preserved':True,'separate_read_mutation_isolation':True,'fixture_results_sha256':api.sha(OUT/'results.json'),'affinity':info,'inputs':mapping,'production_authorized':False}
    job.commit(OUT/'benchmark.json',r);job.commit(OUT/'benchmark_completion.json',{'benchmark_sha256':api.sha(OUT/'benchmark.json')});print('OWNED_DECODE_QUALIFIED',speed,r['material_reader_gain_passed'],flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        path=OUT.parent/'owned_decode_failure_01.json'
        if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
        raise
