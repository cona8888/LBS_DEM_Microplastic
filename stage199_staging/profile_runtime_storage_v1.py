"""Bounded zero-trajectory profile on sealed Stage198-compatible evidence."""
from pathlib import Path
from datetime import datetime, timezone
import cProfile, copy, os, pstats, psutil, shutil, sys, time, traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as held
import direct_trf_v2 as candidate
import fast_storage_v1 as storage
api,job,q=held.api,held.job,held.q
WORK=ROOT/'stage199_designs/eight_hour_optimization_20260926/contract_01.json'
DESIGN=WORK.with_name('profile_01.json')
RUN=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/profile_01')
OUT=ROOT/'stage199_evaluations/eight_hour_optimization_20260926/profile_01'
RAW=Path('D:/MATDEM_MICROPLASTIC/stage198_runs/direct_trf_20260926/fine_01/serial.json.xz')
RAWDESIGN=ROOT/'stage198_designs/direct_trf_20260926/fine_protocol_01.json'

def current():return datetime.now(timezone.utc)
def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'frozen profile protocol');api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    w=api.read(WORK);api.require(current()<datetime.fromisoformat(w['work_end_utc']),'work cutoff');api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS1')
    storage.verify_bindings()

def prepare():
    w=api.read(WORK);api.require(api.sha(w['prior_closure'])==w['prior_closure_sha256'] and api.sha(w['prior_authorization'])==w['prior_authorization_sha256'],'prior closure and authority')
    sources=[Path(__file__),Path(candidate.__file__),Path(candidate.prior.__file__),Path(candidate.compiled.__file__),Path(storage.__file__),Path(storage.canonical.__file__),Path(held.__file__)]
    inputs=[WORK,Path(w['prior_closure']),Path(w['prior_authorization']),RAWDESIGN,RAW,RAW.with_suffix('.seal.json'),held.FINE,held.FINE.with_suffix('.seal.json'),held.FIXTURES]
    p={'stage':'Stage199 zero-step runtime and storage profile','new_trajectory_steps':0,'held_outer_call_limit':80,'profile_wall_seconds':900,'cpu':14,'production_authorized':False,'sources':{str(x):api.sha(x) for x in sources},'inputs':{str(x):api.sha(x) for x in inputs}}
    p['binding']=api.digest(p);job.commit(DESIGN,p);verify(p);print('PROFILE_PROTOCOL',api.sha(DESIGN),flush=True)

def summarized(profile):
    stats=pstats.Stats(profile)
    rows=[]
    for (file,line,fn),(primitive,total,own,cumulative,callers) in stats.stats.items():
        rows.append({'file':file,'line':line,'function':fn,'primitive_calls':primitive,'total_calls':total,'own_seconds':own,'cumulative_seconds':cumulative})
    return {'total_profile_seconds':stats.total_tt,'total_calls':stats.total_calls,'top_own':sorted(rows,key=lambda x:x['own_seconds'],reverse=True)[:40],'top_cumulative':sorted(rows,key=lambda x:x['cumulative_seconds'],reverse=True)[:40]}

def run():
    p=api.read(DESIGN);verify(p);w=api.read(WORK)
    for proc in psutil.process_iter(['name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'one owned worker')
    api.require(shutil.disk_usage(RUN.anchor).free>w['minimum_disk_reserve_bytes']+4*storage.base.MAX_COMPRESSED,'disk reserve')
    affinity=held.pre.wrapper.affinity.bind(14);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':current().isoformat(),'protocol_sha256':api.sha(DESIGN),'new_trajectory_steps':0,'affinity':affinity})
    start=time.perf_counter()
    try:
        trials=held.trials();api.require(len(trials)<=p['held_outer_call_limit'],'bounded profile');job.parent.b.old.parent.configure();runtime=job.parent.engine.runtime
        end=min(current().timestamp()+p['profile_wall_seconds'],datetime.fromisoformat(w['work_end_utc']).timestamp());stop=datetime.fromtimestamp(end,timezone.utc).isoformat()
        import numpy as np
        s=trials[0][1]['inner_systems'][0];args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction']);f,*_=candidate.compiled.optimized_system(*args);f(np.zeros(3*len(s['gaps_m'])))
        profile=cProfile.Profile();answers=[]
        for label,t in trials:
            api.require(current().timestamp()<end,'bounded CPU profile clock')
            job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True;runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
            with candidate.scope('compiled_direct'),candidate.repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,stop,True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True):
                profile.enable();ans=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']));profile.disable()
            api.require(np.asarray(ans[0]).tobytes()==np.asarray(t['velocity'],dtype=np.float64).tobytes(),'known exact held velocity')
            answers.append({'label':label,'velocity_sha256':__import__('hashlib').sha256(np.asarray(ans[0]).tobytes()).hexdigest()})
        compute=summarized(profile);print('HELD_PROFILE_COMPLETE',len(answers),flush=True)
        rec=q.independent_file(RAW,api.sha(RAWDESIGN));before=storage.base.raw_bytes(rec);path=RUN/'serialization.json.xz'
        prof=cProfile.Profile();tick=time.perf_counter();prof.enable();seal,state=storage.codec.write_record(path,rec);prof.disable();write_s=time.perf_counter()-tick;write_profile=summarized(prof)
        prof=cProfile.Profile();tick=time.perf_counter();prof.enable();decoded,recovered=storage.codec.read_record(path,api.sha(RAWDESIGN));prof.disable();read_s=time.perf_counter()-tick
        exact=q.independent_file(path,api.sha(RAWDESIGN));api.require(storage.base.raw_bytes(decoded)==storage.base.raw_bytes(exact)==before and state==recovered,'lossless profile output')
        verify(p);r={'passed':True,'new_trajectory_steps':0,'compute_profile':compute,'storage_write_profile':write_profile,'storage_read_profile':summarized(prof),'profiled_write_seconds':write_s,'profiled_read_seconds':read_s,'held_answers':answers,'elapsed_seconds':time.perf_counter()-start,'protocol_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()},'claim':'Instrumented attribution only; profile times are not unbiased performance benchmarks or production qualification.'}
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('PROFILE_PASS',api.sha(OUT/'results.json'),flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
