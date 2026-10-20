"""7160-step exact hard-fine serial/restart diagnostic of qualified speedups."""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy, importlib.util, os, psutil, shutil, sys, time, traceback
import direct_trf_v2 as candidate
import fast_storage_v1 as storage
import qualify_direct_trf_v1 as held
pre=held.pre;api,q=pre.api,pre.q;ROOT=held.ROOT
BASE='direct_trf_20260926'
DESIGN=ROOT/'stage198_designs'/BASE/'fine_protocol_01.json'
RUN=Path('D:/MATDEM_MICROPLASTIC/stage198_runs')/BASE/'fine_01'
OUT=ROOT/'stage198_evaluations'/BASE/'fine_01'
AUTH=held.AUTH
spec=importlib.util.spec_from_file_location('_stage198_fine_lifecycle',q.campaign.qualified.instance.historical.__file__)
job=importlib.util.module_from_spec(spec);sys.modules[spec.name]=job;spec.loader.exec_module(job)
job.DESIGN=DESIGN;job.codec=storage.codec;job.kernel=pre.job.kernel;job.observer=pre.job.observer
execute=FunctionType(pre.wrapper.raw_execute.__code__,dict(job.__dict__),'execute_segment',pre.wrapper.raw_execute.__defaults__,pre.wrapper.raw_execute.__closure__)

def prepare():
    d=copy.deepcopy(api.read(pre.job.DESIGN));pre.job.verify(d);d.pop('binding')
    results=[ROOT/'stage198_evaluations'/BASE/x/'results.json' for x in ('held_02','storage_01')]
    for path in results:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed exact qualification')
        if 'inputs' in r:api.verify_mapping(r['inputs'])
    files=[Path(__file__),Path(candidate.__file__),Path(candidate.prior.__file__),Path(candidate.compiled.__file__),Path(storage.__file__),Path(storage.canonical.__file__)]
    inputs=[AUTH,pre.job.DESIGN,held.FINE,held.FINE.with_suffix('.seal.json'),ROOT/'stage197_evaluations/deadline_extension_20260926/deadline_check_01/results.json',*results,
        ROOT/'stage198_designs'/BASE/'held_protocol_02.json',ROOT/'stage198_designs'/BASE/'storage_harness_01.json',ROOT/'stage198_designs'/BASE/'canonical_edges_01.json']
    d.update(stage='Stage198 exact hard-fine performance probe',sources={**d['sources'],**{str(x.resolve()):api.sha(x) for x in files}},
        inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},calls={'serial':3580,'split_a':1790,'split_b':1790},diagnostic_maximum_new_steps=7160,
        diagnostic_prior_recovery_steps=45830,production_authorized=False,claim='Local exact implementation/restart qualification only; no full-path or release conclusion.',
        diagnostic_wall_seconds=1200)
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('FINE_PROTOCOL',api.sha(DESIGN),flush=True)

def verify(d):
    pre.job.verify(api.read(pre.job.DESIGN));api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    old=api.read(pre.job.DESIGN)
    api.require(all(d[k]==old[k] for k in ('cases','numerical_gates','budget','minimum_gap_semantics')),'unchanged scientific contract')
    api.require(execute.__code__ is pre.wrapper.raw_execute.__code__ and execute.__globals__['codec'] is storage.codec and execute.__globals__['DESIGN']==DESIGN,'original integration, explicit new transport/lineage')
    api.require(candidate.trf_no_bounds.__code__ is candidate.prior.trf.trf_no_bounds.__code__ and candidate.trust.__code__ is candidate.prior.trf.solve_lsq_trust_region.__code__,'original optimizer algorithms')
    api.require(d['diagnostic_prior_recovery_steps']+d['diagnostic_maximum_new_steps']<=100000,'bounded ledger');storage.verify_bindings()

def seed(d):
    case=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125');_,oldcp=pre.stress_seed(api.read(pre.job.DESIGN))
    cp=job.parent.model.checkpoint(case['spec'],job.binding(d,case),oldcp,True)
    api.require(cp['state']==oldcp['state'],'original conditional seed state exactly preserved')
    return case,cp

def run():
    d=api.read(DESIGN);verify(d);a=api.read(AUTH)
    api.require(job.utc()<job.policy.utc(a['simulation_cutoff_utc'])-timedelta(hours=1),'clock reserve')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'one worker')
    api.require(shutil.disk_usage(RUN.anchor).free>a['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'disk reserve')
    info=pre.wrapper.affinity.bind(14);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False);stop=job.utc()+timedelta(seconds=d['diagnostic_wall_seconds'])
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop.isoformat(),'reserved_steps':7160,'prior_recovery_steps':45830,'design_sha256':api.sha(DESIGN),'affinity':info})
    total=0;reports=[]
    try:
        oracle=q.independent_file(held.FINE,api.sha(pre.job.DESIGN));case,initial=seed(d);job.commit(RUN/'initial.json',initial)
        job.parent.b.old.parent.configure();s=oracle['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0]
        import numpy as np
        args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction']);fn,*_=candidate.compiled.optimized_system(*args);fn(np.zeros(3*len(s['gaps_m'])))
        records={};states={}
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            geo=pre.prior.geometry()
            for label in ('serial','split_a','split_b'):
                cp=initial if label!='split_b' else records['split_a']['result']['checkpoint'];prefix=None if label!='split_b' else states['split_a'];cap=d['calls'][label];path=RUN/(label+'.json.xz')
                api.require(job.utc()<stop-timedelta(seconds=120),'bounded clock')
                job.commit(path.with_suffix('.launch.json'),{'reserved_steps':cap,'input_checkpoint_sha256':api.digest(cp),'utc':job.utc().isoformat()})
                with candidate.scope('compiled_direct'),pre.wrapper.baseline.repair.scope(job.parent.engine.runtime,True,stop.timestamp()):
                    rec,state,_,tx=execute(d,case,copy.deepcopy(cp),path,cap,prefix,stop.isoformat())
                n=len(rec['rows']);total+=n;job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':n,'cumulative_steps':total,'raw_sha256':api.sha(path)})
                prior_rows=None if prefix is None else records['split_a']['result']['history'];prior_ref=None if prefix is None else prefix.reference()
                tick=time.perf_counter();ind=q.independent_file(path,api.sha(DESIGN),prior_rows,prior_ref);read_s=time.perf_counter()-tick
                api.require(storage.base.raw_bytes(ind)==storage.base.raw_bytes(rec),'separate decoder exact full bytes')
                check=job.kernel.evaluate(ind,case['spec'],job.binding(d,case),cp,geo,api.sha(DESIGN),d['minimum_gap_semantics'])
                report={'label':label,'steps':n,'status':rec['result']['status'],'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':tx,'independent_read_seconds':read_s,'audit_seconds':check['audit_seconds'],'simulated_seconds':check['stop_s']-check['start_s'],'audit':check,'raw_sha256':api.sha(path)}
                reports.append(report);job.commit(path.with_suffix('.audit.json'),report);records[label]=rec;states[label]=state
                api.require(n==cap and rec['result']['status']=='paused_checkpoint' and check['passed'] and rec['result']['rejected']==0,'exact bounded healthy call')
                expected=oracle['rows'] if label=='serial' else oracle['rows'][:1790] if label=='split_a' else oracle['rows'][1790:3580]
                api.require(rec['rows']==expected,'bit-exact original fine rows')
                if label!='split_a':api.require(rec['result']['checkpoint']['state']==oracle['result']['checkpoint']['state'],'full original fine end state')
                print('FINE_EXACT',label,n,'compute',rec['compute_call_wall_s'],'transaction',tx,flush=True)
        verify(d);api.require(total==7160 and records['split_a']['rows']+records['split_b']['rows']==records['serial']['rows'] and records['serial']['result']['checkpoint']==records['split_b']['result']['checkpoint'],'exact restart ledger')
        r={'passed':True,'calls':reports,'new_accepted_steps':total,'cumulative_recovery_steps':45830+total,'exact_full_known_fine_rows_and_state':True,'exact_restart':True,'production_authorized':False,'complete_observation':False,'design_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()}}
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('FINE_PASS',total,flush=True)
    except Exception as e:
        paths=list(RUN.glob('*.launch.json'));unresolved=[str(x) for x in paths if not x.with_name(x.name.replace('.launch.json','.accounting.json')).exists()]
        known=sum(api.read(x)['accepted_steps'] for x in RUN.glob('*.accounting.json'))
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'known_new_steps':known,'unresolved':unresolved});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
