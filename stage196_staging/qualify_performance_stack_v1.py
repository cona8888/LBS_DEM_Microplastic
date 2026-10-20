"""Frozen 17,000-step preflight on six distinct performance cores.

6x1000 contact + 1000 serial + 500+500 restart + 6x500 parallel +
6x2x500 live pipeline. Existing failed outputs stay immutable.
"""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy, os, psutil, shutil, subprocess, sys, time, traceback
import performance_stack_preflight_v1 as wrapper
job,api,q=wrapper.job,wrapper.api,wrapper.q
sys.path.insert(0,str(wrapper.ROOT/'stage195_staging'))
import qualify_repaired_stack_v1 as prior
ROOT=wrapper.ROOT;RUN=job.PREFLIGHT;OUT=job.OUT/'preflight_01';SELF=Path(__file__).resolve()
base_protocol=prior.original
# Zero-step cutoff/failure drain uses the unchanged actual lifecycle and auditor.
protocol_fixtures=FunctionType(base_protocol.protocol_fixtures.__code__,{**base_protocol.protocol_fixtures.__globals__,'job':job,'api':api,'RUN':RUN},'protocol_fixtures')


def seed(d,case):
    before,oracle=prior.seed(api.read(prior.job.DESIGN),case)
    cp=job.parent.model.checkpoint(case['spec'],job.binding(d,case),before,True)
    api.require(cp['state']==before['state'],'seed state unchanged')
    return cp,oracle


def stress_seed(d):
    case=next(c for c in d['cases'] if c['id']==d['stress_case'])
    rec=q.independent_file(Path(d['stress_seed_raw']),api.sha(d['stress_seed_design']))
    cp=job.parent.model.checkpoint(case['spec'],job.binding(d,case),rec['result']['checkpoint'],True)
    api.require(cp['state']==rec['result']['checkpoint']['state'],'stress state unchanged')
    return case,cp


def deadline():
    stop=api.read(RUN/'launch.json')['preflight_stop_utc']
    api.require(job.utc()<job.policy.utc(stop)-timedelta(seconds=120),'preflight wall reserve')
    return stop


def call(d,case,cp,name,cap,geo,prefix=None):
    path=RUN/'probes'/(name+'.json.xz');path.parent.mkdir(exist_ok=True)
    job.commit(path.with_suffix('.launch.json'),{'pid':os.getpid(),'utc':job.utc().isoformat(),'reserved_new_accepted_steps':cap,'case':case['id'],
        'input_checkpoint_sha256':api.digest(cp),'design_sha256':api.sha(job.DESIGN),'affinity':psutil.Process().cpu_affinity()})
    rec,state,_,tx=job.execute_segment(d,case,copy.deepcopy(cp),path,cap,prefix,deadline())
    job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':len(rec['rows']),'rejected':rec['result']['rejected'],'raw_sha256':api.sha(path)})
    decoded,_=job.codec.read_record(path,api.sha(job.DESIGN),prefix)
    api.require(job.codec.base.raw_bytes(decoded)==job.codec.base.raw_bytes(rec),'original canonical record identity')
    summary=job.kernel.evaluate(decoded,case['spec'],job.binding(d,case),cp,geo,api.sha(job.DESIGN),d['minimum_gap_semantics'])
    receipt={'case':case['id'],'steps':len(rec['rows']),'path':str(path),'raw_sha256':api.sha(path),'summary':summary,'transaction_seconds':tx,'design_sha256':api.sha(job.DESIGN)}
    job.commit(path.with_suffix('.preflight_audit.json'),receipt)
    api.require(len(rec['rows'])==cap and rec['result']['status']=='paused_checkpoint' and summary['passed'],'exact bounded call success')
    return decoded,state,receipt


def probe(index):
    d=api.read(job.DESIGN);job.verify(d);api.require(0<=index<6,'bounded probe index')
    info=wrapper.affinity.bind(d['worker_logical_cpus'][index])
    job.commit(RUN/f'parallel_{index}.affinity.json',info)
    job.parent.b.old.parent.configure();case,cp=stress_seed(d)
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        call(d,case,cp,f'parallel_{index}',500,prior.geometry())


def run():
    d=api.read(job.DESIGN);job.verify(d);work=api.read(wrapper.WORK)
    api.require(job.utc()<job.policy.utc(work['last_diagnostic_launch_utc'])-timedelta(seconds=3700),'preflight time reserve')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'no duplicate simulation or benchmark')
    info=wrapper.affinity.bind(d['auditor_logical_cpu'])
    api.require(shutil.disk_usage(RUN.parent).free>d['budget']['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'D reserve')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(seconds=d['preflight']['wall_seconds']),job.policy.utc(work['last_diagnostic_launch_utc']))
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'preflight_stop_utc':stop.isoformat(),
        'design_sha256':api.sha(job.DESIGN),'maximum_new_steps':17000,'prior_stage196_steps':8326,'owned_affinity':info})
    started=time.perf_counter();children=[];cases=[];total=0
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            geo=prior.geometry()
            for case in d['cases']:
                cp,oracle=seed(d,case);rec,_,audit=call(d,case,cp,case['id']+'_contact',1000,geo);total+=1000
                api.require(rec['rows']==oracle['rows'] and rec['result']['checkpoint']['state']==oracle['result']['checkpoint']['state'],'exact old contact trajectory and full state')
                cases.append({'case':case['id'],'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':audit['transaction_seconds'],
                    'simulated_seconds':audit['summary']['stop_s']-audit['summary']['start_s'],'exact_contact':True,'numerical_audit':audit['summary']})
                print('PCORE_CONTACT',case['id'],round(rec['compute_call_wall_s'],3),flush=True)
            case,cp=stress_seed(d)
            serial,_,_=call(d,case,cp,'serial',1000,geo);total+=1000
            oracle=q.independent_file(Path(d['stress_oracle_raw']),api.sha(d['stress_oracle_design']))
            api.require(serial['rows']==oracle['rows'][:1000],'repaired contact exact prefix')
            first,prefix,_=call(d,case,cp,'split_first',500,geo);total+=500
            last,_,_=call(d,case,first['result']['checkpoint'],'split_last',500,geo,prefix);total+=500
            api.require(first['rows']+last['rows']==serial['rows'] and last['result']['checkpoint']['state']==serial['result']['checkpoint']['state'],'exact split restart')
        launches=[]
        for i in range(6):
            stdout=(RUN/f'parallel_{i}.stdout.log').open('xb');stderr=(RUN/f'parallel_{i}.stderr.log').open('xb')
            command=[sys.executable,'-B','-u',str(SELF),'probe',str(i)]
            try:p=subprocess.Popen(command,cwd=str(ROOT),env=dict(os.environ,OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
            finally:stdout.close();stderr.close()
            children.append(p);launches.append({'pid':p.pid,'argv':command,'logical_cpu':d['worker_logical_cpus'][i]})
        job.commit(RUN/'parallel_launches.json',{'children':launches,'design_sha256':api.sha(job.DESIGN)})
        while any(p.poll() is None for p in children):time.sleep(.2)
        api.require(all(p.returncode==0 for p in children),'six parallel workers exited successfully')
        ratios=[]
        for i in range(6):
            path=RUN/'probes'/f'parallel_{i}.json.xz';rec,_=job.codec.read_record(path,api.sha(job.DESIGN));total+=len(rec['rows'])
            api.require((RUN/f'parallel_{i}.stderr.log').stat().st_size==0,'empty parallel stderr')
            api.require(rec['rows']==first['rows'] and rec['result']['checkpoint']['state']==first['result']['checkpoint']['state'],'exact parallel 500-step state')
            ratios.append(rec['compute_call_wall_s']/first['compute_call_wall_s'])
        api.require(max(ratios)<=1.3,'unchanged 30-percent parallel slowdown gate')
        print('SIX_PCORE_PARALLEL_PASS',ratios,flush=True)
        deadline();job.supervise('preflight');live=job.evaluate('preflight');total+=live['total_accepted_steps']
        api.require(live['preflight_passed'] and live['total_accepted_steps']==6000,'live six-worker producer/auditor pipeline')
        for case in d['cases']:
            p=job.paths(job.root_for('preflight'),case['id'],1)['raw'];rec,_=job.codec.read_record(p,api.sha(job.DESIGN))
            old=ROOT/'stage195_runs/repaired_stack_preflight_20260925/preflight_01/probes'/(case['id']+'_fresh.json.xz')
            oracle=q.independent_file(old,api.sha(prior.job.DESIGN))
            api.require(rec['rows'][:200]==oracle['rows'],'fresh-start exact original 200-step control')
        fixtures=protocol_fixtures(d);job.verify(d)
        api.require(total==17000 and total+8326<=work['maximum_new_qualification_accepted_steps'],'exact cumulative qualification ledger')
        api.require(sum(c['step_ceiling'] for c in d['cases'])+total<=d['budget']['max_new_steps_total'],'unchanged prospective campaign/preflight ceiling')
        result={'passed':True,'new_steps':total,'prior_stage196_steps':8326,'window_new_accepted_steps':total+8326,'cases':cases,
            'parallel_slowdown_ratios':ratios,'parallel_identity':True,'exact_restart':True,'independent_audit_passed':True,'cutoff_and_failure_drain':True,
            'live_pipeline_steps':6000,'protocol_fixtures':fixtures,'design_sha256':api.sha(job.DESIGN),'sources':d['sources'],
            'artifacts':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()},'wall_seconds':time.perf_counter()-started,
            'production_authorized':False,'runtime_forecast_not_yet_updated':True,'claim':'Bounded exact preflight only; full-path completion and deadline fit remain unverified.'}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('PERFORMANCE_STACK_PASS',total,flush=True)
    except Exception as error:
        # No forceful retirement; bounded child calls share the frozen wall cutoff.
        while any(p.poll() is None for p in children):time.sleep(.2)
        counts=[];unresolved=[]
        for launch in (RUN/'probes').glob('*.launch.json'):
            account=launch.with_name(launch.name.replace('.launch.json','.accounting.json'))
            if account.exists():counts.append(api.read(account)['accepted_steps'])
            else:unresolved.append({'launch':str(launch),'reserved_steps':api.read(launch)['reserved_new_accepted_steps']})
        live_steps=sum(api.read(p)['steps'] for p in (RUN/'live').rglob('segment_*.ready.json')) if (RUN/'live').exists() else 0
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'known_probe_steps':sum(counts),'live_saved_steps':live_steps,
            'window_known_accepted_steps':8326+sum(counts)+live_steps,'unresolved_probes':unresolved,'all_probe_children_retired':True});raise


if __name__=='__main__':
    if sys.argv[1:]==['run']:run()
    elif len(sys.argv)==3 and sys.argv[1]=='probe':probe(int(sys.argv[2]))
    else:raise ValueError('run | probe INDEX')
