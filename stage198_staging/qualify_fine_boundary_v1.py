"""Exact restart and original non-null pending-trial boundary qualification.

The preceding fixed-cap oracle test remains failed. Only its saved healthy
serial record is reused, never restarted as production or overwritten.
"""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy, os, psutil, shutil, sys, time, traceback
import probe_exact_fine_v1 as p
api,q,job=p.api,p.q,p.job
DESIGN=p.DESIGN.with_name('boundary_protocol_01.json')
RUN=p.RUN.parent/'boundary_01'
OUT=p.OUT.parent/'boundary_01'
namespace=dict(p.execute.__globals__);namespace['DESIGN']=DESIGN
execute=FunctionType(p.execute.__code__,namespace,p.execute.__name__,p.execute.__defaults__,p.execute.__closure__)

def boundary(a,b):
    """Require exact all-state identity except the already identified stop tag."""
    x=a['result']['checkpoint']['state'];y=b['result']['checkpoint']['state']
    pending=y['pending_trial']
    api.require(a['result']['status']=='paused_checkpoint' and b['result']['status']=='incomplete_budget','specified two stopping mechanisms')
    api.require(x['pending_trial'] is None and set(pending)=={'attempt','dt_s','time_s'} and pending['attempt']==0 and pending['time_s']==y['t'],'unstarted old trial only')
    api.require(0<pending['dt_s']<=b['spec']['horizon_s']-y['t'],'original valid pending dt')
    api.require({k:v for k,v in x.items() if k!='pending_trial'}=={k:v for k,v in y.items() if k!='pending_trial'},'all other checkpoint fields exactly equal')
    api.require(a['rows']==b['rows'] and not a['result']['rejected'] and not b['result']['rejected'],'all accepted rows exact, no rejected trial')
    return pending

def verify(d):
    p.verify(api.read(p.DESIGN));api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new protocol binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    old=api.read(p.DESIGN)
    api.require(all(d[k]==old[k] for k in ('cases','numerical_gates','budget','minimum_gap_semantics')),'unchanged original scientific contract')
    api.require(d['diagnostic_prior_recovery_steps']==49410 and d['diagnostic_maximum_new_steps']==3676 and 49410+3676<=100000,'bounded exact ledger')
    api.require(execute.__code__ is p.execute.__code__ and execute.__globals__['DESIGN']==DESIGN,'unchanged integration code')

def prepare():
    d=copy.deepcopy(api.read(p.DESIGN));p.verify(d);d.pop('binding')
    serial=p.q.independent_file(p.RUN/'serial.json.xz',api.sha(p.DESIGN));oracle=q.independent_file(p.held.FINE,api.sha(p.pre.job.DESIGN))
    pending=boundary(serial,oracle)
    failed=api.read(p.OUT/'failure.json');api.require(failed['known_new_steps']==3580 and not failed['unresolved'],'failed predecessor ledger is closed')
    sources=[Path(__file__),p.ROOT/'stage119_staging/checkpoint_core_v3.py',p.ROOT/'stage167_staging/audit_paired_deadline_campaign_v3.py']
    inputs=[p.DESIGN,p.OUT/'failure.json',*[x for x in p.RUN.rglob('*') if x.is_file()]]
    d.update(stage='Stage198 exact stopped-trial boundary and partition restart',sources={**d['sources'],**{str(x):api.sha(x) for x in sources}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        calls={'split_a':1790,'split_b':1790,'old_pending_baseline':32,'old_pending_candidate':32,'paused_candidate':32},
        diagnostic_maximum_new_steps=3676,diagnostic_prior_recovery_steps=49410,old_fixed_cap_test_remains_failed=True,
        observed_pending_trial=pending,production_authorized=False,
        criterion='Split rows and full checkpoint equal saved fixed-cap serial; all three 32-step continuations equal in rows and full state, including first dt exactly old pending dt. Original full numerical audits on every record.')
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('BOUNDARY_PROTOCOL',api.sha(DESIGN),flush=True)

def rebind(d,case,cp):
    new=job.parent.model.checkpoint(case['spec'],job.binding(d,case),cp,True)
    api.require(new['state']==cp['state'],'diagnostic state not altered')
    return new

def run():
    d=api.read(DESIGN);verify(d);auth=api.read(p.AUTH)
    api.require(job.utc()<job.policy.utc(auth['simulation_cutoff_utc'])-timedelta(hours=1),'clock reserve')
    for proc in psutil.process_iter(['name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'one diagnostic worker')
    api.require(shutil.disk_usage(RUN.anchor).free>auth['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'disk reserve')
    info=p.pre.wrapper.affinity.bind(14);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False);stop=job.utc()+timedelta(minutes=20)
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop.isoformat(),'design_sha256':api.sha(DESIGN),'reserved_steps':3676,'affinity':info})
    total=0;reports=[];records={};states={}
    try:
        old=q.independent_file(p.held.FINE,api.sha(p.pre.job.DESIGN));serial=q.independent_file(p.RUN/'serial.json.xz',api.sha(p.DESIGN));pending=boundary(serial,old)
        case,initial=p.seed(d);job.commit(RUN/'initial.json',initial);job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            geo=p.pre.prior.geometry()
            for label,cap in d['calls'].items():
                if label=='split_a':cp=initial
                elif label=='split_b':cp=records['split_a']['result']['checkpoint']
                else:cp=rebind(d,case,(serial if label=='paused_candidate' else old)['result']['checkpoint'])
                prefix=states.get('split_a') if label=='split_b' else None
                path=RUN/(label+'.json.xz');api.require(job.utc()<stop-timedelta(seconds=120),'bounded clock')
                job.commit(path.with_suffix('.launch.json'),{'reserved_steps':cap,'input_checkpoint_sha256':api.digest(cp),'utc':job.utc().isoformat()})
                mode='baseline' if label=='old_pending_baseline' else 'compiled_direct'
                with p.candidate.scope(mode),p.pre.wrapper.baseline.repair.scope(job.parent.engine.runtime,True,stop.timestamp()):
                    rec,state,_,tx=execute(d,case,copy.deepcopy(cp),path,cap,prefix,stop.isoformat())
                n=len(rec['rows']);total+=n;job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':n,'cumulative_steps':total,'raw_sha256':api.sha(path)})
                hist=records['split_a']['result']['history'] if prefix is not None else None;ref=prefix.reference() if prefix is not None else None
                tick=time.perf_counter();ind=q.independent_file(path,api.sha(DESIGN),hist,ref);read_s=time.perf_counter()-tick
                api.require(p.storage.base.raw_bytes(ind)==p.storage.base.raw_bytes(rec),'separate decoder exact full bytes')
                audit=job.kernel.evaluate(ind,case['spec'],job.binding(d,case),cp,geo,api.sha(DESIGN),d['minimum_gap_semantics'])
                report={'label':label,'steps':n,'status':rec['result']['status'],'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':tx,'read_seconds':read_s,'audit':audit,'raw_sha256':api.sha(path)}
                job.commit(path.with_suffix('.audit.json'),report);reports.append(report);records[label]=rec;states[label]=state
                api.require(n==cap and rec['result']['status']=='paused_checkpoint' and audit['passed'] and rec['result']['rejected']==0,'unchanged numerical gates and exact call cap')
                if label.startswith('split_'):
                    expected=serial['rows'][:1790] if label=='split_a' else serial['rows'][1790:]
                    api.require(rec['rows']==expected,'bit-exact split trajectory')
                    if label=='split_b':api.require(rec['result']['checkpoint']['state']==serial['result']['checkpoint']['state'],'full split end state exact')
                else:
                    api.require(rec['rows'][0]['dt_s']==pending['dt_s'],'pending dt resumed or recomputed exactly')
                    baseline=records['old_pending_baseline']
                    api.require(rec['rows']==baseline['rows'] and rec['result']['checkpoint']['state']==baseline['result']['checkpoint']['state'],'baseline/candidate/pending/paused continuation exact')
                print('BOUNDARY_EXACT',label,n,flush=True)
        api.require(total==3676,'new accepted accounting');verify(d)
        result={'passed':True,'new_accepted_steps':total,'cumulative_recovery_steps':49410+total,'remaining_recovery_steps':100000-49410-total,'calls':reports,'observed_pending_trial':pending,'exact_partition_restart':True,'exact_pending_and_paused_baseline_candidate_continuations':True,'old_fixed_cap_test_remains_failed':True,'production_authorized':False,'complete_observations':0,'protocol_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()}}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('BOUNDARY_PASS',total,flush=True)
    except Exception as e:
        unresolved=[str(x) for x in RUN.glob('*.launch.json') if not x.with_name(x.name.replace('.launch.json','.accounting.json')).exists()]
        known=sum(api.read(x)['accepted_steps'] for x in RUN.glob('*.accounting.json'))
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'known_new_steps':known,'unresolved':unresolved});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
