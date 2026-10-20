"""Zero-trajectory held-pose comparison on difficult archived fine contacts."""
from pathlib import Path
from datetime import timedelta
import copy, os, sys, time, traceback, hashlib, inspect
import numpy as np
import direct_trf_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage196_staging'))
import qualify_performance_stack_v1 as pre
job,api,q=pre.job,pre.api,pre.q
import audit_early_semismooth_v1 as auditor
BASE='direct_trf_20260926'
DESIGN=ROOT/'stage198_designs'/BASE/'held_protocol_01.json'
OUT=ROOT/'stage198_evaluations'/BASE/'held_01'
AUTH=ROOT/'stage197_designs/deadline_extension_20260926/authorization_01.json'
FINE=Path('D:/MATDEM_MICROPLASTIC/stage197_runs/deadline_extension_20260926/continuation_01/conditional_fine.json.xz')
FIXTURES=ROOT/'stage194_evaluations/evidence_repair_20260924/early_semismooth_qualification_01/fixtures.json'

def trials():
    rec=q.independent_file(FINE,api.sha(job.DESIGN));fine=rec['contact_trial_trace']['detailed_trials']
    def difficulty(t):
        values=[]
        def walk(v):
            if isinstance(v,dict):
                if 'semismooth_nfev' in v:values.append(v['semismooth_nfev'])
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(t);return max(values,default=0)
    indices=sorted(set(np.linspace(0,len(fine)-1,48,dtype=int).tolist()+sorted(range(len(fine)),key=lambda i:difficulty(fine[i]),reverse=True)[:16]))
    old=api.read(FIXTURES)
    selected=[('archived_'+str(i),old[i]['fixture']['contact_trial_trace']['detailed_trials'][0]) for i in np.linspace(0,len(old)-1,16,dtype=int).tolist()]
    selected += [('fine_'+str(i),fine[i]) for i in indices]
    return selected

def prepare():
    job.verify(api.read(job.DESIGN));ts=trials()
    import scipy
    files=[Path(__file__),Path(candidate.__file__),Path(candidate.compiled.__file__),Path(candidate.constant.__file__),Path(candidate.lsq.__file__),Path(candidate.trf.__file__),Path(inspect.getmodule(candidate.trf.solve_lsq_trust_region).__file__)]
    prereq=ROOT/'stage197_evaluations/deadline_extension_20260926/deadline_check_01/results.json'
    inputs=[AUTH,job.DESIGN,FINE,FINE.with_suffix('.seal.json'),FIXTURES,prereq,prereq.parent/'completion.json']
    p={'stage':'Stage198 unchanged TRF narrow entry qualification','sources':{str(x):api.sha(x) for x in files},'inputs':{str(x):api.sha(x) for x in inputs},
       'labels':[x[0] for x in ts],'new_trajectory_steps':0,'maximum_outer_calls':3*len(ts),'modes':['baseline','direct','compiled_direct'],'wall_seconds':900,'logical_cpu':14,
       'criteria':'Bit-identical optimizer x/fun/jac/grad/cost/optimality, nfev/njev/status and outer velocity/health; independent original physical gates; no optimizer controls changed.',
       'scipy_version':scipy.__version__,'production_authorized':False,'recovery_steps_before':45830,'recovery_step_ceiling':100000,
       'trf_source_sha256':hashlib.sha256(inspect.getsource(candidate.trf.trf_no_bounds).encode()).hexdigest()}
    p['binding']=api.digest(p);job.commit(DESIGN,p);print('HELD_PROTOCOL',api.sha(DESIGN),len(ts),flush=True)

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'protocol identity');api.verify_mapping(p['sources']);api.verify_mapping(p['inputs']);job.verify(api.read(job.DESIGN))

def run():
    p=api.read(DESIGN);verify(p);ts=trials();api.require([x[0] for x in ts]==p['labels'],'frozen fixtures')
    for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):api.require(os.environ.get(k)=='1','BLAS1')
    import psutil
    api.require(not any(x.pid!=os.getpid() and 'python' in (x.info['name'] or '').lower() and 'matdem_microplastic' in ' '.join(x.info['cmdline'] or []).lower() for x in psutil.process_iter(['name','cmdline'])),'one owned held-pose worker')
    affinity=pre.wrapper.affinity.bind(14);stop=job.utc()+timedelta(seconds=p['wall_seconds']);end=stop.timestamp()
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop.isoformat(),'affinity':affinity,'protocol_sha256':api.sha(DESIGN),'new_trajectory_steps':0})
    job.parent.b.old.parent.configure();runtime=job.parent.engine.runtime;reports=[]
    def fingerprint(result):
        fields={}
        for k in ('x','fun','jac','grad','cost','optimality','nfev','njev','status','success'):
            a=np.asarray(result[k]);fields[k]={'shape':a.shape,'dtype':a.dtype.str,'bits':a.tobytes().hex()}
        return fields
    def call(t,mode):
        job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True;runtime.probe.RECOVERY.portfolio.set_recovery_mode(False);opts=[]
        with candidate.scope(mode):
            original=candidate.repair.prior.least_squares
            def observed(*args,**kwargs):
                result=original(*args,**kwargs);opts.append(fingerprint(result));return result
            candidate.repair.prior.least_squares=observed
            try:
                tick=time.perf_counter()
                with candidate.repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,stop.isoformat(),True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
                    ans=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                    fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':ans[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                        'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                        'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
                elapsed=time.perf_counter()-tick
            finally:candidate.repair.prior.least_squares=original
        check=auditor.evaluate(fixture,{'state':{'q':t['outer_inputs'][0]}})
        return ans,opts,check,elapsed
    try:
        # Warm strict compilation only, excluded from benchmark timings.
        s=ts[0][1]['inner_systems'][0];args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction'])
        f,*_=candidate.compiled.optimized_system(*args);f(np.zeros(3*len(s['gaps_m'])))
        for i,(label,t) in enumerate(ts):
            api.require(job.utc()<stop,'bounded held-pose clock');ref=None;row={'label':label,'timings':{},'optimizer_calls':{}}
            for mode in p['modes']:
                ans,opts,check,elapsed=call(t,mode);row['timings'][mode]=elapsed;row['optimizer_calls'][mode]=len(opts)
                signature=(ans[0].tobytes(),{k:v for k,v in ans[1].items() if k!='certificate_seconds'},opts)
                if ref is None:ref=signature
                api.require(signature==ref and check['passed'],'bit-exact full optimizer/outer solve and independent gates: '+label+' '+mode)
            reports.append(row)
            if i%16==0:print('HELD_EXACT',i,label,row['timings'],flush=True)
        sums={m:sum(x['timings'][m] for x in reports) for m in p['modes']};verify(p)
        result={'passed':True,'held_comparisons':reports,'timings':sums,'speedups_vs_constant':{m:sums['baseline']/sums[m] for m in p['modes']},'new_trajectory_steps':0,'exact_optimizer_results':True,'independent_physical_audits_passed':True,'protocol_sha256':api.sha(DESIGN),'production_authorized':False,'claim':'Held-pose implementation equivalence and timing only; no full trajectory or deadline qualification.'}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('HELD_PASS',result['speedups_vs_constant'],flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0,'completed':reports});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
